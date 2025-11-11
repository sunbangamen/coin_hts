"""Integration tests for Dual-write mode via ResultManager

Task 3.5: 결과 저장 개선 - Dual-write 기능 통합 테스트

Tests for the complete Dual-write workflow:
1. JSON file + PostgreSQL/Parquet dual storage
2. Mode switching via environment variable
3. Validation and error handling
4. Fallback behavior in case of storage failures
"""

import pytest
import json
import tempfile
import asyncio
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from backend.app.result_manager import ResultManager
from backend.app.storage.result_storage import SQLiteResultStorage


@pytest.fixture
def backtest_result():
    """Sample complete backtest result for testing"""
    return {
        'task_id': 'test-task-001',
        'strategy': 'volume_zone_breakout',
        'symbols': [
            {
                'symbol': 'BTC/USDT',
                'win_rate': 58.5,
                'avg_return': 2.15,
                'max_return': 5.0,
                'min_return': -3.5,
                'max_drawdown': 8.3,
                'total_signals': 100,
                'signals': [
                    {
                        'timestamp': '2024-01-01T10:00:00Z',
                        'type': 'buy',
                        'entry_price': 42000.0,
                        'exit_price': 42840.0,
                        'quantity': 0.5,
                        'return_pct': 2.0,
                        'status': 'closed',
                    },
                ],
                'performance_curve': [
                    {
                        'timestamp': '2024-01-01T00:00:00Z',
                        'equity': 100000.0,
                        'drawdown': 0.0,
                        'cumulative_pnl': 0.0,
                    },
                ],
            },
        ],
        'start_date': '2024-01-01',
        'end_date': '2024-01-31',
        'status': 'completed',
    }


@pytest.fixture
def tmp_env(tmp_path):
    """Create temporary directories for testing"""
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "results").mkdir()

    db_path = tmp_path / "test_results.db"
    storage = SQLiteResultStorage(str(db_path))

    return {
        'data_root': str(data_root),
        'storage': storage,
        'db_path': str(db_path),
        'tmp_path': tmp_path,
    }


