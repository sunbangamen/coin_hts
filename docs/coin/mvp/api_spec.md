# Coin Backtesting API 명세서

## 개요

Coin Backtesting API는 거래 전략을 과거 데이터에 대해 실행하고 성과를 분석할 수 있는 RESTful API입니다.

## 베이스 URL

```
http://localhost:8000
```

## 인증

현재 버전에서는 인증이 필요하지 않습니다.

## 엔드포인트 목록

### 1. GET / (루트)

API 서버의 기본 정보와 사용 가능한 엔드포인트 목록을 반환합니다.

**요청**:
```
GET /
```

**응답 (200 OK)**:
```json
{
  "message": "Coin Backtesting API",
  "version": "1.0.0",
  "endpoints": {
    "POST /api/backtests/run": "Run backtest",
    "GET /api/backtests/{run_id}": "Get backtest result",
    "GET /api/strategies": "List supported strategies",
    "GET /health": "Health check"
  }
}
```

### 2. GET /health (헬스체크)

API 서버의 상태를 확인합니다.

**요청**:
```
GET /health
```

**응답 (200 OK)**:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-31T17:00:00.123456",
  "data_root": "/data",
  "results_dir": "/data/results"
}
```

### 3. GET /api/strategies (전략 목록)

현재 지원되는 백테스트 전략의 목록을 반환합니다.

**요청**:
```
GET /api/strategies
```

**응답 (200 OK)**:
```json
{
  "strategies": [
    "volume_long_candle",
    "volume_zone_breakout"
  ],
  "count": 2
}
```

**전략 설명**:

#### volume_long_candle (거래량 급증 + 장대양봉)

거래량이 평균을 크게 상회하면서 동시에 강한 상승 장봉이 나타나는 패턴을 감지합니다.

지원 파라미터:
- `vol_ma_window` (int, 기본값: 20): 거래량 이동평균 계산 윈도우
- `vol_multiplier` (float, 기본값: 1.5): 거래량 급증 배수 기준
- `body_pct` (float, 기본값: 0.02): 캔들 몸통 비율 (2%)
- `hold_period_bars` (int, 기본값: 1): 신호 후 보유 바 수

#### volume_zone_breakout (매물대 돌파)

최근 구간의 거래량 프로파일을 분석하여 주요 매물대를 파악하고, 상위 매물대를 돌파하는 신호를 감지합니다.

지원 파라미터:
- `volume_window` (int, 기본값: 60): 매물대 형성 윈도우
- `top_percentile` (float, 기본값: 0.2): 상위 백분위 (상위 20%)
- `breakout_buffer` (float, 기본값: 0.01): 돌파 버퍼 비율 (1%)
- `hold_period_bars` (int, 기본값: 1): 신호 후 보유 바 수
- `num_bins` (int, 기본값: 20): 가격 구간 수
- `include_wicks` (bool, 기본값: True): 고가/저가를 가격 범위에 포함할지 여부

### 4. POST /api/backtests/run (백테스트 실행)

지정된 전략으로 백테스트를 실행하고 결과를 저장합니다.

**요청 형식**:
```
POST /api/backtests/run
Content-Type: application/json
```

**요청 바디**:
```json
{
  "strategy": "volume_long_candle",
  "params": {
    "vol_ma_window": 20,
    "vol_multiplier": 1.5,
    "body_pct": 0.02,
    "hold_period_bars": 1
  },
  "symbols": ["BTC_KRW", "ETH_KRW"],
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "timeframe": "1d"
}
```

**요청 파라미터 설명**:

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| strategy | string | ✓ | 전략 이름 |
| params | object | | 전략 파라미터 (기본값: {}) |
| symbols | array | ✓ | 심볼 목록 (최소 1개 필요) |
| start_date | string | ✓ | 시작 날짜 (YYYY-MM-DD 형식, KST 기준) |
| end_date | string | ✓ | 종료 날짜 (YYYY-MM-DD 형식, KST 기준) |
| timeframe | string | | 타임프레임 (기본값: "1d") |

**응답 (200 OK)**:
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "strategy": "volume_long_candle",
  "params": {
    "vol_ma_window": 20,
    "vol_multiplier": 1.5,
    "body_pct": 0.02,
    "hold_period_bars": 1
  },
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "timeframe": "1d",
  "symbols": [
    {
      "symbol": "BTC_KRW",
      "signals": 42,
      "win_rate": 0.59,
      "avg_return": 0.65,
      "max_drawdown": 3.1,
      "avg_hold_bars": 1.0
    },
    {
      "symbol": "ETH_KRW",
      "signals": 35,
      "win_rate": 0.54,
      "avg_return": 0.48,
      "max_drawdown": 2.8,
      "avg_hold_bars": 1.0
    }
  ],
  "total_signals": 77,
  "execution_time": 2.34
}
```

**응답 필드 설명**:

| 필드 | 타입 | 설명 |
|------|------|------|
| run_id | string | 백테스트 실행 고유 ID (UUID v4) |
| strategy | string | 실행된 전략 이름 |
| params | object | 사용된 전략 파라미터 |
| start_date | string | 백테스트 시작 날짜 |
| end_date | string | 백테스트 종료 날짜 |
| timeframe | string | 사용된 타임프레임 |
| symbols | array | 심볼별 백테스트 결과 |
| symbols[].symbol | string | 심볼 이름 |
| symbols[].signals | int | 생성된 신호 개수 |
| symbols[].win_rate | float | 승률 (0.0 ~ 1.0) |
| symbols[].avg_return | float | 평균 수익률 (%) |
| symbols[].max_drawdown | float | 최대 낙폭 (%) |
| symbols[].avg_hold_bars | float | 평균 보유 바 수 |
| total_signals | int | 모든 심볼의 총 신호 개수 |
| execution_time | float | 실행 시간 (초) |

