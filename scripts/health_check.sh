#!/bin/bash
# Task 3.6: 헬스 체크 및 모니터링 스크립트
#
# 목적: 시스템 및 서비스 상태 모니터링
# 사용법:
#   ./scripts/health_check.sh              # 전체 헬스 체크
#   ./scripts/health_check.sh verbose      # 상세 정보 출력
#   ./scripts/health_check.sh alert        # 문제 발생 시 알림 활성화
#   ./scripts/health_check.sh monitor      # 5초 간격 지속 모니터링
#
# 기능:
#   1. PostgreSQL 연결 및 성능 확인
#   2. Redis 연결 및 메모리 확인
#   3. Backend API 상태 확인
#   4. RQ 큐 작업 상태 확인
#   5. 시스템 리소스 모니터링 (CPU, 메모리, 디스크)
#   6. Docker 컨테이너 상태 확인
#   7. 문제 진단 및 권장사항 제시

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════
# 색상 및 로깅
# ═══════════════════════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 헬스 상태 정보
HEALTHY=0
WARNINGS=0
ERRORS=0
CHECKS_TOTAL=0

# 색상 상태 표시
status_ok() { echo -e "${GREEN}✅${NC}"; }
status_warn() { echo -e "${YELLOW}⚠️ ${NC}"; }
status_fail() { echo -e "${RED}❌${NC}"; }
status_unknown() { echo -e "${CYAN}❓${NC}"; }

log_check() {
  ((CHECKS_TOTAL++))
  echo -e "${BLUE}[CHECK]${NC} $*"
}

log_ok() {
  ((HEALTHY++))
  echo -e "${GREEN}[OK]${NC} $*"
}

log_warn() {
  ((WARNINGS++))
  echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
  ((ERRORS++))
  echo -e "${RED}[ERROR]${NC} $*"
}

# ═══════════════════════════════════════════════════════════════════════════
# 설정
# ═══════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERBOSE="${1:-normal}"
HEALTH_CHECK_LOG="${PROJECT_ROOT}/logs/health_check_$(date +%Y%m%d_%H%M%S).log"
ALERT_ENABLED=false
MONITOR_MODE=false

mkdir -p "${PROJECT_ROOT}/logs"

if [ "$VERBOSE" = "verbose" ]; then
  VERBOSE=true
else
  VERBOSE=false
fi

if [ "$1" = "alert" ]; then
  ALERT_ENABLED=true
fi

if [ "$1" = "monitor" ]; then
  MONITOR_MODE=true
fi

# 환경 변수 로드
set -a
source "${PROJECT_ROOT}/.env" 2>/dev/null || {
  log_warn "환경 파일 로드 실패, 기본값 사용"
}
set +a

# ═══════════════════════════════════════════════════════════════════════════
# PostgreSQL 헬스 체크
# ═══════════════════════════════════════════════════════════════════════════

