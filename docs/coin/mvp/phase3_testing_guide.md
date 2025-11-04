# Phase 3 테스트 가이드 (Step 4: 통합 테스트)

## 개요

Phase 3 (운영 안정성) 구현의 통합 테스트 및 회귀 테스트 가이드입니다.

---

## 테스트 환경 요구조건

**중요**: 모든 Phase 3 테스트는 Redis/RQ 실제 인스턴스 없이 실행 가능합니다.

| 환경 | 요구사항 | 상태 |
|------|--------|------|
| Redis | 불필요 (MagicMock 사용) | ✅ |
| RQ | 불필요 (MagicMock 사용) | ✅ |
| 데이터 파일 | 불필요 (API 검증 테스트) | ✅ |
| Python 버전 | 3.9+ | ✅ |
| 필수 패키지 | pytest, fastapi, httpx, unittest.mock | ✅ |

→ **결론**: `pytest tests/test_async_api.py` 단독 실행 가능 (의존성 최소화)

---

## 테스트 구조

### 기존 테스트 (Phase 1-2)
- `tests/test_data_loader.py`: 데이터 로더 테스트
- `tests/test_strategies.py`: 백테스트 전략 테스트
- `tests/test_api.py`: API 엔드포인트 테스트 (동기)

### 신규 테스트 (Phase 3)
- `tests/test_async_api.py`: 비동기 API 엔드포인트 테스트 (Redis/RQ 모킹)
- `tests/test_result_manager.py`: 결과 파일 관리 테스트 (임시 디렉토리 사용)

---

## 테스트 실행

### 환경 설정

#### 1. Docker 환경 (권장)
```bash
# Redis + Backend 실행
docker-compose up -d

# 워커 실행 (별도 터미널)
docker-compose --profile worker up worker
```

#### 2. 로컬 환경
```bash
# Redis 실행 (별도 터미널)
redis-server

# Python 환경 설정
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 테스트 실행 명령

#### 모든 테스트 실행
```bash
# Docker 환경
docker-compose --profile test run test

# 로컬 환경
pytest tests/ -v
```

#### 특정 테스트 실행
```bash
# 기존 테스트만 실행 (회귀 테스트)
pytest tests/test_api.py tests/test_strategies.py tests/test_data_loader.py -v

# 비동기 API 테스트만 실행
pytest tests/test_async_api.py -v

# 결과 파일 관리 테스트만 실행
pytest tests/test_result_manager.py -v

# 특정 테스트 클래스만 실행
pytest tests/test_async_api.py::TestAsyncBacktestEndpoints -v

