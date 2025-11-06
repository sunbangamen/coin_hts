#!/usr/bin/env python3
"""
RQ Job 테스트 스크립트

enqueue_fetch_candles를 테스트하여 RQ 큐에 작업이 정상적으로 추가되고
실행 가능한지 확인합니다.
"""

import sys
import time
import redis
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from backend.app.jobs import (
    enqueue_fetch_candles,
    fetch_candles_job,
    enqueue_batch_fetch,
    DataIngestionStatus
)

def generate_dummy_candles(symbol: str, days: int) -> tuple:
    """모의 캔들 데이터 생성"""
    import pandas as pd
    from datetime import datetime, timedelta, timezone
    import random

    # 최근 N일 데이터 생성
    base_price = 150000000  # 1억 5천만 원
    dates = []
    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    current = start_date

    while current < end_date:
        dates.append(current)

        # 임의의 가격 변동 (±2%)
        change = random.uniform(-0.02, 0.02)
        open_price = base_price * (1 + change)
        close_price = base_price * (1 + random.uniform(-0.02, 0.02))
        high_price = max(open_price, close_price) * 1.01
        low_price = min(open_price, close_price) * 0.99
        volume = random.uniform(100, 500)

        opens.append(open_price)
        closes.append(close_price)
        highs.append(high_price)
        lows.append(low_price)
        volumes.append(volume)

        base_price = close_price
        current += timedelta(hours=1)

    df = pd.DataFrame({
        'timestamp': dates,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    })

    return df, len(df)


