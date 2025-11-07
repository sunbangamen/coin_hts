# Task 3.3-4: 차트 확장 - 상세 요구사항 명세서

## 개요
현재 Equity Curve 차트만 구현되어 있으며, Task 3.3-4에서 다음 3가지 차트를 추가로 구현합니다:
1. **Drawdown Chart** - 최대낙폭 시각화
2. **Returns Distribution Chart** - 수익률 분포 히스토그램
3. **Multi-Symbol Chart** - 다중 심볼 비교

---

## 1. Drawdown Chart (최대낙폭 차트)

### 1.1 기능 설명
- 시간에 따른 누적 낙폭(Underwater Plot)을 보여주는 영역 차트
- 포트폴리오가 최고점에서 얼마나 내려갔는지 시각화
- 리스크 분석에 필수적인 지표

### 1.2 데이터 구조

#### 입력 데이터
```javascript
// BacktestResponse에서 추출
result.symbols[0].performance_curve = [
  {
    timestamp: "2024-01-01",
    equity: 1.05,           // 누적 수익률
    drawdown: -0.08         // 현재 낙폭 (최고점 대비)
  },
  // ... 더 많은 포인트
]
```

#### 차트 데이터 변환
```javascript
// 성능곡선으로부터 Drawdown 계산
const calculateDrawdownData = (performanceData) => {
  let maxEquity = 1.0;
  return performanceData.map(point => {
    if (point.equity > maxEquity) {
      maxEquity = point.equity;
    }
    const drawdown = (point.equity - maxEquity) / maxEquity; // 음수
    return {
      timestamp: point.timestamp,
      drawdown: drawdown * 100, // 퍼센트로 변환
      equity: point.equity
    };
  });
};
```

### 1.3 차트 사양

**차트 유형**: AreaChart (Recharts)
- **높이**: 300px
- **색상 scheme**:
  - 낙폭 영역: `rgba(220, 53, 69, 0.3)` (빨강, 투명)
  - 선: `#dc3545` (빨강)
  - 그리드: `#e0e0e0`

**구성 요소**:
- CartesianGrid: 옅은 그리드
- XAxis: 타임스탬프 (interval=자동 계산)
- YAxis: 낙폭 (%) / 라벨 "낙폭 (%)"
- Tooltip: 날짜 + 낙폭% 표시
- Area: 낙폭 영역 (음수값)
- Legend: Drawdown

### 1.4 UX/UI 설명
```html
<div class="chart-section">
  <h3>📉 Drawdown Chart (최대낙폭)</h3>
  <div class="chart-info">
    <span>최대 낙폭: -8.23% | 현재 낙폭: -2.15%</span>
  </div>
  <ResponsiveContainer>
    <AreaChart data={drawdownData}>
      <!-- 차트 구성 요소 -->
    </AreaChart>
  </ResponsiveContainer>
</div>
```

### 1.5 API 변경사항
**기존**: PerformancePoint에 drawdown 필드 존재 (선택사항)
**변경**: 없음 - 기존 데이터 구조 활용

---

## 2. Returns Distribution Chart (수익률 분포 차트)

### 2.1 기능 설명
- 각 거래의 수익률을 구간별로 분류하여 히스토그램으로 표시
- 수익성 분포를 한눈에 파악 가능
- 전략의 성공률과 손실 패턴 분석

### 2.2 데이터 구조

#### 입력 데이터
```javascript
// BacktestResponse에서 추출
result.symbols[0].signals = [
  {
    symbol: "BTC_KRW",
    type: "buy",
    timestamp: "2024-01-01T10:00:00Z",
    entry_price: 50000,
    exit_price: 52000,
    return_pct: 0.04        // 4% 수익
  },
  // ... 더 많은 신호
]
```

