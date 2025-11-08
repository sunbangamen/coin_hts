"""
비동기 백테스트 API 엔드포인트 테스트 (Phase 3)

비동기 백테스트 실행, 상태 조회 엔드포인트를 테스트합니다.
Redis/RQ 실제 인스턴스 없이 모든 테스트가 실행되도록 설계되었습니다.
"""

import pytest
import json
import uuid
from unittest.mock import patch, MagicMock, call

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.task_manager import TaskManager, TaskStatus

client = TestClient(app)


@pytest.fixture
def async_api_mocks(monkeypatch):
    """
    비동기 API 테스트용 통합 픽스처 (개선됨)

    Redis 연결, RQ 큐, TaskManager 메서드를 모두 모킹합니다.
    테스트가 실제 Redis/RQ 인스턴스 없이 실행되도록 보장합니다.

    개선사항:
    - run_backtest_job mock 추가 (backend/app/jobs에 정의되지 않아 임시 patch)
    - enqueue 호출 시 run_backtest_job이 올바르게 전달되는지 검증 가능
    """
    # 1. Redis 연결 모킹
    mock_redis_conn = MagicMock()

    # 2. RQ Queue 모킹
    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = None  # 나중에 테스트에서 설정
    mock_queue.enqueue = MagicMock(return_value=mock_job)

    # 3. TaskManager 메서드 모킹
    mock_create_task = MagicMock(side_effect=lambda **kwargs: str(uuid.uuid4()))
    mock_get_status = MagicMock(return_value=None)
    mock_get_task = MagicMock(return_value=None)

    # 4. run_backtest_job 더미 함수 (backend/app/jobs에 정의되지 않아 임시)
    mock_run_backtest_job = MagicMock(return_value=None)

    # 5. monkeypatch로 모킹 적용
    monkeypatch.setattr("backend.app.config.redis_conn", mock_redis_conn)
    monkeypatch.setattr("backend.app.main.redis_conn", mock_redis_conn)
    monkeypatch.setattr("backend.app.main.rq_queue", mock_queue)
    monkeypatch.setattr("backend.app.task_manager.TaskManager.create_task", mock_create_task)
    monkeypatch.setattr("backend.app.task_manager.TaskManager.get_task", mock_get_task)
    monkeypatch.setattr("backend.app.main.TaskManager.get_status", mock_get_status)
    monkeypatch.setattr("backend.app.jobs.run_backtest_job", mock_run_backtest_job)

    # 픽스처가 반환하는 모킹 객체들
    yield {
        "redis_conn": mock_redis_conn,
        "queue": mock_queue,
        "job": mock_job,
        "create_task": mock_create_task,
        "get_status": mock_get_status,
        "get_task": mock_get_task,
        "run_backtest_job": mock_run_backtest_job,
    }


