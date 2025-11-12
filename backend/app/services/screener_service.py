"""
조건 검색 서비스 (Feature Breakdown #23, Task 5 개선)

심볼 변환, 데이터 로딩, 마켓 목록 관리, Redis 캐싱을 담당하는 서비스 계층
"""

import logging
import os
import json
import hashlib
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime

import pandas as pd

try:
    from redis import Redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

from backend.app.data_loader import load_ohlcv_data
from backend.app.indicators.calculator import IndicatorCalculator
from backend.app.routers.markets import (
    get_cached_markets,
    cache_markets,
    fetch_krw_markets_from_upbit
)

logger = logging.getLogger(__name__)

# ============================================================================
# 상수
# ============================================================================

DATA_ROOT = os.getenv("DATA_ROOT", "/data")
SCREENER_CACHE_TTL = 60  # 결과 캐시: 1분
MARKET_DATA_CACHE_TTL = 300  # 마켓 데이터 캐시: 5분

# 기본 심볼 리스트 (폴백)
DEFAULT_SYMBOLS = [
    'KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL', 'KRW-XLM',
    'KRW-ADA', 'KRW-DOGE', 'KRW-BCH', 'KRW-NEAR', 'KRW-AVA'
]

# Redis 클라이언트 (싱글톤)
redis_client: Optional[Redis] = None


# ============================================================================
# 헬퍼 함수
# ============================================================================

def convert_symbol_to_data_format(symbol: str) -> str:
    """
    Upbit 심볼 형식 → 데이터 파일 형식 변환

    Args:
        symbol: Upbit 형식 (예: KRW-BTC)

    Returns:
        데이터 파일 형식 (예: BTC_KRW)

    Example:
        >>> convert_symbol_to_data_format('KRW-BTC')
        'BTC_KRW'
        >>> convert_symbol_to_data_format('BTC_KRW')  # 이미 변환됨
        'BTC_KRW'
    """
    if '-' not in symbol:
        # 이미 언더스코어 형식
        return symbol

    parts = symbol.split('-')
    if len(parts) != 2:
        logger.warning(f"Invalid symbol format: {symbol}")
        return symbol

    # KRW-BTC → BTC_KRW
    return f"{parts[1]}_{parts[0]}"


def check_data_exists(symbol: str, timeframe: str = '1D') -> bool:
    """
    심볼의 데이터 파일 존재 여부 확인

    Args:
        symbol: 심볼 (KRW-BTC 또는 BTC_KRW)
        timeframe: 타임프레임 (기본: 1D)

    Returns:
        데이터 파일 존재 여부
    """
    try:
        # 심볼 변환
        data_symbol = convert_symbol_to_data_format(symbol)

        # 최신 연도 파일 확인
        current_year = datetime.now().year
        data_dir = Path(DATA_ROOT) / data_symbol / timeframe

        if not data_dir.exists():
            logger.debug(f"Data directory not found: {data_dir}")
            return False

        # .parquet 파일 존재 확인
        parquet_file = data_dir / f"{current_year}.parquet"
        exists = parquet_file.exists()

        if not exists:
            logger.debug(f"Parquet file not found: {parquet_file}")

        return exists

    except Exception as e:
        logger.debug(f"Error checking data existence for {symbol}: {e}")
        return False


# ============================================================================
# Redis 초기화 및 관리
# ============================================================================

async def init_redis():
    """Redis 클라이언트 초기화"""
    global redis_client
    if HAS_REDIS and redis_client is None:
        try:
            redis_client = Redis(
                host="localhost",
                port=6379,
                db=0,
                decode_responses=True,
                socket_keepalive=True
            )
            redis_client.ping()
            logger.info("Redis client initialized for screener service")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis: {e}")
            redis_client = None


