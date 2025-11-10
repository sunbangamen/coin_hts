# Task 3.2: 비동기 백테스트 API 구현 보고서

**작성일**: 2025-11-08
**상태**: ✅ 완료
**담당자**: Claude Code

---

## 1. 개요

Phase 3에서는 장시간 실행되는 백테스트(1000캔들 이상, 다중 심볼)를 비동기로 처리하여 HTTP 타임아웃을 방지하고, 진행 상태를 조회할 수 있는 API를 구현합니다.

**기술 스택**: Redis Queue (RQ) + Redis

---

## 2. 아키텍처 설계

### 2.1 시스템 흐름

```
사용자 요청
  ↓
[FastAPI 엔드포인트]
  ↓ (task_id 생성 및 즉시 응답)
[응답: task_id + status=queued]
  ↓
  ├─→ [사용자: 폴링으로 상태 확인]
  │     └→ GET /api/backtests/status/{task_id}
  │       ├─ status: queued → running → completed/failed
  │       ├─ progress: 0.0 ~ 1.0
  │       └─ result: BacktestResponse (완료 시)
  │
  └─→ [백그라운드: RQ 워커]
      ├─ 1. load_ohlcv_data() (10%)
      ├─ 2. strategy.run() per symbol (70%)
      ├─ 3. calculate_metrics() (15%)
      └─ 4. save_results() (5%)
```

### 2.2 컴포넌트 구성

| 컴포넌트 | 역할 | 상태 |
|---------|------|------|
| **FastAPI 엔드포인트** | 요청 접수, 응답 반환 | ✅ 구현됨 |
| **TaskManager** | Redis 기반 작업 상태 관리 | ✅ 완성 |
| **RQ Queue** | 작업 큐, 워커 관리 | ✅ 통합 완료 |
| **run_backtest_job()** | 비동기 백테스트 실행 함수 | ✅ 완성 |
| **진행률 콜백** | 작업 진행 상황 업데이트 | ✅ 구현됨 |

---

## 3. API 명세

### 3.1 비동기 백테스트 제출

**엔드포인트**: `POST /api/backtests/run-async`

**요청**:
```json
{
  "strategy": "volume_zone_breakout",
  "params": {
    "volume_window": 10,
    "top_percentile": 0.2,
    "breakout_buffer": 0.0
  },
  "symbols": ["BTC_KRW", "ETH_KRW"],
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "timeframe": "1d"
}
```

**응답** (HTTP 200):
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "created_at": "2025-11-08T16:14:25.281Z"
}
```

**에러 응답** (HTTP 500):
```json
{
  "detail": "Failed to enqueue backtest job: ..."
}
```

### 3.2 작업 상태 조회

**엔드포인트**: `GET /api/backtests/status/{task_id}`

**응답** (HTTP 200):

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "progress": 0.65,
  "result": null,
  "error": null
}
```

**상태 종류**:
- `queued`: 큐에 대기 중
- `running`: 실행 중
- `completed`: 완료 (result 필드에 결과)
- `failed`: 실패 (error 필드에 에러 메시지)
- `cancelled`: 취소됨 (DELETE 요청으로 취소됨, error 필드에 취소 사유)

**완료 응답** (HTTP 200):
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 1.0,
  "result": {
    "version": "1.1.0",
    "run_id": "550e8400-e29b-41d4-a716-446655440000",
    "strategy": "volume_zone_breakout",
    "params": {...},
    "symbols": [...],
    "total_signals": 1520,
    "execution_time": 2.34,
    "metadata": {...}
  },
  "error": null
}
```

### 3.3 작업 취소 (Phase 3에서 추가됨)

**엔드포인트**: `DELETE /api/backtests/tasks/{task_id}`

**설명**: 제출되었거나 실행 중인 백테스트 작업을 취소합니다.

**요청**:
```bash
curl -X DELETE http://localhost:8000/api/backtests/tasks/550e8400-e29b-41d4-a716-446655440000
```

**응답** (HTTP 200):
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "cancelled",
  "created_at": "2025-11-08T16:14:25.281Z"
}
```

**에러 응답** (이미 완료된 작업, HTTP 400):
```json
{
  "detail": "Cannot cancel completed task. Only queued or running tasks can be cancelled."
}
```

**에러 응답** (작업 없음, HTTP 404):
```json
{
  "detail": "Task not found: 550e8400-e29b-41d4-a716-446655440000"
}
```

**동작 로직**:
1. 작업 상태 확인
2. `completed` 또는 `failed` 상태면 400 에러 반환
3. RQ 큐에서 job 취소 시도 (`job.cancel()`)
4. TaskManager에 에러 메시지 저장 ("Task cancelled by user")
5. 상태를 `cancelled`로 표시

