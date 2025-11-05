# Coin Trading Backend - OHLCV Data Loader

코인 백테스트 및 자동매매 플랫폼의 백엔드 데이터 로더 모듈입니다.

## 개요

로컬 parquet 파일 기반의 OHLCV(Open, High, Low, Close, Volume) 데이터 로딩 시스템을 제공합니다.

- **파일 구조**: `DATA_ROOT/{symbol}/{timeframe}/{year}.parquet`
- **타임존 처리**: KST 입력 → 내부 UTC 처리
- **도메인**: 코인 거래량 + 매물대 기반 백테스팅

---

## 주요 기능

### 1. OHLCV 데이터 로드
```python
from backend.app.data_loader import load_ohlcv_data

df = load_ohlcv_data(
    symbols=["BTC_KRW", "XRP_KRW"],
    start_date="2024-01-01",
    end_date="2024-12-31",
    timeframe="1d"
)
```

**반환 DataFrame 컬럼**:
- `timestamp`: UTC 기준 시간 (timezone-aware)
- `symbol`: 심볼명 (대문자, 예: `BTC_KRW`)
- `timeframe`: 타임프레임 (대문자, 예: `1D`, `1H`, `5M`)
- `open`, `high`, `low`, `close`: 가격 (float)
- `volume`: 거래량 (float)

### 2. 타임존 정규화
- **입력**: KST 기반 ISO8601 문자열 (예: `"2024-01-01"`, `"2024-01-01T14:30:00+09:00"`)
- **내부**: UTC로 변환하여 일관되게 처리
- **출력**: UTC timezone-aware timestamp

```python
# "2024-01-01 KST" = "2023-12-31 15:00:00 UTC"로 변환 및 반환
```

### 3. 예외 처리
| 상황 | 예외 | 상태 코드 |
|-----|------|--------|
| 파일이 없음 | HTTPException | 404 |
| 필수 컬럼 누락 | HTTPException | 400 |
| 입력 파라미터 오류 | HTTPException | 422 |

---

## 설치 및 환경 구성

### 1. 로컬 개발 환경

```bash
# 가상환경 생성
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. Docker 환경

```bash
# 이미지 빌드
docker-compose build

# 테스트 실행
docker-compose run --rm test

# 백엔드 실행
docker-compose up backend
```

---

## 데이터 구조

### 디렉토리 구조
```
DATA_ROOT/
├── BTC_KRW/
│   ├── 1D/
│   │   ├── 2022.parquet
│   │   ├── 2023.parquet
│   │   └── 2024.parquet
│   ├── 1H/
│   │   └── 2024.parquet
│   └── 5M/
│       └── 2024.parquet
├── XRP_KRW/
│   ├── 1D/
│   │   ├── 2023.parquet
│   │   └── 2024.parquet
│   └── ...
└── ...
```

### Parquet 파일 포맷

최소 필수 컬럼:
- `open`: float (시가)
- `high`: float (고가)
- `low`: float (저가)
- `close`: float (종가)
- `volume`: float (거래량)
- `timestamp`: datetime (날짜, timezone 선택사항)

**선택 컬럼**:
- `symbol`: str (심볼, 없으면 경로에서 주입)
- `timeframe`: str (타임프레임, 없으면 경로에서 주입)

---

## API 사용 예제

### 예제 1: 단일 심볼 로드
```python
from backend.app.data_loader import load_ohlcv_data

# BTC_KRW 2024년 데이터 로드
df = load_ohlcv_data(
    symbols=["BTC_KRW"],
    start_date="2024-01-01",
    end_date="2024-12-31",
    timeframe="1d"
)

print(df.head())
# Output:
#             timestamp      symbol timeframe  open  high  low  close  volume
# 0 2023-12-31 15:00:00+00:00  BTC_KRW        1D  40000  42000  39000  41500   1234.5
# 1 2024-01-02 15:00:00+00:00  BTC_KRW        1D  41500  43000  41000  42500   2345.6
# ...
```

### 예제 2: 다중 심볼 로드
```python
# 여러 심볼을 동시에 로드
df = load_ohlcv_data(
    symbols=["BTC_KRW", "XRP_KRW", "ETH_KRW"],
    start_date="2024-01-01",
    end_date="2024-03-31",
    timeframe="1h"
)

# 심볼별 데이터 필터링
btc_data = df[df['symbol'] == 'BTC_KRW']
xrp_data = df[df['symbol'] == 'XRP_KRW']
```

### 예제 3: 환경 변수 사용
```bash
# 쉘에서 DATA_ROOT 설정
export DATA_ROOT=/home/user/trading_data

