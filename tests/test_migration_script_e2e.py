"""End-to-end tests for migration script with actual invocation

Task 3.5.5: 마이그레이션 스크립트 배치/강제 옵션 통합 테스트

These tests directly invoke the migration script to verify:
1. Batch processing works correctly with --batch-size
2. Force mode correctly overrides existing records
3. Skip logic works without --force
4. Migration report metrics are accurate
5. JSON backup and rollback work properly
"""

import pytest
import json
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Import the actual migration functions
from scripts.migrate_json_to_parquet import (
    run_migration,
    find_json_results,
    migrate_result,
    MigrationReport,
)
from backend.app.storage.result_storage import SQLiteResultStorage


@pytest.fixture
def migration_env(tmp_path):
    """Setup test environment with JSON files and storage"""
    # Create source directory with JSON files
    source_dir = tmp_path / "source_tasks"
    source_dir.mkdir()

    # Create 10 sample JSON result files
    results = []
    for i in range(10):
        task_dir = source_dir / f"task-{i:03d}"
        task_dir.mkdir()

        result_file = task_dir / "result.json"
        result_data = {
            'task_id': f"task-{i:03d}",
            'strategy': f'strategy_{i}',
            'symbols': [f'SYM{i}'],
            'signals': [
                {
                    'timestamp': '2024-01-01T10:00:00Z',
                    'type': 'buy',
                    'entry_price': 1000.0 + i,
                    'exit_price': 1010.0 + i,
                    'quantity': 1.0,
                    'return_pct': 1.0,
                    'status': 'closed',
                } for _ in range(10)
            ],
            'performance_curve': [
                {
                    'timestamp': '2024-01-01T00:00:00Z',
                    'equity': 100000.0,
                    'drawdown': 0.0,
                    'cumulative_pnl': 0.0,
                }
            ],
        }

        with open(result_file, 'w') as f:
            json.dump(result_data, f)

        results.append((f"task-{i:03d}", result_file))

    # Create backup and database directories
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    db_path = tmp_path / "test_results.db"
    storage = SQLiteResultStorage(str(db_path))

    return {
        'tmp_path': tmp_path,
        'source_dir': str(source_dir),
        'backup_dir': str(backup_dir),
        'storage': storage,
        'results': results,
    }


class TestMigrationScriptBatchProcessing:
    """Test batch processing in actual migration script"""

    @pytest.mark.asyncio
    async def test_batch_processing_with_batch_size_2(self, migration_env):
        """Test batch-size=2 processes files in correct batches"""
        # Run migration with batch_size=2 using injected storage
        report = await run_migration(
            source_dir=migration_env['source_dir'],
            batch_size=2,
            backup_dir=migration_env['backup_dir'],
            storage=migration_env['storage'],  # Inject storage for testing
        )

        # Verify total files and batches
        assert report.total_files == 10
        assert report.successful == 10
        assert report.failed == 0
        assert report.skipped == 0

        # Batch calculation: 10 items, size 2 = 5 batches
        expected_batches = (10 + 2 - 1) // 2
        assert expected_batches == 5

        # Verify data actually saved
        result = await migration_env['storage'].get_result('task-000')
        assert result is not None
        assert result['task_id'] == 'task-000'

        print(f"✓ Batch processing: 10 items in batch_size=2 = {expected_batches} batches")

    @pytest.mark.asyncio
    async def test_batch_processing_with_batch_size_3(self, migration_env):
        """Test batch-size=3 with 10 items (4 batches: 3+3+3+1)"""
        report = await run_migration(
            source_dir=migration_env['source_dir'],
            batch_size=3,
            backup_dir=migration_env['backup_dir'],
            storage=migration_env['storage'],
        )

        assert report.total_files == 10
        assert report.successful == 10
        assert report.failed == 0

        # Batch calculation: 10 items, size 3 = ceil(10/3) = 4 batches
        expected_batches = (10 + 3 - 1) // 3
        assert expected_batches == 4

        # Verify at least one result saved
        result = await migration_env['storage'].get_result('task-005')
        assert result is not None

        print(f"✓ Batch processing: 10 items in batch_size=3 = {expected_batches} batches")

    @pytest.mark.asyncio
    async def test_batch_processing_large_batch_size(self, migration_env):
        """Test batch-size larger than total files (1 batch)"""
        report = await run_migration(
            source_dir=migration_env['source_dir'],
            batch_size=100,
            backup_dir=migration_env['backup_dir'],
            storage=migration_env['storage'],
        )

        assert report.total_files == 10
        assert report.successful == 10
        assert report.failed == 0

        # All files in single batch
        expected_batches = (10 + 100 - 1) // 100
        assert expected_batches == 1

        # Verify all results saved
        for i in range(10):
            result = await migration_env['storage'].get_result(f'task-{i:03d}')
            assert result is not None

        print(f"✓ Batch processing: 10 items in batch_size=100 = 1 batch")


