# Task 3.5: 결과 저장 성능 검증 보고서

**PostgreSQL + Parquet 마이그레이션 성능 평가 (실제 구현 기반)**

---

## ⚠️ 중요 공지

이 문서는 **성능 검증 계획 및 목표**를 나타냅니다.
실제 성능 수치는 실제 환경에서 벤치마크 스크립트 실행 후 측정되어야 합니다.

---

## 1. 성능 검증 개요

### 1.1 검증 목표

PostgreSQL + Parquet 마이그레이션이 다음 성능 목표를 달성하도록 설계됨:

| 지표 | 목표 | 검증 방법 |
|------|------|---------|
| 압축률 | ≥95% | `scripts/benchmark_result_storage.py` |
| 조회 성능 | JSON과 동등 이상 | PostgreSQL 쿼리 성능 측정 |
| 마이그레이션 성공률 | ≥95% | `scripts/migrate_json_to_parquet.py` --dry-run |
| 테스트 통과 | 299개 테스트 모두 통과 (2025-11-11 기준) | `pytest tests/` 또는 `scripts/count_tests.py` |

---

## 2. 테스트 시나리오

### 2.1 시나리오 1: JSON → Parquet 변환

**목적**: JSON 데이터가 Parquet으로 정확하게 변환되는지 검증

**테스트 절차**:
```
1. 샘플 JSON 생성 (10,000개 신호)
2. JSON → Parquet 변환
3. Parquet → JSON 역변환
4. 데이터 동일성 확인
```

**예상 결과**:
- 데이터 손실 없음
- 메타데이터 정확성 보증
- 압축률 ≥95%

---

### 2.2 시나리오 2: PostgreSQL 저장 및 조회

**목적**: PostgreSQL에 메타데이터 저장 및 조회 성능 검증

**테스트 절차**:
```
1. 백테스트 실행 결과 생성
2. PostgreSQL + Parquet에 저장
3. task_id로 메타데이터 조회
4. Parquet 파일 읽기
5. 데이터 병합 및 반환
```

**성능 지표**:
- 저장 시간: < 5초 (10,000 신호)
- 조회 시간: < 2초
- 메타데이터 검색: < 100ms

---

### 2.3 시나리오 3: 기존 데이터 마이그레이션

**목적**: 대량의 기존 JSON 파일을 마이그레이션하고 성공률 검증

**테스트 절차**:
```
1. 테스트 JSON 파일 100개 생성
2. migrate_json_to_parquet.py 실행
3. 성공/실패 개수 기록
4. 압축율 및 소요 시간 측정
```

**성공 기준**:
- 성공률 ≥95%
- 평균 처리 시간 < 1초/파일
- 데이터 무결성 보증

---

## 3. 성능 지표 분석

### 3.1 압축률 (Compression Ratio)

**정의**:
```
압축률 = (원본 크기 - 압축 크기) / 원본 크기 × 100%
```

**측정 방법**:

다음 벤치마크 스크립트를 실행하여 실제 환경에서 측정해야 합니다:
```bash
python scripts/benchmark_result_storage.py --num-signals 10000
```

**성능 목표**:

| 신호 수 | 목표 압축률 | 측정 상태 |
|---------|-----------|---------|
| 1,000 | ≥95% | 🔄 미측정 |
| 10,000 | ≥95% | 🔄 미측정 |
| 100,000 | ≥95% | 🔄 미측정 |

**참고**: 실제 압축률은 데이터 특성(신호 수, 메타데이터 크기, 수치 정밀도)에 따라 달라집니다.

---

### 3.2 조회 성능 (Query Performance)

**메타데이터 조회**:
```sql
SELECT task_id, strategy, status, created_at, file_size
FROM backtest_results
WHERE created_at > NOW() - INTERVAL '7 days'
ORDER BY created_at DESC
LIMIT 100
```

**예상 성능**:
- 인덱스 활용: `idx_backtest_results_created_at`
- 예상 응답 시간: < 100ms
- 처리량: > 1000 queries/sec

---

## 4. 테스트 커버리지

### 4.1 단위 테스트 (실제 구현)

| 모듈 | 테스트 케이스 | 구현 상태 |
|------|----------|---------|
| test_converters.py | 11개 | ✅ |
| test_postgresql_result_storage.py | 13개 | ✅ |
| test_result_storage_migration.py | 10개 | ✅ |

**총 테스트**: **299개** (모두 구현 완료, 2025-11-11 기준, scripts/count_tests.py 참조)

### 4.2 테스트 실행 방법

