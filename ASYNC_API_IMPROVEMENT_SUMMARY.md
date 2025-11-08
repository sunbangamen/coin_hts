# Task 3.2 비동기 API - 테스트 재현성 및 검증 강화

**작성일**: 2025-11-08 18:00 UTC
**상태**: ✅ 완료
**범위**: Message 9 추가 개선사항 구현

---

## 📋 개요

초기 완료된 Task 3.2 정제 작업에 이어, 다음 두 가지 영역을 심화 개선했습니다:

1. **테스트 실행 명령 재현성 확보**
2. **취소 로직 검증 강화**

---

## ✅ 개선사항 1: 테스트 실행 명령 재현성 확보

### 문제점
- 각 문서에서 테스트 실행 명령이 불일치
- PYTHONPATH 설정 없어 import 경로 불명확
- 누구나 동일하게 재현할 수 없음

### 해결책

#### 표준 명령어 정의
```bash
source venv/bin/activate && export PYTHONPATH=. && python -m pytest tests/test_async_api.py::TestCancelBacktestTask -v
```

#### 문서 일관성 확보
| 문서 | 상태 |
|------|------|
| TEST_RESULTS_SUMMARY.md | ✅ 표준 명령어 적용 |
| ASYNC_API_REFINEMENT_SUMMARY.md | ✅ 표준 명령어 적용 |
| PHASE3_IMPLEMENTATION_STATUS.md | ✅ 표준 명령어 추가 |

**핵심 요소**:
- `source venv/bin/activate`: Python 가상환경 활성화
- `export PYTHONPATH=.`: repo 루트를 sys.path에 포함
- `python -m pytest ...`: pytest 실행

### 검증 결과
```
======================== 6 passed, 24 warnings in 0.87s ========================
```

모든 문서에서 동일한 명령으로 재현 가능 ✅

---

## ✅ 개선사항 2: 취소 로직 검증 강화

### 문제점
- TaskManager.cancel_task를 전면 patch (실제 구현 미실행)
- Redis에 상태가 실제로 저장되는지 검증 불가
- 테스트가 API 응답만 확인

### 해결책

#### A. InMemoryRedis 헬퍼 클래스 구현

**파일**: `tests/conftest.py` (신규 추가)

```python
class InMemoryRedis:
    """메모리 기반 Redis 구현 (테스트용)"""

    def __init__(self):
        self._data = {}          # String 저장소
        self._hashes = {}        # Hash 저장소
        self._ttl = {}           # TTL 정보

    def hset(self, name, key, value):
        """Hash 필드 설정"""
        if name not in self._hashes:
            self._hashes[name] = {}
        self._hashes[name][key] = value
        return 1

    def hget(self, name, key):
        """Hash 필드 조회"""
        if name in self._hashes and key in self._hashes[name]:
            return self._hashes[name][key]
        return None

    def hgetall(self, name):
        """Hash 전체 조회"""
        return self._hashes.get(name, {})

    def set(self, key, value):
        """String 값 설정"""
        self._data[key] = value
        return True

    def get(self, key):
        """String 값 조회"""
        return self._data.get(key)

    def expire(self, key, seconds):
        """TTL 설정"""
        self._ttl[key] = seconds
        return 1

    def flushdb(self):
        """데이터베이스 초기화"""
        self._data.clear()
        self._hashes.clear()
        self._ttl.clear()
```

**특징**:
- ✅ 실제 Redis와 동일한 인터페이스
- ✅ 메모리 기반 저장소로 상태 변경 추적 가능
- ✅ 다른 모든 테스트도 사용 가능

#### B. mock_redis_and_queue 픽스처 개선

**변경 전**:
```python
@pytest.fixture(autouse=True)
def mock_redis_and_queue():
    with patch("backend.app.config.redis_conn") as mock_redis, \
         patch("backend.app.main.redis_conn") as mock_redis_main, \
         patch("backend.app.task_manager.redis_conn") as mock_redis_tm, \
         patch("backend.app.main.rq_queue") as mock_queue, \
         patch("backend.app.task_manager.TaskManager.cancel_task") as mock_cancel:

        # MagicMock 설정...
        mock_cancel.return_value = None
        yield {...}
```

**변경 후**:
```python
@pytest.fixture(autouse=True)
def mock_redis_and_queue():
    in_memory_redis = InMemoryRedis()  # ← 변경!

    with patch("backend.app.config.redis_conn", in_memory_redis), \
         patch("backend.app.main.redis_conn", in_memory_redis), \
         patch("backend.app.task_manager.redis_conn", in_memory_redis), \
         patch("backend.app.main.rq_queue") as mock_queue:
        # TaskManager.cancel_task 패치 제거! ← 변경!

        yield {
            "redis": in_memory_redis,
            "queue": mock_queue,
            "job": mock_job,
        }
```