# 특정 테스트 함수만 실행
pytest tests/test_async_api.py::TestAsyncBacktestEndpoints::test_run_backtest_async_success -v
```

#### 커버리지 리포트 생성
```bash
pytest tests/ --cov=backend --cov-report=html
# htmlcov/index.html에서 확인
```

#### 상세 로그 출력
```bash
pytest tests/ -v -s
```

---

## 테스트 케이스 명세

### Step 4.1: 기존 75개 pytest 통과

**목표**: Phase 1-2 기능이 여전히 정상 작동하는지 확인

**포함되는 테스트**:
- `test_api.py`: 21개 (동기 엔드포인트, 데이터 로드, 전략 검증)
- `test_strategies.py`: 28개 (volume_long_candle, volume_zone_breakout 최적화)
- `test_data_loader.py`: 26개 (Parquet 로드, 타임존, 필터링)

**실행**:
```bash
pytest tests/test_api.py tests/test_strategies.py tests/test_data_loader.py -v
```

**기대 결과**: 모든 테스트 통과 ✅

---

### Step 4.2: 비동기 API 엔드포인트 테스트

**파일**: `tests/test_async_api.py`

#### TestAsyncBacktestEndpoints
테스트 케이스:
1. **test_run_backtest_async_request_validation**: 필수 필드 검증
   - 예: symbols 누락 → 422 에러
   - 기대: HTTPStatus 422

2. **test_run_backtest_async_invalid_strategy**: 잘못된 전략명
   - 예: strategy="invalid" → 422 에러
   - 기대: HTTPStatus 422

3. **test_run_backtest_async_invalid_date_format**: 날짜 형식 검증
   - 예: "2024/01/01" (잘못된 형식) → 422 에러
   - 기대: HTTPStatus 422

4. **test_run_backtest_async_invalid_date_range**: 날짜 범위 검증
   - 예: start_date > end_date → 422 에러
   - 기대: HTTPStatus 422

5. **test_run_backtest_async_success**: 성공적인 비동기 실행
   - 예: 유효한 요청 → 202 Accepted
   - 기대: task_id (UUID), status="queued", created_at 포함

6. **test_run_backtest_async_with_params**: 커스텀 파라미터
   - 예: custom params + 복수 심볼
   - 기대: task_id 반환

#### TestTaskStatusEndpoints
테스트 케이스:
1. **test_get_task_status_not_found**: 존재하지 않는 작업
   - 예: invalid task_id → 404 에러
   - 기대: HTTPStatus 404

2. **test_get_task_status_queued**: 대기 중인 작업
   - 기대: status="queued", progress=0.0

3. **test_get_task_status_running**: 실행 중인 작업
   - 기대: status="running", 0.0 < progress < 1.0

4. **test_get_task_status_completed**: 완료된 작업
   - 기대: status="completed", progress=1.0, result != null

5. **test_get_task_status_failed**: 실패한 작업
   - 기대: status="failed", error != null

#### TestAsyncEndtoEndScenarios
테스트 케이스:
1. **test_async_workflow_sequence**: 비동기 워크플로우 전체 시퀀스
   - 1단계: 비동기 실행 (202 Accepted)
   - 2단계: 대기 상태 확인 (queued)
   - 3단계: 실행 상태 확인 (running, progress=0.5)
   - 4단계: 완료 상태 확인 (completed, progress=1.0, result 포함)
   - 기대: 모든 단계 성공

---

### Step 4.3: 결과 파일 관리 테스트

**파일**: `tests/test_result_manager.py`

테스트 케이스:
1. **test_get_task_directory**: 작업 디렉토리 경로
   - 예: get_task_directory("/data", "abc123") → "/data/tasks/abc123"
   - 기대: 올바른 경로 반환

2. **test_create_task_directory**: 디렉토리 생성
   - 기대: 디렉토리 생성됨, os.path.exists() = True

3. **test_calculate_checksum**: 파일 체크섬 계산
   - 기대: MD5 해시 (32자), 일관성 유지

4. **test_save_result_file**: 결과 파일 저장
   - 기대: result.json 생성, 내용 검증

5. **test_save_manifest_file**: manifest.json 저장
   - 기대: manifest.json 생성, 모든 필드 포함

6. **test_save_manifest_file_with_error**: 에러 manifest 저장
   - 기대: error.occurred=true, error.message 포함

7. **test_get_result_file_exists**: 기존 결과 파일 조회
   - 기대: 파일 경로 반환

8. **test_get_result_file_not_exists**: 존재하지 않는 파일
   - 기대: None 반환

9. **test_cleanup_old_results_dry_run**: 정리 dry-run
   - 기대: deleted_count 반환, 파일 미삭제

10. **test_cleanup_old_results_actual**: 정리 실제 실행
    - 기대: 파일 삭제됨

11. **test_cleanup_skips_recent_results**: 최근 결과 보존
    - 기대: deleted_count=0 (TTL 이내 파일 유지)

---

## 성능 기준선 검증

### 요구사항
- **목표**: 1000 캔들 백테스트 1초 이내 실행

### 벤치마크 실행
```bash
# 동기 모드 성능 테스트
python -m pytest tests/test_api.py::TestBacktestEndpoints::test_run_backtest_large_dataset -v

# 비동기 모드 성능 테스트 (실제 워커 필요)
curl -X POST http://localhost:8000/api/backtests/run-async \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "volume_zone_breakout",
    "symbols": ["BTC_KRW"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }'

# 상태 조회하면서 진행률 모니터링
for i in {1..10}; do
  curl http://localhost:8000/api/backtests/status/{task_id}
  sleep 0.5
done
```

### 기대 결과
- ✅ 동기 모드: 1000 캔들 < 1초
- ✅ 비동기 모드: 진행률이 0→1.0으로 증가
- ✅ 메모리 누수 없음 (Redis TTL 정책 작동)

---

## 통합 테스트 시나리오

### 시나리오 1: 정상 비동기 실행
```
1. 클라이언트가 비동기 백테스트 요청
   → /api/backtests/run-async
   ← 202 Accepted + task_id

