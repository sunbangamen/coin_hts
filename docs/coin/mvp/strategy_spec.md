# 백테스트 전략 명세 (Strategy Specification)

## 개요

Phase 1에서 구현한 두 가지 백테스트 전략의 상세 알고리즘, 파라미터, 성과 지표 계산 방식을 정의합니다.

---

## 1. 거래량 급증 + 장대양봉 전략 (Volume Long Candle Strategy)

### 1.1 개요

거래량이 평균을 크게 상회하면서 동시에 강한 상승 장봉이 나타나는 패턴을 감지하는 전략입니다.

**핵심 아이디어**:
- 거래량 급증 → 기관 투자자의 관심 증가 신호
- 장대양봉 → 강한 상승 의도 표현
- 두 조건이 동시에 충족 → 고신뢰도 매수 신호

### 1.2 알고리즘

#### 1.2.1 거래량 조건

```
vol_ma = volume의 이동평균 (window: vol_ma_window)
vol_surge = volume >= vol_ma * vol_multiplier
```

**해석**:
- 현재 봉의 거래량이 최근 평균 거래량의 `vol_multiplier`배 이상일 때 거래량 급증 조건 만족
- 기본값: `vol_ma_window=20`, `vol_multiplier=1.5`

**예시**:
```
최근 20봉 평균 거래량: 1000
현재 봉 거래량: 1600
1600 >= 1000 * 1.5 (1500)? → YES (거래량 급증)
```

#### 1.2.2 장대양봉 조건

```
body_pct_actual = (close - open) / open
upper_wick = (high - close) / open
lower_wick = (open - low) / open

long_candle = (
    body_pct_actual >= body_pct AND
    upper_wick < body_pct * 2 AND
    lower_wick < body_pct * 2 AND
    close > open
)
```

**각 조건 설명**:

1. **몸통 크기** (`body_pct_actual >= body_pct`)
   - 캔들의 몸통(close - open)이 시가 대비 `body_pct` 이상 상승해야 함
   - 기본값: `body_pct=0.02` (2% 상승)

2. **위 꼬리** (`upper_wick < body_pct * 2`)
   - 위 꼬리가 작아야 함 (약한 저항을 의미)
   - 위 꼬리 비율 < 몸통 비율의 2배

3. **아래 꼬리** (`lower_wick < body_pct * 2`)
   - 아래 꼬리도 작아야 함 (약한 하강세 의미)
   - 아래 꼬리 비율 < 몸통 비율의 2배

4. **상승 캔들** (`close > open`)
   - 종가가 시가보다 높아야 함

**예시**:
```
시가: 100, 종가: 102.5, 고가: 102.8, 저가: 99.8
body_pct = (102.5 - 100) / 100 = 0.025 (2.5%) ✓ (0.02 이상)
upper_wick = (102.8 - 102.5) / 100 = 0.003 (0.3%) ✓ (0.04 미만)
lower_wick = (100 - 99.8) / 100 = 0.002 (0.2%) ✓ (0.04 미만)
close > open? 102.5 > 100? ✓
→ long_candle = TRUE
```

#### 1.2.3 신호 생성

```
signal = vol_surge AND long_candle
```

거래량 급증 AND 장대양봉 조건이 모두 만족될 때 BUY 신호 생성

### 1.3 파라미터

| 파라미터 | 기본값 | 범위 | 설명 |
|---------|-------|------|------|
| `vol_ma_window` | 20 | 1 ~ 500 | 거래량 이동평균 윈도우 (바 수) |
| `vol_multiplier` | 1.5 | 1.0 ~ 10.0 | 거래량 급증 배수 |
| `body_pct` | 0.02 | 0.01 ~ 0.10 | 캔들 몸통 비율 (2%) |
| `hold_period_bars` | 1 | 1 ~ 100 | 신호 후 보유 바 수 |

### 1.4 수익률 계산

```
진입가 = 신호 발생 시점의 close
청산가 = 신호 발생 후 hold_period_bars번째 캔들의 close
수익률 = (청산가 - 진입가) / 진입가 * 100 (%)
```

**예시**:
```
신호 발생 시점의 close: 102.5
1봉 보유 후 close: 104.0
수익률 = (104.0 - 102.5) / 102.5 * 100 = 1.46%
```

