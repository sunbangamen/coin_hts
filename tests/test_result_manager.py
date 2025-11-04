"""
결과 파일 관리 모듈 테스트 (Phase 3)

결과 디렉토리 생성, 파일 저장, manifest 생성, 정리 스크립트를 테스트합니다.
"""

import pytest
import os
import json
import tempfile
import shutil
from datetime import datetime, timedelta

from backend.app.result_manager import ResultManager


@pytest.fixture
def temp_data_root():
    """임시 데이터 루트 디렉토리"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


class TestResultManager:
    """결과 파일 관리 테스트"""

    def test_get_task_directory(self):
        """작업 디렉토리 경로 생성 테스트"""
        data_root = "/data"
        task_id = "abc123-def456"

        result = ResultManager.get_task_directory(data_root, task_id)

        assert result == "/data/tasks/abc123-def456"

    def test_create_task_directory(self, temp_data_root):
        """작업 디렉토리 생성 테스트"""
        task_id = "test-task-id"

        result = ResultManager.create_task_directory(temp_data_root, task_id)

        assert os.path.exists(result)
        assert os.path.isdir(result)
        assert "test-task-id" in result

    def test_calculate_checksum(self, temp_data_root):
        """파일 체크섬 계산 테스트"""
        # 테스트 파일 생성
        test_file = os.path.join(temp_data_root, "test.json")
        test_content = {"test": "data"}
        with open(test_file, "w") as f:
            json.dump(test_content, f)

        # 체크섬 계산
        checksum = ResultManager.calculate_checksum(test_file)

        # 체크섬이 32자 16진수 (MD5)인지 확인
        assert len(checksum) == 32
        assert all(c in "0123456789abcdef" for c in checksum)

        # 동일 파일의 체크섬 일관성 확인
        checksum2 = ResultManager.calculate_checksum(test_file)
        assert checksum == checksum2

    def test_save_result_file(self, temp_data_root):
        """결과 파일 저장 테스트"""
        task_id = "test-task-123"
        result_data = {
            "version": "1.1.0",
            "run_id": task_id,
            "strategy": "volume_zone_breakout",
            "total_signals": 25,
            "execution_time": 5.5,
        }

        result_file = ResultManager.save_result_file(
            data_root=temp_data_root,
            task_id=task_id,
            result_data=result_data,
            filename="result.json",
        )

        # 파일이 생성되었는지 확인
        assert os.path.exists(result_file)
        assert "test-task-123" in result_file
        assert result_file.endswith("result.json")

        # 파일 내용 검증
        with open(result_file, "r") as f:
            saved_data = json.load(f)

        assert saved_data["version"] == "1.1.0"
        assert saved_data["total_signals"] == 25

    def test_save_manifest_file(self, temp_data_root):
        """manifest.json 저장 테스트"""
        task_id = "manifest-test-id"
        started_at = "2025-11-04T10:00:00Z"
        finished_at = "2025-11-04T10:05:30Z"

        result_files = [
            {
                "name": "result.json",
                "path": "result.json",
                "size_bytes": 2048,
                "checksum": "abc123def456",
            }
        ]

        manifest_file = ResultManager.save_manifest_file(
            data_root=temp_data_root,
            task_id=task_id,
            strategy="volume_zone_breakout",
            params={"volume_window": 10},
            symbols=["BTC_KRW", "ETH_KRW"],
            start_date="2024-01-01",
            end_date="2024-12-31",
            timeframe="1d",
            result_files=result_files,
            started_at=started_at,
            finished_at=finished_at,
            total_signals=25,
            symbols_processed=2,
            symbols_failed=0,
            status="completed",
        )

        # manifest 파일이 생성되었는지 확인
        assert os.path.exists(manifest_file)
        assert manifest_file.endswith("manifest.json")

        # 파일 내용 검증
        with open(manifest_file, "r") as f:
            manifest = json.load(f)

        assert manifest["task_id"] == task_id
        assert manifest["status"] == "completed"
        assert manifest["strategy"] == "volume_zone_breakout"
        assert manifest["total_signals"] == 25
        assert manifest["summary"]["symbols_processed"] == 2
        assert manifest["summary"]["symbols_failed"] == 0
        assert manifest["error"]["occurred"] is False

    def test_save_manifest_file_with_error(self, temp_data_root):
        """에러 정보가 포함된 manifest.json 저장 테스트"""
        task_id = "error-manifest-test"
        error_message = "Backtest failed: data loader error"

        manifest_file = ResultManager.save_manifest_file(
            data_root=temp_data_root,
            task_id=task_id,
            strategy="volume_zone_breakout",
            params={},
            symbols=["BTC_KRW"],
            start_date="2024-01-01",
            end_date="2024-12-31",
            timeframe="1d",
            result_files=[],
            started_at="2025-11-04T10:00:00Z",
            finished_at="2025-11-04T10:01:00Z",
            total_signals=0,
            symbols_processed=0,
            symbols_failed=1,
            status="failed",
            error_message=error_message,
        )

        # manifest 파일 내용 검증
        with open(manifest_file, "r") as f:
            manifest = json.load(f)

        assert manifest["status"] == "failed"
        assert manifest["error"]["occurred"] is True
        assert manifest["error"]["message"] == error_message
        assert manifest["summary"]["symbols_failed"] == 1

    def test_get_result_file_exists(self, temp_data_root):
        """기존 결과 파일 조회 테스트"""
        task_id = "existing-result-task"
        result_data = {"version": "1.1.0"}

        # 먼저 결과 파일 저장
        ResultManager.save_result_file(
            data_root=temp_data_root,
            task_id=task_id,
            result_data=result_data,
        )

        # 파일 조회
        result_file = ResultManager.get_result_file(temp_data_root, task_id)

        assert result_file is not None
        assert os.path.exists(result_file)

    def test_get_result_file_not_exists(self, temp_data_root):
        """존재하지 않는 결과 파일 조회 테스트"""
        result_file = ResultManager.get_result_file(temp_data_root, "nonexistent-task")

        assert result_file is None

    def test_cleanup_old_results_dry_run(self, temp_data_root):
        """정리 스크립트 dry-run 모드 테스트"""
        # 오래된 작업 생성 (TTL 7일보다 오래됨)
        old_task_id = "old-task-id"
        old_finished_at = (datetime.utcnow() - timedelta(days=8)).isoformat() + "Z"

        manifest_file = ResultManager.save_manifest_file(
            data_root=temp_data_root,
            task_id=old_task_id,
            strategy="volume_zone_breakout",
            params={},
            symbols=[],
            start_date="2024-01-01",
            end_date="2024-12-31",
            timeframe="1d",
            result_files=[],
            started_at=old_finished_at,
            finished_at=old_finished_at,
            total_signals=0,
            symbols_processed=0,
            symbols_failed=0,
        )

        # Dry-run으로 정리
        result = ResultManager.cleanup_old_results(
            data_root=temp_data_root,
            ttl_days=7,
            dry_run=True,
        )

        assert result["success"] is True
        assert result["dry_run"] is True
        assert result["deleted_count"] == 1

        # 파일이 실제로 삭제되지 않았는지 확인
        assert os.path.exists(manifest_file)

    def test_cleanup_old_results_actual(self, temp_data_root):
        """정리 스크립트 실제 삭제 테스트"""
        # 오래된 작업 생성
        old_task_id = "old-task-actual"
        old_finished_at = (datetime.utcnow() - timedelta(days=8)).isoformat() + "Z"

        task_dir = ResultManager.create_task_directory(temp_data_root, old_task_id)
        manifest_file = os.path.join(task_dir, "manifest.json")

        manifest_data = {
            "task_id": old_task_id,
            "status": "completed",
            "strategy": "test",
            "metadata": {
                "finished_at": old_finished_at,
            }
        }

        with open(manifest_file, "w") as f:
            json.dump(manifest_data, f)

        # 실제 정리 실행
        result = ResultManager.cleanup_old_results(
            data_root=temp_data_root,
            ttl_days=7,
            dry_run=False,
        )

        assert result["success"] is True
        assert result["dry_run"] is False
        assert result["deleted_count"] == 1

        # 파일이 실제로 삭제되었는지 확인
        assert not os.path.exists(manifest_file)
        assert not os.path.exists(task_dir)

    def test_cleanup_skips_recent_results(self, temp_data_root):
        """정리가 최근 결과를 건너뛰는지 테스트"""
        # 최근 작업 생성 (TTL 이내)
        recent_task_id = "recent-task-id"
        recent_finished_at = (datetime.utcnow() - timedelta(days=2)).isoformat() + "Z"

        manifest_file = ResultManager.save_manifest_file(
            data_root=temp_data_root,
            task_id=recent_task_id,
            strategy="volume_zone_breakout",
            params={},
            symbols=[],
            start_date="2024-01-01",
            end_date="2024-12-31",
            timeframe="1d",
            result_files=[],
            started_at=recent_finished_at,
            finished_at=recent_finished_at,
            total_signals=0,
            symbols_processed=0,
            symbols_failed=0,
        )

        # 정리 실행
        result = ResultManager.cleanup_old_results(
            data_root=temp_data_root,
            ttl_days=7,
            dry_run=False,
        )

        assert result["deleted_count"] == 0

        # 파일이 삭제되지 않았는지 확인
        assert os.path.exists(manifest_file)
