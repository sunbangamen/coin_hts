"""
실시간 전략 실행 엔진

마켓 데이터 서비스에서 캔들을 수신하여 전략을 실행하고 신호를 생성합니다.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime

from backend.app.database import DatabaseManager, get_db
from backend.app.market_data.candle_builder import CandleData
from backend.app.strategies.base import Strategy, Signal
from backend.app.strategy_factory import StrategyFactory

logger = logging.getLogger(__name__)


class StrategyConfig:
    """전략 설정"""

    def __init__(self, symbol: str, strategy_name: str, params: Dict):
        """
        Args:
            symbol: 거래 심볼 (예: 'KRW-BTC')
            strategy_name: 전략 이름 (예: 'VolumeZoneBreakoutStrategy')
            params: 전략 파라미터 딕셔너리
        """
        self.symbol = symbol
        self.strategy_name = strategy_name
        self.params = params
        self.strategy_instance: Optional[Strategy] = None
        self.is_initialized = False

    def __repr__(self) -> str:
        return f"StrategyConfig({self.symbol}:{self.strategy_name})"


class StrategyRunner:
    """
    실시간 전략 실행 엔진

    여러 전략을 관리하고 실시간 캔들 데이터를 처리합니다.
    """

    def __init__(self):
        """StrategyRunner 초기화"""
        self.strategies: Dict[str, StrategyConfig] = {}  # (symbol, strategy_name) -> StrategyConfig
        self.db: Optional[DatabaseManager] = None
        self.is_running = False
        self.on_signal: Optional[Callable] = None  # 신호 생성 시 콜백
        self.session_id: Optional[str] = None

    def set_signal_callback(self, callback: Callable) -> None:
        """
        신호 생성 콜백 설정

        콜백 함수 시그니처:
            async def callback(signal: Signal, symbol: str, strategy_name: str) -> None:
        """
        self.on_signal = callback

    async def initialize(self, session_id: str) -> None:
        """
        전략 엔진 초기화

        Args:
            session_id: 시뮬레이션 세션 ID
        """
        try:
            self.db = get_db()
            self.session_id = session_id
            logger.info(f"StrategyRunner initialized (session: {session_id})")
        except Exception as e:
            logger.error(f"Failed to initialize StrategyRunner: {e}")
            raise

    async def register_strategy(self, symbol: str, strategy_name: str, params: Dict) -> None:
        """
        전략 등록

        Args:
            symbol: 거래 심볼
            strategy_name: 전략 이름
            params: 전략 파라미터
        """
        try:
            # 전략 인스턴스 생성 (StrategyFactory 사용)
            strategy_instance = StrategyFactory.create(strategy_name)

            # 설정 저장
            config = StrategyConfig(symbol, strategy_name, params)
            config.strategy_instance = strategy_instance

            key = f"{symbol}:{strategy_name}"
            self.strategies[key] = config

            logger.info(f"Strategy registered: {key}")

        except Exception as e:
            logger.error(f"Failed to register strategy {symbol}:{strategy_name}: {e}")
            raise

    async def initialize_strategy(self, symbol: str, strategy_name: str) -> None:
        """
        전략 초기화 (히스토리 로드)

        Args:
            symbol: 거래 심볼
            strategy_name: 전략 이름
        """
        try:
            key = f"{symbol}:{strategy_name}"
            if key not in self.strategies:
                raise ValueError(f"Strategy not registered: {key}")

            config = self.strategies[key]
            if config.is_initialized:
                logger.debug(f"Strategy already initialized: {key}")
                return

            # 전략의 최소 윈도우 크기 조회
            min_window = config.strategy_instance.min_history_window
            logger.debug(f"Loading {min_window} candles for {symbol}:{strategy_name}")

            # 히스토리 로드 (Postgres에서)
            if not self.db:
                raise RuntimeError("Database not initialized")

            # 최신 캔들부터 min_window개만 조회 (DESC)
            recent_candles = await self.db.fetch_all_async(
                """
                SELECT timestamp, open, high, low, close, volume
                FROM market_candles
                WHERE symbol = %s AND timeframe = '1m'
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (symbol, min_window)
            )

            if not recent_candles:
                logger.warning(f"No historical candles found for {symbol}")
                # 히스토리 없이도 진행 가능 (실시간만 수집)
                config.is_initialized = True
                return

            # 전략에 히스토리 로드
            import pandas as pd
            df = pd.DataFrame(recent_candles)
            df['timestamp'] = pd.to_datetime(df['timestamp'])

            # DESC로 가져온 데이터를 ASC로 다시 정렬 (전략은 과거→현재 순서로 데이터를 받아야 함)
            df = df.sort_values('timestamp').reset_index(drop=True)

            # 초기화 데이터 범위 로깅
            earliest_timestamp = df['timestamp'].min()
            latest_timestamp = df['timestamp'].max()
            logger.debug(
                f"Strategy initialized with {len(recent_candles)} candles for {symbol}:{strategy_name} "
                f"(range: {earliest_timestamp} to {latest_timestamp}): {key}"
            )

            config.strategy_instance.initialize_with_history(df, config.params)
            config.is_initialized = True

            logger.info(f"Strategy initialized with {len(recent_candles)} candles: {key}")

        except Exception as e:
            logger.error(f"Failed to initialize strategy {symbol}:{strategy_name}: {e}")
            raise

    async def process_candle(self, candle: CandleData) -> None:
        """
        캔들 처리

        이 캔들을 사용하는 모든 전략을 실행합니다.

        Args:
            candle: 완성된 캔들 데이터
        """
        try:
            symbol = candle.symbol

            # 이 심볼을 사용하는 모든 전략 실행
            for key, config in self.strategies.items():
                if not config.symbol == symbol:
                    continue

                if not config.is_initialized:
                    logger.warning(f"Strategy not initialized: {key}")
                    continue

                # 전략 실행
                signal = config.strategy_instance.process_candle({
                    'timestamp': candle.timestamp,
                    'open': candle.open,
                    'high': candle.high,
                    'low': candle.low,
                    'close': candle.close,
                    'volume': candle.volume,
                })

                # 신호 생성 시 저장 및 브로드캐스트
                if signal:
                    await self._on_signal_generated(signal, symbol, config.strategy_name)

        except Exception as e:
            logger.error(f"Error processing candle for {candle.symbol}: {e}")

    async def _on_signal_generated(self, signal: Signal, symbol: str, strategy_name: str) -> None:
        """
        신호 생성 시 처리

        Args:
            signal: 생성된 신호
            symbol: 거래 심볼
            strategy_name: 전략 이름
        """
        try:
            logger.info(
                f"Signal generated: {symbol}:{strategy_name} {signal.side} "
                f"@{signal.price} (confidence: {signal.confidence})"
            )

            # 1. DB에 저장
            if self.db:
                signal_id = self.db.insert_signal(
                    symbol,
                    strategy_name,
                    signal.timestamp,
                    signal.side,
                    signal.price,
                    signal.confidence
                )
                logger.debug(f"Signal saved to DB (id: {signal_id})")

            # 2. 콜백 호출 (WebSocket 브로드캐스트)
            if self.on_signal:
                await self.on_signal(signal, symbol, strategy_name)

        except Exception as e:
            logger.error(f"Error handling signal: {e}")

    async def start(self) -> None:
        """엔진 시작"""
        self.is_running = True
        logger.info("StrategyRunner started")

    async def stop(self) -> None:
        """엔진 중지"""
        self.is_running = False
        logger.info("StrategyRunner stopped")

    def get_strategies(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        등록된 전략 목록 조회

        Args:
            symbol: 심볼 필터 (선택사항)

        Returns:
            전략 정보 딕셔너리 목록
        """
        result = []

        for key, config in self.strategies.items():
            if symbol and config.symbol != symbol:
                continue

            result.append({
                'symbol': config.symbol,
                'strategy_name': config.strategy_name,
                'params': config.params,
                'is_initialized': config.is_initialized,
            })

        return result

    def get_status(self) -> Dict:
        """엔진 상태 조회"""
        return {
            'is_running': self.is_running,
            'session_id': self.session_id,
            'strategy_count': len(self.strategies),
            'strategies': self.get_strategies(),
        }


# 전역 엔진 인스턴스
_strategy_runner: Optional[StrategyRunner] = None


def get_strategy_runner() -> StrategyRunner:
    """전역 StrategyRunner 인스턴스 반환"""
    global _strategy_runner
    if _strategy_runner is None:
        _strategy_runner = StrategyRunner()
    return _strategy_runner


async def close_strategy_runner() -> None:
    """StrategyRunner 종료"""
    global _strategy_runner
    if _strategy_runner and _strategy_runner.is_running:
        await _strategy_runner.stop()
    _strategy_runner = None
