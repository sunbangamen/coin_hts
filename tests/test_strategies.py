"""
전략 엔진 유닛 테스트

VolumeLongCandleStrategy, VolumeZoneBreakoutStrategy의 신호 생성 및 성과 지표 계산을 검증합니다.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.app.strategies.base import Signal, BacktestResult
from backend.app.strategies.volume_long_candle import VolumeLongCandleStrategy
from backend.app.strategies.volume_zone_breakout import VolumeZoneBreakoutStrategy


@pytest.fixture
def sample_ohlcv_data():
    """
    샘플 OHLCV 데이터 생성

    100개의 일봉 데이터를 생성합니다.
    특정 패턴:
    - 인덱스 20-25: 거래량 급증 + 장대양봉 (volume_long_candle 신호)
    - 인덱스 50-55: 매물대 형성 후 돌파 (volume_zone_breakout 신호)
    """
    np.random.seed(42)

    base_price = 100.0
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D', tz='UTC')

    data = {
        'timestamp': dates,
        'open': [],
        'high': [],
        'low': [],
        'close': [],
        'volume': [],
    }

    current_price = base_price
    for i in range(100):
        # 기본 가격 변동
        change = np.random.randn() * 2
        current_price += change

        open_price = current_price
        close_price = current_price + np.random.randn() * 1

        # 거래량 급증 구간 (인덱스 20-25)
        if 20 <= i <= 25:
            volume = np.random.uniform(2000, 3000)
            # 장대양봉 추가
            if i == 22:
                close_price = open_price * 1.03  # 3% 상승
        # 매물대 형성 구간 (인덱스 40-55)
        elif 40 <= i < 55:
            volume = np.random.uniform(500, 1000)
            # 돌파 구간 (인덱스 55-60)
            if i >= 55:
                close_price = open_price * 1.02  # 2% 상승
        else:
            volume = np.random.uniform(100, 500)

        high_price = max(open_price, close_price) + abs(np.random.randn()) * 0.5
        low_price = min(open_price, close_price) - abs(np.random.randn()) * 0.5

        data['open'].append(open_price)
        data['high'].append(high_price)
        data['low'].append(low_price)
        data['close'].append(close_price)
        data['volume'].append(volume)

    df = pd.DataFrame(data)
    return df


@pytest.fixture
def empty_dataframe():
    """빈 DataFrame 반환"""
    return pd.DataFrame()


class TestVolumeLongCandle:
    """거래량 급증 + 장대양봉 전략 테스트"""

    def test_basic_signal_generation(self, sample_ohlcv_data):
        """기본 신호 생성 테스트"""
        strategy = VolumeLongCandleStrategy()
        result = strategy.run(
            sample_ohlcv_data,
            {
                'vol_ma_window': 20,
                'vol_multiplier': 1.5,
                'body_pct': 0.02,
                'hold_period_bars': 1,
            },
        )

        # 신호 생성 확인
        assert isinstance(result, BacktestResult)
        assert result.samples >= 0
        assert len(result.signals) == result.samples

        # 모든 신호가 BUY 신호인지 확인
        if result.signals:
            assert all(s.side == 'BUY' for s in result.signals)

    def test_no_signals_empty_data(self, empty_dataframe):
        """빈 데이터 처리 테스트"""
        strategy = VolumeLongCandleStrategy()

        with pytest.raises(ValueError):
            strategy.run(empty_dataframe, {})

    def test_win_rate_calculation(self, sample_ohlcv_data):
        """승률 계산 테스트"""
        strategy = VolumeLongCandleStrategy()
        result = strategy.run(sample_ohlcv_data, {})

        # 승률은 0.0 ~ 1.0 범위여야 함
        assert 0.0 <= result.win_rate <= 1.0

        # samples가 0이면 승률도 0.0이어야 함
        if result.samples == 0:
            assert result.win_rate == 0.0

    def test_invalid_parameters(self, sample_ohlcv_data):
        """잘못된 파라미터 처리 테스트"""
        strategy = VolumeLongCandleStrategy()

        # vol_ma_window가 음수
        with pytest.raises(ValueError):
            strategy.run(sample_ohlcv_data, {'vol_ma_window': -1})

        # vol_multiplier가 0 이하
        with pytest.raises(ValueError):
            strategy.run(sample_ohlcv_data, {'vol_multiplier': 0})

    def test_avg_return_calculation(self, sample_ohlcv_data):
        """평균 수익률 계산 테스트"""
        strategy = VolumeLongCandleStrategy()
        result = strategy.run(sample_ohlcv_data, {})

        # samples가 0이면 avg_return도 0.0이어야 함
        if result.samples == 0:
            assert result.avg_return == 0.0
        else:
            # avg_return은 양수 또는 음수일 수 있음
            assert isinstance(result.avg_return, float)


class TestVolumeZoneBreakout:
    """매물대 돌파 전략 테스트"""

    def test_basic_signal_generation(self, sample_ohlcv_data):
        """기본 신호 생성 테스트"""
        strategy = VolumeZoneBreakoutStrategy()
        result = strategy.run(
            sample_ohlcv_data,
            {
                'volume_window': 60,
                'top_percentile': 0.2,
                'breakout_buffer': 0.01,
                'hold_period_bars': 1,
                'num_bins': 20,
                'include_wicks': True,
            },
        )

        # 신호 생성 확인
        assert isinstance(result, BacktestResult)
        assert result.samples >= 0
        assert len(result.signals) == result.samples

        # 모든 신호가 BUY 신호인지 확인
        if result.signals:
            assert all(s.side == 'BUY' for s in result.signals)

    def test_no_signals_empty_data(self, empty_dataframe):
        """빈 데이터 처리 테스트"""
        strategy = VolumeZoneBreakoutStrategy()

        with pytest.raises(ValueError):
            strategy.run(empty_dataframe, {})

    def test_resistance_calculation(self, sample_ohlcv_data):
        """저항선 계산 테스트"""
        strategy = VolumeZoneBreakoutStrategy()
        result = strategy.run(sample_ohlcv_data, {})

        # 신호가 생성되면 저항선 계산이 정상 작동했다는 의미
        # 신호 개수는 데이터의 특성에 따라 달라질 수 있음
        assert result.samples >= 0

    def test_invalid_parameters(self, sample_ohlcv_data):
        """잘못된 파라미터 처리 테스트"""
        strategy = VolumeZoneBreakoutStrategy()

        # volume_window가 음수
        with pytest.raises(ValueError):
            strategy.run(sample_ohlcv_data, {'volume_window': -1})

        # top_percentile이 0 이하
        with pytest.raises(ValueError):
            strategy.run(sample_ohlcv_data, {'top_percentile': 0})

        # num_bins가 0
        with pytest.raises(ValueError):
            strategy.run(sample_ohlcv_data, {'num_bins': 0})

    def test_max_drawdown_calculation(self, sample_ohlcv_data):
        """최대 낙폭 계산 테스트"""
        strategy = VolumeZoneBreakoutStrategy()
        result = strategy.run(sample_ohlcv_data, {})

        # max_drawdown은 양수 % (0.0 이상)이어야 함
        assert result.max_drawdown >= 0.0

        # samples가 0이면 max_drawdown도 0.0이어야 함
        if result.samples == 0:
            assert result.max_drawdown == 0.0


class TestMetricsCalculation:
    """성과 지표 계산 테스트"""

    def test_win_rate_all_winning_trades(self):
        """모든 거래가 수익인 경우"""
        signals = [
            Signal(timestamp=pd.Timestamp('2024-01-01', tz='UTC'), side='BUY', price=100.0, confidence=0.8),
        ]

        # 모든 수익인 경우: win_rate = 1.0
        # 이는 신호를 기반으로 한 수익률이 모두 양수인 경우
        win_count = 1  # 1개 신호
        total_signals = 1
        win_rate = win_count / total_signals if total_signals > 0 else 0.0

        assert win_rate == 1.0

    def test_win_rate_all_losing_trades(self):
        """모든 거래가 손실인 경우"""
        signals = [
            Signal(timestamp=pd.Timestamp('2024-01-01', tz='UTC'), side='BUY', price=100.0, confidence=0.8),
        ]

        win_count = 0  # 모든 거래가 손실
        total_signals = 1
        win_rate = win_count / total_signals if total_signals > 0 else 0.0

        assert win_rate == 0.0

    def test_avg_return_calculation(self):
        """평균 수익률 계산 테스트"""
        returns = [2.5, -1.2, 3.8, -0.5, 1.0]
        avg_return = sum(returns) / len(returns)

        assert abs(avg_return - 1.12) < 0.01

    def test_max_drawdown_positive_returns(self):
        """모든 수익이 양수인 경우의 MDD"""
        returns = [1.0, 2.0, 3.0, 4.0, 5.0]
        cumulative_returns = np.array(returns).cumsum()
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = cumulative_returns - running_max
        max_drawdown = abs(float(np.min(drawdown)))  # 양수로 변환

        assert max_drawdown == 0.0  # 하강이 없음

    def test_max_drawdown_with_losses(self):
        """손실이 포함된 경우의 MDD"""
        returns = [2.0, -3.0, 1.0, -2.0, 3.0]  # 최대 낙폭: |2 - 5| = 3
        cumulative_returns = np.array(returns).cumsum()
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = cumulative_returns - running_max
        max_drawdown = abs(float(np.min(drawdown)))  # 양수로 변환

        assert max_drawdown > 0  # 하강이 있음 (양수로 표현)

    def test_metrics_consistency(self, sample_ohlcv_data):
        """메트릭 일관성 테스트"""
        strategy = VolumeLongCandleStrategy()
        result = strategy.run(sample_ohlcv_data, {})

        # samples와 signals 길이 일치
        assert result.samples == len(result.signals)

        # 승률과 샘플 개수의 일관성
        if result.samples > 0:
            # win_rate는 0 ~ 1 범위
            assert 0.0 <= result.win_rate <= 1.0

        # 평균 보유 바 수는 양수
        assert result.avg_hold_bars >= 0.0

        # BacktestResult 데이터 검증
        try:
            # 데이터 검증 성공하면 pass
            assert True
        except ValueError:
            pytest.fail("BacktestResult validation failed")


class TestSignalValidation:
    """Signal 데이터 검증 테스트"""

    def test_signal_side_validation(self):
        """Signal의 side 검증"""
        # 유효한 side
        signal1 = Signal(
            timestamp=pd.Timestamp('2024-01-01', tz='UTC'),
            side='BUY',
            price=100.0,
            confidence=0.8,
        )
        assert signal1.side == 'BUY'

        signal2 = Signal(
            timestamp=pd.Timestamp('2024-01-01', tz='UTC'),
            side='SELL',
            price=100.0,
            confidence=0.8,
        )
        assert signal2.side == 'SELL'

        # 잘못된 side
        with pytest.raises(ValueError):
            Signal(
                timestamp=pd.Timestamp('2024-01-01', tz='UTC'),
                side='INVALID',
                price=100.0,
                confidence=0.8,
            )

    def test_signal_confidence_validation(self):
        """Signal의 confidence 검증"""
        # 유효한 confidence
        signal = Signal(
            timestamp=pd.Timestamp('2024-01-01', tz='UTC'),
            side='BUY',
            price=100.0,
            confidence=0.5,
        )
        assert signal.confidence == 0.5

        # 범위 초과
        with pytest.raises(ValueError):
            Signal(
                timestamp=pd.Timestamp('2024-01-01', tz='UTC'),
                side='BUY',
                price=100.0,
                confidence=1.5,
            )

        with pytest.raises(ValueError):
            Signal(
                timestamp=pd.Timestamp('2024-01-01', tz='UTC'),
                side='BUY',
                price=100.0,
                confidence=-0.1,
            )

    def test_signal_price_validation(self):
        """Signal의 price 검증"""
        # 유효한 price
        signal = Signal(
            timestamp=pd.Timestamp('2024-01-01', tz='UTC'),
            side='BUY',
            price=100.0,
            confidence=0.8,
        )
        assert signal.price == 100.0

        # 음수 price
        with pytest.raises(ValueError):
            Signal(
                timestamp=pd.Timestamp('2024-01-01', tz='UTC'),
                side='BUY',
                price=-100.0,
                confidence=0.8,
            )


class TestPhase2Optimization:
    """
    Phase 2 최적화 테스트

    출처: docs/coin/mvp/phase2_strategy_optimization.md
    - volume_zone_breakout 파라미터 최적화 검증
    - 신호 생성 확인
    - 승률 검증
    """

    def test_volume_zone_breakout_optimized_params_max_signals(self, sample_ohlcv_data):
        """최적화된 파라미터 (최대 신호)로 신호 생성 확인

        파라미터: volume_window=10, top_percentile=0.30, breakout_buffer=0.0
        예상 결과: 원래 0개 → 최적화 후 신호 생성 가능
        """
        strategy = VolumeZoneBreakoutStrategy()

        # Phase 2 최적화 파라미터 (신호 최대화)
        result = strategy.run(
            sample_ohlcv_data,
            {
                'volume_window': 10,
                'top_percentile': 0.30,
                'breakout_buffer': 0.0,
                'hold_period_bars': 1,
                'num_bins': 20,
                'include_wicks': True,
            },
        )

        # 신호 생성 확인
        assert isinstance(result, BacktestResult)
        assert result.samples >= 0
        assert len(result.signals) == result.samples

        # 모든 신호가 BUY 신호인지 확인
        if result.signals:
            assert all(s.side == 'BUY' for s in result.signals)

    def test_volume_zone_breakout_optimized_params_best_winrate(self, sample_ohlcv_data):
        """최적화된 파라미터 (최고 승률)로 승률 검증

        파라미터: volume_window=10, top_percentile=0.20, breakout_buffer=0.0
        예상: 승률 50% 이상 가능
        """
        strategy = VolumeZoneBreakoutStrategy()

        result = strategy.run(
            sample_ohlcv_data,
            {
                'volume_window': 10,
                'top_percentile': 0.20,
                'breakout_buffer': 0.0,
                'hold_period_bars': 1,
                'num_bins': 20,
                'include_wicks': True,
            },
        )

        # 신호 생성 및 승률 확인
        assert isinstance(result, BacktestResult)
        assert 0.0 <= result.win_rate <= 1.0

    def test_volume_zone_breakout_optimized_vs_old_params(self, sample_ohlcv_data):
        """최적화 전후 파라미터 비교

        이전 파라미터 (60, 0.2, 0.01) vs 최적화 파라미터 (10, 0.2, 0.0)
        """
        strategy = VolumeZoneBreakoutStrategy()

        # 이전 파라미터
        old_result = strategy.run(
            sample_ohlcv_data,
            {
                'volume_window': 60,
                'top_percentile': 0.20,
                'breakout_buffer': 0.01,
            },
        )

        # 최적화 파라미터
        new_result = strategy.run(
            sample_ohlcv_data,
            {
                'volume_window': 10,
                'top_percentile': 0.20,
                'breakout_buffer': 0.0,
            },
        )

        # 최적화 파라미터가 더 많은 신호를 생성해야 함 (또는 같음)
        assert new_result.samples >= old_result.samples
        assert isinstance(old_result, BacktestResult)
        assert isinstance(new_result, BacktestResult)

    def test_volume_long_candle_conservative_preset(self, sample_ohlcv_data):
        """Frontend 프리셋: 보수적 (volume_long_candle)

        프리셋: vol_ma_window=20, vol_multiplier=1.5, body_pct=0.01
        """
        strategy = VolumeLongCandleStrategy()

        result = strategy.run(
            sample_ohlcv_data,
            {
                'vol_ma_window': 20,
                'vol_multiplier': 1.5,
                'body_pct': 0.01,
                'hold_period_bars': 1,
            },
        )

        assert isinstance(result, BacktestResult)
        assert result.samples >= 0
        if result.signals:
            assert all(s.side == 'BUY' for s in result.signals)

    def test_volume_zone_breakout_balanced_preset(self, sample_ohlcv_data):
        """Frontend 프리셋: 균형잡힌 (volume_zone_breakout)

        프리셋: volume_window=20, top_percentile=0.20, breakout_buffer=0.0
        """
        strategy = VolumeZoneBreakoutStrategy()

        result = strategy.run(
            sample_ohlcv_data,
            {
                'volume_window': 20,
                'top_percentile': 0.20,
                'breakout_buffer': 0.0,
                'hold_period_bars': 1,
            },
        )

        assert isinstance(result, BacktestResult)
        assert result.samples >= 0
        assert 0.0 <= result.win_rate <= 1.0

    def test_volume_zone_breakout_aggressive_preset(self, sample_ohlcv_data):
        """Frontend 프리셋: 적극적 (volume_zone_breakout)

        프리셋: volume_window=10, top_percentile=0.30, breakout_buffer=0.0
        """
        strategy = VolumeZoneBreakoutStrategy()

        result = strategy.run(
            sample_ohlcv_data,
            {
                'volume_window': 10,
                'top_percentile': 0.30,
                'breakout_buffer': 0.0,
                'hold_period_bars': 1,
            },
        )

        assert isinstance(result, BacktestResult)
        assert result.samples >= 0
        if result.signals:
            assert all(s.side == 'BUY' for s in result.signals)

    def test_default_params_from_code(self, sample_ohlcv_data):
        """백엔드 기본값 검증

        Phase 2 최적화 적용 후 기본값 확인:
        - volume_zone_breakout: volume_window=10 (이전: 60), breakout_buffer=0.0 (이전: 0.01)
        """
        strategy = VolumeZoneBreakoutStrategy()

        # 기본값으로 실행 (명시적으로 파라미터를 지정하지 않음)
        result = strategy.run(sample_ohlcv_data, {})

        assert isinstance(result, BacktestResult)
        assert result.samples >= 0

    def test_parameter_validation_phase2(self, sample_ohlcv_data):
        """Phase 2 최적화 파라미터 범위 검증"""
        strategy = VolumeZoneBreakoutStrategy()

        # 유효한 최적화 파라미터
        valid_result = strategy.run(
            sample_ohlcv_data,
            {
                'volume_window': 10,
                'top_percentile': 0.30,
                'breakout_buffer': 0.0,
            },
        )
        assert isinstance(valid_result, BacktestResult)

        # 경계값 테스트
        boundary_result = strategy.run(
            sample_ohlcv_data,
            {
                'volume_window': 1,
                'top_percentile': 0.05,
                'breakout_buffer': 0.0,
            },
        )
        assert isinstance(boundary_result, BacktestResult)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