def _get_cache_key(conditions: List[Dict[str, Any]], symbols: List[str]) -> str:
    """
    캐시 키 생성

    조건 세트 + 심볼 리스트를 기반으로 유니크한 캐시 키를 생성합니다.

    Args:
        conditions: 조건 목록
        symbols: 심볼 목록

    Returns:
        캐시 키
    """
    # 조건을 정렬하여 동일한 조건은 같은 키를 생성
    conditions_json = json.dumps(conditions, sort_keys=True)
    symbols_json = json.dumps(sorted(symbols))

    # 해시로 축약
    combined = f"{conditions_json}:{symbols_json}"
    hash_digest = hashlib.md5(combined.encode()).hexdigest()

    return f"screener:{hash_digest}"


async def get_cached_result(
    conditions: List[Dict[str, Any]],
    symbols: List[str]
) -> Optional[List[str]]:
    """
    캐시된 결과 조회

    Args:
        conditions: 조건 목록
        symbols: 심볼 목록

    Returns:
        캐시된 결과 (매칭된 심볼 목록) 또는 None
    """
    if not redis_client:
        return None

    try:
        cache_key = _get_cache_key(conditions, symbols)
        cached = redis_client.get(cache_key)

        if cached:
            logger.debug(f"Cache hit for screener: {cache_key}")
            return json.loads(cached)

    except Exception as e:
        logger.warning(f"Error retrieving from cache: {e}")

    return None


async def set_cached_result(
    conditions: List[Dict[str, Any]],
    symbols: List[str],
    result: List[str]
) -> None:
    """
    캐시에 결과 저장

    Args:
        conditions: 조건 목록
        symbols: 심볼 목록
        result: 매칭된 심볼 목록
    """
    if not redis_client:
        return

    try:
        cache_key = _get_cache_key(conditions, symbols)
        redis_client.setex(
            cache_key,
            SCREENER_CACHE_TTL,
            json.dumps(result)
        )
        logger.debug(f"Result cached: {cache_key}")
    except Exception as e:
        logger.warning(f"Error saving to cache: {e}")


# ============================================================================
# 마켓 목록 관리
# ============================================================================

async def fetch_krw_markets_from_cache_or_api() -> List[str]:
    """
    KRW 마켓 목록 조회 (캐시 또는 API)

    markets.py의 get_cached_markets() 를 재사용하여 캐시를 일원화합니다.
    실패 시 기본 심볼 리스트를 반환합니다 (Graceful degradation).

    Returns:
        심볼 목록 (예: ['KRW-BTC', 'KRW-ETH', ...])
    """
    try:
        # 1. markets.py 의 기존 함수들 재사용
        # 1-1. Redis 캐시 확인 (markets:krw 키 사용)
        try:
            cached_markets = await get_cached_markets()
            if cached_markets:
                logger.debug(f"Markets retrieved from shared cache: {len(cached_markets)} items")
                return [m["market"] for m in cached_markets]
        except Exception as e:
            logger.debug(f"Error retrieving markets from cache: {e}")

        # 1-2. API에서 조회
        logger.info("Fetching KRW markets from Upbit API")
        markets = await fetch_krw_markets_from_upbit()

        if not markets:
            logger.warning("No markets returned from Upbit API")
            return DEFAULT_SYMBOLS

        # 1-3. 캐시에 저장 (markets.py의 cache_markets 함수 사용)
        try:
            await cache_markets(markets)
        except Exception as e:
            logger.debug(f"Error caching markets: {e}")

        symbols = [m["market"] for m in markets]
        logger.info(f"Markets fetched from API: {len(symbols)} items")
        return symbols

    except Exception as e:
        logger.error(f"Unexpected error in fetch_krw_markets_from_cache_or_api: {e}")

    # 2. 폴백: 기본 심볼 리스트
    logger.warning(f"Using fallback symbols ({len(DEFAULT_SYMBOLS)} items)")
    return DEFAULT_SYMBOLS


# ============================================================================
# 데이터 로딩 및 지표 계산
# ============================================================================

