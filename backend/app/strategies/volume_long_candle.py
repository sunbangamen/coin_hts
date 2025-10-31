"""
거래량 급증 + 장대양봉 전략

거래량이 급증하면서 동시에 장대양봉이 나타나는 패턴을 감지합니다.
"""

import logging
from typing import List, Dict, Optional
import pandas as pd

from backend.app.strategies.base import Signal, BacktestResult, Strategy
from backend.app.strategies.metrics import (
    calculate_entry_exit_prices,
    calculate_returns,
    calculate_metrics,
)

logger = logging.getLogger(__name__)


class VolumeLongCandleStrategy(Strategy):
    """
    거래량 급증 + 장대양봉 전략

    거래량이 평균을 크게 상회하면서 동시에 강한 상승 장봉이 나타나는 패턴을 감지합니다.

    Parameters:
        vol_ma_window (int): 거래량 이동평균 계산 윈도우 (기본값: 20)
        vol_multiplier (float): 거래량 급증 배수 기준 (기본값: 1.5)
        body_pct (float): 캔들 몸통 비율 (기본값: 0.02, 즉 2%)
        hold_period_bars (int): 신호 후 보유 바 수 (기본값: 1)
    """

    def run(self, df: pd.DataFrame, params: Dict) -> BacktestResult:
        """
        거래량 급증 + 장대양봉 전략 실행

        Args:
            df (pd.DataFrame): OHLCV 데이터
                - timestamp: UTC 기준 시간
                - open, high, low, close: 가격
                - volume: 거래량

            params (Dict): 전략 파라미터
                - vol_ma_window: int (기본값: 20)
                - vol_multiplier: float (기본값: 1.5)
                - body_pct: float (기본값: 0.02)
                - hold_period_bars: int (기본값: 1)

        Returns:
            BacktestResult: 백테스트 결과

        Raises:
            ValueError: 입력 데이터 오류
        """
        # 파라미터 추출 및 기본값 설정
        vol_ma_window = params.get('vol_ma_window', 20)
        vol_multiplier = params.get('vol_multiplier', 1.5)
        body_pct = params.get('body_pct', 0.02)
        hold_period_bars = params.get('hold_period_bars', 1)

        # 입력 검증
        if df.empty:
            raise ValueError("DataFrame is empty")

        if not all(col in df.columns for col in ['open', 'high', 'low', 'close', 'volume']):
            raise ValueError("Missing required columns: open, high, low, close, volume")

        if vol_ma_window < 1 or vol_multiplier <= 0 or body_pct <= 0 or hold_period_bars < 1:
            raise ValueError("Invalid parameters")

        # 데이터 복사 및 인덱스 재설정 (위치 기반 계산 위해)
        df = df.copy().reset_index(drop=True)

        # 거래량 이동평균 계산
        df['vol_ma'] = df['volume'].rolling(window=vol_ma_window, min_periods=1).mean()

        # 거래량 급증 조건
        df['vol_surge'] = df['volume'] >= df['vol_ma'] * vol_multiplier

        # 캔들 몸통 비율 계산: (close - open) / open
        df['body_pct_actual'] = (df['close'] - df['open']) / df['open']

        # 위/아래 꼬리 비율 계산
        # 위 꼬리: (high - close) / open
        # 아래 꼬리: (open - low) / open
        df['upper_wick'] = (df['high'] - df['close']).clip(lower=0) / df['open']
        df['lower_wick'] = (df['open'] - df['low']).clip(lower=0) / df['open']

        # 장대양봉 조건: 몸통이 충분히 크고, 위 꼬리가 작으며, 아래 꼬리도 작은 상태
        # 추가 조건: close > open (상승 캔들)
        df['long_candle'] = (
            (df['body_pct_actual'] >= body_pct) &  # 몸통 비율 조건
            (df['upper_wick'] < body_pct * 2) &     # 위 꼬리 작음
            (df['lower_wick'] < body_pct * 2) &     # 아래 꼬리 작음
            (df['close'] > df['open'])              # 상승 캔들
        )

        # 시그널 생성 조건: 거래량 급증 AND 장대양봉
        df['signal'] = df['vol_surge'] & df['long_candle']

        # 신호 인덱스 찾기
        signal_indices = df.index[df['signal']].tolist()

        if not signal_indices:
            logger.warning("No signals generated for volume_long_candle strategy")
            return BacktestResult(
                signals=[],
                samples=0,
                win_rate=0.0,
                avg_return=0.0,
                max_drawdown=0.0,
                avg_hold_bars=0.0,
                avg_hold_duration=None,
            )

        # 진입/청산 가격 계산 및 수익률 산출
        entry_exit_pairs = calculate_entry_exit_prices(signal_indices, df, hold_period_bars)
        returns = calculate_returns(entry_exit_pairs)

        # 신호 객체 생성 (confidence는 거래량 배수 기반)
        signals: List[Signal] = []
        for idx, signal_idx in enumerate(signal_indices):
            signal_price = entry_exit_pairs[idx][0]
            signal_time = df.loc[signal_idx, 'timestamp']
            vol_ratio = df.loc[signal_idx, 'volume'] / df.loc[signal_idx, 'vol_ma']
            confidence = min(vol_ratio / vol_multiplier, 1.0)

            signals.append(
                Signal(
                    timestamp=signal_time,
                    side='BUY',
                    price=signal_price,
                    confidence=confidence,
                )
            )

        # 성과 지표 계산 (공통 함수)
        metrics = calculate_metrics(returns, hold_period_bars)

        logger.info(
            "VolumeLongCandle: signals=%s, win_rate=%.2f%%, avg_return=%.2f%%, max_drawdown=%.2f%%",
            len(signals),
            metrics['win_rate'] * 100,
            metrics['avg_return'],
            metrics['max_drawdown'],
        )

        result = BacktestResult(
            signals=signals,
            samples=len(signals),
            win_rate=metrics['win_rate'],
            avg_return=metrics['avg_return'],
            max_drawdown=metrics['max_drawdown'],
            avg_hold_bars=metrics['avg_hold_bars'],
            avg_hold_duration=None,
        )

        return result