#### 차트 데이터 변환
```javascript
// 수익률을 구간으로 분류 (10개 또는 20개 구간)
const calculateReturnsDistribution = (signals, bins = 10) => {
  const returns = signals.map(s => s.return_pct * 100); // 퍼센트로 변환

  if (returns.length === 0) return [];

  const minReturn = Math.min(...returns);
  const maxReturn = Math.max(...returns);
  const binWidth = (maxReturn - minReturn) / bins;

  // 구간별 카운트
  const distribution = Array(bins).fill(0);
  returns.forEach(ret => {
    const binIndex = Math.floor((ret - minReturn) / binWidth);
    const idx = Math.min(binIndex, bins - 1);
    distribution[idx]++;
  });

  // 차트 데이터로 변환
  return distribution.map((count, i) => ({
    range: `${(minReturn + i * binWidth).toFixed(1)}%`,
    count: count,
    percentage: ((count / returns.length) * 100).toFixed(1)
  }));
};
```

### 2.3 차트 사양

**차트 유형**: BarChart (Recharts)
- **높이**: 300px
- **색상 scheme**:
  - 양수(수익) 구간: `#28a745` (녹색)
  - 음수(손실) 구간: `#dc3545` (빨강)

**구성 요소**:
- CartesianGrid: 옅은 그리드
- XAxis: 수익률 범위 (각도 45도)
- YAxis: 거래 수 (건수)
- Tooltip: 범위 + 건수 + 비율 표시
- Bar: 조건부 색상 (양수/음수)
- Legend: Returns Distribution

### 2.4 UX/UI 설명
```html
<div class="chart-section">
  <h3>📊 Returns Distribution (수익률 분포)</h3>
  <div class="chart-info">
    <span>총 거래: 45건 | 평균 수익률: 2.34% | 승률: 62.2%</span>
  </div>
  <ResponsiveContainer>
    <BarChart data={distributionData}>
      <!-- 차트 구성 요소 -->
    </BarChart>
  </ResponsiveContainer>
</div>
```

### 2.5 API 변경사항
**기존**: APISignal에 return_pct 필드 존재
**변경**: 없음 - 기존 데이터 구조 활용

---

## 3. Multi-Symbol Chart (다중 심볼 비교)

### 3.1 기능 설명
- 단일 백테스트 실행에서 여러 심볼의 성과곡선을 동시에 표시
- 심볼 선택/해제 기능으로 유연한 비교
- 각 심볼의 성과를 동일 선상에서 비교 가능

### 3.2 데이터 구조

#### 입력 데이터
```javascript
// BacktestResponse
result.symbols = [
  {
    symbol: "BTC_KRW",
    performance_curve: [
      { timestamp: "2024-01-01", equity: 1.02, drawdown: -0.01 },
      // ... 더 많은 포인트
    ]
  },
  {
    symbol: "ETH_KRW",
    performance_curve: [
      { timestamp: "2024-01-01", equity: 1.015, drawdown: -0.005 },
      // ... 더 많은 포인트
    ]
  }
]
```

#### 차트 데이터 변환
```javascript
// 모든 심볼의 데이터를 통합하고 정렬
const mergeSymbolData = (symbols) => {
  // 모든 타임스탬프 추출 및 정렬
  const timestampSet = new Set();
  symbols.forEach(s => {
    if (s.performance_curve) {
      s.performance_curve.forEach(p => timestampSet.add(p.timestamp));
    }
  });

  const sortedTimestamps = Array.from(timestampSet).sort();

  // 각 타임스탬프별 데이터 통합
  return sortedTimestamps.map(timestamp => {
    const dataPoint = { timestamp };
    symbols.forEach(symbol => {
      const point = symbol.performance_curve?.find(
        p => p.timestamp === timestamp
      );
      if (point) {
        dataPoint[symbol.symbol] = parseFloat((point.equity * 100).toFixed(2));
      }
    });
    return dataPoint;
  });
};
```

### 3.3 차트 사양

**차트 유형**: ComposedChart (다중 Line) - Recharts
- **높이**: 350px
- **색상 scheme** (심볼별 구분):
  - BTC_KRW: `#2c3e50` (다크 블루)
  - ETH_KRW: `#667eea` (퍼플)
  - 추가 심볼: 자동 할당 (컬러 팔레트)

**구성 요소**:
- CartesianGrid: 옅은 그리드
- XAxis: 타임스탐프 (interval=자동)
- YAxis: 누적 수익률 (%)
- Tooltip: 모든 심볼의 equity 표시
- Line: 심볼당 1개 (다른 색상)
- Legend: 심볼명 + Checkbox for toggle

