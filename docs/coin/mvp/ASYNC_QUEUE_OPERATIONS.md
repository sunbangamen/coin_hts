# 비동기 태스크 큐 운영 가이드

**문서**: Phase 3 비동기 태스크 큐 운영 플레이북
**대상**: 운영팀, DevOps, 시스템 관리자
**마지막 업데이트**: 2025-11-10

---

## 목차

1. [아키텍처 개요](#아키텍처-개요)
2. [운영 시나리오](#운영-시나리오)
3. [장애 대응 플레이북](#장애-대응-플레이북)
4. [모니터링 지표](#모니터링-지표)
5. [명령어 참고](#명령어-참고)

---

## 아키텍처 개요

### 데이터 흐름

```
┌──────────────┐
│   Client     │
│  (Frontend)  │
└──────┬───────┘
       │ HTTP POST /api/backtests/run-async
       │
┌──────▼───────┐     ┌─────────────────┐
│  Backend     │────▶│   Redis Queue   │
│   FastAPI    │     │   (RQ)          │
└──────┬───────┘     └─────┬───────────┘
       │                   │
       │ 202 Accepted      │ Task Queued
       │ task_id returned  │
       │                   │
┌──────▼───────────────────▼──────────┐
│        RQ Worker Process(es)        │
│  - Dequeue task from Redis          │
│  - Execute backtest logic           │
│  - Store result to S3/Disk          │
│  - Update task status               │
└────────────────┬────────────────────┘
                 │
        ┌────────▼────────┐
        │  Result Storage │
        │ (S3/Disk)       │
        └─────────────────┘
```

### 핵심 컴포넌트

| 컴포넌트 | 역할 | 위치 |
|---------|------|------|
| **Backend API** | 작업 제출 및 상태 조회 | Docker: `backend` |
| **Redis** | 작업 큐 저장소 | Docker: `redis` |
| **RQ Worker** | 큐에서 작업 처리 | Docker: `worker` (profile: worker) |
| **Result Manager** | 결과 저장 및 정리 | Backend 내부 |
| **Storage Provider** | S3/Disk 저장소 | Backend 내부 |

### 작업 생명주기

```
제출 (Submit)
     ↓
┌─────────────────────┐
│  queued             │ (0-? 초)
│ - Redis에 저장됨    │ 워커가 처리 대기 중
│ - progress: 0.0     │
└────────┬────────────┘
         │ 워커 시작
         ↓
┌─────────────────────┐
│  running            │ (? 초 - ? 분)
│ - 작업 실행 중      │ 진행률 업데이트
│ - progress: 0.0-1.0 │
└────────┬────────────┘
         │ 완료
         ↓
┌─────────────────────┐
│  completed          │ (TTL: 7일)
│ - 결과 저장됨       │ 자동 정리됨
│ - progress: 1.0     │
└─────────────────────┘
```

또는 오류 발생:

```
실행 중 → failed (error 메시지 포함)
       ↓
    DLQ (Dead Letter Queue)
    ↓
  수동 검토 → 재실행 or 삭제
```

---

## 운영 시나리오

### 시나리오 1: 정상 실행

**상황**: 모든 시스템 정상, 비동기 백테스트 성공

**흐름**:

```bash
# 1. 클라이언트: 비동기 백테스트 요청
curl -X POST http://localhost:8000/api/backtests/run-async \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "volume_zone_breakout",
    "symbols": ["BTC_KRW", "ETH_KRW"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }'

# 응답:
# {
#   "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
#   "status": "queued",
#   "created_at": "2025-11-10T10:30:45.123456Z"
# }

# 2. 모니터: Redis에 작업 저장됨
redis-cli LLEN rq:queue:backtest-queue
# 출력: 1 (또는 그 이상)

# 3. 모니터: 워커 처리 중
redis-cli GET rq:job:a1b2c3d4-e5f6-7890-abcd-ef1234567890
# 상태: started (progress 증가)

# 4. 클라이언트: 상태 폴링
curl http://localhost:8000/api/backtests/status/a1b2c3d4-e5f6-7890-abcd-ef1234567890
# 응답: status = "running", progress = 0.45

# 5. 워커: 작업 완료
# → 결과 저장 (S3 또는 Disk)
# → Redis에서 제거

# 6. 클라이언트: 최종 결과
# {
#   "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
#   "status": "completed",
#   "progress": 1.0,
#   "result": { /* 백테스트 결과 */ }
# }
```

**확인 사항**:
- ✅ 202 Accepted 응답 (< 100ms)
- ✅ task_id 생성됨
- ✅ Redis 큐에 작업 저장됨
- ✅ 워커 처리 중 진행률 업데이트
- ✅ 최종 결과 저장됨

**소요 시간**: 구간별 시간 기록

```bash
# 로그 확인
grep "task_id: a1b2c3d4" ${DATA_ROOT}/logs/app.log | tail -10
```

---

### 시나리오 2: 워커 장애

**상황**: RQ 워커 프로세스 다운, 작업 처리 불가

**증상**:
- 작업이 `queued` 상태로 계속 대기
- 진행률 업데이트 없음
- 타임아웃 발생 (기본: 360초)

**진단**:

```bash
# 1. 워커 상태 확인
rq info

# 출력:
# backtest-queue: 1 jobs (stuck in queued)
# default: 0 jobs
# Workers: 0 (should be 2)
# ❌ 워커 없음!

# 2. Docker 컨테이너 확인
docker-compose ps
# worker 컨테이너 상태 확인 (Up? Exited?)

# 3. 워커 로그 확인
docker-compose logs worker --tail=50
```

**복구 방법**:

```bash
# 방법 1: 워커 재시작 (Docker)
docker-compose --profile worker up -d worker

# 방법 2: 워커 재시작 (로컬)
pkill -f "rq worker"
rq worker backtest-queue -w 2 --verbose &

# 3. 상태 확인
rq info
# 출력: Workers: 2 ✅

# 4. 작업 확인
# 자동으로 재처리 또는 수동으로 재시작
curl -X POST http://localhost:8000/api/backtests/retry/a1b2c3d4 \
  -H "Content-Type: application/json"
```

**예방 방법**:
- Docker healthcheck 활성화
- 모니터링 알림 설정 (워커 개수 < 1)

---

### 시나리오 3: Redis 장애

**상황**: Redis 서비스 다운, 모든 큐 손실

**증상**:
- "Connection refused" 오류
- 새 작업 제출 불가
- 기존 작업 조회 불가

**진단**:

```bash
# 1. Redis 연결 확인
redis-cli ping
# 오류: Could not connect to Redis at 127.0.0.1:6379

# 2. Redis 프로세스 확인
docker-compose ps redis
# 또는
ps aux | grep redis-server

# 3. Redis 로그 확인
docker-compose logs redis --tail=50
```

**복구 방법**:

```bash
# 방법 1: Redis 재시작 (Docker)
docker-compose restart redis

# 방법 2: Redis 재시작 (로컬)
redis-cli shutdown
redis-server &

# 3. 헬스 체크
redis-cli INFO server | grep redis_version
# 출력: redis_version:7.0.0

# 4. 큐 상태 확인
rq info
# Redis 재시작 후 기존 작업은 손실됨
```

**데이터 복구**:

```bash
# Redis 백업에서 복구
gunzip -c backups/redis/dump_*.rdb.gz > /tmp/dump.rdb
docker-compose cp /tmp/dump.rdb redis:/data/dump.rdb
docker-compose restart redis

# 복구 확인
rq info | grep "backtest-queue"
```

**예방 방법**:
- Redis persistence 활성화 (appendonly.aof)
- 자동 백업 스케줄 설정 (매일 자정)
- 모니터링 알림 (Redis 메모리 > 80%)

---

### 시나리오 4: 작업 타임아웃

**상황**: 작업이 예상보다 길어서 타임아웃 발생

**증상**:
- 작업 상태: `failed`
- 오류 메시지: "Job exceeded timeout of 360 seconds"
- 부분 결과 손실

**진단**:

```bash
# 1. 작업 상태 확인
curl http://localhost:8000/api/backtests/status/a1b2c3d4
# 응답: status = "failed", error = "Job exceeded timeout..."

# 2. 작업 로그 확인
redis-cli GET rq:job:a1b2c3d4:exc_info
# 또는
grep "a1b2c3d4" ${DATA_ROOT}/logs/app.log

# 3. DLQ 확인
redis-cli LRANGE rq:failed_queue 0 -1
# 실패한 작업 목록
```

**복구 방법**:

```bash
# 방법 1: 타임아웃 증가하고 재실행
# backend/app/config.py 또는 환경 변수 수정
# RQ_JOB_TIMEOUT=1800  # 30분

# 방법 2: 작업 분할 (추천)
# 백테스트를 여러 청크로 나누어 실행
# 예: 12개월 → 4개월 × 3개 작업

# 방법 3: 비동기 작업 최적화
# 병렬 처리 개선
# 캐시 활용

# 방법 4: DLQ에서 수동 재실행
rq requeue -u rq:failed_queue
```

**모니터링**:

```bash
# 느린 작업 추적
watch -n 5 'rq info | grep -A 2 backtest-queue'

# 타임아웃 비율
redis-cli ZCOUNT rq:failed_queue -inf +inf | awk '{print $0 " tasks in DLQ"}'
```

---

### 시나리오 5: DLQ 처리

**상황**: 여러 작업이 DLQ에 쌓임, 수동 검토 필요

**증상**:
- DLQ 큐 길이 증가
- 실패 비율 > 5%
- 알림 발생

**진단**:

```bash
# 1. DLQ 상태 확인
rq info

# 출력:
# backtest-queue: 0 jobs
# failed_queue: 23 jobs ⚠️

# 2. 실패 작업 목록
redis-cli LRANGE rq:failed_queue 0 -1 | head -5

# 3. 실패 이유 분석
redis-cli GET rq:job:<task_id>:exc_info

# 4. 실패율 계산
FAILED=$(redis-cli ZCOUNT rq:failed_queue -inf +inf)
COMPLETED=$(redis-cli ZCOUNT rq:finished_queue -inf +inf)
TOTAL=$((FAILED + COMPLETED))
RATE=$((FAILED * 100 / TOTAL))
echo "Failure rate: ${RATE}%"
```

**복구 방법**:

```bash
# 방법 1: 모든 DLQ 작업 재실행
rq requeue -u rq:failed_queue

# 방법 2: 특정 작업만 재실행
rq requeue --job-ids <task_id1>,<task_id2> -u rq:failed_queue

# 방법 3: 오래된 작업 정리 (7일 이상)
python << 'EOF'
import redis
from datetime import datetime, timedelta

r = redis.Redis()
cutoff = datetime.now() - timedelta(days=7)
failed = r.zrange('rq:failed_queue', 0, -1)

for job_id in failed:
    # 타임스탬프 확인
    info = r.get(f'rq:job:{job_id}')
    # 오래된 경우 삭제
    r.zrem('rq:failed_queue', job_id)
    r.delete(f'rq:job:{job_id}')

print(f"Cleaned up {len(failed)} jobs")
EOF

# 방법 4: 대시보드에서 확인 및 수동 처리
# (선택) Flower 대시보드: http://localhost:5555
```

**예방 방법**:
- 작업 로직 개선 (에러 처리)
- 입력 검증 강화
- 타임아웃 설정 최적화
- 모니터링 알림 설정 (DLQ > 10개)

---

## 장애 대응 플레이북

### 문제 해결 흐름도

```
문제 발생
    ↓
증상 확인 ──→ 로그 수집
    ↓
원인 분석
    ↓
┌──────────────────────────────────┐
│ 1. Redis 문제?                   │
│    → Redis 재시작                │
│    → 백업에서 복구               │
└──────────────────────────────────┘
    ↓
┌──────────────────────────────────┐
│ 2. 워커 문제?                    │
│    → 워커 재시작                 │
│    → 로그 확인                   │
│    → 작업 재실행                 │
└──────────────────────────────────┘
    ↓
┌──────────────────────────────────┐
│ 3. 작업 문제?                    │
│    → 타임아웃 조정               │
│    → 작업 분할                   │
│    → DLQ 정리                    │
└──────────────────────────────────┘
    ↓
해결됨
```

### 일반적인 명령어

| 작업 | 명령어 | 비고 |
|------|--------|------|
| **상태 확인** | `rq info` | 모든 큐와 워커 상태 |
| **특정 작업 확인** | `rq job <task_id>` | 상세 정보 |
| **큐 길이** | `redis-cli LLEN rq:queue:backtest-queue` | 대기 작업 수 |
| **워커 시작** | `rq worker backtest-queue -w 2` | 로컬 환경 |
| **워커 시작 (Docker)** | `docker-compose --profile worker up worker` | Docker 환경 |
| **DLQ 확인** | `redis-cli ZRANGE rq:failed_queue 0 -1` | 실패 작업 목록 |
| **작업 재실행** | `rq requeue -u rq:failed_queue` | 모든 DLQ 작업 |
| **작업 삭제** | `rq empty rq:failed_queue` | DLQ 비우기 |
| **Redis 플러시** | `redis-cli FLUSHDB` | ⚠️ 모든 데이터 삭제! |

---

## 모니터링 지표

### 정상 범위

| 지표 | 정상 | 경고 | 심각 |
|-----|------|------|------|
| **큐 길이** | 0-10 | 10-50 | >50 |
| **작업 실패율** | <5% | 5-10% | >10% |
| **평균 처리 시간** | <300초 | 300-600초 | >600초 |
| **워커 개수** | ≥2 | 1 | 0 |
| **Redis 메모리** | <50% | 50-80% | >80% |
| **DLQ 크기** | <5 | 5-20 | >20 |

### 모니터링 스크립트

**1. 실시간 모니터링** (5초 간격):

```bash
watch -n 5 'rq info'
```

**2. 헬스 체크**:

```bash
./scripts/health_check.sh verbose
```

**3. 성능 벤치마크**:

```bash
./scripts/benchmark.py --monitor
```

**4. 커스텀 모니터링**:

```python
import redis
import time
from collections import defaultdict

r = redis.Redis()

def monitor():
    stats = {
        'queue_length': r.llen('rq:queue:backtest-queue'),
        'failed_count': r.zcount('rq:failed_queue', '-inf', '+inf'),
        'finished_count': r.zcount('rq:finished_queue', '-inf', '+inf'),
        'memory_usage': int(r.info('memory')['used_memory_human'].split('M')[0]),
        'connected_clients': r.info('clients')['connected_clients']
    }

    # 실패율 계산
    total = stats['failed_count'] + stats['finished_count']
    failure_rate = (stats['failed_count'] / total * 100) if total > 0 else 0
    stats['failure_rate'] = failure_rate

    # 경고
    if stats['queue_length'] > 50:
        print(f"⚠️ Queue too long: {stats['queue_length']}")
    if failure_rate > 10:
        print(f"❌ Failure rate high: {failure_rate:.1f}%")
    if stats['memory_usage'] > 512:
        print(f"⚠️ Redis memory high: {stats['memory_usage']}MB")

    return stats

while True:
    stats = monitor()
    print(f"📊 {time.strftime('%Y-%m-%d %H:%M:%S')} - {stats}")
    time.sleep(5)
```

### Slack 알림 통합

```bash
# .env 설정
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_ENABLED=true

# 모니터링 스크립트에서 알림
python << 'EOF'
import os
import requests

SLACK_WEBHOOK = os.getenv('SLACK_WEBHOOK_URL')

def send_alert(message, level='WARNING'):
    color_map = {
        'INFO': '#36a64f',
        'WARNING': '#ff9900',
        'ERROR': '#ff0000'
    }

    payload = {
        'attachments': [{
            'color': color_map.get(level, '#999999'),
            'title': f'{level}: RQ 큐 알림',
            'text': message,
            'ts': int(time.time())
        }]
    }

    requests.post(SLACK_WEBHOOK, json=payload)

# 사용 예
send_alert('Queue length exceeds 50 tasks', 'ERROR')
EOF
```

---

## 명령어 참고

### RQ 명령어

```bash
# 1. 정보 조회
rq info                                    # 전체 상태
rq job <task_id>                         # 특정 작업 정보
rq info --workers                        # 워커 정보
rq info --empty                          # 빈 큐 표시

# 2. 큐 관리
rq empty rq:queue:backtest-queue         # 큐 비우기 (대기 작업 삭제)
rq requeue -u rq:failed_queue            # DLQ 작업 재실행
rq requeue -u rq:failed_queue --job-ids <id> # 특정 작업 재실행

# 3. 워커 관리
rq worker backtest-queue -w 2            # 워커 시작 (2 프로세스)
rq worker --help                         # 옵션 확인
```

### Redis 명령어

```bash
# 1. 연결 확인
redis-cli ping                           # PONG 응답

# 2. 큐 상태
redis-cli LLEN rq:queue:backtest-queue  # 대기 작업 수
redis-cli ZCOUNT rq:failed_queue -inf +inf  # 실패 작업 수
redis-cli ZCOUNT rq:finished_queue -inf +inf # 완료 작업 수

# 3. 메모리 상태
redis-cli INFO memory                    # 메모리 사용률
redis-cli MEMORY STATS                   # 상세 메모리 정보

# 4. 키 확인
redis-cli KEYS "rq:*" | wc -l           # RQ 관련 키 개수
redis-cli SCAN 0 MATCH "rq:job:*" COUNT 100  # 작업 키 스캔

# 5. 데이터 정리
redis-cli FLUSHDB                        # ⚠️ 전체 데이터 삭제!
redis-cli FLUSHDB ASYNC                  # 비동기 삭제
```

### Docker 명령어

```bash
# 1. 서비스 확인
docker-compose ps                        # 컨테이너 상태
docker-compose logs backend -f --tail=50 # 로그 확인
docker-compose logs worker -f --tail=50

# 2. 서비스 재시작
docker-compose restart redis              # Redis 재시작
docker-compose restart backend            # Backend 재시작
docker-compose --profile worker restart worker  # 워커 재시작

# 3. 서비스 스케일링
docker-compose --profile worker up -d worker --scale worker=4  # 워커 4개로 증가
```

---

## 자동화 및 모니터링 설정

### Cron 작업

```bash
# 매일 자정에 모니터링 리포트 생성
0 0 * * * python3 /path/to/monitor.py >> /var/log/rq-monitor.log

# 매주 일요일 DLQ 정리
0 1 * * 0 redis-cli ZREMRANGEBYSCORE rq:failed_queue -inf $(date +%s -d "30 days ago")

# 매시간 백업
0 * * * * /path/to/scripts/backup.sh redis
```

### Systemd 서비스 (선택)

```ini
# /etc/systemd/system/rq-worker.service

[Unit]
Description=RQ Worker for Backtest Queue
After=redis.service

[Service]
Type=simple
User=app
WorkingDirectory=/home/app/coin_hts
ExecStart=/usr/local/bin/rq worker backtest-queue -w 2 --verbose
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 시작
sudo systemctl start rq-worker
sudo systemctl enable rq-worker
```

---

## 참고 문서

- **README.md**: Phase 3 기능 개요 및 API 사용법
- **MIGRATION_CHECKLIST.md**: Phase 2→3 마이그레이션 가이드
- **PHASE3_COMPLETION_SUMMARY.md**: Phase 3 완료 요약 및 테스트 현황
- **scripts/health_check.sh**: 자동 헬스 체크 스크립트
- **scripts/backup.sh**: 자동 백업 스크립트
- **scripts/benchmark.py**: 성능 벤치마킹 도구

---

## FAQ

**Q: 작업이 queued 상태에서 계속 대기합니다**
A: 워커가 없거나 다운되었을 가능성이 높습니다. `rq info` 확인 후 워커 재시작.

**Q: "Job exceeded timeout" 오류가 발생합니다**
A: 작업이 기본 타임아웃(360초)을 초과. 타임아웃 증가 또는 작업 분할 필요.

**Q: Redis 메모리가 계속 증가합니다**
A: TTL이 설정되지 않았거나 오래된 작업 정리 실패. `scripts/cleanup_task_results.py` 실행.

**Q: 워커를 여러 개 실행하려면?**
A: `rq worker backtest-queue -w 4` (4개 프로세스) 또는 Docker Compose로 스케일링.

---

**마지막 검토**: 2025-11-10
**다음 검토**: 2025-11-24 (2주)
