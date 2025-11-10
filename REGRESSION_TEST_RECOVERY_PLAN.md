# Phase 3 회귀 테스트 복구 계획 (Task 3.5 중심)

**작성일**: 2025-11-10
**상태**: 📋 계획 수립 및 분석 단계
**목표**: 203/203 테스트 100% 통과 (현재: 192/203, 94.6%)

---

## 📊 실패 테스트 현황 (11건)

### 1. test_result_manager.py (4건 실패)

#### 실패 케이스
```
- test_save_manifest_file
- test_save_manifest_file_with_error
- test_cleanup_old_results_dry_run
- test_cleanup_skips_recent_results
```

#### 원인 분석
```
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/tmp.../tasks/manifest-test-id/manifest.json'
```

**근본 원인**:
- ResultManager.save_manifest_file() 에서 디렉토리 자동 생성 없이 파일 저장 시도
- 테스트 픽스처에서 임시 디렉토리 구조가 미리 생성되지 않음
- 결과 저장소 레이어 재구조화 필요 (JSON → PostgreSQL + Parquet)

#### 영향도
- 백테스트 결과 저장 및 정리 기능 장애
- 결과 매니페스트 생성 실패
- 기존 결과 정리(cleanup) 로직 미작동

---

### 2. test_strategy_runner.py (7건 실패)

#### 실패 케이스
```
- test_initialize_strategy_with_history
  → ValueError: day is out of range for month
  → 테스트 데이터 생성 시 invalid 날짜 사용

- test_process_candle_single_strategy
- test_process_candle_multiple_strategies
- test_process_candle_no_signal
- test_process_candle_uninitialized_strategy
- test_process_candle_different_symbol
  → TypeError: CandleData.__init__() missing 1 required positional argument: 'timeframe'
  → CandleData 객체 생성 시 timeframe 인자 누락

- test_on_signal_generated_no_callback
  → AssertionError: Expected 'insert_signal' to have been called once. Called 0 times.
  → PositionManager 콜백 호출 미비
```

#### 원인 분석

**root cause 1: CandleData 스키마 변경**
- CandleData 클래스에 `timeframe` 필드 추가됨
- 테스트에서는 여전히 기존 스키마 사용

**root cause 2: StrategyRunner와 결과 저장 의존성**
- StrategyRunner가 ResultManager에 의존
- ResultManager.save_manifest_file() 실패로 인한 cascade 오류

**root cause 3: 픽스처 문제**
- 테스트 데이터가 outdated
- Dependency Injection 부재로 mock 주입 불가

#### 영향도
- 전략 초기화 및 캔들 처리 로직 미검증
- 신호 생성 및 포지션 관리 통합 실패
- e2e 테스트 불가

---

## 🎯 Task 3.5: 결과 저장 파이프라인 개편

### 목표
- JSON index.json 기반 저장소 → PostgreSQL 메타데이터 + Parquet 파일 저장소로 전환
- 테스트 환경에서는 SQLite 또는 InMemory 사용
- ResultManager 레이어 완전 재구조화

### 구현 계획

#### Phase 1: 새로운 저장소 레이어 설계
```python
# backend/app/storage/result_storage.py (NEW)

class ResultStorage(ABC):
    """결과 저장 추상 인터페이스"""

    async def save_result(self, task_id: str, data: dict) -> bool:
        """결과 저장"""
        pass

    async def get_result(self, task_id: str) -> dict:
        """결과 조회"""
        pass

    async def cleanup_old_results(self, days: int = 7) -> int:
        """N일 이상된 결과 삭제"""
        pass

class PostgreSQLResultStorage(ResultStorage):
    """PostgreSQL + Parquet 기반 저장소"""
    pass

class SQLiteResultStorage(ResultStorage):
    """테스트용 SQLite 저장소"""
    pass
```

#### Phase 2: ResultManager 리팩터링
```python
# backend/app/result_manager.py (REFACTORED)

class ResultManager:
    def __init__(self, storage: ResultStorage):
        self.storage = storage  # Dependency Injection

    async def save_manifest_file(self, ...):
        """새 저장소 레이어 사용"""
        return await self.storage.save_result(...)
```

