#!/usr/bin/env python3
"""
오래된 백테스트 결과 파일 정리 스크립트

사용법:
    python scripts/cleanup_task_results.py [--ttl-days TTL_DAYS] [--dry-run]

예시:
    # 7일 이상 된 결과 파일 정리 (실제 삭제)
    python scripts/cleanup_task_results.py

    # 10일 이상 된 결과 파일 정리 (시뮬레이션)
    python scripts/cleanup_task_results.py --ttl-days 10 --dry-run

    # 30일 이상 된 결과 파일 정리
    python scripts/cleanup_task_results.py --ttl-days 30
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.result_manager import ResultManager

# 로거 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="오래된 백테스트 결과 파일 정리 스크립트"
    )
    parser.add_argument(
        "--ttl-days",
        type=int,
        default=7,
        help="보존 기간 (일, 기본값: 7)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 삭제하지 않고 목록만 출력",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="데이터 루트 디렉토리 (환경변수 DATA_ROOT가 우선)",
    )

    args = parser.parse_args()

    # 데이터 루트 확인
    data_root = os.getenv("DATA_ROOT") or args.data_root or "/data"

    if not os.path.exists(data_root):
        logger.error(f"Data root directory not found: {data_root}")
        sys.exit(1)

    logger.info(f"Starting cleanup...")
    logger.info(f"  Data root: {data_root}")
    logger.info(f"  TTL days: {args.ttl_days}")
    logger.info(f"  Dry run: {args.dry_run}")

    # 정리 실행
    try:
        result = ResultManager.cleanup_old_results(
            data_root=data_root,
            ttl_days=args.ttl_days,
            dry_run=args.dry_run,
        )

        # 결과 출력
        logger.info(f"Cleanup completed!")
        logger.info(f"  Deleted count: {result['deleted_count']}")
        logger.info(f"  Deleted size: {result['deleted_size_mb']} MB")
        logger.info(f"  Dry run: {result['dry_run']}")

        if result["deleted_count"] == 0:
            logger.info("No old task results found for cleanup.")
        else:
            if result["dry_run"]:
                logger.info("(This is a dry run - no files were actually deleted)")
            else:
                logger.info(f"Successfully deleted {result['deleted_count']} task directories")

        return 0

    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
