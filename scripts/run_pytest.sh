#!/bin/bash
# Phase 3 테스트 실행 및 결과 저장 스크립트
#
# 사용법: ./scripts/run_pytest.sh
# 결과는 /tmp/test_results_<timestamp>.json에 저장됩니다.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%s)
RESULT_FILE="/tmp/test_results_${TIMESTAMP}.json"

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
python -m pytest tests/ \
  --tb=short \
  --quiet \
  --ignore=tests/test_s3_storage.py \
  -v 2>&1 | tee /tmp/test_results_${TIMESTAMP}.log

# 결과 파일 생성
PASS_COUNT=$(grep -c "PASSED" /tmp/test_results_${TIMESTAMP}.log || echo "0")
FAIL_COUNT=$(grep -c "FAILED" /tmp/test_results_${TIMESTAMP}.log || echo "0")
TOTAL_COUNT=$((PASS_COUNT + FAIL_COUNT))

# JSON 결과 생성
cat > "$RESULT_FILE" << EOF
{
  "timestamp": "$TIMESTAMP",
  "date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "total_tests": $TOTAL_COUNT,
  "passed": $PASS_COUNT,
  "failed": $FAIL_COUNT,
  "pass_rate": $(echo "scale=2; $PASS_COUNT * 100 / $TOTAL_COUNT" | bc)%,
  "command": "python -m pytest tests/ --ignore=tests/test_s3_storage.py -q --tb=short",
  "log_file": "/tmp/test_results_${TIMESTAMP}.log"
}
EOF

echo ""
echo "✅ 테스트 완료!"
echo "📊 결과 요약:"
echo "  - 총 테스트: $TOTAL_COUNT"
echo "  - 통과: $PASS_COUNT"
echo "  - 실패: $FAIL_COUNT"
echo "  - 통과율: $(echo "scale=1; $PASS_COUNT * 100 / $TOTAL_COUNT" | bc)%"
echo ""
echo "💾 결과 저장:"
echo "  - JSON: $RESULT_FILE"
echo "  - Log: /tmp/test_results_${TIMESTAMP}.log"
echo ""
echo "📝 다음 단계: python scripts/generate_phase3_status.py --input $RESULT_FILE --update-docs"
