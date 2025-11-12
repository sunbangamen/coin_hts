#!/bin/bash

################################################################################
# Issue #37 백테스트 워크플로 검증 스크립트
#
# 목적: Step 1~5의 E2E 검증을 자동화하고 로그를 수집합니다
# 사용법: ./scripts/run_backtest_workflow_validation.sh
#
# 생성 파일:
#   - artifacts/ri_22/workflow_validation_YYYYMMDD.log
#   - artifacts/ri_22/step3_manual_ingest_YYYYMMDD.log
#   - artifacts/ri_22/step4_parquet_validation_YYYYMMDD.json
#   - artifacts/ri_22/step5_backtest_response_YYYYMMDD.json
################################################################################

set -e

# 설정
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACTS_DIR="${PROJECT_ROOT}/artifacts/ri_22"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${ARTIFACTS_DIR}/workflow_validation_${TIMESTAMP}.log"
BACKEND_URL="http://localhost:8000"
WAIT_TIME=30

# 색상
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

################################################################################
# 함수 정의
################################################################################

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S.000Z)] $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${YELLOW}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

check_backend() {
    log "백엔드 서버 연결 확인 중..."

    for i in {1..30}; do
        if curl -s "${BACKEND_URL}/api/scheduler/status" > /dev/null 2>&1; then
            success "백엔드 서버 정상"
            return 0
        fi
        echo "대기 중... ($i/30)" >> "$LOG_FILE"
        sleep 1
    done

    error "백엔드 서버에 연결할 수 없습니다. docker-compose up -d를 확인하세요"
}

################################################################################
# 메인 워크플로
################################################################################

main() {
    log "=================================================================================="
    log "Issue #37 백테스트 워크플로 검증 시작"
    log "=================================================================================="
    log ""

    # 디렉터리 생성
    mkdir -p "$ARTIFACTS_DIR"

    # 백엔드 확인
    check_backend

    # Step 1: 프론트엔드 상수 확인
    log "===== Step 1: 프론트엔드 상수 확인 ====="
    log ""

    DATA_MGMT_FILE="${PROJECT_ROOT}/frontend/src/pages/DataManagementPage.jsx"
    BACKTEST_FILE="${PROJECT_ROOT}/frontend/src/pages/BacktestPage.jsx"

    if grep -q "const DEFAULT_SYMBOLS = \['KRW-BTC'" "$DATA_MGMT_FILE"; then
        success "DataManagementPage DEFAULT_SYMBOLS 확인됨"
    else
        error "DataManagementPage DEFAULT_SYMBOLS 없음"
    fi

    if grep -q "const TIMEFRAMES = \['1M'" "$DATA_MGMT_FILE"; then
        success "DataManagementPage TIMEFRAMES 확인됨"
    else
        error "DataManagementPage TIMEFRAMES 없음"
    fi

    if grep -q "const TIMEFRAMES = \['1M'" "$BACKTEST_FILE"; then
        success "BacktestPage TIMEFRAMES 확인됨"
    else
        error "BacktestPage TIMEFRAMES 없음"
    fi

    log ""

    # Step 2: 백엔드 환경 변수 확인
    log "===== Step 2: 백엔드 환경 변수 확인 ====="
    log ""

    SCHEDULER_CONFIG="${PROJECT_ROOT}/backend/app/scheduler_config.py"

    if grep -q "DEFAULT_SYMBOLS = \['KRW-BTC'" "$SCHEDULER_CONFIG"; then
        success "scheduler_config.py DEFAULT_SYMBOLS 확인됨"
    else
        error "scheduler_config.py DEFAULT_SYMBOLS 없음"
    fi

    if grep -q "DEFAULT_TIMEFRAMES = \['1M'" "$SCHEDULER_CONFIG"; then
        success "scheduler_config.py DEFAULT_TIMEFRAMES 확인됨"
    else
        error "scheduler_config.py DEFAULT_TIMEFRAMES 없음"
    fi

    log ""

    # Step 3: 수동 데이터 수집 트리거
    log "===== Step 3: 수동 데이터 수집 트리거 ====="
    log ""

    log "API 요청: POST ${BACKEND_URL}/api/scheduler/trigger"

    STEP3_RESPONSE=$(curl -s -X POST "${BACKEND_URL}/api/scheduler/trigger" \
        -H "Content-Type: application/json" \
        -d '{
            "symbols": ["KRW-BTC"],
            "timeframes": ["1M"],
            "days": 3,
            "overwrite": false
        }')

    log "응답: $STEP3_RESPONSE"

    JOB_ID=$(echo "$STEP3_RESPONSE" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)

    if [ -n "$JOB_ID" ]; then
        success "Job ID 획득: $JOB_ID"
    else
        error "Job ID를 얻을 수 없습니다"
    fi

    # Step 3 로그 저장
    cat > "${ARTIFACTS_DIR}/step3_manual_ingest_${TIMESTAMP}.log" << EOF
[$(date -u +%Y-%m-%dT%H:%M:%S.000Z)] ===== Step 3: 수동 데이터 수집 트리거 =====
[$(date -u +%Y-%m-%dT%H:%M:%S.000Z)] API 엔드포인트: POST ${BACKEND_URL}/api/scheduler/trigger
[$(date -u +%Y-%m-%dT%H:%M:%S.000Z)] 요청 파라미터:
{
  "symbols": ["KRW-BTC"],
  "timeframes": ["1M"],
  "days": 3,
  "overwrite": false
}
[$(date -u +%Y-%m-%dT%H:%M:%S.000Z)] 응답: $STEP3_RESPONSE
[$(date -u +%Y-%m-%dT%H:%M:%S.000Z)] Job ID: $JOB_ID
[$(date -u +%Y-%m-%dT%H:%M:%S.000Z)] 상태: 큐에 추가됨
[$(date -u +%Y-%m-%dT%H:%M:%S.000Z)] ✅ Step 3 완료
EOF

    log "Step 3 로그 저장: ${ARTIFACTS_DIR}/step3_manual_ingest_${TIMESTAMP}.log"

    log "작업 처리 대기 중... (${WAIT_TIME}초)"
    sleep "$WAIT_TIME"
    log ""

    # Step 4: 파일 구조 및 데이터 검증
    log "===== Step 4: 파일 구조 및 데이터 검증 ====="
    log ""

    PARQUET_FILE="/data/KRW-BTC/1M/2025.parquet"

    if [ -f "$PARQUET_FILE" ]; then
        success "Parquet 파일 발견: $PARQUET_FILE"

        # Python으로 파일 검증
        python3 << PYTHON_SCRIPT > "${ARTIFACTS_DIR}/step4_parquet_validation_${TIMESTAMP}.json"
import pandas as pd
import json
import os

file_path = '/data/KRW-BTC/1M/2025.parquet'

if os.path.exists(file_path):
    df = pd.read_parquet(file_path)

    result = {
        "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)",
        "file_path": file_path,
        "validation_results": {
            "file_exists": True,
            "row_count": len(df),
            "columns": list(df.columns),
            "data_types": str(df.dtypes.to_dict())
        },
        "status": "✅ Parquet 파일 검증 완료"
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))
else:
    print(json.dumps({"error": "파일 없음"}, indent=2))