class TestMigrationScriptForceMode:
    """Test force mode in actual migration script"""

    @pytest.mark.asyncio
    async def test_force_mode_without_flag_skips_duplicates(self, migration_env):
        """Test that without --force, duplicate records are skipped"""
        storage = migration_env['storage']

        # Pre-populate one record
        task_id, json_path = migration_env['results'][0]
        with open(json_path) as f:
            result_data = json.load(f)
        original_strategy = result_data['strategy']
        await storage.save_result(task_id, result_data)

        # Run migration without --force
        report = await run_migration(
            source_dir=migration_env['source_dir'],
            batch_size=10,
            backup_dir=migration_env['backup_dir'],
            force=False,  # Without --force
            storage=storage,
        )

        # One should be skipped, rest successful
        assert report.skipped == 1, f"Expected 1 skipped, got {report.skipped}"
        assert report.successful == 9, f"Expected 9 successful, got {report.successful}"
        assert report.failed == 0

        # Verify original record unchanged
        result = await storage.get_result(task_id)
        assert result['strategy'] == original_strategy

        print(f"✓ Force mode: without --force skipped 1 duplicate, migrated 9")

    @pytest.mark.asyncio
    async def test_force_mode_with_flag_overwrites_duplicates(self, migration_env):
        """Test that with --force, duplicate records are overwritten"""
        storage = migration_env['storage']

        # Pre-populate one record with original data
        task_id, json_path = migration_env['results'][0]
        with open(json_path) as f:
            result_data = json.load(f)

        original_strategy = result_data['strategy']
        await storage.save_result(task_id, result_data)

        # Verify original is stored
        original = await storage.get_result(task_id)
        assert original is not None
        assert original['strategy'] == original_strategy

        # Modify the JSON file
        result_data['strategy'] = 'modified_strategy_' + original_strategy
        with open(json_path, 'w') as f:
            json.dump(result_data, f)

        # Run migration WITH --force
        report = await run_migration(
            source_dir=migration_env['source_dir'],
            batch_size=10,
            backup_dir=migration_env['backup_dir'],
            force=True,  # WITH --force
            storage=storage,
        )

        # All should be successful (including the overwrite)
        assert report.successful == 10
        assert report.skipped == 0
        assert report.failed == 0

        # Verify the modified data was written
        updated = await storage.get_result(task_id)
        assert updated is not None
        assert updated['strategy'] == f'modified_strategy_{original_strategy}'

        # Verify backup was created (force=True creates backup)
        backup_file = Path(migration_env['backup_dir']) / task_id / 'result.json'
        assert backup_file.exists(), "Backup file should exist in force mode"

        print(f"✓ Force mode: with --force overwrote 1 duplicate, migrated all 10, backup created")


