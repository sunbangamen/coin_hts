# Phase 3-2-1: VolumeZoneBreakout 저항선 계산 최적화 계획

## 📋 목표

**현재:** 5.1652초 @ 1000 캔들
**목표:** 0.5초 @ 1000 캔들
**개선율:** **11.8배 개선 (O(n²) → O(n))**

---

## 1. 병목 지점 분석

### 1.1 주요 병목 (Lines 88-100)

```python
for i in range(volume_window, len(df)):          # O(n) 반복
    window_start = i - volume_window
    window_df = df.iloc[window_start:i]
    resistance_price = self._calculate_resistance(...)  # O(m*k) 호출
```

**문제:**
- 매 반복마다 전체 window를 다시 계산
- 200 캔들 × 20 window = 3,800회 저항선 계산
- 각 계산 시 O(m×k) 복잡도

### 1.2 2차 병목 (Lines 219-253)

```python
for idx, row in df.iterrows():              # O(n) - 각 캔들
    ...
    for bin_idx in range(num_bins):         # O(k) - 각 bin (20개)
        # overlap 계산 및 거래량 할당
        overlap_ratio = (overlap_end - overlap_start) / candle_height
        bin_volumes[bin_idx] += volume * overlap_ratio
```

**복잡도:** O(n × k) = O(200 × 20) = 4,000개 연산
**문제점:**
- `iterrows()`: pandas의 느린 순회 방식
- 중첩 루프: 모든 bin을 확인
- 불필요한 overlap 계산

---

## 2. 최적화 전략

### 전략 A: Bin 할당 벡터화 (필수)

**목표:** O(n × k) → O(n + k)

**핵심 아이디어:**
1. `np.searchsorted()`로 각 캔들이 overlap되는 bin 범위를 빠르게 찾기
2. 해당 범위 내의 bin들만 계산
3. numpy 배열 연산으로 batch 처리

```python
# 현재 (O(n*k)):
for bin_idx in range(num_bins):  # 모든 bin 확인
    overlap_ratio = ...
    bin_volumes[bin_idx] += ...

# 최적화 (O(k) 평균):
start_bin = np.searchsorted(bins, candle_low, side='right') - 1
end_bin = np.searchsorted(bins, candle_high, side='left')
# 실제 overlap되는 bin들만 반복 (평균 2-3개)
for bin_idx in range(start_bin, end_bin):
    ...
```

**예상 개선:**
- 평균 bin 수를 1/10로 감소
- 5배 이상 속도 향상

### 전략 B: 증분 윈도우 계산 (최적화)

**목표:** 슬라이딩 윈도우에서 이전 결과 재사용

**핵심 아이디어:**
1. i-1의 window_df에서 계산된 bin_volumes를 저장
2. i의 경우, 나가는 캔들(i-window-1)의 기여도를 빼기
3. 들어오는 캔들(i-1)의 기여도만 추가

```python
# 현재 (O(n) 반복):
for i in range(volume_window, len(df)):
    window_df = df.iloc[i-window:i]  # 매번 새로 생성
    bin_volumes = calculate_volumes(window_df)  # 매번 재계산

# 최적화 (증분 계산):
bin_volumes = calculate_volumes(df.iloc[0:volume_window])  # 초기 계산

for i in range(volume_window, len(df)):
    # 나가는 캔들 제거
    if i > volume_window:
        remove_candle_from_bins(bin_volumes, df.iloc[i-window-1])

    # 들어오는 캔들 추가
    add_candle_to_bins(bin_volumes, df.iloc[i-1])

    resistance = get_resistance_from_bins(bin_volumes)
```

**예상 개선:**
- 3,800회 호출 → 200회 호출
- 19배 속도 향상

### 전략 C: 데이터 접근 최적화 (추가)

**목표:** pandas의 느린 순회를 numpy 배열로 변경

```python
# 현재 (느린):
for idx, row in df.iterrows():
    open_price = row['open']
    volume = row['volume']

# 최적화 (빠른):
open_prices = df['open'].values      # numpy 배열
volumes = df['volume'].values        # numpy 배열
for i in range(len(open_prices)):
    open_price = open_prices[i]
    volume = volumes[i]
```

**예상 개선:**
- 2배 속도 향상

---

## 3. 구현 계획

### Phase 1: Bin 할당 벡터화 (필수)

**파일:** `backend/app/strategies/volume_zone_breakout.py`

