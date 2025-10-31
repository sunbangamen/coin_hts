# Issue #2 해결 계획: 백테스트 전략 엔진 구현

## 1. 이슈 정보 요약

| 항목 | 내용 |
|-----|------|
| **제목** | [Phase 1] Task 2: 백테스트 전략 엔진 구현 |
| **URL** | https://github.com/sunbangamen/coin_hts/issues/2 |
| **상태** | OPEN |
| **생성일** | 2025-10-31 |
| **라벨** | Phase-1, backend, strategy, business-logic |
| **예상 소요 시간** | 6시간 |

### 핵심 요구사항
- `volume_long_candle` (거래량 급증 + 장대양봉) 전략 구현
- `volume_zone_breakout` (매물대 돌파) 전략 구현
- 각 전략별 신호 생성 로직 및 성과 지표 계산
- 확장 가능한 추상 클래스 설계

---

## 2. 문제 이해

### 현재 상태
- ✅ Task 1 (데이터 로더): 완료됨
- ❌ Task 2 (전략 엔진): 미작업

### 핵심 요구사항
1. **전략 정의 레이어**: 2개 전략의 시그널 생성 로직
2. **성과 지표 계산**: 승률, 평균수익률, 최대낙폭, 샘플 수
3. **백테스트 결과 모델**: `BacktestResult` 데이터 클래스
4. **테스트 및 문서화**: 유닛 테스트 + 알고리즘 명세

### 의존성
- ✅ Task 1 (데이터 로더): 이미 완료됨
- ✅ PDR 문서: 전략 정의 명세 (docs/pdr.md 참고)

### 불확실성 & 위험요소
1. **시그널 생성 로직 명세**: 정확한 수식 필요
2. **수익률 계산**: 수수료/슬리피지 반영 여부
3. **MDD 계산 방법**: 누적 수익 곡선 vs 개별 거래
4. **청산 로직**: 익절/손절 조건 정의

---

## 3. 해결 계획 수립

### 단계 1: 전략 구조 설계 및 추상 클래스 정의

**작업 내용**:
- `backend/app/strategies/` 디렉토리 생성
- `backend/app/strategies/__init__.py` 생성
- `backend/app/strategies/base.py` 작성
  - `Strategy` 추상 베이스 클래스
  - `Signal` 모델 (timestamp, side, price, confidence)
  - `BacktestResult` 데이터 클래스

**예상 산출물**:
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional
import pandas as pd

@dataclass
class Signal:
    timestamp: pd.Timestamp
    side: str  # 'BUY' or 'SELL'
    price: float
    confidence: float

@dataclass
class BacktestResult:
    signals: List[Signal]
    samples: int
    win_rate: float  # 0.0 ~ 1.0
    avg_return: float  # 평균 수익률 (%)
    max_drawdown: float  # 최대 낙폭 (%)
    avg_hold_bars: float  # 평균 보유 바 수
    avg_hold_duration: Optional[pd.Timedelta]  # 타임프레임이 명확할 때만 사용

class Strategy(ABC):
    @abstractmethod
    def run(self, df: pd.DataFrame, params: Dict) -> BacktestResult:
        pass
```

**확인 방법**:
- 추상 클래스 및 모델 정의 완료
- 타입 힌트 추가
- Docstring 작성

**의존성**: 없음

---

### 단계 2: `volume_long_candle` 전략 구현

**작업 내용**:
- 거래량 이동평균 계산 (`vol_ma_window`)
- 거래량 급증 조건: `volume >= vol_ma * vol_multiplier`
  - 장대양봉 판단
    - 몸통 크기: `(close - open) / open >= body_pct`  # 기준은 시가 대비 상승 비율로 측정
  - 위/아래 꼬리 비율
- 시그널 생성 (BUY 신호만)
- 수익률 계산 (N봉 후 close 대비)

**예상 산출물**:
```python
class VolumeLongCandleStrategy(Strategy):
    def run(self, df: pd.DataFrame, params: Dict) -> BacktestResult:
        """
        거래량 급증 + 장대양봉 전략

        params:
            - vol_ma_window: int (이동평균 윈도우, 기본값: 20)
            - vol_multiplier: float (거래량 배수, 기본값: 1.5)
            - body_pct: float (몸통 비율, 기본값: 0.02)
            - hold_period_bars: int (보유 바 수, 기본값: 1)
        """
