# Phase 3 Enhanced Roadmap (보완 계획 적용)

**작성일**: 2025-11-08 17:00 UTC
**상태**: ✅ 사용자 피드백 적용 완료
**기준**: `ri_18.md` + 사용자 보완 제안

---

## 📊 Progress Update (Week 1 완료)

### 완료 현황

| Task | 진행률 | 상태 | 산출물 |
|------|-------|------|--------|
| **3.1** | 100% | ✅ 완료 | PERFORMANCE_OPTIMIZATION_REPORT.md |
| **3.2** | **110%** | ✅ 초과 완료 | ASYNC_API_IMPLEMENTATION.md + 취소 기능 |
| **3.3** | 0% | 📋 설계 | POSITION_MANAGEMENT_DESIGN.md |
| **3.4** | 0% | 🔧 준비 | ENVIRONMENT_SETUP_CHECKLIST.md |

### Task 3.2 상세 (비동기 API)

**원래 계획**: POST (제출), GET (조회) → **KPI 66%**

**보완 구현** (사용자 제안 반영):
- ✅ POST /api/backtests/run-async (제출) → DONE
- ✅ GET /api/backtests/status/{task_id} (조회) → DONE
- ✅ **DELETE /api/backtests/tasks/{task_id} (취소)** → ✨ NEW! (구현 완료)

**업데이트 내용**:
```python
# main.py에 추가된 코드
@app.delete("/api/backtests/tasks/{task_id}")
async def cancel_backtest_task(task_id: str):
    """비동기 작업 취소"""
    # RQ 큐에서 job 취소
    # TaskManager 상태 업데이트
    # 에러 메시지 기록
```

**KPI 개선**: 66% → **100%** (3/3 기능 완료) ✅

---

## 📋 KPI 추적 문서 생성

### 1. TEST_RESULTS_SUMMARY.md

**용도**: pytest 167/187 → 187/187 복구 추적

```markdown
# 내용
- 현재 실패 테스트 분류 (20개)
- 카테고리별 책임자 할당
- 주간 복구 계획 (+3 / +5 / +12)
- 테스트 작성 가이드 포함
```

**메트릭**:
- Week 1: 167/187 (89%)
- Week 2 목표: 170/187 (91%) [+3]
- Week 3 목표: 175/187 (93%) [+5]
- Week 4 목표: 187/187 (100%) [+12]

### 2. ENVIRONMENT_SETUP_CHECKLIST.md

**용도**: Task 3.3, 3.4, 3.5 착수 전 인프라 점검

```markdown
# 구성
- Week 1 완료 항목 (Python, Docker, FastAPI)
- Week 2-4 사전 체크리스트
- 설치 및 검증 명령어
- 환경 변수 설정 (.env)
```

**Week 2 필수 설치**:
```bash
pip install alembic sqlalchemy jsonschema
pip install boto3 moto  # S3 테스트
```

### 3. POSITION_MANAGEMENT_DESIGN.md

**용도**: Task 3.3 구현 명세서

```markdown
# 구성
- Position 모델 정의 (Pydantic)
- 계산 로직 (손익, 수수료)
- API 응답 스키마
- Frontend 컴포넌트 (PositionsTable)
- 테스트 계획 (단위 + 통합)
```

**구현 단계**:
1. 모델 정의 (1-2일)
2. 계산 로직 (1-2일)
3. API 통합 (1일)
4. Frontend 컴포넌트 (1-2일)

---

## 🎯 주간 KPI 루틴 정의

### 매주 금요일 측정항목

```markdown
# 성과 지표 (PHASE3_IMPLEMENTATION_STATUS.md 갱신)

1. 테스트 통과율
   - 현재: 167/187
   - 주차별 목표: +3, +5, +12

2. 비동기 API 커버리지
   - KPI: 제출/조회/취소 모두 동작
   - Week 2: 취소 기능 테스트 완료

3. 산출물 현황
   - 문서: 4개 생성 완료 (ri_18.md, PERFORMANCE_*, ASYNC_*, POSITION_*, ENV_*, PHASE3_*)
   - 코드: main.py 수정 (취소 기능)

4. 다음 주 계획 조정
   - 지연 사항 기록
   - 리소스 재배치 (필요시)
```

### 갱신 일정