```bash
# 모든 테스트 실행
pytest tests/ -v

# 특정 모듈 테스트
pytest tests/test_converters.py -v
pytest tests/test_postgresql_result_storage.py -v
pytest tests/integration/test_result_storage_migration.py -v

# 커버리지 확인
pytest tests/ --cov=backend.app.storage
```

---

## 5. 구현 검증

### 5.1 구현된 기능

Task 3.5에서 구현한 핵심 기능:

| 기능 | 구현 상태 | 테스트 |
|------|---------|--------|
| PostgreSQL 스키마 | ✅ | test_converters.py |
| Parquet 변환 | ✅ | test_converters.py (11개) |
| ResultStorage 인터페이스 | ✅ | test_postgresql_result_storage.py (13개) |
| PostgreSQLResultStorage | ✅ | test_postgresql_result_storage.py |
| 마이그레이션 스크립트 | ✅ | 배치/강제 옵션 구현 완료 |
| Dual-write 모드 | ✅ | ResultManager에 구현, 테스트 포함 |
| 성능 벤치마크 | ✅ | scripts/benchmark_result_storage.py |

### 5.2 구현 상태 확인

✅ Task 3.5 관련 모든 코드가 실제로 구현됨:
- 마이그레이션 스크립트의 배치 처리 실제 구현
- 강제 옵션 (--force) 실제 구현
- ResultManager의 RESULT_STORAGE_MODE 환경변수 지원
- dual-write 로직 구현

⚠️ **주의**: 성능 수치는 이 문서에 기록된 목표값입니다. 실제 측정 결과는 벤치마크 스크립트 실행 후 업데이트되어야 합니다.

---

## 6. Blue-Green 배포 전략

### 6.1 배포 단계

#### Phase 1: JSON-only (현재)
- 기존 JSON 저장소만 사용

#### Phase 2: Dual-write (마이그레이션)
- 새로운 결과는 PostgreSQL + Parquet에 저장
- 기존 결과는 JSON으로도 백업

#### Phase 3: PostgreSQL/Parquet-only (전환)
- 모든 조회를 PostgreSQL + Parquet으로 변경

#### Phase 4: JSON Archive (정리)
- JSON을 오프라인 저장소로 이동

---

## 7. 권장사항

### 7.1 단기 (1-2주)

1. **모든 테스트 통과 확인**
   ```bash
   pytest tests/ -v
   ```

2. **성능 벤치마크 실행**
   ```bash
   python scripts/benchmark_result_storage.py --num-signals 10000
   ```

3. **테스트 환경에서 마이그레이션 연습**
   ```bash
   python scripts/migrate_json_to_parquet.py --dry-run
   ```

---

## 8. 결론 및 다음 단계

### 8.1 구현 완료 현황

PostgreSQL + Parquet 마이그레이션의 **핵심 인프라는 모두 구현 완료**되었습니다:

| 항목 | 상태 |
|------|------|
| **스키마 설계** | ✅ 완료 (RESULT_STORAGE_SCHEMA.md) |
| **마이그레이션 도구** | ✅ 완료 (배치/강제 옵션 포함) |
| **저장소 구현** | ✅ 완료 (PostgreSQLResultStorage) |
| **Dual-write 기능** | ✅ 완료 (ResultManager에 환경변수 지원) |
| **테스트 코드** | ✅ 완료 (34개 테스트) |
| **성능 벤치마크** | ✅ 스크립트 제공 (실제 실행 필요) |

### 8.2 성능 목표 (설계 기반)

| 지표 | 목표 | 검증 방법 |
|------|------|---------|
| **압축률** | ≥95% | `scripts/benchmark_result_storage.py` 실행 |
| **조회 성능** | JSON 동등 이상 | PostgreSQL 쿼리 성능 측정 |
| **마이그레이션 성공률** | ≥95% | `migrate_json_to_parquet.py --dry-run` |
| **테스트** | 34개 모두 통과 | `pytest tests/` |

### 8.3 다음 단계

**즉시 (1주일):**
1. 테스트 환경에서 성능 벤치마크 실행
2. 실제 PostgreSQL 환경에서 마이그레이션 시뮬레이션
3. Blue-Green 배포 절차 문서화

**단기 (2-4주):**
1. 운영 환경에 Phase 1 배포 준비 (JSON-only)
2. Phase 2 배포 (Dual-write) 계획
3. 기존 데이터 마이그레이션 스크립트 실행

**중기 (1-3개월):**
1. Phase 3 전환 (PostgreSQL/Parquet-only)
2. JSON 아카이브 및 정리
3. 성능 최적화 및 모니터링

---

**문서 작성**: 2025-11-11
**상태**: ✅ 완료
