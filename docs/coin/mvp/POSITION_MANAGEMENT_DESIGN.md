# Task 3.3: 포지션 관리 설계 문서

**작성일**: 2025-11-08
**상태**: 설계 단계 (구현 준비)
**담당자**: Task 3.3 (Week 2)

---

## 1. 개요

Task 3.3은 백테스트 결과에 **포지션 상세 정보**를 추가하여 실전 트레이딩에 필요한 데이터를 제공합니다.

### 1.1 목표

- [x] Position 모델 정의 (Backend)
- [x] BacktestResult 확장
- [x] API 응답 스키마
- [x] Frontend PositionsTable 컴포넌트
- [x] 데이터베이스 스키마

---

## 2. 데이터 모델 설계

### 2.1 Position 모델 (Backend)

```python
# backend/app/models/position.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Position(BaseModel):
    """개별 거래 포지션"""

    # 식별자
    position_id: str = Field(..., description="포지션 ID (UUID)")
    symbol: str = Field(..., description="거래 심볼 (예: BTC_KRW)")

    # 타이밍
    entry_time: str = Field(..., description="진입 시간 (ISO 8601, UTC)")
    exit_time: str = Field(..., description="청산 시간 (ISO 8601, UTC)")

    # 가격
    entry_price: float = Field(..., description="진입 가격 (원)")
    exit_price: float = Field(..., description="청산 가격 (원)")

    # 거래량
    size: float = Field(..., description="거래량 (BTC, ETH 등)")

    # 방향
    side: str = Field(
        default="LONG",
        description="포지션 방향 (LONG, SHORT, 현재는 LONG만 지원)"
    )

    # 수익성
    pnl: float = Field(..., description="손익 (원)")
    pnl_pct: float = Field(..., description="수익률 (%)")

    # 비용
    fees: float = Field(default=0.0, description="거래 수수료 (원)")

    # 메타데이터
    confidence: float = Field(
        default=0.5,
        description="신호 신뢰도 (0.0 ~ 1.0)"
    )
    hold_duration_bars: int = Field(
        default=1,
        description="보유 기간 (캔들 개수)"
    )

    class Config:
        schema_extra = {
            "example": {
                "position_id": "pos-001",
                "symbol": "BTC_KRW",
                "entry_time": "2024-01-12T00:00:00Z",
                "exit_time": "2024-01-15T00:00:00Z",
                "entry_price": 52364029.59,
                "exit_price": 54349847.91,
                "size": 0.01,
                "side": "LONG",
                "pnl": 19818.32,
                "pnl_pct": 3.79,
                "fees": 107.14,
                "confidence": 0.75,
                "hold_duration_bars": 3,
            }
        }
```

### 2.2 BacktestResult 확장

```python
# backend/app/strategies/base.py (기존)

class BacktestResult(BaseModel):
    # 기존 필드들...
    signals: List[Signal]
    samples: int
    win_rate: float
    avg_return: float
    max_drawdown: float
    avg_hold_bars: float

    # Phase 3 추가 필드
    positions: List[Position] = Field(
        default_factory=list,
        description="포지션 상세 목록"
    )
    entry_exit_pairs: List[Dict] = Field(
        default_factory=list,
        description="진입/청산 가격 쌍 (하위호환)"
    )
    returns: List[float] = Field(
        default_factory=list,
        description="개별 수익률 목록 (하위호환)"
    )
```

### 2.3 API 응답 스키마

```python
# backend/app/main.py

class APIPosition(BaseModel):
    """API 응답용 포지션 정보"""
    position_id: str
    symbol: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    size: float
    side: str
    pnl: float
    pnl_pct: float
    fees: float
    confidence: float
    hold_duration_bars: int


class SymbolResult(BaseModel):
    """심볼별 백테스트 결과 (기존 확장)"""
    symbol: str
    signals: List[APISignal] = Field(default_factory=list)
    positions: List[APIPosition] = Field(  # NEW
        default_factory=list,
        description="포지션 상세 목록"
    )
    win_rate: float
    avg_return: float
    max_drawdown: float
    avg_hold_bars: float
```

