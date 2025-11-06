# 자동 실시간 데이터 수집 파이프라인 완전 가이드

**최종 작성일**: 2025-11-06
**상태**: ✅ 완성 (Step 1-3 완료)

---

## 📋 목차
1. [구조 개요](#구조-개요)
2. [Step 1: 실제 API 테스트](#step-1-실제-api-테스트)
3. [Step 2: RQ Worker 배포](#step-2-rq-worker-배포)
4. [Step 3: 자동 스케줄링](#step-3-자동-스케줄링)
5. [모니터링 및 문제 해결](#모니터링-및-문제-해결)
6. [프로덕션 배포](#프로덕션-배포)

---

## 구조 개요

```
┌─────────────────────────────────────────────────────────┐
│  FastAPI Application (Backend)                           │
│  - Startup Event: 스케줄러 초기화                         │
│  - Shutdown Event: 스케줄러 정리                          │
│  - API Endpoint: GET /api/scheduler/status              │
└────────────┬────────────────────────────────────────────┘
             │
             ├─────────────────────────────────────────────┐
             │                                             │
    ┌────────▼────────────┐                    ┌──────────▼─────────┐
    │  APScheduler        │                    │  RQ (Redis Queue)  │
    │  - Daily Schedule   │───────────────────▶│  - Job Queue       │
    │  - 09:00 UTC Run    │                    │  - Background Jobs │
    └────────────────────┘                    └──────────┬─────────┘
                                                        │
                                            ┌───────────▼──────────┐
                                            │  RQ Worker           │
                                            │  - Job Processor     │
                                            │  - PID 33494         │
                                            └───────────┬──────────┘
                                                        │
                    ┌───────────────────────────────────┼──────────────────────┐
                    │                                   │                      │
         ┌──────────▼──────────┐           ┌────────────▼────────┐  ┌─────────▼──────┐
         │ Upbit REST API      │           │  fetch_candles_job  │  │  Parquet Files │
         │ GET /v1/candles/*   │           │  - Symbol: KRW-BTC  │  │  /data/        │
         │ Rate: 10/sec, 600/m │           │  - Timeframe: 1H    │  │  - KRW-BTC/    │
         └──────────────────────┘          │  - Days: 1          │  │  - KRW-ETH/    │
                    ▲                      │  - Overwrite: False  │  │  - KRW-XRP/    │
                    │                      └─────────────────────┘  └────────────────┘
                    └──────────────────────────────────────────────────┘
```

---

## Step 1: 실제 API 테스트

### 목표
Redis와 Upbit API가 정상 작동하는지 확인합니다.

### 실행 방법

```bash
# 1. Redis 상태 확인
redis-cli ping
# 응답: PONG

# 2. 실제 API 테스트 실행
source venv/bin/activate
python scripts/test_rq_job.py
```

### 예상 결과

```
✓ Redis 연결 성공
✓ 작업 큐 추가 성공
  Job ID: b0f81796-24be-4c86-b38b-4a8f443f9eb0
  Status: JobStatus.QUEUED
✓ 함수 실행 성공
  Success: True
  Message: KRW-BTC 1H 데이터 수집 완료
✓ 배치 작업 큐 추가 성공
✓ Parquet 파일 확인
  경로: data/KRW-BTC/1H/2025.parquet
  행 수: 50
```

### 검증 사항

- ✅ Upbit API 정상 호출
- ✅ Rate limiting 준수 (0.12초 간격, 분당 600회)
- ✅ Parquet 파일 생성
- ✅ 타임스탬프 정규화 (UTC)

---

## Step 2: RQ Worker 배포

### 목표
백그라운드에서 큐의 작업을 자동으로 처리하는 Worker를 배포합니다.

### 설정 단계

```bash
# 1. DATA_ROOT 환경변수 설정
export DATA_ROOT=/home/limeking/projects/worktree/coin-19/data

# 2. 디렉토리 권한 설정 (중요!)
chmod 777 $DATA_ROOT

# 3. RQ Worker 시작
source venv/bin/activate
rq worker data_ingestion -u redis://localhost:6379 --verbose
```

### 작업 추가 테스트

```bash
source venv/bin/activate
python3 << 'EOF'
import redis
from rq import Queue
from backend.app.jobs import fetch_candles_job

conn = redis.Redis(host='localhost', port=6379, db=0)
q = Queue('data_ingestion', connection=conn)

# 작업 추가
job = q.enqueue(
    fetch_candles_job,
    symbol='KRW-ETH',
    timeframe='1H',
    days=1,
    overwrite=False
)
print(f"✅ 작업 추가: {job.id}")
EOF
```

### 작업자 상태 확인

```bash
# Worker 프로세스 확인
ps aux | grep "rq worker"

# 예상 출력:
# limeking 33494  0.0  0.2 116904 34424 ? Sl 17:09 0:00 rq worker ...
```

### Docker Compose 배포

```bash
# 1. Worker 프로필로 시작
docker-compose --profile worker up worker

# 2. 로그 확인
docker-compose logs -f worker

# 3. 중지
docker-compose --profile worker down
```

---

## Step 3: 자동 스케줄링

### 환경 변수 기반 설정

모든 스케줄러 설정은 **환경 변수**를 통해 동적으로 제어됩니다:

| 변수 | 기본값 | 설명 | 예시 |
|------|-------|------|------|
| `ENABLE_SCHEDULER` | `true` | 자동 스케줄링 활성화 여부 | `true` / `false` |
| `SCHEDULER_HOUR` | `9` | 수집 시간 (UTC, 0-23) | `9` = UTC 09:00 = KST 18:00 |
| `SCHEDULER_MINUTE` | `0` | 수집 분 (0-59) | `0` |
| `SCHEDULER_SYMBOLS` | `KRW-BTC,KRW-ETH,KRW-XRP` | 수집 심볼 (쉼표 구분) | `KRW-BTC,KRW-ETH` |
| `SCHEDULER_TIMEFRAMES` | `1H,1D` | 수집 타임프레임 (쉼표 구분) | `1H,1D` |
| `REDIS_HOST` | `localhost` | Redis 호스트 | `localhost` / `redis.example.com` |
| `REDIS_PORT` | `6379` | Redis 포트 | `6379` |

#### ENABLE_SCHEDULER 상태별 동작

**ENABLE_SCHEDULER=true (기본값)**
```bash
# 자동 스케줄링 활성화
# - BackgroundScheduler 시작
# - APScheduler를 이용한 매일 자동 실행
# - 지정된 시간에 데이터 자동 수집
# - /api/scheduler/status: 스케줄 정보 포함
export ENABLE_SCHEDULER=true
```

**ENABLE_SCHEDULER=false**
```bash
# 자동 스케줄링 비활성화 (수동 모드)
# - BackgroundScheduler 초기화 안 함 (메모리/CPU 절감)
# - 수동 트리거만 가능: POST /api/scheduler/trigger
# - /api/scheduler/status: "disabled" 상태 반환
# - 여전히 모니터링 가능 (상태 조회, 수동 실행)
export ENABLE_SCHEDULER=false
```

### 구성 요소

#### 1. 스케줄러 모듈 (`backend/app/scheduler.py`)

```python
schedule_daily_collection(
    symbols=['KRW-BTC', 'KRW-ETH', 'KRW-XRP'],
    timeframes=['1H', '1D'],
    hour=9,  # UTC (KST 18:00)
    minute=0,
    days=1,
    overwrite=False
)
```

**시간대 변환**:
- UTC 09:00 = KST 18:00 (오후 6시)
- 필요시 다른 시간으로 변경 가능

#### 2. FastAPI 통합 (`backend/app/main.py`)

```python
@app.on_event("startup")
async def startup_scheduler():
    """앱 시작 시 스케줄러 초기화"""
    start_scheduler()
    schedule_daily_collection(...)

@app.on_event("shutdown")
async def shutdown_scheduler():
    """앱 종료 시 스케줄러 정리"""
    stop_scheduler()

@app.get("/api/scheduler/status")
async def get_scheduler_status_endpoint():
    """스케줄러 상태 조회"""
    return get_scheduler_status()
```

### 실행 방법

```bash
# 1. Backend 시작 (스케줄러 자동 초기화)
export DATA_ROOT=/home/limeking/projects/worktree/coin-19/data
source venv/bin/activate
python -m uvicorn backend.app.main:app --reload

# 2. 로그 확인
# 🚀 스케줄러 시작 중...
# ✅ 스케줄러 준비 완료
# ✅ 스케줄 설정 완료
# 실행 시간: 매일 09:00 (UTC)

# 3. 스케줄러 상태 확인
curl http://localhost:8000/api/scheduler/status
```

### 예상 응답

```json
{
  "running": true,
  "jobs": [
    {
      "id": "daily_data_collection",
      "name": "Daily Data Collection",
      "trigger": "cron[hour='9', minute='0']",
      "next_run": "2025-11-07T09:00:00+00:00"
    }
  ]
}
```

---

## 모니터링 및 문제 해결

### 1. Worker 로그 확인

```bash
# 실시간 로그 모니터링
rq info -i 1

# 특정 큐 확인
rq info -i 1 data_ingestion

# 작업 상세 조회
rq info data_ingestion
```

### 2. Redis 상태 확인

```bash
# 큐 크기
redis-cli LLEN rq:queue:data_ingestion

# 처리 중인 작업
redis-cli HLEN rq:workers

# 모든 키 조회
redis-cli KEYS 'rq:*'
```

### 3. 데이터 파일 확인

```bash
# 저장된 파일 목록
find data -name "*.parquet" -type f -ls

# 파일 검증
source venv/bin/activate
python scripts/inspect_parquet.py --path data/KRW-BTC/1H/2025.parquet --verbose
```

### 4. 일반 문제 해결

| 문제 | 원인 | 해결 |
|------|------|------|
| Permission denied `/data` | 디렉토리 권한 부족 | `chmod 777 $DATA_ROOT` |
| Worker timeout | 작업 시간 초과 | Redis TTL 증가 또는 작업 분할 |
| Parquet 검증 실패 | 파일 손상 | 다시 수집하거나 `--overwrite` 사용 |
| Rate limit 오류 | API 요청 초과 | Worker 수 감소 또는 스케줄 조정 |

---

## 프로덕션 배포

### 1. Docker 기반 배포

```bash
# 1. 이미지 빌드
docker-compose build

# 2. 서비스 시작
docker-compose up -d postgres redis backend

# 3. Worker 시작
docker-compose --profile worker up -d worker

# 4. 상태 확인
docker-compose ps
```

### 2. 환경 변수 설정

```bash
# .env 파일
DATA_ROOT=/data
REDIS_HOST=redis
REDIS_PORT=6379
DATABASE_URL=postgresql://user:password@postgres:5432/db
TZ=Asia/Seoul
```

### 3. Systemd 서비스 (Linux)

```bash
# /etc/systemd/system/rq-worker.service
[Unit]
Description=RQ Worker for Data Ingestion
After=redis.service

[Service]
Type=simple
User=app
WorkingDirectory=/opt/coin-backtesting
Environment="VIRTUAL_ENV=/opt/coin-backtesting/venv"
Environment="PATH=/opt/coin-backtesting/venv/bin"
Environment="DATA_ROOT=/data"
ExecStart=/opt/coin-backtesting/venv/bin/rq worker data_ingestion

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 4. 모니터링 (선택)

```bash
# Supervisor 예제
[program:rq_worker]
command=/path/to/venv/bin/rq worker data_ingestion
directory=/path/to/project
user=app
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
```

---

## 체크리스트

### 개발 환경 (로컬 테스트)
- [ ] Redis 실행 중
- [ ] Backend 실행 중 (ENABLE_SCHEDULER=true 권장)
- [ ] Worker 실행 중 (선택, 수동 테스트 시)
- [ ] Parquet 파일 생성 확인
- [ ] 스케줄러 상태 정상 (GET /api/scheduler/status)
- [ ] 수동 트리거 테스트 (POST /api/scheduler/trigger)

### 스테이징/프로덕션
- [ ] Docker 이미지 빌드 완료
- [ ] 환경 변수 설정 (.env 파일)
  - [ ] ENABLE_SCHEDULER 값 확인
  - [ ] SCHEDULER_HOUR/MINUTE 타임존 확인 (UTC 기준)
  - [ ] SCHEDULER_SYMBOLS, SCHEDULER_TIMEFRAMES 설정
  - [ ] REDIS_HOST/PORT 확인
- [ ] Redis 백업 정책 수립
- [ ] RQ Worker 모니터링 설정
- [ ] verify_scheduler.py 정기 실행 (cron)
- [ ] 모니터링/알림 구성
- [ ] 재해 복구 계획 수립

### ENABLE_SCHEDULER 설정별 체크사항

**자동 모드 (ENABLE_SCHEDULER=true)**
- [ ] BackgroundScheduler 초기화 확인 (로그)
- [ ] 스케줄된 작업 확인 (GET /api/scheduler/status)
- [ ] next_run_time이 올바르게 설정되었는지 확인
- [ ] 지정된 시간에 자동 실행 확인 (RQ 큐 모니터링)

**수동 모드 (ENABLE_SCHEDULER=false)**
- [ ] 스케줄러 비활성화 로그 확인
- [ ] GET /api/scheduler/status에서 "disabled" 메시지 확인
- [ ] POST /api/scheduler/trigger로 수동 실행 가능 확인
- [ ] 메모리/CPU 사용량이 감소했는지 확인

---

## 다음 단계 (Step 4)

### CI/CD 파이프라인 구축
```yaml
# GitHub Actions 예제
name: Test & Deploy

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
      postgres:
        image: postgres:15-alpine
    steps:
      - uses: actions/checkout@v2
      - name: Run offline tests
        run: python scripts/test_rq_job.py --offline
      - name: Run unit tests
        run: pytest tests/ -v
```

---

## 지원 및 문의

- 로그 위치: `/var/log/coin-backtesting/`
- Redis 모니터링: `redis-cli monitor`
- RQ 웹 UI: `rq-dashboard` (선택)

**결론**: 모든 자동 데이터 수집 파이프라인이 준비되어 있으며, Step 1-3이 완료되었습니다. 프로덕션 배포는 팀의 인프라 환경에 맞춰 조정하면 됩니다.