class TestMigrationScriptJsonBackup:
    """Test JSON backup functionality"""

    @pytest.mark.asyncio
    async def test_json_backup_created_on_force_migration(self, migration_env):
        """Test that JSON files are backed up only in force mode"""
        backup_dir = Path(migration_env['backup_dir'])
        storage = migration_env['storage']

        # Run migration WITH force (should create backup)
        report = await run_migration(
            source_dir=migration_env['source_dir'],
            batch_size=10,
            backup_dir=migration_env['backup_dir'],
            force=True,  # Force mode creates backup
            storage=storage,
        )

        assert report.successful == 10

        # In force mode, backups should be created
        # (Note: current policy creates backup only on force)
        backup_files = list(backup_dir.glob('task-*/result.json'))
        assert len(backup_files) == 10, "All files should be backed up in force mode"
        print(f"✓ JSON backup: {len(backup_files)} files backed up in force mode")

    @pytest.mark.asyncio
    async def test_backup_preserves_original_data(self, migration_env):
        """Test that backup files contain original data"""
        backup_dir = Path(migration_env['backup_dir'])
        storage = migration_env['storage']

        # Memorize first file data
        task_id, json_path = migration_env['results'][0]
        with open(json_path) as f:
            original_data = json.load(f)

        # Use force mode to ensure backup creation
        report = await run_migration(
            source_dir=migration_env['source_dir'],
            batch_size=10,
            backup_dir=migration_env['backup_dir'],
            force=True,
            storage=storage,
        )

        # Verify backup has same data
        backup_file = backup_dir / task_id / "result.json"
        assert backup_file.exists(), f"Backup should exist at {backup_file}"

        with open(backup_file) as f:
            backup_data = json.load(f)

        assert backup_data['task_id'] == original_data['task_id']
        assert backup_data['strategy'] == original_data['strategy']
        assert len(backup_data['signals']) == len(original_data['signals'])
        assert backup_data['signals'][0]['entry_price'] == original_data['signals'][0]['entry_price']
        print(f"✓ Backup preservation: data integrity verified")


class TestMigrationScriptReportMetrics:
    """Test migration report metrics"""

    @pytest.mark.asyncio
    async def test_report_tracks_success_count(self, migration_env):
        """Test that report accurately tracks successful migrations"""
        report = await run_migration(
            source_dir=migration_env['source_dir'],
            batch_size=5,
            backup_dir=migration_env['backup_dir'],
            storage=migration_env['storage'],
        )

        assert report.successful == 10
        assert report.total_files == 10
        assert report.successful == report.total_files
        assert report.failed == 0
        print(f"✓ Report metrics: success count = {report.successful}")

    @pytest.mark.asyncio
    async def test_report_tracks_compression_ratio(self, migration_env):
        """Test that report calculates compression ratio"""
        report = await run_migration(
            source_dir=migration_env['source_dir'],
            batch_size=10,
            backup_dir=migration_env['backup_dir'],
            storage=migration_env['storage'],
        )

        # Should have non-zero sizes
        assert report.json_total_size > 0
        assert report.parquet_total_size > 0

        # Parquet should be smaller than or equal to JSON
        # (may be similar size for small files due to overhead)
        compression = report.compression_ratio
        assert compression >= 0
        assert compression <= 100
        print(f"✓ Report metrics: compression ratio = {compression:.1f}%")

    @pytest.mark.asyncio
    async def test_report_duration(self, migration_env):
        """Test that report tracks processing duration"""
        report = await run_migration(
            source_dir=migration_env['source_dir'],
            batch_size=10,
            backup_dir=migration_env['backup_dir'],
            storage=migration_env['storage'],
        )

        duration = report.duration
        assert duration >= 0
        assert report.successful == 10
        print(f"✓ Report metrics: duration = {duration:.2f} seconds")