### 3.4 UX/UI 설명
```html
<div class="chart-section">
  <h3>🔄 Multi-Symbol Performance Comparison</h3>
  <div class="symbol-selector">
    <label><input type="checkbox" value="BTC_KRW" checked> BTC_KRW</label>
    <label><input type="checkbox" value="ETH_KRW" checked> ETH_KRW</label>
    <!-- ... 더 많은 심볼 -->
  </div>
  <div class="chart-info">
    <span>선택된 심볼: 2개</span>
  </div>
  <ResponsiveContainer>
    <ComposedChart data={mergedData}>
      <!-- 차트 구성 요소 -->
    </ComposedChart>
  </ResponsiveContainer>
</div>
```

### 3.5 API 변경사항
**기존**: BacktestResponse.symbols는 배열
**변경**: 없음 - 기존 데이터 구조 활용

---

## 4. 통합 레이아웃

### 4.1 BacktestResults.jsx 레이아웃
```
┌─────────────────────────────────────────┐
│ 메타데이터 섹션                          │
├─────────────────────────────────────────┤
│ 백테스트 정보 섹션                       │
├─────────────────────────────────────────┤
│ 지표 요약 섹션                           │
├─────────────────────────────────────────┤
│ 📈 Equity Curve (기존)                  │
├─────────────────────────────────────────┤
│ 📉 Drawdown Chart (신규)                │
├─────────────────────────────────────────┤
│ 📊 Returns Distribution (신규)          │
├─────────────────────────────────────────┤
│ 🔄 Multi-Symbol Comparison (신규)       │
├─────────────────────────────────────────┤
│ 신호 목록 섹션                           │
└─────────────────────────────────────────┘
```

### 4.2 차트 표시 조건
- **Equity Curve**: performance_curve 존재 시 표시 (기존)
- **Drawdown Chart**: performance_curve 존재 시 표시
- **Returns Distribution**: signals 존재 시 표시
- **Multi-Symbol**: symbols.length > 1 일 때만 표시

---

## 5. 색상 팔레트

### 5.1 기본 색상
```javascript
const colorPalette = {
  // 기존
  equityLine: '#2c3e50',        // 다크 블루
  buySignal: '#28a745',          // 녹색
  sellSignal: '#dc3545',         // 빨강

  // 신규
  drawdownArea: 'rgba(220, 53, 69, 0.3)',
  drawdownLine: '#dc3545',
  returnsPositive: '#28a745',
  returnsNegative: '#dc3545',

  // Multi-Symbol (기본 팔레트)
  symbols: [
    '#2c3e50',  // BTC_KRW
    '#667eea',  // ETH_KRW
    '#f39c12',  // 추가 심볼
    '#e74c3c',  // 추가 심볼
    '#3498db',  // 추가 심볼
  ]
};
```

---

## 6. 성능 고려사항

### 6.1 데이터 양
- **Equity Curve**: 최대 1000+ 포인트 (데이터 감소 필요)
- **Drawdown**: Equity와 동일
- **Returns Distribution**: 신호 개수 (일반적으로 50-500)
- **Multi-Symbol**: 심볼 수 × equity 포인트 수

### 6.2 최적화 전략
```javascript
// 데이터 감소 함수 (1000+ 포인트인 경우 사용)
const decimateData = (data, targetSize = 500) => {
  if (data.length <= targetSize) return data;
  const step = Math.ceil(data.length / targetSize);
  return data.filter((_, i) => i % step === 0);
};

// Returns Distribution binning (신호 많을 경우)
// - 신호 <= 100개: 10 bin
// - 신호 101-500개: 15 bin
// - 신호 > 500개: 20 bin
const getBinCount = (signalCount) => {
  if (signalCount <= 100) return 10;
  if (signalCount <= 500) return 15;
  return 20;
};
```

---

## 7. 구현 순서 및 세부 지침

### Phase 1: Drawdown Chart (최고 우선)
**시작 시점**: 즉시 착수 가능

**핵심 지침**:
- 기존 performance_curve 데이터만 활용 (새로운 API 변경 불필요)
- Equity Curve 바로 아래 섹션에 추가
- `drawdownData` 계산을 `useMemo` 등으로 캐싱하여 성능 최적화