### 1.5 성과 지표

| 지표 | 계산식 | 설명 |
|-----|--------|------|
| **샘플 수** | `len(signals)` | 생성된 신호 개수 |
| **승률** | `수익 신호 / 전체 신호` | 양의 수익률을 낸 신호 비율 |
| **평균 수익률** | `sum(수익률) / 샘플수` | 모든 거래의 평균 수익률 (%) |
| **최대 낙폭** | `min(누적수익곡선 - 누적최고점)` | 누적 수익 기준 최대 하강 (%) |
| **평균 보유 바** | `hold_period_bars` | 항상 고정 |

---

## 2. 매물대 돌파 전략 (Volume Zone Breakout Strategy)

### 2.1 개요

가격대별 거래량을 분석하여 주요 매물대를 파악하고, 저항선 돌파 시 신호를 생성하는 전략입니다.

**핵심 아이디어**:
- 매물대 = 많은 거래가 일어난 가격대 (저항선/지지선 역할)
- 저항선 돌파 = 상승 추세 강화 신호
- Volume Profile 분석 → 객관적 저항선 도출

### 2.2 알고리즘

#### 2.2.1 매물대(Volume Profile) 생성

1. **가격 구간 분할** (Binning)
   ```
   price_min = 최근 volume_window 내 최저가
   price_max = 최근 volume_window 내 최고가
   bin_size = (price_max - price_min) / num_bins
   ```

2. **각 Bin에 거래량 할당**
   ```
   각 캔들마다:
     - 캔들이 차지하는 가격 범위 확인
     - 캔들과 겹치는 bin들에 거래량 비례 배분
   ```

   **배분 방식** (고가/저가 포함 시):
   ```
   candle_height = high - low
   각 bin에 대해:
     overlap = max(0, min(high, bin_end) - max(low, bin_start))
     할당거래량 = volume * (overlap / candle_height)
   ```

3. **상위 매물대 식별**
   ```
   상위 N% 매물대 = 높은 가격부터 누적하여 total_volume * top_percentile%에 도달하는 bin
   ```

**예시**:
```
최근 60봉:
- 최저가: 95, 최고가: 105, num_bins: 20
- bin_size = (105 - 95) / 20 = 0.5
- bin 범위: [95-95.5], [95.5-96], ..., [104.5-105]

거래량 분석:
- 100-101 구간에 많은 거래 (저항선)
- 상위 20% 매물대: 100.5 가격대

저항선 = 100.5
```

#### 2.2.2 돌파 조건

```
breakout_level = resistance_price * (1 + breakout_buffer)
signal = (high >= breakout_level)
```

**해석**:
- 저항선을 `breakout_buffer` 비율만큼 상회할 때 돌파 신호 생성
- 기본값: `breakout_buffer=0.01` (저항선 상방 1%)

**예시**:
```
저항선: 100.5
breakout_buffer: 0.01 (1%)
breakout_level = 100.5 * 1.01 = 101.505

현재 캔들 고가: 101.6
101.6 >= 101.505? → YES (돌파)
```

### 2.3 파라미터

| 파라미터 | 기본값 | 범위 | 설명 |
|---------|-------|------|------|
| `volume_window` | 60 | 10 ~ 500 | 매물대 형성 윈도우 (바 수) |
| `top_percentile` | 0.2 | 0.05 ~ 0.50 | 상위 백분위 (5% ~ 50%) |
| `breakout_buffer` | 0.01 | 0.0 ~ 0.05 | 돌파 버퍼 비율 (0% ~ 5%) |
| `hold_period_bars` | 1 | 1 ~ 100 | 신호 후 보유 바 수 |
| `num_bins` | 20 | 5 ~ 100 | 가격 구간 수 |
| `include_wicks` | True | - | 고가/저가를 범위에 포함할지 여부 |

### 2.4 수익률 계산

동일하게 다음 공식 사용:
```
진입가 = 신호 발생 시점의 close
청산가 = 신호 발생 후 hold_period_bars번째 캔들의 close
수익률 = (청산가 - 진입가) / 진입가 * 100 (%)
```

### 2.5 성과 지표

