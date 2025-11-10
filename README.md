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

## Phase 3: 비동기 태스크 큐 & 운영 안정성

**Phase 3**에서는 장시간 실행되는 백테스트를 비동기로 처리하고, 포지션 관리, 외부 스토리지, 자동 백업, 모니터링/알림을 추가했습니다.

**테스트 통과율**: 218/218 (100%) ✅

### 1. 비동기 백테스트 API

#### 1.1 비동기 모드로 백테스트 실행
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

#### 1.2 작업 상태 조회 (폴링)
```bash
# 작업 상태 조회
curl http://localhost:8000/api/backtests/status/a1b2c3d4-e5f6-7890-abcd-ef1234567890

# 응답 예: 완료됨
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "progress": 1.0,
  "result": {
    "symbols": ["BTC_KRW", "ETH_KRW"],
    "strategy": "volume_zone_breakout",
    "total_trades": 45,
    "win_rate": 0.62,
    "avg_return": 0.0156
  },
  "error": null
}
```

#### 1.3 RQ 워커 실행
```bash
# Docker 환경에서 워커 시작
docker-compose --profile worker up worker

# 로컬 환경에서 워커 시작 (별도 터미널)
rq worker backtest-queue -w 2 --job-monitoring-interval 30
```

### 2. 포지션 관리

비동기 백테스트 중 포지션(진입/청산)을 실시간으로 관리합니다.

**특징**:
- 자동 수수료 계산 (0.1%)
- 슬리피지 반영 (0.02%)
- 진입/청산/업데이트 콜백
- 포지션 조회 API

```python
from backend.app.simulation.position_manager import PositionManager

manager = PositionManager()

# 포지션 진입
position = manager.enter_position(
    symbol="BTC_KRW",
    quantity=1.0,
    entry_price=50000,
    side="BUY"
)

# 포지션 업데이트 (실시간 가격 반영)
manager.update_unrealized_pnl(
    position_id=position.id,
    current_price=51000
)

# 포지션 청산
closed = manager.close_position(
    position_id=position.id,
    exit_price=51500
)

# 포지션 조회
open_positions = manager.get_open_positions()
summary = manager.get_position_summary()
```

### 3. 외부 스토리지 (AWS S3)

백테스트 결과를 로컬/Docker 볼륨에서 AWS S3로 자동 전환합니다.

#### 3.1 S3 설정

**AWS IAM 최소 권한 정책** (doc: `docs/coin/mvp/STORAGE_MIGRATION_REPORT.md`):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::backtest-bucket",
        "arn:aws:s3:::backtest-bucket/*"
      ]
    }
  ]
}
```

#### 3.2 S3 업로드/다운로드
```python
from backend.app.storage.s3_provider import S3StorageProvider

provider = S3StorageProvider(
    bucket_name="backtest-bucket",
    region="us-east-1"
)

# 파일 업로드
result = await provider.upload(
    file_path="./results/backtest.json",
    remote_path="backtests/2024-01-01/result.json",
    metadata={"strategy": "volume_zone_breakout"}
)
# result: {success, etag, size, uploaded_at}

# 무결성 검증 (ETag 기반)
integrity = await provider.verify_integrity(
    remote_path="backtests/2024-01-01/result.json",
    local_etag="abc123..."
)

# 파일 목록 조회
files = await provider.list_files(
    prefix="backtests/2024-01/",
    limit=100
)
```

### 4. 로깅 & 알림 시스템

구조화된 JSON 로깅과 실시간 알림을 통해 운영팀이 시스템 상태를 모니터링합니다.

#### 4.1 구조화된 로깅
```python
from backend.app.logging import get_logger

logger = get_logger(__name__)

# JSON 형식 로그 (자동 타임스탐프, 레벨, 컨텍스트 포함)
logger.info("백테스트 시작", symbol="BTC_KRW", strategy="VZB")
logger.error("Redis 연결 오류", retry_count=3)
```

**로그 파일**: `${DATA_ROOT}/logs/app.log` (JSON 형식, 10MB 롤링)

#### 4.2 Slack 알림
```python
from backend.app.notifications import SlackNotifier

notifier = SlackNotifier()

# 헬스 체크 알림
await notifier.send_health_check_alert(
    title="CPU 사용률 높음",
    cpu_percent=85.5,
    memory_percent=76.3
)

# 백업 알림
await notifier.send_backup_alert(
    backup_type="postgresql",
    status="SUCCESS",
    duration_sec=45.3,
    size_mb=250
)

# 성능 알림
await notifier.send_performance_alert(
    metric="backtest_execution_time",
    value=0.28,
    sla_threshold=1.0,
    status="OK"
)
```

**설정**:
- `SLACK_WEBHOOK_URL`: Slack Incoming Webhook URL

#### 4.3 Email 알림
```python
from backend.app.notifications import EmailNotifier

notifier = EmailNotifier()

await notifier.send(
    to_addresses=["ops@company.com"],
    subject="System Alert - Redis 장애",
    body="Redis 서버가 응답하지 않습니다.",
    html_body="<html><body><h1>Redis 장애</h1>...</body></html>"
)
```

**설정**:
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
- `SMTP_FROM_ADDR`

### 5. 백업 & 자동화

PostgreSQL, Redis, 백테스트 결과를 자동으로 백업하고, 오래된 백업을 정리합니다.

#### 5.1 수동 백업
```bash
# 전체 백업 (DB + Redis + 결과)
./scripts/backup.sh all

