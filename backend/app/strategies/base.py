"""
백테스트 전략의 기본 모델 및 추상 클래스

이 모듈은 모든 전략의 공통 인터페이스와 데이터 구조를 정의합니다.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """
    거래 신호

    거래 시스템에서 생성되는 매수/매도 신호를 나타냅니다.

    Attributes:
        timestamp (pd.Timestamp): 신호 발생 시간 (UTC)
        side (str): 신호 방향 ('BUY' 또는 'SELL')
        price (float): 신호 발생 시점의 가격
        confidence (float): 신호 신뢰도 (0.0 ~ 1.0)
    """
    timestamp: pd.Timestamp
    side: str  # 'BUY' or 'SELL'
    price: float
    confidence: float

    def __post_init__(self):
        """신호 데이터 검증"""
        if self.side not in ('BUY', 'SELL'):
            raise ValueError(f"side must be 'BUY' or 'SELL', got '{self.side}'")

        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")

        if self.price < 0:
            raise ValueError(f"price must be non-negative, got {self.price}")


@dataclass
class BacktestResult:
    """
    백테스트 실행 결과

    전략을 백테스트한 결과로 생성되는 성과 지표를 포함합니다.

    Attributes:
        signals (List[Signal]): 생성된 거래 신호 목록
        samples (int): 신호 개수 (== len(signals))
        win_rate (float): 승률 (0.0 ~ 1.0)
        avg_return (float): 평균 수익률 (%)
        max_drawdown (float): 최대 낙폭 (%)
        avg_hold_bars (float): 평균 보유 바 수
        avg_hold_duration (Optional[pd.Timedelta]): 평균 보유 시간 (타임프레임이 명확할 때만 계산)
    """
    signals: List[Signal]
    samples: int
    win_rate: float  # 0.0 ~ 1.0
    avg_return: float  # 평균 수익률 (%)
    max_drawdown: float  # 최대 낙폭 (%)
    avg_hold_bars: float  # 평균 보유 바 수
    avg_hold_duration: Optional[pd.Timedelta] = None  # 타임프레임이 명확할 때만 사용

    def __post_init__(self):
        """결과 데이터 검증"""
        if len(self.signals) != self.samples:
            raise ValueError(f"signals count ({len(self.signals)}) must equal samples ({self.samples})")

        if not (0.0 <= self.win_rate <= 1.0):
            raise ValueError(f"win_rate must be between 0.0 and 1.0, got {self.win_rate}")

        if self.avg_hold_bars < 0:
            raise ValueError(f"avg_hold_bars must be non-negative, got {self.avg_hold_bars}")


class Strategy(ABC):
    """
    백테스트 전략의 추상 베이스 클래스

    모든 전략은 이 클래스를 상속받아 run() 메서드를 구현해야 합니다.

    Example:
        >>> class MyStrategy(Strategy):
        ...     def run(self, df: pd.DataFrame, params: Dict) -> BacktestResult:
        ...         # 신호 생성 로직
        ...         signals = [...]
        ...         # 지표 계산
        ...         result = BacktestResult(
        ...             signals=signals,
        ...             samples=len(signals),
        ...             win_rate=0.6,
        ...             avg_return=2.5,
        ...             max_drawdown=-5.0,
        ...             avg_hold_bars=1.0
        ...         )
        ...         return result
    """

    @abstractmethod
    def run(self, df: pd.DataFrame, params: Dict) -> BacktestResult:
        """
        전략을 실행하고 백테스트 결과를 반환합니다.

        Args:
            df (pd.DataFrame): OHLCV 데이터
                - timestamp: UTC 기준 시간 (timezone-aware)
                - symbol: 심볼명
                - timeframe: 타임프레임
                - open, high, low, close: 가격
                - volume: 거래량

            params (Dict): 전략 파라미터
                전략별로 다른 파라미터를 받습니다.

        Returns:
            BacktestResult: 백테스트 실행 결과

        Raises:
            ValueError: 입력 데이터 또는 파라미터 오류
            HTTPException: 외부 API 오류 등
        """
        pass
