# 심볼/타임프레임 동기화 가이드

**관련 Issue**: #37 - [Feature] 실전 백테스트 기준 타임프레임/심볼 통일화

**최종 수정**: 2025-11-12

---

## 개요

프론트엔드(React)와 백엔드(FastAPI/Python)가 공유하는 **기본 심볼 목록**과 **타임프레임 목록**을 동기화하기 위한 가이드입니다.

이 문서에서 정의한 상수들은:
1. 데이터 관리 UI (DataManagementPage)에서 드롭다운으로 표시
2. 백테스트 UI (BacktestPage)에서 선택 가능
3. 자동 데이터 수집 스케줄러에서 수집 대상으로 사용

---

## 확정된 상수

### 기본 심볼 목록 (DEFAULT_SYMBOLS)

```
KRW-BTC, KRW-ETH, KRW-XRP, KRW-SOL, KRW-XLM, KRW-ADA, KRW-DOGE, KRW-BCH, KRW-NEAR
```

**설명**: 원화 기준 9개 주요 암호화폐 심볼 (한국 거래소 Upbit 기준)

### 타임프레임 목록 (TIMEFRAMES)

```
1M (1분), 5M (5분), 1H (1시간), 1D (1일), 1W (1주)
```

**설명**: 총 5개 타임프레임을 지원하며, 모두 대문자로 표기

---

## 프론트엔드 정의

### 위치

#### DataManagementPage.jsx
- **파일**: `frontend/src/pages/DataManagementPage.jsx`
- **줄 번호**: Line 8-11
- **상수**:
  ```javascript
  const DEFAULT_SYMBOLS = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL', 'KRW-XLM', 'KRW-ADA', 'KRW-DOGE', 'KRW-BCH', 'KRW-NEAR']
  const TIMEFRAMES = ['1M', '5M', '1H', '1D', '1W']
  ```

**사용처**:
1. 파일 업로드 폼 - 심볼 드롭다운
2. 데이터 조회 필터 - 타임프레임 드롭다운
3. 자동 수집 패널 - 심볼/타임프레임 드롭다운
4. 안내 문본 - 지원 심볼/타임프레임 표시

#### BacktestPage.jsx
- **파일**: `frontend/src/pages/BacktestPage.jsx`
- **줄 번호**: Line 34
- **상수**:
  ```javascript
  const TIMEFRAMES = ['1M', '5M', '1H', '1D', '1W']
  ```

**사용처**:
1. 백테스트 폼 - 타임프레임 드롭다운

---

## 백엔드 정의

### 위치

#### scheduler_config.py (중앙 설정 파일)
- **파일**: `backend/app/scheduler_config.py`
- **줄 번호**: Line 17-23
- **상수**:
  ```python
  DEFAULT_SYMBOLS = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL', 'KRW-XLM', 'KRW-ADA', 'KRW-DOGE', 'KRW-BCH', 'KRW-NEAR']
  DEFAULT_TIMEFRAMES = ['1M', '5M', '1H', '1D', '1W']
  ```

**핵심 함수**:
- `get_scheduler_symbols()` - 환경 변수에서 심볼 로드 (기본값 사용)
- `get_scheduler_timeframes()` - 환경 변수에서 타임프레임 로드 (기본값 사용)
- `get_default_symbols()` - 기본 심볼 목록 반환 (프론트엔드와 동기화)
- `get_default_timeframes()` - 기본 타임프레임 목록 반환 (프론트엔드와 동기화)

#### scheduler.py (스케줄러)
- **파일**: `backend/app/scheduler.py`
- **줄 번호**: Line 24-27, 40-41
- **사용**:
  ```python
  from backend.app.scheduler_config import (
      get_scheduler_symbols,
      get_scheduler_timeframes,
      log_config_info
  )

  # 환경 변수에서 로드 (또는 기본값 사용)
  DEFAULT_SYMBOLS = get_scheduler_symbols()
  DEFAULT_TIMEFRAMES = get_scheduler_timeframes()
  ```

### 환경 변수 설정

#### docker-compose.yml
- **파일**: `docker-compose.yml`
- **서비스**:
  - `backend` (Line 57-61)
  - `worker` (Line 105-106)
  - `test` (Line 142-143)
  - `e2e-test` (Line 219-220)

