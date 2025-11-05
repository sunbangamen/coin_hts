"""
시뮬레이션 오케스트레이션 레이어

MarketDataService와 StrategyRunner를 통합하여 실시간 시뮬레이션을 조율합니다.
"""

import asyncio
import logging
from typing import Optional, List, Dict
from datetime import datetime

from backend.app.market_data.market_data_service import MarketDataService, get_market_data_service
from backend.app.simulation.strategy_runner import StrategyRunner, get_strategy_runner
from backend.app.simulation.position_manager import PositionManager, get_position_manager
from backend.app.simulation.websocket_server import (
    get_websocket_server,
    Signal as WSSignal,
    Position as WSPosition,
    PerformanceMetrics,
    EventType,
)
from backend.app.database import get_db
from backend.app.market_data.candle_builder import CandleData

logger = logging.getLogger(__name__)


class SimulationOrchestrator:
    """
    실시간 시뮬레이션 오케스트레이션

    MarketDataService -> StrategyRunner -> WebSocketServer
    의 데이터 흐름을 조율합니다.
    """

    def __init__(self):
        self.market_data_service: Optional[MarketDataService] = None
        self.strategy_runner: Optional[StrategyRunner] = None
        self.position_manager: Optional[PositionManager] = None
        self.ws_server = get_websocket_server()
        self.db = get_db()
        self.is_running = False
        self.session_id: Optional[str] = None

    async def start_simulation(
        self,
        symbols: List[str],
        strategies: Dict[str, List[Dict]],  # symbol -> [{"strategy_name": str, "params": dict}, ...]
        redis_client: Optional[object] = None,
    ) -> str:
        """
        시뮬레이션 시작

        Args:
            symbols: 모니터링할 심볼 목록 (예: ['KRW-BTC', 'KRW-ETH'])
            strategies: 각 심볼의 전략 설정
                {
                    'KRW-BTC': [
                        {'strategy_name': 'volume_zone_breakout', 'params': {...}},
                        {'strategy_name': 'volume_long_candle', 'params': {...}},
                    ],
                    ...
                }
            redis_client: Redis 클라이언트 (선택사항)

        Returns:
            session_id: 시뮬레이션 세션 ID

        Example:
            >>> orchestrator = SimulationOrchestrator()
            >>> session_id = await orchestrator.start_simulation(
            ...     symbols=['KRW-BTC'],
            ...     strategies={
            ...         'KRW-BTC': [
            ...             {'strategy_name': 'volume_zone_breakout', 'params': {'volume_window': 10}}
            ...         ]
            ...     }
            ... )
        """
        try:
            # 1. 세션 생성
            self.session_id = self.db.create_session()
            logger.info(f"Simulation session created: {self.session_id}")

            # 2. MarketDataService 시작
            self.market_data_service = MarketDataService(symbols, timeframe='1m', redis_client=redis_client)
            self.market_data_service.on_candle_complete = self._on_candle_complete

            # 백그라운드에서 시작
            asyncio.create_task(self.market_data_service.start())
            logger.info(f"MarketDataService started for symbols: {symbols}")

            # 3. StrategyRunner 초기화
            self.strategy_runner = get_strategy_runner()
            await self.strategy_runner.initialize(self.session_id)
            self.strategy_runner.set_signal_callback(self._on_signal)

            # 3-1. PositionManager 초기화
            self.position_manager = get_position_manager()
            await self.position_manager.initialize(self.session_id)

            # PositionManager 콜백 설정
            self.position_manager.set_position_opened_callback(self._on_position_opened)
            self.position_manager.set_position_closed_callback(self._on_position_closed)
            self.position_manager.set_position_updated_callback(self._on_position_updated)

            logger.info("PositionManager initialized")

            # 4. 전략 등록 및 초기화
            for symbol, strategy_configs in strategies.items():
                for config in strategy_configs:
                    strategy_name = config['strategy_name']
                    params = config.get('params', {})

                    # 전략 등록
                    await self.strategy_runner.register_strategy(symbol, strategy_name, params)

                    # 전략 초기화 (히스토리 로드)
                    await self.strategy_runner.initialize_strategy(symbol, strategy_name)

            await self.strategy_runner.start()
            logger.info(f"StrategyRunner started with {len(self.strategy_runner.strategies)} strategies")

            self.is_running = True

            return self.session_id

        except Exception as e:
            logger.error(f"Failed to start simulation: {e}")
            # 세션 상태 업데이트
            if self.session_id:
                self.db.update_session_status(self.session_id, 'STOPPED')
            raise

    async def stop_simulation(self) -> None:
        """시뮬레이션 중지"""
        try:
            self.is_running = False

            # 서비스 중지
            if self.market_data_service:
                await self.market_data_service.stop()

            if self.strategy_runner:
                await self.strategy_runner.stop()

            # PositionManager 정리
            if self.position_manager:
                # 포지션 요약 로깅
                summary = self.position_manager.get_position_summary()
                logger.info(
                    f"Final position summary: "
                    f"open_count={summary['open_positions_count']}, "
                    f"unrealized_pnl={summary['total_unrealized_pnl']}"
                )
                self.position_manager = None

            # 세션 상태 업데이트
            if self.session_id:
                self.db.update_session_status(self.session_id, 'STOPPED')

            logger.info(f"Simulation stopped: {self.session_id}")

        except Exception as e:
            logger.error(f"Error stopping simulation: {e}")

    async def _on_candle_complete(self, candle: CandleData) -> None:
        """
        캔들 완성 시 처리 (MarketDataService 콜백)

        캔들 → StrategyRunner 전달 + 포지션 미실현 손익 업데이트
        """
        try:
            if not self.strategy_runner or not self.is_running:
                return

            # 1. 포지션 미실현 손익 업데이트
            if self.position_manager:
                await self.position_manager.update_unrealized_pnl(candle)

            # 2. 전략 실행
            await self.strategy_runner.process_candle(candle)

        except Exception as e:
            logger.error(f"Error processing candle: {e}")

    async def _on_signal(self, signal, symbol: str, strategy_name: str) -> None:
        """
        신호 생성 시 처리 (StrategyRunner 콜백)

        신호 → PositionManager (포지션 진입/청산) → WebSocket 브로드캐스트
        """
        try:
            if not self.is_running:
                return

            # 1. PositionManager에 신호 전달 (포지션 진입/청산 처리)
            if self.position_manager:
                await self.position_manager.on_signal(signal, symbol, strategy_name)

            # 2. WebSocket으로 클라이언트에 브로드캐스트
            ws_signal = WSSignal(
                timestamp=signal.timestamp.isoformat(),
                symbol=symbol,
                strategy=strategy_name,
                side=signal.side,
                price=signal.price,
                confidence=signal.confidence,
            )

            await self.ws_server.broadcast_signal(ws_signal, symbol=symbol)
            logger.debug(f"Signal broadcasted: {symbol}:{strategy_name} {signal.side}")

        except Exception as e:
            logger.error(f"Error handling signal: {e}")

    async def _on_position_opened(self, position) -> None:
        """
        포지션 진입 시 처리 (PositionManager 콜백)

        포지션 정보를 WebSocket으로 브로드캐스트합니다.
        """
        try:
            # position_manager의 Position을 websocket_server의 Position으로 변환
            ws_position = WSPosition(
                position_id=position.position_id,
                symbol=position.symbol,
                strategy=position.strategy_name,  # strategy_name -> strategy
                entry_time=position.entry_time.isoformat(),
                entry_price=position.entry_price,
                quantity=position.quantity,
                current_price=position.current_price,
                unrealized_pnl=position.unrealized_pnl,
                unrealized_pnl_pct=position.unrealized_pnl_pct,
                status='OPEN',
            )

            await self.ws_server.broadcast_position(
                EventType.POSITION_OPENED,
                ws_position,
                symbol=position.symbol
            )
            logger.debug(f"Position opened broadcasted: {position.symbol}:{position.strategy_name}")

        except Exception as e:
            logger.error(f"Error broadcasting position_opened: {e}")

    async def _on_position_closed(self, position, realized_pnl: float, realized_pnl_pct: float) -> None:
        """
        포지션 청산 시 처리 (PositionManager 콜백)

        포지션 정보를 WebSocket으로 브로드캐스트하고,
        성과 스냅샷을 계산하여 브로드캐스트합니다.
        """
        try:
            # position_manager의 Position을 websocket_server의 Position으로 변환
            ws_position = WSPosition(
                position_id=position.position_id,
                symbol=position.symbol,
                strategy=position.strategy_name,  # strategy_name -> strategy
                entry_time=position.entry_time.isoformat(),
                entry_price=position.entry_price,
                quantity=position.quantity,
                current_price=position.current_price,
                unrealized_pnl=realized_pnl,  # 실현 손익으로 업데이트
                unrealized_pnl_pct=realized_pnl_pct,
                status='CLOSED',
            )

            await self.ws_server.broadcast_position(
                EventType.POSITION_CLOSED,
                ws_position,
                symbol=position.symbol
            )
            logger.debug(f"Position closed broadcasted: {position.symbol}:{position.strategy_name}")

            # 성과 스냅샷 계산 및 브로드캐스트
            await self._broadcast_performance_snapshot()

        except Exception as e:
            logger.error(f"Error broadcasting position_closed: {e}")

    async def _on_position_updated(self, position) -> None:
        """
        포지션 미실현 손익 업데이트 시 처리 (PositionManager 콜백)

        포지션 정보를 WebSocket으로 브로드캐스트합니다.
        """
        try:
            # position_manager의 Position을 websocket_server의 Position으로 변환
            ws_position = WSPosition(
                position_id=position.position_id,
                symbol=position.symbol,
                strategy=position.strategy_name,  # strategy_name -> strategy
                entry_time=position.entry_time.isoformat(),
                entry_price=position.entry_price,
                quantity=position.quantity,
                current_price=position.current_price,
                unrealized_pnl=position.unrealized_pnl,
                unrealized_pnl_pct=position.unrealized_pnl_pct,
                status='OPEN',
            )

            await self.ws_server.broadcast_position(
                EventType.POSITION_UPDATED,
                ws_position,
                symbol=position.symbol
            )

        except Exception as e:
            logger.error(f"Error broadcasting position_updated: {e}")

    async def _broadcast_performance_snapshot(self) -> None:
        """
        성과 스냅샷 계산 및 브로드캐스트

        거래 히스토리를 기반으로 성과 지표를 계산합니다.
        """
        try:
            if not self.position_manager or not self.db:
                return

            # 모든 거래 조회
            closed_trades = self.position_manager.get_closed_trades()

            if not closed_trades:
                # 거래가 없으면 초기값으로 스냅샷 생성
                metrics = PerformanceMetrics(
                    timestamp=datetime.utcnow().isoformat(),
                    total_pnl=0.0,
                    total_pnl_pct=0.0,
                    win_rate=0.0,
                    max_drawdown=0.0,
                    total_trades=0,
                    win_count=0,
                    lose_count=0,
                )
            else:
                # 성과 지표 계산
                total_pnl = sum(trade.get('realized_pnl', 0) for trade in closed_trades)
                total_trades = len(closed_trades)
                win_count = sum(1 for trade in closed_trades if trade.get('realized_pnl', 0) > 0)
                lose_count = sum(1 for trade in closed_trades if trade.get('realized_pnl', 0) < 0)
                break_even_count = total_trades - win_count - lose_count

                # 손익률 계산 (초기 자본 가정: 모든 거래의 진입가 합계)
                total_capital = sum(
                    trade.get('entry_price', 0) * trade.get('quantity', 0)
                    for trade in closed_trades
                )
                total_pnl_pct = (total_pnl / total_capital * 100) if total_capital > 0 else 0.0

                # 승률 계산
                win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0

                # 최대 낙폭 계산 (간단한 방식)
                cumulative_pnl = 0
                max_cumulative = 0
                max_drawdown = 0.0

                for trade in sorted(closed_trades, key=lambda x: x.get('exit_time', '')):
                    cumulative_pnl += trade.get('realized_pnl', 0)
                    if cumulative_pnl > max_cumulative:
                        max_cumulative = cumulative_pnl
                    drawdown = max_cumulative - cumulative_pnl
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown

                metrics = PerformanceMetrics(
                    timestamp=datetime.utcnow().isoformat(),
                    total_pnl=round(total_pnl, 2),
                    total_pnl_pct=round(total_pnl_pct, 2),
                    win_rate=round(win_rate, 2),
                    max_drawdown=round(max_drawdown, 2),
                    total_trades=total_trades,
                    win_count=win_count,
                    lose_count=lose_count,
                )

            # 성과 스냅샷 브로드캐스트
            await self.ws_server.broadcast_performance(metrics)
            logger.debug(f"Performance snapshot broadcasted: PnL={metrics.total_pnl}, WinRate={metrics.win_rate}%")

        except Exception as e:
            logger.error(f"Error broadcasting performance snapshot: {e}")

    def get_simulation_status(self) -> Dict:
        """시뮬레이션 상태 조회"""
        return {
            'session_id': self.session_id,
            'is_running': self.is_running,
            'market_data_status': self.market_data_service.get_status() if self.market_data_service else None,
            'strategy_runner_status': self.strategy_runner.get_status() if self.strategy_runner else None,
            'websocket_clients': self.ws_server.get_connected_clients_count(),
        }


# 전역 오케스트레이터 인스턴스
_orchestrator: Optional[SimulationOrchestrator] = None


def get_orchestrator() -> SimulationOrchestrator:
    """전역 SimulationOrchestrator 인스턴스 반환"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SimulationOrchestrator()
    return _orchestrator


async def close_orchestrator() -> None:
    """오케스트레이터 종료"""
    global _orchestrator
    if _orchestrator and _orchestrator.is_running:
        await _orchestrator.stop_simulation()
    _orchestrator = None