| 지표 | 계산식 | 설명 |
|-----|--------|------|
| **샘플 수** | `len(signals)` | 생성된 신호 개수 |
| **승률** | `수익 신호 / 전체 신호` | 양의 수익률을 낸 신호 비율 |
| **평균 수익률** | `sum(수익률) / 샘플수` | 모든 거래의 평균 수익률 (%) |
| **최대 낙폭** | `min(누적수익곡선 - 누적최고점)` | 누적 수익 기준 최대 하강 (%) |
| **평균 보유 바** | `hold_period_bars` | 항상 고정 |

---

## 3. 성과 지표 상세 계산

### 3.1 승률 (Win Rate)

```
win_rate = (수익 거래 수) / (전체 거래 수)
범위: 0.0 ~ 1.0 (0% ~ 100%)

수익 거래 = 수익률 > 0인 거래
```

**해석**:
- 0.6 (60%): 10개 거래 중 6개가 수익
- 0.5 (50%): 동전 던지기 수준 (무의미)
- 1.0 (100%): 모든 거래가 수익 (이상적이지만 현실적이기 어려움)

### 3.2 평균 수익률 (Average Return)

```
avg_return = sum(모든 거래의 수익률) / 거래 수 (%)

예시: 거래들이 [1.5%, -0.8%, 2.3%, -1.0%, 0.9%]라면
avg_return = (1.5 - 0.8 + 2.3 - 1.0 + 0.9) / 5 = 0.38%
```

**해석**:
- 양수: 평균적으로 수익 거래
- 음수: 평균적으로 손실 거래
- 절댓값이 클수록 전략의 강도가 높음

### 3.3 최대 낙폭 (Maximum Drawdown, MDD)

```
누적 수익 = [return_1, return_1+return_2, ..., sum(returns)]
누적 최고점 = max(누적 수익 이력)

각 시점에 대해:
  현재 낙폭 = 현재 누적 수익 - 누적 최고점

MDD = |min(모든 낙폭)| (절댓값으로 양수 표현)
```

**예시**:
```
수익률들: [2%, 3%, -5%, 1%, 2%]
누적 수익: [2%, 5%, 0%, 1%, 3%]
누적 최고점: [2%, 5%, 5%, 5%, 5%]
낙폭: [0%, 0%, -5%, -4%, -2%]

MDD = 5% (최악의 하강, 양수로 표현)
```

**해석**:
- 5%: 최고 수익에서 5% 하강 경험
- 0%: 항상 상승 (드문 경우)
- 더 큰 값: 더 큰 손실 경험 (위험도 높음)

---

## 4. 신호 신뢰도 (Confidence)

두 전략 모두 신호마다 `confidence` 값을 반환합니다 (0.0 ~ 1.0).

### 4.1 Volume Long Candle Confidence

```
confidence = min(vol_ratio / vol_multiplier, 1.0)

vol_ratio = 현재 거래량 / 이동평균 거래량

해석:
- vol_ratio = 2.0, vol_multiplier = 1.5
- confidence = min(2.0 / 1.5, 1.0) = 1.0 (최고 신뢰도)

- vol_ratio = 1.5, vol_multiplier = 1.5
- confidence = min(1.5 / 1.5, 1.0) = 1.0

- vol_ratio = 1.6, vol_multiplier = 1.5
- confidence = min(1.6 / 1.5, 1.0) ≈ 0.93
```

### 4.2 Volume Zone Breakout Confidence

```
confidence = min(0.5 + breakout_strength, 1.0)

breakout_strength = (현재 고가 - breakout_level) / breakout_level

해석:
- 저항선을 많이 상회할수록 신뢰도 증가
- 최소 0.5 (저항선 정확히 돌파)
- 최대 1.0 (충분히 강한 돌파)
```

---

## 5. 파라미터 최적화 가이드

### 5.1 Volume Long Candle 파라미터 조정

| 파라미터 | 값 증가 시 | 예상 효과 |
|---------|----------|---------|
| `vol_ma_window` | 20→50 | 더 느슨한 거래량 기준 (신호 증가) |
| `vol_multiplier` | 1.5→2.0 | 더 엄격한 거래량 기준 (신호 감소, 품질 향상) |
| `body_pct` | 0.02→0.05 | 더 강한 캔들 기준 (신호 감소, 품질 향상) |
| `hold_period_bars` | 1→5 | 더 긴 보유 기간 (수익률 증가 가능) |

