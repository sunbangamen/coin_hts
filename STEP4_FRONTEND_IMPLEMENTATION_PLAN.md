# Step 4 Frontend 신호 테이블 구현 계획

**작성일**: 2025-11-03
**상태**: 📋 구현 대기 (Backend Phase 1 ✅ 완료)
**목표**: Week 2에 신호 테이블 UI 완성

---

## 📊 API 데이터 구조 확인

**Backend에서 전달되는 신호 데이터**:

```javascript
// result.symbols[0].signals
[
  {
    "symbol": "BTC_KRW",
    "type": "buy",              // "buy" or "sell"
    "timestamp": "2024-01-15T09:00:00",  // ISO 8601
    "entry_price": 50000000.0,
    "exit_price": 51500000.0,
    "return_pct": 0.03          // 0.03 = 3%
  },
  {
    "symbol": "BTC_KRW",
    "type": "sell",
    "timestamp": "2024-01-20T14:00:00",
    "entry_price": 51500000.0,
    "exit_price": 50800000.0,
    "return_pct": -0.0136       // -1.36%
  }
]
```

---

## 🎯 Step 4 구현 아이템

### 1️⃣ SignalsTable 컴포넌트 작성

**파일**: `frontend/src/components/SignalsTable.jsx`

**주요 기능**:
- 신호 데이터 테이블 렌더링
- 6개 컬럼: 심볼, 타입, 시간, 진입가, 청산가, 수익률
- 반응형 레이아웃 (모바일/태블릿/데스크톱)
- 신호 없을 때 안내 메시지

**예상 코드 구조**:
```jsx
export default function SignalsTable({ symbol, signals = [] }) {
  const [sortKey, setSortKey] = useState('timestamp')
  const [sortOrder, setSortOrder] = useState('desc')

  if (!signals || signals.length === 0) {
    return <div className="empty-state">신호 없음</div>
  }

  const sortedSignals = sortSignals(signals, sortKey, sortOrder)

  return (
    <div className="signals-table-container">
      <table className="signals-table">
        <thead>
          <tr>
            <th onClick={() => handleSort('symbol')}>심볼 {sortIcon('symbol')}</th>
            <th onClick={() => handleSort('type')}>타입 {sortIcon('type')}</th>
            <th onClick={() => handleSort('timestamp')}>시간 {sortIcon('timestamp')}</th>
            <th onClick={() => handleSort('entry_price')}>진입가 {sortIcon('entry_price')}</th>
            <th onClick={() => handleSort('exit_price')}>청산가 {sortIcon('exit_price')}</th>
            <th onClick={() => handleSort('return_pct')}>수익률 {sortIcon('return_pct')}</th>
          </tr>
        </thead>
        <tbody>
          {sortedSignals.map((signal, idx) => (
            <tr key={idx} className={`signal-row ${signal.type}`}>
              <td>{signal.symbol}</td>
              <td className={`type ${signal.type}`}>
                {signal.type === 'buy' ? '매수' : '매도'}
              </td>
              <td>{formatDateTime(signal.timestamp)}</td>
              <td className="price">{formatPrice(signal.entry_price)}</td>
              <td className="price">{formatPrice(signal.exit_price)}</td>
              <td className={`return ${getReturnClass(signal.return_pct)}`}>
                {formatPercent(signal.return_pct)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

---

### 2️⃣ 유틸리티 함수 추가/수정

**파일**: `frontend/src/utils/formatters.js` (기존)

**필요한 함수** (이미 일부 존재):
- ✅ `formatPercent(0.03)` → "3.00%"
- ✅ `formatNumber(50000000)` → "50,000,000"
- ✅ `formatDateTime("2024-01-15T09:00:00")` → "2024-01-15 09:00"
- 추가 필요: `formatPrice()` - formatNumber 별칭
- 추가 필요: `getReturnClass()` - 양수/음수 클래스

**구현 예**:
```javascript
export function formatPrice(price) {
  return formatNumber(price)  // "50,000,000"
}

export function getReturnClass(returnPct) {
  if (returnPct > 0) return 'positive'
  if (returnPct < 0) return 'negative'
  return 'neutral'
}
```

---

### 3️⃣ BacktestResults에 신호 섹션 통합

**파일**: `frontend/src/components/BacktestResults.jsx` (기존)

**현재 상태** (라인 99-105):
```jsx
// 신호 목록 섹션 (현재 placeholder)
<div className="signals-section">
  <h3>신호 목록</h3>
  <p className="placeholder">Step 4: 신호 목록 테이블 - 구현 대기</p>
</div>
```

**수정 예**:
```jsx
{/* 신호 목록 섹션 */}
<div className="signals-section">
  <h3>신호 목록</h3>
  {result.symbols.map((symbol, idx) => (
    <div key={idx} className="symbol-signals">
      <h4>{symbol.symbol}</h4>
      {symbol.signals && symbol.signals.length > 0 ? (
        <SignalsTable
          symbol={symbol.symbol}
          signals={symbol.signals}
        />
      ) : (
        <p className="empty">신호 없음</p>
      )}
    </div>
  ))}
</div>
```

---

### 4️⃣ CSS 스타일링

**파일**: `frontend/src/App.css` (기존)

**추가 스타일** (대략 50-80줄):

```css
.signals-table-container {
  overflow-x: auto;
  margin: 20px 0;
}

