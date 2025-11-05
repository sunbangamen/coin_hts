"""
업비트 WebSocket 클라이언트

실시간 체결 데이터를 수신하고 캔들로 집계합니다.
"""

import json
import logging
import asyncio
from typing import Optional, Callable, List
from datetime import datetime
import websockets
from websockets.client import WebSocketClientProtocol

logger = logging.getLogger(__name__)


class UpbitWebSocketClient:
    """
    업비트 WebSocket 클라이언트

    실시간 체결 데이터를 수신하여 콜백함수로 전달합니다.
    """

    # 업비트 API 엔드포인트
    WS_URL = "wss://api.upbit.com/websocket/v1"

    # 재연결 설정
    RECONNECT_DELAY = 5  # 초
    MAX_RECONNECT_ATTEMPTS = 10

    def __init__(self, symbols: List[str]):
        """
        Args:
            symbols: 구독할 심볼 목록 (예: ['KRW-BTC', 'KRW-ETH'])
        """
        self.symbols = symbols
        self.ws: Optional[WebSocketClientProtocol] = None
        self.is_connected = False
        self.is_running = False
        self.reconnect_attempts = 0
        self.on_trade_callback: Optional[Callable] = None

    def set_trade_callback(self, callback: Callable) -> None:
        """
        체결 데이터 수신 시 호출될 콜백 함수 설정

        콜백 함수 시그니처:
            async def callback(symbol: str, price: float, volume: float, timestamp: datetime) -> None:
                ...
        """
        self.on_trade_callback = callback

    async def connect(self) -> None:
        """WebSocket 연결"""
        try:
            self.ws = await websockets.connect(self.WS_URL)
            self.is_connected = True
            self.reconnect_attempts = 0
            logger.info(f"Upbit WebSocket connected")

            # 구독 신청
            await self._subscribe()
        except Exception as e:
            logger.error(f"Failed to connect to Upbit WebSocket: {e}")
            self.is_connected = False
            raise

    async def _subscribe(self) -> None:
        """심볼 구독"""
        if not self.ws:
            raise RuntimeError("WebSocket not connected")

        # 체결 데이터 구독
        subscribe_message = {
            "type": "subscribe",
            "codes": [f"{symbol}" for symbol in self.symbols],
            "isOnlyRealtime": True
        }

        try:
            await self.ws.send(json.dumps(subscribe_message))
            logger.info(f"Subscribed to {len(self.symbols)} symbols: {self.symbols}")
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
            raise

    async def disconnect(self) -> None:
        """WebSocket 연결 해제"""
        if self.ws:
            try:
                await self.ws.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")

        self.is_connected = False
        logger.info("Upbit WebSocket disconnected")

    async def _handle_message(self, message: str) -> None:
        """메시지 처리"""
        try:
            data = json.loads(message)

            # 체결 데이터 처리
            if data.get('type') == 'trade':
                await self._process_trade(data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def _process_trade(self, data: dict) -> None:
        """체결 데이터 처리"""
        try:
            symbol = data.get('code')
            price = float(data.get('trade_price', 0))
            volume = float(data.get('trade_volume', 0))
            timestamp = data.get('trade_timestamp', 0)

            # 타임스탬프를 datetime으로 변환 (밀리초 단위)
            ts = datetime.fromtimestamp(timestamp / 1000.0)

            # 콜백 호출
            if self.on_trade_callback:
                await self.on_trade_callback(symbol, price, volume, ts)
        except Exception as e:
            logger.error(f"Error processing trade data: {e}")

    async def start(self) -> None:
        """WebSocket 시작"""
        self.is_running = True

        while self.is_running:
            try:
                # 연결 확인
                if not self.is_connected:
                    await self.connect()

                # 메시지 수신
                async for message in self.ws:
                    if isinstance(message, bytes):
                        message = message.decode('utf-8')
                    await self._handle_message(message)

            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                self.is_connected = False

                # 재연결 시도
                if self.reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS:
                    self.reconnect_attempts += 1
                    logger.info(f"Reconnecting in {self.RECONNECT_DELAY}s... (attempt {self.reconnect_attempts})")
                    await asyncio.sleep(self.RECONNECT_DELAY)
                else:
                    logger.error("Max reconnection attempts reached")
                    self.is_running = False

            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}")
                self.is_connected = False

                if self.reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS:
                    self.reconnect_attempts += 1
                    logger.info(f"Reconnecting in {self.RECONNECT_DELAY}s... (attempt {self.reconnect_attempts})")
                    await asyncio.sleep(self.RECONNECT_DELAY)
                else:
                    logger.error("Max reconnection attempts reached")
                    self.is_running = False

    async def stop(self) -> None:
        """WebSocket 중지"""
        self.is_running = False
        await self.disconnect()

    def subscribe_symbols(self, symbols: List[str]) -> None:
        """추가 심볼 구독"""
        self.symbols.extend(symbols)
        logger.info(f"Added symbols to subscription: {symbols}")

    def unsubscribe_symbols(self, symbols: List[str]) -> None:
        """심볼 구독 해제"""
        for symbol in symbols:
            if symbol in self.symbols:
                self.symbols.remove(symbol)
        logger.info(f"Removed symbols from subscription: {symbols}")


# Mock WebSocket 클라이언트 (테스트/개발용)
class MockUpbitWebSocketClient(UpbitWebSocketClient):
    """테스트용 Mock WebSocket 클라이언트"""

    def __init__(self, symbols: List[str]):
        super().__init__(symbols)
        self.trade_queue: asyncio.Queue = asyncio.Queue()

    async def connect(self) -> None:
        """Mock 연결 (즉시 성공)"""
        self.is_connected = True
        logger.info("Mock WebSocket connected")

    async def add_mock_trade(self, symbol: str, price: float, volume: float) -> None:
        """테스트용 체결 데이터 추가"""
        await self.trade_queue.put({
            'symbol': symbol,
            'price': price,
            'volume': volume,
            'timestamp': datetime.now()
        })

    async def start(self) -> None:
        """Mock 시작"""
        self.is_running = True

        while self.is_running:
            try:
                trade = await asyncio.wait_for(self.trade_queue.get(), timeout=1.0)

                if self.on_trade_callback:
                    await self.on_trade_callback(
                        trade['symbol'],
                        trade['price'],
                        trade['volume'],
                        trade['timestamp']
                    )
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in mock WebSocket loop: {e}")
                self.is_running = False