```

**확인 방법**:
- 샘플 데이터로 시그널 생성 테스트
- 거래량 조건 검증
- 수익률 계산 정확성 확인

**의존성**: 단계 1 완료

---

### 단계 3: `volume_zone_breakout` 전략 구현

**작업 내용**:
- 최근 `volume_window` 구간에 대해 가격대 히스토그램 구성
  - 기본은 `num_bins`(예: 20)으로 균등 분할, 추후 데이터 분석으로 조정 가능
  - 각 bin별로 체결량 총합을 계산해 매물대(Volume Profile)를 생성
- 상위 `top_percentile`에 해당하는(bin별 누적 비중 기준) 매물대 상단을 저항선으로 간주
- 돌파 조건: `close > resistance_price * (1 + breakout_buffer)`
- 시그널 생성 (BUY 신호만)
- 신호 이후 `hold_period_bars` 만큼 동일 타임프레임 기준으로 보유

**예상 산출물**:
```python
class VolumeZoneBreakoutStrategy(Strategy):
    def run(self, df: pd.DataFrame, params: Dict) -> BacktestResult:
        """
        매물대 돌파 전략

        params:
            - volume_window: int (매물대 형성 윈도우, 기본값: 60)
            - top_percentile: float (상위 백분위, 기본값: 0.2)
            - breakout_buffer: float (돌파 버퍼, 기본값: 0.01)
            - hold_period_bars: int (보유 바 수, 기본값: 1)
        """
        추가 파라미터:
            - num_bins: int (가격 구간 수, 기본값: 20)
            - include_wicks: bool (고가/저가를 가격 범위에 포함할지 여부, 기본값: True)
        ```

**확인 방법**:
- 매물대 계산 검증
- 돌파 신호 생성 테스트
- 지속일수 확인

**의존성**: 단계 1 완료

---

### 단계 4: 성과 지표 계산 로직 구현

**작업 내용**:
- `backend/app/strategies/metrics.py` 공통 함수 추출
  - **승률 (win_rate)**: 수익 거래 수 / 전체 거래 수
  - **평균 수익률 (avg_return)**: 모든 거래의 평균 수익률 (%)
  - **최대 낙폭 (max_drawdown)**: 누적 수익 곡선의 최대 낙폭 (양수 %)
  - **평균 보유 바 수 (avg_hold_bars)**: `hold_period_bars` 기준 평균 보유 바 수
- 각 전략이 공통 함수를 호출하여 지표 계산

**예상 산출물**:
```python
# metrics.py
def calculate_metrics(returns: List[float], hold_period_bars: int) -> Dict[str, float]:
    """
    거래 수익률 배열로부터 성과 지표를 계산합니다.

    반환값:
    - win_rate (float): 0.0 ~ 1.0
    - avg_return (float): 평균 수익률 (%)
    - max_drawdown (float): 최대 낙폭 (양수 %)
    - avg_hold_bars (float): 보유 바 수
    """

def calculate_entry_exit_prices(signal_indices, df, hold_period_bars) -> List[Tuple]:
    """신호 인덱스로부터 진입/청산 가격 계산"""

def calculate_returns(entry_exit_pairs) -> List[float]:
    """진입/청산 가격 쌍으로부터 수익률 계산"""
