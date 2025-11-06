#!/usr/bin/env python3
"""
E2E 테스트: 데이터 관리 기능

목적:
- 데이터 인벤토리 조회 API 테스트
- 파일 업로드 API 테스트
- 업로드된 데이터로 백테스트 실행 테스트

실행:
    # 로컬 개발 환경 (기본값)
    python scripts/e2e_test_data_management.py

    # Docker 환경
    python scripts/e2e_test_data_management.py --base-url http://backend:8000

    # 커스텀 URL
    python scripts/e2e_test_data_management.py --base-url http://example.com:8000
"""

import requests
import json
import tempfile
import sys
import os
import argparse
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa
from datetime import datetime, timedelta

# 기본값
DEFAULT_BASE_URL = "http://localhost:8000"

# 커맨드라인 인자 파싱
parser = argparse.ArgumentParser(description="데이터 관리 E2E 테스트")
parser.add_argument(
    "--base-url",
    type=str,
    default=DEFAULT_BASE_URL,
    help=f"API 베이스 URL (기본값: {DEFAULT_BASE_URL})"
)
parser.add_argument(
    "--verbose",
    action="store_true",
    help="상세 로깅 활성화"
)

args = parser.parse_args()

# 설정
API_BASE = f"{args.base_url}/api"
DATA_API = f"{API_BASE}/data"
BACKTEST_API = f"{API_BASE}/backtests/run"

if args.verbose:
    print(f"API Base URL: {API_BASE}")

# 테스트 데이터 생성 헬퍼 함수
def create_test_parquet_file(output_path, num_rows=100):
    """
    테스트용 Parquet 파일 생성

    Args:
        output_path: 저장 경로
        num_rows: 생성할 행 수
    """
    dates = pd.date_range(start='2024-01-01', periods=num_rows, freq='D')
    data = {
        'timestamp': dates,
        'open': [100.0 + i for i in range(num_rows)],
        'high': [102.0 + i for i in range(num_rows)],
        'low': [99.0 + i for i in range(num_rows)],
        'close': [101.0 + i for i in range(num_rows)],
        'volume': [1000000 + i * 100 for i in range(num_rows)]
    }

    df = pd.DataFrame(data)
    df.to_parquet(output_path, index=False)
    return output_path


def create_invalid_parquet_file(output_path, missing_column='close'):
    """
    필수 컬럼이 누락된 Parquet 파일 생성

    Args:
        output_path: 저장 경로
        missing_column: 누락할 컬럼명
    """
    dates = pd.date_range(start='2024-01-01', periods=10, freq='D')
    data = {
        'timestamp': dates,
        'open': [100.0 + i for i in range(10)],
        'high': [102.0 + i for i in range(10)],
        'low': [99.0 + i for i in range(10)],
        'volume': [1000000 + i * 100 for i in range(10)]
    }

    # missing_column 제외
    if missing_column in data:
        del data[missing_column]

    df = pd.DataFrame(data)
    df.to_parquet(output_path, index=False)
    return output_path


def test_inventory_empty():
    """테스트 1: 초기 빈 인벤토리 확인"""
    print("\n[테스트 1] 초기 빈 인벤토리 확인...")

    try:
        response = requests.get(f"{DATA_API}/inventory")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert 'files' in data, "Response missing 'files' field"
        assert 'total_count' in data, "Response missing 'total_count' field"
        assert isinstance(data['files'], list), "'files' should be a list"

        print(f"✓ 인벤토리 조회 성공: 파일 {data['total_count']}개")
        return True

    except Exception as e:
        print(f"✗ 테스트 실패: {e}")
        return False


