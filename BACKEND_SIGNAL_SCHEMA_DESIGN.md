# Backend Signal 스키마 설계 문서

**작성 날짜**: 2025-11-03
**상태**: ✅ 설계 완료, 구현 대기
**목표**: Step 4 신호 테이블 Frontend 구현을 위한 Backend API 확장

---

## 📋 개요

현재 Backend API는 심볼별 요약 지표만 반환합니다. Step 4 신호 테이블을 구현하기 위해 개별 신호 데이터를 반환하도록 API를 확장해야 합니다.

### 현재 상태
```python
class SymbolResult(BaseModel):
    symbol: str
    signals: int              # 개수만 반환
    win_rate: float
    avg_return: float
    max_drawdown: float
    avg_hold_bars: float
```

### 목표 상태
```python
class Signal(BaseModel):
    symbol: str
    type: str                 # "buy" or "sell"
    timestamp: str            # ISO 8601
    entry_price: float
    exit_price: float
    return: float            # -0.05 ~ 0.10 (소수점 값)

class SymbolResult(BaseModel):
    symbol: str
    signals: List[Signal]    # 배열로 변경
    win_rate: float
    avg_return: float
    max_drawdown: float
    avg_hold_bars: float
```

---

## 🎯 Signal 스키마 상세 설계

### Signal Pydantic 모델

```python
from pydantic import BaseModel
from typing import List
from datetime import datetime

class Signal(BaseModel):
    """개별 거래 신호"""

    symbol: str
    """거래 심볼 (예: "BTC_KRW")"""

    type: str
    """신호 타입: "buy" 또는 "sell" """

    timestamp: str
    """신호 발생 시간 (ISO 8601 형식, UTC)
    예: "2024-01-15T09:30:00Z"
    """

    entry_price: float
    """진입 가격 (KRW)
    구매가 (buy) 또는 판매가 (sell)"""

    exit_price: float
    """청산 가격 (KRW)
    판매가 (buy의 경우) 또는 구매가 (sell의 경우)
    미청산 시 현재 가격 또는 None"""

    return: float
    """거래 수익률 (소수점)
    예: 0.05 (5%), -0.03 (-3%)
    미청산 시 미실현 수익률"""

    class Config:
        schema_extra = {
            "example": {
                "symbol": "BTC_KRW",
                "type": "buy",
                "timestamp": "2024-01-15T09:30:00Z",
                "entry_price": 50000000.0,
                "exit_price": 51500000.0,
                "return": 0.03
            }
        }
```

### SymbolResult 수정 (확장)

```python
class SymbolResult(BaseModel):
    """심볼별 백테스트 결과"""

    symbol: str
    signals: List[Signal]    # int → List[Signal] 변경
    win_rate: float
    avg_return: float
    max_drawdown: float
    avg_hold_bars: float
```

### BacktestResponse (변경 없음)

```python
class BacktestResponse(BaseModel):
    """백테스트 응답 모델"""

    run_id: str
    strategy: str
    params: Dict[str, Any]
    start_date: str
    end_date: str
    timeframe: str
    symbols: List[SymbolResult]    # 변경 없음 (SymbolResult가 확장됨)
    total_signals: int
    execution_time: float
```

---

## 📊 API 응답 예시

### 요청
```bash
POST /api/backtests/run
Content-Type: application/json

{
  "strategy": "volume_long_candle",
  "symbols": ["BTC_KRW"],
  "start_date": "2024-01-01",
  "end_date": "2024-06-30",
  "timeframe": "1d",
  "params": {
    "vol_ma_window": 20,
    "vol_multiplier": 2.0,
    "body_pct": 0.7
  }
}
```

### 응답 (확장된 버전)
```json
{
  "run_id": "bdd26144-e12f-486a-9e8c-df68227517f9",
  "strategy": "volume_long_candle",
  "params": {
    "vol_ma_window": 20,
    "vol_multiplier": 2.0,
    "body_pct": 0.7
  },
  "start_date": "2024-01-01",
  "end_date": "2024-06-30",
  "timeframe": "1d",
  "symbols": [
    {
      "symbol": "BTC_KRW",
      "signals": [
        {
          "symbol": "BTC_KRW",
          "type": "buy",
          "timestamp": "2024-01-15T09:30:00Z",
          "entry_price": 50000000.0,
          "exit_price": 51500000.0,
          "return": 0.03
        },
        {
          "symbol": "BTC_KRW",
          "type": "sell",
          "timestamp": "2024-01-20T14:45:00Z",
          "entry_price": 51500000.0,
          "exit_price": 50800000.0,
          "return": -0.0136
        },
        {
          "symbol": "BTC_KRW",
          "type": "buy",
          "timestamp": "2024-02-05T11:20:00Z",
          "entry_price": 50800000.0,
          "exit_price": 52300000.0,
          "return": 0.0295
        }
      ],
      "win_rate": 0.67,
      "avg_return": 0.0053,
      "max_drawdown": -0.05,
      "avg_hold_bars": 5.2
    }
  ],
  "total_signals": 3,
  "execution_time": 2.34
}
```