**변경 내용:**

#### 1.1 numpy searchsorted 활용

```python
# Lines 243-253 변경
# 현재 코드:
for bin_idx in range(num_bins):
    bin_start = bins[bin_idx]
    bin_end = bins[bin_idx + 1]
    overlap_start = max(candle_low, bin_start)
    overlap_end = min(candle_high, bin_end)
    if overlap_start < overlap_end:
        overlap_ratio = (overlap_end - overlap_start) / candle_height
        bin_volumes[bin_idx] += volume * overlap_ratio

# 최적화 코드:
start_bin = np.searchsorted(bins, candle_low, side='right') - 1
end_bin = np.searchsorted(bins, candle_high, side='left')
start_bin = max(0, start_bin)
end_bin = min(num_bins, end_bin)

for bin_idx in range(start_bin, end_bin):
    bin_start = bins[bin_idx]
    bin_end = bins[bin_idx + 1]
    overlap_start = max(candle_low, bin_start)
    overlap_end = min(candle_high, bin_end)
    overlap_ratio = (overlap_end - overlap_start) / candle_height
    bin_volumes[bin_idx] += volume * overlap_ratio
```

**코드 위치:**
- 수정 대상: `_calculate_resistance()` 메서드 (Lines 180-275)
- 주요 변경: Lines 219-253 (iterrows 루프 및 bin 할당 로직)

#### 1.2 numpy 배열 사용

```python
# Lines 219 이전에 추가
open_prices = df['open'].values
close_prices = df['close'].values
volumes = df['volume'].values

if include_wicks:
    low_prices = df['low'].values
    high_prices = df['high'].values
else:
    low_prices = np.minimum(open_prices, close_prices)
    high_prices = np.maximum(open_prices, close_prices)

candle_heights = high_prices - low_prices

# Lines 219 제거 및 아래로 변경
for i in range(len(df)):
    if candle_heights[i] == 0:
        # 높이 0 처리
        ...
    else:
        # searchsorted 사용하여 bin 범위 찾기
        ...
```

### Phase 2: 증분 윈도우 계산 (선택적)

**파일:** `backend/app/strategies/volume_zone_breakout.py`

**변경 내용:**

#### 2.1 헬퍼 함수 추가

```python
def _add_candle_to_bins(
    self,
    bin_volumes: np.ndarray,
    bins: np.ndarray,
    candle_low: float,
    candle_high: float,
    volume: float,
    candle_height: float,
) -> None:
    """캔들을 bin에 추가"""
    # (벡터화된 추가 로직)

def _remove_candle_from_bins(
    self,
    bin_volumes: np.ndarray,
    bins: np.ndarray,
    candle_low: float,
    candle_high: float,
    volume: float,
    candle_height: float,
) -> None:
    """캔들을 bin에서 제거"""
    # (벡터화된 제거 로직)
```

#### 2.2 메인 루프 변경

```python
# Lines 88-100 변경
# 초기 window 계산
window_start = 0
window_end = volume_window
window_df = df.iloc[window_start:window_end]
bin_volumes, bins = self._calculate_bin_volumes(
    window_df, num_bins, include_wicks
)

# 슬라이딩 윈도우
for i in range(volume_window, len(df)):
    # 이전 캔들 제거 (i >= volume_window + 1)
    if window_start > 0:
        prev_row = df.iloc[window_start - 1]
        self._remove_candle_from_bins(bin_volumes, bins, ...)

    # 새 캔들 추가
    new_row = df.iloc[i - 1]
    self._add_candle_to_bins(bin_volumes, bins, ...)

    # 저항선 계산 (bin_volumes 재사용)
    resistance_price = self._get_resistance_from_bins(
        bin_volumes, bins, top_percentile
    )

    window_start = i - volume_window + 1
```

---

## 4. 성능 예측

### 벡터화만 적용 (Phase 1)

```
현재 성능:
- _calculate_resistance() 호출: 190회
- 각 호출당 overhead: 0.0271초 (5.16 / 190)

벡터화 적용:
- searchsorted 사용: O(log k) per bin overlap
- bin 반복: 평균 2-3개 (20개 → 10% 감소)
- 예상 개선: 5배

예측 성능: 5.16 / 5 = 1.03초
```

### 증분 계산까지 적용 (Phase 1+2)

