"""
시뮬레이션 오케스트레이션 레이어

MarketDataService와 StrategyRunner를 통합하여 실시간 시뮬레이션을 조율합니다.
"""

import asyncio
import logging
from typing import Optional, List, Dict

from backend.app.market_data.market_data_service import MarketDataService, get_market_data_service
from backend.app.simulation.strategy_runner import StrategyRunner, get_strategy_runner
from backend.app.simulation.websocket_server import (
    get_websocket_server,
    Signal as WSSignal,
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

            # 세션 상태 업데이트
            if self.session_id:
                self.db.update_session_status(self.session_id, 'STOPPED')

            logger.info(f"Simulation stopped: {self.session_id}")

        except Exception as e:
            logger.error(f"Error stopping simulation: {e}")

    async def _on_candle_complete(self, candle: CandleData) -> None:
        """
        캔들 완성 시 처리 (MarketDataService 콜백)

        캔들 → StrategyRunner 전달
        """
        try:
            if not self.strategy_runner or not self.is_running:
                return

            # 전략 실행
            await self.strategy_runner.process_candle(candle)

        except Exception as e:
            logger.error(f"Error processing candle: {e}")

    async def _on_signal(self, signal, symbol: str, strategy_name: str) -> None:
        """
        신호 생성 시 처리 (StrategyRunner 콜백)

        신호 → WebSocket 브로드캐스트
        """
        try:
            if not self.is_running:
                return

            # WebSocket으로 클라이언트에 브로드캐스트
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
            logger.error(f"Error broadcasting signal: {e}")

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