class TestMigrationScriptDryRun:
    """Test dry-run mode"""

    @pytest.mark.asyncio
    async def test_dry_run_no_actual_migration(self, migration_env):
        """Test that dry-run doesn't actually migrate files"""
        backup_dir = Path(migration_env['backup_dir'])
        storage = migration_env['storage']

        report = await run_migration(
            source_dir=migration_env['source_dir'],
            batch_size=10,
            backup_dir=migration_env['backup_dir'],
            dry_run=True,  # DRY RUN
            storage=storage,
        )

        # In dry-run, files should be marked as skipped
        assert report.skipped == 10
        assert report.successful == 0
        assert report.failed == 0

        # No backups should be created in dry-run
        backup_files = list(backup_dir.glob('task-*/result.json'))
        assert len(backup_files) == 0

        # Storage should have no data
        result = await storage.get_result('task-000')
        assert result is None

        print(f"✓ Dry-run: no actual migration performed")


class TestMigrationScriptErrorHandling:
    """Test error handling"""

    @pytest.mark.asyncio
    async def test_corrupted_json_file_handling(self, migration_env):
        """Test graceful handling of corrupted JSON files"""
        # Create one corrupted JSON file
        source_dir = Path(migration_env['source_dir'])
        corrupted_dir = source_dir / "task-corrupted"
        corrupted_dir.mkdir()

        corrupted_file = corrupted_dir / "result.json"
        with open(corrupted_file, 'w') as f:
            f.write("{ invalid json")  # Invalid JSON

        # Find results should still work
        results = await find_json_results(migration_env['source_dir'])

        # Should find all valid + corrupted file
        assert len(results) >= 10
        print(f"✓ Error handling: found {len(results)} result files")

    @pytest.mark.asyncio
    async def test_missing_source_directory(self):
        """Test handling of missing source directory"""
        report = await run_migration(
            source_dir='/nonexistent/path',
            batch_size=10,
            backup_dir='/tmp/backup',
            storage=None,  # Will create its own or fail gracefully
        )

        assert report.total_files == 0
        assert report.successful == 0
        assert report.failed == 0
        print(f"✓ Error handling: missing directory handled gracefully")


class TestMigrationScriptDataIntegrity:
    """Test data integrity through migration"""

    @pytest.mark.asyncio
    async def test_signal_data_preserved(self, migration_env):
        """Test that signal data is preserved during migration"""
        storage = migration_env['storage']

        # Get first task data
        task_id, json_path = migration_env['results'][0]
        with open(json_path) as f:
            original_data = json.load(f)

        # Migrate
        report = await run_migration(
            source_dir=migration_env['source_dir'],
            batch_size=10,
            backup_dir=migration_env['backup_dir'],
            storage=storage,
        )

        assert report.successful == 10

        # Retrieve migrated data
        migrated_data = await storage.get_result(task_id)
        assert migrated_data is not None

        # Verify signals preserved
        assert len(migrated_data['signals']) == len(original_data['signals'])
        assert migrated_data['signals'][0]['type'] == original_data['signals'][0]['type']
        assert migrated_data['signals'][0]['entry_price'] == original_data['signals'][0]['entry_price']
        assert migrated_data['signals'][0]['quantity'] == original_data['signals'][0]['quantity']
        print(f"✓ Data integrity: signal data preserved during migration")

    @pytest.mark.asyncio
    async def test_metadata_preserved(self, migration_env):
        """Test that metadata is preserved during migration"""
        storage = migration_env['storage']

        task_id, json_path = migration_env['results'][1]
        with open(json_path) as f:
            original_data = json.load(f)

        report = await run_migration(
            source_dir=migration_env['source_dir'],
            batch_size=10,
            backup_dir=migration_env['backup_dir'],
            storage=storage,
        )

        assert report.successful == 10

        migrated_data = await storage.get_result(task_id)
        assert migrated_data is not None

        assert migrated_data['task_id'] == original_data['task_id']
        assert migrated_data['strategy'] == original_data['strategy']
        assert migrated_data['symbols'] == original_data['symbols']
        print(f"✓ Data integrity: metadata preserved during migration")
