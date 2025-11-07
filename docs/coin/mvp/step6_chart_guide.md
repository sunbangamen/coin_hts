# Step 6: 차트 구현 가이드 (Phase 2)

**작성일**: 2025-11-07
**상태**: Phase 2 계획 문서
**대상**: Phase 2 개발자

---

## 목차
1. 개요
2. 기술 검증 (Phase 1 완료)
3. Phase 2 의사결정 기준
4. 라이브러리 비교 및 선택
5. 구현 가이드
6. 데이터 구조
7. 예상 일정 및 리소스
8. Q&A

---

## 1. 개요

### Step 6 목표
Issue #5 Phase 1에서 구현한 **신호 테이블(Step 4)** 및 **API 연동(Step 5)**을 기반으로,
**Equity Curve 차트** 및 관련 시각화를 Phase 2에서 추가 구현합니다.

### Phase 1 → Phase 2 전환 배경

**Phase 1 결과**:
- ✅ BacktestResults UI 기본 구조 완성
- ✅ SignalsTable 컴포넌트 (신호 목록) 완성
- ✅ API 연동 (동기 방식) 완성
- ✅ Step 6 기술 검증 완료

**Phase 2 목표**:
- 🔄 Equity Curve 차트 추가
- 🔄 거래 신호 오버레이 (선택)
- 🔄 최대 낙폭 시각화 (선택)
- 🔄 비동기 API 개선 (필수)

**연기 이유**:
1. 우선순위: 신호 테이블(Step 4) 및 API 연동(Step 5)이 핵심
2. 리소스: Phase 1 기간 내 모든 Step 완료 불가능
3. 피드백: 사용자 반응 이후 차트 요구사항 재평가 가능

---

## 2. 기술 검증 (Phase 1 완료)

### 2.1 Backend 데이터 구조

✅ **performance_curve 필드 검증 완료**

```json
{
  "symbols": [
    {
      "symbol": "BTC_KRW",
      "signals": [...],
      "win_rate": 0.5,
      "avg_return": 0.0769,
      "max_drawdown": 25.58,
      "avg_hold_bars": 1.0,
      "performance_curve": [
        {
          "timestamp": "2024-01-12",
          "equity": 1.0379,
          "drawdown": null
        },
        {
          "timestamp": "2024-01-15",
          "equity": 1.0938,
          "drawdown": null
        },
        ...
        {
          "timestamp": "2024-02-28",
          "equity": 0.9976,
          "drawdown": null
        }
      ]
    }
  ]
}
```

**데이터 특징**:
- 총 30개 포인트 (BTC_KRW 기준)
- timestamp: 신호 발생 날짜 (YYYY-MM-DD)
- equity: 누적 수익률 (소수점, 1.0 = 기준점)
- drawdown: 해당 시점 낙폭 (현재: null, Phase 2에서 계산 가능)

**데이터 범위**:
- 최소: 0.9139 (-8.61%)
- 최대: 1.1955 (+19.55%)
- 전체: -0.24% (최종 손실)

### 2.2 Equity Curve 로직

**정의**:
- 각 거래 완료 후의 누적 수익률 추적
- 거래 신호 발생 시점마다 하나의 데이터 포인트

**계산 예시**:
```
거래 1: 진입가 100, 청산가 103.5 → 수익률 +3.5%
  Equity = 1.0 + 0.035 = 1.035

거래 2: 진입가 103.5, 청산가 109.0 → 수익률 +5.4%
  Equity = 1.035 * 1.054 = 1.0910

거래 3: 진입가 109.0, 청산가 105.4 → 수익률 -3.3%
  Equity = 1.0910 * 0.967 = 1.0560
```

**구현 시 고려사항**:
- 누적 곱셈 (각 거래의 수익률을 곱함)
- 음수 수익률 처리 (손실)
- 최대 Drawdown 계산 (고점에서 저점까지의 낙폭)

### 2.3 라이브러리 후보 비교

#### Recharts (권장)
**장점**:
- ✅ React 최적화 (JSX 기반)
- ✅ 간단한 API (LineChart, XAxis, YAxis, Line, Tooltip)
- ✅ 반응형 자동 지원
- ✅ 많은 예제와 커뮤니티
- ✅ TypeScript 지원

**단점**:
- Bundle 크기: ~100KB (gzip)
- 복잡한 커스터마이징 시 학습 곡선

**추천도**: ⭐⭐⭐⭐⭐

