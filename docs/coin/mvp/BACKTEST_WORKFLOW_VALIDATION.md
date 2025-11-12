# 백테스트 워크플로 검증 가이드

**관련 Issue**: #37 - [Feature] 실전 백테스트 기준 타임프레임/심볼 통일화

**최종 수정**: 2025-11-12

---

## 개요

이 문서는 Issue #37 완료 후 **데이터 수집 → 저장 → 백테스트 실행**의 전체 워크플로를 검증하는 프로세스를 정의합니다.

검증 대상:
1. ✅ 프론트엔드와 백엔드의 심볼/타임프레임 동기화
2. ✅ 자동 스케줄러의 데이터 수집 기능
3. ✅ 수집된 데이터의 파일 구조 정합성
4. ✅ 백테스트 UI에서 수집된 데이터 활용

---

## 사전 조건

### 필수 환경 설정

```bash
# 1. docker-compose 실행 (필수)
docker-compose up -d

# 2. 백엔드 서버 정상 실행 확인
# 로그 확인:
docker-compose logs backend | grep "Uvicorn running"

# 3. Redis 연결 확인
docker-compose logs backend | grep "✅ Redis 연결 성공"

# 4. 스케줄러 설정 로깅 확인
docker-compose logs backend | grep "📋 스케줄러 설정"
```

### 확인 항목

- [ ] Backend 서버 포트 8000에서 실행 중
- [ ] Redis 연결 성공
- [ ] 스케줄러 설정이 올바르게 로드됨
- [ ] DataManagementPage.jsx와 BacktestPage.jsx 접속 가능

---

## 검증 프로세스

### Step 1: 프론트엔드 상수 확인

#### 1-1. DataManagementPage 확인

**작업**: 프론트엔드 접속 후 DataManagementPage 열기

1. 브라우저에서 `http://localhost:5173` 접속
2. "데이터 관리" 탭 클릭
3. "파일 업로드" 탭 선택

**검증 항목**:
- [ ] 심볼 드롭다운에 9개 심볼 표시 확인
  - KRW-BTC, KRW-ETH, KRW-XRP, KRW-SOL, KRW-XLM, KRW-ADA, KRW-DOGE, KRW-BCH, KRW-NEAR
- [ ] 타임프레임 드롭다운에 5개 타임프레임 표시 확인
  - 1M, 5M, 1H, 1D, 1W
- [ ] 안내 문본에 지원 심볼과 타임프레임이 표시됨

**스크린샷**: 심볼과 타임프레임 드롭다운이 모두 올바르게 표시되는지 캡처

#### 1-2. BacktestPage 확인

**작업**: BacktestPage 열기

1. "백테스트" 탭 클릭
2. 타임프레임 드롭다운 확인

**검증 항목**:
- [ ] 타임프레임 드롭다운에 5개 옵션 표시 확인
  - 1M, 5M, 1H, 1D, 1W
- [ ] 기본 타임프레임이 1H로 설정됨

**스크린샷**: 타임프레임 드롭다운 캡처

---

### Step 2: 백엔드 환경 변수 확인

#### 2-1. 스케줄러 설정 로그 확인

**작업**: 백엔드 로그에서 설정 확인

```bash
# 백엔드 컨테이너 로그 조회
docker-compose logs backend | grep -A 5 "📋 스케줄러 설정"
```

**예상 출력**:
```
📋 스케줄러 설정 (scheduler_config.py)
=======================
심볼 (SCHEDULER_SYMBOLS): KRW-BTC, KRW-ETH, KRW-XRP, KRW-SOL, KRW-XLM, KRW-ADA, KRW-DOGE, KRW-BCH, KRW-NEAR
타임프레임 (SCHEDULER_TIMEFRAMES): 1M, 5M, 1H, 1D, 1W
=======================
```

**검증 항목**:
- [ ] 모든 9개 심볼이 올바른 순서로 표시됨
- [ ] 모든 5개 타임프레임이 대문자로 표시됨
- [ ] 환경 변수가 올바르게 파싱됨

#### 2-2. 환경 변수 직접 확인

```bash
# docker-compose.yml에서 직접 확인
grep -A 2 "SCHEDULER_SYMBOLS\|SCHEDULER_TIMEFRAMES" docker-compose.yml
```

**검증 항목**:
- [ ] SCHEDULER_SYMBOLS에 9개 심볼 포함
- [ ] SCHEDULER_TIMEFRAMES에 5개 타임프레임 포함
- [ ] 모든 서비스(backend, worker, test, e2e-test)에서 동일한 값 설정

---

### Step 3: 수동 데이터 수집 트리거

#### 3-1. DataManagementPage에서 수동 트리거

**작업**: "자동 수집" 탭에서 수동 트리거

1. DataManagementPage의 "자동 수집" 탭 클릭
2. "수동 트리거" 버튼 클릭
3. 심볼: KRW-BTC, 타임프레임: 1M 선택
4. "수집 시작" 버튼 클릭

**검증 항목**:
- [ ] 작업이 큐에 추가되었다는 메시지 표시
- [ ] Job ID가 발급됨

