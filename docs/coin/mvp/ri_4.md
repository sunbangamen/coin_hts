# GitHub Issue #4 해결 계획

## 1. 이슈 정보 요약

**이슈 번호:** #4
**제목:** [Phase 1] Task 4: React 폼 유효성 검사 및 데이터 구조 정합성
**상태:** OPEN
**생성일:** 2025-10-31
**예상 소요 시간:** 3시간

### 핵심 메타데이터
- **Labels:** Phase-1, frontend, validation, ux
- **Dependencies:** 없음 (백엔드와 독립적으로 개발 가능)
- **Related Issues:**
  - Task 3: FastAPI 엔드포인트 실제 로직 연결 (백엔드 검증과 일관성 유지)
  - Phase 1 전체 계획: docs/coin/mvp/phase1.md

---

## 2. 문제 이해

### 현재 상태
- 백엔드 API (`backend/app/main.py`)는 다음을 제공합니다:
  - `/api/backtests/run` - 백테스트 실행 엔드포인트
  - Pydantic 모델 기반의 서버측 검증 (`BacktestRequest`)
  - 전략 파라미터 검증 로직

- 프론트엔드(`frontend/`)가 생성되어 있으며 핵심 기능이 구현됨:
  - React + Vite 기반 프로젝트 구성 완료
  - `App.jsx`: 실시간 검증, 오류 요약, ARIA 속성
  - `validation.js`: 검증 함수 6개 구현
  - `validation.test.js`: 64개 Vitest 케이스(모두 통과)
  - Docker 기반 테스트(`frontend-test` 서비스) 포함

### 핵심 요구사항
프론트엔드에서 사용자 입력을 백엔드 API 스펙에 맞게 사전 검증하여:
1. **사용자 경험 향상** - 잘못된 입력 시 즉각적인 피드백
2. **불필요한 API 호출 방지** - 네트워크 비용 절감
3. **백엔드 검증과 일관성 유지** - 동일한 검증 규칙 적용

### 검증 대상
1. **심볼 목록**: 최소 1개 이상, 쉼표 구분, 공백 불허
2. **날짜 범위**: start_date ≤ end_date, 미래 날짜 불가
3. **전략 파라미터** (전략별로 다름):
   - `volume_long_candle`: vol_ma_window(정수 ≥1), vol_multiplier(실수 ≥1.0), body_pct(실수 0.0~1.0)
   - `volume_zone_breakout`: volume_window(정수 ≥1), top_percentile(실수 0~1 범위, 예: 0.2), breakout_buffer(실수 ≥0.0)

### 리스크 및 불확실성
- 파라미터 범위 제한 기준이 명확하지 않음 → 비즈니스 도메인 전문가 검토 필요
- 백엔드와 프론트엔드 검증 로직 중복 → 공통 스키마 정의 고려
- 다국어 지원 필요 여부 (현재는 한국어만 가정)

---

## 3. 해결 계획

이 계획은 **프론트엔드를 처음부터 구축**하는 것을 포함합니다.

### **Phase 1~5: 실행 상태 요약**

모든 계획 단계가 완료되었습니다. 각 단계별 주요 결과는 아래와 같습니다.

| Phase | 주요 구현 내용 | 완료 여부 |
|-------|----------------|-----------|
| Phase 1 | React + Vite 프로젝트, 기본 구조, CORS 프록시 | ✅ |
| Phase 2 | `validation.js`와 `validation.test.js` (64개 케이스) | ✅ |
| Phase 3 | `App.jsx` 폼 UI, 상태 관리, 스타일링 | ✅ |
| Phase 4 | 폼 제출 검증 통합, 오류 요약, 실시간 검증, 퍼센트 변환 | ✅ |
| Phase 5 | README 문서화, Docker 테스트 환경, 수동 테스트 체크리스트 | ✅ |

**테스트 확인**
- Vitest: `npm run test` (또는 Docker `frontend-test`) → 64/64 케이스 통과
- Docker 컨테이너: `docker compose run --rm frontend-test`
- 환경 변수로 런타임 디렉터리 지정 가능 (`VITEST_RUNTIME_DIR`)

## 4. 결과 요약 및 후속 제안

### 구현 결과
- 프론트엔드 폼 검증 및 UX 개선 요구사항 모두 구현됨
- Vitest 64개 케이스 통과 (Docker 및 로컬 환경에서 검증)
- Docker 기반 테스트 자동화 구성 완료
- README에 실행 방법/트러블슈팅 문서화

### 추천 후속 작업
1. **출시 준비**
   - Issue #4 상태를 CLOSED로 변경
   - 관련 PR 병합 및 배포 스크립트 동기화
2. **추가 개선 아이디어**
   - 백엔드와 프론트엔드 검증 로직 공통 스키마화 검토
   - 다국어 화면(예: 영어) 필요 여부 검토
   - UI 라이브러리 도입 여부 재검토 (디자인 일관성 강화)

## 5. 예상 위험 요소 및 대응 방안

| 위험 요소 | 발생 가능성 | 영향도 | 대응 방안 |
|---------|---------|-------|---------|
| 백엔드 API와 검증 로직 불일치 | 중간 | 높음 | 백엔드 Pydantic 모델과 정기적으로 동기화, 단위 테스트 작성 |
| 파라미터 범위 기준 불명확 | 중간 | 중간 | 비즈니스 확인 후 범위 상향 조정, 유효성 경고 표시 |
| 브라우저 호환성 문제 | 낮음 | 중간 | 주요 브라우저 테스트(Chrome, Firefox, Safari) |
| Docker 환경 의존성 | 낮음 | 중간 | CI/CD에서 동일한 이미지를 사용하여 일관성 유지 |

## 6. 최종 체크리스트 (완료)

- [x] `frontend/` 디렉토리 및 기본 구조 생성
- [x] `frontend/src/validation.js` - 모든 검증 함수 구현
- [x] `frontend/src/App.jsx` - 폼 UI, 오류 요약, 실시간 검증
- [x] `top_percentile` 안내 문구 및 퍼센트→소수 변환 동작 확인
- [x] 심볼 입력, 날짜 범위, 전략별 파라미터 검증 확인
- [x] 제출 버튼 활성화/비활성화 로직 검증
- [x] 오류 메시지 UI 표시 확인
- [x] `npm run test` / Docker 테스트 통과 확인
- [x] 콘솔 경고 없음 확인
- [x] `frontend/README.md` 작성 및 실행 가이드 완료
- [x] Docker 기반 테스트 서비스 구성

모든 요구사항이 충족되었습니다.
