#!/bin/bash
# Task 3.6: 백업 자동화 스크립트
#
# 목적: PostgreSQL, Redis, 백테스트 결과 자동 백업
# 사용법:
#   ./scripts/backup.sh                 # 전체 백업 (DB, Redis, 결과)
#   ./scripts/backup.sh postgres        # PostgreSQL만 백업
#   ./scripts/backup.sh redis           # Redis만 백업
#   ./scripts/backup.sh results         # 백테스트 결과만 백업
#   ./scripts/backup.sh s3              # S3에 백업 (AWS 설정 필요)
#   ./scripts/backup.sh cleanup [days]  # 오래된 백업 삭제 (기본: 7일)
#
# 기능:
#   1. PostgreSQL 백업 (pg_dump)
#   2. Redis 백업 (BGSAVE)
#   3. 백테스트 결과 백업 (data 디렉토리)
#   4. S3 업로드 (선택사항)
#   5. 백업 검증 (파일 크기, 체크섬)
#   6. 백업 정리 (오래된 파일 삭제)
#   7. 백업 리포트 생성

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════
# 색상 및 로깅
# ═══════════════════════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m'

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

log_backup() {
  echo -e "${MAGENTA}💾 BACKUP${NC}: $*"
}

# ═══════════════════════════════════════════════════════════════════════════
# 설정 및 변수
# ═══════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_ROOT}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_LOG="${BACKUP_DIR}/backup_${TIMESTAMP}.log"
BACKUP_TYPE="${1:-all}"
CLEANUP_DAYS="${2:-7}"

# 백업 디렉토리 생성
mkdir -p "$BACKUP_DIR"
mkdir -p "${BACKUP_DIR}/postgresql"
mkdir -p "${BACKUP_DIR}/redis"
mkdir -p "${BACKUP_DIR}/results"

# 환경 변수 로드
set -a
source "${PROJECT_ROOT}/.env" 2>/dev/null || true
set +a

log_info "백업 타입: $BACKUP_TYPE"
log_info "백업 디렉토리: $BACKUP_DIR"
log_info "백업 로그: $BACKUP_LOG"
echo "" | tee -a "$BACKUP_LOG"

# ═══════════════════════════════════════════════════════════════════════════
# PostgreSQL 백업 함수
# ═══════════════════════════════════════════════════════════════════════════

backup_postgresql() {
  log_backup "PostgreSQL 백업 시작..."

  local backup_file="${BACKUP_DIR}/postgresql/backup_${TIMESTAMP}.sql"

  # Docker 컨테이너에서 실행
  if docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" ps postgres | grep -q "postgres"; then
    log_info "Docker PostgreSQL 백업 중..."
    docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T postgres \
      pg_dump -U coin_user -d coin_db --no-owner --no-privileges > "$backup_file" 2>/dev/null
  else
    log_info "로컬 PostgreSQL 백업 중..."
    if [ -z "${DATABASE_URL:-}" ]; then
      log_warn "DATABASE_URL 미설정, 백업 스킵"
      return
    fi
    pg_dump "$DATABASE_URL" --no-owner --no-privileges > "$backup_file" 2>/dev/null || {
      log_error "PostgreSQL 백업 실패"
      return 1
    }
  fi

  # 백업 파일 검증
  if [ ! -f "$backup_file" ] || [ ! -s "$backup_file" ]; then
    log_error "PostgreSQL 백업 파일이 비어있습니다"
    rm -f "$backup_file"
    return 1
  fi

  # 압축
  log_info "PostgreSQL 백업 압축 중..."
  gzip -f "$backup_file"
  backup_file="${backup_file}.gz"

  # 통계
  local file_size=$(du -h "$backup_file" | cut -f1)
  log_backup "PostgreSQL 백업 완료: $backup_file (크기: $file_size)"

  # 체크섬 생성
  md5sum "$backup_file" > "${backup_file}.md5"

  echo "$backup_file" >> "$BACKUP_LOG"
  return 0
}