```

**확인 방법**:
- 공통 함수를 이용한 지표 계산 검증
- 수익률 계산 정확성 확인
- 위치 기반 인덱싱 정상 작동 확인

**의존성**: 단계 2, 3 완료

---

### 단계 5: 유닛 테스트 작성

**작업 내용**:
- `tests/test_strategies.py` 작성
- 각 전략별 정상 케이스 테스트
- 예외 케이스 테스트 (빈 데이터, 잘못된 파라미터)
- 지표 계산 검증 테스트
- 최소 10개 이상의 테스트 케이스

**예상 산출물**:
| 테스트 클래스 | 개수 | 테스트 내용 |
|-----------|------|-----------|
| TestVolumeLongCandle | 5 | 신호 생성, 수익률, 예외처리 |
| TestVolumeZoneBreakout | 5 | 매물대 계산, 돌파, 예외처리 |
| TestMetricsCalculation | 6 | 승률, 평균수익률, MDD 계산 |
| TestSignalValidation | 4 | Signal/BacktestResult 데이터 검증 |

**확인 방법**:
```bash
pytest tests/test_strategies.py -v
```

**의존성**: 단계 2, 3, 4 완료

---

### 단계 6: 알고리즘 명세 문서 작성

**작업 내용**:
- `docs/coin/mvp/strategy_spec.md` 작성
  - 각 전략의 상세 알고리즘
  - 파라미터 설명
  - 예시 및 그래프
- `backend/app/strategies/base.py` 및 구현 코드에 상세 docstring 추가

**예상 산출물**:
- `docs/coin/mvp/strategy_spec.md` (200줄 이상)
- 모든 함수/클래스에 docstring 추가
- 타입 힌트 완성

**확인 방법**:
- 문서 가독성 검증
- 코드 주석 정리

**의존성**: 단계 2, 3, 4, 5 완료

---

## 4. 구현 순서 및 우선순위

### 권장 진행 순서
1. ✅ **단계 1** (1시간): 추상 클래스 설계
2. ✅ **단계 2** (1.5시간): `volume_long_candle` 구현
3. ✅ **단계 3** (1.5시간): `volume_zone_breakout` 구현
4. ✅ **단계 4** (0.5시간): 지표 계산 로직
5. ✅ **단계 5** (1시간): 유닛 테스트
6. ✅ **단계 6** (0.5시간): 문서화

**예상 총 소요 시간**: 6시간 ✅

---

## 5. 추가 고려 사항

### 기술적 결정사항
| 항목 | 결정 | 근거 |
|-----|------|------|
| **수익률 계산** | N봉 후 close 기준 | 단순하고 명확함 |
| **수수료/슬리피지** | 미반영 (Phase 2에서) | 초기 구현 단순화 |
| **MDD 계산** | 누적 수익 곡선 기준 | 일반적인 방식 |
| **청산 로직** | 매도 신호 없이 N봉 자동 청산 | 구현 단순화 |

### 검증 체크리스트
- [ ] 각 전략의 신호 생성 로직 정확성
- [ ] 지표 계산 결과 정확성
- [ ] 예외 처리 완벽성
- [ ] 테스트 커버리지 80% 이상
- [ ] 코드 스타일 일관성
- [ ] 문서화 완성도

---

## 6. 이슈 #2 Acceptance Criteria

### 필수 산출물
- [ ] `backend/app/strategies/` 디렉토리 생성
- [ ] `backend/app/strategies/base.py`: `Strategy` 추상 베이스 클래스 정의
- [ ] `backend/app/strategies/volume_long_candle.py`: 거래량 급증 + 장대양봉 전략 구현
- [ ] `backend/app/strategies/volume_zone_breakout.py`: 매물대 돌파 전략 구현
- [ ] 각 전략의 `run(df: pd.DataFrame, params: dict) -> BacktestResult` 메서드 구현
- [ ] `BacktestResult` 모델에 `win_rate`, `avg_return`, `max_drawdown`, `samples`, `signals` 포함
- [ ] 유닛 테스트로 샘플 데이터에 대한 시그널 생성 검증

### 검증 코드
```python
# 테스트 예시
strategy = VolumeLongCandleStrategy()
result = strategy.run(sample_df, {"vol_ma_window": 20, "vol_multiplier": 1.5, "body_pct": 0.02})
assert result.samples > 0
assert 0 <= result.win_rate <= 1
assert len(result.signals) == result.samples
```

---

## 7. 진행 승인 요청

위 계획대로 진행해도 될까요?

### 확인 사항:
1. **계획 단계**: 단계 1-6이 적절한가요?
2. **시그널 생성 로직**: 제시한 조건이 맞나요?
3. **수익률 계산**: "N봉 후 close 기준"이 맞나요?
4. **MDD 계산**: "누적 수익 곡선 기준"으로 진행할까요?
5. **우선순위**: 다른 순서나 병렬 처리를 원하세요?

---

**준비되면 "계속 진행해주세요" 또는 수정 사항을 알려주세요!**
