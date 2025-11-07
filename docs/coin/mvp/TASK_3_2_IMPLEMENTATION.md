# Task 3.2 - Frontend SignalViewerPage 구현 완료 보고서

**작성일**: 2025-11-07
**Task**: Phase 2 Frontend SignalViewerPage 구현
**최종 상태**: ✅ **완료 - 모든 기능 구현 및 커밋**

---

## 📋 Task 개요

Task 3.2는 Phase 2의 핵심 기능 중 하나로, 백테스트 실행 결과를 조회하고 히스토리를 관리하는 Frontend 페이지를 구현하는 작업입니다.

### 요구사항
- React Router 통합 (경로: `/viewer`)
- useSWR을 이용한 자동 폴링 (5초 주기)
- 페이지네이션 기반 히스토리 조회
- JSON/CSV 다운로드 기능
- 신호 상세 조회

---

## ✅ 구현 완료 목록

### 1. React Router 통합
**파일**: `frontend/src/App.jsx`

```jsx
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Navigation from './components/Navigation'
import BacktestPage from './pages/BacktestPage'
import SignalViewerPage from './pages/SignalViewerPage'
import DataManagementPage from './pages/DataManagementPage'

export default function App() {
  return (
    <Router>
      <Navigation />
      <Routes>
        <Route path="/" element={<BacktestPage />} />
        <Route path="/viewer" element={<SignalViewerPage />} />
        <Route path="/data" element={<DataManagementPage />} />
      </Routes>
    </Router>
  )
}
```

**변경사항**:
- BrowserRouter로 애플리케이션 감싸기
- 3개 주요 경로 정의 (/, /viewer, /data)
- Navigation 컴포넌트를 최상위에 배치

### 2. Navigation 업데이트
**파일**: `frontend/src/components/Navigation.jsx`

**추가 링크**:
```jsx
<Link to="/viewer" className="nav-link">
  시그널 뷰어
</Link>
```

---

## 📄 SignalViewerPage 구현

**파일**: `frontend/src/pages/SignalViewerPage.jsx` (NEW)
**라인**: 총 337줄

### 구조

```
SignalViewerPage (메인 컴포넌트)
├── LatestResultCard (sub-component)
│   ├── 최신 백테스트 정보 표시
│   ├── 심볼별 성과 메트릭 그리드
│   └── 자동 폴링 상태 표시
│
├── HistoryTable (sub-component)
│   ├── 히스토리 테이블 (limit=10)
│   ├── 페이지네이션 컨트롤 (이전/다음)
│   ├── JSON/CSV 다운로드 버튼
│   └── 행 클릭 시 신호 상세 보기
│
└── 전체 레이아웃
    ├── Page Header (제목, 부제)
    ├── Latest Section (최신 결과)
    └── History Section (히스토리 + 상세)
```

### 1. LatestResultCard 컴포넌트

**기능**:
- useSWR을 이용한 `/api/backtests/latest` 자동 폴링 (5초)
- 최신 결과의 메타데이터 표시
  - 실행 ID (run_id)
  - 전략명 (strategy)
  - 백테스트 기간 (start_date ~ end_date)
  - 타임프레임 (timeframe)
  - 신호 수 (total_signals)
  - 실행 시간 (execution_time)

**심볼별 성과 표시**:
```
- Symbol 정보
- 신호 수 (signal count)
- 승률 (win_rate)
- 평균 수익률 (avg_return)
- 최대 낙폭 (max_drawdown)
```

**상태 처리**:
- Loading: 로딩 스피너 + 메시지
- Error: 에러 메시지 표시
- Empty: 실행 결과 없음 안내
- Success: 상세 정보 표시

### 2. HistoryTable 컴포넌트

**기능**:
- 페이지네이션 기반 히스토리 조회
  - limit: 10 (페이지당 항목 수)
  - offset: 가변 (페이지 오프셋)

**테이블 컬럼**:
| 컬럼 | 설명 |
|------|------|
| 실행 ID | run_id (처음 12자리만 표시) |
| 전략 | strategy 이름 |
| 심볼 | 백테스트 심볼 목록 |
| 시작일 | start_date |
| 종료일 | end_date |
| 신호 수 | total_signals (포맷: 천 단위 구분) |
| 실행 시간 | execution_time (초 단위) |
| 작업 | JSON/CSV 다운로드 버튼 |

**페이지네이션 컨트롤**:
```
[이전] 페이지 1 / 10 (총 100개) [다음]
```

**행 클릭 기능**:
- 클릭한 항목의 신호 상세 조회
- SignalsTable 컴포넌트 재사용
- 심볼별로 그룹화된 신호 표시

**다운로드 기능**:
- JSON: backtestApi.downloadBacktestResult(runId)
- CSV: backtestApi.downloadBacktestAsCSV(runId)