# 또는 docker-compose.yml에서 자동으로 설정됨
# /data 볼륨으로 마운트되어 있음
```

---

## 테스트

### ⚡ 빠른 종합 테스트 실행 (권장)

```bash
./scripts/run_e2e_tests.sh --with-unit
```

**실행 내용:**
- ✅ Backend 유닛 테스트 (126/145 passing)
- ✅ E2E 통합 테스트 (8/8 scenarios passing)
- ✅ Docker 자동 실행 (컨테이너 관리 포함)

**예상 시간:** 약 3-4분

> 자세한 테스트 가이드는 [`TESTING_GUIDE.md`](./TESTING_GUIDE.md) 참고

### 로컬 유닛 테스트 실행

```bash
# 가상환경 활성화
source venv/bin/activate

# 전체 테스트
python -m pytest tests/ -v

# 특정 테스트 클래스만 실행
pytest tests/test_data_loader.py::TestLoadOhlcvData -v

# 테스트 결과 상세 출력
pytest tests/test_data_loader.py -vv --tb=long
```

### Docker 테스트 실행

```bash
# 기본 E2E 테스트만
docker-compose down --remove-orphans
./scripts/run_e2e_tests.sh

# E2E + 유닛 테스트
./scripts/run_e2e_tests.sh --with-unit

# E2E + 프론트엔드 테스트
./scripts/run_e2e_tests.sh --with-frontend

# 모든 테스트 (풀 모드)
./scripts/run_e2e_tests.sh --full
```

### 테스트 커버리지

**유닛 테스트 (로컬)**: 22개 케이스

| 테스트 그룹 | 개수 | 설명 |
|-----------|------|------|
| TestNormalizeTimezone | 4 | KST → UTC 타임존 변환 |
| TestExtractYearsFromRange | 3 | 날짜 범위에서 연도 추출 |
| TestValidateDataFrame | 4 | DataFrame 필수 컬럼 검증 |
| TestLoadOhlcvData | 11 | 전체 데이터 로딩 및 필터링 |

**E2E 테스트**: 8개 시나리오

| # | 시나리오 | 상태 |
|----|---------|------|
| 1 | Health Check | ✅ Pass |
| 2 | List Available Strategies | ✅ Pass |
| 3 | Start Simulation | ✅ Pass |
| 4 | Check Simulation Status | ✅ Pass |
| 5 | Verify Strategies Registered | ✅ Pass |
| 6 | Collect Market Data | ✅ Pass |
| 7 | Track Positions | ✅ Pass |
| 8 | Retrieve Trade History | ✅ Pass |

**커버리지**: 80% 이상 (유닛 테스트)

---

## 도메인 규칙

### 1. 타임존 처리
- **입력**: KST 기반 ISO8601 (예: `"2024-01-01"`, `"2024-01-01T14:30:00+09:00"`)
- **변환**: 자동으로 UTC로 변환
- **출력**: UTC timezone-aware `pd.Timestamp`

### 2. 심볼 표기
- **형식**: 대문자 + 언더바 (예: `BTC_KRW`, `ETH_USDT`)
- **주입**: 파일 경로 `{symbol}/{timeframe}/` 에서 추출
- **정규화**: 입력은 소문자도 허용하지만 내부에서 대문자로 변환

### 3. 타임프레임 표기
- **형식**: 대문자 단위 (예: `1S`, `1M`, `5M`, `1H`, `1D`)
- **주입**: 파일 경로 `/{timeframe}/` 에서 추출
- **정규화**: 입력은 소문자도 허용하지만 내부에서 대문자로 변환

---

## 환경 변수

| 변수명 | 기본값 | 설명 |
|-------|-------|------|
| `DATA_ROOT` | `./data` | parquet 파일 루트 디렉토리 |
| `TZ` | `Asia/Seoul` | 컨테이너 시스템 타임존 (참고용, 데이터는 UTC 처리) |
| `PYTHONUNBUFFERED` | `1` | 로그 실시간 출력 |

### Docker 환경
```bash
docker-compose up \
  -e DATA_ROOT=/data \
  -e TZ=Asia/Seoul \
  backend
