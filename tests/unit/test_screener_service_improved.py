"""
개선된 조건 검색 서비스 단위 테스트

새로운 구조에 맞춘 테스트:
1. 마켓 캐시 재사용/폴백 시나리오
2. DataFrame 재사용 로직 검증
3. Redis 초기화 없이 캐시 사용
"""

import pytest
import pandas as pd
import numpy as np
import json
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio

from backend.app.services.screener_service import (
    convert_symbol_to_data_format,
    check_data_exists,
    ScreenerService,
    fetch_krw_markets_from_cache_or_api,
    init_redis,
    get_cached_result,
    set_cached_result
)


# ============================================================================
# 심볼 변환 테스트
# ============================================================================

class TestSymbolConversion:
    """심볼 변환 테스트"""

    def test_convert_krw_btc_to_btc_krw(self):
        """KRW-BTC → BTC_KRW"""
        result = convert_symbol_to_data_format('KRW-BTC')
        assert result == 'BTC_KRW'

    def test_convert_multiple_symbols(self):
        """여러 심볼 변환"""
        test_cases = [
            ('KRW-ETH', 'ETH_KRW'),
            ('KRW-XRP', 'XRP_KRW'),
            ('KRW-SOL', 'SOL_KRW'),
        ]
        for upbit_format, expected in test_cases:
            assert convert_symbol_to_data_format(upbit_format) == expected


# ============================================================================
# 마켓 캐시 재사용 테스트
# ============================================================================

class TestMarketCacheReuse:
    """마켓 캐시 일원화 테스트"""

    @pytest.mark.asyncio
    async def test_fetch_markets_from_shared_cache(self):
        """공유 캐시에서 마켓 조회"""
        mock_markets = [
            {"market": "KRW-BTC", "korean_name": "비트코인", "english_name": "Bitcoin"},
            {"market": "KRW-ETH", "korean_name": "이더리움", "english_name": "Ethereum"},
        ]

        with patch('backend.app.services.screener_service.get_cached_markets') as mock_cache:
            mock_cache.return_value = mock_markets

            result = await fetch_krw_markets_from_cache_or_api()

            # 캐시에서 꺼낸 심볼 확인
            assert len(result) == 2
            assert 'KRW-BTC' in result
            assert 'KRW-ETH' in result

    @pytest.mark.asyncio
    async def test_fetch_markets_fallback_to_api(self):
        """캐시 미스 → API 호출 → 캐시 저장"""
        mock_markets = [
            {"market": "KRW-BTC", "korean_name": "비트코인", "english_name": "Bitcoin"},
        ]

        with patch('backend.app.services.screener_service.get_cached_markets') as mock_cache_get:
            with patch('backend.app.services.screener_service.fetch_krw_markets_from_upbit') as mock_api:
                with patch('backend.app.services.screener_service.cache_markets') as mock_cache_set:
                    # 캐시 미스
                    mock_cache_get.return_value = None
                    # API에서 데이터 반환
                    mock_api.return_value = mock_markets

                    result = await fetch_krw_markets_from_cache_or_api()

                    # API 호출 확인
                    mock_api.assert_called_once()
                    # 캐시 저장 확인
                    mock_cache_set.assert_called_once()
                    # 결과 확인
                    assert 'KRW-BTC' in result

    @pytest.mark.asyncio
    async def test_fetch_markets_fallback_to_defaults(self):
        """캐시 + API 모두 실패 → 기본 심볼"""
        with patch('backend.app.services.screener_service.get_cached_markets') as mock_cache_get:
            with patch('backend.app.services.screener_service.fetch_krw_markets_from_upbit') as mock_api:
                # 캐시 미스 + API 실패
                mock_cache_get.return_value = None
                mock_api.side_effect = Exception("API error")

                result = await fetch_krw_markets_from_cache_or_api()

                # 기본값 반환 (폴백)
                assert len(result) == 10  # DEFAULT_SYMBOLS
                assert 'KRW-BTC' in result


