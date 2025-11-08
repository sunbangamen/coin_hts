"""
Pytest 설정 및 공유 픽스처 (Phase 3)

이 파일은 모든 테스트에서 사용되는 공유 픽스처를 정의합니다.
특히 Redis/RQ 모킹을 중앙에서 관리하여 테스트 안정성을 보장합니다.
"""

import pytest
import uuid
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_redis_and_queue():
    """
    Redis/RQ 모킹 자동 픽스처 (autouse=True)

    모든 테스트에서 자동으로 Redis 연결과 RQ 큐를 모킹합니다.
    테스트가 실제 Redis/RQ 인스턴스 없이 실행되도록 보장합니다.
    """
    with patch("backend.app.config.redis_conn") as mock_redis, \
         patch("backend.app.main.redis_conn") as mock_redis_main, \
         patch("backend.app.task_manager.redis_conn") as mock_redis_tm, \
         patch("backend.app.main.rq_queue") as mock_queue, \
         patch("backend.app.task_manager.TaskManager.cancel_task") as mock_cancel:

        # Redis 연결 설정
        # hget은 None을 반환하도록 설정 (키가 없을 때)
        mock_redis.hset = MagicMock(return_value=1)
        mock_redis.hget = MagicMock(return_value=None)
        mock_redis.hgetall = MagicMock(return_value={})
        mock_redis.set = MagicMock(return_value=True)
        mock_redis.get = MagicMock(return_value=None)
        mock_redis.expire = MagicMock(return_value=1)
        mock_redis.delete = MagicMock(return_value=0)

        mock_redis_main.hset = MagicMock(return_value=1)
        mock_redis_main.hget = MagicMock(return_value=None)
        mock_redis_main.expire = MagicMock(return_value=1)

        mock_redis_tm.hset = MagicMock(return_value=1)
        mock_redis_tm.hget = MagicMock(return_value=None)
        mock_redis_tm.hgetall = MagicMock(return_value={})
        mock_redis_tm.expire = MagicMock(return_value=1)

        # RQ Queue 설정
        mock_job = MagicMock()
        mock_job.id = str(uuid.uuid4())
        mock_queue.enqueue = MagicMock(return_value=mock_job)
        mock_queue.fetch_job = MagicMock(return_value=None)

        # TaskManager.cancel_task 모킹
        mock_cancel.return_value = None

        yield {
            "redis": mock_redis,
            "redis_main": mock_redis_main,
            "redis_tm": mock_redis_tm,
            "queue": mock_queue,
            "job": mock_job,
            "cancel_task": mock_cancel,
        }


@pytest.fixture
def test_client():
    """
    FastAPI 테스트 클라이언트

    모든 API 테스트에서 사용합니다.
    """
    from backend.app.main import app
    return TestClient(app)


@pytest.fixture
def sample_task_id():
    """
    테스트용 샘플 task_id

    일관된 UUID를 제공합니다.
    """
    return str(uuid.uuid4())


@pytest.fixture
def sample_backtest_request():
    """
    테스트용 샘플 백테스트 요청
    """
    return {
        "strategy": "volume_zone_breakout",
        "params": {
            "volume_window": 10,
            "top_percentile": 0.2,
            "breakout_buffer": 0.0
        },
        "symbols": ["BTC_KRW", "ETH_KRW"],
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "timeframe": "1d"
    }


@pytest.fixture
def mock_task_status_response(sample_task_id):
    """
    테스트용 작업 상태 응답 템플릿

    다양한 상태를 반환하는 팩토리로 사용됩니다.
    """
    def factory(status="queued", progress=0.0):
        from backend.app.task_manager import TaskStatus

        responses = {
            "queued": {
                "task_id": sample_task_id,
                "status": TaskStatus.QUEUED.value,
                "progress": 0.0,
                "result": None,
                "error": None,
            },
            "running": {
                "task_id": sample_task_id,
                "status": TaskStatus.RUNNING.value,
                "progress": progress or 0.65,
                "result": None,
                "error": None,
            },
            "completed": {
                "task_id": sample_task_id,
                "status": TaskStatus.COMPLETED.value,
                "progress": 1.0,
                "result": {"run_id": sample_task_id, "signals": 150},
                "error": None,
            },
            "failed": {
                "task_id": sample_task_id,
                "status": TaskStatus.FAILED.value,
                "progress": 0.5,
                "result": None,
                "error": "Test error message",
            },
            "cancelled": {
                "task_id": sample_task_id,
                "status": TaskStatus.CANCELLED.value,
                "progress": 0.5,
                "result": None,
                "error": "Task cancelled by user",
            },
        }

        return responses.get(status, responses["queued"])

    return factory


# 마커 정의
def pytest_configure(config):
    """
    Custom pytest 마커 정의
    """
    config.addinivalue_line(
        "markers",
        "async_api: mark test as an async API test"
    )
    config.addinivalue_line(
        "markers",
        "cancel: mark test as a cancel operation test"
    )


# 테스트 실행 전 초기화
@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """
    테스트 환경 초기화 (세션 레벨)
    """
    import os

    # 테스트 환경 변수 설정
    os.environ["REDIS_HOST"] = "localhost"
    os.environ["REDIS_PORT"] = "6379"
    os.environ["REDIS_DB"] = "1"  # 테스트용 DB
    os.environ["RQ_QUEUE_NAME"] = "test-backtests"

    yield

    # 테스트 종료 후 정리 (필요시)


# 로깅 설정 (선택사항)
@pytest.fixture(autouse=True)
def caplog_setup(caplog):
    """
    로깅 캡처 설정
    """
    caplog.set_level("DEBUG")
    return caplog