```

---

## 파일 구조

```
/home/limeking/projects/worktree/coin-1/
├── backend/
│   └── app/
│       ├── __init__.py
│       └── data_loader.py          # OHLCV 로더 모듈
├── tests/
│   └── test_data_loader.py         # 유닛 테스트 (22개)
├── requirements.txt                # Python 의존성
├── Dockerfile                      # Docker 이미지 정의
├── docker-compose.yml              # Docker 다중 컨테이너 설정
├── README.md                       # 이 파일
├── e2e_test_results.log           # End-to-end 테스트 결과
├── docker_build_results.log        # Docker 빌드 로그
└── docker_test_results.log         # Docker 테스트 실행 결과
```

---

## 주요 함수 API

### `load_ohlcv_data()`

```python
def load_ohlcv_data(
    symbols: List[str],
    start_date: str,
    end_date: str,
    timeframe: str = "1d",
    data_root: Optional[str] = None
) -> pd.DataFrame
```

**파라미터**:
- `symbols` (List[str]): 조회할 심볼 목록 (예: `["BTC_KRW"]`)
- `start_date` (str): 시작 날짜 (ISO8601)
- `end_date` (str): 종료 날짜 (ISO8601)
- `timeframe` (str, 기본값: `"1d"`): 타임프레임
- `data_root` (Optional[str]): 데이터 루트 (기본값: 환경변수 `DATA_ROOT`)

**반환**:
- `pd.DataFrame`: 병합된 OHLCV 데이터 (timestamp 오름차순 정렬)

**예외**:
- `HTTPException(404)`: 조회 가능한 데이터 파일 없음
- `HTTPException(400)`: 필수 컬럼 누락 또는 스키마 오류
- `HTTPException(422)`: 입력 파라미터 오류

---

## Phase 3: 비동기 태스크 큐 (운영 안정성)

**Phase 3**에서는 장시간 실행되는 백테스트를 비동기로 처리하기 위한 인프라를 추가했습니다.

### 비동기 백테스트 실행

#### 1. 비동기 모드로 백테스트 실행
```bash
# 비동기 백테스트 요청
curl -X POST http://localhost:8000/api/backtests/run-async \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "volume_zone_breakout",
    "symbols": ["BTC_KRW", "ETH_KRW"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }'

# 응답 (202 Accepted)
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "queued",
  "created_at": "2025-11-04T10:30:45.123456Z"
}
```

#### 2. 작업 상태 조회 (폴링)
```bash
# 작업 상태 조회
curl http://localhost:8000/api/backtests/status/a1b2c3d4-e5f6-7890-abcd-ef1234567890

# 응답: 대기 중
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "queued",
  "progress": 0.0,
  "result": null,
  "error": null
}

# 응답: 실행 중
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "running",
  "progress": 0.45,
  "result": null,
  "error": null
}

# 응답: 완료됨
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "progress": 1.0,
  "result": { /* BacktestResponse */ },
  "error": null
}
```

### 비동기 인프라 구성

#### Redis 서비스
```bash
# Redis 상태 확인
redis-cli ping

# Redis 메모리 모니터링
redis-cli INFO memory
```

#### 워커 실행
```bash
# Docker 환경에서 워커 실행
docker-compose --profile worker up worker

# 로컬 환경에서 워커 실행
python -m rq worker -c backend.app.config --verbose
```

### 결과 파일 관리

비동기 백테스트 결과는 다음 구조로 저장됩니다:

```
${DATA_ROOT}/tasks/
├── <task_id_1>/
│   ├── manifest.json         # 작업 메타데이터
│   └── result.json           # 백테스트 결과
├── <task_id_2>/
│   ├── manifest.json
│   └── result.json
└── ...
```

#### manifest.json 예시
```json
{
  "task_id": "abc123-def456",
  "status": "completed",
  "strategy": "volume_zone_breakout",
  "metadata": {
    "started_at": "2025-11-04T10:30:45Z",
    "finished_at": "2025-11-04T10:35:20Z",
    "duration_ms": 275000,
    "environment": "production"
  },
  "summary": {
    "total_signals": 45,
    "symbols_processed": 2,
    "symbols_failed": 0
  },
  "error": {
    "occurred": false,
    "message": null
  }
}
```

### 결과 파일 정리

오래된 결과를 자동으로 정리합니다:

```bash
# TTL 기반 정리 (7일 이상 된 파일)
python scripts/cleanup_task_results.py

# 정리 시뮬레이션 (실제 삭제 없음)
python scripts/cleanup_task_results.py --dry-run

# 커스텀 TTL 설정 (30일)
python scripts/cleanup_task_results.py --ttl-days 30
```

### 환경 변수

```bash
# 데이터 루트 (기본값: /data)
DATA_ROOT=/data

# Redis 설정
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# 실행 환경
ENVIRONMENT=development

# 태스크 결과 보존 기간 (일)
TASK_RESULT_TTL_DAYS=7
```

---

## 버전 정보

- **프로젝트 단계**: Phase 3 (운영 안정성 - 비동기 큐)
- **이슈**: Issue #15 - MVP 운영 안정성 확보
- **상태**: ✅ 완료 (Step 1-5: 구현 + 테스트 + 문서화)

---

## 참고 문서

- **PDR (Product Design Review)**: [`docs/pdr.md`](./docs/pdr.md)
  - 전체 프로젝트 로드맵 (Phase 1-3)
  - 백테스트 엔진, 실전 시뮬레이션, 자동매매 설계

- **Issue #1 해결 계획**: [`docs/coin/mvp/ri_1.md`](./docs/coin/mvp/ri_1.md)
  - 데이터 로더 구현 5단계 계획
  - 단계별 의존성 및 산출물

---

## 지원 및 문의

프로젝트 저장소: https://github.com/sunbangamen/coin_hts/

이슈 트래킹: https://github.com/sunbangamen/coin_hts/issues/1
