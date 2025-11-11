"""Tests for PostgreSQLResultStorage

Task 3.5.3: PostgreSQLResultStorage 완전 구현 테스트
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone

from backend.app.storage.result_storage import PostgreSQLResultStorage


@pytest.fixture
def sample_backtest_result():
    """Create sample backtest result"""
    return {
        'task_id': '550e8400-e29b-41d4-a716-446655440000',
        'strategy': 'volume_zone_breakout',
        'start_date': '2024-01-01',
        'end_date': '2024-01-31',
        'symbols': [
            {
                'symbol': 'BTC/USDT',
                'win_rate': 58.5,
                'avg_return': 2.15,
                'max_return': 5.0,
                'min_return': -3.5,
                'max_drawdown': 8.3,
                'avg_hold_bars': 24.5,
                'total_signals': 200,
                'winning_signals': 117,
                'losing_signals': 83,
                'total_pnl': 12500.0,
                'total_pnl_pct': 12.5,
                'signals': [
                    {
                        'timestamp': '2024-01-01T10:00:00Z',
                        'type': 'buy',
                        'entry_price': 42000.0,
                        'exit_price': 42840.0,
                        'quantity': 0.5,
                        'return_pct': 2.0,
                        'hold_bars': 20,
                        'fee_amount': 21.0,
                        'slippage_amount': 10.0,
                        'status': 'closed',
                    },
                ],
                'performance_curve': [
                    {
                        'timestamp': '2024-01-01T00:00:00Z',
                        'equity': 100000.0,
                        'drawdown': 0.0,
                        'cumulative_pnl': 0.0,
                        'cumulative_pnl_pct': 0.0,
                    },
                ],
            },
        ],
    }


@pytest.fixture
def mock_db_manager():
    """Create mock DatabaseManager"""
    mock = MagicMock()

    # Mock connection context manager
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=None)
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=None)

    mock_conn.cursor.return_value = mock_cursor
    mock.get_conn.return_value = mock_conn

    return mock


class TestPostgreSQLResultStorageInit:
    """Test PostgreSQLResultStorage initialization"""

    @patch('backend.app.storage.result_storage.DB_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.CONVERTERS_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.DatabaseManager')
    def test_init_with_default_url(self, mock_db_class):
        """Test initialization with default DATABASE_URL"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        storage = PostgreSQLResultStorage()

        assert storage.parquet_base_dir == 'backtests'
        assert storage.compression == 'snappy'
        mock_db.connect.assert_called_once()

    @patch('backend.app.storage.result_storage.DB_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.CONVERTERS_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.DatabaseManager')
    def test_init_with_custom_url(self, mock_db_class):
        """Test initialization with custom DATABASE_URL"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        custom_url = 'postgresql://user:pass@host:5432/db'

        storage = PostgreSQLResultStorage(database_url=custom_url)

        mock_db_class.assert_called_once_with(custom_url)

    @patch('backend.app.storage.result_storage.DB_AVAILABLE', False)
    def test_init_without_db(self):
        """Test initialization fails when DB not available"""
        with pytest.raises(RuntimeError, match="DatabaseManager not available"):
            PostgreSQLResultStorage()

    @patch('backend.app.storage.result_storage.DB_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.CONVERTERS_AVAILABLE', False)
    def test_init_without_converters(self):
        """Test initialization fails when converters not available"""
        with pytest.raises(RuntimeError, match="Converters module not available"):
            PostgreSQLResultStorage()


class TestPostgreSQLResultStorageSaveResult:
    """Test save_result method"""

    @patch('backend.app.storage.result_storage.DB_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.CONVERTERS_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.DatabaseManager')
    @patch('backend.app.storage.result_storage.json_to_parquet')
    def test_save_result_success(
        self,
        mock_json_to_parquet,
        mock_db_class,
        sample_backtest_result,
        mock_db_manager
    ):
        """Test successful result save"""
        mock_db_class.return_value = mock_db_manager

        # Mock json_to_parquet return value
        mock_json_to_parquet.return_value = {
            'symbol_summary': '/path/symbol_summary.parquet',
            'symbol_signals': '/path/symbol_signals.parquet',
            'performance_curve': '/path/performance_curve.parquet',
            'metadata': {
                'schema_version': '1.0',
                'compression': 'snappy',
                'parquet_files': {
                    'symbol_signals': {'row_count': 1}
                }
            },
            'total_size': 5000,
        }

        mock_cursor = mock_db_manager.get_conn().__enter__().cursor().__enter__()

        storage = PostgreSQLResultStorage()
        result = pytest.asyncio.run(storage.save_result(
            'test_id',
            sample_backtest_result
        ))

        assert result is True
        mock_json_to_parquet.assert_called_once()
        mock_cursor.execute.assert_called_once()

    @patch('backend.app.storage.result_storage.DB_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.CONVERTERS_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.DatabaseManager')
    @patch('backend.app.storage.result_storage.json_to_parquet')
    def test_save_result_failure(
        self,
        mock_json_to_parquet,
        mock_db_class,
        sample_backtest_result
    ):
        """Test save_result handles exceptions"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.get_conn.side_effect = Exception("DB error")

        storage = PostgreSQLResultStorage()
        result = pytest.asyncio.run(storage.save_result(
            'test_id',
            sample_backtest_result
        ))

        assert result is False