class TestAsyncBacktestEndpoints:
    """비동기 백테스트 엔드포인트 테스트"""

    def test_run_backtest_async_request_validation(self):
        """비동기 백테스트 요청 검증 테스트"""
        # 필수 필드 누락 테스트
        response = client.post(
            "/api/backtests/run-async",
            json={
                "strategy": "volume_zone_breakout",
                # symbols 누락
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            }
        )
        assert response.status_code == 422  # 검증 실패

    def test_run_backtest_async_invalid_strategy(self):
        """유효하지 않은 전략명 테스트"""
        response = client.post(
            "/api/backtests/run-async",
            json={
                "strategy": "invalid_strategy",
                "symbols": ["BTC_KRW"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            }
        )
        assert response.status_code == 422  # 전략명 검증 실패

    def test_run_backtest_async_invalid_date_format(self):
        """유효하지 않은 날짜 형식 테스트"""
        response = client.post(
            "/api/backtests/run-async",
            json={
                "strategy": "volume_zone_breakout",
                "symbols": ["BTC_KRW"],
                "start_date": "2024/01/01",  # 잘못된 형식
                "end_date": "2024-12-31",
            }
        )
        assert response.status_code == 422  # 날짜 형식 검증 실패

    def test_run_backtest_async_invalid_date_range(self):
        """start_date > end_date 테스트"""
        response = client.post(
            "/api/backtests/run-async",
            json={
                "strategy": "volume_zone_breakout",
                "symbols": ["BTC_KRW"],
                "start_date": "2024-12-31",
                "end_date": "2024-01-01",  # start_date보다 앞
            }
        )
        assert response.status_code == 422  # 날짜 범위 검증 실패

    def test_run_backtest_async_success(self):
        """비동기 백테스트 성공 테스트 (개선됨)

        API 요청 → task_id 생성 → Queue.enqueue 호출을 검증합니다.
        """
        response = client.post(
            "/api/backtests/run-async",
            json={
                "strategy": "volume_zone_breakout",
                "symbols": ["BTC_KRW"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            }
        )

        # 202 Accepted 응답 확인
        assert response.status_code == 202

        # 응답 형식 검증
        data = response.json()
        assert "task_id" in data
        assert "status" in data
        assert "created_at" in data
        assert data["status"] == "queued"

        # task_id가 UUID 형식인지 확인
        try:
            uuid.UUID(data["task_id"])
        except ValueError:
            pytest.fail(f"Invalid UUID format: {data['task_id']}")

    def test_run_backtest_async_queue_failure(self, async_api_mocks):
        """큐 등록 실패 경로 테스트

        Queue.enqueue가 실패할 때 에러 응답을 반환합니다.
        """
        # 모킹된 TaskManager.create_task 설정
        test_task_id = str(uuid.uuid4())
        async_api_mocks["create_task"].return_value = test_task_id

        # Queue.enqueue 실패 시뮬레이션
        async_api_mocks["queue"].enqueue.side_effect = Exception("Redis connection error")

        # 모킹된 TaskManager.set_error 설정
        async_api_mocks["get_task"].return_value = {
            "task_id": test_task_id,
            "status": "failed",
            "error": "Failed to enqueue job: Redis connection error",
        }

        response = client.post(
            "/api/backtests/run-async",
            json={
                "strategy": "volume_zone_breakout",
                "symbols": ["BTC_KRW"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            }
        )

        # 500 Internal Server Error 응답 확인
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to enqueue" in data["detail"]

    def test_run_backtest_async_with_params(self, async_api_mocks):
        """커스텀 파라미터를 포함한 비동기 백테스트 테스트"""
        test_task_id = str(uuid.uuid4())
        async_api_mocks["create_task"].return_value = test_task_id
        async_api_mocks["get_task"].return_value = {
            "task_id": test_task_id,
            "status": "queued",
            "created_at": "2025-11-04T10:30:45Z",
        }

        custom_params = {
            "volume_window": 15,
            "top_percentile": 0.25,
            "breakout_buffer": 0.001,
        }

        response = client.post(
            "/api/backtests/run-async",
            json={
                "strategy": "volume_zone_breakout",
                "params": custom_params,
                "symbols": ["BTC_KRW", "ETH_KRW"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "timeframe": "1h",
            }
        )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data

        # 파라미터가 TaskManager.create_task에 전달되었는지 검증
        create_task_call_args = async_api_mocks["create_task"].call_args
        call_kwargs = create_task_call_args[1]
        assert call_kwargs.get("params") == custom_params
        assert call_kwargs.get("symbols") == ["BTC_KRW", "ETH_KRW"]
        assert call_kwargs.get("timeframe") == "1h"


class TestTaskStatusEndpoints:
    """작업 상태 조회 엔드포인트 테스트

    TaskManager.get_status를 모킹하여 Redis 의존성 없이 테스트합니다.
    """

    @staticmethod
    def _mock_get_status_for_task(task_id, status, progress=0.0, result=None, error=None, monkeypatch=None):
        """
        특정 task_id에 대해 TaskManager.get_status를 모킹하는 헬퍼 메서드

        Args:
            task_id: 모킹할 작업 ID
            status: 작업 상태
            progress: 진행률 (0.0-1.0)
            result: 결과 데이터
            error: 에러 메시지
            monkeypatch: pytest의 monkeypatch 픽스처
        """
        def mock_get_status(tid):
            if tid == task_id:
                return {
                    "task_id": task_id,
                    "status": status,
                    "progress": progress,
                    "result": result,
                    "error": error,
                }
            return None

        if monkeypatch:
            monkeypatch.setattr(
                "backend.app.main.TaskManager.get_status",
                mock_get_status
            )
        return mock_get_status

    def test_get_task_status_not_found(self):
        """존재하지 않는 작업 조회 테스트"""
        fake_task_id = str(uuid.uuid4())
        response = client.get(f"/api/backtests/status/{fake_task_id}")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_get_task_status_queued(self, monkeypatch):
        """대기 중인 작업 상태 조회 테스트"""
        task_id = str(uuid.uuid4())

        self._mock_get_status_for_task(
            task_id,
            TaskStatus.QUEUED.value,
            progress=0.0,
            monkeypatch=monkeypatch,
        )

        response = client.get(f"/api/backtests/status/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == TaskStatus.QUEUED.value
        assert data["progress"] == 0.0
        assert data["result"] is None
        assert data["error"] is None

    def test_get_task_status_running(self, monkeypatch):
        """실행 중인 작업 상태 조회 테스트"""
        task_id = str(uuid.uuid4())

        self._mock_get_status_for_task(
            task_id,
            TaskStatus.RUNNING.value,
            progress=0.45,
            monkeypatch=monkeypatch,
        )

        response = client.get(f"/api/backtests/status/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == TaskStatus.RUNNING.value
        assert data["progress"] == 0.45
        assert 0.0 <= data["progress"] <= 1.0

    def test_get_task_status_completed(self, monkeypatch):
        """완료된 작업 상태 조회 테스트"""
        task_id = str(uuid.uuid4())
        mock_result = {
            "version": "1.1.0",
            "run_id": task_id,
            "strategy": "volume_zone_breakout",
            "total_signals": 10,
            "execution_time": 5.25,
        }

        self._mock_get_status_for_task(
            task_id,
            TaskStatus.COMPLETED.value,
            progress=1.0,
            result=mock_result,
            monkeypatch=monkeypatch,
        )

        response = client.get(f"/api/backtests/status/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == TaskStatus.COMPLETED.value
        assert data["progress"] == 1.0
        assert data["result"] is not None
        assert data["result"]["run_id"] == task_id
        assert data["error"] is None

    def test_get_task_status_failed(self, monkeypatch):
        """실패한 작업 상태 조회 테스트"""
        task_id = str(uuid.uuid4())
        error_message = "Strategy execution failed for BTC_KRW: insufficient data"

        self._mock_get_status_for_task(
            task_id,
            TaskStatus.FAILED.value,
            progress=0.3,
            error=error_message,
            monkeypatch=monkeypatch,
        )

        response = client.get(f"/api/backtests/status/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == TaskStatus.FAILED.value
        assert data["error"] == error_message
        assert data["result"] is None


class TestAsyncEndtoEndScenarios:
    """비동기 end-to-end 시나리오 테스트

    Redis/RQ 없이 완전한 비동기 워크플로우를 시뮬레이션합니다.
    """

    def test_async_workflow_sequence(self, monkeypatch):
        """비동기 워크플로우 시퀀스 테스트 (개선됨)

        작업 요청 → 큐 등록 → 상태 폴링 (queued → running → completed) 시퀀스를 검증합니다.
        """
        # 1. 비동기 백테스트 실행
        response = client.post(
            "/api/backtests/run-async",
            json={
                "strategy": "volume_zone_breakout",
                "symbols": ["BTC_KRW"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            }
        )

        assert response.status_code == 202
        task_id = response.json()["task_id"]

        # 2. 초기 상태 확인 (대기)
        def mock_status_queued(tid):
            if tid == task_id:
                return {
                    "task_id": task_id,
                    "status": TaskStatus.QUEUED.value,
                    "progress": 0.0,
                    "result": None,
                    "error": None,
                }
            return None

        monkeypatch.setattr(
            "backend.app.main.TaskManager.get_status",
            mock_status_queued
        )

        response = client.get(f"/api/backtests/status/{task_id}")
        assert response.status_code == 200
        assert response.json()["status"] == TaskStatus.QUEUED.value
        assert response.json()["progress"] == 0.0

        # 3. 중간 상태 확인 (실행 중)
        def mock_status_running(tid):
            if tid == task_id:
                return {
                    "task_id": task_id,
                    "status": TaskStatus.RUNNING.value,
                    "progress": 0.5,
                    "result": None,
                    "error": None,
                }
            return None

        monkeypatch.setattr(
            "backend.app.main.TaskManager.get_status",
            mock_status_running
        )

        response = client.get(f"/api/backtests/status/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == TaskStatus.RUNNING.value
        assert data["progress"] == 0.5

        # 4. 최종 상태 확인 (완료)
        mock_result = {
            "version": "1.1.0",
            "run_id": task_id,
            "strategy": "volume_zone_breakout",
            "symbols": ["BTC_KRW"],
            "total_signals": 15,
            "execution_time": 8.5,
        }

        def mock_status_completed(tid):
            if tid == task_id:
                return {
                    "task_id": task_id,
                    "status": TaskStatus.COMPLETED.value,
                    "progress": 1.0,
                    "result": mock_result,
                    "error": None,
                }
            return None

        monkeypatch.setattr(
            "backend.app.main.TaskManager.get_status",
            mock_status_completed
        )

        response = client.get(f"/api/backtests/status/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == TaskStatus.COMPLETED.value
        assert data["progress"] == 1.0
        assert data["result"]["total_signals"] == 15
        assert data["result"]["execution_time"] == 8.5


class TestCancelBacktestTask:
    """작업 취소 엔드포인트 테스트 (Phase 3 추가, 개선됨)

    DELETE /api/backtests/tasks/{task_id} 취소 기능을 테스트합니다.

    개선사항:
    - conftest의 InMemoryRedis를 사용한 실제 상태 저장 검증
    - TaskManager.cancel_task 실제 구현 실행
    - 취소 후 Redis에 status="cancelled" 저장 여부 확인
    """

    def test_cancel_queued_task_success(self, setup_task_in_redis, in_memory_redis_instance):
        """대기 중인 작업 취소 성공 (상태 저장 검증)"""
        task_id = str(uuid.uuid4())

        # 1. Redis에 초기 상태 설정: queued
        setup_task_in_redis(task_id, status=TaskStatus.QUEUED.value, progress=0.0)

        # 2. 취소 API 호출
        response = client.delete(f"/api/backtests/tasks/{task_id}")

        # 3. 응답 검증
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "cancelled"
        assert "created_at" in data

        # 4. Redis 상태 검증 (개선됨: 실제 저장 확인)
        task_key = f"task:{task_id}"
        stored_status = in_memory_redis_instance.hget(task_key, "status")
        assert stored_status == TaskStatus.CANCELLED.value, \
            f"Expected cancelled status in Redis, got {stored_status}"

    def test_cancel_running_task_success(self, setup_task_in_redis, in_memory_redis_instance):
        """실행 중인 작업 취소 성공 (상태 저장 검증)"""
        task_id = str(uuid.uuid4())

        # 1. Redis에 초기 상태 설정: running
        setup_task_in_redis(task_id, status=TaskStatus.RUNNING.value, progress=0.6)

        # 2. 취소 API 호출
        response = client.delete(f"/api/backtests/tasks/{task_id}")

        # 3. 응답 검증
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

        # 4. Redis 상태 검증 (개선됨)
        task_key = f"task:{task_id}"
        stored_status = in_memory_redis_instance.hget(task_key, "status")
        assert stored_status == TaskStatus.CANCELLED.value

    def test_cancel_completed_task_fails(self, setup_task_in_redis):
        """완료된 작업 취소 실패 (400) - 상태 저장 검증"""
        task_id = str(uuid.uuid4())

        # 1. Redis에 초기 상태 설정: completed
        setup_task_in_redis(task_id, status=TaskStatus.COMPLETED.value, progress=1.0)

        # 2. 취소 시도 → 실패 예상
        response = client.delete(f"/api/backtests/tasks/{task_id}")

        # 3. 에러 응답 검증
        assert response.status_code == 400
        data = response.json()
        assert "Cannot cancel" in data["detail"]
        assert "completed" in data["detail"].lower()

    def test_cancel_failed_task_fails(self, setup_task_in_redis):
        """실패한 작업 취소 실패 (400) - 상태 저장 검증"""
        task_id = str(uuid.uuid4())

        # 1. Redis에 초기 상태 설정: failed
        setup_task_in_redis(task_id, status=TaskStatus.FAILED.value, progress=0.5)

        # 2. 취소 시도 → 실패 예상
        response = client.delete(f"/api/backtests/tasks/{task_id}")

        # 3. 에러 응답 검증
        assert response.status_code == 400
        data = response.json()
        assert "Cannot cancel" in data["detail"]

    def test_cancel_nonexistent_task(self, in_memory_redis_instance):
        """존재하지 않는 작업 취소 (404) - Redis에 없는 작업"""
        fake_task_id = str(uuid.uuid4())

        # Redis에 해당 작업이 없음을 확인
        assert in_memory_redis_instance.hget(f"task:{fake_task_id}", "status") is None

        # 취소 시도 → 404 예상
        response = client.delete(f"/api/backtests/tasks/{fake_task_id}")

        assert response.status_code == 404
        data = response.json()
        assert "Task not found" in data["detail"]

    def test_cancel_and_verify_state_consistency(self, setup_task_in_redis):
        """DELETE 취소 후 GET 조회 시 동일한 cancelled 상태 반환 (상태 일관성 개선)

        이 테스트는:
        1. 초기 상태를 Redis에 설정
        2. DELETE로 취소
        3. GET으로 조회하면 같은 cancelled 상태를 반환하는지 검증
        4. 실제 Redis 상태 저장 확인
        """
        task_id = str(uuid.uuid4())

        # 1. Redis에 초기 상태 설정: queued
        setup_task_in_redis(task_id, status=TaskStatus.QUEUED.value, progress=0.0)

        # 2. 취소 전 상태 확인
        response1 = client.get(f"/api/backtests/status/{task_id}")
        assert response1.json()["status"] == "queued"

        # 3. DELETE로 취소
        response2 = client.delete(f"/api/backtests/tasks/{task_id}")
        assert response2.json()["status"] == "cancelled"

        # 4. GET으로 조회 → cancelled 상태 확인 (상태 일관성)
        response3 = client.get(f"/api/backtests/status/{task_id}")
        data = response3.json()
        assert data["status"] == "cancelled", \
            f"Expected cancelled status, got {data['status']}"
        assert data["error"] == "Task cancelled by user", \
            "Expected cancellation reason in error field"
