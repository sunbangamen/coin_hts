"""
시장 데이터 수집 서비스

WebSocket 클라이언트, 캔들 빌더, 데이터베이스를 조율하여
실시간 데이터를 수집하고 저장합니다.
"""

import asyncio
import logging
from typing import List, Optional, Callable, Dict
from datetime import datetime

from backend.app.database import DatabaseManager, get_db
from backend.app.market_data.candle_builder import CandleBuilder, CandleData
from backend.app.market_data.upbit_websocket import UpbitWebSocketClient

logger = logging.getLogger(__name__)


class MarketDataService:
    """
    실시간 시장 데이터 수집 및 처리 서비스

    - WebSocket으로 체결 데이터 수신
    - 캔들 집계 (기본 1분봉)
    - Postgres에 영속 저장
    - Redis Stream으로 브로드캐스트
    """

    def __init__(self, symbols: List[str], timeframe: str = '1m', redis_client: Optional[object] = None):
        """
        Args:
            symbols: 구독할 심볼 목록
            timeframe: 캔들 타임프레임 (기본: '1m')
            redis_client: Redis 클라이언트 (의존성 주입, 선택사항)
        """
        self.symbols = symbols
        self.timeframe = timeframe
        self.ws_client = UpbitWebSocketClient(symbols)
        self.candle_builders: Dict[str, CandleBuilder] = {}
        self.db: Optional[DatabaseManager] = None
        self.redis_client = redis_client  # Redis 클라이언트 의존성 주입
        self.is_running = False
        self.on_candle_complete: Optional[Callable] = None

    async def initialize(self) -> None:
        """서비스 초기화"""
        try:
            # 데이터베이스 연결
            self.db = get_db()

            # 캔들 빌더 초기화
            for symbol in self.symbols:
                self.candle_builders[symbol] = CandleBuilder(symbol, self.timeframe)

                # 히스토리 로드 (최근 200개)
                await self._load_history(symbol)

            # WebSocket 콜백 설정
            self.ws_client.set_trade_callback(self._on_trade)

            logger.info(f"MarketDataService initialized with {len(self.symbols)} symbols")
        except Exception as e:
            logger.error(f"Failed to initialize MarketDataService: {e}")
            raise

    async def _load_history(self, symbol: str, max_retries: int = 3) -> None:
        """과거 데이터 로드 (재시도 로직 포함)"""
        import pandas as pd

        for attempt in range(max_retries):
            try:
                if not self.db:
                    logger.error("Database not initialized")
                    return

                # Postgres에서 최근 캔들 로드 (비동기)
                recent_candles = await self.db.fetch_all_async(
                    """
                    SELECT timestamp, open, high, low, close, volume
                    FROM market_candles
                    WHERE symbol = %s AND timeframe = %s
                    ORDER BY timestamp ASC
                    LIMIT 200
                    """,
                    (symbol, self.timeframe)
                )

                if recent_candles:
                    # DataFrame으로 변환
                    df = pd.DataFrame(recent_candles)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])

                    # 캔들 빌더에 히스토리 로드
                    self.candle_builders[symbol].load_from_dataframe(df)
                    logger.info(f"Loaded {len(recent_candles)} historical candles for {symbol}")
                    return

                else:
                    logger.info(f"No historical candles found for {symbol}")
                    return

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 지수 백오프: 1s, 2s, 4s
                    logger.warning(f"Failed to load history for {symbol} (attempt {attempt + 1}/{max_retries}): {e}")
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed to load history for {symbol} after {max_retries} attempts: {e}")

    async def _on_trade(self, symbol: str, price: float, volume: float, timestamp: datetime) -> None:
        """
        체결 데이터 수신 시 콜백

        Args:
            symbol: 심볼
            price: 체결가
            volume: 거래량
            timestamp: 체결 시간 (UTC)
        """
        try:
            if symbol not in self.candle_builders:
                logger.warning(f"Unknown symbol: {symbol}")
                return

            builder = self.candle_builders[symbol]

            # 캔들 집계
            completed_candle = builder.add_trade(timestamp, price, volume)

            # 완성된 캔들이 있으면 저장
            if completed_candle:
                await self._save_candle(completed_candle)

        except Exception as e:
            logger.error(f"Error in trade callback: {e}")

    async def _save_candle(self, candle: CandleData) -> None:
        """캔들을 저장하고 브로드캐스트"""
        try:
            if not self.db:
                logger.error("Database not initialized")
                return

            # Postgres에 저장 (비동기, 전용 메서드 사용)
            candle_id = await self.db.insert_candle_async(
                candle.symbol,
                candle.timeframe,
                candle.timestamp,
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume
            )

            logger.debug(f"Saved candle: {candle.symbol} {candle.timestamp} (id: {candle_id})")

            # Redis Stream으로 브로드캐스트
            await self._broadcast_to_redis(candle)

            # 콜백 호출
            if self.on_candle_complete:
                await self.on_candle_complete(candle)

        except Exception as e:
            logger.error(f"Failed to save candle: {e}")

    async def _broadcast_to_redis(self, candle: CandleData) -> None:
        """Redis Stream으로 캔들 브로드캐스트"""
        try:
            if not self.redis_client:
                logger.debug("Redis client not configured, skipping broadcast")
                return

            # Redis Stream 키: market_candles:{symbol}:{timeframe}
            stream_key = f"market_candles:{candle.symbol}:{candle.timeframe}"

            # Redis Stream에 추가 (비동기 처리)
            await asyncio.to_thread(
                self.redis_client.xadd,
                stream_key,
                {
                    'timestamp': candle.timestamp.isoformat(),
                    'open': str(candle.open),
                    'high': str(candle.high),
                    'low': str(candle.low),
                    'close': str(candle.close),
                    'volume': str(candle.volume)
                }
            )

            logger.debug(f"Broadcasted candle to Redis: {stream_key}")

        except AttributeError:
            logger.warning("Redis client does not have xadd method")
        except Exception as e:
            logger.error(f"Failed to broadcast to Redis: {e}")

    async def start(self) -> None:
        """서비스 시작"""
        try:
            await self.initialize()
            self.is_running = True

            # WebSocket 시작
            await self.ws_client.start()

        except Exception as e:
            logger.error(f"Failed to start MarketDataService: {e}")
            self.is_running = False
            raise

    async def stop(self) -> None:
        """서비스 중지"""
        self.is_running = False
        await self.ws_client.stop()
        logger.info("MarketDataService stopped")

    def add_symbol(self, symbol: str) -> None:
        """심볼 추가"""
        if symbol not in self.symbols:
            self.symbols.append(symbol)
            self.candle_builders[symbol] = CandleBuilder(symbol, self.timeframe)
            self.ws_client.subscribe_symbols([symbol])
            logger.info(f"Added symbol: {symbol}")

    def remove_symbol(self, symbol: str) -> None:
        """심볼 제거"""
        if symbol in self.symbols:
            self.symbols.remove(symbol)
            if symbol in self.candle_builders:
                del self.candle_builders[symbol]
            self.ws_client.unsubscribe_symbols([symbol])
            logger.info(f"Removed symbol: {symbol}")

    def get_current_candle(self, symbol: str) -> Optional[Dict]:
        """현재 구성 중인 캔들 조회"""
        if symbol not in self.candle_builders:
            return None

        candle = self.candle_builders[symbol].get_current_candle()
        return candle.to_dict() if candle else None

    def get_status(self) -> Dict:
        """서비스 상태 조회"""
        return {
            'is_running': self.is_running,
            'is_connected': self.ws_client.is_connected,
            'symbols': self.symbols,
            'timeframe': self.timeframe,
            'current_candles': {
                symbol: self.get_current_candle(symbol)
                for symbol in self.symbols
            }
        }


# 전역 서비스 인스턴스
_market_data_service: Optional[MarketDataService] = None


def get_market_data_service(symbols: List[str] = None, timeframe: str = '1m') -> MarketDataService:
    """전역 시장 데이터 서비스 획득"""
    global _market_data_service

    if _market_data_service is None:
        if symbols is None:
            symbols = []
        _market_data_service = MarketDataService(symbols, timeframe)

    return _market_data_service


async def close_market_data_service() -> None:
    """시장 데이터 서비스 종료"""
    global _market_data_service
    if _market_data_service and _market_data_service.is_running:
        await _market_data_service.stop()
    _market_data_service = None
