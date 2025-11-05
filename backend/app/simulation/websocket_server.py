"""
실시간 시뮬레이션 WebSocket 서버

프론트엔드에 신호, 포지션, 성과 지표를 실시간으로 전송합니다.
JWT 기반 인증과 재연결 로직을 포함합니다.

표준 WebSocket 스펙 (RFC 6455)을 따릅니다.
"""

import json
import logging
import asyncio
from typing import Dict, Set, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from enum import Enum
import uuid

try:
    import jwt
except ImportError:
    jwt = None

import websockets
from websockets.server import WebSocketServerProtocol, serve as ws_serve

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """WebSocket 이벤트 타입"""
    SIGNAL_CREATED = "signal_created"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_UPDATED = "position_updated"
    PERFORMANCE_SNAPSHOT = "performance_snapshot"
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_CLOSED = "connection_closed"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    SUBSCRIBE_ACK = "subscribe_ack"
    UNSUBSCRIBE_ACK = "unsubscribe_ack"


@dataclass
class Signal:
    """신호 데이터"""
    timestamp: str
    symbol: str
    strategy: str
    side: str  # 'BUY' or 'SELL'
    price: float
    confidence: float

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Position:
    """포지션 데이터"""
    position_id: int
    symbol: str
    strategy: str
    entry_time: str
    entry_price: float
    quantity: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    status: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PerformanceMetrics:
    """성과 지표"""
    timestamp: str
    total_pnl: float
    total_pnl_pct: float
    win_rate: float
    max_drawdown: float
    total_trades: int
    win_count: int
    lose_count: int

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ClientConnection:
    """클라이언트 연결 정보"""
    client_id: str
    websocket: WebSocketServerProtocol
    auth_info: Dict = field(default_factory=dict)
    subscribed_symbols: Set[str] = field(default_factory=set)
    last_event_id: Optional[str] = None
    connected_at: datetime = field(default_factory=datetime.utcnow)


