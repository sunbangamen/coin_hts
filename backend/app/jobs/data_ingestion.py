"""
데이터 수집 백그라운드 작업 (RQ)

Upbit 캔들 데이터를 자동으로 수집하고 저장하는 비동기 작업들을 정의합니다.
Redis Queue (RQ)를 통해 스케줄링하고 실행합니다.
"""

import logging
import subprocess
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from rq import get_current_job
from rq.job import JobStatus

logger = logging.getLogger(__name__)


# 작업 상태 저장용 메타데이터 (데이터베이스에 저장할 수 있음)
class DataIngestionStatus:
    """데이터 수집 작업의 상태를 추적"""

    def __init__(self):
        self.last_run: Optional[datetime] = None
        self.last_success: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.status: str = "idle"  # idle, running, success, failed
        self.total_records: int = 0

    def to_dict(self) -> Dict:
        return {
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'last_success': self.last_success.isoformat() if self.last_success else None,
            'last_error': self.last_error,
            'status': self.status,
            'total_records': self.total_records,
        }


def fetch_candles_job(
    symbol: str,
    timeframe: str,
    days: int = 30,
    overwrite: bool = False,
    log_file: Optional[str] = None
) -> Dict:
    """
    Upbit 캔들 데이터 수집 작업

    Args:
        symbol: 심볼 (예: KRW-BTC)
        timeframe: 타임프레임 (1M, 5M, 1H, 1D, 1W)
        days: 수집 기간 (최근 N일)
        overwrite: 기존 파일 덮어쓰기 여부
        log_file: 로그 파일 경로 (선택사항)

    Returns:
        작업 결과 딕셔너리
    """
    job = get_current_job()
    logger.info(f"[작업 시작] {symbol} {timeframe} (최근 {days}일, Job ID: {job.id if job else 'N/A'})")

    try:
        # 스크립트 경로 (절대경로)
        # __file__ = /backend/app/jobs/data_ingestion.py
        # parents[3] = project root
        script_path = Path(__file__).resolve().parents[3] / "scripts" / "fetch_upbit_candles.py"

        if not script_path.exists():
            error_msg = f"스크립트를 찾을 수 없음: {script_path}"
            logger.error(error_msg)
            return {
                'success': False,
                'symbol': symbol,
                'timeframe': timeframe,
                'error': error_msg
            }

        # 시작/종료 날짜 계산
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        # 명령어 구성 (sys.executable 사용)
        cmd = [
            sys.executable,
            str(script_path),
            '--symbol', symbol,
            '--timeframe', timeframe,
            '--start', start_date.isoformat(),
            '--end', end_date.isoformat(),
            '--verbose'
        ]

        if overwrite:
            cmd.append('--overwrite')

        if log_file:
            cmd.extend(['--log-file', log_file])

        logger.info(f"실행 중: {' '.join(cmd)}")

        # 스크립트 실행
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5분 타임아웃
        )

        if result.returncode != 0:
            error_msg = f"스크립트 실패: {result.stderr}"
            logger.error(error_msg)
            return {
                'success': False,
                'symbol': symbol,
                'timeframe': timeframe,
                'error': error_msg,
                'stdout': result.stdout,
                'stderr': result.stderr
            }

        logger.info(f"작업 완료: {symbol} {timeframe}")
        logger.info(f"출력:\n{result.stdout}")

        return {
            'success': True,
            'symbol': symbol,
            'timeframe': timeframe,
            'message': f'{symbol} {timeframe} 데이터 수집 완료',
            'timestamp': datetime.now().isoformat(),
            'stdout': result.stdout
        }

    except subprocess.TimeoutExpired:
        error_msg = f"타임아웃: {symbol} {timeframe} 수집에 5분 이상 소요"
        logger.error(error_msg)
        return {
            'success': False,
            'symbol': symbol,
            'timeframe': timeframe,
            'error': error_msg
        }

    except Exception as e:
        error_msg = f"작업 실패: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'success': False,
            'symbol': symbol,
            'timeframe': timeframe,
            'error': error_msg
        }


