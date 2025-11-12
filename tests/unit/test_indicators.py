"""
Task 4: 기술 지표 계산 모듈 단위 테스트 (Feature Breakdown #23)

테스트 대상:
- 상승률 계산 (1D, 1W, 1M)
- 거래량 계산
- 거래대금 계산
- 이동평균선 이격도 계산
- 이동평균선 정배열/역배열 판단
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.app.indicators.calculator import IndicatorCalculator


class TestChangeRateCalculation:
    """상승률 계산 테스트"""

    @pytest.fixture
    def calculator(self):
        return IndicatorCalculator()

    @pytest.fixture
    def simple_df(self):
        """간단한 테스트 데이터"""
        return pd.DataFrame({
            'close': [100, 110, 120, 130, 140]  # 계속 상승
        })

    def test_change_rate_1d_positive(self, calculator, simple_df):
        """1일 상승률 - 양수"""
        rate = calculator.calculate_change_rate(simple_df, '1D')
        # (140 - 130) / 130 = 0.0769...
        assert rate > 0
        assert 0.07 < rate < 0.08

    def test_change_rate_1d_no_data(self, calculator):
        """1일 상승률 - 데이터 부족"""
        df = pd.DataFrame({'close': [100]})
        with pytest.raises(ValueError):
            calculator.calculate_change_rate(df, '1D')

    def test_change_rate_1w(self, calculator):
        """1주일 상승률"""
        # 10개 데이터: 100, 110, 120, ..., 190
        df = pd.DataFrame({
            'close': [100 + i * 10 for i in range(10)]
        })
        rate = calculator.calculate_change_rate(df, '1W')
        # (190 - 100) / 100 = 0.9
        assert abs(rate - 0.9) < 0.01

    def test_change_rate_1m(self, calculator):
        """1개월 상승률"""
        # 25개 데이터
        df = pd.DataFrame({
            'close': [100 + i * 2 for i in range(25)]
        })
        rate = calculator.calculate_change_rate(df, '1M')
        # (148 - 100) / 100 = 0.48
        assert abs(rate - 0.48) < 0.01

    def test_change_rate_negative(self, calculator):
        """하락 상승률"""
        df = pd.DataFrame({
            'close': [100, 90, 80, 70, 60]  # 계속 하락
        })
        rate = calculator.calculate_change_rate(df, '1D')
        assert rate < 0  # 음수

    def test_change_rate_zero_division(self, calculator):
        """0으로 나누기 (이전 가격이 0)"""
        df = pd.DataFrame({
            'close': [0, 100]
        })
        rate = calculator.calculate_change_rate(df, '1D')
        assert rate == 0.0


class TestVolumeCalculation:
    """거래량 계산 테스트"""

    @pytest.fixture
    def calculator(self):
        return IndicatorCalculator()

    def test_volume_1d(self, calculator):
        """1일 거래량"""
        df = pd.DataFrame({
            'volume': [100, 200, 300, 400, 500]
        })
        volume = calculator.calculate_volume(df, '1D')
        assert volume == 500  # 마지막 값

    def test_volume_1w(self, calculator):
        """1주일 거래량 합"""
        df = pd.DataFrame({
            'volume': [100] * 10  # 10일 동안 각 100
        })
        volume = calculator.calculate_volume(df, '1W')
        # 최근 7일: 100 * 7 = 700
        assert volume == 700

    def test_volume_1m(self, calculator):
        """1개월 거래량 합"""
        df = pd.DataFrame({
            'volume': [100] * 25  # 25일 동안 각 100
        })
        volume = calculator.calculate_volume(df, '1M')
        # 최근 20일: 100 * 20 = 2000
        assert volume == 2000

    def test_volume_insufficient_data(self, calculator):
        """데이터 부족 시 전체 합계"""
        df = pd.DataFrame({
            'volume': [100, 200, 300]  # 3일만
        })
        volume = calculator.calculate_volume(df, '1W')
        # 7일 필요하지만 3일만 있으므로 전체 합계
        assert volume == 600


class TestTradeAmountCalculation:
    """거래대금 계산 테스트"""

    @pytest.fixture
    def calculator(self):
        return IndicatorCalculator()

    def test_trade_amount_1d(self, calculator):
        """1일 거래대금"""
        df = pd.DataFrame({
            'close': [100, 200, 300, 400, 500],
            'volume': [10, 20, 30, 40, 50]
        })
        amount = calculator.calculate_trade_amount(df, '1D')
        # 500 * 50 = 25000
        assert amount == 25000

    def test_trade_amount_1w(self, calculator):
        """1주일 거래대금"""
        df = pd.DataFrame({
            'close': [100] * 10,
            'volume': [10] * 10
        })
        amount = calculator.calculate_trade_amount(df, '1W')
        # 최근 7일: (100 * 10) * 7 = 7000
        assert amount == 7000

    def test_trade_amount_multiple_prices(self, calculator):
        """거래대금 (가격 변동)"""
        df = pd.DataFrame({
            'close': [100, 200],
            'volume': [100, 100]
        })
        # 각 날짜: 100*100=10000, 200*100=20000
        amount = calculator.calculate_trade_amount(df, '1D')
        # 마지막 날짜 (200 * 100 = 20000)
        assert amount == 20000


class TestMADivergenceCalculation:
    """이동평균선 이격도 계산 테스트"""

    @pytest.fixture
    def calculator(self):
        return IndicatorCalculator()

    def test_ma_divergence_above_ma(self, calculator):
        """현재가가 MA 위에 있을 때"""
        df = pd.DataFrame({
            'close': [100] * 20 + [110]  # MA20 = 100, 현재가 = 110
        })
        divergence = calculator.calculate_ma_divergence(df, 20)
        # (110 / 100 - 1) * 100 = 10%
        assert abs(divergence - 10.0) < 0.1

    def test_ma_divergence_below_ma(self, calculator):
        """현재가가 MA 아래에 있을 때"""
        df = pd.DataFrame({
            'close': [100] * 20 + [90]  # MA20 = 100, 현재가 = 90
        })
        divergence = calculator.calculate_ma_divergence(df, 20)
        # (90 / 100 - 1) * 100 = -10%
        assert abs(divergence + 10.0) < 0.1

    def test_ma_divergence_at_ma(self, calculator):
        """현재가가 MA와 같을 때"""
        df = pd.DataFrame({
            'close': [100] * 21  # MA20 = 100, 현재가 = 100
        })
        divergence = calculator.calculate_ma_divergence(df, 20)
        # (100 / 100 - 1) * 100 = 0%
        assert abs(divergence) < 0.01

    def test_ma_divergence_insufficient_data(self, calculator):
        """데이터 부족"""
        df = pd.DataFrame({
            'close': [100, 110, 120]  # MA20 계산 불가
        })
        divergence = calculator.calculate_ma_divergence(df, 20)
        assert divergence == 0.0


class TestMAAlignmentCheck:
    """이동평균선 정배열/역배열 테스트"""

    @pytest.fixture
    def calculator(self):
        return IndicatorCalculator()

    def test_ma_golden_cross(self, calculator):
        """정배열: MA5 > MA20 > MA60 (상승)"""
        # 상승 추세: 작은 값부터 큰 값으로
        df = pd.DataFrame({
            'close': list(range(1, 70))  # 1부터 69까지 상승
        })
        alignment = calculator.check_ma_alignment(df, [5, 20, 60])
        assert alignment == 'golden_cross'

    def test_ma_dead_cross(self, calculator):
        """역배열: MA5 < MA20 < MA60 (하락)"""
        # 하락 추세: 큰 값부터 작은 값으로
        df = pd.DataFrame({
            'close': list(range(70, 0, -1))  # 69부터 1까지 하락
        })
        alignment = calculator.check_ma_alignment(df, [5, 20, 60])
        assert alignment == 'dead_cross'

    def test_ma_mixed(self, calculator):
        """혼조: 정배열도 역배열도 아님"""
        # 데이터 부족하거나 혼조
        df = pd.DataFrame({
            'close': [100, 110, 100, 110, 100, 110] * 10  # 진동
        })
        alignment = calculator.check_ma_alignment(df, [5, 20, 60])
        assert alignment == 'mixed'

    def test_ma_insufficient_data(self, calculator):
        """데이터 부족"""
        df = pd.DataFrame({
            'close': [100, 110, 120]
        })
        alignment = calculator.check_ma_alignment(df, [5, 20, 60])
        assert alignment == 'mixed'


class TestCalculateAll:
    """전체 지표 계산 테스트"""

    @pytest.fixture
    def calculator(self):
        return IndicatorCalculator()

    @pytest.fixture
    def real_world_df(self):
        """실제 데이터 유사 샘플"""
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=100)
        close_prices = 50000 + np.cumsum(np.random.randn(100) * 1000)
        volumes = 1000 + np.random.randn(100) * 100

        return pd.DataFrame({
            'timestamp': dates,
            'open': close_prices - 100,
            'high': close_prices + 100,
            'low': close_prices - 100,
            'close': close_prices,
            'volume': np.abs(volumes)
        })

    def test_calculate_all_returns_dict(self, calculator, real_world_df):
        """모든 지표 계산 반환"""
        result = calculator.calculate_all(real_world_df)

        # 반환 타입 검증
        assert isinstance(result, dict)

        # 모든 지표가 포함되어 있는지 검증
        expected_keys = [
            'change_rate_1d', 'change_rate_1w', 'change_rate_1m',
            'volume_1d', 'volume_1w', 'volume_1m',
            'trade_amount_1d', 'trade_amount_1w', 'trade_amount_1m',
            'ma_divergence_20', 'ma_divergence_60',
            'ma_alignment'
        ]
        for key in expected_keys:
            assert key in result

    def test_calculate_all_values_are_valid(self, calculator, real_world_df):
        """모든 지표 값이 유효한지 검증"""
        result = calculator.calculate_all(real_world_df)

        # 숫자 지표는 float
        assert isinstance(result['change_rate_1d'], float)
        assert isinstance(result['volume_1d'], float)
        assert isinstance(result['trade_amount_1d'], float)

        # MA 정배열은 문자열
        assert isinstance(result['ma_alignment'], str)
        assert result['ma_alignment'] in ['golden_cross', 'dead_cross', 'mixed']

    def test_calculate_all_no_nan(self, calculator, real_world_df):
        """결과에 NaN이 없는지 확인"""
        result = calculator.calculate_all(real_world_df)

        for key, value in result.items():
            if isinstance(value, (int, float)):
                assert not np.isnan(value), f"{key} is NaN"


class TestErrorHandling:
    """에러 처리 테스트"""

    @pytest.fixture
    def calculator(self):
        return IndicatorCalculator()

    def test_empty_dataframe(self, calculator):
        """빈 DataFrame"""
        df = pd.DataFrame()
        with pytest.raises(ValueError):
            calculator.calculate_change_rate(df, '1D')

    def test_missing_close_column(self, calculator):
        """close 컬럼 없음"""
        df = pd.DataFrame({'volume': [100, 200]})
        with pytest.raises(ValueError):
            calculator.calculate_change_rate(df, '1D')

    def test_missing_volume_column(self, calculator):
        """volume 컬럼 없음"""
        df = pd.DataFrame({'close': [100, 200]})
        with pytest.raises(ValueError):
            calculator.calculate_volume(df, '1D')

    def test_none_dataframe(self, calculator):
        """None DataFrame"""
        with pytest.raises(ValueError):
            calculator.calculate_change_rate(None, '1D')