**차이점**:
1. ✅ TaskManager.cancel_task 패치 **제거** → 실제 구현 실행
2. ✅ MagicMock 대신 InMemoryRedis 사용 → 상태 변경 추적
3. ✅ 세 곳의 redis_conn을 동일 인스턴스로 통일

#### C. 헬퍼 픽스처 추가

```python
@pytest.fixture
def in_memory_redis_instance(mock_redis_and_queue):
    """Redis 인스턴스에 직접 접근"""
    return mock_redis_and_queue["redis"]

@pytest.fixture
def setup_task_in_redis(in_memory_redis_instance):
    """Redis에 작업 상태 직접 설정"""
    def _setup(task_id, status="queued", progress=0.0):
        task_key = f"task:{task_id}"
        # mapping 파라미터로 여러 필드를 한 번에 설정
        in_memory_redis_instance.hset(task_key, mapping={
            "status": status,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "progress": str(progress)
        })
        # progress:{task_id} String에도 저장
        in_memory_redis_instance.set(f"progress:{task_id}", str(progress))
        return task_id
    return _setup
```

#### D. InMemoryRedis Redis 호환성 강화

**개선 사항**:
- `hset()` 메서드가 Redis와 동일한 세 가지 호출 방식 지원:
  1. `hset(name, key, value)` - 단일 필드
  2. `hset(name, mapping={...})` - 여러 필드 동시 설정
  3. `hset(name, key, value, mapping={...})` - 둘 다 동시 설정

**구현**:
```python
def hset(self, name, key=None, value=None, mapping=None):
    """Hash 필드 설정 (Redis 호환)"""
    if name not in self._hashes:
        self._hashes[name] = {}

    added_count = 0

    # mapping 방식: 여러 필드 동시 설정 (Redis 표준)
    if mapping is not None:
        for field, val in mapping.items():
            if field not in self._hashes[name]:
                added_count += 1
            self._hashes[name][field] = val

    # key/value 방식: 단일 필드 설정
    if key is not None:
        if key not in self._hashes[name]:
            added_count += 1
        self._hashes[name][key] = value

    # Redis 호환: 정확히 추가된 필드 수만 반환
    return added_count
```

**테스트 커버리지**:
```python
def test_in_memory_redis_hset_compatibility():
    """InMemoryRedis.hset이 Redis 호환성을 갖는지 검증"""
    redis = InMemoryRedis()

    # 단일 필드 설정 (추가 → 반환값 1)
    assert redis.hset("test_hash", "field1", "value1") == 1

    # 같은 필드 업데이트 (업데이트 → 반환값 0)
    assert redis.hset("test_hash", "field1", "updated") == 0

    # mapping으로 여러 필드 설정 (추가 2개 → 반환값 2)
    assert redis.hset("test_hash", mapping={"field2": "v2", "field3": "v3"}) == 2

    # key/value + mapping 동시 설정 (추가 2개 → 반환값 2)
    assert redis.hset("test_hash", "field4", "v4", mapping={"field5": "v5"}) == 2
```

**사용 예시**:
```python
def test_cancel_queued_task_success(self, setup_task_in_redis):
    task_id = str(uuid.uuid4())

    # 1. Redis에 초기 상태 설정
    setup_task_in_redis(task_id, status="queued", progress=0.0)

    # 2. API 호출
    response = client.delete(f"/api/backtests/tasks/{task_id}")

    # 3. Redis 상태 검증
    task_key = f"task:{task_id}"
    stored_status = in_memory_redis_instance.hget(task_key, "status")
    assert stored_status == TaskStatus.CANCELLED.value
```

#### D. 취소 테스트 6개 모두 개선

**개선된 테스트**:

| 테스트 | 초기 상태 | 검증 내용 |
|--------|----------|---------|
| test_cancel_queued_task_success | queued | ✅ Redis에 cancelled 저장 |
| test_cancel_running_task_success | running | ✅ Redis에 cancelled 저장 |
| test_cancel_completed_task_fails | completed | ✅ 400 응답 + 상태 변경 없음 |
| test_cancel_failed_task_fails | failed | ✅ 400 응답 + 상태 변경 없음 |
| test_cancel_nonexistent_task | (없음) | ✅ 404 응답 + Redis 확인 |
| test_cancel_and_verify_state_consistency | queued | ✅ DELETE/GET 상태 일관성 |

### 검증 결과

**실행 명령어**:
```bash
source venv/bin/activate && export PYTHONPATH=. && python -m pytest tests/test_async_api.py::TestCancelBacktestTask -v
```

