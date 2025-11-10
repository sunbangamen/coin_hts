# Phase 2 → Phase 3 마이그레이션 체크리스트

Phase 2 (동기 백테스트)에서 Phase 3 (비동기 큐)로 업그레이드하기 위한 단계별 가이드입니다.

---

## 목차

1. [사전 준비](#사전-준비)
2. [코드 업그레이드](#코드-업그레이드)
3. [환경 설정](#환경-설정)
4. [데이터 마이그레이션](#데이터-마이그레이션)
5. [검증](#검증)
6. [배포](#배포)
7. [롤백](#롤백-계획)

---

## 사전 준비

### 요구사항 확인

- [ ] Git 저장소 최신 커밋 확인: `git log --oneline -1`
- [ ] 백업 생성:
  ```bash
  tar -czf backup-phase2-$(date +%Y%m%d).tar.gz .
  ```
- [ ] 현재 버전 확인:
  ```bash
  git describe --tags  # Phase 2 태그 확인
  ```

### 현재 상태 점검

- [ ] Phase 2 테스트 모두 통과:
  ```bash
  pytest tests/test_api.py tests/test_strategies.py -v
  ```
- [ ] 모든 동기 API 정상 작동:
  ```bash
  curl http://localhost:8000/health
  curl http://localhost:8000/api/strategies
  ```
- [ ] 디스크 공간 확인 (최소 5GB):
  ```bash
  df -h data/
  ```

### 팀 공지

- [ ] 개발팀에 업그레이드 계획 공지
- [ ] 클라이언트에 API 변경 사항 공지
- [ ] 운영팀에 배포 일정 공지
- [ ] 다운타임 예상 (약 10-15분) 안내

---

## 코드 업그레이드

### Step 1: 최신 코드 적용

```bash
# 1. 최신 코드 다운로드
git fetch origin
git checkout coin-15  # Phase 3 브랜치

# 2. Phase 3 변경사항 확인
git log --oneline phase2..phase3 | head -20

# 3. 의존성 업데이트
pip install -r requirements.txt  # redis, rq 추가됨

# 4. 변경사항 검증
git diff phase2..phase3 --stat
```

- [ ] 새로운 Python 패키지 설치됨 (redis, rq)
- [ ] backend/app/ 디렉토리에 새 파일 추가됨:
  - [ ] `config.py`
  - [ ] `task_manager.py`
  - [ ] `jobs.py`
  - [ ] `result_manager.py`

### Step 2: API 변경사항 이해

**기존 엔드포인트 (변경 없음)**:
- ✅ `POST /api/backtests/run` (동기, 기존 동작 유지)
- ✅ `GET /api/backtests/{run_id}` (기존 동작 유지)
- ✅ `GET /api/strategies` (기존 동작 유지)

**신규 엔드포인트**:
- ✨ `POST /api/backtests/run-async` (비동기 실행)
- ✨ `GET /api/backtests/status/{task_id}` (상태 폴링)

### Step 3: 클라이언트 업데이트 (선택사항)

```javascript
// 기존 동기 모드 (계속 사용 가능)
async function runBacktestSync() {
  const response = await fetch('/api/backtests/run', {
    method: 'POST',
    body: JSON.stringify({ /* ... */ })
  });
  const result = await response.json();
  // 즉시 결과 반환 (최대 1시간 소요)
  return result;
}

// 신규 비동기 모드 (권장)
async function runBacktestAsync() {
  // 1단계: 작업 시작
  const response = await fetch('/api/backtests/run-async', {
    method: 'POST',
    body: JSON.stringify({ /* ... */ })
  });
  const { task_id } = await response.json();

  // 2단계: 진행률 폴링
  while (true) {
    const statusResponse = await fetch(`/api/backtests/status/${task_id}`);
    const { status, progress, result } = await statusResponse.json();

    console.log(`진행률: ${progress * 100}%`);

    if (status === 'completed') {
      return result;
    } else if (status === 'failed') {
      throw new Error(`작업 실패: ${error}`);
    }

    // 0.5초마다 체크
    await new Promise(r => setTimeout(r, 500));
  }
}
```

- [ ] 클라이언트 라이브러리 업데이트 (필요시)
- [ ] 문서 업데이트
- [ ] 테스트 케이스 추가

---

## 환경 설정

### Step 1: 환경변수 설정

```bash
# 1. .env 파일 생성
cp .env.sample .env

# 2. .env 파일 내용 확인
cat .env
```

필수 변수:
```bash
# .env
DATA_ROOT=/data
REDIS_HOST=localhost  # 또는 redis (Docker)
REDIS_PORT=6379
REDIS_DB=0
ENVIRONMENT=development  # 또는 production
TASK_RESULT_TTL_DAYS=7
```

- [ ] `DATA_ROOT` 디렉토리 존재 및 쓰기 권한 확인
- [ ] `REDIS_HOST`, `REDIS_PORT` 설정 확인
- [ ] `ENVIRONMENT` 환경에 맞게 설정
- [ ] `TASK_RESULT_TTL_DAYS` 기본값 7일 확인

### Step 2: Docker 환경 준비

```bash
# 1. Docker 이미지 빌드
docker-compose build

# 2. Redis 데이터 디렉토리 생성
mkdir -p data/redis
mkdir -p data/tasks
mkdir -p data/results
```

- [ ] Dockerfile 변경사항 확인 (변경 없음)
- [ ] docker-compose.yml 변경사항 확인:
  - [ ] Redis 서비스 추가
  - [ ] Worker 서비스 추가
  - [ ] Backend 의존성 추가
- [ ] 네트워크 설정 확인

### Step 3: Redis 설치

#### Docker 사용 (권장)
```bash
# docker-compose.yml에 포함됨
docker-compose up -d redis

# 연결 확인
redis-cli ping
```

#### 로컬 설치
```bash
# macOS
brew install redis
redis-server

# Ubuntu/Debian
sudo apt-get install redis-server
sudo service redis-server start

# 연결 확인
redis-cli ping  # PONG 응답
```

- [ ] Redis 서비스 실행 중
- [ ] `redis-cli ping` 응답 확인 (PONG)
- [ ] 메모리 설정 확인: `redis-cli INFO memory`

---

## 데이터 마이그레이션

### Step 1: 기존 결과 백업

```bash
# 1. Phase 2 결과 파일 백업
mkdir -p backup
tar -czf backup/results-phase2-$(date +%Y%m%d).tar.gz data/results/

# 2. 백업 확인
ls -lh backup/results-*.tar.gz
```

- [ ] `data/results/` 디렉토리 백업됨
- [ ] 백업 파일 크기 확인 (0이 아님)

### Step 2: Phase 3 디렉토리 구조 생성

```bash
# 새로운 디렉토리 생성
mkdir -p data/tasks
mkdir -p data/results

# 기존 결과 디렉토리 유지 (사용 가능)
# data/results/{run_id}.json (Phase 2)

# 새로운 구조 확인
tree data/
# data/
# ├── tasks/                    # (신규)
# │   └── <task_id>/
# │       ├── manifest.json
# │       └── result.json
# └── results/                  # (기존)
#     └── {run_id}.json
```

- [ ] `data/tasks/` 디렉토리 생성됨
- [ ] 기존 `data/results/` 디렉토리 유지됨
- [ ] 파일 권한 확인: `755`

### Step 3: 호환성 확인

```bash
# Phase 2 동기 API 여전히 작동하는지 확인
# (기존 결과는 /api/backtests/{run_id}로 조회)

curl -X POST http://localhost:8000/api/backtests/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "volume_zone_breakout",
    "symbols": ["BTC_KRW"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }'

# 응답 확인
# - run_id 받음
# - data/results/{run_id}.json 생성됨
```

- [ ] 동기 API 정상 작동
- [ ] 결과 파일 생성됨 (`data/results/`)

### Step 3: Phase 3 신규 기능 설정

#### AWS S3 설정

```bash
# 1. S3 버킷 생성
aws s3 mb s3://backtest-bucket --region us-east-1

# 2. 버킷 버저닝 활성화 (선택사항)
aws s3api put-bucket-versioning \
  --bucket backtest-bucket \
  --versioning-configuration Status=Enabled

# 3. Lifecycle 정책 설정 (30일 후 자동 삭제)
aws s3api put-bucket-lifecycle-configuration \
  --bucket backtest-bucket \
  --lifecycle-configuration file://lifecycle.json

# lifecycle.json 내용:
# {
#   "Rules": [
#     {
#       "Prefix": "backtests/",
#       "Expiration": {"Days": 30},
#       "Status": "Enabled"
#     }
#   ]
# }
```

- [ ] S3 버킷 생성 완료
- [ ] IAM 최소 권한 정책 적용
- [ ] S3 버킷 정책 설정 확인
- [ ] 버킷 버저닝 활성화 (선택사항)

#### 로깅/알림 환경 변수 설정

```bash
# 1. .env 파일에 추가
cat >> .env << 'EOF'

# Slack 알림
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_ENABLED=true

# Email 알림
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_ADDR=ops@company.com
EMAIL_ENABLED=true

# AWS S3
AWS_BUCKET_NAME=backtest-bucket
AWS_REGION=us-east-1
EOF

# 2. 환경 변수 검증
echo "SLACK_WEBHOOK_URL: ${SLACK_WEBHOOK_URL:-'NOT SET'}"
echo "SMTP_HOST: ${SMTP_HOST:-'NOT SET'}"
echo "AWS_BUCKET_NAME: ${AWS_BUCKET_NAME:-'NOT SET'}"
```

- [ ] Slack Webhook URL 설정
- [ ] SMTP 설정 확인 (Gmail 앱 비밀번호 사용)
- [ ] AWS S3 환경 변수 설정
- [ ] 환경 변수 검증 완료

#### 백업 스케줄러 활성화

```bash
# 1. 자동 백업 스케줄러 시작
python -c "
from backend.app.backup_scheduler import get_backup_scheduler
scheduler = get_backup_scheduler()
scheduler.start()
print('백업 스케줄러 시작됨')
"

# 2. 스케줄 확인
python -c "
from backend.app.backup_scheduler import get_backup_scheduler
scheduler = get_backup_scheduler()
status = scheduler.get_status()
print(f'실행 중: {status[\"is_running\"]}')
print(f'예약된 작업: {status[\"jobs_count\"]}')
"
```

- [ ] 백업 스케줄러 시작 확인
- [ ] 예약된 작업 목록 확인
- [ ] 백업 디렉토리 생성 확인 (`${DATA_ROOT}/backups/`)

---

## 검증

### Step 1: 비동기 API 테스트

```bash
# 1. 비동기 백테스트 실행
curl -X POST http://localhost:8000/api/backtests/run-async \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "volume_zone_breakout",
    "symbols": ["BTC_KRW"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }'

# 응답: 202 Accepted
# {
#   "task_id": "abc123-def456",
#   "status": "queued",
#   "created_at": "2025-11-04T10:30:45Z"
# }

TASK_ID="abc123-def456"

# 2. 상태 확인 (여러 번)
curl http://localhost:8000/api/backtests/status/$TASK_ID

# 응답: status가 변함
# queued → running (progress 증가) → completed
```

- [ ] 202 Accepted 응답 받음
- [ ] `task_id` (UUID) 반환됨
- [ ] 상태 폴링으로 진행률 확인됨
- [ ] 완료 후 결과 확인됨
- [ ] 결과 파일 생성됨 (`data/tasks/{task_id}/`)

### Step 2: 포지션 관리 API 테스트

```bash
# 1. 포지션 진입
curl -X POST http://localhost:8000/api/positions/enter \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC_KRW",
    "quantity": 1.0,
    "entry_price": 50000,
    "side": "BUY"
  }'

# 2. 오픈 포지션 조회
curl http://localhost:8000/api/positions/open

# 3. 포지션 요약 조회
curl http://localhost:8000/api/positions/summary
```

- [ ] 포지션 진입 성공 (200 OK)
- [ ] 손익 계산 정확함 (수수료 0.1%, 슬리피지 0.02% 반영)
- [ ] 오픈 포지션 조회 가능

### Step 3: S3 스토리지 테스트

```bash
# 1. S3 업로드 테스트
python << 'EOF'
import asyncio
from backend.app.storage.s3_provider import S3StorageProvider

async def test():
    provider = S3StorageProvider(
        bucket_name="backtest-bucket",
        region="us-east-1"
    )

    # 테스트 파일 생성
    with open("/tmp/test.json", "w") as f:
        f.write('{"test": "data"}')

    # 업로드
    result = await provider.upload(
        file_path="/tmp/test.json",
        remote_path="test/test.json",
        metadata={"test": "true"}
    )
    print(f"Upload: {result['success']} - ETag: {result['etag']}")

    # 무결성 검증
    integrity = await provider.verify_integrity(
        remote_path="test/test.json",
        local_etag=result['etag']
    )
    print(f"Integrity: {integrity['matches']}")

asyncio.run(test())
EOF
```

- [ ] S3 업로드 성공
- [ ] ETag 기반 무결성 검증 성공
- [ ] 다운로드 가능

### Step 4: 알림 시스템 테스트

```bash
# 1. Slack 알림 테스트
python << 'EOF'
import asyncio
from backend.app.notifications import SlackNotifier

async def test():
    notifier = SlackNotifier()
    result = await notifier.send(
        title="테스트 알림",
        message="Phase 3 마이그레이션 테스트입니다.",
        level="INFO"
    )
    print(f"Slack Alert: {result}")

asyncio.run(test())
EOF
```

- [ ] Slack 알림 전송 성공
- [ ] Email 알림 전송 가능
- [ ] 알림 내용 확인됨

### Step 5: 백업 시스템 테스트

```bash
# 1. 수동 백업 실행
./scripts/backup.sh all

# 2. 백업 파일 확인
ls -lh backups/postgresql/
ls -lh backups/redis/
ls -lh backups/results/

# 3. 백업 통계 확인
./scripts/backup.sh stats
```

- [ ] PostgreSQL 백업 생성됨
- [ ] Redis 백업 생성됨
- [ ] 결과 백업 생성됨
- [ ] 파일 무결성 검증 (md5sum) 성공

### Step 6: 회귀 테스트

```bash
# 1. 기존 테스트 모두 통과 확인
pytest tests/ -v

# 2. 특정 테스트 실행
pytest tests/test_position_manager.py -v
pytest tests/test_s3_storage.py -v
pytest tests/test_async_api.py -v
```

**기대 결과**: 218/218 테스트 통과 ✅

- [ ] Phase 2 테스트 모두 통과
- [ ] Phase 3 테스트 (포지션, S3, 비동기) 모두 통과
- [ ] 토탈 테스트 커버리지 > 80%

### Step 3: 성능 기준선 검증

```bash
# 동기 모드 성능 (기준선 유지: 1초 이내)
time curl -X POST http://localhost:8000/api/backtests/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "volume_zone_breakout",
    "symbols": ["BTC_KRW"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }'

# 비동기 모드 성능 (즉시 반환)
time curl -X POST http://localhost:8000/api/backtests/run-async \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "volume_zone_breakout",
    "symbols": ["BTC_KRW"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }'

# 기대: < 100ms (202 Accepted 즉시 반환)
```

- [ ] 동기 API: 1초 이내 ✅
- [ ] 비동기 API: 100ms 이내 ✅
- [ ] 메모리 누수 없음 (Redis TTL 작동)

### Step 4: 스트레스 테스트

```bash
# 동시 작업 10개 테스트
for i in {1..10}; do
  curl -X POST http://localhost:8000/api/backtests/run-async \
    -H "Content-Type: application/json" \
    -d '{"strategy":"volume_zone_breakout","symbols":["BTC_KRW"],"start_date":"2024-01-01","end_date":"2024-12-31"}' &
done

# 모든 작업 완료 대기
wait

# Redis 메모리 확인
redis-cli INFO memory | grep used_memory:

# 기대: 메모리 사용량 선형 증가 후 TTL로 감소
```

- [ ] 동시 10개 작업 모두 성공
- [ ] 메모리 누수 없음
- [ ] 디스크 공간 충분함

---

## 배포

### Step 1: 배포 전 점검

```bash
# 1. 변경사항 최종 확인
git status  # clean 상태

# 2. 모든 테스트 통과
pytest tests/ -v --tb=short

# 3. 백업 생성
tar -czf backup-before-migration-$(date +%Y%m%d).tar.gz .
```

- [ ] Git 상태: clean
- [ ] 모든 테스트: 통과
- [ ] 백업: 생성됨

### Step 2: 서비스 배포

#### Docker 환경

```bash
# 1. 기존 서비스 중지
docker-compose down

# 2. 이미지 빌드
docker-compose build

# 3. 새 서비스 시작 (Redis + Backend)
docker-compose up -d

# 4. 상태 확인
docker-compose ps

# 5. 워커 시작 (별도)
docker-compose --profile worker up -d worker

# 6. 로그 확인
docker-compose logs -f --tail=20
```

#### 로컬 환경

```bash
# 1. 기존 서비스 중지
pkill -f uvicorn
pkill -f "rq worker"
redis-cli shutdown

# 2. 새 서비스 시작
redis-server &
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 &
python -m rq worker -c backend.app.config --verbose &

# 3. 상태 확인
ps aux | grep -E "redis|uvicorn|rq"
```

- [ ] Redis 서비스 실행 중
- [ ] Backend 서비스 실행 중
- [ ] Worker 서비스 실행 중

### Step 3: 배포 후 검증

```bash
# 1. 헬스체크
curl http://localhost:8000/health

# 2. 동기 API 테스트
curl -X POST http://localhost:8000/api/backtests/run \
  -H "Content-Type: application/json" \
  -d '{...}'

# 3. 비동기 API 테스트
curl -X POST http://localhost:8000/api/backtests/run-async \
  -H "Content-Type: application/json" \
  -d '{...}'

# 4. 결과 파일 확인
ls -la data/tasks/
ls -la data/results/
```

- [ ] 헬스체크: 200 OK
- [ ] 동기 API: 정상 작동
- [ ] 비동기 API: 정상 작동
- [ ] 결과 파일: 생성됨

---

## 롤백 계획

문제 발생시 즉시 Phase 2로 롤백 가능합니다.

### 즉시 롤백

```bash
# 1. Phase 3 서비스 중지
docker-compose down
# 또는
pkill -f uvicorn && pkill -f "rq worker"

# 2. Phase 2 코드로 전환
git checkout phase2

# 3. Phase 2 서비스 시작
docker-compose up -d backend
# 또는
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# 4. 기존 동기 API로 복원됨
curl http://localhost:8000/health
```

- [ ] 롤백 완료
- [ ] 기존 동기 API 정상 작동
- [ ] 비동기 API 비활성화됨

### 데이터 복구

```bash
# 기존 결과 자동으로 복구됨 (data/results/ 유지)
curl http://localhost:8000/api/backtests/{old_run_id}

# 새로운 Phase 3 결과는 사용 불가
# data/tasks/ 백업에서 수동 복구 필요
tar -xzf backup/results-phase2-*.tar.gz
```

- [ ] 기존 Phase 2 결과: 자동 복구됨
- [ ] Phase 3 결과: 별도 백업 필요

---

## 마이그레이션 완료 확인

모든 항목이 체크되었으면 마이그레이션 완료입니다.

```bash
# 최종 확인
curl http://localhost:8000/
# 응답에 신규 엔드포인트 포함되어야 함:
# - POST /api/backtests/run-async
# - GET /api/backtests/status/{task_id}

# 버전 정보
git log --oneline -1  # Phase 3 커밋
docker-compose version
```

---

---

## 보안 검증

```bash
# 1. AWS IAM 최소 권한 확인
aws iam get-role-policy \
  --role-name backtest-service \
  --policy-name s3-access

# 2. Redis AUTH 설정 확인 (프로덕션)
redis-cli CONFIG GET requirepass
# 반환: "requirepass" "<password>"

# 3. Webhook URL 보안 확인
# ✅ 환경 변수로만 전달
# ✅ .env 파일은 .gitignore에 포함
# ✅ 깃허브 시크릿으로 보호

# 4. 환경 변수 마스킹 확인
env | grep -E "SLACK|SMTP|AWS_SECRET" | head -0  # 출력 안 됨
```

- [ ] AWS IAM 최소 권한 정책 설정
- [ ] Redis AUTH 활성화 (프로덕션)
- [ ] Webhook URL 환경 변수화
- [ ] 중요 정보 .gitignore에 포함

---

## 다음 단계

- [ ] 팀에 마이그레이션 완료 공지
- [ ] 클라이언트에 새로운 API 사용법 안내
- [ ] Slack 채널에 알림 설정
- [ ] 정기 백업 스케줄 설정 (cron)
- [ ] 모니터링 대시보드 구성 (헬스 체크, 벤치마크)
- [ ] 운영 플레이북 검토 (docs/coin/mvp/ASYNC_QUEUE_OPERATIONS.md)

---

## 지원

마이그레이션 중 문제 발생시:
1. OPERATIONS.md의 "트러블슈팅" 섹션 참고
2. 로그 수집: `docker-compose logs > migration.log`
3. GitHub Issues에 보고: https://github.com/sunbangamen/coin_hts/issues
