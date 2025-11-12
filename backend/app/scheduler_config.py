"""
스케줄러 환경 변수 설정 헬퍼 모듈

프론트엔드(DataManagementPage.jsx, BacktestPage.jsx)와 백엔드(scheduler.py)의
심볼/타임프레임 설정을 동기화하기 위한 중앙 설정 관리 모듈입니다.

참고: ri_22.md (Issue #37 분석 문서)
"""

import os
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# 기본 설정 (프론트엔드와 동기화해야 함)
# ============================================================================

# 기본 심볼 목록
# 프론트엔드: frontend/src/pages/DataManagementPage.jsx:8
DEFAULT_SYMBOLS = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL', 'KRW-XLM', 'KRW-ADA', 'KRW-DOGE', 'KRW-BCH', 'KRW-NEAR']

# 기본 타임프레임 목록
# 프론트엔드: frontend/src/pages/DataManagementPage.jsx:11 / BacktestPage.jsx:34
DEFAULT_TIMEFRAMES = ['1M', '5M', '1H', '1D', '1W']

# ============================================================================
# 환경 변수 파서 함수
# ============================================================================

def _parse_csv_list(env_var: str, default_list: list) -> list:
    """
    쉼표로 구분된 환경 변수를 파이썬 리스트로 파싱

    Args:
        env_var: 환경 변수 이름
        default_list: 환경 변수가 없을 때의 기본값

    Returns:
        정규화된 리스트 (공백 제거, 대문자 유지)
    """
    value = os.getenv(env_var, '')

    if not value or not value.strip():
        return default_list

    # 쉼표로 분할 후 공백 제거, 대문자 유지
    parsed = [item.strip().upper() for item in value.split(',') if item.strip()]

    return parsed if parsed else default_list


def get_scheduler_symbols() -> list:
    """
    스케줄러가 수집할 심볼 목록 조회

    환경 변수: SCHEDULER_SYMBOLS
    예시: SCHEDULER_SYMBOLS=KRW-BTC,KRW-ETH,KRW-XRP

    Returns:
        list: 정규화된 심볼 목록
    """
    return _parse_csv_list('SCHEDULER_SYMBOLS', DEFAULT_SYMBOLS)


def get_scheduler_timeframes() -> list:
    """
    스케줄러가 수집할 타임프레임 목록 조회

    환경 변수: SCHEDULER_TIMEFRAMES
    예시: SCHEDULER_TIMEFRAMES=1M,5M,1H,1D,1W

    Returns:
        list: 정규화된 타임프레임 목록
    """
    return _parse_csv_list('SCHEDULER_TIMEFRAMES', DEFAULT_TIMEFRAMES)


def get_default_symbols() -> list:
    """
    기본 심볼 목록 (프론트엔드와 동기화)

    Returns:
        list: 기본 심볼 목록
    """
    return DEFAULT_SYMBOLS


def get_default_timeframes() -> list:
    """
    기본 타임프레임 목록 (프론트엔드와 동기화)

    Returns:
        list: 기본 타임프레임 목록
    """
    return DEFAULT_TIMEFRAMES


def validate_scheduler_config() -> tuple:
    """
    스케줄러 설정 유효성 검증

    Returns:
        tuple: (is_valid, errors)
            - is_valid: bool, 설정이 유효한지 여부
            - errors: list, 발견된 오류 메시지 목록
    """
    errors = []

    symbols = get_scheduler_symbols()
    timeframes = get_scheduler_timeframes()

    # 심볼 검증
    if not symbols:
        errors.append("SCHEDULER_SYMBOLS가 비어 있습니다")

    # 타임프레임 검증
    if not timeframes:
        errors.append("SCHEDULER_TIMEFRAMES가 비어 있습니다")

    # 프론트엔드와의 동기화 확인 (경고)
    if symbols != DEFAULT_SYMBOLS:
        logger.warning(
            f"⚠️  SCHEDULER_SYMBOLS가 기본값과 다릅니다: "
            f"{symbols} != {DEFAULT_SYMBOLS}"
        )

    if timeframes != DEFAULT_TIMEFRAMES:
        logger.warning(
            f"⚠️  SCHEDULER_TIMEFRAMES가 기본값과 다릅니다: "
            f"{timeframes} != {DEFAULT_TIMEFRAMES}"
        )

    is_valid = len(errors) == 0
    return is_valid, errors


def log_config_info():
    """스케줄러 설정 정보를 로그에 출력"""
    symbols = get_scheduler_symbols()
    timeframes = get_scheduler_timeframes()

    logger.info("=" * 70)
    logger.info("📋 스케줄러 설정 (scheduler_config.py)")
    logger.info("=" * 70)
    logger.info(f"심볼 (SCHEDULER_SYMBOLS): {', '.join(symbols)}")
    logger.info(f"타임프레임 (SCHEDULER_TIMEFRAMES): {', '.join(timeframes)}")
    logger.info("=" * 70)
