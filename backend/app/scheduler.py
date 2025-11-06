"""
APScheduler 기반 자동 데이터 수집 스케줄러

매일 특정 시간에 자동으로 Upbit 캔들 데이터를 수집합니다.

환경 변수 설정:
  - REDIS_HOST: Redis 호스트 (기본: localhost)
  - REDIS_PORT: Redis 포트 (기본: 6379)
  - SCHEDULER_HOUR: 실행 시간 시 (0-23, 기본: 9, UTC)
  - SCHEDULER_MINUTE: 실행 분 (0-59, 기본: 0)
  - ENABLE_SCHEDULER: 스케줄러 활성화 여부 (기본: true)
  - SCHEDULER_SYMBOLS: 수집할 심볼 (콤마로 구분, 기본: KRW-BTC,KRW-ETH,KRW-XRP)
  - SCHEDULER_TIMEFRAMES: 수집할 타임프레임 (콤마로 구분, 기본: 1H,1D)
"""

import logging
import os
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import redis
from rq import Queue
from backend.app.jobs import fetch_candles_job, batch_fetch_candles_job

logger = logging.getLogger(__name__)

# 환경 변수 설정 (기본값 포함)
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
SCHEDULER_HOUR = int(os.getenv('SCHEDULER_HOUR', 9))  # UTC 기준
SCHEDULER_MINUTE = int(os.getenv('SCHEDULER_MINUTE', 0))
ENABLE_SCHEDULER = os.getenv('ENABLE_SCHEDULER', 'true').lower() == 'true'

# 기본 심볼 및 타임프레임 설정
DEFAULT_SYMBOLS = os.getenv('SCHEDULER_SYMBOLS', 'KRW-BTC,KRW-ETH,KRW-XRP').split(',')
DEFAULT_TIMEFRAMES = os.getenv('SCHEDULER_TIMEFRAMES', '1H,1D').split(',')

# Redis 연결
redis_conn = None
scheduler = None
last_run_result = None  # 마지막 실행 결과
last_run_time = None    # 마지막 실행 시간
job_history = []        # 작업 실행 기록 (최근 10개)


def init_scheduler():
    """스케줄러 초기화"""
    global scheduler, redis_conn

    if not ENABLE_SCHEDULER:
        logger.warning("⚠️  스케줄러가 비활성화되었습니다 (ENABLE_SCHEDULER=false)")
        return False

    if scheduler is None:
        scheduler = BackgroundScheduler()

        try:
            redis_conn = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=0,
                socket_connect_timeout=5
            )
            redis_conn.ping()
            logger.info(f"✅ Redis 연결 성공 ({REDIS_HOST}:{REDIS_PORT})")
        except Exception as e:
            logger.error(f"❌ Redis 연결 실패 ({REDIS_HOST}:{REDIS_PORT}): {e}")
            return False

        return True

    return True


def schedule_daily_collection(
    symbols: list = None,
    timeframes: list = None,
    hour: int = None,
    minute: int = None,
    days: int = 1,
    overwrite: bool = False
):
    """
    매일 특정 시간에 데이터 수집을 스케줄

    Args:
        symbols: 수집할 심볼 리스트 (기본: DEFAULT_SYMBOLS)
        timeframes: 수집할 타임프레임 리스트 (기본: DEFAULT_TIMEFRAMES)
        hour: 실행 시간 (0-23, UTC 기준, 기본: SCHEDULER_HOUR)
        minute: 실행 분 (0-59, 기본: SCHEDULER_MINUTE)
        days: 수집 기간 (최근 N일)
        overwrite: 기존 파일 덮어쓰기 여부
    """
    global scheduler, redis_conn, last_run_result, last_run_time

    # 기본값 설정
    if symbols is None:
        symbols = DEFAULT_SYMBOLS
    if timeframes is None:
        timeframes = DEFAULT_TIMEFRAMES
    if hour is None:
        hour = SCHEDULER_HOUR
    if minute is None:
        minute = SCHEDULER_MINUTE

    if not init_scheduler():
        logger.error("스케줄러 초기화 실패")
        return False

    def job_function():
        """스케줄 작업 함수"""
        global last_run_result, last_run_time, job_history

        run_start = datetime.now(timezone.utc)
        logger.info(f"[자동 수집 시작] {run_start.isoformat()}")
        logger.info(f"  심볼: {', '.join(symbols)}")
        logger.info(f"  타임프레임: {', '.join(timeframes)}")

        q = Queue('data_ingestion', connection=redis_conn)

        try:
            # 배치 작업으로 모든 심볼/타임프레임 수집
            job = q.enqueue(
                batch_fetch_candles_job,
                symbols=symbols,
                timeframes=timeframes,
                days=days,
                overwrite=overwrite
            )

            run_end = datetime.now(timezone.utc)
            result = {
                'status': 'queued',
                'job_id': job.id,
                'start_time': run_start.isoformat(),
                'end_time': run_end.isoformat(),
                'symbols': symbols,
                'timeframes': timeframes
            }

            last_run_result = result
            last_run_time = run_start

            # 히스토리 추가 (최근 10개만 유지)
            job_history.append(result)
            if len(job_history) > 10:
                job_history.pop(0)

            logger.info(f"✅ 배치 작업 추가됨 - Job ID: {job.id}")
            return True
        except Exception as e:
            run_end = datetime.now(timezone.utc)
            result = {
                'status': 'failed',
                'error': str(e),
                'start_time': run_start.isoformat(),
                'end_time': run_end.isoformat()
            }

            last_run_result = result
            last_run_time = run_start
            job_history.append(result)
            if len(job_history) > 10:
                job_history.pop(0)

            logger.error(f"❌ 작업 추가 실패: {e}")
            return False

    # 기존 작업 제거 (중복 방지)
    if scheduler and scheduler.get_job('daily_data_collection'):
        scheduler.remove_job('daily_data_collection')

    # 매일 지정 시간에 실행하도록 스케줄
    if scheduler:
        scheduler.add_job(
            job_function,
            CronTrigger(hour=hour, minute=minute),
            id='daily_data_collection',
            name='Daily Data Collection',
            replace_existing=True
        )

        logger.info(f"✅ 스케줄 설정 완료")
        logger.info(f"  실행 시간: 매일 {hour:02d}:{minute:02d} (UTC)")
        logger.info(f"  심볼: {', '.join(symbols)}")
        logger.info(f"  타임프레임: {', '.join(timeframes)}")

    return True


