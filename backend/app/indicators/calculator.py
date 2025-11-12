"""
기술 지표 계산 모듈 (Feature Breakdown #23, Task 4)

상승률, 거래량, 거래대금, 이동평균선 이격도, 이동평균선 정배열/역배열 등을 계산합니다.
"""

import logging
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class IndicatorCalculator:
    """
    기술 지표 계산 클래스

    Parquet 데이터를 읽어 다양한 기술 지표를 계산합니다.
    """

    def __init__(self):
        """초기화"""
        pass

    # ========================================================================
    # 상승률 계산
    # ========================================================================

    def calculate_change_rate(
        self,
        df: pd.DataFrame,
        period: str = '1D'
    ) -> float:
        """
        상승률 계산 (현재 종가 / 과거 종가 - 1)

        Args:
            df: OHLCV 데이터 (close 필드 필수)
            period: 기간
                - '1D': 1일 (어제 종가 대비)
                - '1W': 1주 (1주일 전 종가 대비)
                - '1M': 1개월 (1개월 전 종가 대비)

        Returns:
            상승률 (소수점, 예: 0.05 = 5%)

        Raises:
            ValueError: 데이터 부족 시
        """
        if df is None or df.empty:
            raise ValueError("DataFrame is empty")

        if 'close' not in df.columns:
            raise ValueError("'close' column not found in DataFrame")

        # 현재 종가 (가장 최근)
        current_price = df['close'].iloc[-1]

        # 기간별 이전 종가 계산
        try:
            if period == '1D':
                # 1일 전 (하루 전 종가)
                if len(df) < 2:
                    logger.warning(f"Not enough data for {period} change_rate calculation")
                    return 0.0
                previous_price = df['close'].iloc[-2]

            elif period == '1W':
                # 1주일 전 (약 7거래일 전)
                lookback = 7
                if len(df) < lookback:
                    logger.warning(f"Not enough data for {period} change_rate calculation")
                    return 0.0
                previous_price = df['close'].iloc[-lookback]

            elif period == '1M':
                # 1개월 전 (약 20거래일 전)
                lookback = 20
                if len(df) < lookback:
                    logger.warning(f"Not enough data for {period} change_rate calculation")
                    return 0.0
                previous_price = df['close'].iloc[-lookback]

            else:
                raise ValueError(f"Unknown period: {period}")

            # 상승률 계산
            if previous_price == 0:
                return 0.0

            change_rate = (current_price - previous_price) / previous_price
            return round(float(change_rate), 6)

        except Exception as e:
            logger.error(f"Error calculating change_rate: {e}")
            raise

    # ========================================================================
    # 거래량 계산
    # ========================================================================

    def calculate_volume(
        self,
        df: pd.DataFrame,
        period: str = '1D'
    ) -> float:
        """
        거래량 계산 (기간별 합산)

        Args:
            df: OHLCV 데이터 (volume 필드 필수)
            period: 기간
                - '1D': 1일 (어제 거래량)
                - '1W': 1주 (최근 7일 거래량 합)
                - '1M': 1개월 (최근 20일 거래량 합)

        Returns:
            거래량 (합산)

        Raises:
            ValueError: 데이터 부족 시
        """
        if df is None or df.empty:
            raise ValueError("DataFrame is empty")

        if 'volume' not in df.columns:
            raise ValueError("'volume' column not found in DataFrame")

        try:
            if period == '1D':
                # 1일 거래량 (가장 최근)
                volume = df['volume'].iloc[-1]

            elif period == '1W':
                # 최근 7일 거래량 합
                lookback = 7
                if len(df) < lookback:
                    volume = df['volume'].sum()
                else:
                    volume = df['volume'].iloc[-lookback:].sum()

            elif period == '1M':
                # 최근 20일 거래량 합
                lookback = 20
                if len(df) < lookback:
                    volume = df['volume'].sum()
                else:
                    volume = df['volume'].iloc[-lookback:].sum()

            else:
                raise ValueError(f"Unknown period: {period}")

            return round(float(volume), 2)

        except Exception as e:
            logger.error(f"Error calculating volume: {e}")
            raise

    # ========================================================================
    # 거래대금 계산
    # ========================================================================

    def calculate_trade_amount(
        self,
        df: pd.DataFrame,
        period: str = '1D'
    ) -> float:
        """
        거래대금 계산 (price × volume 합산)

        Args:
            df: OHLCV 데이터 (close, volume 필드 필수)
            period: 기간
                - '1D': 1일
                - '1W': 1주
                - '1M': 1개월

        Returns:
            거래대금 (원)

        Raises:
            ValueError: 데이터 부족 시
        """
        if df is None or df.empty:
            raise ValueError("DataFrame is empty")

        if 'close' not in df.columns or 'volume' not in df.columns:
            raise ValueError("'close' and 'volume' columns are required")

        try:
            # 거래대금 = 종가 × 거래량
            df_copy = df.copy()
            df_copy['trade_amount'] = df_copy['close'] * df_copy['volume']

            if period == '1D':
                amount = df_copy['trade_amount'].iloc[-1]

            elif period == '1W':
                lookback = 7
                if len(df_copy) < lookback:
                    amount = df_copy['trade_amount'].sum()
                else:
                    amount = df_copy['trade_amount'].iloc[-lookback:].sum()

            elif period == '1M':
                lookback = 20
                if len(df_copy) < lookback:
                    amount = df_copy['trade_amount'].sum()
                else:
                    amount = df_copy['trade_amount'].iloc[-lookback:].sum()

            else:
                raise ValueError(f"Unknown period: {period}")

            return round(float(amount), 0)

        except Exception as e:
            logger.error(f"Error calculating trade_amount: {e}")
            raise

    # ========================================================================
    # 이동평균선 (MA) 계산
    # ========================================================================

    def _calculate_ma(
        self,
        df: pd.DataFrame,
        period: int
    ) -> pd.Series:
        """
        이동평균선 (Moving Average) 계산

        Args:
            df: OHLCV 데이터 (close 필드 필수)
            period: 기간 (예: 5, 20, 60)

        Returns:
            이동평균선 Series
        """
        if len(df) < period:
            logger.warning(f"Not enough data for MA{period}: {len(df)} < {period}")
            return pd.Series([np.nan] * len(df), index=df.index)

        return df['close'].rolling(window=period).mean()

    # ========================================================================
    # 이동평균선 이격도 계산
    # ========================================================================

    def calculate_ma_divergence(
        self,
        df: pd.DataFrame,
        ma_period: int = 20
    ) -> float:
        """
        이동평균선 이격도 계산 ((현재가 / MA - 1) × 100)

        현재가가 이동평균선으로부터 얼마나 떨어져 있는지 나타냅니다.
        - 양수: 현재가가 MA 위에 있음 (상승 신호)
        - 음수: 현재가가 MA 아래에 있음 (하락 신호)

        Args:
            df: OHLCV 데이터 (close 필드 필수)
            ma_period: 이동평균선 기간 (기본: 20)

        Returns:
            이격도 (퍼센트, 예: 5.0 = 5%)

        Raises:
            ValueError: 데이터 부족 시
        """
        if df is None or df.empty:
            raise ValueError("DataFrame is empty")

        if 'close' not in df.columns:
            raise ValueError("'close' column not found in DataFrame")

        try:
            # 이동평균선 계산
            ma = self._calculate_ma(df, ma_period)

            # 현재 MA값
            current_ma = ma.iloc[-1]

            if pd.isna(current_ma) or current_ma == 0:
                logger.warning(f"MA{ma_period} is NaN or 0, cannot calculate divergence")
                return 0.0

            # 현재 종가
            current_price = df['close'].iloc[-1]

            # 이격도 계산
            divergence = ((current_price / current_ma) - 1.0) * 100
            return round(float(divergence), 2)

        except Exception as e:
            logger.error(f"Error calculating MA divergence: {e}")
            raise

    # ========================================================================
    # 이동평균선 정배열/역배열 판단
    # ========================================================================

    def check_ma_alignment(
        self,
        df: pd.DataFrame,
        ma_periods: Optional[List[int]] = None
    ) -> str:
        """
        이동평균선 정배열/역배열 판단

        정배열: MA5 > MA20 > MA60 (상승 추세)
        역배열: MA5 < MA20 < MA60 (하락 추세)
        혼조: 그 외

        Args:
            df: OHLCV 데이터 (close 필드 필수)
            ma_periods: 이동평균선 기간 목록 (기본: [5, 20, 60])

        Returns:
            'golden_cross' (정배열), 'dead_cross' (역배열), 'mixed' (혼조)

        Raises:
            ValueError: 데이터 부족 시
        """
        if df is None or df.empty:
            raise ValueError("DataFrame is empty")

        if 'close' not in df.columns:
            raise ValueError("'close' column not found in DataFrame")

        if ma_periods is None:
            ma_periods = [5, 20, 60]

        try:
            # 각 MA 계산
            mas = {}
            for period in ma_periods:
                ma = self._calculate_ma(df, period)
                mas[period] = ma.iloc[-1]

                if pd.isna(mas[period]):
                    logger.warning(f"MA{period} is NaN, insufficient data")
                    return 'mixed'

            # 정렬된 기간 (작은 것부터)
            periods_sorted = sorted(ma_periods)

            # MA 값들 (작은 기간부터)
            ma_values = [mas[period] for period in periods_sorted]

            # 정배열 검사: 작은 기간의 MA가 크면 상승 추세
            # 예: MA5 > MA20 > MA60
            is_golden = all(ma_values[i] > ma_values[i+1] for i in range(len(ma_values)-1))

            if is_golden:
                return 'golden_cross'

            # 역배열 검사: 작은 기간의 MA가 작으면 하락 추세
            # 예: MA5 < MA20 < MA60
            is_dead = all(ma_values[i] < ma_values[i+1] for i in range(len(ma_values)-1))

            if is_dead:
                return 'dead_cross'

            # 혼조
            return 'mixed'

        except Exception as e:
            logger.error(f"Error checking MA alignment: {e}")
            raise

    # ========================================================================
    # 종합 지표 계산 (모든 지표를 한 번에)
    # ========================================================================

    def calculate_all(
        self,
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        모든 기술 지표를 한 번에 계산

        Args:
            df: OHLCV 데이터

        Returns:
            모든 지표 정보 딕셔너리

        Example:
            {
                'change_rate_1d': 0.05,
                'change_rate_1w': 0.12,
                'change_rate_1m': -0.03,
                'volume_1d': 1000.0,
                'volume_1w': 7500.0,
                'volume_1m': 20000.0,
                'trade_amount_1d': 50000000.0,
                'trade_amount_1w': 375000000.0,
                'trade_amount_1m': 1000000000.0,
                'ma_divergence_20': 5.0,
                'ma_divergence_60': 10.0,
                'ma_alignment': 'golden_cross'
            }
        """
        result = {}

        try:
            # 상승률
            result['change_rate_1d'] = self.calculate_change_rate(df, '1D')
            result['change_rate_1w'] = self.calculate_change_rate(df, '1W')
            result['change_rate_1m'] = self.calculate_change_rate(df, '1M')

            # 거래량
            result['volume_1d'] = self.calculate_volume(df, '1D')
            result['volume_1w'] = self.calculate_volume(df, '1W')
            result['volume_1m'] = self.calculate_volume(df, '1M')

            # 거래대금
            result['trade_amount_1d'] = self.calculate_trade_amount(df, '1D')
            result['trade_amount_1w'] = self.calculate_trade_amount(df, '1W')
            result['trade_amount_1m'] = self.calculate_trade_amount(df, '1M')

            # 이동평균선 이격도
            result['ma_divergence_20'] = self.calculate_ma_divergence(df, 20)
            result['ma_divergence_60'] = self.calculate_ma_divergence(df, 60)

            # 이동평균선 정배열/역배열
            result['ma_alignment'] = self.check_ma_alignment(df, [5, 20, 60])

        except Exception as e:
            logger.error(f"Error calculating all indicators: {e}")
            raise

        return result