**결과**:
```
tests/test_async_api.py::TestCancelBacktestTask::test_cancel_queued_task_success PASSED
tests/test_async_api.py::TestCancelBacktestTask::test_cancel_running_task_success PASSED
tests/test_async_api.py::TestCancelBacktestTask::test_cancel_completed_task_fails PASSED
tests/test_async_api.py::TestCancelBacktestTask::test_cancel_failed_task_fails PASSED
tests/test_async_api.py::TestCancelBacktestTask::test_cancel_nonexistent_task PASSED
tests/test_async_api.py::TestCancelBacktestTask::test_cancel_and_verify_state_consistency PASSED

======================== 6 passed, 24 warnings in 0.87s ========================
```

---

## 📊 영향받은 파일

### 수정 파일 (5개)

1. **tests/conftest.py**
   - InMemoryRedis 클래스 추가 (79줄)
   - mock_redis_and_queue 픽스처 개선 (TaskManager.cancel_task 패치 제거)
   - in_memory_redis_instance 픽스처 추가
   - setup_task_in_redis 헬퍼 픽스처 추가

2. **tests/test_async_api.py**
   - TestCancelBacktestTask 클래스 전체 개선
   - 모든 6개 테스트에 Redis 상태 검증 추가
   - monkeypatch 제거, setup_task_in_redis 사용

3. **TEST_RESULTS_SUMMARY.md**
   - 표준 실행 명령어 추가 (export PYTHONPATH=.)
   - 개선 전/후 결과 비교
   - 주요 개선사항 기록

4. **ASYNC_API_REFINEMENT_SUMMARY.md**
   - 실행 명령어 표준화
   - 최종 실행 결과 기록 (0.87초)
   - 개선 사항 상세 설명

5. **PHASE3_IMPLEMENTATION_STATUS.md**
   - 정제 작업 섹션 업데이트
   - PYTHONPATH 표준화 추가

### 신규 파일 (1개)

1. **ASYNC_API_IMPROVEMENT_SUMMARY.md** (본 문서)
   - 추가 개선사항 상세 기록

---

## 🎯 체크리스트

### 재현성 확보

- [x] 표준 실행 명령어 정의 (export PYTHONPATH=.)
- [x] 모든 문서에 동일한 명령어 적용
- [x] 실행 타임스탐프 기록
- [x] 누구나 동일하게 재현 가능

### 검증 강화

- [x] InMemoryRedis 헬퍼 클래스 구현
- [x] TaskManager.cancel_task 실제 실행 (patch 제거)
- [x] 각 테스트에 Redis 상태 검증 추가
- [x] 초기 상태 설정 헬퍼 추가
- [x] 모든 테스트 통과 확인 (6/6)

### 문서화

- [x] 실행 명령어 일관성 확보
- [x] 개선 전/후 결과 기록
- [x] 기술 결정사항 문서화
- [x] 영향받은 파일 명시

---

## 📈 최종 성과

| 항목 | 개선 전 | 개선 후 | 변화 |
|------|--------|--------|------|
| **테스트 통과** | 6/6 | 6/6 | ✅ 유지 |
| **Redis 상태 검증** | 없음 | 모든 테스트 | ✅ 추가 |
| **재현성** | 낮음 | 높음 | ✅ 개선 |
| **TaskManager.cancel_task 실행** | patch 됨 | 실제 실행 | ✅ 개선 |
| **실행 속도** | 0.53초 | 0.87초 | ⚠️ 약간 증가 (검증 추가로 인함) |

---

## 💡 기술 교훈

### 1. 테스트 재현성의 중요성
- 명확한 실행 명령어 문서화 필수
- 환경 변수(PYTHONPATH) 명시적 설정
- 모든 문서에서 일관된 지침 제공

### 2. Mock vs 실제 구현
- 상태 검증이 필요하면 실제 구현 실행 고려
- patch 제거 시 의존성 고려 필수 (InMemoryRedis)
- 테스트 자체가 비즈니스 로직 검증

### 3. 헬퍼 함수의 역할
- 초기 상태 설정 자동화 (setup_task_in_redis)
- 인스턴스 직접 접근 용이 (in_memory_redis_instance)
- 테스트 코드 가독성 향상

---

## 🚀 다음 단계

Task 3.2는 다음 수준에서 완성되었습니다:

**Level 1** ✅ 기본 구현: 비동기 API 3개 엔드포인트 (제출/조회/취소)
**Level 2** ✅ 정제 작업: 상태 스키마/문서 동기화, 테스트 안정화
**Level 3** ✅ 심화 개선: **테스트 재현성 확보, 검증 강화** ← 완료

### Week 2 준비
- Task 3.3: 포지션 관리 기능 구현
- Task 3.4: 외부 스토리지 연동 (S3)

---

**최종 상태**: ✅ **Phase 3 Task 3.2 고도화 완성**
**다음 회의**: 2025-11-14 (Week 2 시작 - Task 3.3)