**환경 변수**:
```yaml
SCHEDULER_SYMBOLS=KRW-BTC,KRW-ETH,KRW-XRP,KRW-SOL,KRW-XLM,KRW-ADA,KRW-DOGE,KRW-BCH,KRW-NEAR
SCHEDULER_TIMEFRAMES=1M,5M,1H,1D,1W
```

#### .env (로컬 개발용, 필요시)
프로젝트 루트에 `.env` 파일을 만들어 다음과 같이 설정할 수 있습니다:

```env
# 스케줄러 설정 (Issue #37)
SCHEDULER_SYMBOLS=KRW-BTC,KRW-ETH,KRW-XRP,KRW-SOL,KRW-XLM,KRW-ADA,KRW-DOGE,KRW-BCH,KRW-NEAR
SCHEDULER_TIMEFRAMES=1M,5M,1H,1D,1W
ENABLE_SCHEDULER=true
SCHEDULER_HOUR=9
SCHEDULER_MINUTE=0
```

---

## 동기화 체크리스트

### 추가/변경 시 반드시 확인할 사항

#### ✅ 프론트엔드 - 백엔드 동기화

- [ ] `DataManagementPage.jsx`의 `DEFAULT_SYMBOLS` 변경 시 `scheduler_config.py`의 `DEFAULT_SYMBOLS` 동시 수정
- [ ] `DataManagementPage.jsx`의 `TIMEFRAMES` 변경 시 `BacktestPage.jsx`와 `scheduler_config.py` 동시 수정
- [ ] `docker-compose.yml`의 `SCHEDULER_SYMBOLS` 값이 `DEFAULT_SYMBOLS`과 일치
- [ ] `docker-compose.yml`의 `SCHEDULER_TIMEFRAMES` 값이 `TIMEFRAMES`과 일치

#### ✅ 모든 서비스 환경 변수 동기화

- [ ] `backend` 서비스의 환경 변수 확인
- [ ] `worker` 서비스의 환경 변수 확인
- [ ] `test` 서비스의 환경 변수 확인
- [ ] `e2e-test` 서비스의 환경 변수 확인

#### ✅ 코드 검증

- [ ] 프론트엔드 빌드 성공 (타임프레임 표기 오류 없음)
- [ ] 백엔드 서버 시작 시 `scheduler_config.py`의 로깅 메시지 확인
- [ ] 환경 변수가 올바르게 파싱되었는지 로그로 확인

---

## 변경 시나리오별 가이드

### 시나리오 1: 새로운 심볼 추가

예시: `KRW-SHIB` 추가

**수정 파일**:
1. `frontend/src/pages/DataManagementPage.jsx` (Line 8)
2. `backend/app/scheduler_config.py` (Line 18)
3. `docker-compose.yml`:
   - `backend` 서비스 (Line 57)
   - `worker` 서비스 (Line 105)
   - `test` 서비스 (Line 142)
   - `e2e-test` 서비스 (Line 219)

**예시 변경**:
```javascript
// DataManagementPage.jsx
const DEFAULT_SYMBOLS = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL', 'KRW-XLM', 'KRW-ADA', 'KRW-DOGE', 'KRW-BCH', 'KRW-NEAR', 'KRW-SHIB']
```

```python
# scheduler_config.py
DEFAULT_SYMBOLS = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL', 'KRW-XLM', 'KRW-ADA', 'KRW-DOGE', 'KRW-BCH', 'KRW-NEAR', 'KRW-SHIB']
```

```yaml
# docker-compose.yml (모든 서비스)
SCHEDULER_SYMBOLS=KRW-BTC,KRW-ETH,KRW-XRP,KRW-SOL,KRW-XLM,KRW-ADA,KRW-DOGE,KRW-BCH,KRW-NEAR,KRW-SHIB
```

### 시나리오 2: 새로운 타임프레임 추가

예시: `1W` 제거, `2H` 추가

**수정 파일**:
1. `frontend/src/pages/DataManagementPage.jsx` (Line 11)
2. `frontend/src/pages/BacktestPage.jsx` (Line 34)
3. `backend/app/scheduler_config.py` (Line 23)
4. `docker-compose.yml`:
   - `backend` 서비스 (Line 58)
   - `worker` 서비스 (Line 106)
   - `test` 서비스 (Line 143)
   - `e2e-test` 서비스 (Line 220)