#### 3-2. 데이터 수집 확인

```bash
# 수집 작업 로그 확인 (약 30초 대기)
docker-compose logs worker | tail -20

# 수집된 파일 확인
find ./data -name "*.parquet" | head -10
```

**검증 항목**:
- [ ] 작업이 정상 실행됨 (에러 없음)
- [ ] 파일이 올바른 경로에 저장됨: `data/KRW-BTC/1M/YYYY.parquet`

**예상 파일 구조**:
```
data/
├── KRW-BTC/
│   ├── 1M/
│   │   ├── 2024.parquet
│   │   └── 2025.parquet
│   ├── 5M/
│   ├── 1H/
│   └── ...
├── KRW-ETH/
└── ...
```

---

### Step 4: 파일 구조 및 데이터 검증

#### 4-1. 파일 경로 검증

```bash
# 모든 수집된 파일 목록
find ./data -name "*.parquet" -type f | sort

# 심볼별 타임프레임 확인
ls -la data/KRW-BTC/
```

**검증 항목**:
- [ ] 심볼 디렉터리 생성됨: `data/{SYMBOL}/`
- [ ] 타임프레임 디렉터리 생성됨: `data/{SYMBOL}/{TIMEFRAME}/`
- [ ] 연도별 파일 저장됨: `data/{SYMBOL}/{TIMEFRAME}/YYYY.parquet`

#### 4-2. Parquet 파일 구조 검증

```bash
# Python으로 파일 확인
python3 << 'EOF'
import pandas as pd
import os

# 첫 번째 파일 로드
parquet_files = [f for f in os.walk('./data')]
if parquet_files:
    file_path = next((os.path.join(root, f) for root, dirs, files in os.walk('./data')
                     for f in files if f.endswith('.parquet')), None)

    if file_path:
        df = pd.read_parquet(file_path)
        print(f"파일: {file_path}")
        print(f"행 수: {len(df)}")
        print(f"컬럼: {list(df.columns)}")
        print(f"\n첫 5행:")
        print(df.head())
EOF
```

**검증 항목**:
- [ ] 필수 컬럼 존재: open, high, low, close, volume, timestamp
- [ ] timestamp 컬럼이 datetime 타입
- [ ] 데이터가 올바르게 저장됨 (행 수 > 0)

---

### Step 5: 백테스트 UI에서 데이터 사용

#### 5-1. BacktestPage에서 수집된 데이터 선택

**작업**: BacktestPage에서 수집된 데이터로 백테스트 실행

1. "백테스트" 탭 클릭
2. 심볼 입력: `KRW-BTC` (또는 수집된 심볼)
3. 시작일: `2024-01-01`
4. 종료일: `2025-01-01`
5. 타임프레임: `1H` 또는 `1M` (수집된 타임프레임)
6. 전략 선택: "거래량 급증 + 장대양봉"
7. "백테스트 실행" 클릭

**검증 항목**:
- [ ] 백테스트가 정상 실행됨
- [ ] 수집된 데이터에서 캔들 데이터 로드됨
- [ ] 백테스트 결과가 표시됨

**예상 결과**:
- 거래량 신호 수, 성공률, Sharpe Ratio 등이 표시됨

#### 5-2. 결과 검증

```bash
# 백테스트 API 직접 호출 테스트
curl -X POST http://localhost:8000/api/backtests/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "volume_long_candle",
    "symbols": ["KRW-BTC"],
    "start_date": "2024-01-01",
    "end_date": "2025-01-01",
    "timeframe": "1H",
    "params": {
      "vol_ma_window": 20,
      "vol_multiplier": 1.5,
      "body_pct": 0.01
    }
  }' | jq .
```

**검증 항목**:
- [ ] API 응답 200 OK
- [ ] 백테스트 결과가 JSON으로 반환됨
- [ ] 신호 및 성공률 데이터 포함됨

---

### Step 6: 자동 스케줄러 검증 (선택사항)

#### 6-1. 스케줄러 상태 조회

```bash
# 스케줄러 상태 API
curl -s http://localhost:8000/api/scheduler/status | jq .
```

**검증 항목**:
- [ ] `enabled`: true
- [ ] `running`: true
- [ ] `configuration.symbols`: 9개 심볼
- [ ] `configuration.timeframes`: 5개 타임프레임

#### 6-2. 스케줄 설정 확인

```bash
# 백엔드 로그에서 스케줄 설정 확인
docker-compose logs backend | grep -A 3 "스케줄 설정 완료"
```

**예상 출력**:
```
✅ 스케줄 설정 완료
  실행 시간: 매일 09:00 (UTC)
  심볼: KRW-BTC, KRW-ETH, ...
  타임프레임: 1M, 5M, 1H, 1D, 1W
```

---

## 검증 체크리스트

### 전체 검증 완료 확인

프로젝트 마이그레이션 시 다음 체크리스트를 확인하세요:

#### 프론트엔드
- [ ] DataManagementPage 심볼 드롭다운: 9개 심볼 표시
- [ ] DataManagementPage 타임프레임: 1M, 5M, 1H, 1D, 1W
- [ ] BacktestPage 타임프레임: 1M, 5M, 1H, 1D, 1W
- [ ] 안내 문본에 지원 목록 표시

#### 백엔드
- [ ] scheduler_config.py 상수 확인
- [ ] docker-compose.yml 환경 변수 확인
- [ ] 모든 서비스에서 동일한 환경 변수 설정
- [ ] 스케줄러 로그에 올바른 설정 표시

#### 데이터 수집
- [ ] 수동 트리거로 데이터 수집 성공
- [ ] 파일 경로 정합성: `data/{SYMBOL}/{TIMEFRAME}/YYYY.parquet`
- [ ] Parquet 파일 구조 검증 (컬럼, 데이터 타입)

#### 백테스트 실행
- [ ] 수집된 데이터로 백테스트 실행 가능
- [ ] 백테스트 결과 정상 반환
- [ ] API 응답 200 OK

---

## 알려진 이슈 및 해결 방법

### 이슈 1: 타임프레임 표기 오류

**증상**: 파일이 저장되지 않거나 경로가 잘못됨

**원인**: 백엔드에서 타임프레임을 소문자로 처리하는 경우

**해결**:
```python
# backend/app/jobs/data_ingestion.py 또는 관련 파일
timeframe = timeframe.upper()  # 대문자로 정규화
```

### 이슈 2: 심볼이 드롭다운에 표시되지 않음

**증상**: DataManagementPage 심볼 드롭다운이 비어 있음

**원인**: DEFAULT_SYMBOLS 상수가 정의되지 않았거나 빈 배열

**해결**:
```javascript
// frontend/src/pages/DataManagementPage.jsx
const DEFAULT_SYMBOLS = ['KRW-BTC', 'KRW-ETH', ...] // 반드시 정의
```

### 이슈 3: 스케줄러가 데이터를 수집하지 않음

**증상**: 자동 수집이 실행되지 않거나 작업이 큐에 쌓이지 않음

**원인**: ENABLE_SCHEDULER=false 또는 Redis 연결 실패

**해결**:
```bash
# docker-compose.yml 확인
ENABLE_SCHEDULER=true

# Redis 연결 확인
docker-compose logs backend | grep "Redis 연결"
```

---

## 마이그레이션 체크리스트 (운영팀용)

배포 전 운영팀에서 확인할 사항:

### 프로덕션 배포 전

- [ ] 모든 코드 변경사항이 병합됨 (main/master 브랜치)
- [ ] 프론트엔드 빌드 성공
- [ ] 백엔드 유닛 테스트 통과
- [ ] docker-compose.yml 환경 변수 최종 검증
- [ ] 스케줄러 로그에서 설정 확인
- [ ] 수동 데이터 수집 테스트 통과

### 프로덕션 배포 후

- [ ] 백엔드 서버 정상 실행 확인
- [ ] 스케줄러 설정 로그 확인
- [ ] 첫 자동 수집 완료 확인
- [ ] 수집된 데이터 파일 구조 확인
- [ ] 백테스트 UI에서 데이터 사용 가능 확인

### 롤백 계획

문제 발생 시:
1. docker-compose 중지: `docker-compose down`
2. 이전 버전으로 복구: `git checkout <previous-commit>`
3. 재시작: `docker-compose up -d`

---

## 관련 문서

- **Issue #37 분석**: `docs/coin/mvp/ri_22.md`
- **동기화 가이드**: `docs/coin/mvp/SYMBOL_TIMEFRAME_SYNC_GUIDE.md`
- **자동 데이터 수집**: `docs/AUTOMATED_DATA_COLLECTION_GUIDE.md`
- **스케줄러 설정**: `backend/app/scheduler_config.py`

---

## 검증 완료 기록

이 섹션은 각 환경별로 검증 완료 시 기록합니다.

### 개발 환경 (Development)

| 항목 | 상태 | 담당자 | 날짜 |
|------|------|--------|------|
| 프론트엔드 상수 | - | - | - |
| 백엔드 환경 변수 | - | - | - |
| 수동 데이터 수집 | - | - | - |
| 파일 구조 검증 | - | - | - |
| 백테스트 실행 | - | - | - |

### 스테이징 환경 (Staging)

| 항목 | 상태 | 담당자 | 날짜 |
|------|------|--------|------|
| 프론트엔드 상수 | - | - | - |
| 백엔드 환경 변수 | - | - | - |
| 수동 데이터 수집 | - | - | - |
| 파일 구조 검증 | - | - | - |
| 백테스트 실행 | - | - | - |

### 프로덕션 환경 (Production)

| 항목 | 상태 | 담당자 | 날짜 |
|------|------|--------|------|
| 프론트엔드 상수 | - | - | - |
| 백엔드 환경 변수 | - | - | - |
| 수동 데이터 수집 | - | - | - |
| 파일 구조 검증 | - | - | - |
| 백테스트 실행 | - | - | - |