#### Phase 3: 테스트 픽스처 개선
```python
# tests/conftest.py (UPDATED)

@pytest.fixture
def temp_result_storage(tmp_path):
    """테스트용 임시 결과 저장소"""
    return SQLiteResultStorage(db_path=tmp_path / "results.db")

@pytest.fixture
def result_manager(temp_result_storage):
    """의존성 주입된 ResultManager"""
    return ResultManager(storage=temp_result_storage)
```

---

## 🔄 Task 3.5와 연계된 전략 러너 테스트 수정

### 핵심: Dependency Injection 도입

#### 현재 구조 (문제점)
```python
class StrategyRunner:
    def __init__(self):
        self.result_manager = ResultManager()  # 직접 의존
```

#### 개선된 구조
```python
class StrategyRunner:
    def __init__(self,
                 result_manager: ResultManager = None,
                 position_manager: PositionManager = None):
        self.result_manager = result_manager or ResultManager()
        self.position_manager = position_manager or PositionManager()
```

#### 테스트 적용
```python
def test_process_candle_single_strategy():
    # Stub 생성
    mock_result_manager = MagicMock(spec=ResultManager)
    mock_position_manager = MagicMock(spec=PositionManager)

    # 의존성 주입
    runner = StrategyRunner(
        result_manager=mock_result_manager,
        position_manager=mock_position_manager
    )

    # 테스트 실행
    runner.process_candle(...)

    # 검증
    mock_position_manager.on_signal.assert_called_once()
```

---

## 📋 세부 개선 사항별 계획

### 1. test_result_manager.py 수정

#### 1.1 test_save_manifest_file
```python
def test_save_manifest_file(temp_result_storage):
    """매니페스트 저장 테스트"""
    # 임시 디렉토리 자동 생성됨 (SQLiteResultStorage 사용)
    result = temp_result_storage.save_result(
        task_id="test-id",
        data={
            "strategy": "VolumeZoneBreakout",
            "symbol": "KRW-BTC",
            ...
        }
    )
    assert result is True

    # 저장된 결과 검증
    saved = temp_result_storage.get_result("test-id")
    assert saved["task_id"] == "test-id"
```

#### 1.2 test_cleanup_old_results_dry_run
```python
def test_cleanup_old_results_dry_run(temp_result_storage):
    """cleanup dry-run 테스트"""
    # 오래된 결과 저장 (8일 전)
    old_task_id = "old-task"
    temp_result_storage.save_result(old_task_id, {...})
    temp_result_storage._set_created_date(old_task_id,
                                          datetime.utcnow() - timedelta(days=8))

    # dry-run 실행 (실제 삭제 안 함)
    count = temp_result_storage.cleanup_old_results(
        days=7,
        dry_run=True
    )
    assert count == 1

    # 데이터는 여전히 존재
    assert temp_result_storage.get_result(old_task_id) is not None
```

### 2. test_strategy_runner.py 수정

#### 2.1 CandleData 스키마 업데이트
```python
# tests/test_strategy_runner.py 픽스처

@pytest.fixture
def candle_data():
    """CandleData 객체 생성"""
    return CandleData(
        symbol="KRW-BTC",
        timeframe="1h",  # 추가: timeframe 필수
        timestamp=datetime(2024, 1, 1),
        open=50000,
        high=51000,
        low=49000,
        close=50500,
        volume=1000
    )
```

#### 2.2 test_initialize_strategy_with_history 수정
```python
def test_initialize_strategy_with_history():
    """유효한 날짜로 수정"""
    candles = []
    for i in range(1, 29):  # 1-28일 (유효한 범위)
        candles.append(CandleData(
            symbol="KRW-BTC",
            timeframe="1h",
            timestamp=datetime(2024, 1, i),  # ✅ 2024년 1월 1-28일
            open=50000, high=51000, low=49000, close=50500, volume=1000
        ))

    runner = StrategyRunner()
    runner.initialize(strategy=strategy, candles=candles)
    assert len(runner.strategies) == 1
```