**예시 변경**:
```javascript
// DataManagementPage.jsx & BacktestPage.jsx
const TIMEFRAMES = ['1M', '5M', '2H', '1H', '1D']
```

```python
# scheduler_config.py
DEFAULT_TIMEFRAMES = ['1M', '5M', '2H', '1H', '1D']
```

```yaml
# docker-compose.yml (모든 서비스)
SCHEDULER_TIMEFRAMES=1M,5M,2H,1H,1D
```

---

## 유지보수 팁

### 1. 배포 전 확인

배포 전 다음을 반드시 검증하세요:

```bash
# 프론트엔드 상수 확인
grep -n "const DEFAULT_SYMBOLS\|const TIMEFRAMES" frontend/src/pages/DataManagementPage.jsx
grep -n "const TIMEFRAMES" frontend/src/pages/BacktestPage.jsx

# 백엔드 상수 확인
grep -n "DEFAULT_SYMBOLS\|DEFAULT_TIMEFRAMES" backend/app/scheduler_config.py

# 환경 변수 확인
grep -n "SCHEDULER_SYMBOLS\|SCHEDULER_TIMEFRAMES" docker-compose.yml
```

### 2. 런타임 로깅

백엔드 로그에서 다음을 확인하세요:

```
📋 스케줄러 설정 (scheduler_config.py)
=======================
심볼 (SCHEDULER_SYMBOLS): KRW-BTC, KRW-ETH, ...
타임프레임 (SCHEDULER_TIMEFRAMES): 1M, 5M, 1H, 1D, 1W
=======================
```

### 3. 테스트 자동화

통합 테스트로 동기화를 검증합니다:

**파일**: `tests/integration/test_symbol_timeframe_sync.py`

```python
def test_frontend_symbols_match_backend():
    """프론트엔드 DEFAULT_SYMBOLS와 백엔드 SCHEDULER_SYMBOLS 동기화 확인"""
    # TODO: Phase 5에서 구현

def test_frontend_timeframes_match_backend():
    """프론트엔드 TIMEFRAMES와 백엔드 SCHEDULER_TIMEFRAMES 동기화 확인"""
    # TODO: Phase 5에서 구현
```

---

## 관련 문서

- **Issue #37 분석**: `docs/coin/mvp/ri_22.md`
- **자동 데이터 수집 가이드**: `docs/AUTOMATED_DATA_COLLECTION_GUIDE.md`
- **워크플로 검증**: `docs/coin/mvp/BACKTEST_WORKFLOW_VALIDATION.md` (Phase 4)
- **MVP 단계 계획**: `docs/coin/mvp_phase.md`

---

## FAQ

### Q1: 환경 변수 없이 기본값을 사용할 수 있나요?

**답변**: 네. `scheduler_config.py`의 `get_scheduler_symbols()`, `get_scheduler_timeframes()` 함수는 환경 변수가 없거나 비어 있으면 `DEFAULT_SYMBOLS`, `DEFAULT_TIMEFRAMES`를 반환합니다.

### Q2: 기존 데이터와의 호환성은?

**답변**:
- 타임프레임 표기를 통일했으므로 (예: `1d` → `1D`), 기존 Parquet 파일의 경로도 업데이트해야 합니다.
- 마이그레이션이 필요한 경우 `scripts/migrate_data_structure.py`를 참고하세요 (Phase 4에서 문서화).

### Q3: 여러 환경(개발/운영)에서 다른 심볼/타임프레임을 사용할 수 있나요?

**답변**: 네. 각 환경의 `docker-compose.yml` 또는 `.env` 파일에서 `SCHEDULER_SYMBOLS`, `SCHEDULER_TIMEFRAMES`을 다르게 설정하면 됩니다. 다만 **프론트엔드는 하드코딩되어 있으므로** 프론트엔드 빌드 시 `DEFAULT_SYMBOLS`, `TIMEFRAMES`을 동적으로 변경하거나, Phase 5에서 API로 제공하는 방식을 고려해야 합니다.

---

## 버전 이력

| 날짜 | 작성자 | 변경 사항 |
|------|--------|---------|
| 2025-11-12 | Claude Code | 초안 작성 (Issue #37 Phase 3) |

