"""
캔들 집계 엔진

체결 이벤트를 모아서 1분 단위의 캔들로 집계하고,
Postgres에 영속 저장하고 Redis Stream으로 브로드캐스트합니다.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import pandas as pd
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class CandleData:
    """캔들 데이터 모델"""
    symbol: str
    timeframe: str
    timestamp: datetime  # 캔들 시작 시간 (UTC)
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d


class CandleBuilder:
    """
    체결 데이터를 모아서 캔들로 집계합니다.

    1분봉, 5분봉 등 다양한 타임프레임을 지원합니다.
    """

    # 타임프레임별 초 단위 길이
    TIMEFRAME_SECONDS = {
        '1m': 60,
        '5m': 5 * 60,
        '15m': 15 * 60,
        '1h': 60 * 60,
        '4h': 4 * 60 * 60,
        '1d': 24 * 60 * 60,
    }

    def __init__(self, symbol: str, timeframe: str = '1m'):
        """
        Args:
            symbol: 거래 쌍 (예: 'BTC_KRW')
            timeframe: 타임프레임 (기본: '1m')
        """
        if timeframe not in self.TIMEFRAME_SECONDS:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        self.symbol = symbol
        self.timeframe = timeframe
        self.timeframe_seconds = self.TIMEFRAME_SECONDS[timeframe]

        # 현재 구성 중인 캔들
        self.current_candle: Optional[Dict] = None
        self.candles: List[CandleData] = []

    def _get_candle_start_time(self, timestamp: datetime) -> datetime:
        """타임스탬프에서 캔들 시작 시간 계산"""
        ts = int(timestamp.timestamp())
        candle_start_ts = (ts // self.timeframe_seconds) * self.timeframe_seconds
        return datetime.fromtimestamp(candle_start_ts)

    def add_trade(self, timestamp: datetime, price: float, volume: float) -> Optional[CandleData]:
        """
        체결 데이터를 추가하고, 완성된 캔들이 있으면 반환합니다.

        Args:
            timestamp: 체결 시간 (UTC)
            price: 체결가
            volume: 체결량

        Returns:
            완성된 캔들이 있으면 CandleData, 아니면 None
        """
        candle_start = self._get_candle_start_time(timestamp)

        # 새로운 캔들이 시작되었는지 확인
        if self.current_candle is None or self.current_candle['timestamp'] != candle_start:
            # 이전 캔들을 저장하고 새로운 캔들 시작
            completed_candle = None
            if self.current_candle is not None:
                completed_candle = self._finalize_candle()

            # 새 캔들 시작
            self.current_candle = {
                'timestamp': candle_start,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume,
            }

            return completed_candle

        # 현재 캔들에 데이터 누적
        self.current_candle['high'] = max(self.current_candle['high'], price)
        self.current_candle['low'] = min(self.current_candle['low'], price)
        self.current_candle['close'] = price
        self.current_candle['volume'] += volume

        return None

    def _finalize_candle(self) -> CandleData:
        """현재 캔들을 완성"""
        if self.current_candle is None:
            raise RuntimeError("No candle to finalize")

        candle = CandleData(
            symbol=self.symbol,
            timeframe=self.timeframe,
            timestamp=self.current_candle['timestamp'],
            open=self.current_candle['open'],
            high=self.current_candle['high'],
            low=self.current_candle['low'],
            close=self.current_candle['close'],
            volume=self.current_candle['volume'],
        )

        self.candles.append(candle)
        return candle

    def get_current_candle(self) -> Optional[CandleData]:
        """현재 구성 중인 캔들 반환 (미완성)"""
        if self.current_candle is None:
            return None

        return CandleData(
            symbol=self.symbol,
            timeframe=self.timeframe,
            timestamp=self.current_candle['timestamp'],
            open=self.current_candle['open'],
            high=self.current_candle['high'],
            low=self.current_candle['low'],
            close=self.current_candle['close'],
            volume=self.current_candle['volume'],
        )

    def get_completed_candles(self) -> List[CandleData]:
        """완성된 캔들 모두 반환"""
        return self.candles.copy()

    def clear_completed(self) -> None:
        """완성된 캔들 목록 초기화"""
        self.candles.clear()

    def load_from_dataframe(self, df: pd.DataFrame) -> None:
        """
        DataFrame에서 캔들 데이터 로드

        Args:
            df: OHLCV 데이터 (timestamp, open, high, low, close, volume 포함)
        """
        self.current_candle = None
        self.candles.clear()

        for _, row in df.iterrows():
            self.add_trade(row['timestamp'], row['close'], row['volume'])

        # 마지막 캔들도 저장
        if self.current_candle is not None:
            self._finalize_candle()

    def get_state(self) -> Dict:
        """현재 상태 저장 (직렬화용)"""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'current_candle': self.current_candle,
            'completed_count': len(self.candles),
        }

    def restore_state(self, state: Dict, current_candle_data: Optional[Dict] = None) -> None:
        """이전 상태에서 복원"""
        if state['symbol'] != self.symbol or state['timeframe'] != self.timeframe:
            raise ValueError("State mismatch")

        self.current_candle = current_candle_data


class MultiCandleBuilder:
    """
    여러 심볼/타임프레임에 대한 캔들 집계를 관리합니다.
    """

    def __init__(self):
        self.builders: Dict[tuple, CandleBuilder] = {}  # (symbol, timeframe) -> CandleBuilder

    def get_builder(self, symbol: str, timeframe: str = '1m') -> CandleBuilder:
        """빌더 획득 (없으면 생성)"""
        key = (symbol, timeframe)
        if key not in self.builders:
            self.builders[key] = CandleBuilder(symbol, timeframe)
        return self.builders[key]

    def add_trade(self, symbol: str, timeframe: str, timestamp: datetime,
                 price: float, volume: float) -> Optional[CandleData]:
        """체결 데이터 추가"""
        builder = self.get_builder(symbol, timeframe)
        return builder.add_trade(timestamp, price, volume)

    def get_completed_candles(self, symbol: str = None, timeframe: str = None) -> List[CandleData]:
        """완성된 캔들 조회"""
        candles = []

        for (s, t), builder in self.builders.items():
            if symbol and s != symbol:
                continue
            if timeframe and t != timeframe:
                continue

            candles.extend(builder.get_completed_candles())

        return candles

    def clear_completed(self, symbol: str = None, timeframe: str = None) -> None:
        """완성된 캔들 초기화"""
        for (s, t), builder in self.builders.items():
            if symbol and s != symbol:
                continue
            if timeframe and t != timeframe:
                continue

            builder.clear_completed()
