# Coin Trading Backend - OHLCV Data Loader

코인 백테스트 및 자동매매 플랫폼의 백엔드 데이터 로더 모듈입니다.

## 개요

로컬 parquet 파일 기반의 OHLCV(Open, High, Low, Close, Volume) 데이터 로딩 시스템을 제공합니다.

- **파일 구조**: `DATA_ROOT/{symbol}/{timeframe}/{year}.parquet`
- **타임존 처리**: KST 입력 → 내부 UTC 처리
- **도메인**: 코인 거래량 + 매물대 기반 백테스팅

---

## 주요 기능

### 1. OHLCV 데이터 로드
```python
from backend.app.data_loader import load_ohlcv_data

df = load_ohlcv_data(
    symbols=["BTC_KRW", "XRP_KRW"],
    start_date="2024-01-01",
    end_date="2024-12-31",
    timeframe="1d"
)
```

**반환 DataFrame 컬럼**:
- `timestamp`: UTC 기준 시간 (timezone-aware)
- `symbol`: 심볼명 (대문자, 예: `BTC_KRW`)
- `timeframe`: 타임프레임 (대문자, 예: `1D`, `1H`, `5M`)
- `open`, `high`, `low`, `close`: 가격 (float)
- `volume`: 거래량 (float)

### 2. 타임존 정규화
- **입력**: KST 기반 ISO8601 문자열 (예: `"2024-01-01"`, `"2024-01-01T14:30:00+09:00"`)
- **내부**: UTC로 변환하여 일관되게 처리
- **출력**: UTC timezone-aware timestamp

```python
# "2024-01-01 KST" = "2023-12-31 15:00:00 UTC"로 변환 및 반환
```

### 3. 예외 처리
| 상황 | 예외 | 상태 코드 |
|-----|------|--------|
| 파일이 없음 | HTTPException | 404 |
| 필수 컬럼 누락 | HTTPException | 400 |
| 입력 파라미터 오류 | HTTPException | 422 |

---

## 설치 및 환경 구성

### 1. 로컬 개발 환경

```bash
# 가상환경 생성
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. Docker 환경

```bash
# 이미지 빌드
docker-compose build

# 테스트 실행
docker-compose run --rm test

# 백엔드 실행
docker-compose up backend
```

---

## 데이터 구조

### 디렉토리 구조
```
DATA_ROOT/
├── BTC_KRW/
│   ├── 1D/
│   │   ├── 2022.parquet
│   │   ├── 2023.parquet
│   │   └── 2024.parquet
│   ├── 1H/
│   │   └── 2024.parquet
│   └── 5M/
│       └── 2024.parquet
├── XRP_KRW/
│   ├── 1D/
│   │   ├── 2023.parquet
│   │   └── 2024.parquet
│   └── ...
└── ...
```

### Parquet 파일 포맷

최소 필수 컬럼:
- `open`: float (시가)
- `high`: float (고가)
- `low`: float (저가)
- `close`: float (종가)
- `volume`: float (거래량)
- `timestamp`: datetime (날짜, timezone 선택사항)

**선택 컬럼**:
- `symbol`: str (심볼, 없으면 경로에서 주입)
- `timeframe`: str (타임프레임, 없으면 경로에서 주입)

---

## API 사용 예제

### 예제 1: 단일 심볼 로드
```python
from backend.app.data_loader import load_ohlcv_data

# BTC_KRW 2024년 데이터 로드
df = load_ohlcv_data(
    symbols=["BTC_KRW"],
    start_date="2024-01-01",
    end_date="2024-12-31",
    timeframe="1d"
)

print(df.head())
# Output:
#             timestamp      symbol timeframe  open  high  low  close  volume
# 0 2023-12-31 15:00:00+00:00  BTC_KRW        1D  40000  42000  39000  41500   1234.5
# 1 2024-01-02 15:00:00+00:00  BTC_KRW        1D  41500  43000  41000  42500   2345.6
# ...
```

### 예제 2: 다중 심볼 로드
```python
# 여러 심볼을 동시에 로드
df = load_ohlcv_data(
    symbols=["BTC_KRW", "XRP_KRW", "ETH_KRW"],
    start_date="2024-01-01",
    end_date="2024-03-31",
    timeframe="1h"
)

# 심볼별 데이터 필터링
btc_data = df[df['symbol'] == 'BTC_KRW']
xrp_data = df[df['symbol'] == 'XRP_KRW']
```

### 예제 3: 환경 변수 사용
```bash
# 쉘에서 DATA_ROOT 설정
export DATA_ROOT=/home/user/trading_data

# 또는 docker-compose.yml에서 자동으로 설정됨
# /data 볼륨으로 마운트되어 있음
```

---

## 테스트

### 로컬 테스트 실행
```bash
# 전체 테스트
source venv/bin/activate
python -m pytest tests/test_data_loader.py -v

# 특정 테스트 클래스만 실행
pytest tests/test_data_loader.py::TestLoadOhlcvData -v