**구현 단계**:
1. `frontend/src/components/DrawdownChart.jsx` 생성
2. `frontend/src/utils/charts.ts`에 `calculateDrawdownData` 함수 작성
3. `BacktestResults.jsx`에서 DrawdownChart 컴포넌트 import 및 렌더링
4. 스타일을 `frontend/src/styles/charts.css`에 추가

---

### Phase 2: Returns Distribution Chart (우선순위: 상)
**시작 시점**: Phase 1 완료 후

**핵심 지침**:

1. **신호 없는 경우 처리**
   - 신호가 0건일 때는 "데이터 없음" 카드 표시
   ```jsx
   if (!signals || signals.length === 0) {
     return <div className="chart-empty">거래 신호가 없습니다.</div>;
   }
   ```

2. **Bin 수 자동 조정**
   ```javascript
   const getBinCount = (signalCount) => {
     if (signalCount < 30) return 5;      // 신호 < 30: 5 bin
     if (signalCount <= 100) return 10;   // 신호 <= 100: 10 bin
     if (signalCount <= 500) return 15;   // 신호 <= 500: 15 bin
     return 20;                            // 신호 > 500: 20 bin
   };
   ```

3. **색상 CSS 변수화**
   - 양수(수익): CSS 변수 `--color-profit: #28a745`
   - 음수(손실): CSS 변수 `--color-loss: #dc3545`
   - 이를 통해 테마 일관성 확보

**구현 단계**:
1. `frontend/src/components/ReturnsDistributionChart.jsx` 생성
2. `frontend/src/utils/charts.ts`에 `calculateReturnsDistribution` 함수 작성
3. `BacktestResults.jsx`에서 ReturnsDistributionChart 컴포넌트 import 및 렌더링
4. 스타일을 `frontend/src/styles/charts.css`에 추가

---

### Phase 3: Multi-Symbol Chart (우선순위: 상)
**시작 시점**: Phase 2 완료 후

**핵심 지침**:

1. **심볼 수가 1개일 때는 섹션 숨김**
   ```jsx
   if (!symbols || symbols.length <= 1) {
     return null;
   }
   ```

2. **체크박스 UI 상태 관리**
   ```javascript
   const [selectedSymbols, setSelectedSymbols] = useState(
     symbols.map(s => s.symbol) // 초기값: 모든 심볼 선택
   );

   // Validation: 최소 1개 이상 선택 필수
   const toggleSymbol = (symbol) => {
     if (selectedSymbols.includes(symbol)) {
       // 선택 해제하되, 최소 1개 선택 유지
       if (selectedSymbols.length > 1) {
         setSelectedSymbols(selectedSymbols.filter(s => s !== symbol));
       }
     } else {
       setSelectedSymbols([...selectedSymbols, symbol]);
     }
   };
   ```

3. **색상 팔레트 전략**
   ```javascript
   const colorPalette = [
     '#2c3e50',  // BTC_KRW
     '#667eea',  // ETH_KRW
     '#f39c12',  // 추가 심볼
     '#e74c3c',  // 추가 심볼
     '#3498db',  // 추가 심볼
   ];

   // 심볼 수 > 팔레트 크기일 경우 HSL 회전 fallback
   const getSymbolColor = (symbol, index) => {
     if (index < colorPalette.length) {
       return colorPalette[index];
     }
     // Fallback: HSL 회전으로 추가 색상 생성
     const hue = (index * 60) % 360;
     return `hsl(${hue}, 70%, 50%)`;
   };
   ```

**구현 단계**:
1. `frontend/src/components/MultiSymbolChart.jsx` 생성
2. `frontend/src/utils/charts.ts`에 `mergeSymbolData` 함수 작성
3. `BacktestResults.jsx`에서 MultiSymbolChart 컴포넌트 import 및 렌더링
4. 스타일을 `frontend/src/styles/charts.css`에 추가

---

## 8. 테스트 케이스

### 8.1 Drawdown Chart
- [ ] 단일 심볼로 낙폭 차트 렌더링
- [ ] 최대 낙폭과 현재 낙폭 표시 정확성
- [ ] Tooltip 마우스 호버 시 정보 표시
- [ ] 1000+ 포인트 데이터 성능 확인

