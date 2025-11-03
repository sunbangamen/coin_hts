# Issue #5 구현 상태 분석 및 다음 단계 결정

**분석 날짜**: 2025-11-03
**작성자**: 코덱스 피드백 기반 분석
**상태**: 진행 중 (구성단계)

---

## 📊 Step별 구현 현황

### Step 1: 환경 확인 및 스키마 파악 ✅ 완료

**작업**:
- 프로젝트 구조 확인
- Backend API 응답 스키마 파악

**결과**:
- ✅ `frontend/src/components/` 디렉토리 생성
- ✅ Backend API 스키마 확인
  - `/api/backtests/run`: POST 엔드포인트 존재
  - 응답: `BacktestResponse` 모델 (심볼별 요약만 포함)

---

### Step 2: BacktestResults 컴포넌트 기본 구조 ✅ 완료

**작업**:
- BacktestResults 컴포넌트 작성
- Props 정의 및 조건부 렌더링

**결과**:
- ✅ `frontend/src/components/BacktestResults.jsx` 생성 (142줄)
- ✅ 로딩/에러/빈 상태 처리
- ✅ 정보 섹션 (run_id, 전략, 기간 등)
- ⚠️ 신호 목록 섹션: placeholder만 (실제 렌더링 아직)

---

### Step 3: 지표 테이블 구현 ✅ 완료

**작업**:
- 승률, 평균 수익률, 최대 낙폭, 샘플 수 표시
- 포맷팅 유틸리티 작성

**결과**:
- ✅ 심볼별 지표 카드 렌더링
- ✅ 포맷팅 유틸리티 (formatPercent, formatNumber)
- ✅ 양수/음수 색상 코딩
- ✅ 반응형 그리드 레이아웃

---

### Step 4: 신호 목록 테이블 구현 ❌ 미완료

**작업**:
- 신호 목록 테이블 컴포넌트
- 정렬, 필터링 기능

**현황**:
- ❌ **Backend API 제약**: `signals: int` (개별 신호 데이터 없음)
- ❌ **미구현**: 실제 테이블 렌더링 코드 없음
- ✅ **준비 완료**: 포맷팅 유틸리티 (formatDateTime, formatTime 등)

**해결 방법**:
```
Backend API 확장 필요
  ├─ signals: List[Signal] (배열로 변경)
  └─ Signal 스키마 정의 (symbol, type, timestamp, entry_price, exit_price, return)
```

---

### Step 5: App.jsx API 연동 ⚠️ 부분 구현 (불일치)

**계획 (ri_5.md:120-137)**:
```
1. /api/backtests/latest 호출
2. 상세 데이터 있으면 즉시 렌더링
3. 없으면 run_id로 /api/backtests/{run_id} 추가 호출
4. 주석: "응답 구조가 확정되면 계획을 갱신"
```

**현재 구현 (App.jsx:140-184)**:
```javascript
// POST /api/backtests/run 직접 실행
const response = await axios.post('/api/backtests/run', requestData)
setResult(response.data)  // 즉시 표시
setShowResult(true)
```

**불일치 분석**:
- ❌ `/api/backtests/latest` 미사용
- ❌ `run_id` → 상세 조회 플로우 없음
- ✅ 실제 동작은 정상 (POST 실행 → 즉시 표시)

**3가지 선택지**:

#### 선택지 A: 현재 구현 유지 (가장 간단)

```
사용자 입력
  ↓
POST /api/backtests/run
  ↓
결과 즉시 받음
  ↓
BacktestResults 표시
```

**장점**:
- 간단하고 직관적
- 실제 동작 우수
- API 호출 한 번으로 끝남

**단점**:
- 계획과 불일치
- 재실행 불가능 (결과 다시 조회 방법 없음)

**필요 작업**:
- ri_5.md Step 5 수정 (현재 구현으로 맞춤)

---

#### 선택지 B: /api/backtests/latest 구현

```
GET /api/backtests/latest
  ↓
최신 실행의 run_id 반환
  ↓
GET /api/backtests/{run_id}
  ↓
BacktestResults 표시
```

**장점**:
- 계획과 일치
- 재실행/재조회 가능
- 체계적인 API 설계

**단점**:
- Backend 확장 필요
- API 호출 2번 (1번 추가)
- 구현 복잡도 증가

**필요 작업**:
- Backend: `/api/backtests/latest` 엔드포인트 추가
- Frontend: App.jsx 수정 (latest → run_id 조회)
- 테스트 추가

---

#### 선택지 C: 분리된 플로우 (최강력)

```
실행 화면:
  POST /api/backtests/run → 즉시 표시 (빠름)

재조회 화면 (별도):
  GET /api/backtests/latest → GET /api/backtests/{run_id} (체계적)
```

**장점**:
- 두 가지 장점 모두 활용
- UX 최적화
- 최신 성능 + 체계적 설계

**단점**:
- 구현 복잡도 가장 높음
- UI 수정 필요
- 테스트 케이스 많음

**필요 작업**:
- Backend: latest 엔드포인트 + 상세 조회 페이지
- Frontend: 별도 조회 페이지 추가
- 라우팅 추가

---

---

### Step 6: 차트 구현 ❌ 미수행

**작업**:
- Recharts 라이브러리 통합
- 수익률 곡선 차트
- 거래 수 막대 차트

**현황**:
- ❌ **미시작**: 어떤 라이브러리도 설치 안 됨
- ⚠️ **데이터 제약**: 현재 시계열 데이터 없음

