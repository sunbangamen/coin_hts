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
        entry_exit_pairs (Optional[List[tuple]]): (진입가, 청산가) 쌍 (Step 4 API용)
        returns (Optional[List[float]]): 거래 수익률 배열 (%) (Step 4 API용)
    """
    signals: List[Signal]
    samples: int
    win_rate: float  # 0.0 ~ 1.0
    avg_return: float  # 평균 수익률 (%)
    max_drawdown: float  # 최대 낙폭 (%)
    avg_hold_bars: float  # 평균 보유 바 수
    avg_hold_duration: Optional[pd.Timedelta] = None  # 타임프레임이 명확할 때만 사용
    entry_exit_pairs: Optional[List[tuple]] = None  # (진입가, 청산가) 쌍 - Step 4 신호 테이블용
    returns: Optional[List[float]] = None  # 거래 수익률 (%) - Step 4 신호 테이블용

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
    백테스트 및 실시간 시뮬레이션 전략의 추상 베이스 클래스

    모든 전략은 이 클래스를 상속받아 run() 메서드를 구현해야 하며,
    실시간 모드를 지원하려면 initialize_with_history()를 구현해야 합니다.

    Example (Backtest):
        >>> class MyStrategy(Strategy):
        ...     def run(self, df: pd.DataFrame, params: Dict) -> BacktestResult:
        ...         signals = [...]
        ...         result = BacktestResult(
        ...             signals=signals,
        ...             samples=len(signals),
        ...             win_rate=0.6,
        ...             avg_return=2.5,
        ...             max_drawdown=-5.0,
        ...             avg_hold_bars=1.0
        ...         )
        ...         return result

    Example (Realtime):
        >>> class MyStrategy(Strategy):
        ...     def initialize_with_history(self, df: pd.DataFrame, params: Dict) -> None:
        ...         self.window = params.get('window', 20)
        ...         self.data = df.tail(self.window)
        ...         self.last_signal = None
        ...
        ...     def process_candle(self, candle: Dict) -> Optional[Signal]:
        ...         self.data = pd.concat([self.data, [candle]])
        ...         self.data = self.data.tail(self.window)
        ...         signal = self._generate_signal()
        ...         return signal
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

    def initialize_with_history(self, df: pd.DataFrame, params: Dict) -> None:
        """
        실시간 전략 실행을 위해 히스토리 데이터로 전략을 초기화합니다.

        이 메서드는 실시간 시뮬레이션 시작 시 호출되며, 전략이 필요한 최소 윈도우만큼의
        과거 데이터를 로드하고 내부 상태를 초기화합니다.

        기본 구현은 아무 작업도 하지 않으므로, 실시간 모드를 지원하려면
        서브클래스에서 오버라이드해야 합니다.

        Args:
            df (pd.DataFrame): 초기 히스토리 OHLCV 데이터
                - timestamp: UTC 기준 시간 (timezone-aware)
                - symbol: 심볼명
                - timeframe: 타임프레임
                - open, high, low, close: 가격
                - volume: 거래량
                일반적으로 전략에 필요한 최소 윈도우 크기(예: 200 캔들)만 포함

            params (Dict): 전략 파라미터

        Raises:
            ValueError: 히스토리 데이터 부족 또는 파라미터 오류

        Example:
            >>> def initialize_with_history(self, df, params):
            ...     if len(df) < params.get('min_window', 20):
            ...         raise ValueError(f"Need at least {params['min_window']} candles")
            ...     self.data_buffer = df.tail(params['min_window']).copy()
            ...     self.params = params
        """
        pass

    def process_candle(self, candle: Dict) -> Optional[Signal]:
        """
        새로운 캔들을 처리하고 신호를 생성합니다.

        이 메서드는 실시간 모드에서 매 캔들마다 호출됩니다.
        기본 구현은 None을 반환하므로, 실시간 모드를 지원하려면
        서브클래스에서 오버라이드해야 합니다.

        Args:
            candle (Dict): 새로운 캔들 데이터
                - timestamp: pd.Timestamp (UTC)
                - open: float
                - high: float
                - low: float
                - close: float
                - volume: float

        Returns:
            Optional[Signal]: 생성된 신호 또는 None (신호가 없는 경우)

        Example:
            >>> def process_candle(self, candle):
            ...     row = pd.Series(candle)
            ...     self.data_buffer = pd.concat([self.data_buffer, [row]])
            ...     self.data_buffer = self.data_buffer.tail(self.window)
            ...
            ...     if len(self.data_buffer) < self.window:
            ...         return None
            ...
            ...     signal_side = self._check_signal()
            ...     if signal_side:
            ...         return Signal(
            ...             timestamp=candle['timestamp'],
            ...             side=signal_side,
            ...             price=candle['close'],
            ...             confidence=0.8
            ...         )
            ...     return None
        """
        return None

    def get_state(self) -> Dict:
        """
        전략의 현재 상태를 반환합니다.

        재연결이나 장애 복구 시 전략 상태를 직렬화하기 위해 사용됩니다.
        기본 구현은 빈 딕셔너리를 반환하므로, 상태 저장이 필요한 경우
        서브클래스에서 오버라이드해야 합니다.

        Returns:
            Dict: 전략의 현재 상태 (JSON 직렬화 가능해야 함)

        Example:
            >>> def get_state(self):
            ...     return {
            ...         'data_buffer': self.data_buffer.to_dict(orient='records'),
            ...         'last_signal_price': self.last_signal_price,
            ...         'indicator_values': self.indicator_values
            ...     }
        """
        return {}

    def restore_state(self, state: Dict) -> None:
        """
        이전에 저장된 상태로 전략을 복원합니다.

        기본 구현은 아무 작업도 하지 않으므로, 상태 복원이 필요한 경우
        서브클래스에서 오버라이드해야 합니다.

        Args:
            state (Dict): get_state()가 반환한 상태 딕셔너리

        Example:
            >>> def restore_state(self, state):
            ...     self.data_buffer = pd.DataFrame(state['data_buffer'])
            ...     self.last_signal_price = state.get('last_signal_price')
            ...     self.indicator_values = state.get('indicator_values', {})
        """
        pass

    @property
    def min_history_window(self) -> int:
        """
        전략이 필요한 최소 히스토리 윈도우 크기를 반환합니다.

        실시간 모드에서 초기화 시 이 크기만큼의 과거 캔들을 로드합니다.
        기본값은 200이며, 서브클래스에서 오버라이드할 수 있습니다.

        Returns:
            int: 최소 필요 캔들 수

        Example:
            >>> @property
            >>> def min_history_window(self):
            ...     return self.params.get('lookback_period', 20)
        """
        return 200