---

## 4. 구현 상세

### 4.1 TaskManager (Redis 기반)

**주요 메서드**:

```python
# 작업 생성
task_id = TaskManager.create_task(
    strategy="volume_zone_breakout",
    params={...},
    symbols=["BTC_KRW"],
    start_date="2024-01-01",
    end_date="2024-12-31",
)

# 상태 업데이트
TaskManager.update_status(task_id, TaskStatus.RUNNING)

# 진행률 업데이트
TaskManager.set_progress(task_id, 0.75)  # 75% 완료

# 결과 저장
TaskManager.set_result(task_id, backtest_result)

# 에러 저장
TaskManager.set_error(task_id, "Error message")

# 상태 조회
status = TaskManager.get_status(task_id)
# → {"task_id": "...", "status": "running", "progress": 0.75, "result": null, "error": null}
```

**Redis 키 구조**:
```
task:{task_id}                 → 작업 메타데이터 (Hash, TTL: 1시간)
result:{task_id}               → 백테스트 결과 (String, JSON)
error:{task_id}                → 에러 정보 (String, JSON)
progress:{task_id}             → 진행률 (String, 0.0~1.0)
```

### 4.2 비동기 Job 함수

```python
def run_backtest_job(
    task_id: str,
    strategy: str,
    params: Dict[str, Any],
    symbols: list,
    start_date: str,
    end_date: str,
    timeframe: str = "1d",
) -> Dict[str, Any]:
    """
    비동기 백테스트 실행

    단계:
    1. 상태 업데이트: QUEUED → RUNNING
    2. 데이터 로드 (10%)
    3. 전략 인스턴스 생성
    4. 심볼별 백테스트 실행 (70%)
    5. 메트릭 계산 (15%)
    6. 결과 저장 (5%)
    """
    # 진행률 콜백
    progress_callback = create_progress_callback(task_id)

    # 단계별 처리
    TaskManager.set_progress(task_id, 0.0)
    df = load_ohlcv_data(...)
    progress_callback(0.1, "Data loaded")

    strategy = StrategyFactory.create(strategy)
    progress_callback(0.2, "Strategy created")

    # ... (심볼별 실행)

    progress_callback(0.8, "Results calculating")
    # ... (메트릭 계산)

    # 결과 저장
    TaskManager.set_result(task_id, result)
    progress_callback(1.0, "Backtest completed")
```

### 4.3 RQ 큐 통합

**main.py에 추가된 코드**:

```python
from rq import Queue
from backend.app.config import redis_conn

# RQ 큐 초기화
rq_queue = Queue(connection=redis_conn)

# 비동기 엔드포인트에서 사용
job = rq_queue.enqueue(
    run_backtest_job,
    task_id=task_id,
    strategy=request.strategy,
    params=request.params,
    symbols=request.symbols,
    start_date=request.start_date,
    end_date=request.end_date,
    timeframe=request.timeframe,
    job_id=task_id,  # 작업 ID와 job ID 일치
    timeout=3600,    # 1시간 타임아웃
)
```

---

## 5. 실행 흐름 상세

### 5.1 요청부터 완료까지

**Step 1: 사용자 요청**
```bash
curl -X POST http://localhost:8000/api/backtests/run-async \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "volume_zone_breakout",
    "symbols": ["BTC_KRW"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }'
```

**응답** (즉시):
```json
{
  "task_id": "abc123...",
  "status": "queued",
  "created_at": "2025-11-08T16:14:25Z"
}
```

**Step 2: 폴링으로 상태 확인**
```bash
# 첫 번째 요청
curl http://localhost:8000/api/backtests/status/abc123
# → {"status": "queued", "progress": 0}

# 두 번째 요청 (3초 후)
curl http://localhost:8000/api/backtests/status/abc123
# → {"status": "running", "progress": 0.25}

# 세 번째 요청 (5초 후)
curl http://localhost:8000/api/backtests/status/abc123
# → {"status": "running", "progress": 0.75}

# 마지막 요청 (완료 후)
curl http://localhost:8000/api/backtests/status/abc123
# → {"status": "completed", "progress": 1.0, "result": {...}}
```

### 5.2 진행률 상세

| 단계 | 진행률 | 작업 |
|-----|-------|------|
| 0 | 0% | 작업 시작 |
| 1 | 10% | 데이터 로드 |
| 2 | 20% | 전략 인스턴스 생성 |
| 3 | 30-70% | 심볼별 백테스트 실행 (각 심볼 10-20%) |
| 4 | 80% | 메트릭 계산 |
| 5 | 90% | 결과 저장 |
| 6 | 100% | 완료 |

---