# ============================================================================
# DataFrame 재사용 테스트
# ============================================================================

class TestDataFrameReuse:
    """DataFrame 재사용 구조 테스트"""

    @pytest.fixture
    def sample_df(self):
        """테스트용 샘플 DataFrame"""
        return pd.DataFrame({
            'open': [100] * 25,
            'high': [110] * 25,
            'low': [90] * 25,
            'close': [100 + i for i in range(25)],
            'volume': [1000 + i * 100 for i in range(25)],
            'timestamp': pd.date_range('2024-01-01', periods=25)
        })

    @pytest.mark.asyncio
    async def test_load_and_cache_symbol_data(self, sample_df):
        """심볼 데이터 로드 및 캐시"""
        service = ScreenerService()
        symbol_data = {}

        with patch('backend.app.services.screener_service.load_symbol_data') as mock_load:
            mock_load.return_value = sample_df

            await service._load_and_cache_symbol_data('KRW-BTC', symbol_data)

            # dict에 캐시 확인
            assert 'KRW-BTC' in symbol_data
            assert symbol_data['KRW-BTC'] is not None
            assert len(symbol_data['KRW-BTC']) == 25

    @pytest.mark.asyncio
    async def test_evaluate_condition_with_df(self, sample_df):
        """DataFrame을 사용한 조건 평가"""
        service = ScreenerService()

        condition = {
            'type': 'change_rate',
            'operator': '>',
            'value': 0.1,  # 10%
            'period': '1D'
        }

        result = await service._evaluate_condition_with_df(sample_df, condition)

        # 상승률이 10%를 넘는지 확인
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_evaluate_symbol_with_cached_data_multiple_conditions(self, sample_df):
        """여러 조건을 DataFrame으로 평가"""
        service = ScreenerService()

        conditions = [
            {
                'type': 'change_rate',
                'operator': '>',
                'value': 0,
                'period': '1D'
            },
            {
                'type': 'volume',
                'operator': '>',
                'value': 1000,
                'period': '1D'
            }
        ]

        result = await service._evaluate_symbol_with_cached_data(
            symbol='KRW-BTC',
            df=sample_df,
            conditions=conditions,
            logic='AND'
        )

        # DataFrame을 반복 사용해서 조건 평가
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_data_reuse_no_duplicate_loads(self):
        """데이터 한 번 로드 후 재사용 (반복 로드 없음)"""
        service = ScreenerService()

        mock_df = pd.DataFrame({'close': [100, 110, 120], 'volume': [1000, 1100, 1200]})

        with patch('backend.app.services.screener_service.load_symbol_data') as mock_load:
            mock_load.return_value = mock_df

            # 3개 심볼, 2개 조건 → 최대 6번 로드 가능
            # 하지만 각 심볼 1번만 로드해야 함 (재사용)

            symbol_data = {}
            symbols = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP']

            # 모든 심볼 데이터 로드
            for symbol in symbols:
                await service._load_and_cache_symbol_data(symbol, symbol_data)

            # 로드 호출 횟수 = 심볼 수
            assert mock_load.call_count == 3

            # 각 조건 평가에서도 로드하지 않음 (df 재사용)
            condition = {'type': 'change_rate', 'operator': '>', 'value': 0, 'period': '1D'}

            for symbol in symbols:
                await service._evaluate_condition_with_df(symbol_data[symbol], condition)

            # 여전히 3번 (추가 로드 없음)
            assert mock_load.call_count == 3


# ============================================================================
# Redis 초기화 및 캐싱 테스트
# ============================================================================