def start_scheduler():
    """스케줄러 시작"""
    global scheduler

    if scheduler is None:
        if not init_scheduler():
            logger.error("스케줄러 초기화 실패")
            return False

    if not scheduler.running:
        scheduler.start()
        logger.info("🚀 스케줄러 시작됨")

    return True


def stop_scheduler():
    """스케줄러 중지"""
    global scheduler

    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("⛔ 스케줄러 중지됨")


def trigger_immediate_batch(
    symbols: list = None,
    timeframes: list = None,
    days: int = 1,
    overwrite: bool = False
):
    """
    즉시 배치 작업 실행 (테스트/운영 점검용)

    Args:
        symbols: 수집할 심볼 리스트
        timeframes: 수집할 타임프레임 리스트
        days: 수집 기간
        overwrite: 기존 파일 덮어쓰기 여부

    Returns:
        dict: {'success': bool, 'job_id': str, 'error': str or None}
    """
    global redis_conn, last_run_result, last_run_time, job_history

    if symbols is None:
        symbols = DEFAULT_SYMBOLS
    if timeframes is None:
        timeframes = DEFAULT_TIMEFRAMES

    if redis_conn is None:
        if not init_scheduler():
            return {'success': False, 'error': 'Redis 연결 실패'}

    try:
        q = Queue('data_ingestion', connection=redis_conn)

        job = q.enqueue(
            batch_fetch_candles_job,
            symbols=symbols,
            timeframes=timeframes,
            days=days,
            overwrite=overwrite
        )

        run_time = datetime.now(timezone.utc)
        result = {
            'status': 'queued',
            'job_id': job.id,
            'trigger_time': run_time.isoformat(),
            'symbols': symbols,
            'timeframes': timeframes
        }

        last_run_result = result
        last_run_time = run_time
        job_history.append(result)
        if len(job_history) > 10:
            job_history.pop(0)

        logger.info(f"✅ 즉시 배치 작업 추가됨 - Job ID: {job.id}")

        return {
            'success': True,
            'job_id': job.id,
            'error': None
        }
    except Exception as e:
        logger.error(f"❌ 즉시 배치 작업 실패: {e}")
        return {
            'success': False,
            'job_id': None,
            'error': str(e)
        }


def get_scheduler_status():
    """
    스케줄러 상태 조회 (강화된 버전)

    Returns:
        dict: 스케줄러 상태, 등록된 작업, 최근 실행 결과, RQ 큐 상태
              ENABLE_SCHEDULER=false일 때는 간단한 상태만 반환
    """
    global scheduler, redis_conn, last_run_result, last_run_time

    # Step 4: ENABLE_SCHEDULER=false일 때 disabled 상태 반환
    if not ENABLE_SCHEDULER:
        return {
            'enabled': False,
            'running': False,
            'message': 'Scheduler is disabled (ENABLE_SCHEDULER=false)',
            'note': 'Manual triggers are available via POST /api/scheduler/trigger',
            'redis': {
                'host': REDIS_HOST,
                'port': REDIS_PORT,
                'connected': False
            },
            'scheduled_jobs': [],
            'last_run': {
                'time': None,
                'result': None
            },
            'job_history': [],
            'rq_queue': {
                'size': 0,
                'error': None
            },
            'configuration': {
                'hour': SCHEDULER_HOUR,
                'minute': SCHEDULER_MINUTE,
                'symbols': DEFAULT_SYMBOLS,
                'timeframes': DEFAULT_TIMEFRAMES
            }
        }

    status = {
        'enabled': ENABLE_SCHEDULER,
        'running': scheduler.running if scheduler else False,
        'redis': {
            'host': REDIS_HOST,
            'port': REDIS_PORT,
            'connected': False
        },
        'scheduled_jobs': [],
        'last_run': {
            'time': last_run_time.isoformat() if last_run_time else None,
            'result': last_run_result
        },
        'job_history': job_history[-5:],  # 최근 5개만
        'rq_queue': {
            'size': 0,
            'error': None
        },
        'configuration': {
            'hour': SCHEDULER_HOUR,
            'minute': SCHEDULER_MINUTE,
            'symbols': DEFAULT_SYMBOLS,
            'timeframes': DEFAULT_TIMEFRAMES
        }
    }

    # Redis 연결 상태 확인
    if redis_conn:
        try:
            redis_conn.ping()
            status['redis']['connected'] = True

            # RQ 큐 크기 확인
            try:
                queue_size = redis_conn.llen('rq:queue:data_ingestion')
                status['rq_queue']['size'] = queue_size
            except Exception as e:
                status['rq_queue']['error'] = str(e)
        except Exception as e:
            status['redis']['connected'] = False
            status['redis']['error'] = str(e)

    # 스케줄된 작업 목록
    if scheduler:
        for job in scheduler.get_jobs():
            status['scheduled_jobs'].append({
                'id': job.id,
                'name': job.name,
                'trigger': str(job.trigger),
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None
            })

    return status
