#!/usr/bin/env python3
"""
Parquet 파일 검증 및 통계 출력 스크립트

Parquet 파일의 내용을 검증하고 주요 통계를 출력합니다.
pandas/pyarrow가 없는 경우에도 기본 정보를 출력할 수 있습니다.

사용 예:
  python scripts/inspect_parquet.py --path data/KRW-BTC/1H/2025.parquet
  python scripts/inspect_parquet.py --path data/KRW-BTC/1H/2025.parquet --verbose
"""

import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def inspect_parquet_pandas(file_path: Path) -> Dict[str, Any]:
    """
    pandas/pyarrow를 이용한 상세 검증
    """
    try:
        import pandas as pd
        import pyarrow.parquet as pq

        # Parquet 메타데이터 읽기
        parquet_file = pq.ParquetFile(file_path)
        table = parquet_file.read()
        df = table.to_pandas()

        stats = {
            'file_size': file_path.stat().st_size,
            'rows': len(df),
            'columns': list(df.columns),
            'dtypes': df.dtypes.to_dict(),
            'timestamp_min': str(df['timestamp'].min()) if 'timestamp' in df else 'N/A',
            'timestamp_max': str(df['timestamp'].max()) if 'timestamp' in df else 'N/A',
            'numeric_columns': {}
        }

        # 숫자형 컬럼 통계
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        for col in numeric_cols:
            stats['numeric_columns'][col] = {
                'min': float(df[col].min()),
                'max': float(df[col].max()),
                'mean': float(df[col].mean()),
                'std': float(df[col].std()),
            }

        # 메모리 사용량
        stats['memory_usage'] = df.memory_usage(deep=True).sum()

        # 결측치 체크
        stats['null_counts'] = df.isnull().sum().to_dict()

        return stats

    except ImportError as e:
        logger.warning(f"pandas/pyarrow 라이브러리 필요: {e}")
        return inspect_parquet_basic(file_path)
    except Exception as e:
        logger.error(f"파일 읽기 실패: {e}")
        return {}


def inspect_parquet_basic(file_path: Path) -> Dict[str, Any]:
    """
    기본 정보만 출력 (pandas 없을 경우)
    """
    try:
        import pyarrow.parquet as pq

        parquet_file = pq.ParquetFile(file_path)
        metadata = parquet_file.metadata
        schema = parquet_file.schema_arrow

        stats = {
            'file_size': file_path.stat().st_size,
            'rows': metadata.num_rows,
            'columns': schema.names,
            'note': 'pandas 미설치 상태 - 기본 정보만 제공',
        }

        return stats

    except Exception as e:
        logger.error(f"파일 분석 실패: {e}")
        return {}


def print_stats(stats: Dict[str, Any], verbose: bool = False) -> None:
    """
    통계를 보기 좋게 출력
    """
    if not stats:
        logger.warning("통계 정보를 가져올 수 없습니다")
        return

    print("\n" + "=" * 70)
    print("📊 Parquet 파일 검증 결과")
    print("=" * 70)

    # 기본 정보
    print(f"\n📁 기본 정보:")
    print(f"  파일 크기: {stats.get('file_size', 'N/A'):,} bytes "
          f"({stats.get('file_size', 0) / 1024 / 1024:.2f} MB)")
    print(f"  행(Row) 수: {stats.get('rows', 'N/A'):,}")
    print(f"  컬럼(Column): {', '.join(stats.get('columns', []))}")

    # 타임스탬프 범위
    if 'timestamp_min' in stats:
        print(f"\n⏰ 시간 범위:")
        print(f"  최소: {stats['timestamp_min']}")
        print(f"  최대: {stats['timestamp_max']}")

    # 숫자형 컬럼 통계
    if 'numeric_columns' in stats and stats['numeric_columns']:
        print(f"\n📈 숫자형 컬럼 통계:")
        for col, col_stats in stats['numeric_columns'].items():
            print(f"\n  {col}:")
            print(f"    최소값: {col_stats['min']:,.2f}")
            print(f"    최대값: {col_stats['max']:,.2f}")
            print(f"    평균: {col_stats['mean']:,.2f}")
            print(f"    표준편차: {col_stats['std']:,.2f}")

    # 결측치 정보
    if 'null_counts' in stats:
        null_cols = {k: v for k, v in stats['null_counts'].items() if v > 0}
        if null_cols:
            print(f"\n⚠️  결측치 감지:")
            for col, count in null_cols.items():
                print(f"    {col}: {count}개")
        else:
            print(f"\n✅ 결측치 없음")

    # 메모리 사용량
    if 'memory_usage' in stats:
        mem_mb = stats['memory_usage'] / 1024 / 1024
        print(f"\n💾 메모리 사용량: {mem_mb:.2f} MB")

    # 데이터 타입
    if verbose and 'dtypes' in stats:
        print(f"\n📋 데이터 타입:")
        for col, dtype in stats['dtypes'].items():
            print(f"    {col}: {dtype}")

    # 메모 사항
    if 'note' in stats:
        print(f"\n📝 메모: {stats['note']}")

    print("\n" + "=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Parquet 파일 검증 및 통계 출력 도구',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--path', required=True, help='검증할 Parquet 파일 경로')
    parser.add_argument('--verbose', '-v', action='store_true', help='상세 정보 출력')

    args = parser.parse_args()

    # 파일 경로 검증
    file_path = Path(args.path)
    if not file_path.exists():
        logger.error(f"파일을 찾을 수 없음: {file_path}")
        sys.exit(1)

    if not file_path.suffix.lower() == '.parquet':
        logger.warning(f"파일 확장자가 .parquet이 아닙니다: {file_path.suffix}")

    # 검증 수행
    logger.info(f"파일 분석 중: {file_path}")
    stats = inspect_parquet_pandas(file_path)

    # 결과 출력
    print_stats(stats, verbose=args.verbose)

    # 성공 반환
    if stats:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
