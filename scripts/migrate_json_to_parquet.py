#!/usr/bin/env python3
"""
JSON to Parquet Migration Script

Task 3.5.5: 기존 JSON 결과 마이그레이션

This script migrates existing JSON backtest results to PostgreSQL + Parquet format.
It supports dry-run mode, batch processing, and provides detailed migration reports.

FORCE MODE POLICY:
==================
The --force flag controls how to handle existing records in PostgreSQL:

Without --force (default):
  - Check if task_id already exists in PostgreSQL
  - If exists: SKIP migration, log info message
  - If not exists: Migrate normally
  - JSON backup: Not created for skipped files

With --force:
  - Always overwrite existing PostgreSQL records
  - Read new JSON data → Convert to Parquet → Insert/Update PostgreSQL
  - JSON backup: Created in backup_dir for ALL migrated files
  - Allows re-migrating with modified data

Backup & Rollback:
  - Location: --backup-dir (default: 'backups')
  - Structure: backups/{task_id}/result.json
  - Retention: Keep backups during dual-write phase
  - Restore: Manual copy from backups/{task_id}/result.json to original location

Usage:
    # Dry-run mode (list files, no migration)
    python scripts/migrate_json_to_parquet.py --dry-run

    # Standard migration (skip existing records)
    python scripts/migrate_json_to_parquet.py \\
        --source-dir data/tasks \\
        --batch-size 100 \\
        --backup-dir backups

    # Force migration (overwrite existing records)
    python scripts/migrate_json_to_parquet.py \\
        --source-dir data/tasks \\
        --batch-size 100 \\
        --backup-dir backups \\
        --force

    # Custom database URL
    python scripts/migrate_json_to_parquet.py \\
        --source-dir data/tasks \\
        --database-url postgresql://user:pass@localhost/dbname
"""

import argparse
import json
import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import asyncio
import shutil

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.storage.result_storage import PostgreSQLResultStorage
from backend.app.storage.converters import calculate_compression_ratio


class MigrationReport:
    """Migration report generator"""

    def __init__(self):
        self.start_time = datetime.utcnow()
        self.total_files = 0
        self.successful = 0
        self.failed = 0
        self.skipped = 0
        self.json_total_size = 0
        self.parquet_total_size = 0
        self.failed_tasks = []

    def add_success(self, json_size: int, parquet_size: int):
        """Record successful migration"""
        self.successful += 1
        self.json_total_size += json_size
        self.parquet_total_size += parquet_size

    def add_failure(self, task_id: str, error: str):
        """Record failed migration"""
        self.failed += 1
        self.failed_tasks.append((task_id, error))

    def add_skipped(self):
        """Record skipped migration"""
        self.skipped += 1

    @property
    def duration(self) -> float:
        """Duration in seconds"""
        return (datetime.utcnow() - self.start_time).total_seconds()

    @property
    def compression_ratio(self) -> float:
        """Overall compression ratio"""
        if self.json_total_size == 0:
            return 0.0
        return calculate_compression_ratio(self.json_total_size, self.parquet_total_size)

    def print_report(self, dry_run: bool = False):
        """Print migration report"""
        print("\n" + "=" * 80)
        print("MIGRATION REPORT" + (" (DRY-RUN)" if dry_run else ""))
        print("=" * 80)

        print(f"\nTotal Files Processed: {self.total_files}")
        print(f"  ✓ Successful: {self.successful}")
        print(f"  ✗ Failed: {self.failed}")
        print(f"  ⊘ Skipped: {self.skipped}")

        if self.successful > 0:
            print(f"\nData Size:")
            print(f"  JSON Total: {self.json_total_size / (1024*1024):.2f} MB")
            print(f"  Parquet Total: {self.parquet_total_size / (1024*1024):.2f} MB")
            print(f"  Compression Ratio: {self.compression_ratio:.1f}%")

        print(f"\nProcessing Time: {self.duration:.1f} seconds")

        if self.failed_tasks:
            print(f"\nFailed Tasks ({len(self.failed_tasks)}):")
            for task_id, error in self.failed_tasks[:10]:  # Show first 10
                print(f"  - {task_id}: {error[:60]}...")
            if len(self.failed_tasks) > 10:
                print(f"  ... and {len(self.failed_tasks) - 10} more")

        print("=" * 80 + "\n")


