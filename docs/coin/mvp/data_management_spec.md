# 데이터 관리 시스템 명세 (Phase 5)

**문서 버전**: 1.0
**작성일**: 2025-11-06
**관련 이슈**: #19 - 데이터 관리 페이지 구현

## 개요

데이터 관리 시스템은 사용자가 웹 UI를 통해 OHLCV 데이터 파일(`.parquet`)을 조회하고 업로드할 수 있는 기능을 제공합니다.

## 핵심 기능

### 1. 데이터 인벤토리 조회 (`GET /api/data/inventory`)

#### 목적
로컬 파일 시스템의 데이터 파일 목록을 조회합니다.

#### 요청 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|-----|------|-------|------|
| `symbol` | string | 아니오 | null | 심볼 필터 (예: BTC_KRW) |
| `timeframe` | string | 아니오 | null | 타임프레임 필터 (예: 1D) |
| `year` | integer | 아니오 | null | 연도 필터 (예: 2024) |
| `limit` | integer | 아니오 | 50 | 조회 수 제한 (최대: 200) |
| `offset` | integer | 아니오 | 0 | 페이지네이션 오프셋 |

#### 응답 스키마

```json
{
  "files": [
    {
      "symbol": "BTC_KRW",
      "timeframe": "1D",
      "year": 2024,
      "relative_path": "BTC_KRW/1D/2024.parquet",
      "size_bytes": 1048576,
      "modified_at": "2025-11-06T10:30:00+00:00"
    }
  ],
  "total_count": 150,
  "limit": 50,
  "offset": 0
}
```

#### 오류 응답

| 상태 코드 | 설명 |
|---------|------|
| 404 | DATA_ROOT 디렉토리를 찾을 수 없음 |
| 403 | DATA_ROOT에 대한 읽기 권한 부족 |
| 500 | 서버 오류 |

#### 예시

```bash
# 모든 파일 조회 (기본값)
GET /api/data/inventory

# BTC_KRW 심볼만 조회
GET /api/data/inventory?symbol=BTC_KRW

# ETH_KRW, 1D 타임프레임, 2024년 파일만 조회
GET /api/data/inventory?symbol=ETH_KRW&timeframe=1D&year=2024

# 페이지네이션 (두 번째 페이지, 페이지당 50개)
GET /api/data/inventory?limit=50&offset=50
```

---

### 2. 데이터 파일 업로드 (`POST /api/data/upload`)

#### 목적
Parquet 형식의 OHLCV 데이터 파일을 서버에 업로드합니다.

#### 요청 형식

**Content-Type**: `multipart/form-data`

| 파라미터 | 타입 | 필수 | 설명 |
|---------|-----|------|------|
| `file` | File | 예 | 업로드할 Parquet 파일 |
| `symbol` | string | 예 | 심볼 (예: BTC_KRW) |
| `timeframe` | string | 예 | 타임프레임 (예: 1D) |
| `year` | integer | 예 | 연도 (예: 2024) |
| `overwrite` | boolean | 아니오 | 기존 파일 덮어쓰기 여부 (기본: false) |

#### 응답 스키마

```json
{
  "success": true,
  "message": "파일이 성공적으로 업로드되었습니다",
  "file_path": "BTC_KRW/1D/2024.parquet"
}
```

#### 오류 응답

| 상태 코드 | 설명 |
|---------|------|
| 400 | 입력값 검증 실패 (심볼/타임프레임/연도 형식 오류) |
| 409 | 파일이 이미 존재 (overwrite=false) |
| 413 | 파일 크기 초과 (최대 200MB) |
| 415 | 지원하지 않는 파일 형식 또는 필수 컬럼 누락 |
| 500 | 서버 오류 |

#### 예시

```bash
curl -X POST /api/data/upload \
  -F "file=@BTC_KRW_2024.parquet" \
  -F "symbol=BTC_KRW" \
  -F "timeframe=1D" \
  -F "year=2024" \
  -F "overwrite=false"
```

---

## 파일 구조 및 규칙

### 디렉토리 구조

```
DATA_ROOT/
├── BTC_KRW/
│   ├── 1D/
│   │   ├── 2024.parquet
│   │   └── 2025.parquet
│   ├── 1H/
│   │   └── 2024.parquet
│   └── 5M/
│       └── 2024.parquet
├── ETH_KRW/
│   ├── 1D/
│   │   └── 2024.parquet
│   └── 1H/
│       └── 2024.parquet
└── ...
```

### 네이밍 규칙