# 테스트 결과 상세 출력
pytest tests/test_data_loader.py -vv --tb=long
```

### Docker 테스트 실행
```bash
# 테스트 컨테이너 실행 (test 프로필 사용)
docker-compose run --rm test

# 또는 특정 테스트만 실행
docker-compose run --rm test pytest tests/test_data_loader.py::TestNormalizeTimezone -v
```

### 테스트 커버리지

**테스트 케이스**: 22개

| 테스트 그룹 | 개수 | 설명 |
|-----------|------|------|
| TestNormalizeTimezone | 4 | KST → UTC 타임존 변환 |
| TestExtractYearsFromRange | 3 | 날짜 범위에서 연도 추출 |
| TestValidateDataFrame | 4 | DataFrame 필수 컬럼 검증 |
| TestLoadOhlcvData | 11 | 전체 데이터 로딩 및 필터링 |

**커버리지**: 80% 이상

---

## 도메인 규칙

### 1. 타임존 처리
- **입력**: KST 기반 ISO8601 (예: `"2024-01-01"`, `"2024-01-01T14:30:00+09:00"`)
- **변환**: 자동으로 UTC로 변환
- **출력**: UTC timezone-aware `pd.Timestamp`

### 2. 심볼 표기
- **형식**: 대문자 + 언더바 (예: `BTC_KRW`, `ETH_USDT`)
- **주입**: 파일 경로 `{symbol}/{timeframe}/` 에서 추출
- **정규화**: 입력은 소문자도 허용하지만 내부에서 대문자로 변환

### 3. 타임프레임 표기
- **형식**: 대문자 단위 (예: `1S`, `1M`, `5M`, `1H`, `1D`)
- **주입**: 파일 경로 `/{timeframe}/` 에서 추출
- **정규화**: 입력은 소문자도 허용하지만 내부에서 대문자로 변환

---

## 환경 변수

| 변수명 | 기본값 | 설명 |
|-------|-------|------|
| `DATA_ROOT` | `./data` | parquet 파일 루트 디렉토리 |
| `TZ` | `Asia/Seoul` | 컨테이너 시스템 타임존 (참고용, 데이터는 UTC 처리) |
| `PYTHONUNBUFFERED` | `1` | 로그 실시간 출력 |

### Docker 환경
```bash
docker-compose up \
  -e DATA_ROOT=/data \
  -e TZ=Asia/Seoul \
  backend
```

---

## 파일 구조

```
/home/limeking/projects/worktree/coin-1/
├── backend/
│   └── app/
│       ├── __init__.py
│       └── data_loader.py          # OHLCV 로더 모듈
├── tests/
│   └── test_data_loader.py         # 유닛 테스트 (22개)
├── requirements.txt                # Python 의존성
├── Dockerfile                      # Docker 이미지 정의
├── docker-compose.yml              # Docker 다중 컨테이너 설정
├── README.md                       # 이 파일
├── e2e_test_results.log           # End-to-end 테스트 결과
├── docker_build_results.log        # Docker 빌드 로그
└── docker_test_results.log         # Docker 테스트 실행 결과
```

---

## 주요 함수 API

### `load_ohlcv_data()`

```python
def load_ohlcv_data(
    symbols: List[str],
    start_date: str,
    end_date: str,
    timeframe: str = "1d",
    data_root: Optional[str] = None
) -> pd.DataFrame
```

**파라미터**:
- `symbols` (List[str]): 조회할 심볼 목록 (예: `["BTC_KRW"]`)
- `start_date` (str): 시작 날짜 (ISO8601)
- `end_date` (str): 종료 날짜 (ISO8601)
- `timeframe` (str, 기본값: `"1d"`): 타임프레임
- `data_root` (Optional[str]): 데이터 루트 (기본값: 환경변수 `DATA_ROOT`)

**반환**:
- `pd.DataFrame`: 병합된 OHLCV 데이터 (timestamp 오름차순 정렬)

**예외**:
- `HTTPException(404)`: 조회 가능한 데이터 파일 없음
- `HTTPException(400)`: 필수 컬럼 누락 또는 스키마 오류
- `HTTPException(422)`: 입력 파라미터 오류

---

## 버전 정보

- **프로젝트 단계**: Phase 1 (백테스트 엔진 기초)
- **이슈**: Issue #1 - 백엔드 데이터 로더 구현
- **상태**: ✅ 완료 (단계 5: 통합 테스트 및 문서화)

---

## 참고 문서

- **PDR (Product Design Review)**: [`docs/pdr.md`](./docs/pdr.md)
  - 전체 프로젝트 로드맵 (Phase 1-3)
  - 백테스트 엔진, 실전 시뮬레이션, 자동매매 설계

- **Issue #1 해결 계획**: [`docs/coin/mvp/ri_1.md`](./docs/coin/mvp/ri_1.md)
  - 데이터 로더 구현 5단계 계획
  - 단계별 의존성 및 산출물

---

## 지원 및 문의

프로젝트 저장소: https://github.com/sunbangamen/coin_hts/

이슈 트래킹: https://github.com/sunbangamen/coin_hts/issues/1