**우선순위 판단**:
- **높음** (P1): 신호 목록 테이블 먼저 완료 필요
- **중간** (P2): 차트 선택사항이므로 나중에 가능
- **낮음** (P3): 테스트 데이터 확보 필요

---

### Step 7: 스타일링 및 반응형 디자인 ✅ 완료

**작업**:
- CSS 스타일링
- 모바일 반응형
- 접근성 개선

**결과**:
- ✅ `App.css` 282줄 추가
- ✅ 반응형 @media query
- ✅ 색상 코딩 (양수/음수)
- ✅ 로딩 스피너 애니메이션

---

### Step 8: 통합 테스트 및 검증 ⚠️ 제한적 수행

**작업**:
- 여러 시나리오 테스트
- 성능 모니터링

**현황**:
- ✅ **코드 검증**: 모든 import/구조 검증 완료
- ✅ **Docker 검증**: 8가지 테스트 통과
- ❌ **기능 테스트**: 테스트 데이터 부재로 제한적
- ❌ **다양한 시나리오**: 데이터 없어서 불가능

**필요 사항**:
- 테스트 데이터 생성 (OHLCV 파일)
- 실제 백테스트 결과로 테스트

---

## 🎯 다음 3가지 우선결정 사항

### 1️⃣ /api/backtests/latest 플로우 결정

**선택이 필요합니다:**

| 선택지 | 복잡도 | API 호출 | 재조회 | 우선권 |
|--------|--------|---------|--------|--------|
| A: 현재 유지 | 낮음 | 1회 | 불가 | P1 |
| B: latest 추가 | 중간 | 2회 | 가능 | P2 |
| C: 분리 플로우 | 높음 | 2회 | 가능 | P3 |

**권장**: **A 또는 B** (C는 Phase 2 이후)

---

### 2️⃣ Step 4 신호 목록 테이블 구현 방향

**백엔드 확장 필요**:

현재:
```python
class SymbolResult:
    symbol: str
    signals: int           # 개수만
    win_rate: float
    ...
```

확장 필요:
```python
class Signal:
    symbol: str
    type: str              # "buy" | "sell"
    timestamp: str         # ISO 8601
    entry_price: float
    exit_price: float
    return: float          # -0.05 ~ 0.10

class SymbolResult:
    symbol: str
    signals: List[Signal]  # 배열로 변경
    ...
```

**순서**:
1. Backend API 확장 (Signal 스키마 + 데이터 반환)
2. Frontend Step 4 구현 (신호 목록 테이블)

---

### 3️⃣ Step 6 차트 구현 우선순위

**현재 상황**:
- Step 4 (신호 테이블) 완료 필요
- 테스트 데이터 필요

**우선순위**:
- P1 (높음): Step 4 신호 테이블
- P2 (중간): 차트 구현 (선택사항)
- P3 (낮음): Step 8 전체 테스트

**권장**: Step 4 완료 후 필요성 재평가

---

## 📋 제안 액션 플랜

### Phase 1A: 아키텍처 결정 (이번 주)

- [ ] **Step 5 플로우 결정**: A (현재 유지) 또는 B (latest 추가)?
  - 결정 시: ri_5.md 업데이트
  - 코드 미변경 (이미 정상 동작)

### Phase 1B: Step 4 구현 준비 (다음 주)

- [ ] **Backend 확장**
  - Signal 스키마 정의
  - `/api/backtests/{run_id}` 응답에 signals 추가
  - 데이터 검증

- [ ] **Frontend Step 4**
  - 신호 테이블 컴포넌트 작성
  - 정렬, 페이지네이션 기능
  - BacktestResults에 통합

### Phase 1C: 테스트 및 검증

- [ ] 테스트 데이터 생성 (OHLCV)
- [ ] 통합 테스트 (Step 2~8)
- [ ] 성능 테스트

### Phase 2: 선택사항 (우선순위 확정 후)

- [ ] Step 6: 차트 구현
- [ ] 추가 테스트 시나리오
- [ ] 성능 최적화

---

## 📊 현재 vs 계획 비교표

| Step | 항목 | 계획 | 현황 | 상태 |
|------|------|------|------|------|
| 1 | 환경/스키마 | ✅ | ✅ | 완료 |
| 2 | 기본 구조 | ✅ | ✅ | 완료 |
| 3 | 지표 테이블 | ✅ | ✅ | 완료 |
| 4 | 신호 테이블 | ✅ | ❌ | **Backend 확장 필요** |
| 5 | API 연동 | latest→detail | run만 | **플로우 결정 필요** |
| 6 | 차트 | ✅ | ❌ | **우선순위 결정** |
| 7 | 스타일링 | ✅ | ✅ | 완료 |
| 8 | 테스트 | ✅ | ⚠️ | **데이터 부재** |

---

## 🎬 즉시 액션 (코덱스와 협의 필요)

다음 3가지를 결정해주세요:

### Q1: Step 5 API 플로우?
- [ ] **A**: 현재 구현 유지 (POST 직접 실행 → 즉시 표시)
- [ ] **B**: /api/backtests/latest 추가 구현

### Q2: Step 4 신호 테이블 구현 시기?
- [ ] **지금**: 다음 주부터 Backend 확장 시작
- [ ] **나중**: Phase 2 이후 (차트 먼저)

### Q3: Step 6 차트 우선순위?
- [ ] **높음** (P1): 기본 기능으로 필수
- [ ] **낮음** (P2): 선택사항이므로 나중에

---

**이 3가지가 결정되면 ri_5.md를 업데이트하고 구체적인 개발 계획을 수립할 수 있습니다.**