---

## 3. 계산 로직

### 3.1 포지션 생성 (신호 → 포지션)

```python
# backend/app/utils/position_calculator.py

def create_position(
    signal: Signal,
    entry_idx: int,
    exit_idx: int,
    df: pd.DataFrame,
    symbol: str,
    fees_rate: float = 0.001,  # 0.1%
) -> Position:
    """신호에서 포지션 생성"""

    # 진입/청산 데이터
    entry_row = df.iloc[entry_idx]
    exit_row = df.iloc[exit_idx]

    entry_time = entry_row['timestamp']
    exit_time = exit_row['timestamp']
    entry_price = entry_row['close']
    exit_price = exit_row['close']

    # 포지션 크기 (고정, Phase 3)
    # 실제로는 트레이더가 결정하는 값이지만, 여기서는 고정으로 설정
    size = 0.01  # 0.01 BTC 또는 동등 가치

    # 수익/손실 계산
    pnl = (exit_price - entry_price) * size
    pnl_pct = ((exit_price - entry_price) / entry_price) * 100

    # 수수료 계산 (진입 + 청산)
    fees = (entry_price * size * fees_rate) + (exit_price * size * fees_rate)

    # 순 손익
    net_pnl = pnl - fees
    net_pnl_pct = (net_pnl / (entry_price * size)) * 100

    return Position(
        position_id=str(uuid.uuid4()),
        symbol=symbol,
        entry_time=entry_time.isoformat() + "Z",
        exit_time=exit_time.isoformat() + "Z",
        entry_price=entry_price,
        exit_price=exit_price,
        size=size,
        side="LONG",  # Phase 3는 LONG만 지원
        pnl=net_pnl,
        pnl_pct=net_pnl_pct,
        fees=fees,
        confidence=signal.confidence,
        hold_duration_bars=exit_idx - entry_idx,
    )
```

### 3.2 메트릭 계산

```python
# 기존 metrics.py에서:

def calculate_metrics(positions: List[Position]) -> Dict:
    """포지션 리스트에서 메트릭 계산"""

    if not positions:
        return {
            "win_rate": 0.0,
            "avg_return": 0.0,
            "max_drawdown": 0.0,
            "avg_hold_bars": 0.0,
        }

    pnls = [p.pnl for p in positions]
    returns = [p.pnl_pct for p in positions]

    # 승률 (이익 거래 / 전체 거래)
    win_count = sum(1 for p in positions if p.pnl > 0)
    win_rate = win_count / len(positions)

    # 평균 수익률
    avg_return = sum(returns) / len(returns)

    # 최대 낙폭 (누적 이익 추적)
    cumulative = 0
    running_max = 0
    max_drawdown = 0
    for pnl in pnls:
        cumulative += pnl
        running_max = max(running_max, cumulative)
        drawdown = (running_max - cumulative) / running_max if running_max > 0 else 0
        max_drawdown = max(max_drawdown, drawdown)

    # 평균 보유 기간
    avg_hold_bars = sum(p.hold_duration_bars for p in positions) / len(positions)

    return {
        "win_rate": win_rate,
        "avg_return": avg_return,
        "max_drawdown": max_drawdown,
        "avg_hold_bars": avg_hold_bars,
    }
```

---

## 4. 데이터베이스 스키마

### 4.1 포지션 테이블 (선택사항, Phase 4)

```sql
-- 현재는 JSON 응답으로만 제공, DB 저장은 Task 3.5 참고

-- Task 3.5에서:
CREATE TABLE backtest_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backtest_run_id UUID NOT NULL REFERENCES backtest_runs(run_id),
    position_id VARCHAR(36) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    exit_price NUMERIC(20, 8) NOT NULL,
    size NUMERIC(20, 8) NOT NULL,
    side VARCHAR(10) NOT NULL,
    pnl NUMERIC(20, 2) NOT NULL,
    pnl_pct NUMERIC(10, 4) NOT NULL,
    fees NUMERIC(20, 2) NOT NULL,
    confidence NUMERIC(3, 2) NOT NULL,
    hold_duration_bars INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    INDEX idx_backtest_symbol (backtest_run_id, symbol)
);
```