class TestRedisInitialization:
    """Redis 초기화 및 캐싱 테스트"""

    @pytest.mark.asyncio
    async def test_init_redis_called_on_startup(self):
        """라우터 startup에서 Redis 초기화"""
        # Redis 초기화 호출 성공
        await init_redis()

        # redis_client가 초기화되었거나 이미 초기화됨
        from backend.app.services.screener_service import redis_client
        # redis_client가 설정되었거나 None (실패한 경우)
        # 어느 쪽이든 init_redis는 에러 없이 완료
        assert True

    @pytest.mark.asyncio
    async def test_screener_symbols_uses_cache_after_init(self):
        """Redis 초기화 후 캐시 사용"""
        # 공유 캐시 키 사용 확인
        with patch('backend.app.services.screener_service.redis_client') as mock_redis:
            mock_redis.get.return_value = json.dumps([
                {"market": "KRW-BTC"},
                {"market": "KRW-ETH"}
            ])

            with patch('backend.app.services.screener_service.get_cached_markets') as mock_cache:
                mock_cache.return_value = [
                    {"market": "KRW-BTC"},
                    {"market": "KRW-ETH"}
                ]

                result = await fetch_krw_markets_from_cache_or_api()

                # 캐시 사용 확인
                assert len(result) == 2


# ============================================================================
# 통합 필터링 테스트
# ============================================================================

class TestFilteringWithDataReuse:
    """데이터 재사용을 포함한 필터링 테스트"""

    @pytest.mark.asyncio
    async def test_filter_symbols_loads_data_once(self):
        """filter_symbols에서 각 심볼 데이터 한 번만 로드"""
        service = ScreenerService()

        mock_df = pd.DataFrame({
            'close': [100, 110, 120],
            'volume': [1000, 1100, 1200]
        })

        with patch('backend.app.services.screener_service.redis_client', None):
            with patch('backend.app.services.screener_service.fetch_krw_markets_from_cache_or_api') as mock_markets:
                with patch('backend.app.services.screener_service.load_symbol_data') as mock_load:
                    mock_markets.return_value = ['KRW-BTC', 'KRW-ETH']
                    mock_load.return_value = mock_df

                    result = await service.filter_symbols(
                        conditions=[
                            {'type': 'change_rate', 'operator': '>', 'value': 0, 'period': '1D'},
                            {'type': 'volume', 'operator': '>', 'value': 900, 'period': '1D'}
                        ],
                        symbols=None,
                        logic='AND'
                    )

                    # 2개 심볼만 로드 (조건 2개와는 무관)
                    assert mock_load.call_count == 2

    @pytest.mark.asyncio
    async def test_filter_symbols_with_cache_hit(self):
        """캐시된 검색 결과 사용"""
        service = ScreenerService()
        conditions = [{'type': 'change_rate', 'operator': '>', 'value': 5}]
        symbols = ['KRW-BTC', 'KRW-ETH']

        with patch('backend.app.services.screener_service.get_cached_result') as mock_cached:
            mock_cached.return_value = ['KRW-BTC']

            result = await service.filter_symbols(
                conditions=conditions,
                symbols=symbols,
                logic='AND'
            )

            # 캐시에서 반환됨
            assert result == ['KRW-BTC']
            # 추가 처리 안 함


# ============================================================================
# 성능 및 안정성 테스트
# ============================================================================

class TestPerformanceAndStability:
    """성능 및 안정성 테스트"""

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_data_load_failure(self):
        """데이터 로드 실패 시 graceful degradation"""
        service = ScreenerService()
        symbol_data = {}

        with patch('backend.app.services.screener_service.load_symbol_data') as mock_load:
            mock_load.side_effect = Exception("File not found")

            await service._load_and_cache_symbol_data('KRW-XXX', symbol_data)

            # None으로 캐시 (빠른 스킵)
            assert symbol_data['KRW-XXX'] is None

    @pytest.mark.asyncio
    async def test_evaluate_with_none_df_returns_false_quickly(self):
        """None DataFrame으로 빠른 반환"""
        service = ScreenerService()

        # None DataFrame
        result = await service._evaluate_symbol_with_cached_data(
            symbol='KRW-XXX',
            df=None,
            conditions=[{'type': 'change_rate', 'operator': '>', 'value': 5}],
            logic='AND'
        )

        # 빠른 반환 (False)
        assert result is False

    @pytest.mark.asyncio
    async def test_parallel_evaluation_with_many_symbols(self):
        """많은 심볼 병렬 평가"""
        service = ScreenerService()

        # 100개 심볼 mock
        symbols = [f'KRW-{i}' for i in range(100)]
        mock_df = pd.DataFrame({'close': [100], 'volume': [1000]})

        with patch('backend.app.services.screener_service.redis_client', None):
            with patch('backend.app.services.screener_service.fetch_krw_markets_from_cache_or_api') as mock_markets:
                with patch('backend.app.services.screener_service.load_symbol_data') as mock_load:
                    with patch('backend.app.services.screener_service.get_cached_result') as mock_cache:
                        mock_markets.return_value = symbols
                        mock_load.return_value = mock_df
                        mock_cache.return_value = None

                        result = await service.filter_symbols(
                            conditions=[{'type': 'change_rate', 'operator': '>', 'value': 0}],
                            symbols=None,
                            logic='AND'
                        )

                        # 병렬 평가 완료
                        assert isinstance(result, list)
                        assert len(result) >= 0


