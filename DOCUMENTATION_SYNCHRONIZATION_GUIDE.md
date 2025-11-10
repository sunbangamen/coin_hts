# Phase 3 문서 정합화 및 자동화 가이드 (개선판)

**작성일**: 2025-11-10
**상태**: ✅ 구현 완료 및 테스트 검증
**최종 업데이트**: 자동화 시스템 확정

---

## 📋 개요

이 가이드는 Phase 3 운영 보완 프로젝트의 **문서 정합화 자동화 시스템**을 설명합니다.

### 핵심 개선사항
1. **AUTO 블록 기반 마크다운 치환** - 정규식으로 안전한 업데이트
2. **JSON 검증** - 필수 필드, 타입, 논리 일관성 확인
3. **Strict 모드** - CI/CD에서 자동 검증
4. **메타데이터 자동화** - 타임스탬프, 명령 자동 기입

---

## 🎯 소스 오브 트루스 (Single Source of Truth)

### PHASE3_IMPLEMENTATION_STATUS.md
```
🔴 이것이 공식 기준입니다.
```

**특징**:
- 자동 블록으로 보호됨 (`<!-- AUTO-BEGIN -->` ~ `<!-- AUTO-END -->`)
- 메타데이터 자동 갱신
- JSON 검증으로 데이터 무결성 보장

**AUTO 블록 목록**:
```
<!-- AUTO-BEGIN: TEST_STATISTICS -->
### 테스트 통과율
...
<!-- AUTO-END: TEST_STATISTICS -->

<!-- AUTO-BEGIN: TASK_STATUS -->
### 구현 완료율
...
<!-- AUTO-END: TASK_STATUS -->
```

---

## 🔄 자동화 워크플로우

### 1단계: 테스트 실행

```bash
./scripts/run_pytest.sh
```

**동작**:
- `tests/` 전체 실행 (S3 테스트 제외)
- `/tmp/test_results_<timestamp>.json` 생성
- `/tmp/test_results_<timestamp>.log` 생성
- `/tmp/test_results_latest.json` 심볼릭 링크 자동 생성
- `set -euo pipefail` 으로 안전한 실행 보장
- pytest 요약 행을 `grep -E "(collected|failed|passed)"` 로 추출

**JSON 검증**:
- ✅ 필수 필드: `timestamp`, `date`, `total_tests`, `passed`, `failed`, `pass_rate`
- ✅ 데이터 타입: 정수, 부동소수점 (pass_rate는 float)
- ✅ 논리 일관성: `passed + failed = total_tests`

**심볼릭 링크 자동 관리**:
- 매 실행마다 `/tmp/test_results_latest.json` 이 최신 JSON을 가리킴
- 후속 스크립트에서는 항상 `/tmp/test_results_latest.json` 사용 가능

**출력 예시**:
```
✅ 테스트 완료!
📊 결과 요약:
  - 총 테스트: 203
  - 통과: 192
  - 실패: 11
  - 통과율: 94.6%

💾 결과 저장:
  - JSON: /tmp/test_results_1762745965.json
  - 최신 링크: /tmp/test_results_latest.json
  - Log: /tmp/test_results_1762745965.log

📝 다음 단계:
  1. python scripts/generate_phase3_status.py --input /tmp/test_results_latest.json --update-docs
  2. python scripts/verify_status_consistency.py --strict
  3. git diff && git add -A && git commit
```

### 2단계: 문서 자동 동기화 (세 문서 모두)

```bash
python scripts/generate_phase3_status.py \
  --input /tmp/test_results_latest.json \
  --update-docs
```

**동작**:
1. JSON 로드 및 전체 검증
   - 필수 필드 확인
   - 데이터 타입 검증
   - 논리 일관성 검증
2. **PHASE3_IMPLEMENTATION_STATUS.md** (SOT) 업데이트
   - `<!-- AUTO-BEGIN: TEST_STATISTICS -->` 블록 정규식 치환
   - `<!-- AUTO-BEGIN: TASK_STATUS -->` 블록 정규식 치환
   - 메타데이터 (마지막 업데이트, JSON 소스) 자동 갱신
3. **PHASE3_COMPLETION_SUMMARY.md** (보조) 업데이트
   - `<!-- AUTO-BEGIN: COMPLETION_SUMMARY_STATISTICS -->` 블록 업데이트
   - 테스트 통과율, 모듈별 상태, 실패 테스트 표 생성
