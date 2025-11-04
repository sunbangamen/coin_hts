"""
비동기 백테스트 API 엔드포인트 테스트 (Phase 3)

비동기 백테스트 실행, 상태 조회 엔드포인트를 테스트합니다.
"""

import pytest
import json
import uuid
import time
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.task_manager import TaskManager, TaskStatus

client = TestClient(app)


@pytest.fixture
def mock_redis(monkeypatch):
    """Redis 연결을 mock합니다 (테스트 환경용)"""
    mock_redis_conn = MagicMock()
    monkeypatch.setattr("backend.app.config.redis_conn", mock_redis_conn)
    monkeypatch.setattr("backend.app.main.redis_conn", mock_redis_conn)
    return mock_redis_conn


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

    def test_run_backtest_async_success(self, mock_redis):
        """비동기 백테스트 성공 테스트"""
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
        assert data["status"] in ["queued", "running"]

        # task_id가 UUID 형식인지 확인
        try:
            uuid.UUID(data["task_id"])
        except ValueError:
            pytest.fail(f"Invalid UUID format: {data['task_id']}")

    def test_run_backtest_async_with_params(self, mock_redis):
        """커스텀 파라미터를 포함한 비동기 백테스트 테스트"""
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


class TestTaskStatusEndpoints:
    """작업 상태 조회 엔드포인트 테스트"""

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

        # TaskManager.get_status를 mock
        def mock_get_status(tid):
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
            mock_get_status
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

        def mock_get_status(tid):
            if tid == task_id:
                return {
                    "task_id": task_id,
                    "status": TaskStatus.RUNNING.value,
                    "progress": 0.45,
                    "result": None,
                    "error": None,
                }
            return None

        monkeypatch.setattr(
            "backend.app.main.TaskManager.get_status",
            mock_get_status
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

        def mock_get_status(tid):
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
            mock_get_status
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

        def mock_get_status(tid):
            if tid == task_id:
                return {
                    "task_id": task_id,
                    "status": TaskStatus.FAILED.value,
                    "progress": 0.3,
                    "result": None,
                    "error": error_message,
                }
            return None

        monkeypatch.setattr(
            "backend.app.main.TaskManager.get_status",
            mock_get_status
        )

        response = client.get(f"/api/backtests/status/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == TaskStatus.FAILED.value
        assert data["error"] == error_message
        assert data["result"] is None


class TestAsyncEndtoEndScenarios:
    """비동기 end-to-end 시나리오 테스트"""

    def test_async_workflow_sequence(self, monkeypatch):
        """비동기 워크플로우 시퀀스 테스트"""
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
        assert response.json()["status"] == TaskStatus.RUNNING.value

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