.signals-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.signals-table thead {
  background-color: #f8f9fa;
  border-bottom: 2px solid #dee2e6;
}

.signals-table th,
.signals-table td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid #dee2e6;
}

.signals-table th {
  cursor: pointer;
  user-select: none;
  font-weight: 600;
}

.signals-table th:hover {
  background-color: #e9ecef;
}

.signal-row.buy {
  background-color: #f0f8ff;
}

.signal-row.sell {
  background-color: #fff0f0;
}

.signal-row:hover {
  background-color: #f5f5f5;
}

.type.buy {
  color: #007bff;
  font-weight: 600;
}

.type.sell {
  color: #dc3545;
  font-weight: 600;
}

.return.positive {
  color: #28a745;
  font-weight: 600;
}

.return.negative {
  color: #dc3545;
  font-weight: 600;
}

.return.neutral {
  color: #6c757d;
}

/* 모바일 반응형 */
@media (max-width: 768px) {
  .signals-table {
    font-size: 12px;
  }

  .signals-table th,
  .signals-table td {
    padding: 8px 12px;
  }
}
```

---

## 📋 구현 체크리스트

- [ ] **SignalsTable 컴포넌트**
  - [ ] 테이블 구조 (thead, tbody, 6 컬럼)
  - [ ] 신호 없을 때 안내 메시지
  - [ ] 반응형 레이아웃

- [ ] **정렬 기능**
  - [ ] timestamp 정렬 (기본값: 내림차순)
  - [ ] return_pct 정렬
  - [ ] type 정렬
  - [ ] 정렬 아이콘 표시

- [ ] **포맷팅**
  - [ ] 시간: "2024-01-15 09:00"
  - [ ] 가격: "50,000,000"
  - [ ] 수익률: "3.00%", "-1.36%"

- [ ] **색상 코딩**
  - [ ] buy: 파란색 배경/텍스트
  - [ ] sell: 빨간색 배경/텍스트
  - [ ] 양수 return: 초록색
  - [ ] 음수 return: 빨간색

- [ ] **BacktestResults 통합**
  - [ ] 신호 섹션 활성화
  - [ ] 다중 심볼 신호 표시
  - [ ] 신호 없을 때 처리

- [ ] **테스트**
  - [ ] 단일 심볼 (다양한 신호 수: 0, 1, 5, 10개)
  - [ ] 다중 심볼 (2-3개 심볼)
  - [ ] 모바일 반응형 (iPad, iPhone)
  - [ ] 정렬 기능 동작

---

## 🔧 개발 프로세스

### 1단계: 기본 컴포넌트 (2시간)
1. SignalsTable.jsx 생성
2. 기본 테이블 구조 구현
3. 데이터 렌더링

### 2단계: 정렬 기능 (1시간)
1. sortSignals 함수 구현
2. 정렬 아이콘 추가
3. onClick 이벤트 연결

### 3단계: 스타일링 (1.5시간)
1. CSS 추가
2. 모바일 반응형 확인
3. 색상 코딩 적용

### 4단계: 통합 (1시간)
1. BacktestResults에 SignalsTable 임포트
2. 신호 섹션 활성화
3. 다중 심볼 처리

### 5단계: 테스트 (2시간)
1. 다양한 시나리오 테스트
2. 버그 수정
3. 최적화

**총 예상 시간: 7.5시간 (1일 + 반나절)**

---

## 📝 API 호출 예시

**현재 App.jsx의 요청**:
```javascript
const response = await axios.post('/api/backtests/run', {
  strategy: 'volume_long_candle',
  symbols: ['BTC_KRW'],
  start_date: '2024-01-01',
  end_date: '2024-01-31',
  timeframe: '1d',
  params: {
    vol_ma_window: 20,
    vol_multiplier: 2.0,
    body_pct: 0.7
  }
})

// response.data.symbols[0].signals 접근
const signals = response.data.symbols[0].signals
signals.forEach(signal => {
  console.log(signal.type)     // "buy" | "sell"
  console.log(signal.return_pct)  // 0.03 (3%)
})
```

---

## 🚀 다음 단계

### 즉시 (오늘)
- [ ] SignalsTable.jsx 파일 생성
- [ ] 기본 테이블 구조 작성
- [ ] BacktestResults 업데이트

### 내일
- [ ] 정렬 기능 구현
- [ ] CSS 스타일 추가
- [ ] 테스트 실행

### 모레
- [ ] 버그 수정
- [ ] 성능 최적화
- [ ] 최종 검증

---

## 💾 파일 변경 예상

| 파일 | 작업 | 라인 | 상태 |
|------|------|------|------|
| `SignalsTable.jsx` | 새 파일 생성 | 100-150 | 대기 |
| `BacktestResults.jsx` | 신호 섹션 수정 | 99-105 | 수정 |
| `formatters.js` | 함수 추가 | +10 | 수정 |
| `App.css` | 스타일 추가 | +50~80 | 수정 |

---

## 📦 의존성

- ✅ Backend API: Phase 1 완료 (신호 데이터 제공)
- ✅ Frontend 환경: React, Vite (기존)
- ✅ 유틸리티: formatters.js (이미 존재)
- ⏳ 테스트 데이터: 별도 준비 필요

---

**상태**: 📋 구현 대기 중
**예상 완료**: 2025-11-05 (Week 2)
**우선순위**: P1 (핵심 기능)