---

## 5. API 엔드포인트

### 5.1 백테스트 결과 조회 (포지션 포함)

**기존 엔드포인트** (Phase 2):
```
POST /api/backtests/run
```

**응답** (Phase 3 확장):
```json
{
  "version": "1.1.0",
  "run_id": "...",
  "strategy": "volume_zone_breakout",
  "symbols": [
    {
      "symbol": "BTC_KRW",
      "positions": [  // NEW
        {
          "position_id": "pos-001",
          "entry_time": "2024-01-12T00:00:00Z",
          "exit_time": "2024-01-15T00:00:00Z",
          "entry_price": 52364029.59,
          "exit_price": 54349847.91,
          "size": 0.01,
          "pnl": 19818.32,
          "pnl_pct": 3.79,
          "fees": 107.14
        },
        // ... 추가 포지션
      ],
      "win_rate": 0.65,
      "avg_return": 2.34,
      "max_drawdown": 0.12,
      "avg_hold_bars": 3.2
    }
  ]
}
```

### 5.2 포지션 필터링 (선택사항, Phase 4)

```
GET /api/backtests/{run_id}/positions?
  symbol=BTC_KRW&
  min_pnl=1000&
  side=LONG&
  sort=pnl_pct&
  order=desc
```

---

## 6. Frontend 컴포넌트

### 6.1 PositionsTable 구성

```jsx
// frontend/src/components/PositionsTable.jsx

function PositionsTable({ positions, symbol }) {
  const [sortKey, setSortKey] = useState('entry_time');
  const [sortOrder, setSortOrder] = useState('asc');

  // 포지션 정렬
  const sorted = positions.sort((a, b) => {
    const aVal = a[sortKey];
    const bVal = b[sortKey];
    return sortOrder === 'asc' ? aVal - bVal : bVal - aVal;
  });

  return (
    <table className="positions-table">
      <thead>
        <tr>
          <th onClick={() => setSortKey('entry_time')}>진입시간</th>
          <th onClick={() => setSortKey('exit_time')}>청산시간</th>
          <th onClick={() => setSortKey('entry_price')}>진입가</th>
          <th onClick={() => setSortKey('exit_price')}>청산가</th>
          <th onClick={() => setSortKey('pnl')}>손익</th>
          <th onClick={() => setSortKey('pnl_pct')}>수익률</th>
          <th>수수료</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map(pos => (
          <tr key={pos.position_id} className={pos.pnl > 0 ? 'profit' : 'loss'}>
            <td>{new Date(pos.entry_time).toLocaleDateString()}</td>
            <td>{new Date(pos.exit_time).toLocaleDateString()}</td>
            <td>{pos.entry_price.toLocaleString('ko-KR')}</td>
            <td>{pos.exit_price.toLocaleString('ko-KR')}</td>
            <td className={pos.pnl > 0 ? 'positive' : 'negative'}>
              ₩{Math.abs(pos.pnl).toLocaleString('ko-KR')}
            </td>
            <td className={pos.pnl_pct > 0 ? 'positive' : 'negative'}>
              {pos.pnl_pct > 0 ? '+' : ''}{pos.pnl_pct.toFixed(2)}%
            </td>
            <td>₩{pos.fees.toLocaleString('ko-KR')}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

### 6.2 통계 패널

```jsx
// frontend/src/components/PositionStats.jsx