### 8.2 Returns Distribution
- [ ] 신호 없는 경우 처리
- [ ] 신호 개수별 bin 자동 조정
- [ ] 양수/음수 색상 구분
- [ ] Tooltip에 정확한 통계 표시

### 8.3 Multi-Symbol
- [ ] 단일 심볼: Multi-Symbol 차트 미표시
- [ ] 다중 심볼: 모든 심볼 렌더링
- [ ] 심볼 선택/해제 토글 기능
- [ ] 범례 클릭으로 라인 표시/숨김

---

## 8. 공통 구현 지침

### 8.1 파일 구조
```
frontend/src/
├── components/
│   ├── BacktestResults.jsx          (수정 - 3개 차트 컴포넌트 import)
│   ├── DrawdownChart.jsx            (신규)
│   ├── ReturnsDistributionChart.jsx (신규)
│   └── MultiSymbolChart.jsx         (신규)
├── styles/
│   └── charts.css                   (신규) - 공통 차트 스타일
└── utils/
    └── charts.ts                    (신규) - 데이터 변환 헬퍼 함수
```

### 8.2 데이터 변환 유틸 (frontend/src/utils/charts.ts)
```typescript
/**
 * Drawdown 데이터 계산
 */
export const calculateDrawdownData = (performanceData: PerformancePoint[]) => {
  let maxEquity = 1.0;
  return performanceData.map(point => {
    if (point.equity > maxEquity) maxEquity = point.equity;
    return {
      timestamp: point.timestamp,
      drawdown: ((point.equity - maxEquity) / maxEquity) * 100,
    };
  });
};

/**
 * Returns Distribution 데이터 계산
 */
export const calculateReturnsDistribution = (signals: APISignal[]) => {
  const returns = signals.map(s => s.return_pct * 100);
  const binCount = getBinCount(signals.length);

  // bin 계산 로직...
  return distributionData;
};

/**
 * Multi-Symbol 데이터 병합
 */
export const mergeSymbolData = (symbols: SymbolResult[]) => {
  // 병합 로직...
  return mergedData;
};
```

### 8.3 컴포넌트 구조
**원칙**: 각 차트를 독립적인 프레젠테이션 컴포넌트로 분리

**DrawdownChart.jsx**:
```jsx
const DrawdownChart = ({ performanceData }) => {
  const drawdownData = useMemo(
    () => calculateDrawdownData(performanceData),
    [performanceData]
  );

  if (!performanceData) return null;

  return (
    <div className="chart-section">
      {/* 차트 렌더링 */}
    </div>
  );
};
```

**통합 위치**:
- `BacktestResults.jsx`에서 3개 컴포넌트 import
- 각 컴포넌트에는 필요한 데이터만 전달
- 표시 조건 확인 후 렌더링

### 8.4 표시 조건
```jsx
// BacktestResults.jsx에서

// Drawdown Chart: performance_curve 존재 시 표시
{symbolWithCurve?.performance_curve && renderDrawdownChart()}

// Returns Distribution: signals 존재 시 표시
{symbolWithCurve?.signals && symbolWithCurve.signals.length > 0 && renderReturnsDistributionChart()}

// Multi-Symbol: 심볼 > 1개일 때만 표시
{result.symbols && result.symbols.length > 1 && renderMultiSymbolChart()}
```

### 8.5 스타일 아키텍처
**파일**: `frontend/src/styles/charts.css`

```css
/* 공통 차트 스타일 */
.chart-section {
  margin: 20px 0;
  padding: 20px;
  background: #fff;
  border-radius: 4px;
  border: 1px solid #e0e0e0;
}

.chart-info {
  font-size: 14px;
  color: #666;
  margin-bottom: 15px;
}

.chart-empty {
  padding: 40px;
  text-align: center;
  color: #999;
  background: #f9f9f9;
  border-radius: 4px;
}

/* CSS 변수 (테마 일관성) */
:root {
  --color-profit: #28a745;
  --color-loss: #dc3545;
  --color-grid: #e0e0e0;
}
```

