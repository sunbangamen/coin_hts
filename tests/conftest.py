"""
Pytest 설정 및 공유 픽스처 (Phase 3)

이 파일은 모든 테스트에서 사용되는 공유 픽스처를 정의합니다.
특히 Redis/RQ 모킹을 중앙에서 관리하여 테스트 안정성을 보장합니다.

개선사항:
- InMemoryRedis: 메모리 기반 Redis 추상화 (상태 변경 검증)
- TaskManager.cancel_task는 patch 제거 (실제 구현 실행)
"""

import pytest
import uuid
import json
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


class InMemoryRedis:
    """
    메모리 기반 Redis 구현 (테스트용)

    실제 Redis의 주요 메서드를 메모리 dict로 구현하여,
    테스트에서 상태 변경을 실제로 검증할 수 있게 합니다.
    """

    def __init__(self):
        self._data = {}  # {key: value} 저장소
        self._hashes = {}  # {hash_key: {field: value}} 저장소
        self._ttl = {}  # {key: ttl_seconds} 저장소

    def hset(self, name, key=None, value=None, mapping=None):
        """Hash 필드 설정

        두 가지 호출 방식 지원:
        1. hset(name, key, value) - 단일 필드
        2. hset(name, mapping={...}) - 여러 필드 (Redis 표준)
        """
        if name not in self._hashes:
            self._hashes[name] = {}

        if mapping is not None:
            # mapping={field: value, ...} 방식
            self._hashes[name].update(mapping)
            return len(mapping)
        else:
            # key, value 방식
            self._hashes[name][key] = value
            return 1

    def hget(self, name, key):
        """Hash 필드 조회"""
        if name in self._hashes and key in self._hashes[name]:
            return self._hashes[name][key]
        return None

    def hgetall(self, name):
        """Hash 전체 조회"""
        if name in self._hashes:
            return self._hashes[name]
        return {}

    def set(self, key, value):
        """String 값 설정"""
        self._data[key] = value
        return True

    def get(self, key):
        """String 값 조회"""
        return self._data.get(key)

    def delete(self, key):
        """키 삭제"""
        if key in self._data:
            del self._data[key]
            return 1
        return 0

    def expire(self, key, seconds):
        """TTL 설정"""
        self._ttl[key] = seconds
        return 1

    def flushdb(self):
        """데이터베이스 초기화 (테스트용)"""
        self._data.clear()
        self._hashes.clear()
        self._ttl.clear()

    def __repr__(self):
        return f"InMemoryRedis(hashes={len(self._hashes)}, data={len(self._data)})"


@pytest.fixture(autouse=True)
def mock_redis_and_queue():
    """
    Redis/RQ 모킹 자동 픽스처 (autouse=True, 개선됨)

    모든 테스트에서 자동으로 Redis 연결과 RQ 큐를 모킹합니다.

    개선사항:
    - InMemoryRedis를 사용하여 실제 상태 변경을 메모리에 반영
    - TaskManager.cancel_task는 패치하지 않음 (실제 구현 실행)
    - 테스트에서 상태 변경을 검증 가능
    - run_backtest_job 더미화 (ImportError 방지, Phase 3 임시)
    """
    # 메모리 기반 Redis 인스턴스
    in_memory_redis = InMemoryRedis()

    # run_backtest_job 더미 함수 (backend/app/jobs에 정의되지 않아 임시 patch)
    mock_run_backtest_job = MagicMock(return_value=None)

    with patch("backend.app.config.redis_conn", in_memory_redis), \
         patch("backend.app.main.redis_conn", in_memory_redis), \
         patch("backend.app.task_manager.redis_conn", in_memory_redis), \
         patch("backend.app.main.rq_queue") as mock_queue, \
         patch("backend.app.jobs.run_backtest_job", mock_run_backtest_job):

        # RQ Queue 설정
        mock_job = MagicMock()
        mock_job.id = str(uuid.uuid4())
        mock_queue.enqueue = MagicMock(return_value=mock_job)
        mock_queue.fetch_job = MagicMock(return_value=None)

        yield {
            "redis": in_memory_redis,
            "queue": mock_queue,
            "job": mock_job,
            "run_backtest_job": mock_run_backtest_job,
        }


@pytest.fixture
def in_memory_redis_instance(mock_redis_and_queue):
    """
    테스트에서 직접 접근할 수 있는 InMemoryRedis 인스턴스

    취소 로직 검증을 위해 초기 상태를 설정하거나 최종 상태를 확인할 때 사용합니다.
    """
    return mock_redis_and_queue["redis"]


@pytest.fixture
def setup_task_in_redis(in_memory_redis_instance):
    """
    InMemoryRedis에 작업 상태를 직접 설정하는 헬퍼

    테스트에서 초기 상태를 쉽게 설정할 수 있게 합니다.
    """
    def _setup(task_id, status="queued", progress=0.0):
        from backend.app.task_manager import TaskStatus
        from datetime import datetime

        # task:{task_id} Hash에 상태 저장
        task_key = f"task:{task_id}"
        in_memory_redis_instance.hset(task_key, "status", status)
        in_memory_redis_instance.hset(task_key, "created_at", datetime.utcnow().isoformat() + "Z")
        in_memory_redis_instance.hset(task_key, "progress", str(progress))

        # progress:{task_id} String에도 저장 (TaskManager 호환)
        in_memory_redis_instance.set(f"progress:{task_id}", str(progress))

        return task_id

    return _setup


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