function PositionStats({ positions }) {
  const stats = {
    total: positions.length,
    winners: positions.filter(p => p.pnl > 0).length,
    losers: positions.filter(p => p.pnl < 0).length,
    totalPnl: positions.reduce((sum, p) => sum + p.pnl, 0),
    avgPnl: positions.reduce((sum, p) => sum + p.pnl, 0) / positions.length,
    avgPnlPct: positions.reduce((sum, p) => sum + p.pnl_pct, 0) / positions.length,
    totalFees: positions.reduce((sum, p) => sum + p.fees, 0),
  };

  return (
    <div className="position-stats">
      <div>총 거래: {stats.total}</div>
      <div>승리: {stats.winners} ({((stats.winners/stats.total)*100).toFixed(1)}%)</div>
      <div>평균 손익: ₩{stats.avgPnl.toLocaleString('ko-KR')}</div>
      <div>평균 수익률: {stats.avgPnlPct.toFixed(2)}%</div>
      <div>총 수수료: ₩{stats.totalFees.toLocaleString('ko-KR')}</div>
    </div>
  );
}
```

---

## 7. 구현 단계

### Step 1: 모델 정의 (1-2일)

- [ ] `backend/app/models/position.py` 생성
- [ ] Position Pydantic 모델 정의
- [ ] 단위 테스트: `tests/models/test_position.py`

### Step 2: 계산 로직 (1-2일)

- [ ] `backend/app/utils/position_calculator.py` 생성
- [ ] 포지션 생성 로직
- [ ] 메트릭 계산 로직
- [ ] 단위 테스트: `tests/utils/test_position_calculator.py`

### Step 3: API 통합 (1일)

- [ ] BacktestResult에 positions 필드 추가
- [ ] run_backtest() 엔드포인트 수정
- [ ] 응답 스키마 업데이트
- [ ] 통합 테스트: `tests/api/test_backtests_positions.py`

### Step 4: Frontend 컴포넌트 (1-2일)

- [ ] PositionsTable 컴포넌트
- [ ] PositionStats 컴포넌트
- [ ] CSS 스타일링
- [ ] 통합 테스트: `tests/frontend/test_positions_table.test.js`

**예상 총 소요 시간**: 2-3일

---

## 8. 테스트 계획

### 8.1 단위 테스트

```python
# tests/models/test_position.py
def test_position_creation():
    """포지션 생성"""
    pos = Position(
        position_id="pos-001",
        symbol="BTC_KRW",
        entry_time="2024-01-12T00:00:00Z",
        exit_time="2024-01-15T00:00:00Z",
        entry_price=52000000,
        exit_price=53000000,
        size=0.01,
        pnl=10000,
        pnl_pct=1.92,
        fees=100,
    )
    assert pos.pnl > 0
    assert pos.pnl_pct > 0

# tests/utils/test_position_calculator.py
def test_position_calculation():
    """포지션 계산 정확도"""
    signal = Signal(...)
    entry_idx, exit_idx = 10, 15
    df = load_test_data()

    pos = create_position(signal, entry_idx, exit_idx, df, "BTC_KRW")

    expected_pnl = (exit_price - entry_price) * size
    assert abs(pos.pnl - expected_pnl) < 1  # 1원 오차
```

### 8.2 통합 테스트

```python
# tests/api/test_backtests_positions.py
def test_backtest_includes_positions():
    """백테스트 결과에 포지션 포함"""
    response = client.post("/api/backtests/run", json={...})
    result = response.json()

    for symbol_result in result["symbols"]:
        assert "positions" in symbol_result
        for pos in symbol_result["positions"]:
            assert "pnl" in pos
            assert "pnl_pct" in pos
```

---

## 9. 마이그레이션 전략

### 하위호환성

```python
# 기존 클라이언트를 위해 유지
entry_exit_pairs: List[Dict]  # Phase 1-2 호환
returns: List[float]           # Phase 1-2 호환

# 새로운 포맷
positions: List[Position]      # Phase 3+
```

---

## 10. 미래 확장 (Phase 4+)

- [ ] SHORT 포지션 지원
- [ ] 레버리지 거래
- [ ] 포지션 DB 저장 (PostgreSQL)
- [ ] 포지션 필터링 API
- [ ] 포지션 내보내기 (CSV, Excel)

---

**다음 단계**: Task 3.3 구현 (Week 2)

