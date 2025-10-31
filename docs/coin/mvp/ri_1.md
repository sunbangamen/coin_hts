# 이슈 #1 해결 계획

## 1. 이슈 정보 요약

**제목**: [Phase 1] Task 1: 백엔드 데이터 로더 구현

**URL**: https://github.com/sunbangamen/coin_hts/issues/1

**상태**: OPEN

**핵심 요구사항**:
- 로컬 parquet 파일을 읽어 pandas DataFrame으로 반환하는 데이터 로더 모듈 구현
- 파일 구조: `DATA_ROOT/{symbol}/{timeframe}/{year}.parquet` (예: `DATA_ROOT/BTC_KRW/1M/2022.parquet`)
- 날짜 범위와 심볼을 기준으로 데이터 조회
- 필수 컬럼 검증 및 예외 처리

---

## 2. 문제 이해

### 핵심 기능
백엔드에서 과거 OHLCV(Open, High, Low, Close, Volume) 데이터를 파일 시스템에서 읽어오는 기본 인프라 구축

### 주요 전제 조건
- Phase 0의 기본 스캐폴딩이 완료되어 있음
- PDR 문서에 디렉토리 구조가 정의되어 있음
- 샘플 parquet 파일이 있거나 확보 가능해야 함

### 불확실성
- 실제 parquet 파일의 스키마가 예상과 일치하는지 미확인
- 여러 연도에 걸친 데이터 병합 시 성능 이슈 가능성
- 데이터 누락/불완전 시 처리 방침 명확화 필요

### 도메인 준수 사항
- 한국 거래소 데이터를 기준으로 하되 입력으로 받은 KST 기반 ISO8601 타임스탬프(`YYYY-MM-DDTHH:MM:SS+09:00`)를 내부적으로 UTC로 변환해 처리한다.
- 타임존 정보가 없는 날짜 문자열은 KST로 간주한 뒤 즉시 `Asia/Seoul` → `UTC` 변환을 수행하고, 반환 DataFrame의 `timestamp` 컬럼은 UTC 기준으로 통일한다.
- parquet 경로(`{symbol}/{timeframe}/{year}.parquet`)에 심볼·주기만 정의되어 있다는 전제를 반영하고, 파일 안에 해당 컬럼이 없을 경우 로더에서 경로 정보를 주입한다.
- 심볼은 모두 대문자+언더바 표기(`BTC_KRW`)로 통일하고, 타임프레임은 대문자 단위 문자열(`1S`, `1M`, `5M`, `1H`, `1D` 등)을 사용한다.

---

## 3. 해결 계획

### 단계 1: 환경 및 데이터 소스 확인
**작업 내용**:
- 현재 프로젝트 구조 파악 (`backend/app` 디렉토리 존재 여부)
- `DATA_ROOT` 설정 확인 (환경 변수 또는 설정 파일)
- 샘플 parquet 파일 존재 여부 확인 또는 생성
- Dockerfile 및 `docker-compose.yml` 존재 여부 확인, 빌드 시 `DATA_ROOT`를 컨테이너 내 `/data`로 기본 설정할지 확정

**예상 산출물**:
- 프로젝트 구조 문서
- 샘플 데이터 파일 경로 확인
- 컨테이너 실행 시 필요한 환경 변수/볼륨 정의서

**확인 방법**:
```bash
ls -la backend/app/
head .env  # DATA_ROOT 확인
```

**의존성**: 없음

---

### 단계 2: `data_loader.py` 모듈 구현
**작업 내용**:
- `backend/app/data_loader.py` 파일 생성
- `load_ohlcv_data()` 함수 구현
  - 날짜 범위에서 필요한 연도 추출
  - 각 심볼/timeframe/year 조합으로 파일 경로 생성
  - 존재하는 파일만 읽어서 병합
  - 경로에서 파생한 `symbol`·`timeframe` 값을 DataFrame에 주입하고 UTC 기준 `timestamp` 컬럼으로 정규화
  - 날짜 범위 필터링
  - 필수 컬럼 검증

**예상 산출물**:
```python
def load_ohlcv_data(
    symbols: List[str],
    start_date: str,
    end_date: str,
    timeframe: str = "1d"
) -> pd.DataFrame:
    """
    로컬 parquet 파일에서 OHLCV 데이터 로드

    Returns:
        pd.DataFrame: 컬럼 [timestamp, symbol, timeframe, open, high, low, close, volume]

    Raises:
        HTTPException: 파일이 없거나 필수 컬럼 누락 시
    """
```

**확인 방법**:
- 함수 시그니처 및 docstring 작성 완료
- 기본 로직 구현 완료

**의존성**: 단계 1 완료

**위험 요소**:
- parquet 파일 스키마가 예상과 다를 경우 컬럼명 매핑 필요
- 메모리 이슈 (대용량 데이터 병합 시)

---