**설치**:
```bash
npm install recharts
```

**기본 예시**:
```jsx
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend } from 'recharts'

function EquityChart({ data }) {
  return (
    <LineChart width={800} height={400} data={data}>
      <XAxis dataKey="timestamp" />
      <YAxis />
      <Tooltip formatter={(value) => value.toFixed(4)} />
      <Legend />
      <Line
        type="monotone"
        dataKey="equity"
        stroke="#82ca9d"
        dot={false}
      />
    </LineChart>
  )
}
```

---

#### Chart.js
**장점**:
- ✅ 매우 인기 (대규모 커뮤니티)
- ✅ 가볍고 빠름
- ✅ 다양한 차트 유형

**단점**:
- ❌ React 통합이 복잡 (react-chartjs-2 필요)
- ⚠️ 상태 관리 어려움
- ⚠️ 커스터마이징 복잡

**추천도**: ⭐⭐⭐

**설치**:
```bash
npm install chart.js react-chartjs-2
```

---

#### Victory
**장점**:
- ✅ React Native 호환 가능
- ✅ 고급 커스터마이징 지원
- ✅ 애니메이션

**단점**:
- ❌ Bundle 크기 크다 (~200KB)
- ⚠️ 학습 곡선 가파름
- ⚠️ 문서가 충분하지 않음

**추천도**: ⭐⭐

---

### 2.4 라이브러리 선택 결과

**선택**: **Recharts**

**근거**:
1. React 기반 프로젝트에 최적화
2. 간단한 API로 빠른 구현
3. 반응형 자동 지원
4. 신호 오버레이 확장 용이
5. 커뮤니티 크기

---

## 3. Phase 2 의사결정 기준

### Phase 2 킥오프 시점에 다음을 검토하세요:

**의사결정 1: 차트 구현 여부**

| 기준 | Yes (구현) | No (보류) |
|------|----------|----------|
| **사용자 피드백** | 신호 테이블만으로 부족 | 충분함 |
| **개발 리소스** | 3-5일 투입 가능 | 다른 기능 우선 |
| **시간 제약** | Phase 2 내 완료 가능 | 시간 부족 |
| **우선순위** | 높음 (MVP 필수) | 낮음 (선택) |

**권장**: 최소한 Equity Curve 차트는 구현 (가장 가치 높음)

---

**의사결정 2: 차트 상세 기능**

| 기능 | 우선순위 | 예상 시간 | 구현 여부 |
|------|----------|---------|---------|
| Equity Curve (라인 차트) | P1 (필수) | 1-2일 | ✅ 권장 |
| 신호 오버레이 (점 표시) | P2 (권장) | 1-2일 | 🔄 선택 |
| 거래 수 차트 (막대) | P3 (선택) | 1일 | ❌ 보류 |
| 최대 낙폭 영역 표시 | P2 (권장) | 0.5-1일 | 🔄 선택 |
| 실시간 업데이트 | P3 (선택) | 2-3일 | ❌ Phase 3 |

---

## 4. 구현 가이드 (Phase 2)

### 4.1 Recharts 설치 및 기본 설정

```bash
# 1. Recharts 설치
npm install recharts

# 2. 필요한 유틸리티 함수 추가
# frontend/src/utils/chartUtils.js (신규)
```

### 4.2 데이터 변환 (필요시)

```javascript
// frontend/src/utils/chartUtils.js

/**
 * BacktestResponse 데이터를 차트용으로 변환
 */
export function transformPerformanceData(performanceCurve) {
  // 데이터 정렬 (시간순)
  const sorted = [...performanceCurve].sort((a, b) =>
    new Date(a.timestamp) - new Date(b.timestamp)
  )

  // 차트용 포맷으로 변환
  return sorted.map(point => ({
    timestamp: point.timestamp,
    equity: point.equity,
    equityPercent: (point.equity - 1) * 100,  // 퍼센트로 변환
    drawdown: point.drawdown || 0,
  }))
}

/**
 * 신호 데이터를 차트 오버레이로 변환
 */
export function transformSignalsForOverlay(signals) {
  return signals.map(signal => ({
    timestamp: signal.timestamp.split('T')[0],  // 날짜만 추출
    type: signal.type,
    return_pct: signal.return_pct,
    entry_price: signal.entry_price,
  }))
}

/**
 * 최대 낙폭 계산
 */
export function calculateDrawdowns(performanceCurve) {
  let maxEquity = 1.0
  const drawdowns = []

  performanceCurve.forEach(point => {
    maxEquity = Math.max(maxEquity, point.equity)
    const drawdown = ((point.equity - maxEquity) / maxEquity) * 100
    drawdowns.push({
      timestamp: point.timestamp,
      drawdown,
      equityPercent: (point.equity - 1) * 100,
    })
  })

  return drawdowns
}
```