class TestPostgreSQLResultStorageGetResult:
    """Test get_result method"""

    @patch('backend.app.storage.result_storage.DB_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.CONVERTERS_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.DatabaseManager')
    @patch('backend.app.storage.result_storage.parquet_to_json')
    def test_get_result_success(
        self,
        mock_parquet_to_json,
        mock_db_class,
        sample_backtest_result,
        mock_db_manager
    ):
        """Test successful result retrieval"""
        mock_db_class.return_value = mock_db_manager

        # Mock database row
        mock_cursor = mock_db_manager.get_conn().__enter__().cursor().__enter__()
        mock_cursor.fetchone.return_value = (
            '550e8400-e29b-41d4-a716-446655440000',  # task_id
            'volume_zone_breakout',  # strategy
            '["BTC/USDT"]',  # symbols (JSON)
            datetime(2024, 1, 1),  # start_date
            datetime(2024, 1, 31),  # end_date
            'completed',  # status
            '/path/to/parquet',  # parquet_path
            5000,  # file_size
            1,  # record_count
            '{"schema_version": "1.0"}',  # metadata (JSON)
        )

        # Mock parquet_to_json
        mock_parquet_to_json.return_value = {
            'symbols': sample_backtest_result['symbols'],
        }

        storage = PostgreSQLResultStorage()
        result = pytest.asyncio.run(storage.get_result('550e8400-e29b-41d4-a716-446655440000'))

        assert result is not None
        assert result['task_id'] == '550e8400-e29b-41d4-a716-446655440000'
        assert result['strategy'] == 'volume_zone_breakout'
        assert result['status'] == 'completed'

    @patch('backend.app.storage.result_storage.DB_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.CONVERTERS_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.DatabaseManager')
    def test_get_result_not_found(self, mock_db_class, mock_db_manager):
        """Test get_result when result not found"""
        mock_db_class.return_value = mock_db_manager

        mock_cursor = mock_db_manager.get_conn().__enter__().cursor().__enter__()
        mock_cursor.fetchone.return_value = None

        storage = PostgreSQLResultStorage()
        result = pytest.asyncio.run(storage.get_result('nonexistent_id'))

        assert result is None