### 단계 3: 예외 처리 및 검증 로직 추가
**작업 내용**:
- 파일 미존재 시 `FileNotFoundError` → `HTTPException(404)` 변환
- 필수 컬럼 누락 시 예외 발생
- 빈 DataFrame 처리 로직
- 입력 파라미터 오류(타임존 누락 등)는 `HTTPException(422)`로 변환
- 로깅 추가 (파일 읽기 실패, 병합 결과 등)

**예상 산출물**:
- 견고한 예외 처리 코드
- 로깅 구문 추가

**확인 방법**:
- 존재하지 않는 파일 경로로 테스트
- 잘못된 컬럼을 가진 파일로 테스트

**의존성**: 단계 2 완료

---

### 단계 4: 유닛 테스트 작성
**작업 내용**:
- `tests/test_data_loader.py` 작성
- 정상 케이스 테스트 (단일 심볼, 여러 심볼, 여러 연도)
- 예외 케이스 테스트 (파일 없음, 컬럼 누락)
- 날짜 범위 필터링 검증
- 테스트 픽스처는 실행 시점에 임시 디렉터리에 parquet 파일을 생성해 심볼·타임프레임 주입 및 UTC 변환 로직을 검증

**예상 산출물**:
- 최소 5개 이상의 테스트 케이스
- 코드 커버리지 80% 이상

**확인 방법**:
```bash
pytest tests/test_data_loader.py -v
```

**의존성**: 단계 3 완료

---

### 단계 5: 통합 테스트 및 문서화
**작업 내용**:
- 실제 샘플 데이터로 end-to-end 테스트
- README 또는 함수 docstring 업데이트
- 코드 리뷰 준비 (타입 힌트, 주석 정리)

**예상 산출물**:
- 통합 테스트 성공
- 문서화 완료

**확인 방법**:
- 이슈의 Acceptance Criteria 체크리스트 모두 완료
- 코드 스타일 검사 통과

**의존성**: 단계 4 완료

---

- KST 입력을 UTC로 정규화하는 규칙과 반환 스키마(UTC `timestamp`, 경로 기반의 `symbol`, `timeframe`)는 위 계획에 따라 구현한다.
- 데이터 로더 시그니처는 `symbols` 인자를 필수로 유지하고, `timeframe`은 `1D` 기본값을 제공한다.
- 테스트 데이터는 실행 시점에 동적으로 생성하며, 실제 샘플 파일이 필요한 경우 별도 태스크로 다룬다.
- 컨테이너 환경에서는 `DATA_ROOT`를 `/data`로 기본 설정하고, 로컬 개발 시 `-v $(pwd)/data:/data` 형태로 마운트해 parity를 맞춘다.

---

## 5. 진행 승인 요청

위 계획대로 진행해도 괜찮을까요?

- 단계별로 진행하며 각 단계마다 확인을 받고 싶으시면 말씀해 주세요.
- 한 번에 모든 구현을 완료하길 원하시면 바로 시작하겠습니다.
- 계획에 수정이 필요한 부분이 있다면 알려주세요.

---

## 부록: 컨테이너 실행 전략 (초안)

### Docker 이미지 구성
- 베이스 이미지: `python:3.11-slim`
- 주요 패키지: `pandas`, `pyarrow`, `fastapi`, `uvicorn`, `pytest`
- 작업 디렉터리: `/app`
- 환경 변수:
  - `DATA_ROOT=/data`
  - `TZ=Asia/Seoul` (컨테이너 내부 시간은 KST지만, 데이터는 UTC로 변환해 처리)
- 볼륨: 호스트의 `./data` 디렉터리를 컨테이너 `/data`로 마운트

### 빌드 및 실행 예시
```bash
docker build -t coin-backend .
docker run --rm \
  -v "$(pwd)/data:/data" \
  -e DATA_ROOT=/data \
  coin-backend pytest tests/test_data_loader.py -v
```

### 로컬 개발 작동 흐름
1. 로컬에서 `data/` 디렉터리에 parquet 샘플 데이터를 생성하거나 동적으로 만들어 테스트한다.
2. `docker-compose.yml`이 있는 경우, `services.backend.volumes`에 `./data:/data`를 선언하고 `environment`에 `DATA_ROOT=/data`를 설정한다.
3. 백엔드 앱 실행은 `docker compose up backend`로, 테스트 실행은 `docker compose run --rm backend pytest ...`로 일관성을 유지한다.

### CI 통합 고려 사항
- CI 파이프라인에서 동일한 이미지(`coin-backend`)를 사용하고, `DATA_ROOT`를 워크스페이스 하위 임시 디렉터리로 지정한다.
- 테스트 픽스처는 컨테이너 실행 시점에 생성되므로 추가 아티팩트 업로드 없이도 재현 가능하다.
- 필요 시 `make test-docker` 같은 타겟을 정의해 로컬/CI 명령어를 통일한다.
