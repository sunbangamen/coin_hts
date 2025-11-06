#!/usr/bin/env python3
"""
스케줄러 검증 스크립트

Step 1-3이 정상 작동하는지 자동으로 검증합니다:
1. Backend 헬스 체크
2. 스케줄러 상태 확인
3. 수동 트리거 실행
4. Parquet 파일 생성 확인
5. 데이터 무결성 검증
"""

import sys
import time
import requests
import os
from pathlib import Path
from datetime import datetime

# 설정
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8000')
DATA_ROOT = os.getenv('DATA_ROOT', '/data')
POLLING_TIMEOUT = 30  # 초

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'


def print_section(title):
    """섹션 제목 출력"""
    print(f"\n{Colors.BLUE}{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}{Colors.RESET}\n")


def print_success(msg):
    """성공 메시지"""
    print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")


def print_error(msg):
    """오류 메시지"""
    print(f"{Colors.RED}❌ {msg}{Colors.RESET}")


def print_warning(msg):
    """경고 메시지"""
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.RESET}")


def print_info(msg):
    """정보 메시지"""
    print(f"ℹ️  {msg}")


def check_backend_health():
    """1. Backend 헬스 체크"""
    print_section("Step 1: Backend 헬스 체크")

    try:
        response = requests.get(f"{BACKEND_URL}/api/health", timeout=5)
        if response.status_code == 200:
            print_success("Backend가 응답 중입니다")
            return True
        else:
            print_error(f"Backend 상태 이상 (Status: {response.status_code})")
            return False
    except Exception as e:
        print_error(f"Backend 연결 실패: {e}")
        return False


def check_scheduler_status():
    """2. 스케줄러 상태 확인"""
    print_section("Step 2: 스케줄러 상태 확인")

    try:
        response = requests.get(f"{BACKEND_URL}/api/scheduler/status", timeout=5)
        if response.status_code != 200:
            print_error(f"상태 조회 실패 (Status: {response.status_code})")
            return None

        status = response.json()

        # 스케줄러 상태
        enabled = status.get('enabled', False)
        running = status.get('running', False)
        print_info(f"스케줄러 활성화: {enabled}")
        print_info(f"스케줄러 실행 중: {running}")

        if not enabled or not running:
            print_warning("스케줄러가 비활성화 또는 중지 상태입니다")

        # Redis 상태
        redis_info = status.get('redis', {})
        redis_connected = redis_info.get('connected', False)
        print_info(f"Redis 연결: {redis_connected} ({redis_info.get('host')}:{redis_info.get('port')})")

        if not redis_connected:
            print_error("Redis 연결 실패")
            return None

        # 설정 정보
        config = status.get('configuration', {})
        print_info(f"실행 시간: {config.get('hour', 'N/A'):02d}:{config.get('minute', 'N/A'):02d} (UTC)")
        print_info(f"심볼: {', '.join(config.get('symbols', []))}")
        print_info(f"타임프레임: {', '.join(config.get('timeframes', []))}")

        print_success("스케줄러 상태 정상")
        return status

    except Exception as e:
        print_error(f"상태 조회 실패: {e}")
        return None


def trigger_immediate_job():
    """3. 수동 트리거 실행"""
    print_section("Step 3: 수동 배치 작업 트리거")

    try:
        payload = {
            "symbols": ["KRW-BTC"],
            "timeframes": ["1H"],
            "days": 1,
            "overwrite": False
        }

        print_info("배치 작업 실행 중...")
        response = requests.post(
            f"{BACKEND_URL}/api/scheduler/trigger",
            json=payload,
            timeout=10
        )

        if response.status_code != 200:
            print_error(f"트리거 실패 (Status: {response.status_code})")
            return None

        result = response.json()
        job_id = result.get('job_id')
        print_success(f"배치 작업 추가됨: {job_id}")

        return job_id

    except Exception as e:
        print_error(f"트리거 실패: {e}")
        return None


