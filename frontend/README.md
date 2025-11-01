# Coin Backtesting Frontend

코인 백테스팅 플랫폼의 React 프론트엔드 애플리케이션입니다. 사용자가 거래 전략의 파라미터를 입력하고, 백테스트를 실행한 후 결과를 시각화할 수 있습니다.

## 개요

### 기술 스택
- **Framework**: React 18.2
- **Build Tool**: Vite 5.0
- **Testing**: Vitest 1.6
- **HTTP Client**: Axios
- **CSS**: Vanilla CSS3

### 주요 기능

1. **폼 유효성 검사** - 사용자 입력을 실시간으로 검증
2. **동적 파라미터 관리** - 선택된 전략에 따라 파라미터 필드 자동 변경
3. **백테스트 실행** - 백엔드 API와 통신하여 백테스트 실행
4. **결과 표시** - 심볼별 성과 지표를 테이블로 표시

## 설치 및 실행

### 사전 요구사항
- Node.js 16.0 이상
- npm 7.0 이상 (또는 yarn, pnpm)

### 설치

```bash
cd frontend
npm install
```

### 개발 서버 실행

```bash
npm run dev
```

브라우저에서 `http://localhost:3000`으로 접속합니다.

개발 서버는 자동으로 `/api` 경로를 `http://localhost:8000`으로 프록시합니다.

### 프로덕션 빌드

```bash
npm run build
```

빌드된 파일은 `dist/` 디렉토리에 생성됩니다.

### 프로덕션 미리보기

```bash
npm run preview
```

## 프로젝트 구조

```
frontend/
├── src/
│   ├── App.jsx              # 430줄 - 메인 애플리케이션 컴포넌트
│   │   ├─ performRealTimeValidation() - 실시간 검증
│   │   ├─ generateErrorSummary() - 오류 요약 생성
│   │   └─ ARIA 속성 지원 (aria-invalid, aria-describedby, etc.)
│   ├── App.css              # 222줄 - 애플리케이션 스타일 + 반응형 디자인
│   ├── main.jsx             # 9줄 - React 엔트리포인트
│   ├── validation.js        # 277줄 - 검증 함수 모음 (6개 함수)
│   └── validation.test.js   # 745줄 - Vitest 유닛 테스트 (64개 케이스)
├── index.html               # 12줄 - HTML 템플릿
├── vite.config.js           # 16줄 - Vite 설정 + API 프록시
├── vitest.config.js         # 8줄 - Vitest 설정
├── package.json             # 22줄 - 프로젝트 의존성 및 스크립트
├── .gitignore               # Git 무시 목록
└── README.md                # 586줄 - 완전한 문서

코드 통계:
- 소스 코드 (테스트 제외): ~938줄
- 테스트 코드: 745줄
- 문서: 586줄
- 설정 파일: 58줄
- 총합: 2,327줄 (package-lock.json 제외)
```

## 검증 규칙

### 심볼 입력 (Symbols)

- **필수**: 최소 1개 이상의 심볼 필요
- **형식**: 쉼표로 구분 (예: `BTC_KRW, ETH_KRW, SOL_KRW`)
- **규칙**: 각 심볼 내에 공백 포함 불가

**오류 메시지:**
- 입력 없음 → "심볼을 최소 1개 이상 입력하세요"
- 공백 포함 → "심볼 내에 공백이 포함될 수 없습니다"

### 날짜 범위 (Date Range)

- **형식**: `YYYY-MM-DD` (예: `2025-10-31`)
- **규칙**:
  - start_date ≤ end_date
  - 미래 날짜 불가 (오늘 이전이어야 함)

**오류 메시지:**
- 형식 오류 → "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD)"
- 시작일 > 종료일 → "시작일은 종료일보다 이전이어야 합니다"
- 미래 날짜 → "종료일은 오늘 이전이어야 합니다"

### 전략 파라미터 (Strategy Parameters)

#### 1. volume_long_candle (거래량 급증 + 장대양봉)

| 파라미터 | 타입 | 범위 | 설명 |
|---------|------|------|------|
| vol_ma_window | 정수 | 1~200 | 이동 평균 윈도우 (일) |
| vol_multiplier | 실수 | 1.0~10.0 | 거래량 배수 |
| body_pct | 실수 | 0.0~1.0 | 몸통 크기 비율 |

