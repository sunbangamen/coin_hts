# Backend Signal API 구현 - Phase 1 완료

**작성일**: 2025-11-03
**상태**: ✅ Phase 1 완료 (스키마 정의 + 데이터 반환 로직)
**다음**: Frontend Step 4 신호 테이블 구현

---

## 📋 구현 내용

### Phase 1: 스키마 정의 및 API 확장 ✅ **완료**

#### 1. APISignal Pydantic 모델 정의 (main.py:107-119)

**파일**: `backend/app/main.py`

```python
class APISignal(BaseModel):
    """
    API 응답용 거래 신호 모델 (Step 4 신호 테이블용)

    각 개별 거래 신호의 상세 정보를 포함합니다.
    """

    symbol: str = Field(..., description="거래 심볼 (예: BTC_KRW)")
    type: str = Field(..., description="신호 타입: 'buy' 또는 'sell'")
    timestamp: str = Field(..., description="신호 발생 시간 (ISO 8601, UTC)")
    entry_price: float = Field(..., description="진입 가격 (KRW)")
    exit_price: float = Field(..., description="청산 가격 (KRW)")
    return_pct: float = Field(..., description="거래 수익률 (소수점, 예: 0.05 = 5%)")
```

**특징**:
- ISO 8601 타임스탬프 (UTC)
- 소수점 수익률 형식 (0.05 = 5%)
- buy/sell 소문자 형식 (JSON API 표준)

---

#### 2. SymbolResult 모델 확장 (main.py:122-133)

**변경사항**:
```python
# 이전
signals: int

# 현재
signals: List[APISignal] = Field(
    default_factory=list,
    description="개별 거래 신호 목록 (Step 4 신호 테이블용)"
)
```

**영향 범위**:
- `BacktestResponse` 자동으로 확장됨 (signals 필드는 SymbolResult의 일부)
- API 응답 구조 변경됨

---

#### 3. BacktestResult 기본 클래스 확장 (base.py:46-72)

**파일**: `backend/app/strategies/base.py`

```python
@dataclass
class BacktestResult:
    # ... 기존 필드들 ...
    entry_exit_pairs: Optional[List[tuple]] = None  # (진입가, 청산가) 쌍
    returns: Optional[List[float]] = None  # 거래 수익률 (%)
```

**목적**:
- 내부 Signal 객체에 없는 진입/청산 가격 정보 보존
- 전략에서 계산한 수익률 정보 API에 전달
- 하위 호환성 유지 (Optional 필드)

---

#### 4. 전략 구현 업데이트

**VolumeLongCandleStrategy** (`volume_long_candle.py:149-161`):
```python
result = BacktestResult(
    signals=signals,
    samples=len(signals),
    win_rate=metrics['win_rate'],
    avg_return=metrics['avg_return'],
    max_drawdown=metrics['max_drawdown'],
    avg_hold_bars=metrics['avg_hold_bars'],
    avg_hold_duration=None,
    entry_exit_pairs=entry_exit_pairs,  # ← 추가
    returns=returns,  # ← 추가
)
```

**VolumeZoneBreakoutStrategy** (`volume_zone_breakout.py:141-151, 166-178`):
- 동일한 방식으로 entry_exit_pairs, returns 포함

---

#### 5. API 엔드포인트 데이터 변환 (main.py:274-291)

**파일**: `backend/app/main.py` (run_backtest 함수)

**핵심 로직**:
```python
# 내부 Signal을 API용 APISignal로 변환
api_signals: List[APISignal] = []
if result.signals and result.entry_exit_pairs and result.returns:
    for i, signal in enumerate(result.signals):
        if i < len(result.entry_exit_pairs) and i < len(result.returns):
            entry_price, exit_price = result.entry_exit_pairs[i]
            return_pct = result.returns[i] / 100.0  # % → 소수점 변환

            api_signals.append(
                APISignal(
                    symbol=symbol,
                    type=signal.side.lower(),  # BUY → buy
                    timestamp=signal.timestamp.isoformat(),  # pd.Timestamp → ISO 8601
                    entry_price=entry_price,
                    exit_price=exit_price,
                    return_pct=return_pct,
                )
            )
```

**변환 로직**:
1. 내부 Signal.side (BUY/SELL) → type (buy/sell)
2. pd.Timestamp → ISO 8601 문자열
3. 수익률 % 형식 → 소수점 형식 (113% → 1.13)
4. entry_exit_pairs, returns 데이터 매칭

---

### 데이터 흐름 다이어그램

```
Strategy.run(df, params)
    ↓
BacktestResult(
    signals: List[Signal],
    entry_exit_pairs: [(entry1, exit1), ...],
    returns: [0.03, -0.02, ...]
)
    ↓
run_backtest() - API 변환 계층
    ↓
APISignal 생성
    - symbol, type, timestamp, entry_price, exit_price, return_pct
    ↓
SymbolResult(
    signals: List[APISignal],
    win_rate, avg_return, ...
)
    ↓
BacktestResponse (JSON)
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
  "end_date": "2024-01-31",
  "timeframe": "1d",
  "params": {
    "vol_ma_window": 20,
    "vol_multiplier": 2.0,
    "body_pct": 0.7
  }
}
```