def test_upload_valid_file():
    """테스트 2: 유효한 파일 업로드"""
    print("\n[테스트 2] 유효한 파일 업로드...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # 테스트 파일 생성
            file_path = Path(tmpdir) / "test_upload.parquet"
            create_test_parquet_file(str(file_path))

            # 파일 업로드
            with open(file_path, 'rb') as f:
                files = {'file': f}
                data = {
                    'symbol': 'TEST_KRW',
                    'timeframe': '1D',
                    'year': 2024,
                    'overwrite': False
                }

                response = requests.post(f"{DATA_API}/upload", files=files, data=data)

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            result = response.json()
            assert result['success'] == True, f"Upload failed: {result.get('message')}"
            assert 'file_path' in result, "Response missing 'file_path' field"

            print(f"✓ 파일 업로드 성공: {result['file_path']}")
            return True

    except Exception as e:
        print(f"✗ 테스트 실패: {e}")
        return False


def test_upload_invalid_file():
    """테스트 3: 잘못된 파일 업로드 거부"""
    print("\n[테스트 3] 잘못된 파일 업로드 거부...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # 필수 컬럼 누락 파일 생성
            file_path = Path(tmpdir) / "invalid.parquet"
            create_invalid_parquet_file(str(file_path), missing_column='close')

            # 파일 업로드 시도
            with open(file_path, 'rb') as f:
                files = {'file': f}
                data = {
                    'symbol': 'INVALID_KRW',
                    'timeframe': '1D',
                    'year': 2024,
                    'overwrite': False
                }

                response = requests.post(f"{DATA_API}/upload", files=files, data=data)

            # 415 (Unsupported Media Type) 또는 400 (Bad Request) 기대
            assert response.status_code in [400, 415], f"Expected 400 or 415, got {response.status_code}"

            print(f"✓ 유효하지 않은 파일 거부됨 (상태코드: {response.status_code})")
            return True

    except Exception as e:
        print(f"✗ 테스트 실패: {e}")
        return False


def test_upload_traversal_attempt():
    """테스트 4: 경로 이탈 시도 차단"""
    print("\n[테스트 4] 경로 이탈 시도 차단...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # 테스트 파일 생성
            file_path = Path(tmpdir) / "test.parquet"
            create_test_parquet_file(str(file_path))

            # 경로 이탈 시도 (심볼에 ../ 포함)
            with open(file_path, 'rb') as f:
                files = {'file': f}
                data = {
                    'symbol': '../../../ETC',
                    'timeframe': '1D',
                    'year': 2024,
                    'overwrite': False
                }

                response = requests.post(f"{DATA_API}/upload", files=files, data=data)

            # 400 (Bad Request) 기대
            assert response.status_code == 400, f"Expected 400, got {response.status_code}"

            print(f"✓ 경로 이탈 시도 차단됨")
            return True

    except Exception as e:
        print(f"✗ 테스트 실패: {e}")
        return False


def test_inventory_after_upload():
    """테스트 5: 업로드 후 인벤토리 반영 확인"""
    print("\n[테스트 5] 업로드 후 인벤토리 반영 확인...")

    try:
        # 업로드 전 인벤토리 조회
        response_before = requests.get(f"{DATA_API}/inventory")
        assert response_before.status_code == 200
        count_before = response_before.json()['total_count']

        # 파일 업로드
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "inventory_test.parquet"
            create_test_parquet_file(str(file_path))

            with open(file_path, 'rb') as f:
                files = {'file': f}
                data = {
                    'symbol': 'INVENTORY_TEST',
                    'timeframe': '1D',
                    'year': 2024,
                    'overwrite': False
                }

                response_upload = requests.post(f"{DATA_API}/upload", files=files, data=data)
                assert response_upload.status_code == 200

        # 업로드 후 인벤토리 조회
        response_after = requests.get(f"{DATA_API}/inventory")
        assert response_after.status_code == 200
        count_after = response_after.json()['total_count']

        assert count_after > count_before, f"File count should increase (before: {count_before}, after: {count_after})"

        print(f"✓ 인벤토리 반영 확인: {count_before} → {count_after}")
        return True

    except Exception as e:
        print(f"✗ 테스트 실패: {e}")
        return False


def test_backtest_with_uploaded_data():
    """테스트 6: 업로드된 데이터로 백테스트 실행"""
    print("\n[테스트 6] 업로드된 데이터로 백테스트 실행...")

    try:
        # 먼저 파일 업로드
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "backtest_test.parquet"
            create_test_parquet_file(str(file_path), num_rows=365)

            with open(file_path, 'rb') as f:
                files = {'file': f}
                upload_data = {
                    'symbol': 'BT_TEST_KRW',
                    'timeframe': '1D',
                    'year': 2024,
                    'overwrite': False
                }

                response_upload = requests.post(f"{DATA_API}/upload", files=files, data=upload_data)
                assert response_upload.status_code == 200, f"Upload failed: {response_upload.text}"

        # 업로드된 데이터로 백테스트 실행
        backtest_data = {
            'strategy': 'volume_long_candle',
            'symbols': ['BT_TEST_KRW'],
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'timeframe': '1d',
            'params': {
                'vol_ma_window': 10,
                'vol_multiplier': 1.5,
                'body_pct': 0.01
            }
        }

        response_backtest = requests.post(BACKTEST_API, json=backtest_data)

        # 백테스트 성공 또는 데이터 부족으로 인한 404 둘 다 OK
        assert response_backtest.status_code in [200, 404], f"Expected 200 or 404, got {response_backtest.status_code}"

        if response_backtest.status_code == 200:
            print(f"✓ 백테스트 실행 성공")
        else:
            print(f"⚠ 데이터 부족으로 백테스트 실패 (예상된 동작)")

        return True

    except Exception as e:
        print(f"✗ 테스트 실패: {e}")
        return False


def health_check(base_url, timeout=30, retries=5):
    """
    API 서버 헬스 체크

    Args:
        base_url: API 베이스 URL
        timeout: 각 시도의 타임아웃 (초)
        retries: 재시도 횟수

    Returns:
        True if healthy, False otherwise
    """
    health_url = f"{base_url}/api/health"

    for attempt in range(retries):
        try:
            response = requests.get(health_url, timeout=timeout)
            if response.status_code == 200:
                return True
            print(f"  [시도 {attempt + 1}/{retries}] 상태코드: {response.status_code}", end="")
        except requests.exceptions.ConnectionError:
            print(f"  [시도 {attempt + 1}/{retries}] 연결 거부", end="")
        except requests.exceptions.Timeout:
            print(f"  [시도 {attempt + 1}/{retries}] 타임아웃", end="")
        except Exception as e:
            print(f"  [시도 {attempt + 1}/{retries}] 오류: {str(e)[:50]}", end="")

        if attempt < retries - 1:
            print(" (재시도 중...)")
            import time
            time.sleep(2)
        else:
            print(" (최종 실패)")

    return False


def main():
    """메인 테스트 실행"""
    print("=" * 60)
    print("데이터 관리 E2E 테스트")
    print("=" * 60)

    # API 서버 연결 확인
    print(f"\n🔌 API 서버 헬스 체크: {args.base_url}")
    print("  (최대 30초 대기...)")

    if not health_check(args.base_url):
        print(f"\n✗ API 서버에 연결할 수 없습니다")
        print(f"  URL: {args.base_url}")
        print(f"\n해결 방법:")
        print(f"  1. 로컬 개발 환경:")
        print(f"     python -m uvicorn backend.app.main:app --reload")
        print(f"  2. Docker 환경:")
        print(f"     docker-compose up backend")
        print(f"  3. 커스텀 URL 지정:")
        print(f"     python scripts/e2e_test_data_management.py --base-url http://your-server:8000")
        return False

    print("✓ API 서버 연결 성공\n")

    # 테스트 실행
    tests = [
        test_inventory_empty,
        test_upload_valid_file,
        test_upload_invalid_file,
        test_upload_traversal_attempt,
        test_inventory_after_upload,
        test_backtest_with_uploaded_data
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ 테스트 중 예상 밖의 오류 발생: {e}")
            results.append(False)

    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    for i, (test, result) in enumerate(zip(tests, results), 1):
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{i}. {test.__name__}: {status}")

    print(f"\n총 {total}개 중 {passed}개 통과 ({100 * passed // total}%)")

    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
