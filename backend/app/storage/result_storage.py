"""
결과 저장 추상 인터페이스 및 구현체
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json
import sqlite3
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ResultStorage(ABC):
    """
    백테스트 결과 저장 추상 인터페이스

    결과 저장, 조회, 정리 기능을 제공합니다.
    """

    @abstractmethod
    async def save_result(self, task_id: str, data: dict) -> bool:
        """
        백테스트 결과 저장

        Args:
            task_id: 작업 ID (고유값)
            data: 저장할 결과 데이터

        Returns:
            성공 여부
        """
        pass

    @abstractmethod
    async def get_result(self, task_id: str) -> Optional[dict]:
        """
        백테스트 결과 조회

        Args:
            task_id: 작업 ID

        Returns:
            결과 데이터 또는 None
        """
        pass

    @abstractmethod
    async def cleanup_old_results(
        self,
        days: int = 7,
        dry_run: bool = False
    ) -> int:
        """
        오래된 결과 삭제

        Args:
            days: N일 이상된 결과 삭제
            dry_run: True면 실제 삭제하지 않고 개수만 반환

        Returns:
            삭제된 결과 개수
        """
        pass

    @abstractmethod
    async def list_results(self, limit: int = 100) -> List[dict]:
        """
        결과 목록 조회

        Args:
            limit: 최대 조회 개수

        Returns:
            결과 메타데이터 리스트
        """
        pass


class PostgreSQLResultStorage(ResultStorage):
    """
    PostgreSQL + Parquet 기반 결과 저장소 (향후 구현)
    """

    def __init__(self, connection_string: str):
        """
        Args:
            connection_string: PostgreSQL 연결 문자열
        """
        self.connection_string = connection_string
        logger.info(f"PostgreSQLResultStorage initialized: {connection_string}")

    async def save_result(self, task_id: str, data: dict) -> bool:
        """PostgreSQL에 결과 저장 (미구현)"""
        # TODO: PostgreSQL 연결 후 데이터 저장
        # 1. 메타데이터를 results 테이블에 INSERT
        # 2. 결과 데이터를 Parquet 파일로 저장
        logger.warning("PostgreSQLResultStorage.save_result not implemented yet")
        return False

    async def get_result(self, task_id: str) -> Optional[dict]:
        """PostgreSQL에서 결과 조회 (미구현)"""
        logger.warning("PostgreSQLResultStorage.get_result not implemented yet")
        return None

    async def cleanup_old_results(
        self,
        days: int = 7,
        dry_run: bool = False
    ) -> int:
        """PostgreSQL에서 오래된 결과 삭제 (미구현)"""
        logger.warning("PostgreSQLResultStorage.cleanup_old_results not implemented yet")
        return 0

    async def list_results(self, limit: int = 100) -> List[dict]:
        """PostgreSQL에서 결과 목록 조회 (미구현)"""
        logger.warning("PostgreSQLResultStorage.list_results not implemented yet")
        return []


class SQLiteResultStorage(ResultStorage):
    """
    SQLite 기반 결과 저장소 (테스트용)

    빠른 초기화와 테스트 실행을 위해 사용됩니다.
    """

    def __init__(self, db_path: str):
        """
        Args:
            db_path: SQLite 데이터베이스 파일 경로
        """
        self.db_path = str(db_path)
        self._init_db()
        logger.info(f"SQLiteResultStorage initialized: {self.db_path}")

    def _init_db(self):
        """데이터베이스 초기화"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 결과 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                task_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    async def save_result(self, task_id: str, data: dict) -> bool:
        """
        SQLite에 결과 저장

        Args:
            task_id: 작업 ID
            data: 저장할 데이터

        Returns:
            저장 성공 여부
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            data_json = json.dumps(data, default=str)

            cursor.execute("""
                INSERT OR REPLACE INTO results (task_id, data, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (task_id, data_json))

            conn.commit()
            conn.close()

            logger.info(f"Result saved: task_id={task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save result: {e}")
            return False

    async def get_result(self, task_id: str) -> Optional[dict]:
        """
        SQLite에서 결과 조회

        Args:
            task_id: 작업 ID

        Returns:
            저장된 데이터 또는 None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT data FROM results WHERE task_id = ?
            """, (task_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return json.loads(row[0])
            return None
        except Exception as e:
            logger.error(f"Failed to get result: {e}")
            return None

    async def cleanup_old_results(
        self,
        days: int = 7,
        dry_run: bool = False
    ) -> int:
        """
        SQLite에서 오래된 결과 삭제

        Args:
            days: N일 이상된 결과 삭제
            dry_run: True면 실제 삭제하지 않고 개수만 반환

        Returns:
            삭제된 결과 개수
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 삭제할 결과 개수 조회
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

            cursor.execute("""
                SELECT COUNT(*) FROM results
                WHERE created_at < ?
            """, (cutoff_date,))

            count = cursor.fetchone()[0]

            if not dry_run and count > 0:
                cursor.execute("""
                    DELETE FROM results
                    WHERE created_at < ?
                """, (cutoff_date,))
                conn.commit()
                logger.info(f"Deleted {count} old results (older than {days} days)")
            elif dry_run:
                logger.info(f"Dry run: would delete {count} results (older than {days} days)")

            conn.close()
            return count
        except Exception as e:
            logger.error(f"Failed to cleanup old results: {e}")
            return 0

    async def list_results(self, limit: int = 100) -> List[dict]:
        """
        SQLite에서 결과 목록 조회

        Args:
            limit: 최대 조회 개수

        Returns:
            결과 메타데이터 리스트
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT task_id, created_at, updated_at
                FROM results
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            results = []
            for task_id, created_at, updated_at in rows:
                results.append({
                    'task_id': task_id,
                    'created_at': created_at,
                    'updated_at': updated_at,
                })

            return results
        except Exception as e:
            logger.error(f"Failed to list results: {e}")
            return []