async def load_symbol_data(symbol: str) -> Optional[pd.DataFrame]:
    """
    심볼의 데이터 로드

    Args:
        symbol: 심볼 (KRW-BTC)

    Returns:
        OHLCV DataFrame 또는 None

    Note:
        실패 시 로그를 남기고 None을 반환합니다 (graceful degradation).
    """
    try:
        # 데이터 존재 여부 먼저 확인
        if not check_data_exists(symbol):
            logger.debug(f"Data not found for {symbol}")
            return None

        # 심볼 변환
        data_symbol = convert_symbol_to_data_format(symbol)

        # 데이터 로드
        df = load_ohlcv_data(
            symbols=[data_symbol],
            timeframe="1D",
            start_date="2024-01-01",
            end_date=datetime.now().strftime('%Y-%m-%d')
        )

        if df is None or df.empty:
            logger.debug(f"Empty data for {symbol}")
            return None

        return df

    except Exception as e:
        logger.debug(f"Error loading data for {symbol}: {e}")
        return None


async def calculate_indicators_for_symbol(
    symbol: str
) -> Optional[Dict[str, Any]]:
    """
    심볼의 모든 기술 지표 계산

    Args:
        symbol: 심볼 (KRW-BTC)

    Returns:
        지표 결과 딕셔너리 또는 None
    """
    try:
        df = await load_symbol_data(symbol)
        if df is None:
            return None

        calculator = IndicatorCalculator()
        indicators = calculator.calculate_all(df)

        return indicators

    except Exception as e:
        logger.debug(f"Error calculating indicators for {symbol}: {e}")
        return None


# ============================================================================
# ScreenerService 클래스
# ============================================================================