---

## 🔧 구현 계획 (Backend)

### Phase 1: 스키마 정의

**파일**: `backend/app/models.py` (또는 별도 `backend/app/schemas.py`)

```python
from pydantic import BaseModel
from typing import List

class Signal(BaseModel):
    symbol: str
    type: str
    timestamp: str
    entry_price: float
    exit_price: float
    return: float

class SymbolResult(BaseModel):
    symbol: str
    signals: List[Signal]    # 변경
    win_rate: float
    avg_return: float
    max_drawdown: float
    avg_hold_bars: float
```

### Phase 2: 데이터 생성 로직

**위치**: Strategy 실행 결과에서 신호 추출

현재 Strategy 구조:
```python
class StrategyResult:
    samples: int              # 신호 개수
    win_rate: float
    avg_return: float
    max_drawdown: float
    avg_hold_bars: float

    # 추가 필요:
    # signals: List[Signal]    # 개별 신호 데이터
```

**필요한 정보**:
1. 각 신호의 진입/청산 시점과 가격
2. 신호 타입 (buy/sell)
3. 거래 수익률

### Phase 3: API 응답 변환

**파일**: `backend/app/main.py` (run_backtest 함수)

```python
# 현재 (변경 전)
symbol_results.append(
    SymbolResult(
        symbol=symbol,
        signals=result.samples,          # int
        win_rate=result.win_rate,
        ...
    )
)

# 변경 후
symbol_results.append(
    SymbolResult(
        symbol=symbol,
        signals=result.signals,          # List[Signal]
        win_rate=result.win_rate,
        ...
    )
)
```

---

## 📝 Frontend 활용 시나리오

### Step 4 신호 테이블 렌더링

```javascript
// frontend/src/components/BacktestResults.jsx

const renderSignalsSection = () => {
  if (!result.symbols) return null;

  return (
    <div className="signals-section">
      <h3>신호 목록</h3>
      {result.symbols.map(symbol => (
        <table key={symbol.symbol}>
          <thead>
            <tr>
              <th>심볼</th>
              <th>타입</th>
              <th>시간</th>
              <th>진입가</th>
              <th>청산가</th>
              <th>수익률</th>
            </tr>
          </thead>
          <tbody>
            {symbol.signals.map((signal, idx) => (
              <tr key={idx}>
                <td>{signal.symbol}</td>
                <td className={`type ${signal.type}`}>
                  {signal.type === 'buy' ? '매수' : '매도'}
                </td>
                <td>{formatDateTime(signal.timestamp)}</td>
                <td>{signal.entry_price.toLocaleString()}</td>
                <td>{signal.exit_price.toLocaleString()}</td>
                <td className={getValueClass(signal.return)}>
                  {formatPercent(signal.return)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ))}
    </div>
  )
}
```

---

## ✅ 구현 체크리스트

### Backend

- [ ] Signal Pydantic 모델 정의
- [ ] SymbolResult.signals 타입 변경 (int → List[Signal])
- [ ] Strategy 실행 시 신호 데이터 수집
- [ ] Signal 객체 생성 로직
- [ ] BacktestResponse에 신호 데이터 포함
- [ ] API 응답 검증 (샘플 실행 후)
- [ ] 에러 처리 및 로깅

### Frontend

- [ ] Signal 타입 정의 (TypeScript)
- [ ] 신호 테이블 컴포넌트
- [ ] 정렬 기능 (시간순, 수익률순)
- [ ] 색상 코딩 (양수/음수)
- [ ] BacktestResults에 신호 섹션 통합
- [ ] 테스트 데이터로 UI 검증

---

## 🚀 예상 일정

**Week 1: Backend 구현**
- 월: Signal 모델 + 데이터 수집 로직 (2-3시간)
- 화: 통합 + API 테스트 (2시간)
- 수: 버그 수정 + 최적화 (2시간)

**Week 2: Frontend 구현**
- 목: 신호 테이블 컴포넌트 (3시간)
- 금: 정렬 + 색상 코딩 (2시간)
- 월: 통합 + 테스트 (2시간)

**병렬: 테스트 데이터 준비** (모든 주)
- OHLCV 파일 준비
- 실제 백테스트 실행

---

## 💡 참고 사항

### 신호 데이터 정확성

- 시간대: UTC 사용 권장 (타임존 혼동 방지)
- 가격: 정확한 진입/청산 가격 필요
- 수익률: (exit_price - entry_price) / entry_price

### 대량 신호 처리

- 신호 100개 이상 예상 시 페이지네이션 검토
- 현재: 정렬만 구현, 가상 스크롤링은 추후

### 향후 확장

- buy/sell 외 다른 신호 타입 추가
- 신호별 confidence/strength 추가
- 미청산 신호 구분

---

**다음 단계**: Backend API 구현 시작 ✅
