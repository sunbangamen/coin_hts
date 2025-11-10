"""
RQ (Redis Queue) 작업 정의 모듈

백그라운드 작업들을 정의하고 관리합니다.
"""

from typing import Dict, Any, List, Optional
from .data_ingestion import (
    fetch_candles_job,
    batch_fetch_candles_job,
    refresh_latest_candles_job,
    get_default_symbols,
    get_default_timeframes,
    schedule_daily_refresh,
    enqueue_fetch_candles,
    enqueue_batch_fetch,
    DataIngestionStatus,
)


def run_backtest_job(
    task_id: str,
    strategy: str,
    params: Dict[str, Any],
    symbols: List[str],
    start_date: str,
    end_date: str,
    timeframe: str = "1d"
) -> Optional[Dict[str, Any]]:
    """
    비동기 백테스트 작업 (Phase 3 Task 3.2)

    Args:
        task_id: 작업 ID
        strategy: 전략명
        params: 전략 파라미터
        symbols: 심볼 목록
        start_date: 시작일 (YYYY-MM-DD)
        end_date: 종료일 (YYYY-MM-DD)
        timeframe: 캔들 타임프레임

    Returns:
        백테스트 결과 (또는 None)

    Note:
        이 함수는 RQ 큐에서 호출됩니다.
        실제 구현은 Phase 3 후속 작업에서 완성될 예정입니다.
    """
    # TODO: Phase 3 후속 작업에서 실제 구현
    # 1. 데이터 로드
    # 2. 전략 인스턴스 생성
    # 3. 심볼별 백테스트 실행
    # 4. 메트릭 계산
    # 5. 결과 저장
    pass


__all__ = [
    'fetch_candles_job',
    'batch_fetch_candles_job',
    'refresh_latest_candles_job',
    'get_default_symbols',
    'get_default_timeframes',
    'schedule_daily_refresh',
    'enqueue_fetch_candles',
    'enqueue_batch_fetch',
    'DataIngestionStatus',
    'run_backtest_job',
]