async def find_json_results(source_dir: str) -> List[Tuple[str, Path]]:
    """
    Find all result.json files in source directory

    Returns:
        List of (task_id, json_path) tuples
    """
    results = []
    source_path = Path(source_dir)

    if not source_path.exists():
        logger.warning(f"Source directory not found: {source_dir}")
        return results

    for task_dir in source_path.iterdir():
        if not task_dir.is_dir():
            continue

        result_file = task_dir / 'result.json'
        if result_file.exists():
            results.append((task_dir.name, result_file))

    logger.info(f"Found {len(results)} JSON result files")
    return results


async def migrate_result(
    storage: PostgreSQLResultStorage,
    task_id: str,
    json_path: Path,
    backup_dir: Optional[str] = None,
    force: bool = False,
) -> Tuple[bool, int, int]:
    """
    Migrate a single JSON result to Parquet

    Args:
        storage: PostgreSQLResultStorage instance
        task_id: Task ID
        json_path: Path to result.json
        backup_dir: Optional backup directory
        force: If True, overwrite existing records

    Returns:
        (success, json_size, parquet_size)

    Force Mode Policy:
    - If force=False and record exists: Skip migration, keep existing
    - If force=True and record exists: Overwrite with new data + backup JSON
    - If force=False and record not exists: Migrate normally, no backup
    - If force=True and no record exists: Migrate normally + backup JSON
    - JSON backup: Only created when force=True or new migration occurs
    - Rollback: Keep original JSON in backup directory for recovery
    """
    try:
        # Read JSON file
        with open(json_path, 'r') as f:
            json_data = json.load(f)

        json_size = json_path.stat().st_size

        # Add task_id to data if not present
        if 'task_id' not in json_data:
            json_data['task_id'] = task_id

        # Handle force mode: clean up existing Parquet files if forcing overwrite
        if force:
            parquet_dir = Path('backtests') / task_id
            if parquet_dir.exists():
                logger.info(f"Force mode: deleting existing parquet directory for {task_id}")
                shutil.rmtree(parquet_dir)

        # Save to PostgreSQL + Parquet
        success = await storage.save_result(task_id, json_data)

        if success:
            # Backup JSON file only if force=True (policy: backup only on force overwrite)
            if force and backup_dir:
                backup_path = Path(backup_dir) / task_id
                backup_path.mkdir(parents=True, exist_ok=True)
                backup_file = backup_path / 'result.json'
                shutil.copy2(json_path, backup_file)
                logger.info(f"Force mode: backed up original JSON file to {backup_file}")

            # Get parquet size (approximate from metadata)
            parquet_dir = Path('backtests') / task_id
            parquet_size = sum(
                p.stat().st_size for p in parquet_dir.glob('**/*.parquet')
                if p.is_file()
            )

            logger.info(f"Migrated {task_id}: {json_size} bytes → {parquet_size} bytes")
            return True, json_size, parquet_size
        else:
            logger.error(f"Failed to migrate {task_id}: save_result returned False")
            return False, json_size, 0

    except Exception as e:
        logger.error(f"Failed to migrate {task_id}: {str(e)}", exc_info=True)
        return False, 0, 0