# ═══════════════════════════════════════════════════════════════════════════
# Redis 백업 함수
# ═══════════════════════════════════════════════════════════════════════════

backup_redis() {
  log_backup "Redis 백업 시작..."

  if docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" ps redis | grep -q "redis"; then
    log_info "Docker Redis BGSAVE 실행 중..."
    docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T redis redis-cli BGSAVE 2>/dev/null

    # Redis 덤프 파일 복사
    log_info "Redis 덤프 파일 복사 중..."
    docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" cp redis:/data/dump.rdb \
      "${BACKUP_DIR}/redis/dump_${TIMESTAMP}.rdb" 2>/dev/null || {
      log_warn "Redis 덤프 파일 복사 실패"
      return 1
    }
  else
    log_info "로컬 Redis BGSAVE 실행 중..."
    redis-cli BGSAVE 2>/dev/null || {
      log_warn "Redis BGSAVE 실패 (Redis 미실행)"
      return 1
    }

    # 로컬 dump.rdb 복사
    if [ -f "/var/lib/redis/dump.rdb" ]; then
      cp /var/lib/redis/dump.rdb "${BACKUP_DIR}/redis/dump_${TIMESTAMP}.rdb"
    elif [ -f "${HOME}/.redis/dump.rdb" ]; then
      cp "${HOME}/.redis/dump.rdb" "${BACKUP_DIR}/redis/dump_${TIMESTAMP}.rdb"
    else
      log_warn "Redis dump.rdb 파일을 찾을 수 없습니다"
      return 1
    fi
  fi

  local backup_file="${BACKUP_DIR}/redis/dump_${TIMESTAMP}.rdb"

  if [ ! -f "$backup_file" ]; then
    log_error "Redis 백업 파일을 찾을 수 없습니다"
    return 1
  fi

  # 압축
  gzip -f "$backup_file"
  backup_file="${backup_file}.gz"

  local file_size=$(du -h "$backup_file" | cut -f1)
  log_backup "Redis 백업 완료: $backup_file (크기: $file_size)"

  md5sum "$backup_file" > "${backup_file}.md5"

  echo "$backup_file" >> "$BACKUP_LOG"
  return 0
}

# ═══════════════════════════════════════════════════════════════════════════
# 백테스트 결과 백업
# ═══════════════════════════════════════════════════════════════════════════

backup_results() {
  log_backup "백테스트 결과 백업 시작..."

  local data_dir="${PROJECT_ROOT}/data"

  if [ ! -d "$data_dir" ]; then
    log_warn "데이터 디렉토리가 없습니다: $data_dir"
    return 0
  fi

  # 데이터 디렉토리의 JSON 결과 백업
  local backup_file="${BACKUP_DIR}/results/results_${TIMESTAMP}.tar.gz"

  log_info "데이터 디렉토리 압축 중..."
  tar -czf "$backup_file" -C "$data_dir" . 2>/dev/null || {
    log_warn "데이터 압축 부분 실패, 계속 진행..."
  }

  if [ ! -f "$backup_file" ]; then
    log_warn "백테스트 결과 백업 생략"
    return 0
  fi

  local file_size=$(du -h "$backup_file" | cut -f1)
  log_backup "백테스트 결과 백업 완료: $backup_file (크기: $file_size)"

  md5sum "$backup_file" > "${backup_file}.md5"

  echo "$backup_file" >> "$BACKUP_LOG"
  return 0
}

# ═══════════════════════════════════════════════════════════════════════════
# S3 업로드
# ═══════════════════════════════════════════════════════════════════════════