#### 2. volume_zone_breakout (매물대 돌파)

| 파라미터 | 타입 | 범위 | 설명 |
|---------|------|------|------|
| volume_window | 정수 | 1~200 | 거래량 계산 윈도우 (일) |
| top_percentile | 실수 | 0<x≤1.0 | 상위 백분위수 (UI에서는 0~100% 입력) |
| breakout_buffer | 실수 | 0.0~1.0 | 돌파 확인 버퍼 |

**특별 규칙:**
- **top_percentile**: 사용자는 0~100의 퍼센트 값으로 입력 (예: 20)하고, 내부적으로 0~1의 소수로 변환됩니다 (예: 20 → 0.2)
  - 입력 UI 라벨: "상위 백분위수 (0~100%)"
  - 안내 문구: "0~100의 퍼센트 값으로 입력하세요"

**오류 메시지:**
- 필수 입력 누락 → "[파라미터명]을(를) 입력하세요"
- 타입 오류 → "[파라미터명]은(는) 숫자여야 합니다"
- 정수 필수 → "[파라미터명]은(는) 정수여야 합니다"
- 범위 초과 → "[파라미터명]은(는) X 이상/이하여야 합니다"

## API 연동

### 백엔드 API 주소

기본값: `http://localhost:8000`

개발 환경에서는 Vite 프록시로 자동 설정됩니다.

### 요청 형식

```javascript
POST /api/backtests/run
Content-Type: application/json

{
  "strategy": "volume_long_candle",
  "symbols": ["BTC_KRW", "ETH_KRW"],
  "start_date": "2025-01-01",
  "end_date": "2025-10-31",
  "timeframe": "1d",
  "params": {
    "vol_ma_window": 20,
    "vol_multiplier": 1.5,
    "body_pct": 0.02
  }
}
```

### 응답 형식

성공 (200 OK):
```javascript
{
  "run_id": "uuid",
  "strategy": "volume_long_candle",
  "params": { ... },
  "start_date": "2025-01-01",
  "end_date": "2025-10-31",
  "timeframe": "1d",
  "symbols": [
    {
      "symbol": "BTC_KRW",
      "signals": 42,
      "win_rate": 0.59,
      "avg_return": 0.0065,
      "max_drawdown": -0.031,
      "avg_hold_bars": 2.1
    },
    ...
  ],
  "total_signals": 150,
  "execution_time": 12.34
}
```

실패 (400, 500, 등):
```javascript
{
  "detail": "에러 메시지"
}
```

## 사용자 인터페이스

### 폼 섹션 (Form Section)

1. **전략 선택** - 드롭다운에서 사용할 거래 전략 선택
2. **심볼 입력** - 백테스트할 암호화폐 심볼 입력
3. **날짜 범위** - 백테스트 기간 설정
4. **타임프레임** - 캔들 주기 선택 (1d, 1h, 5m)
5. **파라미터** - 전략별 파라미터 입력
6. **제출 버튼** - "백테스트 실행" 버튼 (검증 실패 시 비활성화)

### 실시간 검증 (Real-Time Validation)

폼의 모든 입력 필드에서 사용자가 값을 변경하면 즉시 검증이 수행됩니다:

- **입력 중 즉시 검증**: `handleInputChange`, `handleParamChange`, `handleStrategyChange`에서 모든 변경 후 `performRealTimeValidation()`을 호출
- **동적 상태 업데이트**: 검증 결과가 `errors` 상태에 반영되어 UI가 실시간으로 갱신
- **점진적 오류 해결**: 사용자가 입력을 수정하면 해당 필드의 오류가 자동으로 제거됨
- **제출 버튼 동적 활성화/비활성화**: 모든 검증이 통과해야만 제출 버튼이 활성화됨

### 오류 요약 (Error Summary)

폼 상단에 모든 검증 오류를 집계하여 표시합니다:

- **요약 오류 박스**: 빨간색 배경의 목록 형식으로 모든 오류를 한눈에 표시
- **생성 방식**: `generateErrorSummary()` 함수가 `errors` 객체를 순회하여 모든 오류 메시지를 추출
  - 심볼, 날짜, 전략 오류 포함
  - 파라미터별 오류도 리스트에 포함