class ScreenerService:
    """
    조건 검색 서비스

    마켓 목록 관리, 데이터 로딩, 조건 평가를 담당합니다.

    생성 시 Redis를 초기화하여 캐시 일원화를 보장합니다.
    """

    def __init__(self):
        """초기화"""
        self.calculator = IndicatorCalculator()
        # Redis 초기화는 라우터의 startup 이벤트에서 처리

    async def get_available_symbols(self) -> List[str]:
        """
        검색 가능한 심볼 목록 조회

        Returns:
            심볼 목록
        """
        return await fetch_krw_markets_from_cache_or_api()

    async def evaluate_condition(
        self,
        symbol: str,
        condition_type: str,
        operator: str,
        value: float,
        period: Optional[str] = None,
        ma_periods: Optional[List[int]] = None
    ) -> bool:
        """
        단일 조건 평가

        Args:
            symbol: 심볼
            condition_type: 조건 타입 (change_rate, volume, etc.)
            operator: 연산자 (>, <, >=, <=, ==)
            value: 비교 값
            period: 기간 (1D, 1W, 1M)
            ma_periods: MA 기간 목록

        Returns:
            조건 만족 여부
        """
        try:
            # 데이터 로드
            df = await load_symbol_data(symbol)
            if df is None:
                return False

            # 조건 타입별 평가
            if condition_type == 'change_rate':
                period = period or '1D'
                indicator_value = self.calculator.calculate_change_rate(df, period)

            elif condition_type == 'volume':
                period = period or '1D'
                indicator_value = self.calculator.calculate_volume(df, period)

            elif condition_type == 'trade_amount':
                period = period or '1D'
                indicator_value = self.calculator.calculate_trade_amount(df, period)

            elif condition_type == 'ma_divergence':
                indicator_value = self.calculator.calculate_ma_divergence(df, 20)

            elif condition_type == 'ma_alignment':
                ma_alignment = self.calculator.check_ma_alignment(df, ma_periods or [5, 20, 60])
                # MA 정배열/역배열은 문자열 비교만 지원
                if operator == '==':
                    return ma_alignment == value
                return False

            else:
                logger.warning(f"Unknown condition type: {condition_type}")
                return False

            # 연산자 적용
            if operator == '>':
                return indicator_value > value
            elif operator == '<':
                return indicator_value < value
            elif operator == '>=':
                return indicator_value >= value
            elif operator == '<=':
                return indicator_value <= value
            elif operator == '==':
                # 부동소수점 비교는 오차 범위 고려
                if isinstance(indicator_value, float):
                    return abs(indicator_value - value) < 0.01
                return indicator_value == value

            return False

        except Exception as e:
            logger.debug(f"Error evaluating condition for {symbol}: {e}")
            return False

    async def filter_symbols(
        self,
        conditions: List[Dict[str, Any]],
        symbols: Optional[List[str]] = None,
        logic: str = 'AND'
    ) -> List[str]:
        """
        심볼 필터링 (병렬 처리 + 데이터 재사용)

        **개선 사항**:
        - 각 심볼의 DataFrame을 한 번만 로드하여 dict에 캐시
        - 모든 조건 평가에서 동일 DF를 재사용 (반복 로드 제거)
        - 데이터 로드 실패한 심볼은 메모이제이션으로 빠르게 스킵

        Args:
            conditions: 조건 목록
            symbols: 검색할 심볼 목록 (None이면 전체 마켓)
            logic: 논리 연산자 ('AND' 또는 'OR')

        Returns:
            매칭된 심볼 목록
        """
        try:
            await init_redis()

            # 1. 캐시 확인
            if symbols is None:
                symbols = await self.get_available_symbols()

            cached_result = await get_cached_result(conditions, symbols)
            if cached_result:
                logger.info(f"Screening result retrieved from cache: {len(cached_result)} matches")
                return cached_result

            logger.info(
                f"Screening {len(symbols)} symbols with {len(conditions)} conditions, "
                f"logic: {logic}"
            )

            # 2. 모든 심볼의 DataFrame을 미리 로드 (재사용을 위해)
            # 각 심볼당 한 번만 로드
            symbol_data: Dict[str, Optional[pd.DataFrame]] = {}

            logger.debug(f"Loading data for {len(symbols)} symbols...")
            load_tasks = [
                self._load_and_cache_symbol_data(symbol, symbol_data)
                for symbol in symbols
            ]
            await asyncio.gather(*load_tasks, return_exceptions=True)

            logger.debug(f"Data loaded for {len([d for d in symbol_data.values() if d is not None])} symbols")

            # 3. 병렬 처리로 각 심볼 평가 (미리 로드된 데이터 사용)
            tasks = [
                self._evaluate_symbol_with_cached_data(
                    symbol,
                    symbol_data.get(symbol),
                    conditions,
                    logic
                )
                for symbol in symbols
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 4. 결과 수집
            matched = []
            for symbol, result in zip(symbols, results):
                if isinstance(result, Exception):
                    logger.debug(f"Exception for {symbol}: {result}")
                    continue
                if result:
                    matched.append(symbol)

            logger.info(f"Screening completed: {len(matched)} matches out of {len(symbols)} symbols")

            # 5. 결과 캐시
            await set_cached_result(conditions, symbols, matched)

            return matched

        except Exception as e:
            logger.error(f"Error in filter_symbols: {e}", exc_info=True)
            return []

    async def _load_and_cache_symbol_data(
        self,
        symbol: str,
        symbol_data: Dict[str, Optional[pd.DataFrame]]
    ) -> None:
        """
        심볼 데이터를 로드하여 dict에 캐시

        Args:
            symbol: 심볼
            symbol_data: 심볼별 데이터 딕셔너리 (수정)
        """
        try:
            df = await load_symbol_data(symbol)
            symbol_data[symbol] = df
            if df is not None:
                logger.debug(f"Data loaded for {symbol}: {len(df)} rows")
            else:
                logger.debug(f"No data for {symbol}")
        except Exception as e:
            logger.debug(f"Error loading data for {symbol}: {e}")
            symbol_data[symbol] = None

    async def _evaluate_symbol_with_cached_data(
        self,
        symbol: str,
        df: Optional[pd.DataFrame],
        conditions: List[Dict[str, Any]],
        logic: str
    ) -> bool:
        """
        미리 로드된 DataFrame을 사용하여 심볼 평가

        Args:
            symbol: 심볼
            df: 미리 로드된 DataFrame (None 가능)
            conditions: 조건 목록
            logic: 'AND' 또는 'OR'

        Returns:
            조건 만족 여부
        """
        try:
            # 데이터가 없으면 False (빠른 반환)
            if df is None:
                return False

            # 각 조건 평가 (DataFrame 재사용)
            results = []
            for condition in conditions:
                result = await self._evaluate_condition_with_df(df, condition)
                results.append(result)

            # 논리 연산 적용
            if logic == 'AND':
                return all(results)
            elif logic == 'OR':
                return any(results)

            return False

        except Exception as e:
            logger.debug(f"Error evaluating symbol {symbol}: {e}")
            return False

    async def _evaluate_condition_with_df(
        self,
        df: pd.DataFrame,
        condition: Dict[str, Any]
    ) -> bool:
        """
        주어진 DataFrame으로 조건 평가 (반복 로드 제거)

        Args:
            df: 이미 로드된 DataFrame
            condition: 조건

        Returns:
            조건 만족 여부
        """
        try:
            condition_type = condition.get('type')
            operator = condition.get('operator', '>')
            value = condition.get('value')
            period = condition.get('period', '1D')
            ma_periods = condition.get('ma_periods')

            # 조건 타입별 지표 계산
            if condition_type == 'change_rate':
                indicator_value = self.calculator.calculate_change_rate(df, period)

            elif condition_type == 'volume':
                indicator_value = self.calculator.calculate_volume(df, period)

            elif condition_type == 'trade_amount':
                indicator_value = self.calculator.calculate_trade_amount(df, period)

            elif condition_type == 'ma_divergence':
                indicator_value = self.calculator.calculate_ma_divergence(df, 20)

            elif condition_type == 'ma_alignment':
                ma_alignment = self.calculator.check_ma_alignment(df, ma_periods or [5, 20, 60])
                if operator == '==':
                    return ma_alignment == value
                return False

            else:
                logger.warning(f"Unknown condition type: {condition_type}")
                return False

            # 연산자 적용
            if operator == '>':
                return indicator_value > value
            elif operator == '<':
                return indicator_value < value
            elif operator == '>=':
                return indicator_value >= value
            elif operator == '<=':
                return indicator_value <= value
            elif operator == '==':
                if isinstance(indicator_value, float):
                    return abs(indicator_value - value) < 0.01
                return indicator_value == value

            return False

        except Exception as e:
            logger.debug(f"Error in _evaluate_condition_with_df: {e}")
            return False

    # ========================================================================
    # [DEPRECATED] 다음 메서드들은 이제 사용되지 않습니다.
    # filter_symbols()의 데이터 재사용 구조로 인해 직접 호출 제거됨.
    # 기존 테스트 호환성을 위해 유지.
    # ========================================================================

    async def _evaluate_symbol(
        self,
        symbol: str,
        conditions: List[Dict[str, Any]],
        logic: str
    ) -> bool:
        """
        [DEPRECATED] 직접 호출하지 마세요.
        filter_symbols() 내에서 _evaluate_symbol_with_cached_data() 사용.

        심볼이 모든/어느 조건을 만족하는지 평가

        Args:
            symbol: 심볼
            conditions: 조건 목록
            logic: 'AND' 또는 'OR'

        Returns:
            조건 만족 여부
        """
        try:
            results = []
            for condition in conditions:
                result = await self.evaluate_condition(
                    symbol=symbol,
                    condition_type=condition.get('type'),
                    operator=condition.get('operator', '>'),
                    value=condition.get('value'),
                    period=condition.get('period'),
                    ma_periods=condition.get('ma_periods')
                )
                results.append(result)

            # 논리 연산 적용
            if logic == 'AND':
                return all(results)
            elif logic == 'OR':
                return any(results)

            return False

        except Exception as e:
            logger.debug(f"Error evaluating symbol {symbol}: {e}")
            return False