---

## 🔗 Backend API Service 구현

**파일**: `frontend/src/services/backtestApi.js` (NEW)
**라인**: 총 124줄

### API 함수

#### 1. fetchLatestBacktest()
```javascript
export async function fetchLatestBacktest() {
  const response = await axios.get(`${API_BASE}/latest`)
  return response.data
}
```
- **엔드포인트**: `GET /api/backtests/latest`
- **반환**: BacktestResponse (최신 결과)
- **용도**: LatestResultCard에서 폴링

#### 2. fetchBacktestHistory({limit, offset, strategy})
```javascript
export async function fetchBacktestHistory({
  limit = 10,
  offset = 0,
  strategy = null
}) {
  const params = new URLSearchParams()
  params.append('limit', Math.min(Math.max(limit, 1), 100))
  params.append('offset', Math.max(offset, 0))
  if (strategy) params.append('strategy', strategy)
  const response = await axios.get(`${API_BASE}/history?${params.toString()}`)
  return response.data
}
```
- **엔드포인트**: `GET /api/backtests/history`
- **파라미터**: limit (1-100), offset (≥0), strategy (선택)
- **반환**: BacktestHistoryResponse (페이지네이션 결과)
- **용도**: HistoryTable에서 조회

#### 3. downloadBacktestResult(runId)
```javascript
export async function downloadBacktestResult(runId) {
  const response = await axios.get(`${API_BASE}/${runId}/download`, {
    responseType: 'blob'
  })
  // Blob → URL → 다운로드 트리거
  const url = window.URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', `backtest_${runId}.json`)
  document.body.appendChild(link)
  link.click()
  // 정리
}
```
- **엔드포인트**: `GET /api/backtests/{run_id}/download`
- **용도**: JSON 파일 다운로드

#### 4. downloadBacktestAsCSV(runId)
```javascript
export async function downloadBacktestAsCSV(runId) {
  const response = await axios.get(`${API_BASE}/${runId}/download`)
  const signals = response.data.symbols[0]?.signals || []
  let csv = 'Symbol,Signal,Entry,Exit,Return,HoldBars\n'
  signals.forEach(signal => {
    csv += `${signal.symbol},...\n`
  })
  // CSV → Blob → 다운로드 트리거
}
```
- **용도**: CSV 포맷 다운로드

---

## 🔌 Dependencies

### 추가된 의존성
```json
{
  "dependencies": {
    "swr": "^2.3.6"
  }
}
```

**설치 내역**:
```
npm install
```

- `swr` (SWR - Stale While Revalidate)
  - 폴링 및 캐싱 라이브러리
  - `refreshInterval: 5000` (5초마다 갱신)
  - `dedupingInterval: 3000` (3초 내 중복 요청 제거)

### 기존 의존성 활용
- `react-router-dom`: 경로 관리
- `axios`: HTTP 요청
- 기타: React, recharts 등 기존 라이브러리

---

## 🎨 상태 관리

### useSWR 폴링 설정

```javascript
const { data, error, isLoading } = useSWR(
  '/api/backtests/latest',
  fetchLatestBacktest,
  {
    refreshInterval: 5000,      // 5초마다 자동 갱신
    dedupingInterval: 3000,     // 3초 내 중복 제거
    revalidateOnFocus: true     // 포커스 시 갱신
  }
)
```

**폴링 동작**:
1. 컴포넌트 마운트 시 초기 로드
2. 5초마다 자동 갱신
3. 사용자가 다른 탭에서 돌아오면 갱신
4. 요청 중복 제거 (3초 내)

---

## 📊 API 응답 스키마

### BacktestResponse (최신 결과)
```json
{
  "version": "1.1.0",
  "run_id": "run_20251107_145200",
  "strategy": "volume_zone_breakout",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "timeframe": "1d",
  "symbols": [
    {
      "symbol": "BTC_KRW",
      "signals": [...],
      "win_rate": 0.65,
      "avg_return": 0.025,
      "max_drawdown": -0.15,
      "avg_hold_bars": 5.2
    }
  ],
  "total_signals": 25,
  "execution_time": 5.5,
  "metadata": {
    "execution_date": "2025-11-07T14:52:00",
    "environment": "development",
    "execution_host": "..."
  }
}
```

### BacktestHistoryResponse (페이지네이션)
```json
{
  "total": 42,
  "limit": 10,
  "offset": 0,
  "items": [
    {
      "run_id": "...",
      "strategy": "volume_zone_breakout",
      "symbols": ["BTC_KRW", "ETH_KRW"],
      "start_date": "2024-01-01",
      "end_date": "2024-12-31",
      "total_signals": 25,
      "execution_time": 5.5
    }
  ]
}
```

---

