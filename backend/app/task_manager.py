"""비동기 작업 상태 관리 모듈"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from enum import Enum
import uuid

from .config import redis_conn

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """작업 상태"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskManager:
    """Redis 기반 비동기 작업 상태 관리"""

    TASK_KEY_PREFIX = "task:"
    TASK_PROGRESS_PREFIX = "progress:"
    TASK_RESULT_PREFIX = "result:"
    TASK_ERROR_PREFIX = "error:"
    TASK_TIMEOUT = 3600  # 1시간

    @classmethod
    def create_task(
        cls,
        strategy: str,
        params: Dict[str, Any],
        symbols: list,
        start_date: str,
        end_date: str,
        timeframe: str = "1d",
    ) -> str:
        """
        새로운 비동기 작업 생성

        Args:
            strategy: 전략명
            params: 전략 파라미터
            symbols: 심볼 목록
            start_date: 시작 날짜
            end_date: 종료 날짜
            timeframe: 타임프레임

        Returns:
            task_id (UUID)
        """
        task_id = str(uuid.uuid4())
        task_data = {
            "task_id": task_id,
            "status": TaskStatus.QUEUED.value,
            "strategy": strategy,
            "params": json.dumps(params),
            "symbols": json.dumps(symbols),
            "start_date": start_date,
            "end_date": end_date,
            "timeframe": timeframe,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "progress": 0,
        }

        # Redis에 작업 정보 저장 (TTL: 1시간)
        task_key = f"{cls.TASK_KEY_PREFIX}{task_id}"
        redis_conn.hset(task_key, mapping=task_data)
        redis_conn.expire(task_key, cls.TASK_TIMEOUT)

        logger.info(f"Task created: {task_id} ({strategy})")
        return task_id

    @classmethod
    def get_task(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """
        작업 정보 조회

        Args:
            task_id: 작업 ID

        Returns:
            작업 정보 dict 또는 None
        """
        task_key = f"{cls.TASK_KEY_PREFIX}{task_id}"
        task_data = redis_conn.hgetall(task_key)

        if not task_data:
            return None

        # JSON 필드 역직렬화
        if "params" in task_data:
            task_data["params"] = json.loads(task_data["params"])
        if "symbols" in task_data:
            task_data["symbols"] = json.loads(task_data["symbols"])

        return task_data

    @classmethod
    def update_status(cls, task_id: str, status: TaskStatus) -> None:
        """
        작업 상태 업데이트

        Args:
            task_id: 작업 ID
            status: 새로운 상태
        """
        task_key = f"{cls.TASK_KEY_PREFIX}{task_id}"
        redis_conn.hset(task_key, "status", status.value)
        redis_conn.expire(task_key, cls.TASK_TIMEOUT)
        logger.info(f"Task {task_id} status updated to {status.value}")

    @classmethod
    def set_progress(cls, task_id: str, progress: float) -> None:
        """
        작업 진행률 업데이트 (0.0 ~ 1.0)

        Args:
            task_id: 작업 ID
            progress: 진행률 (0.0 ~ 1.0)
        """
        progress = max(0.0, min(1.0, progress))  # 0.0 ~ 1.0 범위로 제한
        task_key = f"{cls.TASK_KEY_PREFIX}{task_id}"
        redis_conn.hset(task_key, "progress", str(progress))
        redis_conn.expire(task_key, cls.TASK_TIMEOUT)

    @classmethod
    def set_result(cls, task_id: str, result_data: Dict[str, Any]) -> None:
        """
        작업 결과 저장

        Args:
            task_id: 작업 ID
            result_data: 결과 데이터 (dict)
        """
        result_key = f"{cls.TASK_RESULT_PREFIX}{task_id}"
        result_json = json.dumps(result_data, default=str)
        redis_conn.set(result_key, result_json)
        redis_conn.expire(result_key, cls.TASK_TIMEOUT)

        # 작업 상태 업데이트
        cls.update_status(task_id, TaskStatus.COMPLETED)
        logger.info(f"Task {task_id} result saved")

    @classmethod
    def get_result(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """
        작업 결과 조회

        Args:
            task_id: 작업 ID

        Returns:
            결과 데이터 dict 또는 None
        """
        result_key = f"{cls.TASK_RESULT_PREFIX}{task_id}"
        result_json = redis_conn.get(result_key)

        if not result_json:
            return None

        return json.loads(result_json)

    @classmethod
    def set_error(cls, task_id: str, error_message: str) -> None:
        """
        작업 에러 저장

        Args:
            task_id: 작업 ID
            error_message: 에러 메시지
        """
        error_key = f"{cls.TASK_ERROR_PREFIX}{task_id}"
        error_data = {
            "task_id": task_id,
            "error": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        error_json = json.dumps(error_data)
        redis_conn.set(error_key, error_json)
        redis_conn.expire(error_key, cls.TASK_TIMEOUT)

        # 작업 상태 업데이트
        cls.update_status(task_id, TaskStatus.FAILED)
        logger.error(f"Task {task_id} failed: {error_message}")

    @classmethod
    def get_error(cls, task_id: str) -> Optional[str]:
        """
        작업 에러 조회

        Args:
            task_id: 작업 ID

        Returns:
            에러 메시지 또는 None
        """
        error_key = f"{cls.TASK_ERROR_PREFIX}{task_id}"
        error_json = redis_conn.get(error_key)

        if not error_json:
            return None

        error_data = json.loads(error_json)
        return error_data.get("error")

    @classmethod
    def get_status(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """
        작업 상태 조회 (status, progress, result 포함)

        Args:
            task_id: 작업 ID

        Returns:
            상태 정보 dict 또는 None (keys: task_id, status, progress, result, error)
        """
        task = cls.get_task(task_id)
        if not task:
            return None

        status_info = {
            "task_id": task_id,
            "status": task.get("status", TaskStatus.QUEUED.value),
            "progress": float(task.get("progress", 0)),
            "result": cls.get_result(task_id),
            "error": cls.get_error(task_id),
        }

        return status_info