async def run_migration(
    source_dir: str = 'data/tasks',
    dry_run: bool = False,
    batch_size: int = 100,
    force: bool = False,
    database_url: Optional[str] = None,
    backup_dir: Optional[str] = None,
    storage: Optional['PostgreSQLResultStorage'] = None,
) -> MigrationReport:
    """
    Run full migration with batch processing

    Args:
        source_dir: Source directory containing JSON results
        dry_run: Don't actually migrate, just report
        batch_size: Number of files to process per batch
        force: Overwrite existing PostgreSQL records (if record exists, update it)
        database_url: PostgreSQL connection URL
        backup_dir: Backup directory for JSON files
        storage: ResultStorage instance (optional, for testing)
                If None: create PostgreSQLResultStorage with database_url
                If provided: use injected storage (e.g., SQLiteResultStorage for tests)

    Returns:
        MigrationReport
    """
    report = MigrationReport()

    # Find JSON files
    json_results = await find_json_results(source_dir)
    report.total_files = len(json_results)

    if report.total_files == 0:
        logger.warning("No JSON result files found")
        return report

    if dry_run:
        logger.info(f"DRY-RUN MODE: Would migrate {report.total_files} files")
        logger.info(f"Batch size: {batch_size}")
        logger.info(f"Force overwrite: {force}")
        report.skipped = report.total_files
        return report

    # Initialize storage (use injected storage or create new one)
    if storage is None:
        try:
            storage = PostgreSQLResultStorage(database_url=database_url)
        except Exception as e:
            logger.error(f"Failed to initialize storage: {e}")
            return report
    else:
        logger.info(f"Using injected storage: {type(storage).__name__}")

    # Process in batches
    try:
        from tqdm import tqdm
        pbar = tqdm(total=report.total_files, desc="Migrating")
    except ImportError:
        logger.warning("tqdm not available, progress bar disabled")
        pbar = None

    current_batch = []
    batch_num = 0

    for task_id, json_path in json_results:
        current_batch.append((task_id, json_path))

        # Process batch when full
        if len(current_batch) >= batch_size:
            batch_num += 1
            logger.info(f"Processing batch {batch_num} ({len(current_batch)} files)...")

            for batch_task_id, batch_json_path in current_batch:
                try:
                    # Check if record exists (for force option)
                    existing = await storage.get_result(batch_task_id)
                    if existing and not force:
                        logger.debug(f"Skipping {batch_task_id}: already exists (use --force to overwrite)")
                        report.add_skipped()
                        if pbar:
                            pbar.update(1)
                        continue

                    success, json_size, parquet_size = await migrate_result(
                        storage,
                        batch_task_id,
                        batch_json_path,
                        backup_dir=backup_dir,
                        force=force,
                    )

                    if success:
                        report.add_success(json_size, parquet_size)
                    else:
                        report.add_failure(batch_task_id, "Migration returned False")

                except Exception as e:
                    report.add_failure(batch_task_id, str(e))

                finally:
                    if pbar:
                        pbar.update(1)

            current_batch = []

    # Process remaining batch
    if current_batch:
        batch_num += 1
        logger.info(f"Processing final batch {batch_num} ({len(current_batch)} files)...")

        for batch_task_id, batch_json_path in current_batch:
            try:
                # Check if record exists (for force option)
                existing = await storage.get_result(batch_task_id)
                if existing and not force:
                    logger.debug(f"Skipping {batch_task_id}: already exists (use --force to overwrite)")
                    report.add_skipped()
                    if pbar:
                        pbar.update(1)
                    continue

                success, json_size, parquet_size = await migrate_result(
                    storage,
                    batch_task_id,
                    batch_json_path,
                    backup_dir=backup_dir,
                    force=force,
                )

                if success:
                    report.add_success(json_size, parquet_size)
                else:
                    report.add_failure(batch_task_id, "Migration returned False")

            except Exception as e:
                report.add_failure(batch_task_id, str(e))

            finally:
                if pbar:
                    pbar.update(1)

    if pbar:
        pbar.close()

    logger.info(f"Migration completed: {report.successful} successful, {report.failed} failed, {report.skipped} skipped")
    return report


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Migrate JSON backtest results to PostgreSQL + Parquet format'
    )

    parser.add_argument(
        '--source-dir',
        default='data/tasks',
        help='Source directory containing JSON results (default: data/tasks)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually migrating'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Number of files to process per batch (default: 100)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing PostgreSQL records (Force Mode Policy: '
             'skip if record exists without --force; '
             'overwrite and backup JSON if --force is specified)'
    )

    parser.add_argument(
        '--database-url',
        default=None,
        help='PostgreSQL connection URL (default: DATABASE_URL env var)'
    )

    parser.add_argument(
        '--backup-dir',
        default='backups',
        help='Backup directory for JSON files (default: backups)'
    )

    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    logger.info("Starting migration...")
    logger.info(f"Source directory: {args.source_dir}")
    logger.info(f"Dry-run: {args.dry_run}")
    logger.info(f"Batch size: {args.batch_size}")

    # Run migration
    report = asyncio.run(run_migration(
        source_dir=args.source_dir,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        force=args.force,
        database_url=args.database_url,
        backup_dir=args.backup_dir if not args.dry_run else None,
    ))

    # Print report
    report.print_report(dry_run=args.dry_run)

    # Exit with appropriate code
    sys.exit(0 if report.failed == 0 else 1)


if __name__ == '__main__':
    main()
