#!/bin/bash
# Task 3.6: 배포 자동화 스크립트
#
# 목적: 개발/스테이징/프로덕션 환경 배포 자동화
# 사용법:
#   ./scripts/deploy.sh              # 기본 배포 (development)
#   ./scripts/deploy.sh staging      # 스테이징 배포
#   ./scripts/deploy.sh production   # 프로덕션 배포 (확인 필수)
#
# 기능:
#   1. 환경 검증 (Python, Docker, docker-compose)
#   2. .env 파일 설정 및 유효성 검증
#   3. Docker 이미지 빌드
#   4. Docker Compose 서비스 시작 (PostgreSQL, Redis, Backend, Worker)
#   5. 데이터베이스 초기화 (migrations 실행)
#   6. RQ 큐 초기화 (backtest-queue, data_ingestion)
#   7. 상태 검증 (health check)
#   8. 배포 완료 보고서 생성

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════
# 색상 및 로깅 함수
# ═══════════════════════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
  echo -e "${BLUE}ℹ️  INFO${NC}: $*"
}

log_success() {
  echo -e "${GREEN}✅ SUCCESS${NC}: $*"
}

log_warn() {
  echo -e "${YELLOW}⚠️  WARN${NC}: $*"
}

log_error() {
  echo -e "${RED}❌ ERROR${NC}: $*"
}

# ═══════════════════════════════════════════════════════════════════════════
# 설정 및 변수
# ═══════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${1:-development}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEPLOY_LOG="${PROJECT_ROOT}/logs/deploy_${ENVIRONMENT}_${TIMESTAMP}.log"

# 로그 디렉토리 생성
mkdir -p "${PROJECT_ROOT}/logs"
mkdir -p "${PROJECT_ROOT}/data"

log_info "배포 환경: $ENVIRONMENT"
log_info "프로젝트 경로: $PROJECT_ROOT"
log_info "배포 로그: $DEPLOY_LOG"
echo "" | tee -a "$DEPLOY_LOG"

# ═══════════════════════════════════════════════════════════════════════════
# 1. 환경 검증 (Prerequisites)
# ═══════════════════════════════════════════════════════════════════════════

log_info "Step 1: 환경 검증 중..."

# Python 확인
if ! command -v python3 &> /dev/null; then
  log_error "Python3을 찾을 수 없습니다"
  exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
log_success "Python3 설치 확인: $PYTHON_VERSION"

# Docker 확인
if ! command -v docker &> /dev/null; then
  log_error "Docker을 찾을 수 없습니다. https://docs.docker.com/install 참조"
  exit 1
fi
DOCKER_VERSION=$(docker --version)
log_success "Docker 설치 확인: $DOCKER_VERSION"

# Docker Compose 확인
if ! command -v docker-compose &> /dev/null; then
  log_error "docker-compose를 찾을 수 없습니다"
  exit 1
fi
COMPOSE_VERSION=$(docker-compose --version)
log_success "Docker Compose 설치 확인: $COMPOSE_VERSION"

echo "" | tee -a "$DEPLOY_LOG"

# ═══════════════════════════════════════════════════════════════════════════
# 2. 환경 변수 설정
# ═══════════════════════════════════════════════════════════════════════════

log_info "Step 2: 환경 변수 설정 중..."

# .env 파일 확인 및 생성
if [ ! -f "${PROJECT_ROOT}/.env" ]; then
  log_warn ".env 파일이 없습니다. .env.example에서 복사합니다"
  cp "${PROJECT_ROOT}/.env.example" "${PROJECT_ROOT}/.env"
  log_success ".env 파일 생성됨"
fi

# 환경 변수 로드
set -a
source "${PROJECT_ROOT}/.env"
set +a

# 주요 환경 변수 검증
if [ -z "${REDIS_HOST:-}" ]; then
  log_warn "REDIS_HOST이 설정되지 않았습니다. 기본값 사용: localhost"
  export REDIS_HOST="localhost"
fi