class TestDualWriteJsonOnly:
    """Test json-only mode (no storage layer)"""

    def test_json_only_mode_saves_json_file(self, tmp_env, backtest_result):
        """Test that json-only mode saves JSON file"""
        manager = ResultManager(
            storage=None,
            data_root=tmp_env['data_root'],
            storage_mode='json-only'
        )

        now = datetime.utcnow()
        manifest_file = manager.save_manifest_file(
            data_root=tmp_env['data_root'],
            task_id='task-001',
            strategy='test_strategy',
            params={'param1': 'value1'},
            symbols=['BTC/USDT', 'ETH/USDT'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            timeframe='1h',
            result_files=[],
            started_at=now.isoformat() + 'Z',
            finished_at=(now + timedelta(minutes=5)).isoformat() + 'Z',
            total_signals=100,
            symbols_processed=2,
            symbols_failed=0,
        )

        # Verify manifest file was created
        assert Path(manifest_file).exists()

        # Verify content
        with open(manifest_file) as f:
            manifest = json.load(f)
        assert manifest['task_id'] == 'task-001'
        assert manifest['strategy'] == 'test_strategy'

        print(f"✓ json-only mode: manifest file saved at {manifest_file}")

    def test_json_only_mode_no_storage_call(self, tmp_env, backtest_result):
        """Test that json-only mode doesn't call storage layer"""
        manager = ResultManager(
            storage=None,
            data_root=tmp_env['data_root'],
            storage_mode='json-only'
        )

        now = datetime.utcnow()
        # Should not raise any error even without storage
        manifest_file = manager.save_manifest_file(
            data_root=tmp_env['data_root'],
            task_id='task-002',
            strategy='test_strategy',
            params={},
            symbols=['BTC/USDT'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            timeframe='1h',
            result_files=[],
            started_at=now.isoformat() + 'Z',
            finished_at=(now + timedelta(minutes=1)).isoformat() + 'Z',
            total_signals=50,
            symbols_processed=1,
            symbols_failed=0,
        )

        assert Path(manifest_file).exists()
        print(f"✓ json-only mode: no storage layer call made")


class TestDualWriteMode:
    """Test dual-write mode (JSON + PostgreSQL/Parquet)"""

    def test_dual_write_saves_to_both_json_and_storage(self, tmp_env, backtest_result):
        """Test that dual-write mode saves to both JSON and storage"""
        manager = ResultManager(
            storage=tmp_env['storage'],
            data_root=tmp_env['data_root'],
            storage_mode='dual-write'
        )

        now = datetime.utcnow()
        manifest_file = manager.save_manifest_file(
            data_root=tmp_env['data_root'],
            task_id='task-dual-001',
            strategy='dual_strategy',
            params={'param1': 'value1'},
            symbols=['BTC/USDT', 'ETH/USDT'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            timeframe='1h',
            result_files=[],
            started_at=now.isoformat() + 'Z',
            finished_at=(now + timedelta(minutes=5)).isoformat() + 'Z',
            total_signals=100,
            symbols_processed=2,
            symbols_failed=0,
            backtest_result=backtest_result,
        )

        # Verify manifest file exists
        assert Path(manifest_file).exists()

        # Verify storage has the data
        result = asyncio.run(tmp_env['storage'].get_result('task-dual-001'))
        assert result is not None
        assert result['strategy'] == 'dual_strategy'

        print(f"✓ dual-write mode: data saved to both JSON and storage")

    def test_dual_write_with_validation_failure_continues(self, tmp_env):
        """Test that dual-write mode continues if validation fails"""
        manager = ResultManager(
            storage=tmp_env['storage'],
            data_root=tmp_env['data_root'],
            storage_mode='dual-write'
        )

        now = datetime.utcnow()
        # backtest_result with invalid structure
        invalid_result = {
            'task_id': 'task-invalid',
            'symbols': 12345,  # Invalid: should be list, not int
        }

        # In dual-write mode, should log warning but not raise
        manifest_file = manager.save_manifest_file(
            data_root=tmp_env['data_root'],
            task_id='task-invalid-001',
            strategy='invalid_strategy',
            params={},
            symbols=['BTC/USDT'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            timeframe='1h',
            result_files=[],
            started_at=now.isoformat() + 'Z',
            finished_at=(now + timedelta(minutes=1)).isoformat() + 'Z',
            total_signals=50,
            symbols_processed=1,
            symbols_failed=0,
            backtest_result=invalid_result,
        )

        # JSON should still be saved
        assert Path(manifest_file).exists()
        print(f"✓ dual-write mode: validation failure handled gracefully")

    def test_dual_write_with_valid_backtest_result(self, tmp_env, backtest_result):
        """Test dual-write with complete backtest result"""
        manager = ResultManager(
            storage=tmp_env['storage'],
            data_root=tmp_env['data_root'],
            storage_mode='dual-write'
        )

        now = datetime.utcnow()
        manifest_file = manager.save_manifest_file(
            data_root=tmp_env['data_root'],
            task_id='task-complete-001',
            strategy='complete_strategy',
            params={'param1': 'value1'},
            symbols=['BTC/USDT'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            timeframe='1h',
            result_files=[],
            started_at=now.isoformat() + 'Z',
            finished_at=(now + timedelta(minutes=5)).isoformat() + 'Z',
            total_signals=100,
            symbols_processed=1,
            symbols_failed=0,
            backtest_result=backtest_result,
        )

        # Verify storage has complete data
        result = asyncio.run(tmp_env['storage'].get_result('task-complete-001'))
        assert result is not None
        assert result['task_id'] == 'test-task-001'
        assert result['strategy'] == 'volume_zone_breakout'
        assert len(result['symbols']) == 1
        assert result['symbols'][0]['symbol'] == 'BTC/USDT'

        print(f"✓ dual-write mode: complete backtest result stored correctly")


class TestPostgresOnlyMode:
    """Test postgres-only mode (storage layer required)"""

    def test_postgres_only_saves_to_storage_only(self, tmp_env, backtest_result):
        """Test that postgres-only mode saves to storage only"""
        manager = ResultManager(
            storage=tmp_env['storage'],
            data_root=tmp_env['data_root'],
            storage_mode='postgres-only'
        )

        now = datetime.utcnow()
        manifest_file = manager.save_manifest_file(
            data_root=tmp_env['data_root'],
            task_id='task-postgres-001',
            strategy='postgres_strategy',
            params={},
            symbols=['BTC/USDT'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            timeframe='1h',
            result_files=[],
            started_at=now.isoformat() + 'Z',
            finished_at=(now + timedelta(minutes=1)).isoformat() + 'Z',
            total_signals=100,
            symbols_processed=1,
            symbols_failed=0,
            backtest_result=backtest_result,
        )

        # Verify storage has data
        result = asyncio.run(tmp_env['storage'].get_result('task-postgres-001'))
        assert result is not None

        print(f"✓ postgres-only mode: data saved to storage")

    def test_postgres_only_raises_on_storage_failure(self, tmp_env):
        """Test that postgres-only mode raises on storage failure"""
        # Create a mock storage that fails
        mock_storage = AsyncMock()
        mock_storage.save_result.side_effect = Exception("Storage connection failed")

        manager = ResultManager(
            storage=mock_storage,
            data_root=tmp_env['data_root'],
            storage_mode='postgres-only'
        )

        now = datetime.utcnow()
        # Should raise exception
        with pytest.raises(Exception):
            manager.save_manifest_file(
                data_root=tmp_env['data_root'],
                task_id='task-fail-001',
                strategy='fail_strategy',
                params={},
                symbols=['BTC/USDT'],
                start_date='2024-01-01',
                end_date='2024-01-31',
                timeframe='1h',
                result_files=[],
                started_at=now.isoformat() + 'Z',
                finished_at=(now + timedelta(minutes=1)).isoformat() + 'Z',
                total_signals=100,
                symbols_processed=1,
                symbols_failed=0,
            )

        print(f"✓ postgres-only mode: raises exception on storage failure")


class TestDataValidation:
    """Test data validation in dual-write mode"""

    def test_validate_symbols_field(self, tmp_env, backtest_result):
        """Test validation of symbols field"""
        manager = ResultManager(
            storage=tmp_env['storage'],
            data_root=tmp_env['data_root'],
            storage_mode='dual-write'
        )

        # backtest_result with proper symbols format
        valid_result = backtest_result.copy()
        valid_result['symbols'] = [
            {'symbol': 'BTC/USDT', 'win_rate': 50.0},
            {'symbol': 'ETH/USDT', 'win_rate': 45.0},
        ]

        now = datetime.utcnow()
        manifest_file = manager.save_manifest_file(
            data_root=tmp_env['data_root'],
            task_id='task-validate-symbols',
            strategy='validate_strategy',
            params={},
            symbols=['BTC/USDT', 'ETH/USDT'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            timeframe='1h',
            result_files=[],
            started_at=now.isoformat() + 'Z',
            finished_at=(now + timedelta(minutes=1)).isoformat() + 'Z',
            total_signals=100,
            symbols_processed=2,
            symbols_failed=0,
            backtest_result=valid_result,
        )

        result = asyncio.run(tmp_env['storage'].get_result('task-validate-symbols'))
        assert result is not None
        assert len(result['symbols']) == 2

        print(f"✓ Data validation: symbols field validated correctly")

    def test_validate_strategy_field(self, tmp_env, backtest_result):
        """Test validation of strategy field"""
        manager = ResultManager(
            storage=tmp_env['storage'],
            data_root=tmp_env['data_root'],
            storage_mode='dual-write'
        )

        valid_result = backtest_result.copy()
        valid_result['strategy'] = 'valid_strategy_name'

        now = datetime.utcnow()
        manifest_file = manager.save_manifest_file(
            data_root=tmp_env['data_root'],
            task_id='task-validate-strategy',
            strategy='validate_strategy',
            params={},
            symbols=['BTC/USDT'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            timeframe='1h',
            result_files=[],
            started_at=now.isoformat() + 'Z',
            finished_at=(now + timedelta(minutes=1)).isoformat() + 'Z',
            total_signals=100,
            symbols_processed=1,
            symbols_failed=0,
            backtest_result=valid_result,
        )

        result = asyncio.run(tmp_env['storage'].get_result('task-validate-strategy'))
        assert result is not None
        assert result['strategy'] == 'valid_strategy_name'

        print(f"✓ Data validation: strategy field validated correctly")


class TestModeTransition:
    """Test mode transitions and compatibility"""

    def test_transition_from_json_only_to_dual_write(self, tmp_env, backtest_result):
        """Test transitioning from json-only to dual-write mode"""
        # First, save in json-only mode
        manager1 = ResultManager(
            storage=None,
            data_root=tmp_env['data_root'],
            storage_mode='json-only'
        )

        now = datetime.utcnow()
        manifest_file1 = manager1.save_manifest_file(
            data_root=tmp_env['data_root'],
            task_id='task-transition-001',
            strategy='transition_strategy',
            params={},
            symbols=['BTC/USDT'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            timeframe='1h',
            result_files=[],
            started_at=now.isoformat() + 'Z',
            finished_at=(now + timedelta(minutes=1)).isoformat() + 'Z',
            total_signals=100,
            symbols_processed=1,
            symbols_failed=0,
        )

        # Then switch to dual-write mode
        manager2 = ResultManager(
            storage=tmp_env['storage'],
            data_root=tmp_env['data_root'],
            storage_mode='dual-write'
        )

        manifest_file2 = manager2.save_manifest_file(
            data_root=tmp_env['data_root'],
            task_id='task-transition-002',
            strategy='transition_strategy',
            params={},
            symbols=['BTC/USDT'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            timeframe='1h',
            result_files=[],
            started_at=now.isoformat() + 'Z',
            finished_at=(now + timedelta(minutes=1)).isoformat() + 'Z',
            total_signals=100,
            symbols_processed=1,
            symbols_failed=0,
            backtest_result=backtest_result,
        )

        # Verify both files exist and storage has new data
        assert Path(manifest_file1).exists()
        assert Path(manifest_file2).exists()

        result = asyncio.run(tmp_env['storage'].get_result('task-transition-002'))
        assert result is not None

        print(f"✓ Mode transition: json-only → dual-write works correctly")

    def test_transition_from_dual_write_to_postgres_only(self, tmp_env, backtest_result):
        """Test transitioning from dual-write to postgres-only mode"""
        # First in dual-write mode
        manager1 = ResultManager(
            storage=tmp_env['storage'],
            data_root=tmp_env['data_root'],
            storage_mode='dual-write'
        )

        now = datetime.utcnow()
        manifest_file1 = manager1.save_manifest_file(
            data_root=tmp_env['data_root'],
            task_id='task-to-pg-001',
            strategy='to_postgres',
            params={},
            symbols=['BTC/USDT'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            timeframe='1h',
            result_files=[],
            started_at=now.isoformat() + 'Z',
            finished_at=(now + timedelta(minutes=1)).isoformat() + 'Z',
            total_signals=100,
            symbols_processed=1,
            symbols_failed=0,
            backtest_result=backtest_result,
        )

        # Then postgres-only mode
        manager2 = ResultManager(
            storage=tmp_env['storage'],
            data_root=tmp_env['data_root'],
            storage_mode='postgres-only'
        )

        manifest_file2 = manager2.save_manifest_file(
            data_root=tmp_env['data_root'],
            task_id='task-to-pg-002',
            strategy='to_postgres',
            params={},
            symbols=['BTC/USDT'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            timeframe='1h',
            result_files=[],
            started_at=now.isoformat() + 'Z',
            finished_at=(now + timedelta(minutes=1)).isoformat() + 'Z',
            total_signals=100,
            symbols_processed=1,
            symbols_failed=0,
            backtest_result=backtest_result,
        )

        # Both should be in storage
        result1 = asyncio.run(tmp_env['storage'].get_result('task-to-pg-001'))
        result2 = asyncio.run(tmp_env['storage'].get_result('task-to-pg-002'))

        assert result1 is not None
        assert result2 is not None

        print(f"✓ Mode transition: dual-write → postgres-only works correctly")