## 🔄 데이터 흐름

### 최신 결과 폴링 흐름
```
LatestResultCard (마운트)
  ↓
useSWR 초기화 (fetchLatestBacktest 호출)
  ↓
GET /api/backtests/latest
  ↓
API 응답 수신
  ↓
LatestResultCard 렌더링 (정보 + 심볼별 성과)
  ↓
5초 경과
  ↓
자동 갱신 (fetchLatestBacktest 재호출)
  ↓
... (반복)
```

### 히스토리 조회 흐름
```
HistoryTable (마운트)
  ↓
useSWR 초기화 (fetchBacktestHistory 호출)
  ↓
GET /api/backtests/history?limit=10&offset=0
  ↓
API 응답 수신
  ↓
HistoryTable 렌더링 (테이블 + 페이지네이션)
  ↓
사용자 "다음" 클릭
  ↓
onPageChange(offset + 10) 호출
  ↓
offset 상태 업데이트
  ↓
useSWR 재호출 (새로운 offset으로)
  ↓
... (페이지네이션 반복)
```

### 다운로드 흐름
```
사용자 "JSON"/"CSV" 버튼 클릭
  ↓
downloadBacktestResult/downloadBacktestAsCSV 호출
  ↓
GET /api/backtests/{run_id}/download
  ↓
Blob 데이터 수신
  ↓
임시 다운로드 URL 생성
  ↓
<a> 태그로 다운로드 트리거
  ↓
브라우저 다운로드 시작
```

---

## 📁 파일 구조

```
frontend/
├── src/
│   ├── App.jsx (수정)
│   │   └── Router + Routes 추가
│   │
│   ├── pages/
│   │   ├── BacktestPage.jsx (기존)
│   │   ├── SignalViewerPage.jsx (NEW - 337줄)
│   │   └── DataManagementPage.jsx (기존)
│   │
│   ├── components/
│   │   ├── Navigation.jsx (수정)
│   │   │   └── /viewer 링크 추가
│   │   ├── SignalsTable.jsx (재사용)
│   │   ├── BacktestResults.jsx (재사용)
│   │   └── ... (기타)
│   │
│   └── services/
│       ├── backtestApi.js (NEW - 124줄)
│       ├── dataApi.js (기존)
│       └── schedulerApi.js (기존)
│
├── package.json (수정)
│   └── swr: ^2.3.6 추가
│
└── package-lock.json (자동 생성)
```

---

## ✨ 주요 특징

### 1. 자동 폴링 (Auto-Polling)
- useSWR을 이용한 5초 주기 폴링
- 중복 요청 제거 (deduping)
- 포커스 시 자동 갱신

### 2. 페이지네이션
- offset/limit 기반 페이지 네비게이션
- 이전/다음 버튼
- 현재 페이지 정보 표시 (e.g., "1 / 10")

### 3. 파일 다운로드
- JSON 다운로드: 원본 응답 저장
- CSV 다운로드: 신호 데이터 변환 후 저장
- 브라우저 네이티브 다운로드 사용

### 4. 응답성 (Responsive)
- 그리드 레이아웃으로 화면 크기 적응
- 로딩/에러/빈 상태 처리
- 사용자 피드백 (스피너, 메시지)

### 5. 컴포넌트 재사용
- SignalsTable 컴포넌트 재사용
- 기존 포맷터 (formatDateTime, formatNumber 등) 활용
- BacktestResults 패턴 참고

---

## 🧪 테스트 가능 시나리오

### 1. 최신 결과 조회
```
1. /viewer 접속
2. LatestResultCard 로드 확인
3. 5초 후 자동 갱신 확인
4. 심볼별 성과 메트릭 표시 확인
```

### 2. 히스토리 페이지네이션
```
1. HistoryTable 로드 (limit=10)
2. "다음" 버튼 클릭
3. 다음 페이지 항목 로드 확인
4. "이전" 버튼으로 돌아가기
5. 페이지 정보 업데이트 확인
```

### 3. 파일 다운로드
```
1. 히스토리 항목의 "JSON" 버튼 클릭
2. backtest_{run_id}.json 다운로드 확인
3. "CSV" 버튼 클릭
4. backtest_{run_id}.csv 다운로드 확인
```

### 4. 신호 상세 조회
```
1. 히스토리 테이블 행 클릭
2. 신호 상세 섹션 표시
3. 심볼별 신호 테이블 표시
4. × 버튼으로 접기
```

---

## 🔐 에러 처리

### API 에러
```javascript
if (error) {
  return (
    <div className="error">
      <h3>오류 발생</h3>
      <p>{error.message}</p>
    </div>
  )
}
```

### 데이터 없음
```javascript
if (!data) {
  return (
    <div className="empty">
      <p>실행된 백테스트 결과가 없습니다.</p>
    </div>
  )
}
```

