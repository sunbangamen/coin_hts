"""
백테스트 성과 지표 계산 공통 함수

모든 전략이 공유하는 성과 지표 계산 로직을 정의합니다.
"""

import logging
from typing import List, Dict, Tuple
import numpy as np

logger = logging.getLogger(__name__)


def calculate_metrics(
    returns: List[float],
    hold_period_bars: int,
) -> Dict[str, float]:
    """
    거래 수익률 배열로부터 성과 지표를 계산합니다.

    Args:
        returns (List[float]): 각 거래의 수익률 배열 (%)
            예: [1.5, -0.8, 2.3, -1.0, 0.9]

        hold_period_bars (int): 신호당 평균 보유 바 수

    Returns:
        Dict[str, float]: 성과 지표 딕셔너리
            - win_rate (float): 승률 (0.0 ~ 1.0)
            - avg_return (float): 평균 수익률 (%)
            - max_drawdown (float): 최대 낙폭 (양수 %)
            - avg_hold_bars (float): 평균 보유 바 수

    Raises:
        ValueError: 입력 데이터 오류
    """
    if not isinstance(returns, list) or len(returns) == 0:
        raise ValueError("returns must be a non-empty list")

    if hold_period_bars < 0:
        raise ValueError("hold_period_bars must be non-negative")

    # 승률 계산: 수익 거래 / 전체 거래
    win_count = sum(1 for r in returns if r > 0)
    win_rate = win_count / len(returns) if returns else 0.0

    # 평균 수익률 계산
    avg_return = sum(returns) / len(returns) if returns else 0.0

    # 최대 낙폭 (MDD) 계산 - 양수 %로 반환
    cumulative_returns = np.array(returns).cumsum()
    running_max = np.maximum.accumulate(cumulative_returns)
    drawdown = cumulative_returns - running_max
    # min(drawdown)은 음수이므로 절댓값으로 변환하여 양수 %로 표현
    max_drawdown = abs(float(np.min(drawdown))) if len(drawdown) > 0 else 0.0

    return {
        'win_rate': win_rate,
        'avg_return': avg_return,
        'max_drawdown': max_drawdown,
        'avg_hold_bars': float(hold_period_bars),
    }


def calculate_entry_exit_prices(
    signal_indices: List[int],
    df,
    hold_period_bars: int,
) -> List[Tuple[float, float]]:
    """
    신호 인덱스로부터 진입/청산 가격을 계산합니다.

    Args:
        signal_indices (List[int]): 신호 발생 위치 (0-based 위치 기반 인덱스)
        df: DataFrame (reset_index(drop=True)로 정규화됨)
        hold_period_bars (int): 신호당 보유 바 수

    Returns:
        List[Tuple[float, float]]: (진입가, 청산가) 튜플 리스트
    """
    entry_exit_pairs = []

    for signal_idx in signal_indices:
        entry_price = df.iloc[signal_idx]['close']

        # 청산 인덱스 계산 (위치 기반)
        exit_idx = signal_idx + hold_period_bars

        if exit_idx >= len(df):
            exit_idx = len(df) - 1

        exit_price = df.iloc[exit_idx]['close']
        entry_exit_pairs.append((entry_price, exit_price))

    return entry_exit_pairs


def calculate_returns(
    entry_exit_pairs: List[Tuple[float, float]],
) -> List[float]:
    """
    진입/청산 가격 쌍으로부터 수익률을 계산합니다.

    Args:
        entry_exit_pairs (List[Tuple[float, float]]): (진입가, 청산가) 튜플 리스트

    Returns:
        List[float]: 수익률 배열 (%)
    """
    returns = []

    for entry_price, exit_price in entry_exit_pairs:
        ret = ((exit_price - entry_price) / entry_price) * 100
        returns.append(ret)

    return returns