```
증분 계산 이점:
- 전체 호출: 190회 → 1회
- 각 윈도우마다 추가/제거만 수행: O(2-3 bins)
- 예상 개선: 190배 × (현재 복잡도)

그러나 초기 계산 비용 고려:
- 초기 window: O(volume_window × bins)
- 이후 반복: O(bins)
- 전체: O(volume_window × bins + (n - volume_window) × bins)

예측 성능: 5.16 / 20 = 0.26초 (25배 개선)
```

### 최종 예측 (보수적)

```
단계별 개선:
1. searchsorted 벡터화: 5배 → 1.03초
2. 증분 계산 추가: 5배 → 0.21초
3. 기타 최적화: 2배 → 0.1초

최종 목표: 0.5초 (기대: 0.1-0.2초 가능)
달성율: 95%+ 확률
```

---

## 5. 테스트 계획

### 5.1 성능 테스트

```python
# 기존 성능 테스트 재실행
docker-compose exec backend python scripts/test_performance_phase3.py

# 개별 함수 성능 테스트
import timeit

# 벡터화 전
time_before = timeit.timeit(
    lambda: strategy.run(df_100, params),
    number=10
)

# 벡터화 후
time_after = timeit.timeit(
    lambda: strategy_optimized.run(df_100, params),
    number=10
)

improvement = time_before / time_after
print(f"Improvement: {improvement:.1f}x")
```

### 5.2 정확도 테스트

```python
# 신호 생성 동일성 검증
result_before = strategy.run(df_test, params)
result_after = strategy_optimized.run(df_test, params)

# 신호 개수 비교
assert len(result_before.signals) == len(result_after.signals)

# 신호 시간 비교
for sig_before, sig_after in zip(result_before.signals, result_after.signals):
    assert sig_before.timestamp == sig_after.timestamp
    assert abs(sig_before.price - sig_after.price) < 0.01

# 메트릭 비교
assert abs(result_before.win_rate - result_after.win_rate) < 0.01
assert abs(result_before.avg_return - result_after.avg_return) < 0.1
```

### 5.3 회귀 테스트

```bash
# 전체 테스트 실행
docker-compose exec backend python -m pytest tests/ -v

# VolumeZoneBreakout 테스트만 실행
docker-compose exec backend python -m pytest tests/test_strategies.py::TestVolumeZoneBreakout -v
```

---

## 6. 구현 체크리스트

- [ ] 현재 코드 벤치마크 (기준선)
- [ ] Phase 1: searchsorted 벡터화 구현
- [ ] Phase 1: numpy 배열 접근 최적화
- [ ] Phase 1: 성능 테스트 및 검증
- [ ] Phase 1: 회귀 테스트 실행
- [ ] Phase 2: 증분 윈도우 계산 구현 (선택)
- [ ] Phase 2: 성능 테스트
- [ ] Phase 2: 최종 회귀 테스트
- [ ] 문서 업데이트 및 최적화 결과 정리
- [ ] Git commit

---

## 7. 예상 일정

| 작업 | 소요 시간 | 상태 |
|------|---------|------|
| Phase 1 구현 | 1-2시간 | 예정 |
| Phase 1 테스트 | 30분 | 예정 |
| Phase 2 구현 | 1시간 | 선택 |
| Phase 2 테스트 | 30분 | 선택 |
| 최종 검증 | 30분 | 예정 |
| **총 소요 시간** | **2-3시간** | |

---

## 8. 위험 요소 및 대응 방안

| 위험 | 확률 | 영향 | 대응 방안 |
|------|------|------|---------|
| 신호 개수 변경 | 낮음 | 높음 | 철저한 정확도 테스트 |
| 메트릭 오차 | 중간 | 중간 | 부동소수점 오차 범위 설정 (±0.01) |
| 성능 개선 미달 | 낮음 | 중간 | Phase 2 증분 계산 자동 실행 |
| 코드 복잡도 증가 | 중간 | 낮음 | 명확한 주석 및 docstring 추가 |

---

## 9. 참고 자료

- [NumPy searchsorted](https://numpy.org/doc/stable/reference/generated/numpy.searchsorted.html)
- [pandas vs numpy performance](https://realpython.com/numpy-array-programming/)
- [Sliding window optimization](https://stackoverflow.com/questions/6822725/rolling-or-sliding-window-iterator-in-python)

---

**작성일:** 2025-11-03
**상태:** 준비 완료 (Phase 1 구현 예정)

