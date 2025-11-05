"""
데이터베이스 연결 및 ORM 설정

PostgreSQL을 주 저장소로 사용하며, 실시간 시뮬레이션 데이터를 저장합니다.
연결 풀링을 지원하며, 동기/비동기 컨텍스트 모두 지원합니다.
"""

import os
import logging
import asyncio
from contextlib import contextmanager
from typing import Optional, Generator, Dict, List, Tuple
from datetime import datetime

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool

logger = logging.getLogger(__name__)


class DatabaseManager:
    """PostgreSQL 연결 풀 관리자"""

    def __init__(self, database_url: Optional[str] = None, pool_size: int = 5):
        """
        Args:
            database_url: PostgreSQL 연결 URL
                          미제공 시 환경 변수 DATABASE_URL 사용
            pool_size: 연결 풀 크기 (기본: 5)
        """
        self.database_url = database_url or os.getenv(
            'DATABASE_URL',
            'postgresql://coin_user:coin_password@localhost:5432/coin_db'
        )
        self.pool_size = pool_size
        self.pool: Optional[SimpleConnectionPool] = None

    def connect(self) -> None:
        """연결 풀 초기화"""
        try:
            self.pool = SimpleConnectionPool(1, self.pool_size, self.database_url)
            logger.info(f"PostgreSQL connection pool initialized (size: {self.pool_size})")
        except psycopg2.Error as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise

    def disconnect(self) -> None:
        """연결 풀 종료"""
        if self.pool:
            self.pool.closeall()
            logger.info("PostgreSQL connection pool closed")
            self.pool = None

    @contextmanager
    def get_conn(self) -> Generator:
        """
        동기 컨텍스트: 연결 풀에서 연결 획득

        Usage:
            with db.get_conn() as conn:
                cur = conn.cursor()
                cur.execute(...)
        """
        if not self.pool:
            raise RuntimeError("Connection pool not initialized")

        conn = self.pool.getconn()
        try:
            yield conn
        finally:
            self.pool.putconn(conn)

    async def execute_async(self, query: str, params: tuple = None) -> None:
        """비동기 SQL 쿼리 실행 (asyncio.to_thread 사용)"""
        def _execute():
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                conn.commit()

        await asyncio.to_thread(_execute)

    async def fetch_one_async(self, query: str, params: tuple = None) -> Optional[dict]:
        """비동기 SQL 쿼리 실행 (단일 행 반환)"""
        def _fetch():
            with self.get_conn() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, params)
                    return cur.fetchone()

        return await asyncio.to_thread(_fetch)

    async def fetch_all_async(self, query: str, params: tuple = None) -> List[dict]:
        """비동기 SQL 쿼리 실행 (모든 행 반환, 읽기 전용)"""
        def _fetch():
            with self.get_conn() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, params)
                    return cur.fetchall()

        return await asyncio.to_thread(_fetch)

    # ============ 캔들 데이터 CRUD ============

    async def insert_candle_async(self, symbol: str, timeframe: str, timestamp: datetime,
                                 open_price: float, high: float, low: float,
                                 close: float, volume: float) -> int:
        """캔들 데이터 비동기 저장 (INSERT OR UPDATE with COMMIT)"""
        def _insert():
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO market_candles (symbol, timeframe, timestamp, open, high, low, close, volume)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (symbol, timeframe, timestamp) DO UPDATE
                        SET open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                            close = EXCLUDED.close, volume = EXCLUDED.volume
                        RETURNING id
                    """, (symbol, timeframe, timestamp, open_price, high, low, close, volume))
                    candle_id = cur.fetchone()[0]
                conn.commit()
                return candle_id

        return await asyncio.to_thread(_insert)

    def insert_candle(self, symbol: str, timeframe: str, timestamp: datetime,
                     open_price: float, high: float, low: float,
                     close: float, volume: float) -> int:
        """캔들 데이터 저장 (INSERT OR UPDATE)"""
        query = """
            INSERT INTO market_candles (symbol, timeframe, timestamp, open, high, low, close, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, timeframe, timestamp) DO UPDATE
            SET open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                close = EXCLUDED.close, volume = EXCLUDED.volume
            RETURNING id
        """

        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (symbol, timeframe, timestamp, open_price, high, low, close, volume))
                candle_id = cur.fetchone()[0]
            conn.commit()
            return candle_id

    def get_latest_candle(self, symbol: str, timeframe: str) -> Optional[dict]:
        """최신 캔들 조회"""
        query = """
            SELECT id, timestamp, open, high, low, close, volume
            FROM market_candles
            WHERE symbol = %s AND timeframe = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """

        with self.get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (symbol, timeframe))
                return cur.fetchone()

    def get_recent_candles(self, symbol: str, timeframe: str, count: int = 200) -> List[dict]:
        """최근 N개 캔들 조회"""
        query = """
            SELECT id, timestamp, open, high, low, close, volume
            FROM market_candles
            WHERE symbol = %s AND timeframe = %s
            ORDER BY timestamp DESC
            LIMIT %s
        """

        with self.get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (symbol, timeframe, count))
                rows = cur.fetchall()
                return list(reversed(rows))  # 오래된 순서로 반환

    # ============ 신호 데이터 CRUD ============

    def insert_signal(self, symbol: str, strategy_name: str, timestamp: datetime,
                     side: str, price: float, confidence: float) -> int:
        """신호 저장"""
        query = """
            INSERT INTO signals (symbol, strategy_name, timestamp, side, price, confidence)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """

        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (symbol, strategy_name, timestamp, side, price, confidence))
                signal_id = cur.fetchone()[0]
            conn.commit()
            return signal_id

    # ============ 포지션 데이터 CRUD (Phase 3) ============

    def insert_position(self, symbol: str, strategy_name: str, entry_time: datetime,
                       entry_price: float, quantity: float, fee_amount: float = 0) -> int:
        """포지션 진입 기록"""
        query = """
            INSERT INTO simulation_positions
            (symbol, strategy_name, entry_time, entry_price, quantity, status, fee_amount)
            VALUES (%s, %s, %s, %s, %s, 'OPEN', %s)
            RETURNING id
        """

        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (symbol, strategy_name, entry_time, entry_price, quantity, fee_amount))
                position_id = cur.fetchone()[0]
            conn.commit()
            return position_id

    def update_position_unrealized_pnl(self, position_id: int, current_price: float) -> None:
        """포지션 미실현 손익 업데이트"""
        query = """
            UPDATE simulation_positions
            SET last_price = %s,
                unrealized_pnl = (quantity * (%s - entry_price) - fee_amount),
                unrealized_pnl_pct = ((quantity * (%s - entry_price) - fee_amount) / (entry_price * quantity)) * 100,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """

        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (current_price, current_price, current_price, position_id))
            conn.commit()

    def update_position_on_close(self, position_id: int, exit_time: datetime,
                                exit_price: float, slippage_amount: float = 0) -> None:
        """포지션 종료 기록 (realized_pnl 및 realized_pnl_pct 자동 계산)"""
        query = """
            UPDATE simulation_positions
            SET status = 'CLOSED',
                exit_time = %s,
                exit_price = %s,
                realized_pnl = (quantity * (%s - entry_price) - fee_amount - %s),
                realized_pnl_pct = ((quantity * (%s - entry_price) - fee_amount - %s) /
                                   (entry_price * quantity)) * 100,
                slippage_amount = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """

        with self.get_conn() as conn:
            with conn.cursor() as cur:
                # 파라미터: exit_time, exit_price, exit_price (realized_pnl용), slippage_amount,
                #          exit_price (realized_pnl_pct용), slippage_amount, slippage_amount (SET), position_id
                cur.execute(query, (exit_time, exit_price, exit_price, slippage_amount,
                                  exit_price, slippage_amount, slippage_amount, position_id))
            conn.commit()

    def insert_trade(self, symbol: str, strategy_name: str, entry_time: datetime,
                    entry_price: float, exit_time: datetime, exit_price: float,
                    quantity: float, realized_pnl: float, realized_pnl_pct: float,
                    fee_amount: float = 0, slippage_amount: float = 0) -> int:
        """거래 기록 (포지션 종료 후 호출)"""
        hold_duration = exit_time - entry_time

        query = """
            INSERT INTO simulation_trades
            (symbol, strategy_name, entry_time, entry_price, exit_time, exit_price,
             quantity, realized_pnl, realized_pnl_pct, fee_amount, slippage_amount, hold_duration)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """

        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (symbol, strategy_name, entry_time, entry_price,
                                  exit_time, exit_price, quantity, realized_pnl,
                                  realized_pnl_pct, fee_amount, slippage_amount, hold_duration))
                trade_id = cur.fetchone()[0]
            conn.commit()
            return trade_id

    def get_open_positions(self, symbol: str = None, strategy_name: str = None) -> List[dict]:
        """활성 포지션 조회"""
        query = "SELECT * FROM simulation_positions WHERE status = 'OPEN'"
        params = []

        if symbol:
            query += " AND symbol = %s"
            params.append(symbol)

        if strategy_name:
            query += " AND strategy_name = %s"
            params.append(strategy_name)

        query += " ORDER BY entry_time DESC"

        with self.get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params if params else None)
                return cur.fetchall()

    # ============ 세션 및 스냅샷 CRUD (Phase 3) ============

    def create_session(self) -> str:
        """시뮬레이션 세션 생성"""
        query = """
            INSERT INTO simulation_sessions (session_id, status, start_time)
            VALUES (gen_random_uuid(), 'RUNNING', CURRENT_TIMESTAMP)
            RETURNING session_id::text
        """

        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                session_id = cur.fetchone()[0]
            conn.commit()
            return session_id

    def update_session_status(self, session_id: str, status: str) -> None:
        """세션 상태 업데이트"""
        query = """
            UPDATE simulation_sessions
            SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE session_id = %s::uuid
        """

        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (status, session_id))
            conn.commit()

    def insert_performance_snapshot(self, session_id: str, timestamp: datetime,
                                   total_pnl: float, total_pnl_pct: float,
                                   win_count: int, lose_count: int, win_rate: float,
                                   max_drawdown: float) -> int:
        """성능 스냅샷 기록"""
        query = """
            INSERT INTO performance_snapshots
            (session_id, timestamp, total_pnl, total_pnl_pct, win_count, lose_count, win_rate, max_drawdown)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """

        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (session_id, timestamp, total_pnl, total_pnl_pct,
                                  win_count, lose_count, win_rate, max_drawdown))
                snapshot_id = cur.fetchone()[0]
            conn.commit()
            return snapshot_id

    # ============ 데이터 수집 상태 CRUD ============

    def update_collection_status(self, symbol: str, timeframe: str,
                                last_timestamp: datetime, status: str,
                                error_msg: str = None) -> None:
        """데이터 수집 상태 업데이트"""
        query = """
            INSERT INTO market_data_collection_status
            (symbol, timeframe, last_candle_timestamp, last_collected_at, status, error_count, last_error_message)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, 0, %s)
            ON CONFLICT (symbol, timeframe) DO UPDATE
            SET last_candle_timestamp = EXCLUDED.last_candle_timestamp,
                last_collected_at = CURRENT_TIMESTAMP,
                status = EXCLUDED.status,
                error_count = CASE WHEN EXCLUDED.status = 'ERROR'
                              THEN market_data_collection_status.error_count + 1
                              ELSE 0 END,
                last_error_message = EXCLUDED.last_error_message
        """

        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (symbol, timeframe, last_timestamp, status, error_msg))
            conn.commit()

    def get_collection_status(self, symbol: str, timeframe: str) -> Optional[dict]:
        """데이터 수집 상태 조회"""
        query = """
            SELECT symbol, timeframe, last_candle_timestamp, status, error_count
            FROM market_data_collection_status
            WHERE symbol = %s AND timeframe = %s
        """

        with self.get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (symbol, timeframe))
                return cur.fetchone()


# 전역 데이터베이스 인스턴스
_db_manager: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """전역 데이터베이스 인스턴스 반환"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        _db_manager.connect()
    return _db_manager


def init_db() -> None:
    """데이터베이스 초기화"""
    db = get_db()
    logger.info("Database initialized")


def close_db() -> None:
    """데이터베이스 연결 풀 종료"""
    global _db_manager
    if _db_manager:
        _db_manager.disconnect()
        _db_manager = None
