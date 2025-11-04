"""결과 파일 관리 모듈"""
import json
import os
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ResultManager:
    """백테스트 결과 파일 관리"""

    @staticmethod
    def get_task_directory(data_root: str, task_id: str) -> str:
        """
        작업 결과 디렉토리 경로 반환

        Args:
            data_root: 데이터 루트 디렉토리 (예: /data)
            task_id: 작업 ID

        Returns:
            작업 디렉토리 경로 (예: /data/tasks/{task_id})
        """
        task_dir = os.path.join(data_root, "tasks", task_id)
        return task_dir

    @staticmethod
    def create_task_directory(data_root: str, task_id: str) -> str:
        """
        작업 결과 디렉토리 생성

        Args:
            data_root: 데이터 루트 디렉토리
            task_id: 작업 ID

        Returns:
            생성된 디렉토리 경로
        """
        task_dir = ResultManager.get_task_directory(data_root, task_id)
        os.makedirs(task_dir, exist_ok=True)
        logger.info(f"Task directory created: {task_dir}")
        return task_dir

    @staticmethod
    def calculate_checksum(file_path: str, algorithm: str = "md5") -> str:
        """
        파일 체크섬 계산

        Args:
            file_path: 파일 경로
            algorithm: 해시 알고리즘 (md5, sha256 등)

        Returns:
            체크섬 해시 문자열
        """
        hash_func = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()

    @staticmethod
    def save_result_file(
        data_root: str,
        task_id: str,
        result_data: Dict[str, Any],
        filename: str = "result.json",
    ) -> str:
        """
        백테스트 결과 파일 저장

        Args:
            data_root: 데이터 루트 디렉토리
            task_id: 작업 ID
            result_data: 결과 데이터
            filename: 파일명 (기본값: result.json)

        Returns:
            저장된 파일 경로
        """
        task_dir = ResultManager.create_task_directory(data_root, task_id)
        result_file = os.path.join(task_dir, filename)

        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Result file saved: {result_file}")
        return result_file

    @staticmethod
    def save_manifest_file(
        data_root: str,
        task_id: str,
        strategy: str,
        params: Dict[str, Any],
        symbols: List[str],
        start_date: str,
        end_date: str,
        timeframe: str,
        result_files: List[Dict[str, Any]],
        started_at: str,
        finished_at: str,
        total_signals: int,
        symbols_processed: int,
        symbols_failed: int,
        status: str = "completed",
        error_message: Optional[str] = None,
    ) -> str:
        """
        manifest.json 파일 저장

        Args:
            data_root: 데이터 루트 디렉토리
            task_id: 작업 ID
            strategy: 전략명
            params: 전략 파라미터
            symbols: 심볼 목록
            start_date: 백테스트 시작 날짜
            end_date: 백테스트 종료 날짜
            timeframe: 타임프레임
            result_files: 생성된 파일 목록
            started_at: 시작 시간 (ISO 8601, UTC)
            finished_at: 종료 시간 (ISO 8601, UTC)
            total_signals: 총 신호 개수
            symbols_processed: 처리한 심볼 수
            symbols_failed: 실패한 심볼 수
            status: 작업 상태 (completed, failed)
            error_message: 에러 메시지 (status=failed 시)

        Returns:
            저장된 manifest 파일 경로
        """
        # 실행 시간 계산
        start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        finished_dt = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
        duration_ms = int((finished_dt - start_dt).total_seconds() * 1000)

        # 심볼당 평균 실행 시간
        symbols_total = symbols_processed + symbols_failed
        avg_execution_time = (
            duration_ms / symbols_total if symbols_total > 0 else 0
        )

        # Manifest 데이터
        manifest_data = {
            "task_id": task_id,
            "status": status,
            "strategy": strategy,
            "params": params,
            "symbols": symbols,
            "start_date": start_date,
            "end_date": end_date,
            "timeframe": timeframe,
            "result_files": result_files,
            "metadata": {
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_ms": duration_ms,
                "execution_host": os.getenv("HOSTNAME", "local"),
                "environment": os.getenv("ENVIRONMENT", "development"),
            },
            "summary": {
                "total_signals": total_signals,
                "symbols_processed": symbols_processed,
                "symbols_failed": symbols_failed,
                "average_execution_time_per_symbol_ms": avg_execution_time,
            },
            "error": {
                "occurred": error_message is not None,
                "message": error_message,
            },
        }

        # manifest.json 저장
        task_dir = ResultManager.get_task_directory(data_root, task_id)
        manifest_file = os.path.join(task_dir, "manifest.json")

        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Manifest file saved: {manifest_file}")
        return manifest_file

    @staticmethod
    def get_result_file(data_root: str, task_id: str, filename: str = "result.json") -> Optional[str]:
        """
        결과 파일 경로 조회

        Args:
            data_root: 데이터 루트 디렉토리
            task_id: 작업 ID
            filename: 파일명 (기본값: result.json)

        Returns:
            파일 경로 또는 None
        """
        result_file = os.path.join(
            ResultManager.get_task_directory(data_root, task_id),
            filename
        )
        if os.path.exists(result_file):
            return result_file
        return None

    @staticmethod
    def cleanup_old_results(
        data_root: str,
        ttl_days: int = 7,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        오래된 결과 파일 정리

        Args:
            data_root: 데이터 루트 디렉토리
            ttl_days: 보존 기간 (일)
            dry_run: True일 경우 삭제하지 않고 목록만 반환

        Returns:
            정리 결과 dict
        """
        tasks_dir = os.path.join(data_root, "tasks")

        if not os.path.exists(tasks_dir):
            return {
                "success": True,
                "deleted_count": 0,
                "deleted_size_bytes": 0,
                "dry_run": dry_run,
            }

        now = datetime.utcnow()
        cutoff_date = now - timedelta(days=ttl_days)
        deleted_count = 0
        deleted_size = 0

        for task_id in os.listdir(tasks_dir):
            task_dir = os.path.join(tasks_dir, task_id)

            if not os.path.isdir(task_dir):
                continue

            # manifest.json의 생성 시간 확인
            manifest_file = os.path.join(task_dir, "manifest.json")

            try:
                if not os.path.exists(manifest_file):
                    logger.warning(f"Manifest not found: {manifest_file}")
                    continue

                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)

                finished_at_str = manifest.get("metadata", {}).get("finished_at")
                if not finished_at_str:
                    logger.warning(f"No finished_at in manifest: {task_id}")
                    continue

                # ISO 8601 시간 파싱
                finished_at = datetime.fromisoformat(
                    finished_at_str.replace("Z", "+00:00")
                ).replace(tzinfo=None)

                # TTL 초과 확인
                if finished_at < cutoff_date:
                    # 디렉토리 전체 크기 계산
                    dir_size = sum(
                        os.path.getsize(os.path.join(task_dir, f))
                        for f in os.listdir(task_dir)
                        if os.path.isfile(os.path.join(task_dir, f))
                    )

                    logger.info(
                        f"Cleaning up old task: {task_id} "
                        f"(finished: {finished_at}, size: {dir_size} bytes)"
                    )

                    if not dry_run:
                        # 디렉토리 삭제
                        import shutil
                        shutil.rmtree(task_dir)
                        logger.info(f"Deleted task directory: {task_dir}")

                    deleted_count += 1
                    deleted_size += dir_size

            except Exception as e:
                logger.error(
                    f"Error processing task directory {task_dir}: {str(e)}",
                    exc_info=True
                )
                continue

        return {
            "success": True,
            "deleted_count": deleted_count,
            "deleted_size_bytes": deleted_size,
            "deleted_size_mb": round(deleted_size / (1024 * 1024), 2),
            "dry_run": dry_run,
        }
