"""
data_loader 모듈 유닛 테스트

테스트 픽스처는 실행 시점에 임시 디렉터리에 parquet 파일을 동적으로 생성하며,
심볼·타임프레임 주입 및 UTC 변환 로직을 검증합니다.
"""

import pytest
import pandas as pd
import numpy as np
import pytz
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import HTTPException
import sys
from tempfile import TemporaryDirectory

# 테스트 실행 시점에 backend 모듈을 임포트할 수 있도록 경로 설정
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.data_loader import (
    load_ohlcv_data,
    _normalize_timezone,
    _extract_years_from_range,
    _validate_dataframe,
)


class TestNormalizeTimezone:
    """타임존 정규화 함수 테스트"""

    def test_timezone_aware_string_with_kst(self):
        """KST 타임존 정보가 있는 문자열 변환"""
        result = _normalize_timezone("2024-01-01T12:00:00+09:00")
        assert result.tz is not None
        assert result.hour == 3  # KST 12시 -> UTC 3시

    def test_timezone_naive_string(self):
        """타임존 정보 없는 문자열은 KST로 간주"""
        result = _normalize_timezone("2024-01-01T12:00:00")
        assert result.tz is not None
        assert result.hour == 3  # KST 12시 -> UTC 3시

    def test_date_only_string(self):
        """날짜만 있는 문자열 변환"""
        result = _normalize_timezone("2024-01-01")
        assert result.tz is not None
        # 자정 KST -> UTC 15시 (전날)
        assert result.year == 2023
        assert result.month == 12
        assert result.day == 31
        assert result.hour == 15

    def test_invalid_date_format(self):
        """잘못된 날짜 형식"""
        with pytest.raises(ValueError):
            _normalize_timezone("invalid-date")


class TestExtractYearsFromRange:
    """연도 추출 함수 테스트"""

    def test_single_year(self):
        """단일 연도 범위"""
        result = _extract_years_from_range("2024-01-01", "2024-12-31")
        assert result == [2024]

    def test_multiple_years(self):
        """여러 연도 범위"""
        result = _extract_years_from_range("2023-06-01", "2025-06-01")
        assert result == [2023, 2024, 2025]

    def test_start_after_end_raises_error(self):
        """시작 날짜가 종료 날짜보다 나중인 경우"""
        with pytest.raises(HTTPException) as exc_info:
            _extract_years_from_range("2024-12-31", "2024-01-01")
        assert exc_info.value.status_code == 422


class TestValidateDataFrame:
    """DataFrame 검증 함수 테스트"""

    def test_valid_dataframe(self):
        """필수 컬럼이 모두 있는 경우"""
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10),
            'open': np.random.rand(10),
            'high': np.random.rand(10),
            'low': np.random.rand(10),
            'close': np.random.rand(10),
            'volume': np.random.rand(10),
        })
        # 예외 없이 통과해야 함
        _validate_dataframe(df, "BTC_KRW", "1D")

    def test_valid_dataframe_with_datetime_index(self):
        """timestamp가 인덱스인 경우"""
        df = pd.DataFrame({
            'open': np.random.rand(10),
            'high': np.random.rand(10),
            'low': np.random.rand(10),
            'close': np.random.rand(10),
            'volume': np.random.rand(10),
        }, index=pd.date_range('2024-01-01', periods=10))
        # 예외 없이 통과해야 함
        _validate_dataframe(df, "BTC_KRW", "1D")

    def test_missing_required_column(self):
        """필수 컬럼 누락"""
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10),
            'open': np.random.rand(10),
            # 'high' 누락
            'low': np.random.rand(10),
            'close': np.random.rand(10),
            'volume': np.random.rand(10),
        })
        with pytest.raises(HTTPException) as exc_info:
            _validate_dataframe(df, "BTC_KRW", "1D")
        assert exc_info.value.status_code == 400

    def test_missing_timestamp(self):
        """timestamp 컬럼 누락"""
        df = pd.DataFrame({
            'open': np.random.rand(10),
            'high': np.random.rand(10),
            'low': np.random.rand(10),
            'close': np.random.rand(10),
            'volume': np.random.rand(10),
        })
        with pytest.raises(HTTPException) as exc_info:
            _validate_dataframe(df, "BTC_KRW", "1D")
        assert exc_info.value.status_code == 400


