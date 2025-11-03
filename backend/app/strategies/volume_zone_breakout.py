"""
매물대 돌파 전략

가격대별 거래량을 분석하여 매물대를 형성하고, 저항선 돌파 시 신호를 생성합니다.
"""

import logging
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np

from backend.app.strategies.base import Signal, BacktestResult, Strategy
from backend.app.strategies.metrics import (
    calculate_entry_exit_prices,
    calculate_returns,
    calculate_metrics,
)

logger = logging.getLogger(__name__)


class VolumeZoneBreakoutStrategy(Strategy):
    """
    매물대 돌파 전략

    최근 구간의 거래량 프로파일을 분석하여 주요 매물대를 파악하고,
    상위 매물대를 돌파하는 신호를 감지합니다.

    Parameters:
        volume_window (int): 매물대 형성 윈도우 (기본값: 10, 최적화됨)
        top_percentile (float): 상위 백분위 (기본값: 0.2, 즉 상위 20%)
        breakout_buffer (float): 돌파 버퍼 비율 (기본값: 0.0, 즉 0%, 최적화됨)
        hold_period_bars (int): 신호 후 보유 바 수 (기본값: 1)
        num_bins (int): 가격 구간 수 (기본값: 20)
        include_wicks (bool): 고가/저가를 가격 범위에 포함할지 여부 (기본값: True)
    """

    def run(self, df: pd.DataFrame, params: Dict) -> BacktestResult:
        """
        매물대 돌파 전략 실행

        Args:
            df (pd.DataFrame): OHLCV 데이터
                - timestamp: UTC 기준 시간
                - open, high, low, close: 가격
                - volume: 거래량

            params (Dict): 전략 파라미터
                - volume_window: int (기본값: 10)
                - top_percentile: float (기본값: 0.2)
                - breakout_buffer: float (기본값: 0.0)
                - hold_period_bars: int (기본값: 1)
                - num_bins: int (기본값: 20)
                - include_wicks: bool (기본값: True)

        Returns:
            BacktestResult: 백테스트 결과

        Raises:
            ValueError: 입력 데이터 오류
        """
        # 파라미터 추출 및 기본값 설정
        volume_window = params.get('volume_window', 10)
        top_percentile = params.get('top_percentile', 0.2)
        breakout_buffer = params.get('breakout_buffer', 0.0)
        hold_period_bars = params.get('hold_period_bars', 1)
        num_bins = params.get('num_bins', 20)
        include_wicks = params.get('include_wicks', True)

        # 입력 검증
        if df.empty:
            raise ValueError("DataFrame is empty")

        if not all(col in df.columns for col in ['open', 'high', 'low', 'close', 'volume']):
            raise ValueError("Missing required columns: open, high, low, close, volume")

        if volume_window < 1 or top_percentile <= 0 or breakout_buffer < 0 or hold_period_bars < 1 or num_bins < 1:
            raise ValueError("Invalid parameters")

        # 데이터 복사 (원본 수정 방지)
        df = df.copy().reset_index(drop=True)

        # 신호 생성
        signals: List[Signal] = []
        signal_indices: List[int] = []

        # Phase 3-2-1 최적화: 증분 윈도우 계산
        # 초기 window 계산 (처음 volume_window개 캔들)
        initial_window_df = df.iloc[0:volume_window]
        bin_volumes, bins = self._calculate_bin_volumes(
            initial_window_df,
            num_bins=num_bins,
            include_wicks=include_wicks,
        )

        # numpy 배열로 변환 (빠른 접근용)
        open_prices = df['open'].values
        close_prices = df['close'].values
        high_prices = df['high'].values
        low_prices = df['low'].values
        volumes = df['volume'].values

        if not include_wicks:
            low_prices = np.minimum(open_prices, close_prices)
            high_prices = np.maximum(open_prices, close_prices)

        # 슬라이딩 윈도우로 매물대 계산 및 신호 생성 (증분 방식)
        for i in range(volume_window, len(df)):
            # 현재 window:[i - volume_window, ..., i-1]에 대한 저항선 계산
            resistance_price = self._get_resistance_from_bins(
                bin_volumes,
                bins,
                top_percentile=top_percentile,
            )

            if resistance_price is None:
                continue

            # 현재 캔들 데이터
            current_close = close_prices[i]
            current_high = high_prices[i]

            # 돌파 조건 확인
            breakout_level = resistance_price * (1 + breakout_buffer)

            if current_high >= breakout_level:
                # 돌파 신호 생성
                signal_price = current_close
                signal_time = df.loc[i, 'timestamp']

                # 청산 인덱스 계산
                exit_idx = i + hold_period_bars

                if exit_idx >= len(df):
                    exit_idx = len(df) - 1

                exit_price = df.iloc[exit_idx]['close']

                # 신호 객체 생성
                # confidence는 breakout 강도로 설정
                breakout_strength = (current_high - breakout_level) / breakout_level
                confidence = min(0.5 + breakout_strength, 1.0)  # 0.5 ~ 1.0 범위

                signal = Signal(
                    timestamp=signal_time,
                    side='BUY',
                    price=signal_price,
                    confidence=confidence,
                )
                signals.append(signal)
                signal_indices.append(i)

            # 다음 반복을 위해 윈도우 슬라이드 (가장 오래된 캔들 제거, 새로운 캔들 추가)
            if i + 1 < len(df):
                exit_idx = i - volume_window
                exit_candle_low = low_prices[exit_idx]
                exit_candle_high = high_prices[exit_idx]
                exit_volume = volumes[exit_idx]
                exit_height = exit_candle_high - exit_candle_low

                self._remove_candle_from_bins(
                    bin_volumes,
                    bins,
                    exit_candle_low,
                    exit_candle_high,
                    exit_volume,
                    exit_height,
                )

                enter_idx = i
                enter_candle_low = low_prices[enter_idx]
                enter_candle_high = high_prices[enter_idx]
                enter_volume = volumes[enter_idx]
                enter_height = enter_candle_high - enter_candle_low

                self._add_candle_to_bins(
                    bin_volumes,
                    bins,
                    enter_candle_low,
                    enter_candle_high,
                    enter_volume,
                    enter_height,
                )

        if not signals:
            logger.warning("No signals generated for volume_zone_breakout strategy")
            return BacktestResult(
                signals=[],
                samples=0,
                win_rate=0.0,
                avg_return=0.0,
                max_drawdown=0.0,
                avg_hold_bars=0.0,
                avg_hold_duration=None,
                entry_exit_pairs=[],  # Step 4 신호 테이블용
                returns=[],  # Step 4 신호 테이블용
            )

        # 공통 함수로 성과 지표 계산
        entry_exit_pairs = calculate_entry_exit_prices(signal_indices, df, hold_period_bars)
        returns = calculate_returns(entry_exit_pairs)
        metrics = calculate_metrics(returns, hold_period_bars)

        logger.info(
            "VolumeZoneBreakout: signals=%s, win_rate=%.2f%%, avg_return=%.2f%%, max_drawdown=%.2f%%",
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
            entry_exit_pairs=entry_exit_pairs,  # Step 4 신호 테이블용
            returns=returns,  # Step 4 신호 테이블용
        )

        return result

    def _calculate_bin_volumes(
        self,
        df: pd.DataFrame,
        num_bins: int,
        include_wicks: bool,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        주어진 데이터에서 bin별 거래량 계산

        Phase 3-2-1 최적화: 증분 윈도우 계산을 위해 추출

        Args:
            df (pd.DataFrame): OHLCV 데이터
            num_bins (int): bin 수
            include_wicks (bool): wick 포함 여부

        Returns:
            Tuple[np.ndarray, np.ndarray]: (bin_volumes, bins)
        """
        if df.empty:
            return np.zeros(num_bins), np.array([0.0, 1.0])

        # 가격 범위 결정
        if include_wicks:
            price_min = df['low'].min()
            price_max = df['high'].max()
        else:
            price_min = df['open'].min()
            price_max = max(df['close'].max(), df['open'].max())

        if price_min == price_max:
            return np.zeros(num_bins), np.array([price_min, price_min + 1])

        # 가격 구간 생성
        bins = np.linspace(price_min, price_max, num_bins + 1)
        bin_volumes = np.zeros(num_bins)

        # numpy 배열로 변환
        open_prices = df['open'].values
        close_prices = df['close'].values
        volumes = df['volume'].values

        if include_wicks:
            low_prices = df['low'].values
            high_prices = df['high'].values
        else:
            low_prices = np.minimum(open_prices, close_prices)
            high_prices = np.maximum(open_prices, close_prices)

        candle_heights = high_prices - low_prices

        # 각 캔들 처리
        for i in range(len(df)):
            candle_low = low_prices[i]
            candle_high = high_prices[i]
            volume = volumes[i]
            candle_height = candle_heights[i]

            if candle_height == 0:
                center = (candle_low + candle_high) / 2
                bin_idx = np.searchsorted(bins, center, side='right') - 1
                bin_idx = max(0, min(bin_idx, num_bins - 1))
                bin_volumes[bin_idx] += volume
            else:
                # searchsorted로 overlap bin 범위 찾기
                start_bin = np.searchsorted(bins, candle_low, side='right') - 1
                end_bin = np.searchsorted(bins, candle_high, side='left')
                start_bin = max(0, start_bin)
                end_bin = min(num_bins, end_bin)

                for bin_idx in range(start_bin, end_bin):
                    bin_start = bins[bin_idx]
                    bin_end = bins[bin_idx + 1]
                    overlap_start = max(candle_low, bin_start)
                    overlap_end = min(candle_high, bin_end)

                    if overlap_start < overlap_end:
                        overlap_ratio = (overlap_end - overlap_start) / candle_height
                        bin_volumes[bin_idx] += volume * overlap_ratio

        return bin_volumes, bins

    def _add_candle_to_bins(
        self,
        bin_volumes: np.ndarray,
        bins: np.ndarray,
        candle_low: float,
        candle_high: float,
        volume: float,
        candle_height: float,
    ) -> None:
        """
        캔들을 bin_volumes에 추가 (증분 계산용)

        Args:
            bin_volumes (np.ndarray): bin 거래량 배열 (수정됨)
            bins (np.ndarray): bin 경계 배열
            candle_low, candle_high: 캔들 범위
            volume: 캔들 거래량
            candle_height: 캔들 높이
        """
        if candle_height == 0:
            center = (candle_low + candle_high) / 2
            bin_idx = np.searchsorted(bins, center, side='right') - 1
            bin_idx = max(0, min(bin_idx, len(bin_volumes) - 1))
            bin_volumes[bin_idx] += volume
        else:
            start_bin = np.searchsorted(bins, candle_low, side='right') - 1
            end_bin = np.searchsorted(bins, candle_high, side='left')
            start_bin = max(0, start_bin)
            end_bin = min(len(bin_volumes), end_bin)

            for bin_idx in range(start_bin, end_bin):
                bin_start = bins[bin_idx]
                bin_end = bins[bin_idx + 1]
                overlap_start = max(candle_low, bin_start)
                overlap_end = min(candle_high, bin_end)

                if overlap_start < overlap_end:
                    overlap_ratio = (overlap_end - overlap_start) / candle_height
                    bin_volumes[bin_idx] += volume * overlap_ratio

    def _remove_candle_from_bins(
        self,
        bin_volumes: np.ndarray,
        bins: np.ndarray,
        candle_low: float,
        candle_high: float,
        volume: float,
        candle_height: float,
    ) -> None:
        """
        캔들을 bin_volumes에서 제거 (증분 계산용)

        Args:
            bin_volumes (np.ndarray): bin 거래량 배열 (수정됨)
            bins (np.ndarray): bin 경계 배열
            candle_low, candle_high: 캔들 범위
            volume: 캔들 거래량
            candle_height: 캔들 높이
        """
        if candle_height == 0:
            center = (candle_low + candle_high) / 2
            bin_idx = np.searchsorted(bins, center, side='right') - 1
            bin_idx = max(0, min(bin_idx, len(bin_volumes) - 1))
            bin_volumes[bin_idx] -= volume
        else:
            start_bin = np.searchsorted(bins, candle_low, side='right') - 1
            end_bin = np.searchsorted(bins, candle_high, side='left')
            start_bin = max(0, start_bin)
            end_bin = min(len(bin_volumes), end_bin)

            for bin_idx in range(start_bin, end_bin):
                bin_start = bins[bin_idx]
                bin_end = bins[bin_idx + 1]
                overlap_start = max(candle_low, bin_start)
                overlap_end = min(candle_high, bin_end)

                if overlap_start < overlap_end:
                    overlap_ratio = (overlap_end - overlap_start) / candle_height
                    bin_volumes[bin_idx] -= volume * overlap_ratio

    def _get_resistance_from_bins(
        self,
        bin_volumes: np.ndarray,
        bins: np.ndarray,
        top_percentile: float,
    ) -> Optional[float]:
        """
        bin_volumes에서 저항선 계산

        Args:
            bin_volumes (np.ndarray): bin별 거래량
            bins (np.ndarray): bin 경계
            top_percentile (float): 상위 백분위

        Returns:
            Optional[float]: 저항선 가격
        """
        total_volume = bin_volumes.sum()

        if total_volume == 0:
            return None

        # 가장 높은 가격부터 누적
        cumulative_from_top = 0.0
        threshold_volume = total_volume * top_percentile

        for bin_idx in range(len(bin_volumes) - 1, -1, -1):
            cumulative_from_top += bin_volumes[bin_idx]

            if cumulative_from_top >= threshold_volume:
                resistance = bins[bin_idx]
                return resistance

        # 기본값
        return bins[-1]

    def _calculate_resistance(
        self,
        df: pd.DataFrame,
        top_percentile: float,
        num_bins: int,
        include_wicks: bool,
    ) -> Optional[float]:
        """
        매물대 기반 저항선 계산 (Phase 3-2-1 벡터화 최적화)

        Args:
            df (pd.DataFrame): 윈도우 내 OHLCV 데이터
            top_percentile (float): 상위 백분위
            num_bins (int): 가격 구간 수
            include_wicks (bool): 고가/저가를 가격 범위에 포함할지 여부

        Returns:
            Optional[float]: 저항 가격 (없으면 None)

        최적화 포인트:
        - numpy searchsorted로 bin 범위 찾기 (O(log k) per candle)
        - iterrows() 제거하고 numpy 배열 직접 접근
        - 전체 bin 확인 대신 overlap되는 bin만 처리 (20개 → 평균 2-3개)
        """
        if df.empty:
            return None

        # 가격 범위 결정
        if include_wicks:
            price_min = df['low'].min()
            price_max = df['high'].max()
        else:
            price_min = df['open'].min()
            price_max = max(df['close'].max(), df['open'].max())

        if price_min == price_max:
            return None

        # 가격 구간 생성 (bin)
        bins = np.linspace(price_min, price_max, num_bins + 1)

        # 각 bin에 거래량 할당
        bin_volumes = np.zeros(num_bins)

        # 최적화: numpy 배열로 변환하여 더 빠른 접근 (iterrows 제거)
        open_prices = df['open'].values
        close_prices = df['close'].values
        volumes = df['volume'].values

        if include_wicks:
            low_prices = df['low'].values
            high_prices = df['high'].values
        else:
            low_prices = np.minimum(open_prices, close_prices)
            high_prices = np.maximum(open_prices, close_prices)

        candle_heights = high_prices - low_prices

        # 벡터화된 방식으로 각 캔들 처리
        for i in range(len(df)):
            candle_low = low_prices[i]
            candle_high = high_prices[i]
            volume = volumes[i]
            candle_height = candle_heights[i]

            if candle_height == 0:
                # 높이가 0이면 중앙 bin에만 할당
                center = (candle_low + candle_high) / 2
                bin_idx = np.searchsorted(bins, center, side='right') - 1
                bin_idx = max(0, min(bin_idx, num_bins - 1))
                bin_volumes[bin_idx] += volume
            else:
                # 최적화: searchsorted로 overlap되는 bin 범위 찾기 (O(log k))
                # 기존: 모든 bin 확인 (O(k)) → 실제 overlap bin만 처리
                start_bin = np.searchsorted(bins, candle_low, side='right') - 1
                end_bin = np.searchsorted(bins, candle_high, side='left')

                # 범위 제한
                start_bin = max(0, start_bin)
                end_bin = min(num_bins, end_bin)

                # 해당 범위의 bin들만 처리 (평균 2-3개, 기존 20개 → 90% 감소)
                for bin_idx in range(start_bin, end_bin):
                    bin_start = bins[bin_idx]
                    bin_end = bins[bin_idx + 1]

                    # 캔들과 bin의 교집합 높이
                    overlap_start = max(candle_low, bin_start)
                    overlap_end = min(candle_high, bin_end)

                    if overlap_start < overlap_end:
                        overlap_ratio = (overlap_end - overlap_start) / candle_height
                        bin_volumes[bin_idx] += volume * overlap_ratio

        # 상위 percentile 매물대 찾기
        # 누적 거래량 기준으로 상위 top_percentile에 해당하는 가격대 찾기
        total_volume = bin_volumes.sum()

        if total_volume == 0:
            return None

        # 가장 높은 가격부터 누적
        cumulative_from_top = 0.0
        threshold_volume = total_volume * top_percentile

        for bin_idx in range(num_bins - 1, -1, -1):
            cumulative_from_top += bin_volumes[bin_idx]

            if cumulative_from_top >= threshold_volume:
                # 이 bin의 하단을 저항선으로 설정
                resistance = bins[bin_idx]
                return resistance

        # 기본값: 최고가
        return df['high'].max()