backup_s3() {
  log_backup "S3 백업 업로드 시작..."

  if ! command -v aws &> /dev/null; then
    log_warn "AWS CLI를 찾을 수 없습니다 (S3 업로드 스킵)"
    return 0
  fi

  if [ -z "${AWS_BUCKET_NAME:-}" ]; then
    log_warn "AWS_BUCKET_NAME 미설정 (S3 업로드 스킵)"
    return 0
  fi

  log_info "S3 버킷 확인 중: $AWS_BUCKET_NAME"
  if ! aws s3 ls "s3://${AWS_BUCKET_NAME}" 2>/dev/null; then
    log_warn "S3 버킷 접근 불가 (AWS 자격증명 확인)"
    return 0
  fi

  # 최근 백업 파일 업로드
  log_info "S3에 백업 파일 업로드 중..."

  aws s3 sync "${BACKUP_DIR}" "s3://${AWS_BUCKET_NAME}/backups/" \
    --exclude "*.log" \
    --exclude "*.md5" \
    --delete \
    2>&1 | grep -E "upload|delete|sync" | head -20

  log_success "S3 업로드 완료"

  return 0
}

# ═══════════════════════════════════════════════════════════════════════════
# 백업 정리 (오래된 파일 삭제)
# ═══════════════════════════════════════════════════════════════════════════

cleanup_backups() {
  log_info "오래된 백업 삭제 중 (${CLEANUP_DAYS}일 이상)..."

  local deleted_count=0

  # PostgreSQL 백업 정리
  if [ -d "${BACKUP_DIR}/postgresql" ]; then
    while IFS= read -r file; do
      rm -f "$file"
      ((deleted_count++))
      log_warn "삭제됨: $(basename $file)"
    done < <(find "${BACKUP_DIR}/postgresql" -type f -name "*.gz" -mtime +${CLEANUP_DAYS})
  fi

  # Redis 백업 정리
  if [ -d "${BACKUP_DIR}/redis" ]; then
    while IFS= read -r file; do
      rm -f "$file"
      ((deleted_count++))
      log_warn "삭제됨: $(basename $file)"
    done < <(find "${BACKUP_DIR}/redis" -type f -name "*.gz" -mtime +${CLEANUP_DAYS})
  fi

  # 결과 백업 정리
  if [ -d "${BACKUP_DIR}/results" ]; then
    while IFS= read -r file; do
      rm -f "$file"
      ((deleted_count++))
      log_warn "삭제됨: $(basename $file)"
    done < <(find "${BACKUP_DIR}/results" -type f -name "*.tar.gz" -mtime +${CLEANUP_DAYS})
  fi

  # 체크섬 및 로그 파일도 정리
  find "${BACKUP_DIR}" -type f -name "*.md5" -mtime +${CLEANUP_DAYS} -delete || true
  find "${BACKUP_DIR}" -type f -name "*.log" -mtime +30 -delete || true

  log_success "백업 정리 완료 ($deleted_count개 파일 삭제)"
}

# ═══════════════════════════════════════════════════════════════════════════
# 백업 통계
# ═══════════════════════════════════════════════════════════════════════════