class TestPostgreSQLResultStorageCleanup:
    """Test cleanup_old_results method"""

    @patch('backend.app.storage.result_storage.DB_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.CONVERTERS_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.DatabaseManager')
    def test_cleanup_dry_run(self, mock_db_class, mock_db_manager):
        """Test cleanup in dry-run mode"""
        mock_db_class.return_value = mock_db_manager

        mock_cursor = mock_db_manager.get_conn().__enter__().cursor().__enter__()
        mock_cursor.fetchall.return_value = [
            ('task1', '/path1'),
            ('task2', '/path2'),
        ]

        storage = PostgreSQLResultStorage()
        count = pytest.asyncio.run(storage.cleanup_old_results(days=7, dry_run=True))

        assert count == 2

    @patch('backend.app.storage.result_storage.DB_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.CONVERTERS_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.DatabaseManager')
    def test_cleanup_actual_deletion(self, mock_db_class, mock_db_manager):
        """Test actual cleanup (non-dry-run)"""
        mock_db_class.return_value = mock_db_manager

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test parquet directory
            test_dir = Path(tmpdir) / 'task1'
            test_dir.mkdir()
            (test_dir / 'test.parquet').touch()

            mock_cursor = mock_db_manager.get_conn().__enter__().cursor().__enter__()
            mock_cursor.fetchall.return_value = [
                ('task1', tmpdir),
            ]

            storage = PostgreSQLResultStorage()
            count = pytest.asyncio.run(storage.cleanup_old_results(days=7, dry_run=False))

            # Should have deleted 1 result
            assert count == 1


class TestPostgreSQLResultStorageListResults:
    """Test list_results method"""

    @patch('backend.app.storage.result_storage.DB_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.CONVERTERS_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.DatabaseManager')
    def test_list_results_success(self, mock_db_class, mock_db_manager):
        """Test successful result listing"""
        mock_db_class.return_value = mock_db_manager

        mock_cursor = mock_db_manager.get_conn().__enter__().cursor().__enter__()
        mock_cursor.fetchall.return_value = [
            (
                '550e8400-e29b-41d4-a716-446655440000',
                'volume_zone_breakout',
                'completed',
                datetime(2024, 1, 1),
                datetime(2024, 1, 2),
                5000,
                100,
            ),
        ]

        storage = PostgreSQLResultStorage()
        results = pytest.asyncio.run(storage.list_results(limit=10))

        assert len(results) == 1
        assert results[0]['task_id'] == '550e8400-e29b-41d4-a716-446655440000'
        assert results[0]['strategy'] == 'volume_zone_breakout'

    @patch('backend.app.storage.result_storage.DB_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.CONVERTERS_AVAILABLE', True)
    @patch('backend.app.storage.result_storage.DatabaseManager')
    def test_list_results_with_filters(self, mock_db_class, mock_db_manager):
        """Test listing with filters"""
        mock_db_class.return_value = mock_db_manager

        mock_cursor = mock_db_manager.get_conn().__enter__().cursor().__enter__()
        mock_cursor.fetchall.return_value = []

        storage = PostgreSQLResultStorage()
        results = pytest.asyncio.run(storage.list_results(
            limit=10,
            offset=0,
            strategy='volume_zone_breakout',
            status='completed'
        ))

        assert len(results) == 0
        # Verify filters were applied in query
        call_args = mock_cursor.execute.call_args
        assert 'volume_zone_breakout' in call_args[0]


# Integration test (requires actual PostgreSQL)
@pytest.mark.skip(reason="Requires actual PostgreSQL instance")
class TestPostgreSQLResultStorageIntegration:
    """Integration tests with real PostgreSQL"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test database"""
        # Create connection to test database
        # Run migrations
        pass

    def test_full_workflow(self, sample_backtest_result):
        """Test full save/get/list/cleanup workflow"""
        storage = PostgreSQLResultStorage(
            database_url='postgresql://test:test@localhost:5432/test_coin_db'
        )

        # Save
        saved = pytest.asyncio.run(storage.save_result(
            'test_id',
            sample_backtest_result
        ))
        assert saved is True

        # Get
        retrieved = pytest.asyncio.run(storage.get_result('test_id'))
        assert retrieved is not None
        assert retrieved['strategy'] == sample_backtest_result['strategy']

        # List
        results = pytest.asyncio.run(storage.list_results(limit=10))
        assert len(results) > 0

        # Cleanup
        cleaned = pytest.asyncio.run(storage.cleanup_old_results(days=0))
        assert cleaned >= 1
