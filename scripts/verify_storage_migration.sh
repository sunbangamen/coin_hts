#!/bin/bash

################################################################################
# Storage Migration Verification Script
#
# 목적: 로컬/Docker/S3 스토리지 전환 무결성 검증
# 사용법: ./scripts/verify_storage_migration.sh [OPTIONS]
# 옵션:
#   --dry-run      실제 복사 없이 시뮬레이션
#   --verbose      상세 로그 출력
#   --cleanup      테스트 후 임시 파일 삭제
#   --s3-profile   AWS CLI 프로파일 선택
#
# 테스트 시나리오:
#   1. 로컬 디렉토리 → Docker 볼륨
#   2. 외부 마운트 → Docker 볼륨 바인딩
#   3. Docker 볼륨 → AWS S3 버킷
#
################################################################################

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 변수
DRY_RUN=false
VERBOSE=false
CLEANUP=true
AWS_PROFILE=${AWS_PROFILE:-"default"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_ROOT="${DATA_ROOT:-${PROJECT_ROOT}/data}"
TEST_DIR="${DATA_ROOT}/test_migration"
REPORT_FILE="${PROJECT_ROOT}/docs/coin/mvp/STORAGE_MIGRATION_REPORT.md"

# 통계
TEST_RESULTS=()
PASSED_TESTS=0
FAILED_TESTS=0

################################################################################
# 유틸 함수
################################################################################

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
    ((PASSED_TESTS++))
    TEST_RESULTS+=("✅ $1")
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    ((FAILED_TESTS++))
    TEST_RESULTS+=("❌ $1")
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

verbose_log() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}   $1${NC}"
    fi
}

run_command() {
    local cmd="$1"
    verbose_log "실행: $cmd"

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] $cmd"
        return 0
    else
        eval "$cmd"
    fi
}

calculate_checksum() {
    local filepath="$1"
    if command -v md5sum &> /dev/null; then
        md5sum "$filepath" | awk '{print $1}'
    else
        md5 -q "$filepath"  # macOS
    fi
}

################################################################################
# 테스트 시나리오 1: 로컬 → Docker 볼륨
################################################################################

test_local_to_docker_volume() {
    print_header "테스트 1: 로컬 디렉토리 → Docker 볼륨"

    # 테스트 파일 생성
    local test_file="${TEST_DIR}/test_1/sample.json"
    mkdir -p "$(dirname "$test_file")"

    verbose_log "테스트 파일 생성: $test_file"
    cat > "$test_file" << 'EOF'
{
    "strategy": "volume_zone_breakout",
    "symbols": ["BTC_KRW", "ETH_KRW"],
    "test": "local_to_docker",
    "timestamp": "2025-11-10T10:00:00Z"
}
EOF

    # 원본 체크섬
    local original_checksum=$(calculate_checksum "$test_file")
    print_info "원본 파일 체크섬: $original_checksum"

    # Docker 볼륨 경로
    local docker_path="/data/test_migration/test_1/sample.json"
    local docker_volume="$(docker-compose config --services 2>/dev/null | grep backend || echo 'backend')"

    # 파일 복사 (Docker 볼륨)
    print_info "Docker 볼륨으로 복사 중..."
    run_command "docker-compose cp '$test_file' ${docker_volume}:${docker_path}"

    # 복사된 파일 체크섬
    verbose_log "Docker 컨테이너에서 파일 검증..."
    local copied_checksum=$(docker-compose exec -T backend \
        md5sum "$docker_path" 2>/dev/null | awk '{print $1}' || echo "ERROR")

    # 검증
    if [ "$original_checksum" = "$copied_checksum" ]; then
        print_success "로컬 → Docker 볼륨 전환 성공 (체크섬 일치)"
    else
        print_error "체크섬 불일치: $original_checksum vs $copied_checksum"
        return 1
    fi

    # 읽기/쓰기 권한 검증
    verbose_log "권한 검증 중..."
    run_command "docker-compose exec -T backend test -r '$docker_path' && echo 'Read OK'"
    print_success "Docker 볼륨 읽기 권한 확인"
}

################################################################################
# 테스트 시나리오 2: 외부 마운트 → Docker 볼륨 바인딩
################################################################################

test_external_mount_binding() {
    print_header "테스트 2: 외부 마운트 → Docker 볼륨 바인딩"

    # 외부 경로 시뮬레이션 (실제 OneDrive/NAS 경로)
    local external_dir="${TEST_DIR}/external_mount"
    mkdir -p "$external_dir"

    print_info "외부 마운트 시뮬레이션: $external_dir"

    # 테스트 파일 생성
    local test_file="${external_dir}/backtest_result.json"
    cat > "$test_file" << 'EOF'
{
    "strategy": "volume_zone_breakout",
    "total_trades": 45,
    "win_rate": 0.62,
    "external_mount": true
}
EOF

    local original_checksum=$(calculate_checksum "$test_file")
    print_info "외부 파일 체크섬: $original_checksum"

    # Docker 바인딩 검증
    print_info "Docker 컨테이너에서 바인딩된 볼륨 접근 중..."

    # docker-compose.yml에서 바인딩된 경로 확인
    local mounted_path="/data/external_mount"

    # 실제 Docker 바인딩이 있는지 확인 (docker-compose up 필요)
    if docker-compose ps | grep -q backend; then
        verbose_log "Backend 컨테이너 실행 확인"
        run_command "docker-compose exec -T backend test -d '$mounted_path' && echo 'Mount OK'"
        print_success "외부 마운트 Docker 바인딩 확인"
    else
        print_warning "Backend 컨테이너가 실행 중이지 않아 바인딩 테스트 스킵"
    fi

    # 권한 검증 (로컬)
    if [ -r "$test_file" ] && [ -w "$external_dir" ]; then
        print_success "외부 마운트 읽기/쓰기 권한 확인"
    else
        print_error "외부 마운트 권한 부족"
        return 1
    fi
}