### 4.3 EquityChart 컴포넌트 (기본)

```jsx
// frontend/src/components/EquityChart.jsx

import React from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

/**
 * Equity Curve 차트 컴포넌트
 *
 * Props:
 *   - data: performance_curve 배열
 *   - symbol: 심볼 이름
 */
export default function EquityChart({ data, symbol }) {
  if (!data || data.length === 0) {
    return <div className="chart-empty">차트 데이터 없음</div>
  }

  // 데이터 변환 (필요시)
  const chartData = data.map(point => ({
    timestamp: point.timestamp,
    equity: parseFloat(point.equity.toFixed(4)),
    equityPercent: ((point.equity - 1) * 100).toFixed(2),
  }))

  return (
    <div className="equity-chart-container">
      <h3>수익률 곡선 ({symbol})</h3>
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="timestamp"
            tick={{ fontSize: 12 }}
            interval={Math.max(0, Math.floor(chartData.length / 10))}
          />
          <YAxis
            tick={{ fontSize: 12 }}
            label={{ value: '누적 수익률', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip
            formatter={(value) => {
              if (typeof value === 'number') {
                return value.toFixed(4)
              }
              return value
            }}
            labelFormatter={(label) => `${label}`}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="equity"
            stroke="#82ca9d"
            dot={false}
            strokeWidth={2}
            name="Equity Curve"
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
```

### 4.4 BacktestResults 컴포넌트 통합

```jsx
// frontend/src/components/BacktestResults.jsx (수정)

import React from 'react'
import MetricsTable from './MetricsTable'
import SignalsTable from './SignalsTable'
import EquityChart from './EquityChart'  // 추가

export default function BacktestResults({ result }) {
  if (!result || !result.symbols) {
    return <div>결과 데이터 없음</div>
  }

  return (
    <div className="backtest-results">
      <h2>{result.strategy} 백테스트 결과</h2>
      <p>실행 ID: {result.run_id}</p>

      {result.symbols.map((symbolResult) => (
        <div key={symbolResult.symbol} className="symbol-section">
          <h3>{symbolResult.symbol}</h3>

          {/* 지표 테이블 */}
          <MetricsTable result={symbolResult} />

          {/* 차트 (Phase 2) */}
          {symbolResult.performance_curve && (
            <EquityChart
              data={symbolResult.performance_curve}
              symbol={symbolResult.symbol}
            />
          )}

          {/* 신호 테이블 */}
          <SignalsTable
            symbol={symbolResult.symbol}
            signals={symbolResult.signals}
          />
        </div>
      ))}
    </div>
  )
}
```

### 4.5 CSS 스타일링 (예시)

```css
/* frontend/src/App.css (추가) */

.equity-chart-container {
  margin: 20px 0;
  padding: 20px;
  background: #f9f9f9;
  border-radius: 8px;
}

.equity-chart-container h3 {
  margin-top: 0;
  color: #333;
}

.chart-empty {
  text-align: center;
  padding: 40px;
  color: #999;
}

/* 반응형 디자인 */
@media (max-width: 768px) {
  .equity-chart-container {
    margin: 15px 0;
    padding: 15px;
  }
}
```

---

## 5. 데이터 구조

### 5.1 Backend 응답 (이미 구현됨)

```python
class PerformancePoint(BaseModel):
    """성과곡선 포인트"""
    timestamp: str           # YYYY-MM-DD
    equity: float            # 누적 수익률 (1.0 = 기준)
    drawdown: Optional[float] # 낙폭 (현재: null)

class SymbolResult(BaseModel):
    """심볼별 결과"""
    symbol: str
    signals: List[APISignal]
    win_rate: float
    avg_return: float
    max_drawdown: float
    avg_hold_bars: float
    performance_curve: List[PerformancePoint]  # 차트용 데이터
```

### 5.2 Frontend 컴포넌트 Props

```javascript
// EquityChart
<EquityChart
  data={symbolResult.performance_curve}  // List[PerformancePoint]
  symbol={symbolResult.symbol}           // str
/>

// BacktestResults
<BacktestResults result={response.data} />
```