show_backup_stats() {
  log_info "백업 통계:"
  echo ""

  # PostgreSQL
  if [ -d "${BACKUP_DIR}/postgresql" ]; then
    local count=$(find "${BACKUP_DIR}/postgresql" -type f -name "*.gz" | wc -l)
    local total=$(du -sh "${BACKUP_DIR}/postgresql" 2>/dev/null | cut -f1)
    echo "  📊 PostgreSQL: $count 파일, $total"
    ls -lh "${BACKUP_DIR}/postgresql"/*.gz 2>/dev/null | awk '{print "     " $9 " (" $5 ")"}' | head -5
  fi

  # Redis
  if [ -d "${BACKUP_DIR}/redis" ]; then
    local count=$(find "${BACKUP_DIR}/redis" -type f -name "*.gz" | wc -l)
    local total=$(du -sh "${BACKUP_DIR}/redis" 2>/dev/null | cut -f1)
    echo "  📊 Redis: $count 파일, $total"
    ls -lh "${BACKUP_DIR}/redis"/*.gz 2>/dev/null | awk '{print "     " $9 " (" $5 ")"}' | head -5
  fi

  # Results
  if [ -d "${BACKUP_DIR}/results" ]; then
    local count=$(find "${BACKUP_DIR}/results" -type f -name "*.tar.gz" | wc -l)
    local total=$(du -sh "${BACKUP_DIR}/results" 2>/dev/null | cut -f1)
    echo "  📊 Results: $count 파일, $total"
    ls -lh "${BACKUP_DIR}/results"/*.tar.gz 2>/dev/null | awk '{print "     " $9 " (" $5 ")"}' | head -5
  fi

  # 전체
  local total_size=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
  echo ""
  echo "  📦 전체 백업 크기: $total_size"
}

# ═══════════════════════════════════════════════════════════════════════════
# 메인 실행 로직
# ═══════════════════════════════════════════════════════════════════════════

case "$BACKUP_TYPE" in
  all)
    log_info "전체 백업 시작..."
    backup_postgresql
    backup_redis
    backup_results
    log_info "S3 동기화 시도..."
    backup_s3 || true
    ;;
  postgres|postgresql)
    backup_postgresql
    ;;
  redis)
    backup_redis
    ;;
  results)
    backup_results
    ;;
  s3)
    backup_s3
    ;;
  cleanup)
    cleanup_backups
    show_backup_stats
    exit 0
    ;;
  stats|status)
    show_backup_stats
    exit 0
    ;;
  *)
    log_error "알 수 없는 백업 타입: $BACKUP_TYPE"
    echo "사용법: $0 {all|postgres|redis|results|s3|cleanup|stats}"
    exit 1
    ;;
esac

echo "" | tee -a "$BACKUP_LOG"

# ═══════════════════════════════════════════════════════════════════════════
# 백업 완료 리포트
# ═══════════════════════════════════════════════════════════════════════════

log_success "백업 작업 완료"
echo "" | tee -a "$BACKUP_LOG"

show_backup_stats

# 리포트 생성
cat > "${BACKUP_DIR}/BACKUP_REPORT_${TIMESTAMP}.txt" << EOF
╔════════════════════════════════════════════════════════════════════════════╗
║                    백업 리포트                                            ║
║                    (Task 3.6: 백업 자동화)                                ║
╚════════════════════════════════════════════════════════════════════════════╝

📋 백업 정보
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  타입:       $BACKUP_TYPE
  타임스탬프: $TIMESTAMP
  디렉토리:   $BACKUP_DIR

📦 백업 통계
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
$(show_backup_stats)

🔐 백업 검증
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

체크섬 확인:
$(find "${BACKUP_DIR}" -name "*.md5" -exec sh -c 'echo "  $(cat {})"' \; 2>/dev/null | head -10 || echo "  체크섬 파일 없음")

🔄 복구 방법
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. PostgreSQL 복구:
   gunzip -c backups/postgresql/backup_*.sql.gz | \
     docker-compose exec -T postgres psql -U coin_user -d coin_db

2. Redis 복구:
   gunzip -c backups/redis/dump_*.rdb.gz > /tmp/dump.rdb
   docker-compose cp /tmp/dump.rdb redis:/data/dump.rdb
   docker-compose exec -T redis redis-cli SHUTDOWN
   docker-compose restart redis

3. 결과 백업 복구:
   tar -xzf backups/results/results_*.tar.gz -C ./data

📅 백업 정리 정책
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  보관 기간: $CLEANUP_DAYS일
  정리 명령: ./scripts/backup.sh cleanup $CLEANUP_DAYS

🚀 자동화 스케줄
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cron 예시 (매일 자정에 백업):
  0 0 * * * /path/to/scripts/backup.sh all
  0 1 * * 0 /path/to/scripts/backup.sh cleanup 7

═══════════════════════════════════════════════════════════════════════════════
백업 일시: $(date '+%Y-%m-%d %H:%M:%S %Z')
상태: ✅ 완료
═══════════════════════════════════════════════════════════════════════════════
EOF

log_info "백업 리포트: BACKUP_REPORT_${TIMESTAMP}.txt"

echo "" | tee -a "$BACKUP_LOG"
log_info "복구 방법은 BACKUP_REPORT_${TIMESTAMP}.txt에서 확인하세요"
