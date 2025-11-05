"""
포지션 관리 모듈

거래 신호를 수신하여 가상 포지션을 관리하고 손익을 계산합니다.
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime

from backend.app.database import DatabaseManager, get_db
from backend.app.market_data.candle_builder import CandleData
from backend.app.strategies.base import Signal

logger = logging.getLogger(__name__)


class Position:
    """포지션 정보"""

    def __init__(
        self,
        position_id: int,
        symbol: str,
        strategy_name: str,
        entry_time: datetime,
        entry_price: float,
        quantity: float,
        fee_amount: float = 0,
    ):
        self.position_id = position_id
        self.symbol = symbol
        self.strategy_name = strategy_name
        self.entry_time = entry_time
        self.entry_price = entry_price
        self.quantity = quantity
        self.fee_amount = fee_amount
        self.current_price = entry_price
        self.unrealized_pnl = 0.0
        self.unrealized_pnl_pct = 0.0

    def update_price(self, current_price: float) -> None:
        """현재 가격으로 미실현 손익 업데이트"""
        self.current_price = current_price
        self.unrealized_pnl = (
            self.quantity * (current_price - self.entry_price) - self.fee_amount
        )
        if self.entry_price * self.quantity > 0:
            self.unrealized_pnl_pct = (
                (self.unrealized_pnl / (self.entry_price * self.quantity)) * 100
            )

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'strategy_name': self.strategy_name,
            'entry_time': self.entry_time.isoformat(),
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'current_price': self.current_price,
            'unrealized_pnl': round(self.unrealized_pnl, 2),
            'unrealized_pnl_pct': round(self.unrealized_pnl_pct, 2),
            'fee_amount': self.fee_amount,
        }


class PositionManager:
    """
    포지션 관리 엔진

    거래 신호를 수신하여 가상 포지션을 진입/청산하고,
    손익을 계산하고 추적합니다.
    """

    def __init__(self):
        """PositionManager 초기화"""
        self.db: Optional[DatabaseManager] = None
        self.session_id: Optional[str] = None
        self.positions: Dict[str, Position] = {}  # (symbol, strategy_name) -> Position
        self.fee_rate = 0.001  # 거래 수수료 0.1%
        self.slippage_rate = 0.0002  # 슬리피지 0.02%
        self.on_position_opened = None  # 포지션 진입 콜백
        self.on_position_closed = None  # 포지션 청산 콜백
        self.on_position_updated = None  # 포지션 미실현 손익 업데이트 콜백

    async def initialize(self, session_id: str) -> None:
        """
        포지션 매니저 초기화

        Args:
            session_id: 시뮬레이션 세션 ID
        """
        try:
            self.db = get_db()
            self.session_id = session_id
            logger.info(f"PositionManager initialized (session: {session_id})")
        except Exception as e:
            logger.error(f"Failed to initialize PositionManager: {e}")
            raise

    def set_position_opened_callback(self, callback) -> None:
        """
        포지션 진입 시 호출될 콜백 설정

        Args:
            callback: async def callback(position: Position) -> None
        """
        self.on_position_opened = callback

    def set_position_closed_callback(self, callback) -> None:
        """
        포지션 청산 시 호출될 콜백 설정

        Args:
            callback: async def callback(position: Position, realized_pnl: float, realized_pnl_pct: float) -> None
        """
        self.on_position_closed = callback

    def set_position_updated_callback(self, callback) -> None:
        """
        포지션 미실현 손익 업데이트 시 호출될 콜백 설정

        Args:
            callback: async def callback(position: Position) -> None
        """
        self.on_position_updated = callback

    async def on_signal(
        self, signal: Signal, symbol: str, strategy_name: str, current_candle: Optional[CandleData] = None
    ) -> None:
        """
        신호 수신 시 처리

        Args:
            signal: 생성된 신호
            symbol: 거래 심볼
            strategy_name: 전략 이름
            current_candle: 신호 발생 시의 캔들 데이터 (선택사항)
        """
        try:
            # 현재 캔들이 없으면 신호가 발생한 캔들의 종가로 체결가 사용
            execution_price = current_candle.close if current_candle else signal.price

            if signal.side == 'BUY':
                await self.enter_position(
                    symbol=symbol,
                    strategy_name=strategy_name,
                    entry_price=execution_price,
                    timestamp=signal.timestamp,
                )
            elif signal.side == 'SELL':
                await self.close_position(
                    symbol=symbol,
                    strategy_name=strategy_name,
                    exit_price=execution_price,
                    timestamp=signal.timestamp,
                )

        except Exception as e:
            logger.error(f"Error handling signal for {symbol}:{strategy_name}: {e}")

    async def enter_position(
        self,
        symbol: str,
        strategy_name: str,
        entry_price: float,
        timestamp: datetime,
    ) -> Optional[int]:
        """
        포지션 진입

        Args:
            symbol: 거래 심볼
            strategy_name: 전략 이름
            entry_price: 진입 가격
            timestamp: 진입 시간

        Returns:
            포지션 ID (성공 시) 또는 None (실패 시)
        """
        try:
            key = f"{symbol}:{strategy_name}"

            # 이미 오픈 포지션이 있는지 확인
            if key in self.positions:
                logger.warning(
                    f"Position already open for {key}, ignoring BUY signal"
                )
                return None

            # 수수료 계산 (거래액 기준)
            # 수량을 고정값으로 설정 (실제로는 포트폴리오 크기에 따라 조정 가능)
            quantity = 0.1  # 0.1 단위로 거래 (예: 0.1 BTC, 1 ETH 등)
            trade_amount = entry_price * quantity
            fee_amount = trade_amount * self.fee_rate

            # DB에 포지션 저장
            if not self.db:
                raise RuntimeError("Database not initialized")

            position_id = self.db.insert_position(
                symbol=symbol,
                strategy_name=strategy_name,
                entry_time=timestamp,
                entry_price=entry_price,
                quantity=quantity,
                fee_amount=fee_amount,
            )

            # 메모리에 포지션 저장
            position = Position(
                position_id=position_id,
                symbol=symbol,
                strategy_name=strategy_name,
                entry_time=timestamp,
                entry_price=entry_price,
                quantity=quantity,
                fee_amount=fee_amount,
            )
            self.positions[key] = position

            # 포지션 진입 콜백 실행
            if self.on_position_opened:
                try:
                    await self.on_position_opened(position)
                except Exception as e:
                    logger.error(f"Error in position_opened callback: {e}")

            logger.info(
                f"Position opened: {key} @ {entry_price} (qty: {quantity}, "
                f"fee: {fee_amount:.2f}) [id: {position_id}]"
            )

            return position_id

        except Exception as e:
            logger.error(f"Failed to enter position {symbol}:{strategy_name}: {e}")
            return None

    async def close_position(
        self,
        symbol: str,
        strategy_name: str,
        exit_price: float,
        timestamp: datetime,
        slippage_amount: Optional[float] = None,
    ) -> Optional[int]:
        """
        포지션 청산

        Args:
            symbol: 거래 심볼
            strategy_name: 전략 이름
            exit_price: 청산 가격
            timestamp: 청산 시간
            slippage_amount: 슬리피지 금액 (선택사항, None이면 자동 계산)

        Returns:
            거래 ID (성공 시) 또는 None (실패 시)
        """
        try:
            key = f"{symbol}:{strategy_name}"

            # 오픈 포지션이 있는지 확인
            if key not in self.positions:
                logger.warning(f"No open position for {key}, ignoring SELL signal")
                return None

            position = self.positions[key]

            # 슬리피지 자동 계산 (미제공 시)
            if slippage_amount is None:
                if self.slippage_rate <= 0 or position.quantity <= 0:
                    slippage_amount = 0.0
                else:
                    slippage_amount = exit_price * position.quantity * self.slippage_rate
                logger.debug(
                    f"Auto-calculated slippage for {key}: {slippage_amount:.2f} "
                    f"(rate={self.slippage_rate*100:.4f}%)"
                )
            else:
                if slippage_amount < 0:
                    logger.warning(f"Negative slippage amount for {key}, setting to 0")
                    slippage_amount = 0.0

            # 실현 손익 계산
            realized_pnl = (
                position.quantity * (exit_price - position.entry_price)
                - position.fee_amount
                - slippage_amount
            )
            if position.entry_price * position.quantity > 0:
                realized_pnl_pct = (
                    (realized_pnl / (position.entry_price * position.quantity)) * 100
                )
            else:
                realized_pnl_pct = 0.0

            # DB에 포지션 종료 기록
            if not self.db:
                raise RuntimeError("Database not initialized")

            self.db.update_position_on_close(
                position_id=position.position_id,
                exit_time=timestamp,
                exit_price=exit_price,
                slippage_amount=slippage_amount,
            )

            # 거래 기록 저장
            trade_id = self.db.insert_trade(
                symbol=symbol,
                strategy_name=strategy_name,
                entry_time=position.entry_time,
                entry_price=position.entry_price,
                exit_time=timestamp,
                exit_price=exit_price,
                quantity=position.quantity,
                realized_pnl=realized_pnl,
                realized_pnl_pct=realized_pnl_pct,
                fee_amount=position.fee_amount,
                slippage_amount=slippage_amount,
            )

            # 메모리에서 포지션 제거
            del self.positions[key]

            # 포지션 청산 콜백 실행
            if self.on_position_closed:
                try:
                    await self.on_position_closed(position, realized_pnl, realized_pnl_pct)
                except Exception as e:
                    logger.error(f"Error in position_closed callback: {e}")

            logger.info(
                f"Position closed: {key} @ {exit_price} "
                f"(PnL: {realized_pnl:.2f}, {realized_pnl_pct:.2f}%) [trade_id: {trade_id}]"
            )

            return trade_id

        except Exception as e:
            logger.error(f"Failed to close position {symbol}:{strategy_name}: {e}")
            return None

    async def update_unrealized_pnl(self, candle: CandleData) -> None:
        """
        미실현 손익 업데이트

        캔들 데이터를 수신하여 해당 심볼의 모든 오픈 포지션의
        미실현 손익을 업데이트합니다.

        Args:
            candle: 캔들 데이터
        """
        try:
            # 해당 심볼의 모든 포지션 업데이트
            for key, position in list(self.positions.items()):
                if position.symbol == candle.symbol:
                    position.update_price(candle.close)

                    # DB에도 업데이트
                    if self.db:
                        self.db.update_position_unrealized_pnl(
                            position_id=position.position_id,
                            current_price=candle.close,
                        )

                    # 포지션 업데이트 콜백 실행
                    if self.on_position_updated:
                        try:
                            await self.on_position_updated(position)
                        except Exception as e:
                            logger.error(f"Error in position_updated callback for {key}: {e}")

        except Exception as e:
            logger.error(f"Error updating unrealized PnL for {candle.symbol}: {e}")

    def get_open_positions(
        self, symbol: Optional[str] = None, strategy_name: Optional[str] = None
    ) -> List[Dict]:
        """
        오픈 포지션 조회

        Args:
            symbol: 심볼 필터 (선택사항)
            strategy_name: 전략명 필터 (선택사항)

        Returns:
            포지션 정보 딕셔너리 목록
        """
        result = []

        for key, position in self.positions.items():
            if symbol and position.symbol != symbol:
                continue
            if strategy_name and position.strategy_name != strategy_name:
                continue

            result.append(position.to_dict())

        return sorted(result, key=lambda x: x['entry_time'], reverse=True)

    def get_closed_trades(
        self,
        symbol: Optional[str] = None,
        strategy_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """
        클로즈된 거래 조회

        Args:
            symbol: 심볼 필터 (선택사항)
            strategy_name: 전략명 필터 (선택사항)
            limit: 조회 개수 제한

        Returns:
            거래 정보 딕셔너리 목록
        """
        if not self.db:
            return []

        try:
            query = "SELECT * FROM simulation_trades WHERE 1=1"
            params = []

            if symbol:
                query += " AND symbol = %s"
                params.append(symbol)

            if strategy_name:
                query += " AND strategy_name = %s"
                params.append(strategy_name)

            query += " ORDER BY exit_time DESC LIMIT %s"
            params.append(limit)

            with self.db.get_conn() as conn:
                from psycopg2.extras import RealDictCursor

                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, params)
                    trades = cur.fetchall()

            # ISO 형식 날짜로 변환
            result = []
            for trade in trades:
                trade_dict = dict(trade)
                if 'entry_time' in trade_dict and trade_dict['entry_time']:
                    trade_dict['entry_time'] = trade_dict['entry_time'].isoformat()
                if 'exit_time' in trade_dict and trade_dict['exit_time']:
                    trade_dict['exit_time'] = trade_dict['exit_time'].isoformat()
                if 'hold_duration' in trade_dict and trade_dict['hold_duration']:
                    trade_dict['hold_duration'] = str(trade_dict['hold_duration'])
                # 소수점 반올림
                for key in ['entry_price', 'exit_price', 'realized_pnl', 'realized_pnl_pct', 'fee_amount', 'slippage_amount']:
                    if key in trade_dict and isinstance(trade_dict[key], float):
                        trade_dict[key] = round(trade_dict[key], 2)
                result.append(trade_dict)

            return result

        except Exception as e:
            logger.error(f"Error retrieving closed trades: {e}")
            return []

    def get_position_summary(self) -> Dict:
        """
        포지션 요약 통계

        Returns:
            포지션 통계 정보
        """
        total_unrealized_pnl = sum(
            position.unrealized_pnl for position in self.positions.values()
        )
        open_count = len(self.positions)

        return {
            'open_positions_count': open_count,
            'total_unrealized_pnl': round(total_unrealized_pnl, 2),
            'positions_by_symbol': self._get_positions_by_symbol(),
        }

    def _get_positions_by_symbol(self) -> Dict[str, int]:
        """심볼별 오픈 포지션 개수"""
        by_symbol = {}

        for position in self.positions.values():
            by_symbol[position.symbol] = by_symbol.get(position.symbol, 0) + 1

        return by_symbol


# 전역 포지션 매니저 인스턴스
_position_manager: Optional[PositionManager] = None


def get_position_manager() -> PositionManager:
    """전역 PositionManager 인스턴스 반환"""
    global _position_manager
    if _position_manager is None:
        _position_manager = PositionManager()
    return _position_manager


async def close_position_manager() -> None:
    """PositionManager 종료"""
    global _position_manager
    if _position_manager:
        # 필요한 정리 작업 수행
        _position_manager = None