## 6. Docker Compose 설정

### 6.1 필수 서비스

**이미 구성된 서비스**:
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    # TaskManager와 RQ Queue에서 사용

  backend:
    build: .
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
```

### 6.2 RQ Worker 실행

현재 구성에서는 FastAPI 앱이 job을 RQ Queue에 추가하면, 별도의 RQ Worker가 필요합니다.

**로컬 테스트 (Docker 외부)**:
```bash
# Worker 실행 (백그라운드)
cd /home/limeking/projects/worktree/29
source venv/bin/activate
rq worker -c backend.app.config
```

**Docker 내부 Worker** (선택사항, Phase 4):
```yaml
services:
  worker:
    build: .
    command: rq worker -c backend.app.config
    environment:
      - REDIS_HOST=redis
```

---

## 7. 테스트 계획

### 7.1 단위 테스트

```python
def test_async_backtest_api():
    """비동기 백테스트 API 테스트"""
    response = client.post(
        "/api/backtests/run-async",
        json={
            "strategy": "volume_zone_breakout",
            "symbols": ["BTC_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-02-29",
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"

    # 상태 조회
    task_id = data["task_id"]
    status_response = client.get(f"/api/backtests/status/{task_id}")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["task_id"] == task_id
    assert status["status"] in ["queued", "running", "completed", "failed"]
```

### 7.2 통합 테스트

```python
def test_async_backtest_full_flow():
    """비동기 백테스트 완전 흐름 테스트"""
    # 1. 백테스트 제출
    submit_response = client.post("/api/backtests/run-async", json={...})
    task_id = submit_response.json()["task_id"]

    # 2. 폴링으로 완료 기다리기
    max_attempts = 60  # 60초
    for i in range(max_attempts):
        status_response = client.get(f"/api/backtests/status/{task_id}")
        status = status_response.json()

        if status["status"] == "completed":
            # 3. 결과 검증
            assert "result" in status
            result = status["result"]
            assert result["strategy"] == "volume_zone_breakout"
            assert result["total_signals"] > 0
            break
        elif status["status"] == "failed":
            pytest.fail(f"Task failed: {status['error']}")

        time.sleep(1)
    else:
        pytest.fail("Task did not complete within timeout")
```

### 7.3 성능 테스트

```python
def test_async_backtest_performance():
    """비동기 백테스트 성능 테스트"""
    start_time = time.time()

    # 제출
    response = client.post("/api/backtests/run-async", json={...})
    submit_time = time.time() - start_time

    # 제출 응답 시간 < 100ms
    assert submit_time < 0.1, f"Submit took {submit_time}s"

    # 상태 조회 응답 시간 < 50ms
    task_id = response.json()["task_id"]
    query_start = time.time()
    client.get(f"/api/backtests/status/{task_id}")
    query_time = time.time() - query_start
    assert query_time < 0.05, f"Query took {query_time}s"
```

---

## 8. 주요 특징

### 8.1 장점

✅ **타임아웃 방지**
- 장시간 백테스트도 즉시 응답 (< 100ms)
- 클라이언트는 추가 대기 없음

✅ **실시간 진행 상황**
- 진행률 (0.0 ~ 1.0) 실시간 제공
- 사용자는 진행 상황 모니터링 가능

✅ **결과 조회**
- 백테스트 완료 후 결과 조회 가능
- 재실행 불필요

✅ **에러 처리**
- 작업 실패 시 에러 메시지 제공
- 작업 상태 추적 가능

### 8.2 제한사항

⚠️ **RQ Worker 별도 실행**
- 현재 FastAPI 서버와 분리
- Phase 4에서 Docker 서비스로 통합 예정

⚠️ **진행률 세밀도**
- 현재 5단계 (10%, 20%, 70%, 80%, 100%)
- 세밀한 추적이 필요할 경우 개선 필요

⚠️ **동시 작업 제한**
- RQ Worker 수에 따라 제한됨
- 기본 1개 Worker → 순차 처리

---

## 9. 향후 개선 사항 (Phase 4)

### 9.1 Docker Worker 통합
```yaml
services:
  worker:
    build: .
    command: rq worker -c backend.app.config
    depends_on:
      - redis
```

### 9.2 실시간 WebSocket 지원
```python
@app.websocket("/ws/backtest/{task_id}")
async def websocket_backtest_status(websocket: WebSocket, task_id: str):
    await websocket.accept()
    while True:
        status = TaskManager.get_status(task_id)
        await websocket.send_json(status)
        if status["status"] in ["completed", "failed"]:
            break
        await asyncio.sleep(1)
```

### 9.3 비동기 Job 취소 기능
```python
@app.delete("/api/backtests/tasks/{task_id}")
async def cancel_backtest_task(task_id: str):
    """진행 중인 백테스트 취소"""
    job = rq_queue.fetch_job(task_id)
    if job:
        job.cancel()
        TaskManager.set_error(task_id, "Task cancelled by user")
        return {"status": "cancelled"}
```

### 9.4 다중 Worker 지원
```python
# docker-compose.yml
services:
  worker-1:
    command: rq worker -c backend.app.config
  worker-2:
    command: rq worker -c backend.app.config
  worker-3:
    command: rq worker -c backend.app.config
```

---

## 10. 결론

### 10.1 Task 3.2 완료 상태

✅ **완료 정의(DoD) 충족**:

- [x] **기술 스택 선정**
  - [x] RQ (Redis Queue) 선택 ✅
  - [x] Docker Compose에 Redis 이미 구성됨 ✅

- [x] **API 엔드포인트 구현**
  - [x] `POST /api/backtests/run-async` ✅
  - [x] `GET /api/backtests/status/{task_id}` ✅

- [x] **Celery Task 구현**
  - [x] `run_backtest_job()` 함수 ✅
  - [x] 진행 상황 업데이트 콜백 ✅
  - [x] RQ 큐 통합 ✅

- [x] **Frontend 연동** (기초)
  - [x] API 스펙 문서화 완료 ✅
  - [x] 폴링 기반 상태 조회 가능 ✅

- [x] **테스트 계획**
  - [x] 단위 테스트 계획 작성 ✅
  - [x] 통합 테스트 계획 작성 ✅
  - [x] 성능 테스트 계획 작성 ✅

- [x] **산출물**
  - [x] `backend/app/main.py` (RQ 통합 완료) ✅
  - [x] `backend/app/task_manager.py` (완성) ✅
  - [x] `backend/app/jobs.py` (완성) ✅
  - [x] 본 문서 작성 완료 ✅

### 10.2 다음 단계

**Task 3.3: 포지션 관리 기능 구현**으로 진행

---

## 부록: 사용 예시

### 예시 1: 단순 비동기 백테스트

```bash
# 요청 제출
RESPONSE=$(curl -X POST http://localhost:8000/api/backtests/run-async \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "volume_zone_breakout",
    "symbols": ["BTC_KRW"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }')

TASK_ID=$(echo $RESPONSE | jq -r '.task_id')

# 상태 폴링
for i in {1..60}; do
  STATUS=$(curl -s http://localhost:8000/api/backtests/status/$TASK_ID | jq -r '.status')
  PROGRESS=$(curl -s http://localhost:8000/api/backtests/status/$TASK_ID | jq -r '.progress')

  echo "[$i] Status: $STATUS, Progress: $PROGRESS"

  if [ "$STATUS" = "completed" ]; then
    echo "✅ Backtest completed!"
    curl -s http://localhost:8000/api/backtests/status/$TASK_ID | jq '.result'
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "❌ Backtest failed!"
    curl -s http://localhost:8000/api/backtests/status/$TASK_ID | jq '.error'
    break
  fi

  sleep 1
done
```

### 예시 2: Python 클라이언트

```python
import requests
import time
from typing import Optional, Dict

class AsyncBacktestClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    def submit_backtest(self, strategy: str, symbols: list,
                       start_date: str, end_date: str) -> str:
        """백테스트 제출"""
        response = requests.post(
            f"{self.base_url}/api/backtests/run-async",
            json={
                "strategy": strategy,
                "symbols": symbols,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        return response.json()["task_id"]

    def wait_for_completion(self, task_id: str, timeout: int = 300) -> Dict:
        """완료까지 대기"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            response = requests.get(
                f"{self.base_url}/api/backtests/status/{task_id}"
            )
            status = response.json()

            print(f"Status: {status['status']}, Progress: {status['progress']:.0%}")

            if status["status"] == "completed":
                return status["result"]
            elif status["status"] == "failed":
                raise Exception(f"Task failed: {status['error']}")

            time.sleep(1)

        raise TimeoutError(f"Task did not complete within {timeout}s")

# 사용
client = AsyncBacktestClient()
task_id = client.submit_backtest(
    strategy="volume_zone_breakout",
    symbols=["BTC_KRW", "ETH_KRW"],
    start_date="2024-01-01",
    end_date="2024-12-31"
)

result = client.wait_for_completion(task_id)
print(f"Total signals: {result['total_signals']}")
print(f"Execution time: {result['execution_time']}s")
```

---

## 문서 버전 히스토리

| 일자 | 버전 | 변경 사항 |
|------|------|---------|
| 2025-11-08 | 1.0 | 초기 작성, Task 3.2 완료 |

