# 운영 가이드 (Operations)

Coin Backtesting API의 운영, 모니터링, 트러블슈팅 가이드입니다.

---

## 목차

1. [시스템 아키텍처](#시스템-아키텍처)
2. [배포](#배포)
3. [모니터링](#모니터링)
4. [성능 관리](#성능-관리)
5. [로그 관리](#로그-관리)
6. [트러블슈팅](#트러블슈팅)
7. [재해 복구](#재해-복구)

---

## 시스템 아키텍처

### 컴포넌트 구성

```
┌─────────────────────────────────────┐
│       클라이언트 (HTTP/REST)        │
└────────────────┬────────────────────┘
                 │
         ┌───────▼──────────┐
         │  FastAPI Backend │
         │  (포트 8000)      │
         └───────┬──────────┘
                 │
      ┌──────────┼──────────┐
      │          │          │
  ┌───▼──┐  ┌───▼──┐  ┌────▼────┐
  │ Redis│  │ RQ   │  │ 결과    │
  │ (큐)  │  │ 워커 │  │ 파일   │
  └──────┘  └──────┘  └─────────┘
```

### 서비스별 역할

| 서비스 | 역할 | 포트 | 상태 확인 |
|--------|------|------|----------|
| **FastAPI Backend** | API 요청 처리, 비동기 작업 큐 등록 | 8000 | `/health` |
| **Redis** | 작업 큐, 상태 저장소, 진행률 추적 | 6379 | `redis-cli ping` |
| **RQ Worker** | 백테스트 작업 처리 | - | 로그 확인 |
| **Data Volume** | 입력 데이터 (Parquet), 결과 저장 | - | 디스크 확인 |

---

## 배포

### 1. Docker 환경 배포

#### 사전 요구사항
- Docker 20.10+
- Docker Compose 1.29+
- 최소 2GB RAM
- 최소 10GB 디스크 공간

#### 배포 단계

```bash
# 1. 환경 변수 설정
cp .env.sample .env
# .env 파일 편집 (필요시)

# 2. 데이터 디렉토리 준비
mkdir -p data/results data/tasks

# 3. 이미지 빌드
docker-compose build

# 4. 서비스 시작 (Redis + Backend)
docker-compose up -d

# 5. 워커 시작 (별도 터미널 또는 스크린)
docker-compose --profile worker up -d worker

# 6. 상태 확인
docker-compose ps
```

#### 로그 확인
```bash
# 모든 서비스 로그
docker-compose logs -f

# 특정 서비스 로그
docker-compose logs -f backend
docker-compose logs -f redis
docker-compose logs -f worker
```

### 2. 로컬 환경 배포

```bash
# 1. Python 환경 설정
python -m venv venv
source venv/bin/activate

# 2. 의존성 설치
pip install -r requirements.txt

# 3. Redis 실행 (별도 터미널)
redis-server

# 4. Backend 실행
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# 5. 워커 실행 (별도 터미널)
python -m rq worker -c backend.app.config --verbose
```

### 3. 프로덕션 배포

#### Gunicorn + Supervisor 사용

```bash
# Gunicorn 설치
pip install gunicorn

# Supervisor 설정 파일 생성
# /etc/supervisor/conf.d/coin-api.conf

[program:coin-api]
command=/path/to/venv/bin/gunicorn \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  backend.app.main:app
directory=/path/to/project
user=nobody
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/coin-api.log

[program:coin-worker]
command=/path/to/venv/bin/python -m rq worker \
  -c backend.app.config \
  --verbose
directory=/path/to/project
user=nobody
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/coin-worker.log
```

```bash
# Supervisor 재로드
sudo supervisorctl reread
sudo supervisorctl update
```

---

## 모니터링

### 1. API 헬스체크

```bash
# 백엔드 상태 확인
curl http://localhost:8000/health

# 응답
{
  "status": "healthy",
  "timestamp": "2025-11-04T10:30:45.123456",
  "data_root": "/data",
  "results_dir": "/data/results"
}
```

### 2. Redis 모니터링

```bash
# Redis 연결 확인
redis-cli ping

# 메모리 사용량
redis-cli INFO memory

# 예상 출력
# used_memory: 5242880 (5MB)
# used_memory_peak: 10485760 (10MB)
# maxmemory: 0 (무제한)

# 작업 큐 상태
redis-cli LLEN rq:queue:default

# 진행 중인 작업
redis-cli KEYS "task:*"

# 특정 작업 상태 확인
redis-cli HGETALL "task:{task_id}"
```

### 3. 작업 모니터링

```bash
# 로그 실시간 모니터링
docker-compose logs -f worker

# 완료된 작업 확인
ls -la data/tasks/

# 특정 작업 결과 확인
cat data/tasks/{task_id}/manifest.json
```

### 4. 성능 메트릭

```bash
# 시스템 리소스 사용량
docker stats

# 백테스트 실행 시간 추적 (로그에서)
grep "execution_time" backend/logs/*.log
```

### 5. 모니터링 대시보드 (선택사항)

#### Prometheus + Grafana 설정

```bash
# Prometheus 설치
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v /path/to/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus

# Grafana 설치
docker run -d \
  --name grafana \
  -p 3000:3000 \
  grafana/grafana
```

---

## 성능 관리

### 1. Redis 메모리 관리

#### 메모리 제한 설정
```bash
# Redis 메모리 제한 (2GB)
redis-cli CONFIG SET maxmemory 2gb

# 제거 정책 설정 (LRU)
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# 설정 저장
redis-cli CONFIG REWRITE
```

#### TTL 정책
```bash
# Redis 자동 정리 (Task Manager에서 구현)
# TASK_TIMEOUT = 3600 초 (1시간)
# RESULT_TTL = 500 초

# 만료된 항목 확인
redis-cli SCAN 0 TYPE hash
```

### 2. 작업 큐 최적화

#### 워커 수 조정
```bash
# 현재 CPU 코어 수 확인
nproc

# 추천: CPU 코어 수 = 워커 수
# 예: 4 코어 → 4개 워커 시작

# Docker 환경에서 워커 스케일링
docker-compose up -d --scale worker=4
```

#### 작업 타임아웃 설정
```python
# backend/app/config.py
RQ_JOB_TIMEOUT = 3600  # 1시간 (필요시 조정)
```

### 3. 디스크 공간 관리

```bash
# 현재 디스크 사용량
du -sh data/

# 결과 파일 정리 (자동)
python scripts/cleanup_task_results.py

# 정리 스케줄 (cron)
# 매일 자정에 정리 실행
0 0 * * * /path/to/venv/bin/python /path/to/scripts/cleanup_task_results.py

# crontab 편집
crontab -e
```

### 4. 데이터베이스 정리

```bash
# 임시 파일 정리
docker-compose exec backend rm -rf /tmp/*

# 패키지 캐시 정리
docker image prune -a --force
docker volume prune --force
```

---

## 로그 관리

### 1. 로그 위치

```bash
# Docker 환경
docker-compose logs backend > backend.log
docker-compose logs worker > worker.log
docker-compose logs redis > redis.log

# 로컬 환경
# ~/.local/share/python-apps/rq/rq.log (RQ)
# stdout/stderr 리다이렉션 필요
```

### 2. 로그 레벨 설정

```python
# backend/app/main.py
import logging

logging.basicConfig(
    level=logging.INFO,  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="coin-api.log",  # 파일로 저장하려면
)
```

### 3. 로그 로테이션

```bash
# logrotate 설정
# /etc/logrotate.d/coin-api

/var/log/coin-*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 nobody nobody
    sharedscripts
    postrotate
        systemctl reload coin-api > /dev/null 2>&1 || true
    endscript
}
```

```bash
# 설정 검증
logrotate -d /etc/logrotate.d/coin-api

# 즉시 실행
logrotate -f /etc/logrotate.d/coin-api
```

### 4. 중요 로그 신호

#### 정상 동작
```
[Task abc123] Starting backtest: volume_zone_breakout
[Task abc123] Data loaded: 250 rows
[Task abc123] Processing BTC_KRW (1/2)
[Task abc123] Backtest completed successfully
```

#### 경고
```
[Task abc123] No data for BTC_KRW
[WARNING] Redis connection slow (>100ms)
[WARNING] Memory usage: 85% of maxmemory
```

#### 에러
```
[ERROR] Failed to load data for BTC_KRW: FileNotFoundError
[ERROR] Redis connection timeout
[CRITICAL] Out of memory
```

---

## 트러블슈팅

### 1. Redis 연결 실패

**증상**: `ConnectionError: redis connection error`

**진단**:
```bash
# Redis 서비스 상태 확인
redis-cli ping

# Docker 환경에서 Redis 재시작
docker-compose restart redis

# 포트 확인
netstat -tlnp | grep 6379
```

**해결**:
```bash
# Redis 서비스 시작
redis-server --daemonize yes

# 또는 Docker
docker-compose up -d redis
```

### 2. 워커가 작업을 처리하지 않음

**증상**: 비동기 작업이 `queued` 상태 유지

**진단**:
```bash
# 워커 상태 확인
docker-compose logs worker

# 작업 큐 상태
redis-cli LRANGE rq:queue:default 0 -1

# 워커 프로세스 확인
ps aux | grep "rq worker"
```

**해결**:
```bash
# 워커 재시작
docker-compose restart worker

# 또는
pkill -f "rq worker"
python -m rq worker -c backend.app.config --verbose
```

### 3. 메모리 부족

**증상**: `MemoryError`, 작업 실패

**진단**:
```bash
# 메모리 사용량 확인
free -h
docker stats

# Redis 메모리
redis-cli INFO memory | grep used
```

**해결**:
```bash
# 오래된 작업 정리
python scripts/cleanup_task_results.py

# Redis 메모리 제한 설정
redis-cli CONFIG SET maxmemory 2gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# 워커 수 감소 (메모리 사용량 감소)
docker-compose up -d --scale worker=2
```

### 4. 느린 응답

**증상**: API 응답 > 5초

**진단**:
```bash
# 로그에서 실행 시간 확인
grep "execution_time" backend/logs/*.log

# 데이터 크기 확인
du -sh data/

# 워커 큐 길이
redis-cli LLEN rq:queue:default
```

**해결**:
```bash
# 워커 수 증가
docker-compose up -d --scale worker=6

# 데이터 정리
python scripts/cleanup_task_results.py

# 파라미터 최적화 (기본값 사용)
```

### 5. 파일 저장 실패

**증상**: `Failed to save result file`, 결과 파일 없음

**진단**:
```bash
# 디스크 공간 확인
df -h data/

# 파일 권한 확인
ls -la data/tasks/

# 로그 확인
docker-compose logs backend | grep "save"
```

**해결**:
```bash
# 디스크 공간 확보
rm -rf data/tasks/old_*

# 정리 스크립트 실행
python scripts/cleanup_task_results.py --ttl-days 1

# 권한 수정
sudo chown -R nobody:nobody data/
sudo chmod 755 data/
```

---

## 재해 복구

### 1. 백업 전략

#### 주요 데이터
```bash
# 결과 파일 백업
tar -czf backup-results-$(date +%Y%m%d).tar.gz data/tasks/

# 설정 파일 백업
tar -czf backup-config-$(date +%Y%m%d).tar.gz .env docker-compose.yml

# 정기 백업 (cron)
0 2 * * * tar -czf /backup/coin-$(date +\%Y\%m\%d).tar.gz /data/tasks/
```

#### 입력 데이터
```bash
# Parquet 파일 백업 (매주)
0 3 * * 0 tar -czf /backup/data-$(date +\%Y\%m\%d).tar.gz /data/BTC_KRW/ /data/ETH_KRW/
```

### 2. 복구 절차

#### 부분 복구 (작업 결과만)
```bash
# 백업에서 복구
tar -xzf backup-results-20251104.tar.gz -C /

# Redis 상태 초기화 (필요시)
redis-cli FLUSHDB
```

#### 전체 복구 (데이터 + 설정)
```bash
# 1. 서비스 정지
docker-compose down

# 2. 데이터 복구
tar -xzf backup-data-20251104.tar.gz -C /
tar -xzf backup-config-20251104.tar.gz -C /path/to/project

# 3. 서비스 재시작
docker-compose up -d

# 4. 상태 확인
docker-compose logs -f
curl http://localhost:8000/health
```

### 3. 장애 격리

#### Redis 초기화 (주의: 진행 중인 작업 손실)
```bash
# 모든 데이터 삭제
redis-cli FLUSHALL

# 특정 키만 삭제
redis-cli DEL rq:queue:default
redis-cli KEYS "task:*" | xargs redis-cli DEL
```

#### 작업 큐 초기화
```bash
# 대기 중인 작업 모두 삭제
redis-cli DEL rq:queue:default

# 워커 재시작
docker-compose restart worker
```

---

## 점검표

### 주간 점검
- [ ] 디스크 공간 확인 (>20% 여유)
- [ ] 메모리 사용량 확인 (<70%)
- [ ] Redis 연결 상태 확인
- [ ] 워커 프로세스 상태 확인
- [ ] 에러 로그 검토

### 월간 점검
- [ ] 결과 파일 정리 실행
- [ ] 로그 로테이션 확인
- [ ] 성능 추세 분석
- [ ] 백업 복구 테스트
- [ ] 의존성 업데이트 검토

### 분기별 점검
- [ ] 전체 시스템 성능 평가
- [ ] 용량 계획 검토
- [ ] 보안 패치 적용
- [ ] 재해 복구 프로세스 검증

---

## 지원

### 로그 수집
```bash
# 전체 로그 수집 (문제 보고시)
tar -czf logs-$(date +%Y%m%d-%H%M%S).tar.gz \
  <(docker-compose logs backend) \
  <(docker-compose logs worker) \
  <(docker-compose logs redis)
```

### 연락처
- GitHub Issues: https://github.com/sunbangamen/coin_hts/issues
- 문제 보고: 위 로그 파일을 함께 제출