### 8.6 재사용성
**대상**: `SignalViewerPage`, `CompareResultsModal`

- 같은 데이터 변환 함수 재사용
- 컴포넌트는 `frontend/src/components/`의 중앙 위치에서 import
- 필요 시 props 확장 (예: 추가 필터, 커스텀 색상)

### 8.7 테스트 전략
**위치**: `frontend/src/__tests__/utils/charts.test.ts`

```typescript
describe('Chart Data Transformers', () => {
  describe('calculateDrawdownData', () => {
    it('should calculate drawdown correctly', () => {
      // 테스트 케이스
    });
  });

  describe('calculateReturnsDistribution', () => {
    it('should handle empty signals', () => {
      // 테스트 케이스
    });
    it('should adjust bin count based on signal count', () => {
      // 테스트 케이스
    });
  });

  describe('mergeSymbolData', () => {
    it('should merge multi-symbol data correctly', () => {
      // 테스트 케이스
    });
  });
});
```

---

---

## 9. 구현 시작 체크리스트

### Phase 1: Drawdown Chart
- [ ] `frontend/src/components/DrawdownChart.jsx` 생성
- [ ] `frontend/src/utils/charts.ts` 생성 및 `calculateDrawdownData` 함수 작성
- [ ] `BacktestResults.jsx` 수정: DrawdownChart import 및 렌더링
- [ ] `frontend/src/styles/charts.css` 생성 및 스타일 추가
- [ ] useMemo 캐싱 확인
- [ ] 차트 렌더링 테스트

### Phase 2: Returns Distribution Chart
- [ ] `frontend/src/components/ReturnsDistributionChart.jsx` 생성
- [ ] `frontend/src/utils/charts.ts` 수정: `calculateReturnsDistribution`, `getBinCount` 함수 추가
- [ ] BacktestResults.jsx 수정: ReturnsDistributionChart import 및 렌더링
- [ ] 신호 없는 경우 처리 (chart-empty 카드)
- [ ] CSS 변수 `--color-profit`, `--color-loss` 적용
- [ ] bin 수 자동 조정 로직 검증

### Phase 3: Multi-Symbol Chart
- [ ] `frontend/src/components/MultiSymbolChart.jsx` 생성
- [ ] `frontend/src/utils/charts.ts` 수정: `mergeSymbolData`, `getSymbolColor` 함수 추가
- [ ] BacktestResults.jsx 수정: MultiSymbolChart import 및 렌더링
- [ ] useState로 selectedSymbols 상태 관리
- [ ] 최소 1개 선택 validation 구현
- [ ] 심볼 수 > 팔레트 크기일 때 HSL fallback 색상 생성
- [ ] 체크박스 토글 기능 테스트

### 공통
- [ ] `frontend/src/__tests__/utils/charts.test.ts` 작성 (데이터 변환 함수 테스트)
- [ ] `TASK_3_3_TEST_RESULTS.md` 작성 (테스트 로그 추가)
- [ ] git commit 및 push

---

## 10. 요약

| 항목 | Drawdown | Returns Dist. | Multi-Symbol |
|------|----------|---------------|--------------|
| 차트 유형 | AreaChart | BarChart | ComposedChart |
| 높이 | 300px | 300px | 350px |
| 데이터 출처 | performance_curve | signals | performance_curve |
| 데이터 변환 | 계산 필요 | 빈 분류 필요 | 병합 필요 |
| UI 상호작용 | 기본 (Tooltip) | 기본 (Tooltip) | 심볼 선택 체크박스 |
| 우선순위 | **최고** | **상** | **상** |
| 의존성 | 없음 | 없음 | 없음 |
| 예상 시간 | 2-3시간 | 2-3시간 | 3-4시간 |

---

## 11. 최종 지침

**구현 순서**: 1 → 2 → 3

**각 Phase 완료 후**:
1. 로컬에서 모든 차트 렌더링 테스트
2. 데이터 변환 함수 단위 테스트 작성
3. Vitest로 테스트 실행
4. git commit 및 PR 준비

**마무리**:
- 3개 차트 모두 구현 완료 후
- `TASK_3_3_TEST_RESULTS.md`에 테스트 로그 추가
- 최종 PR 제출