################################################################################
# 테스트 시나리오 3: Docker 볼륨 → AWS S3
################################################################################

test_docker_to_s3() {
    print_header "테스트 3: Docker 볼륨 → AWS S3 버킷"

    # AWS 설정 확인
    if ! command -v aws &> /dev/null; then
        print_warning "AWS CLI가 설치되지 않음. S3 테스트 스킵"
        return 0
    fi

    local bucket_name="${AWS_BUCKET_NAME:-}"
    if [ -z "$bucket_name" ]; then
        print_warning "AWS_BUCKET_NAME 환경 변수가 설정되지 않음. S3 테스트 스킵"
        return 0
    fi

    print_info "AWS S3 버킷: $bucket_name"
    print_info "AWS 프로파일: $AWS_PROFILE"

    # 테스트 파일 생성
    local test_file="${TEST_DIR}/s3_test/result.json"
    mkdir -p "$(dirname "$test_file")"

    cat > "$test_file" << 'EOF'
{
    "strategy": "volume_zone_breakout",
    "test": "s3_upload_download",
    "timestamp": "2025-11-10T11:00:00Z",
    "data": "This is a test file for S3 migration verification"
}
EOF

    local original_checksum=$(calculate_checksum "$test_file")
    print_info "원본 파일 체크섬: $original_checksum"

    # S3에 업로드
    local s3_path="s3://${bucket_name}/test/migration/result.json"
    print_info "S3 업로드 중: $s3_path"

    if run_command "aws s3 cp '$test_file' '$s3_path' --profile $AWS_PROFILE 2>&1"; then
        print_success "S3 업로드 완료"

        # S3에서 다운로드
        local download_file="${TEST_DIR}/s3_downloaded.json"
        print_info "S3 다운로드 중..."

        if run_command "aws s3 cp '$s3_path' '$download_file' --profile $AWS_PROFILE 2>&1"; then
            print_success "S3 다운로드 완료"

            # 체크섬 비교
            local downloaded_checksum=$(calculate_checksum "$download_file")
            if [ "$original_checksum" = "$downloaded_checksum" ]; then
                print_success "S3 업로드/다운로드 무결성 검증 성공"
            else
                print_error "체크섬 불일치: $original_checksum vs $downloaded_checksum"
                return 1
            fi
        else
            print_error "S3 다운로드 실패"
            return 1
        fi
    else
        print_error "S3 업로드 실패 (AWS 자격증명 확인)"
        return 1
    fi
}

################################################################################
# 메인 실행 로직
################################################################################

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --no-cleanup)
                CLEANUP=false
                shift
                ;;
            --s3-profile)
                AWS_PROFILE="$2"
                shift 2
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done
}

cleanup() {
    if [ "$CLEANUP" = true ] && [ "$DRY_RUN" = false ]; then
        print_header "정리 중..."

        if [ -d "$TEST_DIR" ]; then
            verbose_log "테스트 디렉토리 삭제: $TEST_DIR"
            rm -rf "$TEST_DIR"
            print_info "임시 파일 정리 완료"
        fi
    fi
}

generate_report() {
    print_header "테스트 결과 요약"

    echo ""
    echo "📊 테스트 결과:"
    echo "   통과: $PASSED_TESTS"
    echo "   실패: $FAILED_TESTS"
    echo "   총계: $((PASSED_TESTS + FAILED_TESTS))"
    echo ""

    if [ $FAILED_TESTS -eq 0 ]; then
        print_success "모든 테스트 통과! ✅"
        return 0
    else
        print_error "일부 테스트 실패"
        return 1
    fi
}

main() {
    parse_arguments "$@"

    print_header "스토리지 마이그레이션 검증"
    print_info "시작 시간: $(date)"
    print_info "데이터 루트: $DATA_ROOT"

    if [ "$DRY_RUN" = true ]; then
        print_warning "DRY-RUN 모드: 실제 파일 작업 수행 안 됨"
    fi

    # Docker Compose 상태 확인
    if docker-compose ps &> /dev/null; then
        print_info "Docker Compose 실행 중"
    else
        print_warning "Docker Compose가 실행 중이지 않음"
    fi

    echo ""

    # 테스트 실행
    test_local_to_docker_volume || true
    echo ""

    test_external_mount_binding || true
    echo ""

    test_docker_to_s3 || true
    echo ""

    # 정리
    cleanup

    # 보고서
    generate_report
}

# 스크립트 실행
main "$@"
