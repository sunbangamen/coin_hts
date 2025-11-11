# Test Suite Documentation

## Overview

This directory contains all unit and integration tests for the project.

**Last Updated**: 2025-11-11
**Total Tests**: 299 (automatically calculated via `scripts/count_tests.py`)

## Test Count

To get the current test count, run:

```bash
python3 scripts/count_tests.py --format text
```

Output formats available:
- `--format text` (default): Plain text report
- `--format markdown`: Markdown table format
- `--format json`: JSON format for CI/CD integration

## Test Organization

### Unit Tests (267)

Located in `tests/` directory:

- `test_api.py`: API endpoint tests (26)
- `test_async_api.py`: Async API tests (19)
- `test_converters.py`: Data format conversion tests (11)
- `test_data_api.py`: Data API tests (11)
- `test_data_loader.py`: Data loading tests (22)
- `test_dual_write_integration.py`: Dual-write storage tests (11)
- `test_in_memory_redis.py`: In-memory Redis tests (10)
- `test_migration_batch_force.py`: Migration batch/force options (7)
- `test_migration_script_e2e.py`: End-to-end migration tests (15)
- `test_position_manager.py`: Position management tests (20)
- `test_postgresql_result_storage.py`: PostgreSQL storage tests (13)
- `test_result_manager.py`: Result manager tests (18)
- `test_s3_storage.py`: S3 storage tests (10)
- `test_strategies.py`: Trading strategy tests (34)
- `test_strategy_preset_manager.py`: Strategy preset tests (14)
- `test_strategy_runner.py`: Strategy runner tests (26)

### Integration Tests (32)

Located in `tests/integration/` directory:

- `test_integration_phase3.py`: Phase 3 integration tests (14)
- `test_performance_regression.py`: Performance regression tests (7)
- `test_result_storage_migration.py`: Result storage migration tests (11)

## Running Tests

### All Tests

```bash
# Run all tests
pytest tests/ -v

# Run with minimal output
pytest tests/ -q

# Run with specific markers
pytest tests/ -m "not slow"
```

### Specific Test Files

```bash
# Task 3.5 related tests
pytest tests/test_converters.py -v
pytest tests/test_postgresql_result_storage.py -v
pytest tests/integration/test_result_storage_migration.py -v
pytest tests/test_migration_script_e2e.py -v
pytest tests/test_dual_write_integration.py -v
```

### Test Filtering

```bash
# Run only integration tests
pytest tests/integration/ -v

# Run only unit tests
pytest tests/ --ignore=tests/integration/ -v

# Run specific test class
pytest tests/test_migration_script_e2e.py::TestMigrationScriptBatchProcessing -v

# Run specific test function
pytest tests/test_migration_script_e2e.py::TestMigrationScriptBatchProcessing::test_batch_processing_with_batch_size_2 -v
```

## Test Categories

### Task 3.5: Result Storage Migration

These tests verify the PostgreSQL + Parquet migration functionality:

| File | Tests | Purpose |
|------|-------|---------|
| `test_converters.py` | 11 | JSON ↔ Parquet conversion |
| `test_postgresql_result_storage.py` | 13 | PostgreSQL storage CRUD operations |
| `test/integration/test_result_storage_migration.py` | 11 | Full migration workflow |
| `test_migration_batch_force.py` | 7 | Batch processing and force mode |
| `test_migration_script_e2e.py` | 15 | End-to-end migration with storage injection |
| `test_dual_write_integration.py` | 11 | Dual-write mode and transitions |

**Task 3.5 Total**: 68 tests

## Important Notes

### Automatic Test Count

The test count is **automatically calculated** from the actual test functions in the codebase using:

```bash
rg -c "^\s*(async\s+)?def\s+test_" tests/**/*.py
```

This ensures documentation always reflects the actual test count.

### Documentation References

- Update `scripts/count_tests.py` when adding new test structure
- Run `python3 scripts/count_tests.py --format markdown` to generate reports
- All documentation referencing test counts should include:
  - Actual count from `scripts/count_tests.py`
  - Date of measurement (format: YYYY-MM-DD)
  - Reference to the counting script

### Test Development Guidelines

1. Always name test functions with `test_` prefix
2. Organize related tests into test classes
3. Use `@pytest.mark.asyncio` for async tests
4. Add docstrings explaining what each test verifies
5. Run `scripts/count_tests.py` before committing to verify counts

## CI/CD Integration

For CI/CD pipelines, use:

```bash
# Get total test count as JSON
python3 scripts/count_tests.py --format json > test_count.json

# Run tests with summary
pytest tests/ --tb=short -q 2>&1 | tee test_results.txt
```

## Performance Notes

- Unit tests typically complete in < 30 seconds
- Integration tests may take 1-5 minutes
- Use `-m "not slow"` to skip long-running tests
- Use `--maxfail=1` to stop at first failure for faster feedback

## Debugging Tests

```bash
# Show print statements
pytest tests/ -s

# Verbose output with detailed failures
pytest tests/ -vv

# Drop into debugger on failure
pytest tests/ --pdb

# Show local variables in tracebacks
pytest tests/ -l
```

## References

- **Test Counter Script**: `scripts/count_tests.py`
- **Implementation Summary**: `TASK_3_5_IMPLEMENTATION_SUMMARY.md`
- **Performance Report**: `docs/coin/mvp/RESULT_STORAGE_PERFORMANCE.md`
- **Task Requirements**: `docs/coin/mvp/ri_20.md`

---

**Maintainer Note**: This README is manually maintained. Keep test counts in sync with actual test functions using `scripts/count_tests.py`.