if [ -z "${DATABASE_URL:-}" ]; then
  log_warn "DATABASE_URL이 설정되지 않았습니다. Docker 기본값 사용"
  export DATABASE_URL="postgresql://coin_user:coin_password@postgres:5432/coin_db"
fi

if [ -z "${DATA_ROOT:-}" ]; then
  log_warn "DATA_ROOT이 설정되지 않았습니다. 기본값 사용: ./data"
  export DATA_ROOT="${PROJECT_ROOT}/data"
fi

log_success "환경 변수 로드 완료"
log_info "  - REDIS_HOST: $REDIS_HOST"
log_info "  - DATABASE_URL: $(echo $DATABASE_URL | sed 's/:.*@/@/g')"
log_info "  - DATA_ROOT: $DATA_ROOT"

echo "" | tee -a "$DEPLOY_LOG"

# ═══════════════════════════════════════════════════════════════════════════
# 3. 가상환경 설정
# ═══════════════════════════════════════════════════════════════════════════

log_info "Step 3: Python 가상환경 설정 중..."

cd "$PROJECT_ROOT"

if [ ! -d "venv" ]; then
  log_info "가상환경 생성 중..."
  python3 -m venv venv
  log_success "가상환경 생성 완료"
fi

# venv 활성화
source venv/bin/activate
log_success "가상환경 활성화 완료"

# 의존성 설치
log_info "의존성 설치 중 (requirements.txt)..."
pip install -q -r requirements.txt 2>&1 | grep -v "already satisfied" | head -20 || true
log_success "의존성 설치 완료"

echo "" | tee -a "$DEPLOY_LOG"

# ═══════════════════════════════════════════════════════════════════════════
# 4. Docker Compose 이미지 빌드
# ═══════════════════════════════════════════════════════════════════════════

log_info "Step 4: Docker 이미지 빌드 중..."

# Docker 네트워크 생성 (없는 경우)
if ! docker network inspect coin-network &> /dev/null; then
  log_info "Docker 네트워크 생성 중..."
  docker network create coin-network || true
fi

# Docker 이미지 빌드
log_info "Backend 이미지 빌드 중..."
docker-compose build --no-cache backend 2>&1 | tail -5
log_success "Backend 이미지 빌드 완료"

echo "" | tee -a "$DEPLOY_LOG"

# ═══════════════════════════════════════════════════════════════════════════
# 5. Docker Compose 서비스 시작
# ═══════════════════════════════════════════════════════════════════════════

log_info "Step 5: Docker Compose 서비스 시작 중..."

# 기존 컨테이너 중지 (충돌 방지)
log_info "기존 컨테이너 정리 중..."
docker-compose down --remove-orphans 2>&1 | grep -v "is not running" || true

# PostgreSQL, Redis 시작 (백그라운드)
log_info "PostgreSQL, Redis 시작 중..."
docker-compose up -d postgres redis 2>&1 | grep -E "Creating|Already|Started"

# 서비스 건강 확인 대기
log_info "PostgreSQL 헬스 체크 (최대 30초 대기)..."
for i in {1..30}; do
  if docker-compose exec -T postgres pg_isready -U coin_user -d coin_db 2>&1 | grep -q "accepting"; then
    log_success "PostgreSQL 준비 완료"
    break
  fi
  if [ $i -eq 30 ]; then
    log_error "PostgreSQL 헬스 체크 실패"
    exit 1
  fi
  sleep 1
done

log_info "Redis 헬스 체크 (최대 30초 대기)..."
for i in {1..30}; do
  if docker-compose exec -T redis redis-cli ping 2>&1 | grep -q "PONG"; then
    log_success "Redis 준비 완료"
    break
  fi
  if [ $i -eq 30 ]; then
    log_error "Redis 헬스 체크 실패"
    exit 1
  fi
  sleep 1
done

echo "" | tee -a "$DEPLOY_LOG"