**에러 응답**:

**400 Bad Request** (잘못된 파라미터):
```json
{
  "detail": "Invalid date format: 2024/01/01. Expected YYYY-MM-DD"
}
```

**422 Unprocessable Entity** (유효성 검사 실패):
```json
{
  "detail": [
    {
      "loc": ["body", "symbols"],
      "msg": "ensure this value has at least 1 items",
      "type": "value_error.list.min_items"
    }
  ]
}
```

**500 Internal Server Error** (서버 오류):
```json
{
  "detail": "Strategy execution failed for BTC_KRW: [error message]"
}
```

### 5. GET /api/backtests/{run_id} (결과 조회)

저장된 백테스트 결과를 조회합니다.

**요청**:
```
GET /api/backtests/{run_id}
```

**경로 파라미터**:

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| run_id | string | 백테스트 실행 ID |

**응답 (200 OK)**:

POST /api/backtests/run의 응답과 동일한 형식입니다.

**에러 응답**:

**404 Not Found** (결과를 찾을 수 없음):
```json
{
  "detail": "Backtest result not found: invalid-run-id"
}
```

## 사용 예제

### curl을 사용한 예제

#### 1. 헬스체크
```bash
curl http://localhost:8000/health
```

#### 2. 전략 목록 조회
```bash
curl http://localhost:8000/api/strategies
```

#### 3. 백테스트 실행
```bash
curl -X POST http://localhost:8000/api/backtests/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "volume_long_candle",
    "params": {
      "vol_ma_window": 20,
      "vol_multiplier": 1.5,
      "body_pct": 0.02
    },
    "symbols": ["BTC_KRW"],
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "timeframe": "1d"
  }'
```

응답 예시:
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  ...
}
```

#### 4. 결과 조회
```bash
curl http://localhost:8000/api/backtests/550e8400-e29b-41d4-a716-446655440000
```

### Python을 사용한 예제

```python
import requests
import json

# API 베이스 URL
API_URL = "http://localhost:8000"

# 백테스트 실행
payload = {
    "strategy": "volume_zone_breakout",
    "params": {
        "volume_window": 60,
        "top_percentile": 0.2,
        "breakout_buffer": 0.01
    },
    "symbols": ["BTC_KRW"],
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
}

response = requests.post(f"{API_URL}/api/backtests/run", json=payload)

if response.status_code == 200:
    result = response.json()
    run_id = result["run_id"]
    print(f"Backtest run_id: {run_id}")
    print(f"Total signals: {result['total_signals']}")

    # 결과 조회
    result = requests.get(f"{API_URL}/api/backtests/{run_id}")
    print(json.dumps(result.json(), indent=2, ensure_ascii=False))
else:
    print(f"Error: {response.status_code}")
    print(response.json())
```

## 데이터 저장 위치

백테스트 결과는 다음 경로에 JSON 파일로 저장됩니다:

```
DATA_ROOT/results/{run_id}.json
```

예시:
```
/data/results/550e8400-e29b-41d4-a716-446655440000.json
```

## 오류 처리

API는 다음의 HTTP 상태 코드를 사용합니다:

| 상태 코드 | 설명 |
|----------|------|
| 200 | 성공 |
| 400 | 나쁜 요청 (잘못된 파라미터) |
| 404 | 찾을 수 없음 (결과 파일이 없음) |
| 422 | 처리할 수 없는 엔티티 (유효성 검사 실패) |
| 500 | 내부 서버 오류 |

## 제한사항 및 주의사항

1. **타임아웃**: 대량의 심볼이나 긴 기간에 대한 백테스트는 시간이 걸릴 수 있습니다. 현재 버전에서는 동기 처리를 사용합니다.

2. **동시 요청**: 동시에 많은 백테스트 요청을 보내지 않는 것이 좋습니다.

3. **데이터 보존**: 결과 파일은 수동으로 삭제하지 않으면 영구적으로 저장됩니다.

4. **파일 시스템**: `DATA_ROOT` 환경변수가 마운트된 디렉토리를 가리켜야 합니다.

## 로깅

API는 모든 요청과 에러를 로깅합니다. 로그 메시지는 다음을 포함합니다:

- 백테스트 시작/종료
- 심볼별 데이터 로드 시간
- 전략 실행 시간
- 결과 저장 경로

## 버전 정보

| 항목 | 값 |
|------|-----|
| API 버전 | 1.0.0 |
| Python 버전 | 3.11+ |
| FastAPI 버전 | 0.104.0+ |
| Uvicorn 버전 | 0.24.0+ |

## 변경 기록

### v1.0.0 (2025-10-31)

- 초기 릴리스
- 2개 전략 지원 (volume_long_candle, volume_zone_breakout)
- POST /api/backtests/run 엔드포인트
- GET /api/backtests/{run_id} 엔드포인트
- GET /api/strategies 엔드포인트
- GET /health 헬스체크 엔드포인트
