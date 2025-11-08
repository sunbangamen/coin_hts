# Environment Setup Checklist for Phase 3

**최종 업데이트**: 2025-11-08
**상태**: Week 1 완료, Week 2-4 사전 점검용

---

## 1. 현재 인프라 상태

### ✅ 완료된 설정 (Week 1)

- [x] Python 3.x + venv 설정
- [x] Docker Compose (PostgreSQL, Redis) 구성
- [x] FastAPI + RQ 라이브러리 설치
- [x] requirements.txt 완성

**검증**:
```bash
# 모든 패키지 설치 확인
source venv/bin/activate && pip list | grep -E "fastapi|rq|redis|pandas"
```

### 📋 Task 3.3 필수 (포지션 관리)

| 항목 | 상태 | 점검 |
|------|------|------|
| SQLAlchemy ORM | ✅ 설치됨 | `pip show sqlalchemy` |
| Alembic (DB 마이그레이션) | ❌ 설치 필요 | `pip install alembic` |
| Pydantic 스키마 | ✅ 설치됨 | 기존 코드에서 사용 중 |
| JSON Schema 검증 | ⚠️ 부분 | `pip install jsonschema` 고려 |

### 📋 Task 3.4 필수 (S3 스토리지)

| 항목 | 상태 | 점검 |
|------|------|------|
| boto3 (AWS SDK) | ❌ 설치 필요 | `pip install boto3` |
| AWS 계정 | ❌ 준비 필요 | AWS 콘솔 접근 확인 |
| S3 버킷 | ❌ 생성 필요 | 버킷명: `coin-backtest-results-[env]` |
| IAM 역할 | ❌ 설정 필요 | S3 읽기/쓰기 권한 |
| AWS 자격 증명 | ❌ 설정 필요 | `.env` 파일에 보관 |
| moto (S3 mock) | ⚠️ 선택 | `pip install moto` (테스트용) |

### 📋 Task 3.5 필수 (결과 저장 개선)

| 항목 | 상태 | 점검 |
|------|------|------|
| pyarrow (Parquet) | ❌ 설치 필요 | `pip install pyarrow` |
| PostgreSQL 설정 | ✅ Docker 중 | `docker compose logs postgres` |
| Alembic 마이그레이션 | ⚠️ 준비 필요 | `alembic init backend/migrations` |

---

## 2. Week 2 준비 체크리스트 (Task 3.3, 3.4 착수 전)

### 2.1 Task 3.3 준비 (포지션 관리)

```bash
# 1. Alembic 초기화
alembic init backend/migrations

# 2. requirements.txt 업데이트
pip install sqlalchemy alembic jsonschema
pip freeze >> requirements.txt

# 3. Position 스키마 디렉토리 생성
mkdir -p backend/app/schemas
touch backend/app/schemas/__init__.py
touch backend/app/schemas/position.py

# 4. DB 마이그레이션 준비
alembic revision --autogenerate -m "Add position table"

# 체크포인트
pytest tests/api/test_backtests_positions.py -v  # 0/5 통과 확인
```

**체크리스트**:
- [ ] Alembic 초기화
- [ ] Position 모델 파일 생성
- [ ] DB 마이그레이션 생성
- [ ] Pydantic Position 스키마 작성
- [ ] API 응답 스키마 통합

### 2.2 Task 3.4 준비 (S3 스토리지)

```bash
# 1. AWS SDK 설치
pip install boto3 moto

# 2. AWS 자격 증명 확인 (선택: CLI 설정 또는 .env)
# Option A: AWS CLI
aws configure

# Option B: .env 파일 (권장)
cat >> .env << 'ENVEOF'
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=ap-northeast-2
S3_BUCKET=coin-backtest-results-dev
ENVEOF

# 3. S3 버킷 생성 (AWS CLI 또는 콘솔)
# AWS CLI:
aws s3 mb s3://coin-backtest-results-dev --region ap-northeast-2

# 4. IAM 정책 확인 (최소 권한)
# - s3:GetObject
# - s3:PutObject
# - s3:DeleteObject
# - s3:ListBucket

# 5. S3Provider 테스트 파일 생성
mkdir -p backend/app/storage
touch backend/app/storage/__init__.py
touch backend/app/storage/base.py
touch backend/app/storage/s3_provider.py
touch backend/app/storage/local_provider.py

# 체크포인트
pytest tests/storage/test_s3_provider.py -v  # 0/5 통과 확인
```

**체크리스트**:
- [ ] boto3 설치 완료
- [ ] AWS 계정 접근 가능
- [ ] S3 버킷 생성됨
- [ ] IAM 역할/정책 설정됨
- [ ] AWS 자격 증명 .env에 저장됨
- [ ] 자격 증명이 .gitignore에 있는지 확인

---

## 3. Week 3 준비 체크리스트 (Task 3.5, 3.6 착수 전)

### 3.1 Task 3.5 준비 (결과 저장 개선)