1. **심볼 정규화**: 모든 심볼은 대문자로 정규화됩니다
   - 입력: `btc_krw` → 저장: `BTC_KRW/...`

2. **타임프레임 정규화**: 모든 타임프레임은 대문자로 정규화됩니다
   - 입력: `1d` → 저장: `1D/...`

3. **연도 형식**: 4자리 숫자 (2000~2099)
   - 유효: `2024`, `2025`
   - 무효: `24`, `202a`, `2100`

4. **파일명**: `{year}.parquet` (확장자는 반드시 `.parquet`)

### 필수 컬럼

Parquet 파일에 반드시 포함되어야 하는 컬럼:

```
open      - 시가 (float)
high      - 고가 (float)
low       - 저가 (float)
close     - 종가 (float)
volume    - 거래량 (float)
timestamp - 타임스탬프 (datetime64 또는 string)
```

### 타임존 처리

- **저장**: 모든 타임스탬프는 UTC 기준으로 저장됩니다
- **입력**: KST(한국 표준시) 또는 UTC 모두 수용합니다
  - 타임존 정보가 없으면 KST로 간주하고 UTC로 변환
  - 타임존 정보가 있으면 그대로 UTC로 변환

---

## 검증 규칙

### 입력값 검증

#### 심볼 (`symbol`)
- 필수 길이: 1~20자
- 허용 문자: 대문자(A-Z), 숫자(0-9)
- 자동 정규화: 소문자 → 대문자 변환
- 거부되는 경우: 특수 문자(./\등), 공백, 경로 이탈 시도(`..` 포함)

#### 타임프레임 (`timeframe`)
- 필수 길이: 1~10자
- 허용 문자: 대문자(A-Z), 숫자(0-9)
- 자동 정규화: 소문자 → 대문자 변환
- 공통 값: `1M`, `5M`, `1H`, `4H`, `1D`, `1W`

#### 연도 (`year`)
- 형식: 정확히 4자리 숫자
- 범위: 2000~2099
- 거부되는 경우: 음수, 3자리 이하, 5자리 이상

### 파일 검증

#### 파일 확장자
- 필수: `.parquet`
- 대소문자 구분 없음

#### 파일 크기
- 최대: 200MB (209,715,200 바이트)
- 초과 시: 413 Unsupported Media Type 반환

#### 파일 스키마 (Parquet 메타데이터)
- 필수 컬럼: `open`, `high`, `low`, `close`, `volume`, `timestamp`
- 누락 시: 415 Unsupported Media Type 반환
- **주의**: 전체 데이터를 읽지 않고 메타데이터만 검증하므로 성능 영향 최소화

### 경로 이탈 방지

파일 저장 경로는 다음과 같이 검증됩니다:

1. **화이트리스트 정규식 검증**
   - 심볼: `^[A-Z0-9]+$`
   - 타임프레임: `^[A-Z0-9]+$`
   - 연도: `^\d{4}$`

2. **경로 정규화 및 비교**
   ```python
   normalized_target = os.path.normpath(target_path)
   normalized_root = os.path.normpath(DATA_ROOT)

   # normalized_target이 normalized_root 아래에 있는지 확인
   if not normalized_target.startswith(normalized_root + os.sep):
       raise SecurityError("경로 이탈 시도")
   ```

3. **거부되는 경우**
   - 상위 디렉토리 참조: `../../../etc/passwd`
   - 절대 경로: `/etc/passwd`
   - 심볼에 경로 구분자: `BTC/..\\KRW`

---

## 보안 고려사항

### 현재 구현 (MVP)

1. **인증 없음**: 현재 모든 API는 인증 없이 접근 가능합니다
   - 개발/테스트 환경 전제
   - 프로덕션 배포 전 인증 추가 필수

2. **권한 관리 없음**: 모든 사용자가 모든 데이터에 접근 가능합니다
   - 향후 역할 기반 접근 제어(RBAC) 추가 필요

3. **파일 동시성**: 단일 사용자 환경 가정
   - 다중 사용자 환경에서는 파일 잠금 메커니즘 필요

### 향후 개선 사항

1. **API 키 또는 JWT 인증**
   - 관리자 토큰 기반 접근 제어
   - 사용자별 API 키 관리

2. **역할 기반 권한 관리**
   - 관리자, 사용자 등 역할 구분
   - 파일 공유 및 개인 영역 구분

3. **감사 로깅**
   - 모든 업로드/삭제 작업 기록
   - 접근 이력 추적

4. **데이터 암호화**
   - 저장소 암호화
   - 전송 암호화 (HTTPS)

---

## 성능 최적화