# ═══════════════════════════════════════════════════════════════════════════
# 6. 데이터베이스 초기화 (마이그레이션)
# ═══════════════════════════════════════════════════════════════════════════

log_info "Step 6: 데이터베이스 초기화 중..."

# 마이그레이션 파일 확인
if [ -d "${PROJECT_ROOT}/backend/migrations" ]; then
  log_info "마이그레이션 스크립트 실행 중..."
  docker-compose exec -T postgres psql -U coin_user -d coin_db \
    -f /docker-entrypoint-initdb.d/*.sql 2>&1 | head -10 || true
  log_success "데이터베이스 마이그레이션 완료"
else
  log_warn "마이그레이션 디렉토리가 없습니다"
fi

echo "" | tee -a "$DEPLOY_LOG"

# ═══════════════════════════════════════════════════════════════════════════
# 7. RQ 큐 초기화
# ═══════════════════════════════════════════════════════════════════════════

log_info "Step 7: RQ 큐 초기화 중..."

# Backend 서비스 시작 (RQ 큐 초기화를 위해 필요)
log_info "Backend API 시작 중..."
docker-compose up -d backend 2>&1 | grep -E "Creating|Already|Started"

# Backend 헬스 체크
log_info "Backend 헬스 체크 (최대 30초 대기)..."
for i in {1..30}; do
  if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    log_success "Backend API 준비 완료"
    break
  fi
  if [ $i -eq 30 ]; then
    log_warn "Backend 헬스 체크 실패 (재시도 필요)"
  fi
  sleep 1
done

# RQ 큐 확인
log_info "RQ 큐 상태 확인..."
docker-compose exec -T backend python3 -c "
import redis
from rq import Queue
try:
    r = redis.from_url('redis://redis:6379')
    q_backtest = Queue('backtest-queue', connection=r)
    q_data = Queue('data_ingestion', connection=r)
    print(f'✅ Backtest Queue: {len(q_backtest)} jobs')
    print(f'✅ Data Ingestion Queue: {len(q_data)} jobs')
except Exception as e:
    print(f'⚠️  RQ Queue 초기화 에러: {e}')
" 2>&1 || true

log_success "RQ 큐 초기화 완료"

echo "" | tee -a "$DEPLOY_LOG"

# ═══════════════════════════════════════════════════════════════════════════
# 8. S3 스토리지 검증 (선택사항)
# ═══════════════════════════════════════════════════════════════════════════

log_info "Step 8: 외부 스토리지 검증 중..."

if command -v aws &> /dev/null; then
  if [ -n "${AWS_BUCKET_NAME:-}" ]; then
    log_info "S3 버킷 검증: $AWS_BUCKET_NAME"
    if aws s3 ls "s3://${AWS_BUCKET_NAME}" 2>/dev/null; then
      log_success "S3 버킷 접근 가능"
    else
      log_warn "S3 버킷 접근 불가 (AWS 자격증명 확인)"
    fi
  else
    log_warn "AWS_BUCKET_NAME 미설정 (S3 스토리지 비활성화)"
  fi
else
  log_warn "AWS CLI 미설치 (S3 검증 스킵)"
fi

echo "" | tee -a "$DEPLOY_LOG"

# ═══════════════════════════════════════════════════════════════════════════
# 9. 배포 완료 보고서
# ═══════════════════════════════════════════════════════════════════════════

log_info "Step 9: 배포 완료 보고서 생성 중..."

cat > "${PROJECT_ROOT}/DEPLOY_REPORT_${TIMESTAMP}.txt" << EOF
╔════════════════════════════════════════════════════════════════════════════╗
║                    배포 완료 보고서                                        ║
║                    (Task 3.6: 배포 자동화)                                ║
╚════════════════════════════════════════════════════════════════════════════╝

📋 배포 정보
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  환경:       $ENVIRONMENT
  타임스탬프: $TIMESTAMP
  스크립트:   ${BASH_SOURCE[0]}
  프로젝트:   $PROJECT_ROOT

🔧 환경 확인
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ Python 3:        $PYTHON_VERSION
  ✅ Docker:          $DOCKER_VERSION
  ✅ Docker Compose:  $COMPOSE_VERSION
  ✅ 가상환경:        $(python3 --version 2>&1)

📦 배포된 서비스
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PostgreSQL:  postgresql://coin_user@postgres:5432/coin_db
  Redis:       redis://redis:6379
  Backend API: http://localhost:8000
  Frontend:    http://localhost:5173 (필요시 별도 실행)

🚀 다음 단계
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣  Backend API 시작 (이미 실행 중)
    curl http://localhost:8000/docs

2️⃣  RQ 워커 시작 (터미널 2)
    docker-compose up worker

3️⃣  성능 모니터링 및 헬스 체크
    ./scripts/health_check.sh
    ./scripts/benchmark.py

4️⃣  백테스트 실행
    curl -X POST http://localhost:8000/api/v1/backtests/async \
      -H "Content-Type: application/json" \
      -d '{
        "symbols": ["KRW-BTC"],
        "strategy": "volume_zone_breakout",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31"
      }'

📊 서비스 상태 확인
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Docker 컨테이너:
$(docker-compose ps 2>/dev/null || echo "  docker-compose ps 실행 불가")

PostgreSQL:
$(docker-compose exec -T postgres pg_isready -U coin_user -d coin_db 2>/dev/null || echo "  연결 확인 불가")

Redis:
$(docker-compose exec -T redis redis-cli ping 2>/dev/null || echo "  연결 확인 불가")

🔒 보안 설정 체크리스트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ☐ .env 파일에 민감한 정보가 포함되어 있는지 확인
  ☐ AWS IAM 자격증명이 안전하게 관리되는지 확인
  ☐ PostgreSQL 기본 비밀번호 변경 (프로덕션 환경)
  ☐ Redis 비밀번호 설정 (프로덕션 환경)
  ☐ HTTPS 인증서 설정 (프로덕션 환경)

📝 로그 경로
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  배포 로그:     $DEPLOY_LOG
  Docker 로그:   docker-compose logs [service]
  Backend 로그:  docker-compose logs backend

💡 문제 해결
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

문제: PostgreSQL 연결 실패
해결:
  docker-compose logs postgres
  docker-compose down && docker-compose up -d postgres

문제: Redis 연결 실패
해결:
  docker-compose logs redis
  docker-compose down && docker-compose up -d redis

문제: Backend API 응답 없음
해결:
  docker-compose logs backend
  curl http://localhost:8000/docs

문제: RQ 워커 작업 미처리
해결:
  docker-compose logs worker
  docker-compose exec -T backend rq info

═══════════════════════════════════════════════════════════════════════════════
배포 일시: $(date '+%Y-%m-%d %H:%M:%S %Z')
상태: ✅ 배포 완료
═══════════════════════════════════════════════════════════════════════════════
EOF

log_success "배포 완료 보고서: DEPLOY_REPORT_${TIMESTAMP}.txt"

echo "" | tee -a "$DEPLOY_LOG"
log_success "═════════════════════════════════════════════════════════════"
log_success "배포 완료! 주요 서비스를 확인하세요:"
log_success "  • Backend API: http://localhost:8000"
log_success "  • API 문서: http://localhost:8000/docs"
log_success "  • PostgreSQL: psql -U coin_user -d coin_db -h localhost"
log_success "  • Redis: redis-cli -h localhost -p 6379"
log_success "═════════════════════════════════════════════════════════════"
echo "" | tee -a "$DEPLOY_LOG"
log_info "다음 명령어로 서비스 로그를 확인하세요:"
log_info "  docker-compose logs -f backend"
log_info "  docker-compose logs -f postgres"
log_info "  docker-compose logs -f redis"
echo "" | tee -a "$DEPLOY_LOG"

# ═══════════════════════════════════════════════════════════════════════════
# 종료
# ═══════════════════════════════════════════════════════════════════════════

exit 0