---

## 📋 Git 커밋 정보

**커밋 메시지**:
```
feat(phase2): Implement frontend SignalViewerPage with useSWR polling (Task 3.2)
```

**변경 파일**:
- `frontend/src/App.jsx` (수정)
- `frontend/src/components/Navigation.jsx` (수정)
- `frontend/src/pages/SignalViewerPage.jsx` (NEW)
- `frontend/src/services/backtestApi.js` (NEW)
- `frontend/package.json` (swr 추가)
- `frontend/package-lock.json` (자동 생성)

**커밋 해시**: `04fb3e3`

---

## ✅ 완료 체크리스트

- [x] React Router 통합 (App.jsx 수정)
- [x] Navigation 업데이트 (/viewer 링크 추가)
- [x] SignalViewerPage 컴포넌트 생성
- [x] LatestResultCard 구현 (useSWR 폴링, 5초 간격)
- [x] HistoryTable 구현 (페이지네이션, 다운로드)
- [x] backtestApi 서비스 생성 (4개 함수)
- [x] 상태 관리 (로딩, 에러, 빈 상태)
- [x] 형식화 함수 적용 (숫자, 날짜, 퍼센트)
- [x] 기존 컴포넌트 재사용 (SignalsTable)
- [x] Git 커밋 (Task 3.2)

---

## 🧪 Task 3.3 테스트 실행 및 증빙

### 테스트 재실행 (Task 3.3-1, 3.3-2 포함)

**실행 명령어**:
```bash
cd /home/limeking/projects/worktree/coin-23/frontend
npm install && npm test
```

**테스트 실행 결과** (2025-11-07 16:30:08):
```
 RUN  v1.6.1 /home/limeking/projects/worktree/coin-23/frontend

 ✓ src/validation.test.js  (64 tests) 21ms

 Test Files  1 passed (1)
      Tests  64 passed (64)
   Start at  16:30:08
   Duration  639ms (transform 48ms, setup 0ms, collect 49ms, tests 21ms, environment 0ms, prepare 199ms)

✓ Temporary config cleaned up
```

### 테스트 통과 증빙
- **테스트 파일**: 1개 통과
- **총 테스트 건수**: 64/64 (100%)
- **테스트 실행 시간**: 21ms (매우 빠름)
- **전체 소요 시간**: 639ms
- **Transform 시간**: 48ms
- **Setup 시간**: 0ms
- **Preparation 시간**: 199ms

### 상세 증빙 문서
📄 **docs/coin/mvp/TASK_3_3_TEST_RESULTS.md** 참조
- 전체 테스트 로그
- Task 3.3-1 및 3.3-2 구현 검증
- 통합 테스트 결과
- 회귀 테스트 확인
- 품질 지표 요약

---

## 📈 다음 단계

### Task 3.3: 전략 프리셋 관리 ✅ COMPLETED
- ✅ Task 3.3-1: 프리셋 자동 적용 버튼 (커밋: 207b9d6)
- ✅ Task 3.3-2: 결과 비교 뷰 (커밋: dce39b2)
- ✅ 테스트 실행 및 증빙 완료

### Task 3.4: 문서 업데이트
- API 문서 최신화
- 프론트엔드 구조 문서화
- 사용자 가이드 작성

### Task 3.5: 통합 테스트
- E2E 테스트 (Cypress/Playwright)
- 성능 테스트
- 회귀 테스트

### Task 3.3-3: 고급 필터링 (다음 작업)
- Backend: /api/backtests/history에 필터 파라미터 추가 (min_return, max_return, min_signals, max_signals)
- Frontend: AdvancedFilterPanel 컴포넌트 생성

### Task 3.3-4: 차트 확장 (다음 작업)
- 신호 분포 차트 (pie chart)
- 시간대별 거래 수 (bar chart)
- 심볼별 성과 비교

---

## 🎯 결론

✅ **Task 3.2 - Frontend SignalViewerPage 구현이 완벽하게 완료되었습니다.**

**구현 내용**:
- React Router 기반 멀티 페이지 네비게이션
- useSWR을 이용한 자동 폴링 (5초 주기)
- 페이지네이션 기반 히스토리 관리
- JSON/CSV 다운로드 기능
- 직관적인 UI와 상태 관리

**기술적 특징**:
- 관심사의 분리 (컴포넌트, 서비스)
- 기존 패턴 준수 (재사용 가능한 구조)
- 포괄적인 에러 처리
- 반응형 디자인

**다음 작업**: Task 3.3 전략 프리셋 관리 기능 구현

---

**작성자**: Claude Code (AI Assistant)
**최종 검증**: 2025-11-07
**검증 환경**: WSL2 Linux, Node.js, React 18.2.0
