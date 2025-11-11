"""
결과 저장 추상 인터페이스 및 구현체
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from pathlib import Path
import logging
import os
import uuid

logger = logging.getLogger(__name__)

# Import converters for Parquet operations
try:
    from backend.app.storage.converters import json_to_parquet, parquet_to_json
    CONVERTERS_AVAILABLE = True
except ImportError:
    CONVERTERS_AVAILABLE = False
    logger.warning("converters module not available, Parquet operations disabled")

# Import database manager for PostgreSQL operations
try:
    from backend.app.database import DatabaseManager
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("database module not available")


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
    PostgreSQL + Parquet 기반 결과 저장소

    Task 3.5.3: PostgreSQL에 메타데이터를 저장하고,
    Parquet 파일로 대용량 신호 데이터를 저장합니다.
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        parquet_base_dir: str = "backtests",
        compression: str = "snappy",
    ):
        """
        Args:
            database_url: PostgreSQL 연결 문자열 (없으면 DATABASE_URL 환경변수 사용)
            parquet_base_dir: Parquet 파일 저장 기본 디렉토리
            compression: Parquet 압축 코덱 ('snappy', 'gzip', etc.)
        """
        if not DB_AVAILABLE:
            raise RuntimeError("DatabaseManager not available")
        if not CONVERTERS_AVAILABLE:
            raise RuntimeError("Converters module not available")

        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://coin_user:coin_password@localhost:5432/coin_db"
        )
        self.db = DatabaseManager(self.database_url)
        self.parquet_base_dir = parquet_base_dir
        self.compression = compression

        # Initialize database connection
        try:
            self.db.connect()
            logger.info(f"PostgreSQLResultStorage initialized: {self.database_url}")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL connection: {e}")
            raise

    async def save_result(self, task_id: str, data: dict) -> bool:
        """
        PostgreSQL + Parquet에 결과 저장

        1. Parquet 파일로 신호 데이터 저장
        2. PostgreSQL에 메타데이터 INSERT (트랜잭션)
        3. 실패 시 롤백 및 파일 삭제

        Args:
            task_id: 작업 ID
            data: 백테스트 결과 dict

        Returns:
            성공 여부
        """
        try:
            # Create output directory
            task_id_str = str(task_id)
            output_dir = str(Path(self.parquet_base_dir) / task_id_str)
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            # Convert JSON to Parquet
            logger.info(f"Converting JSON to Parquet: task_id={task_id_str}")
            parquet_result = json_to_parquet(
                data,
                output_dir,
                compression=self.compression,
            )

            # Extract metadata
            symbols = [s.get('symbol') for s in data.get('symbols', [])]
            total_size = parquet_result['total_size']
            metadata = parquet_result['metadata']

            # Get dates from data (optional fields)
            start_date = data.get('start_date')
            end_date = data.get('end_date')

            # Insert into PostgreSQL
            with self.db.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO backtest_results
                        (task_id, strategy, symbols, start_date, end_date, status,
                         parquet_path, file_size, record_count, metadata, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (task_id) DO UPDATE
                        SET status = EXCLUDED.status,
                            file_size = EXCLUDED.file_size,
                            record_count = EXCLUDED.record_count,
                            metadata = EXCLUDED.metadata,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        task_id_str,
                        data.get('strategy'),
                        json.dumps(symbols),  # JSONB
                        start_date,
                        end_date,
                        'completed',
                        output_dir,
                        total_size,
                        metadata['parquet_files']['symbol_signals']['row_count'],
                        json.dumps(metadata),
                    ))
                conn.commit()

            logger.info(f"Result saved successfully: task_id={task_id_str}, size={total_size} bytes")
            return True

        except Exception as e:
            logger.error(f"Failed to save result: {e}", exc_info=True)
            # Try to cleanup Parquet files on failure
            try:
                import shutil
                output_dir = str(Path(self.parquet_base_dir) / str(task_id))
                if Path(output_dir).exists():
                    shutil.rmtree(output_dir)
                    logger.info(f"Cleaned up Parquet files: {output_dir}")
            except Exception as cleanup_err:
                logger.warning(f"Failed to cleanup Parquet files: {cleanup_err}")
            return False

    async def get_result(self, task_id: str) -> Optional[dict]:
        """
        PostgreSQL + Parquet에서 결과 조회

        1. PostgreSQL에서 메타데이터 조회
        2. Parquet 파일 읽기
        3. 데이터 병합

        Args:
            task_id: 작업 ID

        Returns:
            결과 dict 또는 None
        """
        try:
            task_id_str = str(task_id)

            # Get metadata from PostgreSQL
            with self.db.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT task_id, strategy, symbols, start_date, end_date, status,
                               parquet_path, file_size, record_count, metadata
                        FROM backtest_results
                        WHERE task_id = %s::uuid
                    """, (task_id_str,))

                    row = cur.fetchone()

            if not row:
                logger.warning(f"Result not found: task_id={task_id_str}")
                return None

            # Unpack row
            (task_id_db, strategy, symbols_json, start_date, end_date, status,
             parquet_path, file_size, record_count, metadata_json) = row

            # Read Parquet files
            parquet_data = parquet_to_json(parquet_path, include_metadata=False)

            # Merge metadata
            result = {
                'task_id': str(task_id_db),
                'strategy': strategy,
                'symbols': parquet_data.get('symbols', []),
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None,
                'status': status,
                'file_size': file_size,
                'record_count': record_count,
                'metadata': json.loads(metadata_json) if metadata_json else {},
            }

            logger.info(f"Result retrieved successfully: task_id={task_id_str}")
            return result

        except Exception as e:
            logger.error(f"Failed to get result: {e}", exc_info=True)
            return None

    async def cleanup_old_results(
        self,
        days: int = 7,
        dry_run: bool = False
    ) -> int:
        """
        오래된 결과 삭제

        N일 이상된 결과의 PostgreSQL 레코드와 Parquet 파일을 삭제합니다.

        Args:
            days: N일 이상된 결과 삭제
            dry_run: True면 실제 삭제하지 않고 개수만 반환

        Returns:
            삭제된 결과 개수
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Find old results
            with self.db.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT task_id, parquet_path
                        FROM backtest_results
                        WHERE created_at < %s
                    """, (cutoff_date,))

                    old_results = cur.fetchall()

            deleted_count = 0

            if dry_run:
                logger.info(f"Dry-run: would delete {len(old_results)} old results (older than {days} days)")
                return len(old_results)

            # Delete Parquet files and PostgreSQL records
            for task_id, parquet_path in old_results:
                try:
                    # Delete Parquet directory
                    parquet_dir = Path(parquet_path)
                    if parquet_dir.exists():
                        import shutil
                        shutil.rmtree(parquet_dir)
                        logger.info(f"Deleted Parquet directory: {parquet_path}")

                    # Delete PostgreSQL record
                    with self.db.get_conn() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                DELETE FROM backtest_results
                                WHERE task_id = %s::uuid
                            """, (str(task_id),))
                        conn.commit()

                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete result {task_id}: {e}")
                    continue

            logger.info(f"Deleted {deleted_count} old results (older than {days} days)")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old results: {e}", exc_info=True)
            return 0

    async def list_results(
        self,
        limit: int = 100,
        offset: int = 0,
        strategy: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[dict]:
        """
        결과 목록 조회

        필터링과 페이지네이션을 지원합니다.

        Args:
            limit: 최대 조회 개수
            offset: 시작 위치
            strategy: 전략 필터
            status: 상태 필터 ('completed', 'failed', 'running')

        Returns:
            결과 메타데이터 리스트
        """
        try:
            query = """
                SELECT task_id, strategy, status, created_at, updated_at,
                       file_size, record_count
                FROM backtest_results
                WHERE 1=1
            """
            params = []

            if strategy:
                query += " AND strategy = %s"
                params.append(strategy)

            if status:
                query += " AND status = %s"
                params.append(status)

            query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            results = []
            with self.db.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    rows = cur.fetchall()

            for row in rows:
                result_dict = {
                    'task_id': str(row[0]),
                    'strategy': row[1],
                    'status': row[2],
                    'created_at': row[3].isoformat() if row[3] else None,
                    'updated_at': row[4].isoformat() if row[4] else None,
                    'file_size': row[5],
                    'record_count': row[6],
                }
                results.append(result_dict)

            logger.info(f"Listed {len(results)} results (limit={limit}, offset={offset})")
            return results

        except Exception as e:
            logger.error(f"Failed to list results: {e}", exc_info=True)
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