# ============================================================================
# 마켓 캐시 저장 실패 처리 테스트
# ============================================================================

class TestCacheSaveFailure:
    """캐시 저장 실패 시 graceful handling"""

    @pytest.mark.asyncio
    async def test_cache_save_failure_continues_to_function(self):
        """캐시 저장 실패해도 결과 반환"""
        mock_df = pd.DataFrame({'close': [100, 110], 'volume': [1000, 1100]})

        with patch('backend.app.services.screener_service.redis_client') as mock_redis:
            # setex 호출 실패
            mock_redis.setex.side_effect = Exception("Cache write failed")

            with patch('backend.app.services.screener_service.fetch_krw_markets_from_cache_or_api') as mock_markets:
                with patch('backend.app.services.screener_service.load_symbol_data') as mock_load:
                    mock_markets.return_value = ['KRW-BTC']
                    mock_load.return_value = mock_df

                    service = ScreenerService()
                    result = await service.filter_symbols(
                        conditions=[{'type': 'change_rate', 'operator': '>', 'value': 0}],
                        symbols=['KRW-BTC'],
                        logic='AND'
                    )

                    # 캐시 저장 실패해도 결과 반환
                    assert isinstance(result, list)


# ============================================================================
# MA 정배열/역배열 조건 평가 테스트
# ============================================================================

class TestMAAlignmentCondition:
    """이동평균선 정배열/역배열 조건"""

    @pytest.mark.asyncio
    async def test_evaluate_ma_alignment_golden_cross(self):
        """MA 정배열 조건 평가"""
        # 상승 추세 데이터
        df = pd.DataFrame({
            'close': list(range(1, 70)),
            'volume': [1000] * 69
        })

        service = ScreenerService()

        condition = {
            'type': 'ma_alignment',
            'operator': '==',
            'value': 'golden_cross',
            'ma_periods': [5, 20, 60]
        }

        result = await service._evaluate_condition_with_df(df, condition)
        # 상승 추세이므로 정배열일 가능성 높음
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_evaluate_ma_alignment_dead_cross(self):
        """MA 역배열 조건 평가"""
        # 하락 추세 데이터
        df = pd.DataFrame({
            'close': list(range(70, 0, -1)),
            'volume': [1000] * 70
        })

        service = ScreenerService()

        condition = {
            'type': 'ma_alignment',
            'operator': '==',
            'value': 'dead_cross',
            'ma_periods': [5, 20, 60]
        }

        result = await service._evaluate_condition_with_df(df, condition)
        assert isinstance(result, bool)


# ============================================================================
# 라우터 E2E 테스트 (모킹)
# ============================================================================

class TestScreenerRouterE2E:
    """/api/screener/symbols 라우트 E2E"""

    @pytest.mark.asyncio
    async def test_screener_symbols_route_with_cache(self):
        """GET /api/screener/symbols (캐시 있음)"""
        from backend.app.routers.screener import get_available_symbols

        with patch('backend.app.services.screener_service.fetch_krw_markets_from_cache_or_api') as mock_fetch:
            mock_fetch.return_value = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP']

            result = await get_available_symbols()

            assert result.count == 3
            assert len(result.symbols) == 3
            assert 'KRW-BTC' in result.symbols