- **접근성**: `role="alert"`, `aria-live="polite"`으로 스크린 리더 사용자에게 알림
- **동적 업데이트**: 오류가 모두 해결되면 요약 박스 자동 숨김

**예시:**
```
❌ 다음 오류를 수정하세요:
- 심볼을 최소 1개 이상 입력하세요
- 시작일은 종료일보다 이전이어야 합니다
- vol_multiplier는 1.0 이상이어야 합니다
```

### 필드별 오류 표시

각 입력 필드 아래에 개별 오류 메시지를 표시합니다:

- **빨간색 테두리**: 오류 상태의 필드는 빨간색 테두리와 배경색 강조
- **인라인 메시지**: 필드 바로 아래에 작은 빨간색 텍스트로 오류 메시지 표시
- **필드별 검증**: 각 필드는 독립적으로 검증되어 오류가 추적됨

### 접근성 (Accessibility)

WCAG 2.1 AA 표준을 준수하는 접근성 기능을 포함합니다:

#### ARIA 속성

- **`aria-invalid`**: 오류가 있는 필드에 `aria-invalid="true"` 적용
  - 스크린 리더가 입력 오류를 사용자에게 알림
  - 예: `<input aria-invalid={!!errors.symbols} />`

- **`aria-describedby`**: 오류 메시지와 입력 필드를 연결
  - 오류 메시지 컨테이너에 고유 `id` 지정 (예: `symbols-error`)
  - 입력 필드의 `aria-describedby` 속성에 이 `id` 연결
  - 예: `<input aria-describedby="symbols-error" />` + `<div id="symbols-error" className="error-message">`

- **`aria-busy`**: 제출 버튼에 로딩 상태 표시
  - API 호출 중일 때 `aria-busy="true"`로 설정
  - 스크린 리더 사용자가 진행 상태를 알 수 있음

- **`aria-disabled`**: 제출 버튼의 비활성 상태 명시
  - 검증 실패 시 `aria-disabled="true"`로 설정

- **`role="alert"`**: 오류 메시지에 경고 역할 지정
  - 새 오류가 나타나면 스크린 리더가 자동으로 읽음

- **`aria-live="polite"`**: 동적 오류 요약의 업데이트를 알림
  - 오류가 생기거나 해결되면 스크린 리더가 내용 재읽음

#### 시맨틱 마크업

- 모든 입력 필드는 명확한 `<label>` 요소와 연결
- 필드 그룹을 논리적으로 구성
- 정보성 텍스트는 `className="info-text"`로 구분

### 결과 표시

백테스트 실행 후 다음 정보를 표시:

- **요약**: 전략, 기간, 총 신호 수, 실행 시간
- **결과 테이블**:
  - 심볼: 거래 대상 심볼
  - 신호 수: 전략에서 생성된 거래 신호의 개수
  - 승률: 이익이 난 거래의 비율 (%)
  - 평균 수익률: 거래당 평균 수익률 (%)
  - 최대 낙폭: 피크에서 저점까지의 최대 손실률 (%)
  - 평균 보유 바: 거래를 보유한 평균 기간 (캔들 개수)

## 주요 컴포넌트

### App.jsx (430줄)

메인 애플리케이션 컴포넌트로, 다음 기능을 포함합니다:

- **상태 관리**: React `useState`를 사용한 폼 데이터, 오류, 결과 관리
- **실시간 검증**: `performRealTimeValidation()` - 모든 입력 변경 시 즉시 검증
- **오류 요약**: `generateErrorSummary()` - 모든 오류를 폼 상단에 리스트 형식으로 표시
- **폼 핸들러** (실시간 검증 통합):
  - `handleStrategyChange`: 전략 변경 시 파라미터 초기화 및 검증
  - `handleInputChange`: 일반 입력 필드 변경 및 검증
  - `handleParamChange`: 파라미터 필드 변경 (백분위수 변환 포함) 및 검증
  - `handleSubmit`: 폼 제출 및 API 호출
- **접근성**: ARIA 속성 (`aria-invalid`, `aria-describedby`, `aria-busy`, `role="alert"`, `aria-live="polite"`)
- **API 통신**: Axios를 사용한 백테스트 요청 및 응답 처리

### validation.js (277줄)

폼 검증 함수 모음:

```javascript
// 심볼 검증
validateSymbols(symbolsText)
→ { isValid, error, symbols[] }

// 날짜 범위 검증
validateDateRange(startDate, endDate)
→ { isValid, error }

// 파라미터 검증
validateParams(strategy, params)
→ { isValid, errors: {} }

// 전체 요청 검증
validateBacktestRequest(request)
→ { isValid, errors: {} }

// 백분위수 변환
percentToDecimal(percentValue) → decimalValue
decimalToPercent(decimalValue) → percentValue
```

### validation.test.js (745줄)

Vitest 기반 테스트 스위트 - **총 64개 테스트 케이스**:

```javascript
describe('Validation Functions', () => {
  describe('validateSymbols', () => { /* 7 tests */ })
  describe('validateDateRange', () => { /* 7 tests */ })
  describe('validateParams', () => { /* 13 tests */ })
  describe('validateBacktestRequest', () => { /* 3 tests */ })
  describe('Percentage Conversion', () => { /* 5 tests */ })
  describe('Form Behavior', () => { /* 29 tests */ })
})
// Total: 64 tests
```

## 테스트

### 유닛 테스트 실행

```bash
npm run test
```

**총 64개의 Vitest 테스트 케이스**를 포함합니다 (validation.test.js: 745줄):

#### validateSymbols (심볼 검증) - 7개 테스트
- 유효한 심볼 입력 (단일/다중)
- 공백 포함 심볼 거부
- 빈 입력 처리
- 심볼 이름 패턴 (언더스코어, 숫자)
- 탭 문자 거부
- 매우 긴 심볼 목록 (50개 이상)
- 연속 쉼표 처리

#### validateDateRange (날짜 범위 검증) - 7개 테스트
- 유효한 날짜 범위
- 같은 날짜 (경계값)
- 오늘 날짜 (경계값)
- 역순 날짜 거부
- 미래 날짜 거부
- 형식 검증 (YYYY-MM-DD)
- 단일 날짜 차이

#### validateParams (파라미터 검증) - 13개 테스트
- **volume_long_candle**:
  - vol_ma_window 범위 (1~200), 정수 타입, 경계값
  - vol_multiplier 범위 (1.0~10.0), 분수값, 범위 초과 거부
  - body_pct 범위 (0.0~1.0), 경계값

- **volume_zone_breakout**:
  - volume_window 범위 (1~200)
  - top_percentile 범위 (0<x≤1.0, exclusive minimum)
  - breakout_buffer 범위 (0.0~1.0)
  - 지원되지 않는 전략 거부

#### validateBacktestRequest (전체 요청 검증) - 3개 테스트
- 완전한 유효한 요청
- 다중 필드 오류 집계
- 누락된 필드 처리

#### Percentage Conversion (백분위수 변환) - 5개 테스트
- 백분위수 → 소수 변환 정확도
- 소수 → 백분위수 변환 정확도
- 엣지 케이스 (1%, 99%, 0%, 100%)
- Round-trip 정확도
- 잘못된 입력 처리

#### Form Behavior (폼 동작 - 실시간 검증) - 29개 테스트
- 다중 오류 누적 및 검증
- 점진적 오류 제거 (유효 → 무효 전환)
- 전략 변경 시 재검증
- 퍼센트 ↔ 소수 변환 검증 (실제 사용 시뮬레이션)
- 복잡한 다중 필드 시나리오
- 날짜 경계값 및 미래 날짜
- 최소/최대 범위 경계값
- 다양한 심볼 구분자 처리
- 빈 파라미터 객체 처리
- 파라미터 순서 유지
- 부분 실패 감지 (한 필드만 오류)

### 테스트 실행 구조

```javascript
describe('Validation Functions', () => {
  describe('validateSymbols', () => { /* 7 tests */ })
  describe('validateDateRange', () => { /* 7 tests */ })
  describe('validateParams', () => { /* 13 tests */ })
  describe('validateBacktestRequest', () => { /* 3 tests */ })
  describe('Percentage Conversion', () => { /* 5 tests */ })
  describe('Form Behavior', () => { /* 29 tests */ })
})
// Total: 64 tests
```

### 환경 설정 (Workaround)

**상황**: Vitest는 설정 파일을 로드할 때 임시 파일을 생성하려고 하기 때문에, 읽기 전용 워크트리 또는 제한된 권한 환경에서 EACCES 오류가 발생할 수 있습니다.