### 현재 구현

1. **페이지네이션**
   - 기본 limit: 50개
   - 최대 limit: 200개
   - 대량의 데이터 조회 시 성능 저하 방지

2. **정렬**
   - 기본 정렬: 수정일 내림차순 (최신순)
   - 파일 검색 시 빠른 결과 제공

3. **메타데이터 검증**
   - Parquet 파일의 스키마만 검증
   - 전체 데이터 로드 방지 → 빠른 업로드 검증

### 향후 개선 사항

1. **캐싱**
   - 인벤토리 캐시 (TTL: 5분)
   - 심볼/타임프레임 목록 캐시

2. **데이터베이스 인덱싱**
   - 파일 메타데이터 DB 저장
   - 파일 시스템 스캔 대신 DB 쿼리

3. **비동기 처리**
   - 대용량 파일 업로드 시 백그라운드 작업
   - 사용자 경험 개선

---

## 확장 계획

### Phase 5+ (향후)

1. **데이터 정합성 검사**
   - 중복 타임스탬프 감지
   - 누락 구간 감지
   - 데이터 품질 점수 제공

2. **파일 삭제 기능**
   - 사용자가 업로드한 파일 삭제 가능
   - 삭제 전 확인 대화
   - 감사 로깅

3. **통계 API**
   - 파일별 행 수 계산
   - 데이터 분포 분석
   - 메모리 효율적인 스트리밍 처리

4. **데이터 검증 및 변환**
   - 데이터 타입 자동 변환
   - 이상치 감지 및 처리
   - 데이터 정규화 옵션

5. **배치 처리**
   - 여러 파일 동시 업로드
   - ZIP/TAR 아카이브 지원
   - 정기적 자동 업로드

---

## 테스트 시나리오

### 유닛 테스트

1. **인벤토리 API**
   - 빈 디렉토리 조회
   - 필터링 (심볼, 타임프레임, 연도)
   - 페이지네이션
   - limit 최대값 제한

2. **업로드 API**
   - 유효한 파일 업로드
   - 입력값 검증 (심볼, 타임프레임, 연도)
   - 파일 형식 검증
   - 중복 파일 처리
   - 경로 이탈 방지

### E2E 테스트

1. **전체 워크플로우**
   - 빈 인벤토리 확인
   - 파일 업로드
   - 업로드된 파일 조회
   - 업로드 데이터로 백테스트 실행

2. **에러 처리**
   - 잘못된 파일 형식 거부
   - 필수 컬럼 누락 거부
   - 파일 크기 초과 거부
   - 경로 이탈 시도 차단

---

## 문제 해결 가이드

### 문제: "DATA_ROOT 디렉토리를 찾을 수 없음" 에러

**원인**: 환경변수 `DATA_ROOT`가 설정되지 않았거나 경로가 존재하지 않음

**해결**:
```bash
# 환경변수 확인
echo $DATA_ROOT

# 디렉토리 생성
mkdir -p /path/to/data

# 환경변수 설정
export DATA_ROOT=/path/to/data
```

### 문제: "파일 크기가 200MB를 초과합니다" 에러

**원인**: 업로드하려는 파일이 200MB보다 큼

**해결**:
- 파일을 연도별로 분할하여 업로드
- 필요 없는 컬럼 제거 후 재압축

### 문제: "필수 컬럼 누락" 에러

**원인**: Parquet 파일에 필수 컬럼(open, high, low, close, volume, timestamp) 중 일부가 없음

**해결**:
- Parquet 파일의 컬럼명 확인
- 필수 컬럼 포함하여 파일 재생성

```python
import pandas as pd

# 필수 컬럼 확인
required_cols = ['open', 'high', 'low', 'close', 'volume', 'timestamp']
df = pd.read_parquet('file.parquet')

missing = set(required_cols) - set(df.columns)
if missing:
    print(f"Missing columns: {missing}")
```

---

## 참고 자료

- [FastAPI 파일 업로드](https://fastapi.tiangolo.com/tutorial/request-files/)
- [Parquet 형식](https://parquet.apache.org/)
- [PyArrow 문서](https://arrow.apache.org/docs/python/)
- [관련 이슈]: #19 - 데이터 관리 페이지 구현
- [Feature Breakdown]: docs/coin/mvp/fb_13.md
- [E2E 테스트 가이드]: docs/E2E_TESTING_GUIDE.md

---

## 버전 히스토리

| 버전 | 날짜 | 변경 사항 |
|-----|------|---------|
| 1.0 | 2025-11-06 | 초기 작성 |