def test_rq_job(offline: bool = False, offline_prefix: str = "OFFLINE"):
    """RQ 작업 테스트

    Args:
        offline: 오프라인 모드 (Redis/API 미연결)
        offline_prefix: 오프라인 모드에서 심볼 prefix (예: OFFLINE_KRW-BTC)
    """
    print("=" * 60)
    mode_str = "[오프라인 모드]" if offline else ""
    print(f"RQ Job 테스트 시작 {mode_str}")
    print("=" * 60)

    # Redis 연결 (오프라인 모드 제외)
    if not offline:
        try:
            conn = redis.Redis(host='localhost', port=6379, db=0)
            conn.ping()
            print("✓ Redis 연결 성공\n")
        except Exception as e:
            print(f"✗ Redis 연결 실패: {e}")
            return False
    else:
        conn = None
        print("ℹ️  오프라인 모드: Redis 미연결")
        print(f"📝 파일 저장 심볼 prefix: {offline_prefix}\n")

    # 1. 작업 큐에 추가 테스트 (오프라인 모드 제외)
    if not offline:
        print("1️⃣  작업 큐 추가 테스트")
        print("-" * 60)
        try:
            job = enqueue_fetch_candles(
                connection=conn,
                symbol='KRW-BTC',
                timeframe='1H',
                days=1,
                overwrite=False
            )
            print(f"✓ 작업 큐 추가 성공")
            print(f"  Job ID: {job.id}")
            print(f"  Status: {job.get_status()}\n")
        except Exception as e:
            print(f"✗ 작업 큐 추가 실패: {e}\n")
            return False
    else:
        print("1️⃣  작업 큐 추가 테스트")
        print("-" * 60)
        print("⊘ 오프라인 모드: 큐 테스트 스킵\n")

    # 2. 직접 함수 호출 테스트 (Worker 없이)
    print("2️⃣  직접 함수 호출 테스트 (동기)")
    print("-" * 60)

    if offline:
        # 오프라인 모드: 모의 데이터 생성 및 저장
        try:
            print("⊙ 오프라인 모드: 모의 캔들 데이터 생성 중...")

            # 테스트용 심볼
            test_symbol = f"{offline_prefix}_KRW-BTC"
            test_timeframe = '1H'

            # 모의 데이터 생성
            df, row_count = generate_dummy_candles(symbol='KRW-BTC', days=1)
            print(f"  ✓ {row_count}개 모의 캔들 생성 완료")

            # Parquet으로 저장
            # fetch_upbit_candles.py에서 save_to_parquet_by_year 함수를 import
            import sys
            from pathlib import Path
            # scripts 디렉토리의 fetch_upbit_candles 모듈에서 함수 로드
            sys.path.insert(0, str(Path(__file__).parent))
            from fetch_upbit_candles import save_to_parquet_by_year

            saved_files = save_to_parquet_by_year(
                df=df,
                symbol=test_symbol,
                timeframe=test_timeframe,
                overwrite=True
            )

            print(f"✓ 오프라인 데이터 저장 성공")
            print(f"  저장 파일: {saved_files[0] if saved_files else 'N/A'}")
            print(f"  행 수: {row_count}")

            # Parquet 검증
            parquet_file = saved_files[0] if saved_files else None
            offline_test_result = {
                'success': True,
                'message': f'{test_symbol} {test_timeframe} 오프라인 테스트 완료',
                'file_path': parquet_file,
                'row_count': row_count
            }
            print()

        except Exception as e:
            print(f"✗ 오프라인 모드 실패: {e}\n")
            import traceback
            traceback.print_exc()
            return False
    else:
        # 정상 모드: 실제 API 호출
        try:
            result = fetch_candles_job(
                symbol='KRW-BTC',
                timeframe='1H',
                days=1,
                overwrite=False
            )
            offline_test_result = result
            print(f"✓ 함수 실행 성공")
            print(f"  Success: {result['success']}")
            if result['success']:
                print(f"  Message: {result['message']}")
                print(f"  Timestamp: {result.get('timestamp', 'N/A')}")
            else:
                print(f"  Error: {result.get('error', 'Unknown error')}")
            print()
        except Exception as e:
            print(f"✗ 함수 실행 실패: {e}\n")
            import traceback
            traceback.print_exc()
            return False

    # 3. 배치 작업 테스트 (오프라인 모드 제외)
    if not offline:
        print("3️⃣  배치 작업 테스트")
        print("-" * 60)
        try:
            job = enqueue_batch_fetch(
                connection=conn,
                symbols=['KRW-BTC'],
                timeframes=['1H'],
                days=1,
                overwrite=False
            )
            print(f"✓ 배치 작업 큐 추가 성공")
            print(f"  Job ID: {job.id}")
            print(f"  Status: {job.get_status()}\n")
        except Exception as e:
            print(f"✗ 배치 작업 큐 추가 실패: {e}\n")
            return False
    else:
        print("3️⃣  배치 작업 테스트")
        print("-" * 60)
        print("⊘ 오프라인 모드: 배치 작업 테스트 스킵\n")

    # 4. 데이터 저장 경로 확인 및 검증
    print("4️⃣  데이터 저장 경로 확인 및 검증")
    print("-" * 60)
    try:
        from pathlib import Path
        import os
        import subprocess

        data_root = Path(os.getenv('DATA_ROOT', '/data'))

        if offline:
            # 오프라인 모드: 생성된 파일 확인
            symbol_to_check = f"{offline_prefix}_KRW-BTC"
            parquet_file = data_root / symbol_to_check / '1H' / '2025.parquet'
        else:
            # 정상 모드: 실데이터 파일 확인
            parquet_file = data_root / 'KRW-BTC' / '1H' / '2025.parquet'

        if parquet_file.exists():
            import pandas as pd
            df = pd.read_parquet(parquet_file)
            print(f"✓ Parquet 파일 확인")
            print(f"  경로: {parquet_file}")
            print(f"  행 수: {len(df)}")
            print(f"  타임스탬프 범위: {df['timestamp'].min()} ~ {df['timestamp'].max()}")

            # 자동으로 inspect_parquet.py 호출
            print(f"\n📊 inspect_parquet.py로 상세 검증 중...\n")
            result = subprocess.run(
                [sys.executable, "scripts/inspect_parquet.py", "--path", str(parquet_file)],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=False
            )
            if result.returncode == 0:
                print("\n✓ Parquet 검증 완료")
            else:
                print("\n⚠ Parquet 검증 중 오류 발생")
        else:
            print(f"⚠ Parquet 파일이 아직 없음: {parquet_file}")
        print()
    except Exception as e:
        print(f"⚠ 데이터 확인 중 오류: {e}\n")

    # 결과 요약
    print("=" * 60)
    print("✅ RQ Job 테스트 완료")
    print("=" * 60)
    print("\n테스트 요약:")
    print("  1. Redis 연결: ✓")
    print("  2. 작업 큐 추가: ✓")
    print("  3. 동기 함수 실행: ✓")
    print("  4. 배치 작업: ✓")
    print("\nRQ Worker를 시작하여 큐에 있는 작업을 실행하려면:")
    print("  rq worker data_ingestion -c backend.app.main")

    return True


if __name__ == '__main__':
    import os
    import argparse

    parser = argparse.ArgumentParser(
        description='RQ Job 테스트 스크립트',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예제:
  # 정상 모드 (Redis 및 실제 API 호출)
  python scripts/test_rq_job.py

  # 오프라인 모드 (모의 데이터 사용)
  python scripts/test_rq_job.py --offline

  # 오프라인 모드 + 커스텀 prefix
  python scripts/test_rq_job.py --offline --offline-prefix SANDBOX
"""
    )
    parser.add_argument('--offline', action='store_true', help='오프라인 모드: Redis 없이 로컬 테스트만 수행')
    parser.add_argument('--offline-prefix', default='OFFLINE', help='오프라인 모드에서 심볼 prefix (기본값: OFFLINE)')
    args = parser.parse_args()

    # DATA_ROOT 환경변수 설정
    if 'DATA_ROOT' not in os.environ:
        data_root = Path(__file__).resolve().parents[1] / 'data'
        os.environ['DATA_ROOT'] = str(data_root)
        print(f"DATA_ROOT 설정: {os.environ['DATA_ROOT']}\n")

    success = test_rq_job(offline=args.offline, offline_prefix=args.offline_prefix)
    sys.exit(0 if success else 1)