**권장 해결책**:
- **읽기 전용 워크트리**: Docker 컨테이너 사용 (✅ 권한 문제 해결)
- **로컬/CI 환경**: VITEST_RUNTIME_DIR 환경변수 지정 (✅ 쓰기 가능한 경로 사용)

---

## 🐳 방법 1: Docker 기반 실행 (권장 - 읽기 전용 워크트리용)

호스트 파일 시스템 권한에 관계없이 **컨테이너 내부의 /tmp는 항상 쓰기 가능**하므로, Docker를 사용하면 권한 문제를 완전히 우회할 수 있습니다.

### 실행 방법

```bash
# 한 줄 명령으로 64개 Vitest 테스트 실행
docker compose run --rm frontend-test
```

### 동작 원리

1. Node 20 Bullseye 컨테이너 시작
2. `/workspace`에 `frontend/` 디렉터리 마운트
3. `npm ci` 실행 (의존성 설치)
4. `VITEST_RUNTIME_DIR=/tmp/vitest-runtime` 자동 설정
5. `npm run test` 실행 → **64개 테스트 모두 통과**
6. 컨테이너 자동 종료 및 정리

### 실행 예시

```bash
$ docker compose run --rm frontend-test

[... npm ci 설치 과정 ...]

> coin-backtesting-frontend@0.1.0 test
> node scripts/run-vitest.js

ℹ️  Runtime directory: /tmp/vitest-runtime
✓ Created directory: /tmp/vitest-runtime
✓ Directory is writable: /tmp/vitest-runtime
✓ Write test passed: /tmp/vitest-runtime

ℹ️  Subdirectories:
   Config: /tmp/vitest-runtime/config
   Cache: /tmp/vitest-runtime/cache

✓ Config file copied to: /tmp/vitest-runtime/config/vitest-config-1761984930007.js

🧪 Running Vitest with temporary config...

 RUN  v1.6.1 /workspace

 ✓ src/validation.test.js  (64 tests) 14ms

 Test Files  1 passed (1)
      Tests  64 passed (64)
   Start at  08:15:30
   Duration  457ms

✓ Temporary config cleaned up
```

### 장점
- ✅ 호스트 파일 시스템 권한 영향 없음
- ✅ 일관된 Node 20 환경 보장
- ✅ CI/CD 파이프라인과 동일한 환경
- ✅ 호스트 파일 시스템 오염 없음 (컨테이너만 마운트)

---

## 🖥️ 방법 2: 로컬 실행 (쓰기 가능한 경로 지정)

로컬 개발 환경이나 CI/CD에서 쓰기 권한이 있는 경우, VITEST_RUNTIME_DIR 환경변수로 경로를 지정합니다.

### 실행 방법

```bash
# 쓰기 가능한 디렉터리를 지정하여 npm run test 실행
VITEST_RUNTIME_DIR=/var/tmp/vitest npm run test
```

또는

```bash
# /tmp를 사용하는 경우
VITEST_RUNTIME_DIR=/tmp/vitest npm run test
```

### 동작 원리

1. VITEST_RUNTIME_DIR 환경변수에서 지정된 경로 확인
2. 경로가 없으면 자동 생성
3. probe 파일로 쓰기 권한 검증
4. 설정 파일을 지정된 디렉터리로 복사
5. Vitest 실행 → **64개 테스트 모두 통과**
6. 임시 파일 자동 정리

### 실행 예시

```bash
$ VITEST_RUNTIME_DIR=/var/tmp/vitest npm run test

ℹ️  Runtime directory: /var/tmp/vitest
   (커스텀 경로를 원하면: VITEST_RUNTIME_DIR=/path/to/writable npm run test)

✓ Created directory: /var/tmp/vitest
✓ Directory is writable: /var/tmp/vitest
✓ Write test passed: /var/tmp/vitest

ℹ️  Subdirectories:
   Config: /var/tmp/vitest/config
   Cache: /var/tmp/vitest/cache

✓ Config file copied to: /var/tmp/vitest/config/vitest-config-1761984866849.js

🧪 Running Vitest with temporary config...

 RUN  v1.6.1 /home/limeking/projects/worktree/coin-1/frontend

 ✓ src/validation.test.js  (64 tests) 17ms

 Test Files  1 passed (1)
      Tests  64 passed (64)
   Start at  17:14:27
   Duration  502ms

✓ Temporary config cleaned up
```