#### 2.3 test_on_signal_generated_no_callback 수정
```python
def test_on_signal_generated_no_callback(mock_position_manager):
    """콜백 없이 신호 생성"""
    runner = StrategyRunner(
        position_manager=mock_position_manager  # 주입
    )

    # 신호 발생
    runner.on_signal_generated(signal={
        "strategy_id": "test",
        "symbol": "KRW-BTC",
        "action": "BUY",
        ...
    })

    # PositionManager 호출 검증
    mock_position_manager.on_signal.assert_called_once()
```

---

## ✅ 검증 루틴

### 단계 1: 로컬 테스트 (개발자)
```bash
# 1. pytest 실행
./scripts/run_pytest.sh

# 2. 문서 동기화
python scripts/generate_phase3_status.py \
  --input /tmp/test_results_latest.json \
  --update-docs

# 3. 검증
python scripts/verify_status_consistency.py --strict
```

### 단계 2: 회귀 테스트 집중 (Task 3.5 진행 중)
```bash
# test_result_manager.py만 실행
pytest tests/test_result_manager.py -v

# test_strategy_runner.py만 실행
pytest tests/test_strategy_runner.py -v

# 통과 시에만 전체 실행
pytest tests/ -q
```

### 단계 3: 최종 검증 (203/203 통과)
```bash
./scripts/run_pytest.sh && \
  python scripts/generate_phase3_status.py \
    --input /tmp/test_results_latest.json \
    --update-docs && \
  python scripts/verify_status_consistency.py --strict && \
  git diff && git add -A && git commit
```

---

## 📝 문서 업데이트

### PHASE3_IMPLEMENTATION_STATUS.md에 추가
```markdown
### ⏳ Task 3.5: 결과 저장 파이프라인 개편 (진행 중)

**상태**: 진행 중 (회귀 테스트 복구 중)

**작업 내용**:
- ResultManager 리팩터링: JSON → PostgreSQL + Parquet
- Dependency Injection으로 테스트성 개선
- SQLite mock 저장소로 빠른 테스트 초기화
- 기존 test_result_manager.py 11건 중 4건 수정
- test_strategy_runner.py 7건 수정

**진행률**: 0% → 진행 중

**예상 완료**: 2025-11-17
```

### DOCUMENTATION_SYNCHRONIZATION_GUIDE.md에 추가
```markdown
## 회귀 테스트 복구 절차 (Task 3.5)

### 1. 로컬 개발 시
```bash
# 집중 테스트
pytest tests/test_result_manager.py -v
pytest tests/test_strategy_runner.py -v

# 부분 통과 시에만
python scripts/generate_phase3_status.py --input /tmp/test_results_latest.json --update-docs

# 전체 통과 시
./scripts/run_pytest.sh && python scripts/verify_status_consistency.py --strict
```

### 2. 완료 후
```bash
# git diff로 변경사항 확인
git diff PHASE3_IMPLEMENTATION_STATUS.md

# 커밋
git add -A && git commit -m "fix: 회귀 테스트 11건 복구 (Task 3.5)"
```
```

---

## 🚀 다음 단계

### Immediate (지금 진행)
- [ ] test_result_manager.py의 4개 실패 케이스 분석 및 수정
- [ ] test_strategy_runner.py의 7개 실패 케이스 분석 및 수정
- [ ] 로컬 pytest 실행으로 통과 검증

### Short-term (Task 3.5 완료 후)
- [ ] 203/203 테스트 100% 통과 확인
- [ ] 문서 자동 갱신 (192 → 203)
- [ ] git commit 및 git push

### Long-term (Phase 3 완료)
- [ ] Task 3.6-3.8 수행
- [ ] Phase 3 최종 리포트 작성
- [ ] CI/CD 파이프라인 통합

---

**상태**: 📋 계획 수립 완료
**마지막 업데이트**: 2025-11-10
**담당자**: Claude Code (AI Assistant)