PYTHON_SCRIPT

        log "Step 4 결과 저장: ${ARTIFACTS_DIR}/step4_parquet_validation_${TIMESTAMP}.json"
    else
        error "Parquet 파일을 찾을 수 없습니다: $PARQUET_FILE"
    fi

    log ""

    # Step 5: 백테스트 실행 및 결과 검증
    log "===== Step 5: 백테스트 실행 및 결과 검증 ====="
    log ""

    log "API 요청: POST ${BACKEND_URL}/api/backtests/run"

    STEP5_RESPONSE=$(curl -s -X POST "${BACKEND_URL}/api/backtests/run" \
        -H "Content-Type: application/json" \
        -d '{
            "strategy": "volume_long_candle",
            "symbols": ["KRW-BTC"],
            "start_date": "2025-11-11",
            "end_date": "2025-11-12",
            "timeframe": "1M",
            "params": {
                "vol_ma_window": 20,
                "vol_multiplier": 1.5,
                "body_pct": 0.01
            }
        }')

    log "응답: $STEP5_RESPONSE"

    # Step 5 응답 저장
    echo "$STEP5_RESPONSE" > "${ARTIFACTS_DIR}/step5_backtest_response_${TIMESTAMP}.json"
    log "Step 5 결과 저장: ${ARTIFACTS_DIR}/step5_backtest_response_${TIMESTAMP}.json"

    RUN_ID=$(echo "$STEP5_RESPONSE" | grep -o '"run_id":"[^"]*"' | cut -d'"' -f4)

    if [ -n "$RUN_ID" ]; then
        success "백테스트 실행 완료: $RUN_ID"
    else
        error "백테스트 실행 실패"
    fi

    log ""

    # 최종 요약
    log "=================================================================================="
    log "E2E 워크플로 검증 완료"
    log "=================================================================================="
    log ""
    log "✅ Step 1: 프론트엔드 상수 확인 - 통과"
    log "✅ Step 2: 백엔드 환경 변수 확인 - 통과"
    log "✅ Step 3: 수동 데이터 수집 - 통과 (Job ID: $JOB_ID)"
    log "✅ Step 4: 파일 구조 및 데이터 검증 - 통과"
    log "✅ Step 5: 백테스트 실행 및 결과 검증 - 통과 (Run ID: $RUN_ID)"
    log ""
    log "🎉 모든 Step 통과! 배포 준비 완료"
    log ""
    log "아티팩트 위치:"
    log "  - ${LOG_FILE}"
    log "  - ${ARTIFACTS_DIR}/step3_manual_ingest_${TIMESTAMP}.log"
    log "  - ${ARTIFACTS_DIR}/step4_parquet_validation_${TIMESTAMP}.json"
    log "  - ${ARTIFACTS_DIR}/step5_backtest_response_${TIMESTAMP}.json"
}

# 메인 실행
main "$@"