def batch_fetch_candles_job(
    symbols: List[str],
    timeframes: List[str],
    days: int = 30,
    overwrite: bool = False
) -> Dict:
    """
    여러 심볼과 타임프레임에 대한 일괄 수집 작업

    Args:
        symbols: 심볼 리스트 (예: ['KRW-BTC', 'KRW-ETH'])
        timeframes: 타임프레임 리스트 (예: ['1H', '1D'])
        days: 수집 기간
        overwrite: 덮어쓰기 여부

    Returns:
        작업 결과 딕셔너리
    """
    job = get_current_job()
    logger.info(f"[배치 작업 시작] {len(symbols)}개 심볼 × {len(timeframes)}개 타임프레임 (Job ID: {job.id if job else 'N/A'})")

    results = {
        'success': True,
        'total': len(symbols) * len(timeframes),
        'completed': 0,
        'failed': 0,
        'details': []
    }

    for symbol in symbols:
        for timeframe in timeframes:
            try:
                result = fetch_candles_job(
                    symbol=symbol,
                    timeframe=timeframe,
                    days=days,
                    overwrite=overwrite
                )

                if result['success']:
                    results['completed'] += 1
                else:
                    results['failed'] += 1
                    results['success'] = False

                results['details'].append(result)

            except Exception as e:
                logger.error(f"배치 작업 중 오류: {symbol} {timeframe} - {str(e)}")
                results['failed'] += 1
                results['success'] = False
                results['details'].append({
                    'success': False,
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'error': str(e)
                })

    logger.info(f"[배치 작업 완료] 성공: {results['completed']}, 실패: {results['failed']}")
    results['timestamp'] = datetime.now().isoformat()
    return results


def refresh_latest_candles_job(
    symbol: str = 'KRW-BTC',
    timeframe: str = '1H',
    days: int = 7
) -> Dict:
    """
    최신 캔들 데이터 새로고침 작업 (일일/주간)

    Args:
        symbol: 심볼
        timeframe: 타임프레임
        days: 업데이트할 기간 (기본 7일)

    Returns:
        작업 결과
    """
    logger.info(f"[새로고침] {symbol} {timeframe} (최근 {days}일)")

    # 기존 파일을 덮어쓰기로 최신 데이터로 업데이트
    return fetch_candles_job(
        symbol=symbol,
        timeframe=timeframe,
        days=days,
        overwrite=True  # 최신 데이터로 업데이트
    )


def get_default_symbols() -> List[str]:
    """기본 수집 심볼 리스트 반환"""
    symbols_env = os.getenv('UPBIT_SYMBOLS', 'KRW-BTC,KRW-ETH,KRW-XRP,KRW-ADA')
    return symbols_env.split(',')


def get_default_timeframes() -> List[str]:
    """기본 수집 타임프레임 리스트 반환"""
    timeframes_env = os.getenv('UPBIT_TIMEFRAMES', '1H,1D')
    return timeframes_env.split(',')


def schedule_daily_refresh() -> Dict:
    """일일 자동 새로고침 작업"""
    symbols = get_default_symbols()
    timeframes = get_default_timeframes()

    logger.info(f"[일일 새로고침 스케줄] {symbols} × {timeframes}")

    return batch_fetch_candles_job(
        symbols=symbols,
        timeframes=timeframes,
        days=7,  # 최근 7일 업데이트
        overwrite=True
    )


def enqueue_fetch_candles(
    connection,
    symbol: str,
    timeframe: str,
    days: int = 30,
    overwrite: bool = False,
    job_timeout: int = 600
):
    """
    RQ 큐에 캔들 수집 작업 추가

    Args:
        connection: Redis 연결
        symbol: 심볼
        timeframe: 타임프레임
        days: 수집 기간
        overwrite: 덮어쓰기 여부
        job_timeout: 작업 타임아웃 (초)

    Returns:
        Job 객체
    """
    from rq import Queue

    queue = Queue('data_ingestion', connection=connection)

    job = queue.enqueue(
        fetch_candles_job,
        symbol=symbol,
        timeframe=timeframe,
        days=days,
        overwrite=overwrite,
        job_timeout=job_timeout,
        result_ttl=300,  # 결과 저장 5분
    )

    logger.info(f"작업 큐 추가: {job.id} ({symbol} {timeframe})")
    return job


def enqueue_batch_fetch(
    connection,
    symbols: List[str],
    timeframes: List[str],
    days: int = 30,
    overwrite: bool = False,
    job_timeout: int = 1800
):
    """
    배치 수집 작업을 RQ 큐에 추가

    Args:
        connection: Redis 연결
        symbols: 심볼 리스트
        timeframes: 타임프레임 리스트
        days: 수집 기간
        overwrite: 덮어쓰기 여부
        job_timeout: 작업 타임아웃 (초)

    Returns:
        Job 객체
    """
    from rq import Queue

    queue = Queue('data_ingestion', connection=connection)

    job = queue.enqueue(
        batch_fetch_candles_job,
        symbols=symbols,
        timeframes=timeframes,
        days=days,
        overwrite=overwrite,
        job_timeout=job_timeout,
        result_ttl=600,  # 결과 저장 10분
    )

    logger.info(f"배치 작업 큐 추가: {job.id}")
    return job