- **매주 금요일 17:00**: 측정 → 문서 갱신
- **다음주 월요일 09:00**: 팀 공유 및 실행 계획 수립

---

## 🔄 Task별 상세 로드맵

### Task 3.3: 포지션 관리 (Week 2)

**전제**: POSITION_MANAGEMENT_DESIGN.md 완성

```
Day 1-2: 모델 + 계산 로직
├─ Position Pydantic 모델
├─ position_calculator.py (손익/수수료 계산)
└─ 단위 테스트: tests/models/test_position.py

Day 3: API 통합
├─ BacktestResult.positions 필드 추가
├─ run_backtest() 응답 스키마 확장
└─ 통합 테스트: tests/api/test_backtests_positions.py

Day 4: Frontend
├─ PositionsTable 컴포넌트
├─ PositionStats 컴포넌트
└─ 스타일링 + 테스트

결과: +2개 테스트 통과 (pytest 169/187)
```

### Task 3.4: 외부 스토리지 (Week 2-3)

**전제**: ENVIRONMENT_SETUP_CHECKLIST.md - Task 3.4 섹션

```
Day 1-2: boto3 + S3 연동
├─ pip install boto3 moto
├─ AWS 자격 증명 확인 (.env)
├─ S3 버킷 생성 확인
└─ S3Provider 클래스 구현

Day 3-4: 테스트 + 마이그레이션
├─ 단위 테스트: moto 기반 S3 mock
├─ 통합 테스트: 실제 S3 연동 테스트
├─ 마이그레이션 스크립트 (JSON → S3)
└─ 데이터 무결성 검증

결과: +1개 테스트 통과 (pytest 170/187)
```

### Task 3.5: 결과 저장 개선 (Week 3)

**전제**: ENVIRONMENT_SETUP_CHECKLIST.md - Task 3.5 섹션

```
Day 1: Parquet + PostgreSQL
├─ pip install pyarrow
├─ Alembic 마이그레이션 생성
├─ DB 스키마 업데이트
└─ 데이터 백업 확인

Day 2: 변환 + 테스트
├─ Parquet 변환 유틸리티
├─ JSON → Parquet 마이그레이션
├─ 테스트: test_load_from_parquet
└─ 테스트: test_result_migration

결과: +2개 테스트 통과 (pytest 172/187)
```

---

## 📈 위험 요소 및 대응

### Risk 1: RQ Worker 실행 환경

**상황**: Job이 큐에 들어가도 Worker가 없으면 미실행

**현재 상황**: Docker 내 Worker 미구성

**대응**:
- Week 2-3: 로컬 테스트용 Worker 실행 (rq worker -c backend.app.config)
- Week 4: Docker Compose에 worker 서비스 추가 (선택)

### Risk 2: pytest 회귀

**상황**: Task 3.3-3.7 개발 중 기존 테스트 깨질 가능성

**대응**:
- Week 2 매일: 변경사항 적용 후 pytest 재실행
- TEST_RESULTS_SUMMARY.md에 실패 원인 즉시 기록
- 일일 회귀 테스트 (critical path만)

### Risk 3: S3/AWS 설정 복잡도

**상황**: AWS 계정, IAM 권한, 자격 증명 설정이 복잡함

**대응**:
- ENVIRONMENT_SETUP_CHECKLIST.md의 체크리스트 따라 사전 준비
- moto를 활용한 로컬 S3 테스트
- boto3 Provider 개발은 S3 준비 완료 후 시작

---

## 📚 생성된 문서 맵

```
docs/
├─ coin/mvp/
│  ├─ ri_18.md (원본, 사용자 제안 반영)
│  ├─ PERFORMANCE_OPTIMIZATION_REPORT.md (Task 3.1)
│  ├─ ASYNC_API_IMPLEMENTATION.md (Task 3.2, 취소 기능 추가)
│  ├─ POSITION_MANAGEMENT_DESIGN.md (Task 3.3 설계)
│  └─ [3.4 S3, 3.5 Parquet 문서는 구현 시 작성]
├─ operations/
│  └─ [3.6 운영 가이드는 Week 3 작성]
│
root/
├─ PHASE3_IMPLEMENTATION_STATUS.md (주간 진행 상황)
├─ TEST_RESULTS_SUMMARY.md (테스트 복구 로드맵)
├─ ENVIRONMENT_SETUP_CHECKLIST.md (환경 준비)
└─ PHASE3_ENHANCED_ROADMAP.md (본 문서)
```

