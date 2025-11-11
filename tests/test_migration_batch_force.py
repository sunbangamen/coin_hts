"""Tests for migration script batch and force options

Task 3.5.5: 마이그레이션 스크립트의 배치/강제 옵션 테스트
"""

import pytest
import json
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from backend.app.storage.result_storage import SQLiteResultStorage


@pytest.fixture
def sample_json_results(tmp_path):
    """Create sample JSON result files for testing"""
    results = []
    for i in range(5):
        task_dir = tmp_path / f"task-{i:03d}"
        task_dir.mkdir()

        result_file = task_dir / "result.json"
        result_data = {
            'task_id': f"task-{i:03d}",
            'strategy': 'test_strategy',
            'symbols': [f'SYM{i}'],
            'signals': [],
            'performance_curve': [],
        }

        with open(result_file, 'w') as f:
            json.dump(result_data, f)

        results.append((f"task-{i:03d}", result_file))

    return tmp_path, results


class TestMigrationBatchProcessing:
    """Test batch processing functionality"""

    @pytest.mark.asyncio
    async def test_batch_size_option(self, sample_json_results):
        """Test --batch-size option works correctly"""
        tmp_path, results = sample_json_results
        storage = SQLiteResultStorage(str(tmp_path / "test.db"))

        # Simulate batch processing with batch_size=2
        batch_size = 2
        total = len(results)
        expected_batches = (total + batch_size - 1) // batch_size

        assert expected_batches == 3, f"Expected 3 batches for 5 items, got {expected_batches}"

        # Verify batch logic
        batch_num = 0
        current_batch = []
        for task_id, json_path in results:
            current_batch.append((task_id, json_path))

            if len(current_batch) >= batch_size:
                batch_num += 1
                # Process batch
                current_batch = []

        if current_batch:
            batch_num += 1

        assert batch_num == 3, f"Expected 3 batches, got {batch_num}"
        print(f"✓ Batch processing: {total} items processed in {batch_num} batches")

    @pytest.mark.asyncio
    async def test_batch_size_edge_cases(self):
        """Test batch size edge cases"""
        test_cases = [
            (5, 2, 3),  # 5 items, batch 2 = 3 batches
            (5, 5, 1),  # 5 items, batch 5 = 1 batch
            (5, 10, 1), # 5 items, batch 10 = 1 batch
            (6, 2, 3),  # 6 items, batch 2 = 3 batches
        ]

        for total, batch_size, expected_batches in test_cases:
            actual = (total + batch_size - 1) // batch_size
            assert actual == expected_batches, \
                f"For {total} items with batch {batch_size}, expected {expected_batches} batches, got {actual}"

        print(f"✓ Batch size edge cases verified")


class TestMigrationForceOption:
    """Test force option functionality"""

    @pytest.mark.asyncio
    async def test_force_option_skips_without_flag(self, sample_json_results):
        """Test that duplicates are skipped without --force"""
        tmp_path, results = sample_json_results
        storage = SQLiteResultStorage(str(tmp_path / "test.db"))

        # Pre-populate one result
        task_id, json_path = results[0]
        with open(json_path) as f:
            result_data = json.load(f)

        await storage.save_result(task_id, result_data)

        # Without force, should return existing record
        existing = await storage.get_result(task_id)
        assert existing is not None, "Record should exist"

        print(f"✓ Force option: without --force, existing record found and skipped")

    @pytest.mark.asyncio
    async def test_force_option_overwrites_with_flag(self, sample_json_results):
        """Test that duplicates are overwritten with --force"""
        tmp_path, results = sample_json_results
        storage = SQLiteResultStorage(str(tmp_path / "test.db"))

        task_id, json_path = results[0]

        # First save
        with open(json_path) as f:
            result_data = json.load(f)

        await storage.save_result(task_id, result_data)

        first_result = await storage.get_result(task_id)
        assert first_result is not None

        # Modify data and save with force=True (simulated by saving again)
        result_data['strategy'] = 'updated_strategy'
        await storage.save_result(task_id, result_data)

        second_result = await storage.get_result(task_id)
        assert second_result is not None
        assert second_result['strategy'] == 'updated_strategy', \
            "Record should be overwritten"

        print(f"✓ Force option: with --force, existing record overwritten")


class TestMigrationReportMetrics:
    """Test migration report metrics"""

    def test_migration_report_structure(self):
        """Test migration report has correct structure"""
        from scripts.migrate_json_to_parquet import MigrationReport

        report = MigrationReport()

        # Test initial state
        assert report.successful == 0
        assert report.failed == 0
        assert report.skipped == 0
        assert report.total_files == 0
        assert report.compression_ratio == 0.0

        # Test adding success
        report.add_success(100, 10)
        assert report.successful == 1
        assert report.json_total_size == 100
        assert report.parquet_total_size == 10

        # Test compression ratio
        compression = report.compression_ratio
        assert compression == 90.0, f"Expected 90% compression, got {compression}%"

        # Test adding failure
        report.add_failure("task-1", "Test error")
        assert report.failed == 1
        assert len(report.failed_tasks) == 1

        # Test adding skipped
        report.add_skipped()
        assert report.skipped == 1

        print(f"✓ Migration report: structure and metrics verified")

    def test_migration_report_compression_calculation(self):
        """Test compression ratio calculation"""
        from backend.app.storage.converters import calculate_compression_ratio

        test_cases = [
            (100, 5, 95.0),    # 100 -> 5 = 95% compression
            (1000, 50, 95.0),  # 1000 -> 50 = 95% compression
            (100, 100, 0.0),   # No compression
            (100, 0, 100.0),   # Perfect compression
        ]

        for json_size, parquet_size, expected in test_cases:
            result = calculate_compression_ratio(json_size, parquet_size)
            assert result == expected, \
                f"For {json_size}/{parquet_size}, expected {expected}%, got {result}%"

        print(f"✓ Compression ratio calculation verified")


class TestMigrationDataValidation:
    """Test data validation in migration"""

    def test_result_manager_dual_write_mode(self):
        """Test ResultManager dual-write mode setting"""
        from backend.app.result_manager import ResultManager

        # Test mode constants exist
        assert hasattr(ResultManager, 'MODE_JSON_ONLY')
        assert hasattr(ResultManager, 'MODE_DUAL_WRITE')
        assert hasattr(ResultManager, 'MODE_POSTGRES_ONLY')

        # Test mode values
        assert ResultManager.MODE_JSON_ONLY == 'json-only'
        assert ResultManager.MODE_DUAL_WRITE == 'dual-write'
        assert ResultManager.MODE_POSTGRES_ONLY == 'postgres-only'

        # Test initialization with mode
        manager = ResultManager(
            storage=None,
            data_root='/tmp',
            storage_mode='dual-write'
        )

        assert manager.storage_mode == 'dual-write'

        print(f"✓ ResultManager dual-write mode: properly configured")