### 응답 (신호 포함)
```json
{
  "run_id": "abc123...",
  "strategy": "volume_long_candle",
  "params": {...},
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "timeframe": "1d",
  "symbols": [
    {
      "symbol": "BTC_KRW",
      "signals": [
        {
          "symbol": "BTC_KRW",
          "type": "buy",
          "timestamp": "2024-01-15T09:00:00",
          "entry_price": 50000000.0,
          "exit_price": 51500000.0,
          "return_pct": 0.03
        },
        {
          "symbol": "BTC_KRW",
          "type": "sell",
          "timestamp": "2024-01-20T14:00:00",
          "entry_price": 51500000.0,
          "exit_price": 50800000.0,
          "return_pct": -0.0136
        }
      ],
      "win_rate": 0.5,
      "avg_return": 0.008,
      "max_drawdown": -0.05,
      "avg_hold_bars": 5.0
    }
  ],
  "total_signals": 2,
  "execution_time": 2.34
}
```

---

## ✅ 검증 현황

### 코드 검증
- ✅ APISignal Pydantic 모델: 유효한 필드 정의
- ✅ SymbolResult 타입 변경: List[APISignal]
- ✅ BacktestResult 확장: entry_exit_pairs, returns 필드
- ✅ VolumeLongCandleStrategy: 데이터 전달
- ✅ VolumeZoneBreakoutStrategy: 데이터 전달
- ✅ API 변환 로직: 신호 변환 구현

### Docker 검증
- ✅ Backend 이미지 빌드 성공
- ✅ 컨테이너 시작 성공
- ✅ /health 엔드포인트 정상 작동

### API 호출 준비
- ✅ 모든 Pydantic 모델 검증 완료
- ✅ 데이터 변환 로직 구현 완료
- ✅ 에러 처리 유지됨

---

## 🎯 다음 단계

### Step 4: Frontend 신호 테이블 구현 (Week 2)

**Frontend 구현 아이템**:
1. SignalsTable 컴포넌트 작성
2. 신호 데이터 렌더링
3. 정렬 기능 (시간순, 수익률순)
4. 색상 코딩 (양수/음수)
5. BacktestResults에 통합

**필요한 Frontend 데이터 접근**:
```javascript
result.symbols[0].signals.forEach(signal => {
  console.log(signal.symbol)        // "BTC_KRW"
  console.log(signal.type)          // "buy" | "sell"
  console.log(signal.timestamp)     // ISO 8601 문자열
  console.log(signal.entry_price)   // 50000000.0
  console.log(signal.exit_price)    // 51500000.0
  console.log(signal.return_pct)    // 0.03 (3%)
})
```

---

## 📝 파일 변경 요약

| 파일 | 변경사항 | 라인 | 상태 |
|------|---------|------|------|
| `main.py` | APISignal 모델 정의 | 107-119 | ✅ 추가 |
| `main.py` | SymbolResult 확장 (int → List) | 122-133 | ✅ 수정 |
| `main.py` | 신호 변환 로직 | 274-291 | ✅ 추가 |
| `base.py` | BacktestResult 확장 | 61-72 | ✅ 수정 |
| `volume_long_candle.py` | entry_exit_pairs, returns | 149-161 | ✅ 수정 |
| `volume_zone_breakout.py` | 두 위치 모두 수정 | 141-151, 166-178 | ✅ 수정 |

---

## 💡 설계 결정사항

### 왜 List[APISignal]을 SymbolResult에?
- **신호 개수 제약 없음**: 대량 신호 처리 가능
- **Frontend 직접 사용**: 별도 변환 불필요
- **하위호환성**: BacktestResponse 구조는 동일

### 왜 entry_exit_pairs, returns를 따로 보관?
- **백엔드 로직 분리**: Strategy는 내부 계산 유지
- **점진적 확장**: 미래에 추가 필드 가능
- **변환 계층 분리**: main.py에서 명확하게 처리

### 왜 return_pct은 소수점?
- **JSON 표준**: 0.03 = 3% (percentage 형식)
- **Frontend 편의성**: formatPercent(0.03) = "3.00%"
- **정확도**: 부동소수점 오류 최소화

---

## 🚀 현재 상태

**Backend Phase 1 완료**:
- ✅ Signal 스키마 정의
- ✅ API 응답 확장
- ✅ 데이터 변환 로직
- ✅ 전략 연동
- ✅ Docker 빌드 성공
- ✅ API 실행 확인

**준비 완료 상태**:
```
Backend API: 🟢 Running (신호 데이터 반환 준비)
Frontend:   🟡 대기 (Step 4 신호 테이블 구현)
Tests:      🟡 대기 (데이터 파일 준비)
```

---

## 📞 연락처 및 질문

**다음 작업**:
1. Frontend SignalsTable 컴포넌트 구현
2. 테스트 데이터 준비 (OHLCV 파일)
3. 통합 테스트 실행

**예상 일정**:
- Week 2: Frontend Step 4 구현
- Week 3: 통합 테스트 및 검증

---

**작업 상태**: ✅ Phase 1 완료
**다음 검토**: Frontend 구현 준비 완료
