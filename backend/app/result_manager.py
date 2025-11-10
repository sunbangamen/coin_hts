"""결과 파일 관리 모듈"""
import json
import os
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import fcntl

logger = logging.getLogger(__name__)


class ResultManager:
    """
    백테스트 결과 파일 관리 (Task 3.5: 의존성 주입 지원)

    생성자에서 storage: ResultStorage를 받아 저장소 계층에 위임합니다.
    storage가 None인 경우 기존 파일 기반 동작을 유지합니다.
    """

    def __init__(self, storage=None, data_root: Optional[str] = None):
        """
        ResultManager 초기화 (의존성 주입 + PostgreSQL 기본값)

        Args:
            storage: ResultStorage 인스턴스 (선택사항)
                     None인 경우 PostgreSQL 스토리지 시도 후 파일 기반으로 폴백
            data_root: 데이터 루트 디렉토리 (선택사항)
        """
        # storage가 None인 경우 PostgreSQL 기본값 시도 (향후 구현)
        if storage is None:
            try:
                from backend.app.storage.result_storage import PostgreSQLResultStorage
                db_url = os.getenv("DATABASE_URL")
                if db_url:
                    storage = PostgreSQLResultStorage(db_url)
                    logger.info("PostgreSQL storage initialized from DATABASE_URL")
                else:
                    logger.info("DATABASE_URL not set, falling back to file-based mode")
            except Exception as e:
                logger.warning(f"PostgreSQL storage initialization failed: {e}, using file-based mode")

        self.storage = storage
        self.data_root = data_root
        if storage:
            logger.info(f"ResultManager initialized with storage: {type(storage).__name__}")
        else:
            logger.info("ResultManager initialized in file-based mode")

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

    def save_manifest_file(
        self,
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
        manifest.json 파일 저장 (Task 3.5: 저장소 계층 위임)

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

        # manifest.json 저장 (파일 기반)
        task_dir = ResultManager.create_task_directory(data_root, task_id)
        manifest_file = os.path.join(task_dir, "manifest.json")

        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Manifest file saved: {manifest_file}")

        # 저장소 계층에 메타데이터 저장 (storage 있을 경우)
        if self.storage:
            import asyncio
            try:
                asyncio.run(self.storage.save_result(task_id, manifest_data))
                logger.info(f"Manifest saved to storage layer: task_id={task_id}")
            except Exception as e:
                logger.warning(f"Failed to save manifest to storage layer: {e}")

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
    def _get_index_file_path(data_root: str) -> str:
        """
        인덱스 파일 경로 반환

        Args:
            data_root: 데이터 루트 디렉토리

        Returns:
            인덱스 파일 경로 (RESULTS_DIR/index.json)
        """
        results_dir = os.path.join(data_root, "results")
        return os.path.join(results_dir, "index.json")

    @staticmethod
    def _read_index(data_root: str) -> Dict[str, Any]:
        """
        index.json 파일 읽기 (원자적 읽기)

        Args:
            data_root: 데이터 루트 디렉토리

        Returns:
            인덱스 데이터 dict
        """
        index_file = ResultManager._get_index_file_path(data_root)

        if not os.path.exists(index_file):
            return {"items": []}

        try:
            with open(index_file, "r", encoding="utf-8") as f:
                # 읽기 잠금 설정 (비차단)
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in index file: {e}")
            return {"items": []}
        except Exception as e:
            logger.error(f"Error reading index file: {e}")
            return {"items": []}

    @staticmethod
    def _write_index(data_root: str, index_data: Dict[str, Any]) -> bool:
        """
        index.json 파일 쓰기 (원자적 쓰기)

        Args:
            data_root: 데이터 루트 디렉토리
            index_data: 인덱스 데이터

        Returns:
            성공 여부
        """
        results_dir = os.path.join(data_root, "results")
        os.makedirs(results_dir, exist_ok=True)

        index_file = ResultManager._get_index_file_path(data_root)
        temp_file = index_file + ".tmp"

        try:
            # 임시 파일에 쓰기
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)

            # 원자적 이름 변경
            os.replace(temp_file, index_file)
            logger.info(f"Index file updated: {index_file}")
            return True
        except Exception as e:
            logger.error(f"Error writing index file: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False

    @staticmethod
    def save_result(
        data_root: str,
        run_id: str,
        result_data: Dict[str, Any],
    ) -> bool:
        """
        백테스트 결과 저장 및 인덱스 업데이트

        Args:
            data_root: 데이터 루트 디렉토리
            run_id: 실행 ID
            result_data: 결과 데이터 (BacktestResponse dict)

        Returns:
            성공 여부
        """
        # 1. 결과 파일 저장
        results_dir = os.path.join(data_root, "results")
        os.makedirs(results_dir, exist_ok=True)

        result_file = os.path.join(results_dir, f"{run_id}.json")
        try:
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"Result file saved: {result_file}")
        except Exception as e:
            logger.error(f"Failed to save result file: {e}")
            return False

        # 2. 인덱스 업데이트
        index_data = ResultManager._read_index(data_root)

        # 메타데이터 추출
        metadata = {
            "run_id": run_id,
            "strategy": result_data.get("strategy"),
            "symbols": result_data.get("symbols", []) if isinstance(result_data.get("symbols"), list) else [s["symbol"] for s in result_data.get("symbols", [])],
            "start_date": result_data.get("start_date"),
            "end_date": result_data.get("end_date"),
            "timeframe": result_data.get("timeframe"),
            "total_signals": result_data.get("total_signals"),
            "execution_time": result_data.get("execution_time"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        # 기존 항목 확인 (덮어쓰기 시)
        items = index_data.get("items", [])
        existing_idx = next((i for i, item in enumerate(items) if item["run_id"] == run_id), None)

        if existing_idx is not None:
            items[existing_idx] = metadata
        else:
            items.insert(0, metadata)  # 최신순으로 앞에 추가

        index_data["items"] = items

        return ResultManager._write_index(data_root, index_data)

    @staticmethod
    def get_latest_run_id(data_root: str) -> Optional[str]:
        """
        최신 실행 ID 조회

        Args:
            data_root: 데이터 루트 디렉토리

        Returns:
            최신 run_id 또는 None
        """
        index_data = ResultManager._read_index(data_root)
        items = index_data.get("items", [])

        if items:
            return items[0]["run_id"]
        return None

    @staticmethod
    def get_history(
        data_root: str,
        limit: int = 10,
        offset: int = 0,
        strategy: Optional[str] = None,
        min_return: Optional[float] = None,
        max_return: Optional[float] = None,
        min_signals: Optional[int] = None,
        max_signals: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        백테스트 히스토리 조회 (페이지네이션 + 필터링 지원, Task 3.3-3)

        Args:
            data_root: 데이터 루트 디렉토리
            limit: 조회 개수 (기본: 10, 최대: 100)
            offset: 시작 위치 (기본: 0)
            strategy: 전략명 필터 (선택사항)
            min_return: 최소 평균 수익률 (%, 선택사항)
            max_return: 최대 평균 수익률 (%, 선택사항)
            min_signals: 최소 신호 개수 (선택사항)
            max_signals: 최대 신호 개수 (선택사항)
            date_from: 시작 날짜 필터 (YYYY-MM-DD, 선택사항)
            date_to: 종료 날짜 필터 (YYYY-MM-DD, 선택사항)

        Returns:
            히스토리 dict
                - total: 전체 항목 수 (필터 적용 후)
                - limit: 조회 개수
                - offset: 시작 위치
                - items: 결과 배열 (페이지네이션 적용)
        """
        index_data = ResultManager._read_index(data_root)
        items = index_data.get("items", [])

        # 1. 전략 필터 적용
        if strategy:
            items = [item for item in items if item.get("strategy") == strategy]

        # 2. 신호 개수 필터 적용
        if min_signals is not None:
            items = [item for item in items if item.get("total_signals", 0) >= min_signals]
        if max_signals is not None:
            items = [item for item in items if item.get("total_signals", 0) <= max_signals]

        # 3. 기간 필터 적용
        if date_from:
            items = [item for item in items if item.get("start_date", "") >= date_from]
        if date_to:
            items = [item for item in items if item.get("end_date", "") <= date_to]

        # 4. 수익률 필터 적용 (각 항목의 메타데이터에서 평균 수익률 계산)
        if min_return is not None or max_return is not None:
            filtered_items = []
            for item in items:
                # 백테스트 결과 파일 읽기 (메모리 효율성을 위해 캐싱 가능)
                result_file = os.path.join(data_root, f"{item.get('run_id')}.json")
                try:
                    if os.path.exists(result_file):
                        with open(result_file, 'r', encoding='utf-8') as f:
                            result_data = json.load(f)
                            # 심볼별 평균 수익률 계산
                            symbols = result_data.get("symbols", [])
                            if symbols:
                                avg_return = sum(s.get("avg_return", 0) for s in symbols) / len(symbols)
                                # 수익률 필터 확인
                                if min_return is not None and avg_return < min_return:
                                    continue
                                if max_return is not None and avg_return > max_return:
                                    continue
                        filtered_items.append(item)
                except (json.JSONDecodeError, IOError):
                    # 파일 읽기 실패시 항목 제외
                    continue
            items = filtered_items

        total = len(items)
        paginated_items = items[offset : offset + limit]

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": paginated_items,
        }

    @staticmethod
    def get_result(data_root: str, run_id: str) -> Optional[Dict[str, Any]]:
        """
        특정 실행 결과 조회

        Args:
            data_root: 데이터 루트 디렉토리
            run_id: 실행 ID

        Returns:
            결과 데이터 dict 또는 None
        """
        results_dir = os.path.join(data_root, "results")
        result_file = os.path.join(results_dir, f"{run_id}.json")

        if not os.path.exists(result_file):
            return None

        try:
            with open(result_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading result file {result_file}: {e}")
            return None

    def cleanup_old_results(
        self,
        data_root: str,
        ttl_days: int = 7,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        오래된 결과 파일 정리 (Task 3.5: 저장소 계층 위임)

        Args:
            data_root: 데이터 루트 디렉토리
            ttl_days: 보존 기간 (일)
            dry_run: True일 경우 삭제하지 않고 목록만 반환

        Returns:
            정리 결과 dict
        """
        # 저장소 계층에 정리 위임은 선택사항 (별도 구현 필요)
        # Task 3.5: 현재는 파일 기반 cleanup만 사용
        # storage layer cleanup은 향후 구현 예정

        # 파일 기반 정리 (storage 없거나 실패한 경우)
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