check_postgresql() {
  log_check "PostgreSQL 헬스 체크..."

  # Docker 컨테이너 상태 확인
  if docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" ps postgres | grep -q "postgres"; then
    # Docker 환경
    if docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T postgres \
      pg_isready -U coin_user -d coin_db 2>/dev/null | grep -q "accepting"; then
      log_ok "PostgreSQL 연결 정상 (Docker)"

      # 연결 수 확인
      local conn_count=$(docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T postgres \
        psql -U coin_user -d coin_db -t -c "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null || echo "?")

      if [ "$conn_count" != "?" ]; then
        if [ "$conn_count" -gt 50 ]; then
          log_warn "PostgreSQL 연결 수 과다: $conn_count"
        else
          [ "$VERBOSE" = "true" ] && log_ok "PostgreSQL 연결 수: $conn_count"
        fi
      fi

      # 데이터베이스 크기 확인
      local db_size=$(docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T postgres \
        psql -U coin_user -d coin_db -t -c "SELECT pg_size_pretty(pg_database_size('coin_db'));" 2>/dev/null || echo "?")

      if [ "$db_size" != "?" ]; then
        [ "$VERBOSE" = "true" ] && log_ok "데이터베이스 크기: $db_size"
      fi
    else
      log_error "PostgreSQL 연결 불가 (Docker)"
      return 1
    fi
  elif command -v psql &> /dev/null; then
    # 로컬 환경
    if psql "$DATABASE_URL" -c "\q" 2>/dev/null; then
      log_ok "PostgreSQL 연결 정상 (로컬)"
    else
      log_error "PostgreSQL 연결 불가 (로컬)"
      return 1
    fi
  else
    log_warn "PostgreSQL 확인 불가 (psql 미설치)"
    return 0
  fi

  return 0
}

# ═══════════════════════════════════════════════════════════════════════════
# Redis 헬스 체크
# ═══════════════════════════════════════════════════════════════════════════

check_redis() {
  log_check "Redis 헬스 체크..."

  # Docker 컨테이너 상태 확인
  if docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" ps redis | grep -q "redis"; then
    # Docker 환경
    if docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T redis \
      redis-cli ping 2>/dev/null | grep -q "PONG"; then
      log_ok "Redis 연결 정상 (Docker)"

      # Redis 메모리 사용량
      local memory_info=$(docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T redis \
        redis-cli info memory 2>/dev/null | grep "used_memory_human" | cut -d: -f2 || echo "?")

      if [ "$memory_info" != "?" ]; then
        [ "$VERBOSE" = "true" ] && log_ok "Redis 메모리 사용: $memory_info"
      fi

      # RQ 큐 상태
      local backtest_queue=$(docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T redis \
        redis-cli llen "rq:queue:backtest-queue" 2>/dev/null || echo "0")
      local data_queue=$(docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T redis \
        redis-cli llen "rq:queue:data_ingestion" 2>/dev/null || echo "0")

      if [ "$backtest_queue" = "0" ] && [ "$data_queue" = "0" ]; then
        [ "$VERBOSE" = "true" ] && log_ok "RQ 큐: 대기 작업 없음"
      else
        log_warn "RQ 큐: backtest-queue($backtest_queue), data_ingestion($data_queue)"
      fi
    else
      log_error "Redis 연결 불가 (Docker)"
      return 1
    fi
  elif command -v redis-cli &> /dev/null; then
    # 로컬 환경
    if redis-cli ping 2>/dev/null | grep -q "PONG"; then
      log_ok "Redis 연결 정상 (로컬)"
    else
      log_error "Redis 연결 불가 (로컬)"
      return 1
    fi
  else
    log_warn "Redis 확인 불가 (redis-cli 미설치)"
    return 0
  fi

  return 0
}

# ═══════════════════════════════════════════════════════════════════════════
# Backend API 헬스 체크
# ═══════════════════════════════════════════════════════════════════════════

check_backend_api() {
  log_check "Backend API 헬스 체크..."

  if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    log_ok "Backend API 응답 정상 (http://localhost:8000)"

    # API 응답 시간 측정
    local response_time=$(curl -s -w "%{time_total}" -o /dev/null http://localhost:8000/docs)
    if (( $(echo "$response_time < 1.0" | bc -l) )); then
      [ "$VERBOSE" = "true" ] && log_ok "API 응답 시간: ${response_time}초"
    else
      log_warn "API 응답 시간 지연: ${response_time}초"
    fi
  else
    log_error "Backend API 응답 불가 (http://localhost:8000)"
    return 1
  fi

  return 0
}

# ═══════════════════════════════════════════════════════════════════════════
# Docker 컨테이너 상태 확인
# ═══════════════════════════════════════════════════════════════════════════

check_docker_containers() {
  log_check "Docker 컨테이너 상태 확인..."

  if ! command -v docker-compose &> /dev/null; then
    log_warn "docker-compose 미설치"
    return 0
  fi

  local container_status=$(docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" ps 2>/dev/null)

  if echo "$container_status" | grep -q "running"; then
    log_ok "Docker 컨테이너 실행 중"

    if [ "$VERBOSE" = "true" ]; then
      echo "$container_status" | grep "running" | awk '{print "       " $1 " -> " $NF}'
    fi

    # 중지된 컨테이너 확인
    if echo "$container_status" | grep -q "exited\|stopped"; then
      log_warn "중지된 컨테이너 발견"
      echo "$container_status" | grep -E "exited|stopped" | awk '{print "       " $1 " -> " $NF}'
    fi
  else
    log_error "Docker 컨테이너 실행 불가"
    return 1
  fi

  return 0
}

# ═══════════════════════════════════════════════════════════════════════════
# 시스템 리소스 확인
# ═══════════════════════════════════════════════════════════════════════════

check_system_resources() {
  log_check "시스템 리소스 확인..."

  # CPU 사용률
  if command -v top &> /dev/null; then
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
      log_warn "CPU 사용률 높음: ${cpu_usage}%"
    else
      [ "$VERBOSE" = "true" ] && log_ok "CPU 사용률: ${cpu_usage}%"
    fi
  fi

  # 메모리 사용률
  if command -v free &> /dev/null; then
    local mem_info=$(free | grep Mem)
    local total=$(echo "$mem_info" | awk '{print $2}')
    local used=$(echo "$mem_info" | awk '{print $3}')
    local mem_usage=$(echo "scale=1; $used * 100 / $total" | bc)

    if (( $(echo "$mem_usage > 80" | bc -l) )); then
      log_warn "메모리 사용률 높음: ${mem_usage}%"
    else
      [ "$VERBOSE" = "true" ] && log_ok "메모리 사용률: ${mem_usage}%"
    fi
  fi

  # 디스크 사용률
  if command -v df &> /dev/null; then
    local disk_usage=$(df -h / | tail -1 | awk '{print $(NF-1)}' | sed 's/%//')
    if (( disk_usage > 80 )); then
      log_warn "디스크 사용률 높음: ${disk_usage}%"
    else
      [ "$VERBOSE" = "true" ] && log_ok "디스크 사용률: ${disk_usage}%"
    fi
  fi

  return 0
}

# ═══════════════════════════════════════════════════════════════════════════
# 종합 상태 리포트
# ═══════════════════════════════════════════════════════════════════════════

print_summary() {
  echo ""
  echo "════════════════════════════════════════════════════════════════════════════"
  echo "                    헬스 체크 종합 리포트"
  echo "════════════════════════════════════════════════════════════════════════════"
  echo ""
  echo "📊 검사 결과:"
  echo "   총 검사: $CHECKS_TOTAL"
  echo "   정상:   $(status_ok) $HEALTHY"
  echo "   경고:   $(status_warn) $WARNINGS"
  echo "   오류:   $(status_fail) $ERRORS"
  echo ""

  # 종합 상태
  local overall_status="✅ HEALTHY"
  if [ $ERRORS -gt 0 ]; then
    overall_status="❌ CRITICAL"
  elif [ $WARNINGS -gt 0 ]; then
    overall_status="⚠️  WARNING"
  fi

  echo "   종합: $overall_status"
  echo ""
  echo "════════════════════════════════════════════════════════════════════════════"
  echo "시간: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "════════════════════════════════════════════════════════════════════════════"
}

# ═══════════════════════════════════════════════════════════════════════════
# 문제 진단 및 권장사항
# ═══════════════════════════════════════════════════════════════════════════

print_recommendations() {
  if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo ""
    log_ok "모든 서비스가 정상 작동 중입니다!"
    return 0
  fi

  echo ""
  echo "🔧 권장사항:"
  echo ""

  # PostgreSQL 문제
  if [ $ERRORS -gt 0 ]; then
    echo "   PostgreSQL 연결 실패:"
    echo "   1. Docker 상태 확인: docker-compose ps postgres"
    echo "   2. PostgreSQL 로그 확인: docker-compose logs postgres"
    echo "   3. 서비스 재시작: docker-compose restart postgres"
    echo ""
  fi

  # Redis 문제
  if [ $ERRORS -gt 0 ]; then
    echo "   Redis 연결 실패:"
    echo "   1. Docker 상태 확인: docker-compose ps redis"
    echo "   2. Redis 로그 확인: docker-compose logs redis"
    echo "   3. 서비스 재시작: docker-compose restart redis"
    echo ""
  fi

  # API 문제
  if [ $ERRORS -gt 0 ]; then
    echo "   Backend API 응답 불가:"
    echo "   1. Backend 로그 확인: docker-compose logs backend"
    echo "   2. Port 충돌 확인: lsof -i :8000"
    echo "   3. 서비스 재시작: docker-compose restart backend"
    echo ""
  fi

  # 성능 경고
  if [ $WARNINGS -gt 0 ]; then
    echo "   성능 저하:"
    echo "   1. 메모리 사용량 높음: free -h | grep Mem"
    echo "   2. CPU 사용량 높음: top -b -n 1 | head -20"
    echo "   3. 디스크 공간 부족: df -h"
    echo ""
  fi
}

# ═══════════════════════════════════════════════════════════════════════════
# 메인 헬스 체크
# ═══════════════════════════════════════════════════════════════════════════

main_health_check() {
  echo "🏥 헬스 체크 시작..."
  echo ""

  check_postgresql || true
  check_redis || true
  check_backend_api || true
  check_docker_containers || true
  check_system_resources || true

  print_summary
  print_recommendations

  # 결과 저장
  {
    echo "헬스 체크 결과 ($(date '+%Y-%m-%d %H:%M:%S'))"
    echo "정상: $HEALTHY, 경고: $WARNINGS, 오류: $ERRORS"
  } >> "$HEALTH_CHECK_LOG"

  # 알림 활성화 시
  if [ "$ALERT_ENABLED" = "true" ] && [ $ERRORS -gt 0 ]; then
    if command -v mail &> /dev/null; then
      echo "❌ 헬스 체크 실패 (오류: $ERRORS개)" | mail -s "Alert: Health Check Failed" root
    fi
  fi
}

# ═══════════════════════════════════════════════════════════════════════════
# 지속 모니터링 (Monitor Mode)
# ═══════════════════════════════════════════════════════════════════════════

if [ "$MONITOR_MODE" = "true" ]; then
  echo "📡 모니터링 모드 시작 (5초 간격, Ctrl+C로 종료)"
  echo ""

  while true; do
    clear
    echo "$(date '+%H:%M:%S') - 모니터링 중..."
    echo ""

    HEALTHY=0
    WARNINGS=0
    ERRORS=0
    CHECKS_TOTAL=0

    check_postgresql || true
    check_redis || true
    check_backend_api || true
    check_docker_containers || true
    check_system_resources || true

    print_summary

    sleep 5
  done
else
  main_health_check
fi