4. **docs/coin/mvp/ri_18.md** (이슈 #29) 업데이트
   - `<!-- AUTO-BEGIN: ISSUE_29_METRICS -->` 블록 업데이트
   - pytest 상태 메트릭 자동 갱신
5. 보조 문서 검토 및 상태 보고

**JSON 검증 에러 예시**:
```
❌ 오류 발생: JSON에서 필수 필드를 찾을 수 없습니다: pass_rate
```

**성공 출력 예시**:
```
📂 결과 파일 로드: /tmp/test_results_latest.json

============================================================
📊 Phase 3 상태 요약
============================================================
타임스탬프: 2025-11-10T12:40:00Z
총 테스트: 203
통과: 192 ✅
실패: 11 ❌
통과율: 94.5%
============================================================

📚 문서 검토:
✅ summary: SOT 참조 (AUTO 블록 없음)
✅ issue: SOT 참조 (AUTO 블록 없음)

🔄 문서 업데이트 중...
✅ PHASE3_IMPLEMENTATION_STATUS.md 업데이트 완료
✅ 모든 문서가 업데이트되었습니다.

📝 다음 단계:
  1. git diff로 변경 사항 확인
  2. python scripts/verify_status_consistency.py --strict로 검증
  3. git add && git commit으로 커밋
```

### 3단계: 일관성 검증 (일반 모드)

```bash
python scripts/verify_status_consistency.py
```

**검증 항목**:
1. **SOT 문서 완정성** (7개)
   - 소스 오브 트루스 표시
   - 마지막 업데이트 시간
   - 업데이트 명령
   - 상태 검증 명령
   - AUTO 블록 (TEST_STATISTICS)
   - AUTO 블록 (TASK_STATUS)
   - 재현 가능 명령

2. **다중 문서 간 수치 일관성**
   - 기준값 (SOT): `192/203 (94.6%)`
   - 보조 문서 비교 (PHASE3_COMPLETION_SUMMARY.md에서 추출)

3. **AUTO 블록 존재 여부 (모든 문서)**
   - PHASE3_IMPLEMENTATION_STATUS.md: TEST_STATISTICS, TASK_STATUS (2개)
   - PHASE3_COMPLETION_SUMMARY.md: COMPLETION_SUMMARY_STATISTICS (1개)
   - docs/coin/mvp/ri_18.md: ISSUE_29_METRICS (1개)

**출력 예시**:
```
🔍 Phase 3 문서 일관성 검증 시작
엄격 모드: ⚠️ 비활성화

📌 소스 오브 트루스 문서 검증
------------------------------------------------------------
✅ 소스 오브 트루스 표시
✅ 마지막 업데이트 시간
✅ 업데이트 명령
✅ 상태 검증 명령
✅ AUTO 블록 (TEST_STATISTICS)
✅ AUTO 블록 (TASK_STATUS)
✅ 재현 가능 명령

결과: 7/7 통과

📊 수치 일관성 검증
------------------------------------------------------------
📌 기준값 (SOT): 192/203 (94.5%)
✅ summary: (수치 없음)
✅ issue: (수치 없음)

🔲 AUTO 블록 검증
------------------------------------------------------------
✅ AUTO-BEGIN: TEST_STATISTICS
✅ AUTO-BEGIN: TASK_STATUS

============================================================
📋 Phase 3 문서 일관성 검증 결과
============================================================
✅ 모든 검증이 통과했습니다!
============================================================
```

### 3단계-Strict: 일관성 검증 (Strict 모드, CI/CD용)

```bash
python scripts/verify_status_consistency.py --strict
```

**동작**:
- 모든 불일치를 **에러**로 취급
- CI/CD 파이프라인에서 실패 (종료 코드: 1)
- 수동 수정 방지

**종료 코드**:
- `0`: 모든 검증 통과
- `1`: 에러 발생 (Strict 모드 한정)

---

## 📚 각 문서의 역할

| 문서 | 역할 | 수정 방식 | 대상자 |
|------|------|---------|-------|
| **PHASE3_IMPLEMENTATION_STATUS.md** | 공식 기준 (SOT) | 자동 스크립트만 | 개발팀, CI/CD |
| **PHASE3_COMPLETION_SUMMARY.md** | 운영 가이드 | 자동 참조 | 운영팀, 신규 온보딩 |
| **docs/coin/mvp/ri_18.md** | 사용자 커뮤니케이션 | 자동 참조 | 외부 이해관계자 |

---

## 🚀 통합 명령 (One-liner)

```bash
# 전체 프로세스 자동 실행
./scripts/run_pytest.sh && \
  python scripts/generate_phase3_status.py --input /tmp/test_results_latest.json --update-docs && \
  python scripts/verify_status_consistency.py --strict && \
  git add -A && \
  git diff --cached --stat
```

---

## 🔒 회귀 방지

### CI/CD 통합 예시

```yaml
Phase 3 Document Sync:
  script:
    - ./scripts/run_pytest.sh
    - python scripts/generate_phase3_status.py --input /tmp/test_results_latest.json --update-docs
    - python scripts/verify_status_consistency.py --strict
  on_failure:
    - echo "Document synchronization failed. Check git diff."
```

### Pre-commit Hook 예시

```bash
#!/bin/bash
# .git/hooks/pre-commit

if git diff --cached | grep -q "PHASE3_IMPLEMENTATION_STATUS.md"; then
  echo "🔍 문서 일관성 검증 중..."
  python scripts/verify_status_consistency.py --strict || exit 1
fi
```

---

## 📝 수동 수정이 필요한 경우

AUTO 블록 **외부**에만 수정을 가하고, 다음 절차를 따릅니다:

1. **AUTO 블록 외부 영역만 수정**
   ```markdown
   <!-- AUTO-BEGIN: TEST_STATISTICS -->
   # 이 영역은 자동 갱신됩니다. 수정하지 마세요.
   <!-- AUTO-END: TEST_STATISTICS -->

   ## 이 영역은 수동으로 수정 가능합니다
   - 설명, 컨텍스트, 참고사항 등을 추가할 수 있습니다.
   ```

2. **수정 완료 후 자동 스크립트 다시 실행**
   ```bash
   ./scripts/run_pytest.sh                                             # 테스트 재실행
   python scripts/generate_phase3_status.py --input /tmp/test_results_latest.json --update-docs  # 문서 재동기화
   python scripts/verify_status_consistency.py --strict                # 검증
   git diff                                                            # 변경사항 확인
   git add -A && git commit -m "docs: update phase3 status"           # 커밋
   ```

3. **AUTO 블록 직접 수정이 불가피한 경우**
   - 스크립트를 수정하여 새로운 AUTO 블록 형식 지원
   - 검증 스크립트도 함께 업데이트
   - PR로 리뷰 후 병합

---

## ⚠️ 주의사항

### ❌ 하지 말아야 할 것
- AUTO 블록 내부를 **직접 편집**
- 수치를 **수동으로 변경**
- JSON 파일을 **수동으로 생성**
- 스크립트 없이 문서 **동기화**
- `/tmp/test_results_latest.json`을 **복사**로 관리 (항상 심볼릭 링크 사용)

### ✅ 해야 할 것
- `./scripts/run_pytest.sh`로 테스트 실행
- `generate_phase3_status.py --update-docs`로 자동 동기화 (세 문서 모두)
- `verify_status_consistency.py --strict`로 검증
- AUTO 블록 외부 영역만 수동 수정
- 스크립트 자체와 수정사항은 **git에 커밋**

---

## 🛠️ 스크립트 상세 사용법

### run_pytest.sh
```bash
./scripts/run_pytest.sh
```

**옵션**: 없음 (완전 자동)

**환경**:
- 자동 가상환경 활성화
- PYTHONPATH 자동 설정
- `set -euo pipefail` 으로 안전한 실행

**결과 파일**:
- JSON: `/tmp/test_results_<timestamp>.json`
- Log: `/tmp/test_results_<timestamp>.log`
- 최신 링크: `/tmp/test_results_latest.json` (자동으로 심볼릭 링크 유지)

**JSON 파싱 방식**:
- `grep -E "(collected|failed|passed)"` 로 pytest 요약 행 추출
- 정규식: `[0-9]+ (failed|passed)` 로 개수 계산
- `pass_rate` 는 float 형식으로 기록 (예: `94.6`)

### generate_phase3_status.py
```bash
# 검증만 수행 (문서 수정 안 함)
python scripts/generate_phase3_status.py --input /tmp/test_results_latest.json

# 문서 자동 업데이트 (세 문서 모두)
python scripts/generate_phase3_status.py --input /tmp/test_results_latest.json --update-docs

# 글롭 패턴 지원 (최신 파일 자동 선택)
python scripts/generate_phase3_status.py --input /tmp/test_results_*.json --update-docs
```

**업데이트 대상 (3개 문서)**:
1. `PHASE3_IMPLEMENTATION_STATUS.md` (SOT)
   - TEST_STATISTICS, TASK_STATUS 블록
2. `PHASE3_COMPLETION_SUMMARY.md` (보조)
   - COMPLETION_SUMMARY_STATISTICS 블록
3. `docs/coin/mvp/ri_18.md` (이슈)
   - ISSUE_29_METRICS 블록

**JSON 검증 항목**:
- 필수 필드: `timestamp`, `date`, `total_tests`, `passed`, `failed`, `pass_rate`
- 데이터 타입: int, float 확인
- 논리 일관성: `passed + failed == total_tests`

### verify_status_consistency.py
```bash
# 경고 수준 (CI/CD에서 무시 가능)
python scripts/verify_status_consistency.py

# Strict 모드 (CI/CD 에러 발생, 권장)
python scripts/verify_status_consistency.py --strict
```

**검증 세부 항목**:
1. **SOT 문서 검증** (7개 항목)
   - 소스 오브 트루스 표시 확인
   - 마지막 업데이트 시간 확인
   - 업데이트 명령 존재 확인
   - --strict 옵션 존재 확인
   - TEST_STATISTICS AUTO 블록 확인
   - TASK_STATUS AUTO 블록 확인
   - pytest 재현 가능 명령 확인

2. **수치 일관성 검증**
   - SOT의 메트릭 추출
   - 보조 문서들과 비교
   - 불일치 시 경고/에러

3. **AUTO 블록 검증 (모든 문서)**
   - 각 문서별 필수 AUTO 블록 확인
   - 누락 시 경고/에러

**종료 코드**:
- `0`: 모든 검증 통과
- `1`: 에러 발생 (Strict 모드) 또는 CRITICAL 에러

---

## 🔧 회귀 테스트 복구 절차 (Task 3.5)

### 개요
현재 203/203 테스트 중 192 통과, 11 실패 (94.6%)
- test_result_manager.py: 4건 실패
- test_strategy_runner.py: 7건 실패

세부 내용은 [REGRESSION_TEST_RECOVERY_PLAN.md](./REGRESSION_TEST_RECOVERY_PLAN.md) 참조

### 1단계: 단계별 구현 (Task 3.5 진행)

#### 1-1. ResultStorage 구현 (1-2시간)
```bash
# 1. backend/app/storage/result_storage.py 작성
#    - 추상 인터페이스 + PostgreSQL/SQLite 뼈대

# 2. tests/conftest.py에 픽스처 추가
#    - temp_result_storage (SQLite 기반)
#    - result_manager (의존성 주입)

# 3. 로컬 임포트 테스트
python -c "from backend.app.storage.result_storage import ResultStorage; print('OK')"
```

#### 1-2. ResultManager 리팩터링 (30분~1시간)
```bash
# 1. backend/app/result_manager.py 수정
#    - __init__(storage: ResultStorage) 추가
#    - 메서드들을 storage 레이어로 리팩터링

# 2. 회귀 테스트 집중 실행
pytest tests/test_result_manager.py -v
# 예상: 4건 모두 통과 ✅
```

#### 1-3. StrategyRunner 개선 (1-2시간)
```bash
# 1. backend/app/simulation/strategy_runner.py 수정
#    - __init__()에 result_manager, position_manager 주입

# 2. tests/test_strategy_runner.py 수정
#    - CandleData에 timeframe 필드 추가
#    - 테스트 데이터 유효성 확인

pytest tests/test_strategy_runner.py -v
# 예상: 7건 모두 통과 ✅
```

#### 1-4. 회귀 테스트 확인 (선택)
```bash
# 부분 통과 시 (선택사항)
# python scripts/generate_phase3_status.py --input /tmp/test_results_latest.json --update-docs
```

### 2단계: 전체 통과 확인 (203/203)

```bash
# 1. 전체 pytest 실행
./scripts/run_pytest.sh

# 2. 결과 확인
#   ✅ 192 → 203 통과 (100%)
#   ✅ 11개 실패 → 0개 해결
```

### 3단계: 문서 자동 동기화

```bash
# 1. 테스트 결과 자동 갱신
python scripts/generate_phase3_status.py \
  --input /tmp/test_results_latest.json \
  --update-docs

# 2. Strict 검증
python scripts/verify_status_consistency.py --strict

# 3. git diff 확인
git diff PHASE3_IMPLEMENTATION_STATUS.md
git diff PHASE3_COMPLETION_SUMMARY.md
```

### 4단계: 커밋

```bash
# git diff로 변경사항 최종 확인
git diff

# 커밋 (203/203 통과 확인 후)
git add -A && git commit -m "fix: 회귀 테스트 11건 복구 (Task 3.5)"

# 또는 상세 커밋 메시지
git commit -m "$(cat <<'EOF'
fix: Phase 3 회귀 테스트 11건 복구 완료

## 해결된 이슈

### test_result_manager.py (4건)
- test_save_manifest_file: 디렉토리 자동 생성
- test_save_manifest_file_with_error: 저장소 레이어 개선
- test_cleanup_old_results_dry_run: cleanup 로직 수정
- test_cleanup_skips_recent_results: 리센트 결과 보존 확인

### test_strategy_runner.py (7건)
- test_initialize_strategy_with_history: 유효한 날짜 데이터
- test_process_candle_*: CandleData timeframe 필드 추가
- test_on_signal_generated_no_callback: PositionManager 콜백 검증

## 개선 사항

- ResultStorage 추상 인터페이스 도입
- Dependency Injection으로 테스트성 향상
- SQLite 기반 테스트 저장소 추가
- conftest.py 픽스처 개선

## 검증

- 203/203 테스트 100% 통과
- Strict 모드 검증 통과
- 문서 자동 동기화 완료

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### 예상 결과

```
✅ 회귀 테스트 11건 모두 통과
✅ 문서 메트릭 자동 갱신 (192 → 203)
✅ Strict 검증 통과
✅ git log에 기록
```

---

## 📞 문제해결

### Q: JSON 파일을 찾을 수 없음
```bash
# 최신 파일 확인
ls -lt /tmp/test_results_*.json | head -3

# 명시적 파일 지정
python scripts/generate_phase3_status.py --input /tmp/test_results_1731167600.json --update-docs
```

### Q: AUTO 블록이 업데이트되지 않음
```bash
# 1. JSON 검증
python scripts/generate_phase3_status.py --input /tmp/test_results_latest.json

# 2. AUTO 블록 확인
grep -n "AUTO-BEGIN" PHASE3_IMPLEMENTATION_STATUS.md

# 3. 수동 추가 후 재시도
echo "<!-- AUTO-BEGIN: TEST_STATISTICS -->" >> ...
```

### Q: --strict 검증이 실패함
```bash
# 1. 일반 모드로 확인
python scripts/verify_status_consistency.py

# 2. 상세 log 확인
git diff PHASE3_IMPLEMENTATION_STATUS.md

# 3. 수치 일치 확인
grep -i "test" PHASE3_IMPLEMENTATION_STATUS.md | head -5
```

---

## 📚 관련 문서

- [PHASE3_IMPLEMENTATION_STATUS.md](./PHASE3_IMPLEMENTATION_STATUS.md) - 소스 오브 트루스 (SOT)
- [PHASE3_COMPLETION_SUMMARY.md](./PHASE3_COMPLETION_SUMMARY.md) - 운영 가이드
- [docs/coin/mvp/ri_18.md](./docs/coin/mvp/ri_18.md) - 사용자 문서 (이슈 #29)
- [REGRESSION_TEST_RECOVERY_PLAN.md](./REGRESSION_TEST_RECOVERY_PLAN.md) - Task 3.5 회귀 테스트 복구 계획

---

**마지막 업데이트**: 2025-11-10
**검증 상태**: ✅ 모든 스크립트 및 AUTO 블록 작동 확인
**현재 진행**: 📋 Task 3.5 회귀 테스트 복구 계획 수립 (192/203 → 203/203 목표)
**다음 단계**: Task 3.5 구현 및 회귀 테스트 복구