### 5.2 Volume Zone Breakout 파라미터 조정

| 파라미터 | 값 증가 시 | 예상 효과 |
|---------|----------|---------|
| `volume_window` | 60→120 | 더 오래된 매물대 포함 (안정성 향상) |
| `top_percentile` | 0.2→0.3 | 더 넓은 매물대 기준 (신호 증가) |
| `breakout_buffer` | 0.01→0.03 | 더 높은 돌파 기준 (신호 감소, 품질 향상) |
| `num_bins` | 20→50 | 더 세밀한 매물대 분석 (정확성 향상) |

---

## 6. 사용 예시

### 6.1 Python 코드 예시

```python
import pandas as pd
from backend.app.data_loader import load_ohlcv_data
from backend.app.strategies.volume_long_candle import VolumeLongCandleStrategy
from backend.app.strategies.volume_zone_breakout import VolumeZoneBreakoutStrategy

# 1. 데이터 로드
df = load_ohlcv_data(
    symbols=['BTC_KRW'],
    start_date='2024-01-01',
    end_date='2024-12-31',
    timeframe='1d'
)

# 2. 거래량 급증 + 장대양봉 전략 실행
strategy1 = VolumeLongCandleStrategy()
result1 = strategy1.run(df, {
    'vol_ma_window': 20,
    'vol_multiplier': 1.5,
    'body_pct': 0.02,
    'hold_period_bars': 1,
})

print(f"Volume Long Candle:")
print(f"  신호 수: {result1.samples}")
print(f"  승률: {result1.win_rate:.2%}")
print(f"  평균 수익률: {result1.avg_return:.2f}%")
print(f"  최대 낙폭: {result1.max_drawdown:.2f}%")

# 3. 매물대 돌파 전략 실행
strategy2 = VolumeZoneBreakoutStrategy()
result2 = strategy2.run(df, {
    'volume_window': 60,
    'top_percentile': 0.2,
    'breakout_buffer': 0.01,
    'hold_period_bars': 1,
    'num_bins': 20,
    'include_wicks': True,
})

print(f"\nVolume Zone Breakout:")
print(f"  신호 수: {result2.samples}")
print(f"  승률: {result2.win_rate:.2%}")
print(f"  평균 수익률: {result2.avg_return:.2f}%")
print(f"  최대 낙폭: {result2.max_drawdown:.2f}%")
```

---

## 7. 주의사항

### 7.1 백테스트 한계

- **수수료/슬리피지 미반영**: Phase 2에서 추가 예정
- **청산 로직 단순화**: N봉 후 자동 청산 (사용자 정의 불가)
- **과최적화 위험**: 파라미터 스윕 시 최소 샘플 수 확인 필수

### 7.2 파라미터 선택 기준

1. **보수적 선택** (적중률 우선)
   - vol_multiplier ↑, breakout_buffer ↑
   - 신호 감소, 품질 증가

2. **공격적 선택** (수익률 우선)
   - vol_ma_window ↓, top_percentile ↑
   - 신호 증가, 기회 증가

3. **균형 선택** (기본값 권장)
   - 대부분의 상황에서 안정적 성과

---

## 8. 추가 고려사항

### 8.1 타임프레임별 추천 파라미터

| 타임프레임 | vol_ma_window | volume_window | 설명 |
|-----------|--------------|--------------|------|
| 1분 (1M) | 60 | 300 | 짧은 주기, 잦은 신호 |
| 5분 (5M) | 50 | 200 | 중단기 기준 |
| 1시간 (1H) | 30 | 100 | 중기 기준 |
| 1일 (1D) | 20 | 60 | 장기 기준, 안정적 |

### 8.2 상관계수 분석 권장

여러 전략/코인 조합 시 상관계수 확인:
- 상관계수 > 0.7: 같은 신호 → 하나 선택
- 상관계수 < 0.3: 독립적 신호 → 포트폴리오 구성 가능

---

## 요약

| 전략 | 강점 | 약점 | 추천 상황 |
|-----|------|------|---------|
| **Volume Long Candle** | 명확한 패턴 감지 | 거짓 신호 가능성 | 변동성 큰 시장 |
| **Volume Zone Breakout** | 객관적 저항선 | 복잡한 계산 | 추세 형성 시장 |

---

마지막 업데이트: 2025-10-31