# PostgreSQL만 백업
./scripts/backup.sh postgres

# Redis만 백업
./scripts/backup.sh redis

# S3에 백업
./scripts/backup.sh s3

# 오래된 백업 정리 (7일 이상)
./scripts/backup.sh cleanup 7

# 백업 통계 조회
./scripts/backup.sh stats
```

#### 5.2 자동 백업 스케줄
```python
from backend.app.backup_scheduler import get_backup_scheduler

scheduler = get_backup_scheduler()
scheduler.start()

# 기본 스케줄:
# - 매일 자정 (00:00 UTC): 전체 백업
# - 매주 일요일 01:00 UTC: 오래된 백업 정리 (7일 이상)
```

#### 5.3 백업 복구
```bash
# PostgreSQL 복구
gunzip -c backups/postgresql/backup_*.sql.gz | \
  docker-compose exec -T postgres psql -U coin_user -d coin_db

# Redis 복구
gunzip -c backups/redis/dump_*.rdb.gz > /tmp/dump.rdb
docker-compose cp /tmp/dump.rdb redis:/data/dump.rdb

# 결과 복구
tar -xzf backups/results/results_*.tar.gz -C ./data
```

### 6. 배포 자동화

#### 6.1 전체 배포
```bash
# 개발 환경 배포
./scripts/deploy.sh

# 스테이징 배포
./scripts/deploy.sh staging

# 프로덕션 배포
./scripts/deploy.sh production
```

**자동 실행 항목**:
- 환경 검증 (Python, Docker, docker-compose)
- 가상환경 생성 및 의존성 설치
- Docker 이미지 빌드
- 데이터베이스 마이그레이션
- RQ 큐 초기화
- 헬스 체크 (PostgreSQL, Redis, Backend API, S3)

#### 6.2 헬스 체크
```bash
# 기본 헬스 체크
./scripts/health_check.sh

# 상세 정보 출력
./scripts/health_check.sh verbose

# 지속 모니터링 (5초 간격)
./scripts/health_check.sh monitor

# 문제 발생 시 알림
./scripts/health_check.sh alert
```

**검사 항목**:
- PostgreSQL (연결, 데이터베이스 크기)
- Redis (메모리, RQ 큐 상태)
- Backend API (응답 시간)
- Docker 컨테이너
- 시스템 리소스 (CPU, 메모리, 디스크)

#### 6.3 성능 벤치마킹
```bash
# SLA 벤치마크 (100, 300, 1000캔들)
./scripts/benchmark.py

# 500캔들 벤치마크
./scripts/benchmark.py --candles 500

# 이전 결과와 비교
./scripts/benchmark.py --compare

# 지속 모니터링 (5분 간격)
./scripts/benchmark.py --monitor

# CSV 내보내기
./scripts/benchmark.py --export csv
```

**SLA 달성 현황**:
| 캔들 수 | 목표 | 실제 | 달성율 |
|--------|------|------|--------|
| 100 | < 0.1초 | 0.0228초 | ✅ 78% 초과 |
| 300 | < 0.5초 | 0.0708초 | ✅ 86% 초과 |
| 1000 | < 1.0초 | 0.2688초 | ✅ 73% 초과 |

### 7. 환경 변수

| 변수명 | 기본값 | 설명 |
|-------|-------|------|
| **데이터** | | |
| `DATA_ROOT` | `/data` | 데이터 루트 디렉토리 |
| **Redis** | | |
| `REDIS_URL` | `redis://redis:6379/0` | Redis 연결 URL |
| `REDIS_HOST` | `redis` | Redis 호스트 |
| `REDIS_PORT` | `6379` | Redis 포트 |
| `REDIS_DB` | `0` | Redis DB 번호 |
| **AWS S3** | | |
| `AWS_BUCKET_NAME` | - | S3 버킷 이름 |
| `AWS_REGION` | `us-east-1` | AWS 리전 |
| `AWS_ACCESS_KEY_ID` | - | AWS IAM 액세스 키 |
| `AWS_SECRET_ACCESS_KEY` | - | AWS IAM 시크릿 키 |
| **Slack 알림** | | |
| `SLACK_WEBHOOK_URL` | - | Slack Incoming Webhook URL |
| `SLACK_ENABLED` | `false` | Slack 알림 활성화 |
| **Email 알림** | | |
| `SMTP_HOST` | - | SMTP 서버 주소 |
| `SMTP_PORT` | `587` | SMTP 포트 |
| `SMTP_USER` | - | SMTP 사용자 |
| `SMTP_PASSWORD` | - | SMTP 비밀번호 |
| `SMTP_FROM_ADDR` | - | 발신자 이메일 |
| `EMAIL_ENABLED` | `false` | Email 알림 활성화 |
| **기타** | | |
| `ENVIRONMENT` | `development` | 실행 환경 |
| `TASK_RESULT_TTL_DAYS` | `7` | 태스크 결과 보존 기간 |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL 연결 URL |

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