class SimulationWebSocketServer:
    """
    실시간 시뮬레이션 WebSocket 서버

    Features:
    - JWT 기반 인증
    - 역할 기반 접근 제어 (RBAC)
    - 클라이언트 연결 관리
    - 이벤트 브로드캐스트
    - 재연결 및 상태 복구 (이벤트 히스토리 기반)
    - 표준 WebSocket 스펙 준수

    이벤트 히스토리:
    - 각 심볼별 최근 이벤트 1000개 보존
    - 재연결 시 마지막 이벤트 ID 이후의 이벤트 재전송
    """

    # JWT 설정
    SECRET_KEY = "your-secret-key-change-in-production"
    TOKEN_EXPIRY_HOURS = 24

    # 하트비트 간격 (초)
    HEARTBEAT_INTERVAL = 30

    # 이벤트 히스토리 설정
    MAX_EVENTS_PER_SYMBOL = 1000  # 심볼당 최대 이벤트 수
    MAX_GLOBAL_EVENTS = 10000     # 전체 최대 이벤트 수

    def __init__(self, host: str = "0.0.0.0", port: int = 8001):
        self.host = host
        self.port = port
        self.clients: Dict[str, ClientConnection] = {}
        self.event_history: Dict[str, list] = {}  # symbol -> [event, ...]
        self.global_event_list: list = []  # 모든 이벤트 순서대로 저장
        self.is_running = False
        self.server = None

    def _generate_client_id(self) -> str:
        """클라이언트 ID 생성"""
        return str(uuid.uuid4())

    async def _authenticate_client(self, websocket: WebSocketServerProtocol) -> Optional[Dict]:
        """
        클라이언트 JWT 토큰 검증

        프로토콜: 첫 메시지는 다음 형식이어야 함
        {
            "type": "auth",
            "token": "jwt-token-here"
        }
        """
        try:
            # 첫 메시지: 인증 토큰 수신 (타임아웃: 10초)
            message_json = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            message = json.loads(message_json)

            if message.get('type') != 'auth':
                logger.warning(f"Expected auth message, got: {message.get('type')}")
                return None

            if not jwt:
                logger.error("JWT library not installed")
                return None

            token = message.get('token')
            if not token:
                logger.warning("No token provided")
                return None

            # JWT 토큰 검증
            try:
                payload = jwt.decode(token, self.SECRET_KEY, algorithms=['HS256'])
                logger.info(f"Client authenticated: user_id={payload.get('user_id')}, role={payload.get('role')}")
                return payload
            except jwt.ExpiredSignatureError:
                logger.warning("Token expired")
                return None
            except jwt.InvalidTokenError as e:
                logger.warning(f"Invalid token: {e}")
                return None

        except asyncio.TimeoutError:
            logger.warning("Authentication timeout")
            return None
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in auth message")
            return None
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            return None

    async def _check_role_permission(self, auth_info: Dict, permission: str) -> bool:
        """역할 기반 권한 검사"""
        if not auth_info:
            return False

        role = auth_info.get('role', 'viewer')

        # 간단한 권한 검사 로직
        permissions = {
            'admin': ['read', 'write', 'delete'],
            'trader': ['read', 'write'],
            'viewer': ['read']
        }

        return permission in permissions.get(role, [])

    async def _handle_client(self, websocket: WebSocketServerProtocol, path: str) -> None:
        """클라이언트 연결 처리"""
        client_id = self._generate_client_id()
        addr = websocket.remote_address

        logger.info(f"New client connection: {addr} (id: {client_id})")

        try:
            # 인증
            auth_info = await self._authenticate_client(websocket)
            if not auth_info:
                await self._send_event(
                    websocket, EventType.ERROR,
                    {'message': 'Authentication failed', 'code': 'AUTH_FAILED'}
                )
                return

            # 클라이언트 연결 정보 저장
            client_conn = ClientConnection(
                client_id=client_id,
                websocket=websocket,
                auth_info=auth_info
            )
            self.clients[client_id] = client_conn

            # 연결 확립 메시지 전송
            await self._send_event(
                websocket, EventType.CONNECTION_ESTABLISHED,
                {
                    'client_id': client_id,
                    'user': auth_info.get('user_id'),
                    'role': auth_info.get('role'),
                    'timestamp': datetime.utcnow().isoformat()
                }
            )

            # 하트비트 태스크 시작
            heartbeat_task = asyncio.create_task(self._send_heartbeat(websocket))

            try:
                # 클라이언트 메시지 수신 루프
                async for message_json in websocket:
                    try:
                        message = json.loads(message_json)
                        await self._handle_message(client_id, message)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from client {client_id}")
                        await self._send_event(
                            websocket, EventType.ERROR,
                            {'message': 'Invalid JSON', 'code': 'INVALID_JSON'}
                        )

            finally:
                heartbeat_task.cancel()

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client connection closed: {addr}")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
            await self._send_event(
                websocket, EventType.ERROR,
                {'message': str(e), 'code': 'INTERNAL_ERROR'}
            )
        finally:
            # 클라이언트 정리
            if client_id in self.clients:
                del self.clients[client_id]
            logger.info(f"Client disconnected: {client_id}")

    async def _send_heartbeat(self, websocket: WebSocketServerProtocol) -> None:
        """정기적으로 하트비트 전송"""
        try:
            while True:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                await self._send_event(
                    websocket, EventType.HEARTBEAT,
                    {'timestamp': datetime.utcnow().isoformat()}
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")

    async def _handle_message(self, client_id: str, message: Dict) -> None:
        """클라이언트 메시지 처리"""
        try:
            if client_id not in self.clients:
                logger.warning(f"Client {client_id} not found")
                return

            client_conn = self.clients[client_id]
            websocket = client_conn.websocket
            message_type = message.get('type')

            if message_type == 'subscribe':
                # 심볼 구독
                symbols = message.get('symbols', [])

                # 권한 검사
                if not await self._check_role_permission(client_conn.auth_info, 'read'):
                    await self._send_event(
                        websocket, EventType.ERROR,
                        {'message': 'Permission denied', 'code': 'PERMISSION_DENIED'}
                    )
                    return

                client_conn.subscribed_symbols.update(symbols)
                await self._send_event(
                    websocket, EventType.SUBSCRIBE_ACK,
                    {'symbols': symbols, 'timestamp': datetime.utcnow().isoformat()}
                )
                logger.debug(f"Client {client_id} subscribed to {symbols}")

            elif message_type == 'unsubscribe':
                # 심볼 구독 해제
                symbols = message.get('symbols', [])
                for symbol in symbols:
                    client_conn.subscribed_symbols.discard(symbol)
                await self._send_event(
                    websocket, EventType.UNSUBSCRIBE_ACK,
                    {'symbols': symbols, 'timestamp': datetime.utcnow().isoformat()}
                )
                logger.debug(f"Client {client_id} unsubscribed from {symbols}")

            elif message_type == 'ping':
                # 핑 응답
                await self._send_event(
                    websocket, EventType.HEARTBEAT,
                    {'type': 'pong', 'timestamp': datetime.utcnow().isoformat()}
                )

            elif message_type == 'sync':
                # 상태 동기화 (재연결 시)
                last_event_id = message.get('last_event_id')
                symbols = message.get('symbols', [])

                logger.info(f"Client {client_id} requesting sync from event {last_event_id} for symbols {symbols}")

                # 마지막 이벤트 ID 이후의 이벤트 찾아 재전송
                await self._resend_history_events(websocket, client_id, last_event_id, symbols)

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            client_conn = self.clients.get(client_id)
            if client_conn:
                await self._send_event(
                    client_conn.websocket, EventType.ERROR,
                    {'message': str(e), 'code': 'MESSAGE_HANDLE_ERROR'}
                )

    async def _resend_history_events(self, websocket: WebSocketServerProtocol,
                                     client_id: str, last_event_id: Optional[str],
                                     symbols: list) -> None:
        """
        마지막 이벤트 ID 이후의 이벤트를 찾아 재전송

        재연결 시 클라이언트가 놓친 이벤트를 복구합니다.

        Args:
            websocket: 클라이언트 WebSocket
            client_id: 클라이언트 ID
            last_event_id: 마지막 수신한 이벤트 ID
                - None: 전체 히스토리 전송
                - 유효한 ID: 해당 ID 이후 이벤트만 전송
                - 만료된 ID (히스토리에서 찾지 못함): 선택지 A/B에 따라 처리
            symbols: 재전송할 심볼 목록 (빈 리스트면 모든 심볼)

        히스토리 동기화 정책:
        ┌─────────────────────────────────────────────────────────────┐
        │ Policy: SAFETY MODE (Choice A) - 권장                        │
        │                                                              │
        │ last_event_id를 찾지 못하는 경우:                            │
        │ → 전체 히스토리를 처음부터 재전송 (start_sending = True 강제)│
        │ → 클라이언트가 최신 상태를 최대한 복구                       │
        │                                                              │
        │ Choice B로 전환하려면: 아래 주석된 코드 참고                 │
        └─────────────────────────────────────────────────────────────┘
        """
        try:
            resent_count = 0
            event_found = False
            start_sending = (last_event_id is None)  # last_event_id가 없으면 처음부터 전송

            # 1단계: 히스토리에서 last_event_id 찾기
            for event in self.global_event_list:
                event_id = event.get('event_id')

                # last_event_id 찾으면 다음부터 전송
                if event_id == last_event_id:
                    event_found = True
                    start_sending = True
                    continue

                if not start_sending:
                    continue

                # 심볼 필터링
                event_symbol = event.get('data', {}).get('symbol')
                if symbols and event_symbol and event_symbol not in symbols:
                    continue

                # 이벤트 재전송
                await websocket.send(json.dumps(event, default=str))
                resent_count += 1

            # 2단계: last_event_id를 찾지 못한 경우 처리
            # ============================================
            # CHOICE A: Safety Mode (기본 선택지)
            # last_event_id가 지정되었으나 히스토리에서 찾지 못한 경우
            # → 히스토리가 만료되었을 가능성이 높음
            # → 전체 히스토리를 재전송하여 최신 상태 복구
            if last_event_id is not None and not event_found and resent_count == 0:
                logger.warning(
                    f"Last event ID '{last_event_id}' not found in history (possibly truncated). "
                    f"Resending full history for client {client_id}"
                )

                # 전체 히스토리를 처음부터 재전송
                for event in self.global_event_list:
                    # 심볼 필터링
                    event_symbol = event.get('data', {}).get('symbol')
                    if symbols and event_symbol and event_symbol not in symbols:
                        continue

                    await websocket.send(json.dumps(event, default=str))
                    resent_count += 1

                # 정책 안내 메시지 전송
                await self._send_event(
                    websocket, EventType.HEARTBEAT,
                    {
                        'type': 'sync_fallback',
                        'reason': 'history_truncated',
                        'message': 'Last event not found; sending full history',
                        'resent_count': resent_count,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                )

            # ============================================
            # CHOICE B: Explicit Error (선택지 B)
            # 아래 주석을 해제하면 명시적 오류로 전환 가능
            # elif last_event_id is not None and not event_found:
            #     logger.error(
            #         f"Last event ID '{last_event_id}' not found in history. "
            #         f"Client {client_id} may need full resync"
            #     )
            #
            #     await self._send_event(
            #         websocket, EventType.ERROR,
            #         {
            #             'code': 'SYNC_FAILED',
            #             'reason': 'event_not_found',
            #             'message': 'Requested event not in history; please request full sync',
            #             'last_event_id': last_event_id,
            #             'timestamp': datetime.utcnow().isoformat()
            #         }
            #     )
            #     return
            # ============================================

            # 동기화 완료 메시지 전송
            # Choice A (fallback) 경로에서도 sync_complete을 보내야 하므로 resent_count > 0도 포함
            if last_event_id is None or event_found or resent_count > 0:
                await self._send_event(
                    websocket, EventType.HEARTBEAT,
                    {
                        'type': 'sync_complete',
                        'resent_count': resent_count,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                )

            logger.info(f"Sync complete for client {client_id}: resent {resent_count} events")

        except Exception as e:
            logger.error(f"Error resending history events: {e}")
            await self._send_event(
                websocket, EventType.ERROR,
                {'message': str(e), 'code': 'SYNC_FAILED', 'reason': 'internal_error'}
            )

    def _save_to_event_history(self, event_id: str, event_type: EventType, data: Dict, symbol: Optional[str] = None) -> None:
        """이벤트를 히스토리에 저장"""
        event = {
            'event_id': event_id,
            'type': event_type.value,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }

        # 전역 이벤트 리스트에 추가
        self.global_event_list.append(event)
        if len(self.global_event_list) > self.MAX_GLOBAL_EVENTS:
            self.global_event_list.pop(0)

        # 심볼별 히스토리에 추가 (신호/포지션 이벤트만)
        if symbol and event_type in (EventType.SIGNAL_CREATED, EventType.POSITION_OPENED,
                                    EventType.POSITION_CLOSED, EventType.POSITION_UPDATED):
            if symbol not in self.event_history:
                self.event_history[symbol] = []

            self.event_history[symbol].append(event)
            if len(self.event_history[symbol]) > self.MAX_EVENTS_PER_SYMBOL:
                self.event_history[symbol].pop(0)

    async def _send_event(self, websocket: WebSocketServerProtocol,
                         event_type: EventType, data: Dict, symbol: Optional[str] = None) -> str:
        """
        WebSocket을 통해 이벤트 전송

        Returns:
            event_id: 생성된 이벤트 ID
        """
        try:
            event_id = str(uuid.uuid4())
            message = {
                'event_id': event_id,
                'type': event_type.value,
                'data': data,
                'timestamp': datetime.utcnow().isoformat()
            }

            await websocket.send(json.dumps(message, default=str))
            logger.debug(f"Sent event: {event_type.value} (id: {event_id})")

            # 히스토리에 저장
            self._save_to_event_history(event_id, event_type, data, symbol)

            return event_id

        except websockets.exceptions.ConnectionClosed:
            logger.debug("Connection closed while sending event")
        except Exception as e:
            logger.error(f"Failed to send event: {e}")

        return None

    async def broadcast_signal(self, signal: Signal, symbol: Optional[str] = None) -> None:
        """신호를 구독한 클라이언트에 브로드캐스트"""
        disconnected = []

        for client_id, client_conn in list(self.clients.items()):
            try:
                # 심볼 구독 여부 확인
                if symbol and symbol not in client_conn.subscribed_symbols:
                    continue

                event_id = await self._send_event(
                    client_conn.websocket, EventType.SIGNAL_CREATED,
                    signal.to_dict(),
                    symbol=symbol
                )

                # 클라이언트 last_event_id 갱신
                if event_id:
                    client_conn.last_event_id = event_id

            except Exception as e:
                logger.error(f"Failed to broadcast signal to {client_id}: {e}")
                disconnected.append(client_id)

        # 끊긴 연결 제거
        for client_id in disconnected:
            if client_id in self.clients:
                del self.clients[client_id]

    async def broadcast_position(self, event_type: EventType, position: Position,
                                symbol: Optional[str] = None) -> None:
        """포지션 정보를 구독한 클라이언트에 브로드캐스트"""
        disconnected = []

        for client_id, client_conn in list(self.clients.items()):
            try:
                # 심볼 구독 여부 확인
                if symbol and symbol not in client_conn.subscribed_symbols:
                    continue

                event_id = await self._send_event(
                    client_conn.websocket, event_type,
                    position.to_dict(),
                    symbol=symbol
                )

                # 클라이언트 last_event_id 갱신
                if event_id:
                    client_conn.last_event_id = event_id

            except Exception as e:
                logger.error(f"Failed to broadcast position to {client_id}: {e}")
                disconnected.append(client_id)

        # 끊긴 연결 제거
        for client_id in disconnected:
            if client_id in self.clients:
                del self.clients[client_id]

    async def broadcast_performance(self, metrics: PerformanceMetrics) -> None:
        """성과 지표를 모든 클라이언트에 브로드캐스트"""
        disconnected = []

        for client_id, client_conn in list(self.clients.items()):
            try:
                event_id = await self._send_event(
                    client_conn.websocket, EventType.PERFORMANCE_SNAPSHOT,
                    metrics.to_dict()
                )

                # 클라이언트 last_event_id 갱신
                if event_id:
                    client_conn.last_event_id = event_id

            except Exception as e:
                logger.error(f"Failed to broadcast performance to {client_id}: {e}")
                disconnected.append(client_id)

        # 끊긴 연결 제거
        for client_id in disconnected:
            if client_id in self.clients:
                del self.clients[client_id]

    def generate_token(self, user_id: str, role: str = 'viewer') -> str:
        """JWT 토큰 생성"""
        if not jwt:
            raise RuntimeError("JWT library not installed")

        payload = {
            'user_id': user_id,
            'role': role,
            'exp': datetime.utcnow() + timedelta(hours=self.TOKEN_EXPIRY_HOURS),
            'iat': datetime.utcnow()
        }

        return jwt.encode(payload, self.SECRET_KEY, algorithm='HS256')

    async def start(self) -> None:
        """WebSocket 서버 시작"""
        self.is_running = True

        try:
            self.server = await ws_serve(self._handle_client, self.host, self.port)
            logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
            await self.server.wait_closed()
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            self.is_running = False
            raise

    async def stop(self) -> None:
        """WebSocket 서버 중지"""
        self.is_running = False

        # 모든 클라이언트 연결 종료
        for client_conn in list(self.clients.values()):
            try:
                await client_conn.websocket.close()
            except Exception as e:
                logger.error(f"Error closing client connection: {e}")

        if self.server:
            self.server.close()
            await self.server.wait_closed()

        logger.info("WebSocket server stopped")

    def get_connected_clients_count(self) -> int:
        """연결된 클라이언트 수 반환"""
        return len(self.clients)


# 전역 서버 인스턴스
_ws_server: Optional[SimulationWebSocketServer] = None


def get_websocket_server(host: str = "0.0.0.0", port: int = 8001) -> SimulationWebSocketServer:
    """전역 WebSocket 서버 획득"""
    global _ws_server

    if _ws_server is None:
        _ws_server = SimulationWebSocketServer(host, port)

    return _ws_server


async def close_websocket_server() -> None:
    """WebSocket 서버 종료"""
    global _ws_server
    if _ws_server and _ws_server.is_running:
        await _ws_server.stop()
    _ws_server = None
