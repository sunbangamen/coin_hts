#!/usr/bin/env python3
"""
Issue #37 워크플로 아티팩트 검증 스크립트

목적: artifacts/ri_22에 저장된 로그 및 JSON 파일의 유효성을 검증합니다.

사용법: python3 scripts/verify_workflow_artifacts.py
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / 'artifacts' / 'ri_22'

# 색상
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'


def log_success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")


def log_error(msg):
    print(f"{RED}❌ {msg}{RESET}")


def log_warning(msg):
    print(f"{YELLOW}⚠️  {msg}{RESET}")


def log_info(msg):
    print(f"{YELLOW}ℹ️  {msg}{RESET}")


def check_artifacts_directory():
    """artifacts/ri_22 디렉터리 확인"""
    if not ARTIFACTS_DIR.exists():
        log_error(f"artifacts/ri_22 디렉터리 없음: {ARTIFACTS_DIR}")
        return False

    log_success(f"artifacts/ri_22 디렉터리 발견: {ARTIFACTS_DIR}")
    return True


def find_latest_artifact(pattern, extension=None):
    """주어진 패턴과 일치하는 가장 최근 파일 찾기

    Args:
        pattern: 파일명 패턴 (예: "workflow_validation")
        extension: 파일 확장자 (예: ".log", ".json", None=모두)

    Returns:
        가장 최근 파일의 Path 객체 또는 None
    """
    if extension:
        # 특정 확장자만 검색
        matching_files = list(ARTIFACTS_DIR.glob(f"{pattern}_*{extension}"))
    else:
        # .log와 .json 모두 검색
        log_files = list(ARTIFACTS_DIR.glob(f"{pattern}_*.log"))
        json_files = list(ARTIFACTS_DIR.glob(f"{pattern}_*.json"))
        matching_files = log_files + json_files

    matching_files = sorted(matching_files)
    return matching_files[-1] if matching_files else None


def verify_main_log():
    """workflow_validation_*.log 검증"""
    log_file = find_latest_artifact("workflow_validation")

    if not log_file:
        log_error("workflow_validation_*.log 파일 없음")
        return False

    log_success(f"워크플로 로그 발견: {log_file.name}")

    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 필수 키워드 확인
    required_keywords = [
        "Step 1: 프론트엔드 상수 확인",
        "Step 2: 백엔드 환경 변수 확인",
        "Step 3: 수동 데이터 수집 트리거",
        "Step 4: 파일 구조 및 데이터 검증",
        "Step 5: 백테스트 실행 및 결과 검증",
        "Job ID",
        "1762",  # Parquet 행 수
        "✅ Step",
    ]

    missing_keywords = [kw for kw in required_keywords if kw not in content]

    if missing_keywords:
        log_error(f"워크플로 로그에 필수 키워드 부재: {missing_keywords}")
        return False

    log_success("워크플로 로그 내용 검증 통과")
    return True


def verify_step3_log():
    """step3_manual_ingest_*.log 검증"""
    log_file = find_latest_artifact("step3_manual_ingest", extension=".log")

    if not log_file:
        log_warning("step3_manual_ingest_*.log 파일 없음 (선택사항)")
        return True

    log_success(f"Step 3 로그 발견: {log_file.name}")

    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 필수 정보 확인
    required_info = [
        "Job ID",
        "success",
    ]

    missing_info = [info for info in required_info if info not in content]

    if missing_info:
        log_error(f"Step 3 로그에 필수 정보 부재: {missing_info}")
        return False

    log_success("Step 3 로그 내용 검증 통과")
    return True


def verify_step4_json():
    """step4_parquet_validation_*.json 검증"""
    json_file = find_latest_artifact("step4_parquet_validation", extension=".json")

    if not json_file:
        log_warning("step4_parquet_validation_*.json 파일 없음 (선택사항)")
        return True

    log_success(f"Step 4 JSON 발견: {json_file.name}")

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        log_error(f"Step 4 JSON 파싱 오류: {e}")
        return False

    # 필수 필드 확인
    required_fields = [
        'file_path',
        'validation_results',
        'status'
    ]

    missing_fields = [field for field in required_fields if field not in data]

    if missing_fields:
        log_error(f"Step 4 JSON에 필수 필드 부재: {missing_fields}")
        return False

    # 검증 결과 확인
    validation = data.get('validation_results', {})

    if not validation.get('file_exists'):
        log_error("Step 4: Parquet 파일이 없음으로 기록됨")
        return False

    row_count = validation.get('row_count', 0)
    if row_count < 100:
        log_warning(f"Step 4: 행 수가 적음 ({row_count})")

    log_success(f"Step 4 JSON 검증 통과 (행 수: {row_count})")
    return True


def verify_step5_json():
    """step5_backtest_response_*.json 검증"""
    json_file = find_latest_artifact("step5_backtest_response", extension=".json")

    if not json_file:
        log_warning("step5_backtest_response_*.json 파일 없음 (선택사항)")
        return True

    log_success(f"Step 5 JSON 발견: {json_file.name}")

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        log_error(f"Step 5 JSON 파싱 오류: {e}")
        return False

    # 필수 필드 확인
    required_fields = [
        'run_id',
        'strategy',
        'timeframe',
        'symbols',
        'execution_time'
    ]

    # 필드를 두 가지 경로에서 찾기: 최상위 또는 response 하위
    def get_field_value(field_name):
        """최상위 또는 response 하위에서 필드 값 찾기"""
        # 최상위에서 먼저 확인
        if field_name in data:
            return data.get(field_name)
        # response 하위에서 확인
        response = data.get('response', {})
        return response.get(field_name)

    missing_fields = [field for field in required_fields if get_field_value(field) is None]

    if missing_fields:
        log_error(f"Step 5 JSON에 필수 필드 부재: {missing_fields}")
        return False

    # 백테스트 응답 검증
    if data.get('response'):
        response = data['response']
        if not response.get('run_id'):
            log_error("Step 5: run_id 없음")
            return False

    # timeframe 값 출력 (최상위 또는 response 하위 중 실제 값)
    timeframe = get_field_value('timeframe')
    log_success(f"Step 5 JSON 검증 통과 (timeframe: {timeframe})")
    return True


def verify_latest_artifacts():
    """최신 아티팩트 확인"""
    log_info("아티팩트 파일 목록:")

    log_files = sorted(ARTIFACTS_DIR.glob("*.log"))
    json_files = sorted(ARTIFACTS_DIR.glob("*.json"))

    if log_files:
        log_info("로그 파일:")
        for lf in log_files[-3:]:  # 최근 3개
            print(f"  - {lf.name} ({datetime.fromtimestamp(lf.stat().st_mtime).isoformat()})")

    if json_files:
        log_info("JSON 파일:")
        for jf in json_files[-3:]:  # 최근 3개
            print(f"  - {jf.name} ({datetime.fromtimestamp(jf.stat().st_mtime).isoformat()})")


def main():
    """메인 검증 프로세스"""
    print("=" * 80)
    print("Issue #37 워크플로 아티팩트 검증")
    print("=" * 80)
    print()

    # 디렉터리 확인
    if not check_artifacts_directory():
        sys.exit(1)

    print()

    # 아티팩트 파일 목록 확인
    verify_latest_artifacts()
    print()

    # 검증 실행
    all_passed = True

    print("검증 항목:")
    all_passed &= verify_main_log()
    all_passed &= verify_step3_log()
    all_passed &= verify_step4_json()
    all_passed &= verify_step5_json()

    print()
    print("=" * 80)

    if all_passed:
        log_success("모든 아티팩트 검증 통과")
        print("=" * 80)
        sys.exit(0)
    else:
        log_error("일부 아티팩트 검증 실패")
        print("=" * 80)
        sys.exit(1)


if __name__ == '__main__':
    main()