### 권한 오류 발생 시

지정한 경로에 쓰기 권한이 없으면 스크립트가 명확한 안내를 제공합니다:

```
❌ Error with VITEST_RUNTIME_DIR: /var/tmp/vitest
   Reason: EACCES: permission denied...

💡 해결 방법:
   1. 쓰기 가능한 디렉터리를 만든 뒤:
      mkdir -p /path/to/writable
   2. VITEST_RUNTIME_DIR 환경변수로 지정해서 실행하세요:
      VITEST_RUNTIME_DIR=/path/to/writable npm run test
```

---

## 📋 방법 비교

| 환경 | 명령 | 상태 |
|------|------|------|
| 읽기 전용 워크트리 | `docker compose run --rm frontend-test` | ✅ **권장** |
| 로컬 (권한 있음) | `npm run test` | ✅ 직접 실행 가능 |
| 로컬 (권한 제한) | `VITEST_RUNTIME_DIR=/var/tmp/vitest npm run test` | ✅ 경로 지정 필요 |
| CI/CD (GitHub Actions) | `VITEST_RUNTIME_DIR=/tmp/vitest npm run test` | ✅ 환경변수 설정 |

---

## 📂 런타임 디렉터리 구조

스크립트가 자동으로 생성하는 디렉터리 구조:

```
~/.cache/vitest-runtime/           (또는 VITEST_RUNTIME_DIR)
├── config/                         # 임시 설정 파일
│   └── vitest-config-1761984866849.js
└── cache/                          # Vitest 캐시
    └── ...
```

각 실행 후 임시 설정 파일은 자동으로 삭제됩니다.

---

## ✅ 검증 결과

### 로컬 환경 (VITEST_RUNTIME_DIR 지정)
```
✓ Config file copied to: /tmp/vitest-runtime-test/config/vitest-config-1761984866849.js
✓ src/validation.test.js  (64 tests) 17ms
✓ Tests  64 passed (64)
```

### Docker 환경
```
✓ Config file copied to: /tmp/vitest-runtime/config/vitest-config-1761984930007.js
✓ src/validation.test.js  (64 tests) 14ms
✓ Tests  64 passed (64)
```

---

## 🔧 파일 구조

```
frontend/
├── scripts/
│   ├── run-vitest.js           # npm run test 실행 스크립트
│   │   ├─ VITEST_RUNTIME_DIR 환경변수 확인
│   │   ├─ 기본값: ~/.cache/vitest-runtime
│   │   ├─ probe 파일로 쓰기 권한 검증
│   │   └─ 권한 오류 시 명확한 가이드 메시지
│   └── run-vitest-ui.js        # npm run test:ui 실행 스크립트
├── docker-compose.yml          # frontend-test 서비스 정의
│   └─ VITEST_RUNTIME_DIR=/tmp/vitest-runtime 자동 설정
├── package.json                # npm scripts
└── vitest.config.js            # Vitest 설정
```

모든 환경(읽기 전용 워크트리, 로컬, CI/CD)에서 64개의 Vitest 테스트를 안정적으로 실행할 수 있습니다!

### 수동 테스트 체크리스트

#### 기본 기능 테스트
- [ ] 앱 시작 시 전략 "거래량 급증 + 장대양봉" 선택됨
- [ ] 전략 변경 시 파라미터 필드가 동적으로 변경됨
- [ ] 모든 필드가 초기 상태에서 비워져 있음
- [ ] 제출 버튼이 초기 상태에서 비활성화됨

#### 실시간 검증 테스트
- [ ] 심볼 입력 중 즉시 검증 수행
- [ ] 날짜 입력 중 즉시 검증 수행
- [ ] 파라미터 입력 중 즉시 검증 수행
- [ ] 한 필드 수정 시 전체 폼 재검증
- [ ] 검증 오류 제거 시 제출 버튼 자동 활성화

#### 오류 요약 테스트
- [ ] 폼 상단에 오류 요약 박스 표시됨 (다중 오류)
- [ ] 오류 요약이 리스트 형식으로 표시됨
- [ ] 모든 오류 해결 시 요약 박스 사라짐
- [ ] 새 오류 발생 시 요약 박스 자동 업데이트