---

## 6. 예상 일정 및 리소스

### 6.1 개발 일정 (Phase 2)

| 항목 | 예상 시간 | 담당자 |
|------|----------|-------|
| 기술 검토 및 계획 | 0.5-1일 | 리드 개발자 |
| Recharts 통합 | 1-2일 | Frontend 개발자 |
| EquityChart 컴포넌트 | 1-2일 | Frontend 개발자 |
| BacktestResults 통합 | 0.5-1일 | Frontend 개발자 |
| 스타일링 및 반응형 | 1일 | Frontend 개발자 |
| 테스트 및 버그 수정 | 1-2일 | QA / 개발자 |
| **총 일정** | **5-9일** | - |

### 6.2 필요 리소스

**개발 인력**:
- Frontend 개발자: 1명
- Backend 개발자: 0.5명 (비동기 API 구현 필요시)

**외부 라이브러리**:
- recharts: npm 설치
- 추가 라이브러리 불필요

**데이터/환경**:
- 테스트 데이터: 이미 준비됨 (generate_test_data.py)
- Backend API: 이미 준비됨

---

## 7. Q&A

### Q1: 왜 Phase 1에서 차트를 구현하지 않았나?
**A**: Issue #5의 주요 목표는 신호 테이블(Step 4)과 API 연동(Step 5)이고, 차트는 선택사항입니다. Phase 1에서는 최소 viable product(MVP)에 집중했습니다.

### Q2: Phase 2에서 차트를 반드시 구현해야 하나?
**A**: 아니오. Phase 2 킥오프 시점에 우선순위를 재평가합니다. 사용자 피드백 및 개발 리소스에 따라 결정합니다.

### Q3: 신호 오버레이는 어떻게 구현하나?
**A**: Recharts의 Scatter 컴포넌트를 사용하여 라인 차트 위에 신호 포인트를 추가할 수 있습니다:
```jsx
<LineChart>
  <Line dataKey="equity" ... />
  <Scatter dataKey="signals" ... />  // Phase 2 확장
</LineChart>
```

### Q4: 대량 데이터 (1000개 이상 신호)는 어떻게 처리하나?
**A**:
- 단기: ResponsiveContainer로 차트 크기 조정
- 중기: 샘플링 (매 N번째 포인트만 표시)
- 장기: 가상 렌더링 (react-window + Recharts 통합)

### Q5: 모바일에서도 동작하나?
**A**: 예. Recharts의 ResponsiveContainer가 자동으로 반응형을 처리합니다.

### Q6: 비동기 API는 필수인가?
**A**: Phase 2 우선순위 높음. 대량 데이터 처리 시 UI 블로킹을 피하기 위해 필수입니다.

---

## 8. 체크리스트 (Phase 2 개발자용)

### 개발 전
- [ ] 이 가이드 전체 읽기
- [ ] Recharts 공식 문서 검토
- [ ] 기존 SignalsTable, BacktestResults 코드 분석
- [ ] 테스트 데이터 확인

### 개발 중
- [ ] Recharts 설치 및 기본 예제 실행
- [ ] EquityChart 컴포넌트 구현
- [ ] BacktestResults 통합
- [ ] 스타일링 및 반응형 확인
- [ ] 여러 브라우저/기기에서 테스트

### 개발 후
- [ ] 단위 테스트 작성 (optional)
- [ ] 성능 프로파일링 (대량 데이터)
- [ ] 문서화 (comments, README 업데이트)
- [ ] 코드 리뷰 요청
- [ ] 병합 및 배포

---

## 참고 자료

### 공식 문서
- Recharts: https://recharts.org/
- React: https://react.dev/

### 예제 및 튜토리얼
- Recharts LineChart: https://recharts.org/en-US/api/LineChart
- Recharts Examples: https://recharts.org/en-US/examples

### 관련 이슈 및 PR
- Issue #5: React 결과 테이블 및 차트 컴포넌트 구현
- Issue #21: Phase 1 정리
- ri_5.md: Issue #5 상세 계획

---

## 이 가이드에 대한 피드백

Phase 2 개발 중에 이 가이드에 대한 피드백이 있으면 다음을 통해 공유하세요:
- GitHub Issue: #21
- 이메일: (조직 이메일)

추가 예제, 명확한 설명, 또는 보정이 필요하면 언제든 알려주세요!

---

**마지막 업데이트**: 2025-11-07
**다음 검토**: Phase 2 킥오프 (예정)