2. 클라이언트가 진행률 폴링
   → /api/backtests/status/{task_id}
   ← status=queued, progress=0.0

3. 워커가 작업 처리
   (1) 데이터 로드
   (2) 전략 실행
   (3) 결과 계산

4. 진행률 업데이트
   → progress=0.2 → 0.5 → 0.95 → 1.0

5. 완료 시 결과 저장
   - ${DATA_ROOT}/tasks/<task_id>/result.json
   - ${DATA_ROOT}/tasks/<task_id>/manifest.json

6. 클라이언트가 최종 상태 조회
   → /api/backtests/status/{task_id}
   ← status=completed, progress=1.0, result={...}
```

### 시나리오 2: 에러 처리
```
1. 클라이언트가 잘못된 요청
   → /api/backtests/run-async (invalid params)
   ← 422 Unprocessable Entity

2. 워커가 데이터 로드 실패
   → /api/backtests/status/{task_id}
   ← status=failed, error="Data loader error"

3. Manifest 저장 (에러 기록)
   - ${DATA_ROOT}/tasks/<task_id>/manifest.json
   - error.occurred=true, error.message 포함
```

### 시나리오 3: 결과 정리
```
1. 매일 정리 스크립트 실행
   python scripts/cleanup_task_results.py

2. 7일 이상 된 작업 디렉토리 삭제
   - manifest.json 생성 시간 기준
   - ${DATA_ROOT}/tasks/<task_id>/ 전체 삭제

3. 정리 로그 기록
   - Deleted count: N
   - Deleted size: M MB
```

---

## 회귀 테스트 체크리스트

### API 호환성
- ✅ POST /api/backtests/run (기존)
- ✅ GET /api/backtests/{run_id} (기존)
- ✅ GET /api/strategies (기존)
- ✅ POST /api/backtests/run-async (신규)
- ✅ GET /api/backtests/status/{task_id} (신규)

### 데이터 검증
- ✅ BacktestResponse 스키마 (v1.1.0)
- ✅ 날짜 형식 (YYYY-MM-DD)
- ✅ 타임존 처리 (UTC, KST)
- ✅ 숫자 정밀도 (float)

### 전략 검증
- ✅ volume_long_candle (기존)
- ✅ volume_zone_breakout (Phase 2 최적화)
- ✅ 파라미터 기본값 (자동 적용)

### 파일 시스템
- ✅ 결과 파일 저장 (result.json)
- ✅ Manifest 생성 (manifest.json)
- ✅ 체크섬 계산 (MD5)
- ✅ 정리 스크립트 (TTL 기반)

### 성능
- ✅ 1000 캔들 < 1초 (기준선 유지)
- ✅ Redis 메모리 관리 (TTL 정책)
- ✅ 동시성 처리 (다중 워커)

---

## 문제 해결

### Redis 연결 실패
```bash
# Redis 상태 확인
redis-cli ping

# Docker Redis 재시작
docker-compose restart redis
```

### 테스트 실패 시 디버깅
```bash
# 상세 로그 출력
pytest tests/ -v -s --tb=short

# 특정 테스트 디버깅
pytest tests/test_async_api.py::TestAsyncBacktestEndpoints::test_run_backtest_async_success -v -s --pdb
```

### 파일 시스템 문제
```bash
# 임시 파일 정리
rm -rf data/tasks/

# 정리 스크립트 dry-run
python scripts/cleanup_task_results.py --dry-run --ttl-days 0
```

---

## 예상 테스트 실행 시간

| 테스트 | 실행 시간 | 예상 |
|--------|----------|------|
| test_api.py | ~5초 | 21개 테스트 |
| test_strategies.py | ~10초 | 28개 테스트 |
| test_data_loader.py | ~8초 | 26개 테스트 |
| test_async_api.py | ~2초 | 12개 테스트 (mock 사용) |
| test_result_manager.py | ~3초 | 11개 테스트 |
| **전체** | **~30초** | **98개 테스트** |

---

## 다음 단계 (Step 5)

- 운영 문서 작성
  - README 업데이트
  - operations.md (모니터링, 트러블슈팅)
  - migration_checklist.md (Phase 2→3 마이그레이션)