#### 접근성 테스트
- [ ] 오류 있는 필드에 `aria-invalid="true"` 속성 확인
- [ ] 오류 메시지에 오류 메시지 ID와 연결 (`aria-describedby`)
- [ ] 제출 버튼 로딩 시 `aria-busy="true"` 확인
- [ ] 브라우저 개발자 도구에서 ARIA 속성 확인 가능
- [ ] 스크린 리더(NVDA, JAWS) 테스트 (선택사항)

#### 검증 테스트
- [ ] 빈 심볼 입력 → 오류 메시지 표시
- [ ] 공백 포함 심볼 → 오류 메시지 표시
- [ ] 유효한 심볼 입력 → 오류 메시지 사라짐
- [ ] start_date > end_date → 날짜 오류 표시
- [ ] vol_multiplier = 0.5 → 범위 오류 표시
- [ ] 모든 필드 유효 → 제출 버튼 활성화

#### 파라미터 테스트 (volume_long_candle)
- [ ] vol_ma_window 입력 (1~200) → 제대로 저장됨
- [ ] vol_multiplier 입력 (1.0~10.0) → 제대로 저장됨
- [ ] body_pct 입력 (0.0~1.0) → 제대로 저장됨
- [ ] 범위 밖 값 입력 → 즉시 오류 표시

#### 파라미터 테스트 (volume_zone_breakout)
- [ ] volume_window 입력 → 제대로 저장됨
- [ ] top_percentile 입력 (0~100%) → 소수로 변환되어 저장됨
  - 예: 20 입력 → 0.2로 저장 (검증 요청 시)
  - 예: 75 입력 → 0.75로 저장
- [ ] 안내 문구 "0~100의 퍼센트 값으로 입력하세요" 표시됨
- [ ] breakout_buffer 입력 → 제대로 저장됨
- [ ] top_percentile = 0 또는 > 100 → 오류 표시

#### API 통신 테스트
- [ ] 유효한 입력으로 제출 → API 호출됨
- [ ] API 성공 응답 → 결과 테이블 표시됨
- [ ] API 오류 응답 → 오류 메시지 표시됨
- [ ] 실행 중 제출 버튼 비활성화 → 중복 요청 방지
- [ ] 로딩 중 버튼 텍스트 "실행 중..." 변경됨

#### UI/UX 테스트
- [ ] 폼 전체가 화면에 잘 표시됨
- [ ] 날짜 필드가 2열 레이아웃 → 모바일 1열로 반응형 동작
- [ ] 오류 메시지가 빨간색으로 표시됨
- [ ] 오류 필드의 테두리/배경색 변경됨
- [ ] 브라우저 콘솔에 경고/에러 없음
- [ ] 개발자 도구에서 ARIA 속성 확인

## 트러블슈팅

### 개발 서버 실행 안 됨

```bash
# 캐시 제거 후 재설치
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### API 연결 실패

- 백엔드 서버가 `http://localhost:8000`에서 실행 중인지 확인
- `vite.config.js`의 프록시 설정 확인
- 브라우저 개발자 도구 → Network 탭에서 API 요청 확인

### 오류 메시지가 표시 안 됨

- React DevTools 확인: 폼 상태에 에러가 저장되어 있는지 확인
- 콘솔에서 validation 함수 동작 확인: `console.log(validateBacktestRequest(...))`

## 환경 설정

### API 주소 변경

`vite.config.js`의 `server.proxy` 섹션 수정:

```javascript
proxy: {
  '/api': {
    target: 'http://your-backend-server:port',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, '/api')
  }
}
```

## 배포

### Docker를 사용한 배포

```dockerfile
# Dockerfile 예시
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM node:18-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/dist ./dist
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
```

### Docker Compose

```yaml
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    environment:
      - REACT_APP_API_URL=http://backend:8000
```

## 성능 최적화

- **Code Splitting**: Vite의 자동 코드 분할
- **Lazy Loading**: 필요시 컴포넌트 지연 로딩
- **번들 크기 모니터링**: `npm run build`로 빌드 후 `dist/` 폴더 크기 확인

## 라이센스

MIT

## 관련 문서

- [백엔드 API 문서](../backend/README.md)
- [전체 프로젝트 문서](../docs/pdr.md)
- [Issue #4: React 폼 유효성 검사 및 데이터 구조 정합성](../docs/coin/mvp/ri_4.md)