class TestLoadOhlcvData:
    """load_ohlcv_data 함수 통합 테스트"""

    @pytest.fixture
    def sample_data_dir(self):
        """테스트 데이터 디렉토리 생성"""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # 테스트 데이터 생성: BTC_KRW/1D/2024.parquet
            btc_dir = tmpdir_path / "BTC_KRW" / "1D"
            btc_dir.mkdir(parents=True)

            dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
            df_btc = pd.DataFrame({
                'timestamp': dates,
                'open': np.random.rand(len(dates)) * 100,
                'high': np.random.rand(len(dates)) * 100,
                'low': np.random.rand(len(dates)) * 100,
                'close': np.random.rand(len(dates)) * 100,
                'volume': np.random.rand(len(dates)) * 1000,
            })
            df_btc.to_parquet(btc_dir / '2024.parquet')

            # 테스트 데이터 생성: XRP_KRW/1D/2024.parquet
            xrp_dir = tmpdir_path / "XRP_KRW" / "1D"
            xrp_dir.mkdir(parents=True)

            df_xrp = pd.DataFrame({
                'timestamp': dates,
                'open': np.random.rand(len(dates)) * 50,
                'high': np.random.rand(len(dates)) * 50,
                'low': np.random.rand(len(dates)) * 50,
                'close': np.random.rand(len(dates)) * 50,
                'volume': np.random.rand(len(dates)) * 500,
            })
            df_xrp.to_parquet(xrp_dir / '2024.parquet')

            yield tmpdir_path

    def test_load_single_symbol(self, sample_data_dir):
        """단일 심볼 로드"""
        result = load_ohlcv_data(
            symbols=["BTC_KRW"],
            start_date="2024-01-01",
            end_date="2024-01-31",
            timeframe="1d",
            data_root=str(sample_data_dir)
        )

        assert not result.empty
        assert 'BTC_KRW' in result['symbol'].values
        assert all(col in result.columns for col in ['timestamp', 'symbol', 'timeframe', 'open', 'high', 'low', 'close', 'volume'])
        # 1월은 31일
        assert len(result) == 31

    def test_load_multiple_symbols(self, sample_data_dir):
        """여러 심볼 로드"""
        result = load_ohlcv_data(
            symbols=["BTC_KRW", "XRP_KRW"],
            start_date="2024-01-01",
            end_date="2024-01-31",
            timeframe="1d",
            data_root=str(sample_data_dir)
        )

        assert not result.empty
        assert set(result['symbol'].unique()) == {'BTC_KRW', 'XRP_KRW'}
        # 각 심볼당 31일
        assert len(result) == 62

    def test_date_range_filtering(self, sample_data_dir):
        """날짜 범위 필터링"""
        result = load_ohlcv_data(
            symbols=["BTC_KRW"],
            start_date="2024-06-01",
            end_date="2024-06-30",
            timeframe="1d",
            data_root=str(sample_data_dir)
        )

        assert not result.empty
        # 6월은 30일
        assert len(result) == 30

    def test_timeframe_normalization(self, sample_data_dir):
        """타임프레임 정규화 (소문자 입력 -> 대문자 저장)"""
        result = load_ohlcv_data(
            symbols=["BTC_KRW"],
            start_date="2024-01-01",
            end_date="2024-01-31",
            timeframe="1d",  # 소문자 입력
            data_root=str(sample_data_dir)
        )

        assert all(tf == '1D' for tf in result['timeframe'])

    def test_symbol_injection(self, sample_data_dir):
        """심볼 정보 주입 (파일 경로에서만 추출)"""
        result = load_ohlcv_data(
            symbols=["BTC_KRW"],
            start_date="2024-01-01",
            end_date="2024-01-31",
            timeframe="1d",
            data_root=str(sample_data_dir)
        )

        assert all(sym == 'BTC_KRW' for sym in result['symbol'])

    def test_timezone_conversion(self, sample_data_dir):
        """타임존 변환 검증 (UTC 기준으로 반환)"""
        result = load_ohlcv_data(
            symbols=["BTC_KRW"],
            start_date="2024-01-01",
            end_date="2024-01-05",
            timeframe="1d",
            data_root=str(sample_data_dir)
        )

        # timestamp가 UTC 기준인지 확인
        assert result['timestamp'].dt.tz == pytz.UTC or result['timestamp'].dt.tz.zone == 'UTC'

    def test_no_data_found_raises_error(self, sample_data_dir):
        """조회 데이터 없음"""
        with pytest.raises(HTTPException) as exc_info:
            load_ohlcv_data(
                symbols=["UNKNOWN_COIN"],
                start_date="2024-01-01",
                end_date="2024-01-31",
                timeframe="1d",
                data_root=str(sample_data_dir)
            )
        assert exc_info.value.status_code == 404

    def test_invalid_data_root_raises_error(self):
        """존재하지 않는 DATA_ROOT"""
        with pytest.raises(HTTPException) as exc_info:
            load_ohlcv_data(
                symbols=["BTC_KRW"],
                start_date="2024-01-01",
                end_date="2024-01-31",
                timeframe="1d",
                data_root="/nonexistent/path"
            )
        assert exc_info.value.status_code == 404

    def test_invalid_date_format_raises_error(self, sample_data_dir):
        """잘못된 날짜 형식"""
        with pytest.raises(HTTPException) as exc_info:
            load_ohlcv_data(
                symbols=["BTC_KRW"],
                start_date="invalid-date",
                end_date="2024-01-31",
                timeframe="1d",
                data_root=str(sample_data_dir)
            )
        assert exc_info.value.status_code == 422

    def test_start_after_end_raises_error(self, sample_data_dir):
        """시작 날짜가 종료 날짜보다 나중"""
        with pytest.raises(HTTPException) as exc_info:
            load_ohlcv_data(
                symbols=["BTC_KRW"],
                start_date="2024-12-31",
                end_date="2024-01-01",
                timeframe="1d",
                data_root=str(sample_data_dir)
            )
        assert exc_info.value.status_code == 422

    def test_sorted_by_timestamp(self, sample_data_dir):
        """결과가 timestamp 기준 정렬"""
        result = load_ohlcv_data(
            symbols=["BTC_KRW", "XRP_KRW"],
            start_date="2024-01-01",
            end_date="2024-01-10",
            timeframe="1d",
            data_root=str(sample_data_dir)
        )

        # timestamp 순서 확인
        assert (result['timestamp'].iloc[:-1].values <= result['timestamp'].iloc[1:].values).all()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