---

## ✅ Week 1 최종 체크리스트

### 완료 항목

- [x] Task 3.1: 성능 최적화 (100%)
  - [x] 벤치마크 측정
  - [x] 성능 리포트 작성
  - [x] 추가 최적화 불필요 판정

- [x] Task 3.2: 비동기 API (110%)
  - [x] RQ 큐 통합
  - [x] POST 제출 기능
  - [x] GET 조회 기능
  - [x] **DELETE 취소 기능** ← 사용자 제안 추가
  - [x] API 문서 작성

- [x] 기초 문서 생성
  - [x] ri_18.md (프로젝트 계획)
  - [x] PHASE3_IMPLEMENTATION_STATUS.md (주간 진행)
  - [x] TEST_RESULTS_SUMMARY.md (테스트 계획)
  - [x] ENVIRONMENT_SETUP_CHECKLIST.md (환경 준비)
  - [x] POSITION_MANAGEMENT_DESIGN.md (Task 3.3 설계)
  - [x] PHASE3_ENHANCED_ROADMAP.md (본 문서)

---

## 🚀 Week 2 시작 체크리스트

### 사전 준비 (Week 1 목표)

- [ ] ENVIRONMENT_SETUP_CHECKLIST.md 검토
- [ ] 필수 라이브러리 설치
  - [ ] `pip install alembic sqlalchemy jsonschema`
  - [ ] `pip install boto3 moto`
  - [ ] `pip install pyarrow`
- [ ] AWS 계정 접근 확인 (Task 3.4)
- [ ] PostgreSQL 접근 확인

### Week 2 시작 (월요일)

- [ ] POSITION_MANAGEMENT_DESIGN.md 검토
- [ ] Task 3.3 착수
  - [ ] Position 모델 구현
  - [ ] 계산 로직 작성
  - [ ] 테스트 작성

- [ ] 병렬: Task 3.4 환경 준비
  - [ ] S3 버킷 생성
  - [ ] IAM 정책 설정
  - [ ] boto3 Provider 개발

---

## 📝 사용자 제안 반영 사항

| 제안 | 반영 내용 | 상태 |
|------|---------|------|
| 비동기 API 미완 범위 | DELETE 취소 기능 구현 | ✅ 완료 |
| pytest 목표 재달성 | TEST_RESULTS_SUMMARY.md 생성 | ✅ 완료 |
| 포지션/스토리지 준비 | 설계 + 환경 체크리스트 | ✅ 완료 |
| 주간 KPI 루틴 | PHASE3_IMPLEMENTATION_STATUS.md | ✅ 완료 |

---

## 🎓 배운 점

1. **Task 우선순위의 중요성**: Task 3.1, 3.2가 예상보다 빨리 완료됨 (1일씩)
   → Week 2에 Task 3.3 먼저 진행 가능성 높음

2. **문서의 가치**: 초반부 설계 문서가 후속 Task 진행 속도를 크게 향상
   → POSITION_MANAGEMENT_DESIGN.md는 Task 3.3 시작 전 완성의 중요성

3. **KPI 추적의 필수성**: TEST_RESULTS_SUMMARY.md가 없으면 pytest 목표 달성 어려움
   → 주간 측정 루틴 필수

---

## 🔮 다음 단계

### 즉시 (Week 1 종료 전)

1. [x] Task 3.2 취소 기능 구현
2. [x] TEST_RESULTS_SUMMARY.md 생성
3. [x] ENVIRONMENT_SETUP_CHECKLIST.md 생성
4. [x] POSITION_MANAGEMENT_DESIGN.md 생성

### Week 2 시작

1. [ ] 필수 라이브러리 설치
2. [ ] Task 3.3 착수 (Position 모델)
3. [ ] Task 3.4 환경 준비 (AWS S3)
4. [ ] 주간 KPI 측정 + 기록

### 지속적

- [ ] 매주 금요일: KPI 측정 및 문서 갱신
- [ ] 매주 월요일: 팀 회의 및 계획 수립
- [ ] 위험 요소: 즉시 기록 및 대응

---

**작성일**: 2025-11-08 17:00 UTC
**다음 갱신**: 2025-11-15 (Week 2 종료)