def wait_for_parquet_file(job_id, timeout=POLLING_TIMEOUT):
    """4. Parquet 파일 생성 확인"""
    print_section("Step 4: Parquet 파일 생성 확인")

    parquet_file = Path(DATA_ROOT) / "KRW-BTC" / "1H" / "2025.parquet"
    start_time = time.time()

    print_info(f"대기 중 (최대 {timeout}초)...")
    print_info(f"파일 경로: {parquet_file}")

    while time.time() - start_time < timeout:
        if parquet_file.exists():
            file_size = parquet_file.stat().st_size
            print_success(f"Parquet 파일 생성됨 ({file_size} bytes)")
            return str(parquet_file)

        time.sleep(2)
        elapsed = int(time.time() - start_time)
        print_info(f"  [{elapsed}초] 파일 생성 대기 중...")

    print_warning("Parquet 파일이 생성되지 않았습니다 (Worker가 실행 중인지 확인하세요)")
    return None


def verify_parquet_data(parquet_path):
    """5. 데이터 무결성 검증"""
    print_section("Step 5: 데이터 무결성 검증")

    if not parquet_path:
        print_warning("검증할 파일이 없습니다")
        return False

    try:
        import pandas as pd

        df = pd.read_parquet(parquet_path)

        # 기본 검증
        rows = len(df)
        cols = list(df.columns)

        print_info(f"행 수: {rows}")
        print_info(f"컬럼: {', '.join(cols)}")

        # 필수 컬럼 확인
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = [c for c in required_cols if c not in cols]

        if missing_cols:
            print_error(f"누락된 컬럼: {', '.join(missing_cols)}")
            return False

        # 데이터 타입 확인
        if df[['open', 'high', 'low', 'close', 'volume']].isnull().any().any():
            print_error("결측치 발견")
            return False

        # 타임스탬프 확인
        if df['timestamp'].isnull().any():
            print_error("타임스탬프 결측치 발견")
            return False

        print_success("데이터 무결성 검증 완료")
        print_info(f"  - 기간: {df['timestamp'].min()} ~ {df['timestamp'].max()}")

        return True

    except Exception as e:
        print_error(f"검증 실패: {e}")
        return False


def run_all_checks():
    """모든 검증 실행"""
    print(f"\n{Colors.BLUE}{'='*70}")
    print(f"  스케줄러 통합 검증 시작")
    print(f"  Backend: {BACKEND_URL}")
    print(f"  Data Root: {DATA_ROOT}")
    print(f"{'='*70}{Colors.RESET}\n")

    results = {
        'backend_health': False,
        'scheduler_status': False,
        'trigger_success': False,
        'parquet_created': False,
        'data_valid': False
    }

    # Step 1: Backend 헬스 체크
    results['backend_health'] = check_backend_health()
    if not results['backend_health']:
        print_error("\nBackend가 준비되지 않았습니다. 먼저 Backend를 시작하세요.")
        return results

    # Step 2: 스케줄러 상태
    scheduler_status = check_scheduler_status()
    results['scheduler_status'] = scheduler_status is not None

    # Step 3: 즉시 트리거
    job_id = trigger_immediate_job()
    results['trigger_success'] = job_id is not None

    if not results['trigger_success']:
        print_error("\n트리거 실패. Worker가 실행 중인지 확인하세요.")
        return results

    # Step 4: Parquet 파일 생성 대기
    parquet_file = wait_for_parquet_file(job_id)
    results['parquet_created'] = parquet_file is not None

    # Step 5: 데이터 검증
    if results['parquet_created']:
        results['data_valid'] = verify_parquet_data(parquet_file)

    # 최종 결과
    print_section("최종 검증 결과")

    all_passed = all(results.values())

    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check}")

    print()

    if all_passed:
        print_success("모든 검증이 완료되었습니다! 🎉")
        return results

    print_warning("일부 검증에 실패했습니다.")
    return results


if __name__ == '__main__':
    results = run_all_checks()

    # 종료 코드
    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)