```bash
# 1. Parquet 라이브러리 설치
pip install pyarrow

# 2. 기존 결과 백업
cp -r data/results data/results.backup.2025-11-08

# 3. Parquet 변환 유틸리티 생성
touch backend/app/utils/parquet_converter.py

# 4. DB 마이그레이션 재실행
alembic revision --autogenerate -m "Add backtest results table"
alembic upgrade head

# 체크포인트
pytest tests/api/test_backtests_storage.py -v  # 0/3 통과 확인
```

**체크리스트**:
- [ ] pyarrow 설치
- [ ] 기존 결과 백업
- [ ] DB 마이그레이션 준비
- [ ] Parquet 변환 유틸리티 생성

### 3.2 Task 3.6 준비 (운영 가이드)

```bash
# 1. 운영 문서 디렉토리 생성
mkdir -p docs/operations

# 2. 기본 가이드 템플릿 생성
touch docs/operations/INSTALLATION_GUIDE.md
touch docs/operations/TROUBLESHOOTING.md
touch docs/operations/BACKUP_RESTORE.md

# 3. 운영 체크리스트
touch docs/operations/OPERATIONAL_CHECKLIST.md
```

**체크리스트**:
- [ ] 운영 문서 구조 생성
- [ ] README 업데이트
- [ ] 배포 가이드 작성
- [ ] 트러블슈팅 가이드 작성

---

## 4. Week 4 준비 체크리스트 (Task 3.7, 3.8 착수 전)

### 4.1 Task 3.7 준비 (백업 및 모니터링)

```bash
# 1. Celery Beat 설치 (또는 기존 스케줄러 확인)
pip show schedule apscheduler

# 2. 백업 스크립트 디렉토리
mkdir -p scripts/backup
touch scripts/backup/backup_database.sh
touch scripts/backup/backup_data.sh
touch scripts/backup/backup_restore.sh

# 3. 로깅 설정
touch backend/app/utils/structured_logging.py

# 체크포인트
pytest tests/backup/test_backup_restore.py -v
```

### 4.2 Task 3.8 준비 (통합 테스트)

```bash
# 1. E2E 테스트 디렉토리
mkdir -p tests/e2e
touch tests/e2e/__init__.py
touch tests/e2e/test_phase3_e2e.py

# 2. 성능 테스트
touch tests/performance/test_phase3_performance.py

# 3. 회귀 테스트
touch tests/regression/test_phase3_regression.py

# 체크포인트
pytest tests/ -m "phase3" -v
```

---

## 5. 환경 변수 설정 (.env)

### 필수 항목 (Week 1 완료)

```env
DATA_ROOT=/data
REDIS_HOST=redis
REDIS_PORT=6379
POSTGRES_USER=coin_user
POSTGRES_PASSWORD=coin_password
POSTGRES_DB=coin_db
```

### Week 2 추가

```env
# Task 3.3 (포지션 관리)
DB_URL=postgresql://coin_user:coin_password@postgres:5432/coin_db

# Task 3.4 (S3)
AWS_ACCESS_KEY_ID=<your_key>
AWS_SECRET_ACCESS_KEY=<your_secret>
AWS_REGION=ap-northeast-2
S3_BUCKET=coin-backtest-results-dev
STORAGE_TYPE=s3
```

### Week 3 추가

```env
# Task 3.5 (결과 저장)
PARQUET_ENABLED=true
DB_BACKUP_PATH=/backups

# Task 3.6 (운영)
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Week 4 추가

```env
# Task 3.7 (백업)
BACKUP_SCHEDULE=0 0 * * *  # 매일 자정
BACKUP_RETENTION_DAYS=7

# Task 3.8 (모니터링)
ENABLE_MONITORING=true
SLACK_WEBHOOK_URL=<optional>
```

---

## 6. 사전 점검 항목

### 환경 변수 확인

```bash
# .env 파일 존재 여부
[ -f .env ] && echo "✅ .env 파일 있음" || echo "❌ .env 파일 없음"

# 기본 환경 변수 확인
grep -E "DATA_ROOT|REDIS_HOST|POSTGRES" .env
```

### Docker 서비스 상태

```bash
# 서비스 실행 확인
docker compose ps

# 예상 출력:
# NAME              STATUS
# coin-postgres    Up
# coin-redis       Up
# coin-backend     Up
```

### Python 환경 확인

```bash
# venv 활성화
source venv/bin/activate

# 주요 패키지 확인
python -c "
import fastapi
import rq
import redis
import pandas
import sqlalchemy
print('✅ All packages imported successfully')
"
```

---

## 7. 갱신 로그

| 날짜 | 항목 | 상태 |
|------|------|------|
| 2025-11-08 | Week 1 설정 | ✅ 완료 |
| 2025-11-15 | Week 2 체크리스트 | ⏳ 대기 |
| 2025-11-22 | Week 3 체크리스트 | ⏳ 대기 |
| 2025-11-29 | Week 4 체크리스트 | ⏳ 대기 |

---

**다음 갱신**: 2025-11-15 (Week 2 착수 시)