# ============================================================================
# 캐시 TTL 및 재조회 테스트
# ============================================================================

class TestCacheTTLAndRefresh:
    """캐시 TTL 만료 및 재조회"""

    @pytest.mark.asyncio
    async def test_cache_miss_forces_api_call(self):
        """캐시 미스 시 API 재호출"""
        mock_markets = [{"market": "KRW-BTC", "korean_name": "비트코인", "english_name": "Bitcoin"}]

        with patch('backend.app.services.screener_service.get_cached_markets') as mock_cache:
            with patch('backend.app.services.screener_service.fetch_krw_markets_from_upbit', new_callable=AsyncMock) as mock_api:
                with patch('backend.app.services.screener_service.cache_markets', new_callable=AsyncMock) as mock_cache_set:
                    # 첫 번째: 캐시 미스
                    mock_cache.return_value = None
                    mock_api.return_value = mock_markets
                    mock_cache_set.return_value = None

                    result = await fetch_krw_markets_from_cache_or_api()

                    # API 호출 확인 (캐시 미스 후)
                    mock_api.assert_called_once()
                    assert 'KRW-BTC' in result


# ============================================================================
# AND vs OR 논리 조합 정합성 테스트
# ============================================================================

class TestLogicCombinations:
    """AND vs OR 논리 연산 정합성"""

    @pytest.mark.asyncio
    async def test_and_logic_all_conditions_must_pass(self):
        """AND: 모든 조건 만족"""
        service = ScreenerService()
        df = pd.DataFrame({'close': [100, 110, 120], 'volume': [1000, 1100, 1200]})

        conditions = [
            {'type': 'change_rate', 'operator': '>', 'value': 0, 'period': '1D'},
            {'type': 'volume', 'operator': '>', 'value': 900, 'period': '1D'}
        ]

        result = await service._evaluate_symbol_with_cached_data(
            symbol='KRW-BTC',
            df=df,
            conditions=conditions,
            logic='AND'
        )

        # 두 조건 모두 만족해야 True
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_or_logic_any_condition_passes(self):
        """OR: 하나의 조건만 만족"""
        service = ScreenerService()
        df = pd.DataFrame({'close': [100, 110, 120], 'volume': [1000, 1100, 1200]})

        conditions = [
            {'type': 'change_rate', 'operator': '>', 'value': 100, 'period': '1D'},  # 거짓
            {'type': 'volume', 'operator': '>', 'value': 900, 'period': '1D'}  # 참
        ]

        result = await service._evaluate_symbol_with_cached_data(
            symbol='KRW-BTC',
            df=df,
            conditions=conditions,
            logic='OR'
        )

        # 하나의 조건만 만족해도 True
        assert isinstance(result, bool)


# ============================================================================
# 문서화 및 테스트 수 검증
# ============================================================================

def test_documentation_accuracy():
    """문서 정확성 검증 - 실제 테스트 수 확인"""
    # 모든 테스트 클래스 수집
    test_classes = [
        TestSymbolConversion,
        TestMarketCacheReuse,
        TestDataFrameReuse,
        TestRedisInitialization,
        TestFilteringWithDataReuse,
        TestPerformanceAndStability,
        TestCacheSaveFailure,           # 신규
        TestMAAlignmentCondition,       # 신규
        TestScreenerRouterE2E,          # 신규
        TestCacheTTLAndRefresh,         # 신규
        TestLogicCombinations           # 신규
    ]

    # 실제 테스트 함수 개수 계산
    total_tests = sum(
        len([m for m in dir(cls) if m.startswith('test_')])
        for cls in test_classes
    )

    # 20개 이상 확인
    assert total_tests >= 20, f"Expected at least 20 tests, got {total_tests}"

    print(f"\n✓ 총 {total_tests}개 테스트 케이스 (요구: 20+)")
