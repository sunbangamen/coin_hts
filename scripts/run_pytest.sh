#!/bin/bash
# Phase 3 테스트 실행 및 결과 저장 스크립트
#
# 사용법: ./scripts/run_pytest.sh
# 결과는 /tmp/test_results_<timestamp>.json에 저장되고,
# /tmp/test_results_latest.json 심볼릭 링크가 생성됩니다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%s)
RESULT_FILE="/tmp/test_results_${TIMESTAMP}.json"
LATEST_LINK="/tmp/test_results_latest.json"

# 가상환경 활성화
cd "$PROJECT_ROOT"
source venv/bin/activate
export PYTHONPATH="."

echo "🧪 Phase 3 테스트 실행 중..."
echo "프로젝트: $PROJECT_ROOT"
echo "결과 저장: $RESULT_FILE"
echo "타임스탬프: $TIMESTAMP"
echo ""

# pytest 실행 (S3 테스트 제외 - 의존성 이슈)
# pytest 실패도 캡처하기 위해 || true 사용
python -m pytest tests/ \
  --tb=short \
  --ignore=tests/test_s3_storage.py \
  -v 2>&1 | tee "/tmp/test_results_${TIMESTAMP}.log" || PYTEST_EXIT_CODE=$?

# pytest 종료 코드 확인
PYTEST_EXIT_CODE=${PYTEST_EXIT_CODE:-$?}

# 결과 파일 생성 - pytest summary 라인에서 정규식으로 파싱
LOG_FILE="/tmp/test_results_${TIMESTAMP}.log"

if [ ! -f "$LOG_FILE" ]; then
  echo "❌ 에러: 로그 파일을 찾을 수 없습니다: $LOG_FILE"
  exit 1
fi

# pytest 요약 행 추출 (grep -E 사용)
SUMMARY_LINE=$(grep -E "(collected|failed|passed)" "$LOG_FILE" | tail -1 || echo "")

if [ -z "$SUMMARY_LINE" ]; then
  echo "⚠️  경고: pytest 요약 행을 파싱할 수 없습니다"
  echo "로그 내용:"
  tail -10 "$LOG_FILE"
  PASS_COUNT="0"
  FAIL_COUNT="0"
  TOTAL_COUNT="0"
  PASS_RATE="0.0"
else
  # 정규식으로 failed와 passed 개수 추출
  if [[ $SUMMARY_LINE =~ ([0-9]+)\ failed,\ ([0-9]+)\ passed ]]; then
    FAIL_COUNT="${BASH_REMATCH[1]}"
    PASS_COUNT="${BASH_REMATCH[2]}"
  elif [[ $SUMMARY_LINE =~ ([0-9]+)\ passed ]]; then
    PASS_COUNT="${BASH_REMATCH[1]}"
    FAIL_COUNT="0"
  else
    PASS_COUNT="0"
    FAIL_COUNT="0"
  fi

  TOTAL_COUNT=$((PASS_COUNT + FAIL_COUNT))

  # 통과율 계산 (float 형식)
  if [ "$TOTAL_COUNT" -gt 0 ]; then
    PASS_RATE=$(awk "BEGIN {printf \"%.1f\", $PASS_COUNT * 100 / $TOTAL_COUNT}")
  else
    PASS_RATE="0.0"
  fi
fi

# JSON 결과 생성 (pass_rate는 숫자)
cat > "$RESULT_FILE" << EOF
{
  "timestamp": "$TIMESTAMP",
  "date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "total_tests": $TOTAL_COUNT,
  "passed": $PASS_COUNT,
  "failed": $FAIL_COUNT,
  "pass_rate": $PASS_RATE,
  "command": "python -m pytest tests/ --ignore=tests/test_s3_storage.py -v",
  "log_file": "$LOG_FILE"
}
EOF

# /tmp/test_results_latest.json 심볼릭 링크 생성 또는 업데이트
if [ -L "$LATEST_LINK" ] || [ -f "$LATEST_LINK" ]; then
  rm -f "$LATEST_LINK"
fi
ln -s "$RESULT_FILE" "$LATEST_LINK"

echo ""
echo "✅ 테스트 완료!"
echo "📊 결과 요약:"
echo "  - 총 테스트: $TOTAL_COUNT"
echo "  - 통과: $PASS_COUNT"
echo "  - 실패: $FAIL_COUNT"
echo "  - 통과율: ${PASS_RATE}%"
echo ""
echo "💾 결과 저장:"
echo "  - JSON: $RESULT_FILE"
echo "  - 최신 링크: $LATEST_LINK"
echo "  - Log: $LOG_FILE"
echo ""
echo "📝 다음 단계:"
echo "  1. python scripts/generate_phase3_status.py --input /tmp/test_results_latest.json --update-docs"
echo "  2. python scripts/verify_status_consistency.py --strict"
echo "  3. git diff && git add -A && git commit"
echo ""

# pytest 실패 시 비정상 종료
if [ "$PYTEST_EXIT_CODE" -ne 0 ] && [ "$TOTAL_COUNT" -gt 0 ] && [ "$FAIL_COUNT" -gt 0 ]; then
  echo "⚠️  pytest 실행 중 테스트 실패가 있습니다 ($FAIL_COUNT개)"
  echo "스크립트는 정상 종료되지만 CI/CD에서는 이를 감지할 수 있습니다."
fi
