# Phase 1: 전략 입력 & 백테스트 실행 - 상세 계획

## 1. 문제 성격 요약

Phase 1의 목표는 사용자가 선택한 전략(`volume_long_candle`, `volume_zone_breakout`)과 파라미터를 입력받아 실제 로컬 parquet 데이터로 백테스트를 실행하고, 결과 지표(승률, 평균 수익률, 최대 낙폭, 샘플 수, 신호 목록)를 React UI에서 확인할 수 있도록 end-to-end 파이프라인을 완성하는 것입니다.

현재 Phase 0에서 FastAPI + React 스캐폴딩은 구축되었으며, `/api/backtests/run` 엔드포인트는 더미 결과만 반환합니다. Phase 1에서는 실제 백테스트 로직, 데이터 로더, UI 결과 표현, 파일 저장 구조를 구현하여 Phase 2 이후 확장 가능한 기반을 마련합니다.

**주요 제약:**
- 로컬 parquet 데이터 파일 기반 (외부 DB 없이)
- 동기 방식 실행 (비동기 태스크 큐는 Phase 3에서 검토)
- `DATA_ROOT/results`에 JSON 결과 저장
- Docker Compose 환경 유지

**기대 산출물:**
- 완전히 작동하는 백테스트 실행 API
- 전략별 파라미터 입력 폼 (유효성 검사 포함)
- 결과 테이블 및 차트 UI 컴포넌트
- 실행 로그/결과 JSON 파일 구조
- End-to-end 검증 완료 보고서

---

## 2. 분해 기준 선정

**선택한 분해 축: 데이터 흐름 + 기술 레이어**

Phase 1은 프론트엔드 입력 → 백엔드 처리 → 파일 저장 → UI 출력이라는 명확한 데이터 흐름이 있으며, 각 단계가 기술적으로 독립적입니다. 따라서 다음 기준으로 작업을 나눕니다:

1. **백엔드 데이터 레이어**: parquet 데이터 로더 구현
2. **백엔드 비즈니스 로직**: 전략별 백테스트 엔진 구현
3. **백엔드 API 레이어**: 엔드포인트와 로직 연결, 결과 저장
4. **프론트엔드 입력 검증**: 폼 유효성 검사 및 데이터 구조 정합성
5. **프론트엔드 결과 표현**: 테이블/차트 컴포넌트 구현
6. **통합 검증**: End-to-end 테스트 및 파일 구조 점검

이 방식은 병렬 작업이 가능하고(프론트/백엔드), 각 레이어의 책임이 명확하며, Phase 2 이후 확장 시에도 변경 범위를 최소화할 수 있습니다.

---

## 3. 세부 작업 플랜

### Task 1: 백엔드 데이터 로더 구현

**설명:**
로컬 parquet 파일을 읽어 pandas DataFrame으로 반환하는 데이터 로더 모듈을 작성합니다. 기본 경로는 `DATA_ROOT/{symbol}/{interval}/{year}.parquet` 구조(PDR 기준)를 따르며, 실제 파일 배치가 다를 경우 환경 변수 또는 설정 파일로 커스터마이즈할 수 있도록 옵셔널 매핑을 지원합니다. 날짜 범위와 심볼을 기준으로 데이터를 조회합니다.

**완료 정의 (DoD):**
- [ ] `backend/app/data_loader.py` 모듈 작성 완료
- [ ] `load_ohlcv_data(symbols: List[str], start_date: str, end_date: str, timeframe: str = "1d")` 함수 구현
- [ ] 파일이 없는 경우 적절한 예외 처리 (FileNotFoundError → HTTPException 400)
- [ ] 최소 1개 심볼에 대한 샘플 parquet 파일로 로컬 테스트 완료
- [ ] 로드된 DataFrame에 필수 컬럼(`open`, `high`, `low`, `close`, `volume`, `timestamp`) 존재 검증

**의존성:**
- 데이터 소스 점검 및 샘플 parquet 확보 (Phase 1 준비 작업)
- 없음 (병렬 작업 가능)

**리스크/불확실성:**
- parquet 파일의 실제 스키마/컬럼명이 예상과 다를 수 있음
- 날짜 범위가 여러 파일에 걸쳐 있을 경우 병합 로직 필요 여부 불확실
- 데이터 누락/불완전한 경우 처리 방침 미정

**검증:**
```python
# 테스트 코드 예시
df = load_ohlcv_data(["BTC_KRW"], "2024-01-01", "2024-01-31", "1d")
assert not df.empty
assert all(col in df.columns for col in ["open", "high", "low", "close", "volume"])
```

---

### Task 2: 백테스트 전략 엔진 구현

**설명:**
`volume_long_candle`, `volume_zone_breakout` 두 전략의 시그널 생성 로직을 구현합니다. 각 전략은 OHLCV DataFrame을 입력받아 매수/매도 신호 목록을 반환하며, 수익률/승률/최대 낙폭 등의 지표를 계산합니다.

**완료 정의 (DoD):**
- [ ] `backend/app/strategies/` 디렉토리 생성
- [ ] `backend/app/strategies/base.py`: `Strategy` 추상 베이스 클래스 정의
- [ ] `backend/app/strategies/volume_long_candle.py`: 거래량 급증 + 장대양봉 전략 구현
- [ ] `backend/app/strategies/volume_zone_breakout.py`: 매물대 돌파 전략 구현
- [ ] 각 전략의 `run(df: pd.DataFrame, params: dict) -> BacktestResult` 메서드 구현
- [ ] `BacktestResult` 모델에 `win_rate`, `avg_return`, `max_drawdown`, `samples`, `signals` 포함
- [ ] 유닛 테스트로 샘플 데이터에 대한 시그널 생성 검증

**의존성:**
- Task 1 완료 (데이터 로더로 테스트 데이터 로드 필요)

**리스크/불확실성:**
- 전략의 정확한 시그널 생성 로직(수식, 조건)이 명확히 정의되지 않음
- 수익률 계산 시 수수료/슬리피지 고려 여부 미정
- 최대 낙폭(MDD) 계산 방법 (누적 수익 곡선 vs 개별 거래)

**검증:**
```python
# 테스트 예시
strategy = VolumeLongCandleStrategy()
result = strategy.run(sample_df, {"vol_ma_window": 20, "vol_multiplier": 1.5, "body_pct": 0.02})
assert result.samples > 0
assert 0 <= result.win_rate <= 1
assert len(result.signals) == result.samples
```

---

### Task 3: FastAPI 엔드포인트 실제 로직 연결

**설명:**
`/api/backtests/run` 엔드포인트에서 데이터 로더와 전략 엔진을 호출하여 실제 백테스트를 실행하고, 결과를 `DATA_ROOT/results/{run_id}.json`에 저장합니다. 기존 더미 응답을 실제 계산 결과로 대체합니다.

- **완료 정의 (DoD):**
  - [ ] `backend/app/main.py`의 `run_backtest` 함수 수정
  - [ ] 요청 파라미터 유효성 검사 추가 (심볼 목록 비어있지 않음, 날짜 형식 검증)
  - [ ] `load_ohlcv_data` 호출하여 데이터 로드
  - [ ] 전략 팩토리 패턴으로 `request.strategy`에 맞는 전략 인스턴스 생성
  - [ ] 전략 실행 후 결과를 JSON으로 직렬화하여 파일 저장
  - [ ] `GET /api/backtests/{run_id}` 세부 조회 엔드포인트 신규 추가 (결과 JSON 반환)
  - [ ] 로그 메시지 추가 (실행 시작/종료, 데이터 로드 시간, 결과 저장 경로)
  - [ ] 에러 발생 시 적절한 HTTP 상태 코드 및 메시지 반환 (400, 500)

**의존성:**
- Task 1, Task 2 완료 필수

**리스크/불확실성:**
- 전략 실행 시간이 길어질 경우 타임아웃 이슈 (Phase 3에서 비동기 처리 예정)
- 여러 심볼에 대한 백테스트 결과 집계 방식 (심볼별 개별 결과 vs 통합 지표)

**검증:**
```bash
# curl 테스트
curl -X POST http://localhost:8000/api/backtests/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "volume_long_candle",
    "params": {"vol_ma_window": 20, "vol_multiplier": 1.5, "body_pct": 0.02},
    "symbols": ["BTC_KRW"],
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }'

# 결과 파일 확인
cat data/results/{run_id}.json
```

---

### Task 4: React 폼 유효성 검사 및 데이터 구조 정합성

**설명:**
프론트엔드 폼에서 사용자 입력을 실제 백엔드 데이터 모델에 맞게 검증하고, 잘못된 입력 시 경고 메시지를 표시합니다. 빈 필드, 날짜 범위 오류, 숫자 파라미터 범위 등을 체크합니다.

**완료 정의 (DoD):**
- [ ] `frontend/src/validation.js` 유틸리티 함수 작성
- [ ] 심볼 목록 입력: 최소 1개 이상, 쉼표로 구분, 공백 허용하지 않음
- [ ] 날짜 범위: `start_date <= end_date`, 미래 날짜 불가
- [ ] 전략 파라미터: 숫자 타입, 양수, 범위 제한 (예: `vol_multiplier >= 1.0`)
- [ ] 검증 실패 시 제출 버튼 비활성화 및 오류 메시지 표시
- [ ] `App.jsx`에 검증 로직 통합

**의존성:**
- 없음 (백엔드와 독립적으로 개발 가능)

**리스크/불확실성:**
- 파라미터 범위 제한 기준이 명확하지 않음 (비즈니스 도메인 전문가 검토 필요)
- 백엔드 API와 프론트엔드 검증 로직 중복 (일관성 유지 필요)

**검증:**
- 유효하지 않은 입력(빈 심볼, 잘못된 날짜 등)으로 폼 제출 시도 → 오류 메시지 확인
- 브라우저 콘솔에 경고 없이 깨끗한 상태 확인

---

### Task 5: React 결과 테이블 및 차트 컴포넌트 구현

**설명:**
백테스트 결과를 시각적으로 표현하는 UI 컴포넌트를 작성합니다. 지표(승률, 평균 수익률, 최대 낙폭, 샘플 수)를 테이블로 보여주고, 신호 목록을 시간순 테이블로 렌더링합니다. 선택적으로 간단한 차트(수익률 곡선) 추가를 검토합니다.

- **완료 정의 (DoD):**
  - [ ] `frontend/src/components/BacktestResults.jsx` 컴포넌트 작성
  - [ ] 지표 테이블: 승률(%), 평균 수익률(%), 최대 낙폭(%), 샘플 수 표시
  - [ ] 신호 목록 테이블: 심볼, 타입(buy/sell), 시간, 가격, 수익률 등 컬럼 표시
  - [ ] 데이터 없을 경우 안내 메시지 표시
  - [ ] `App.jsx`에서 `/api/backtests/latest` 응답으로 받은 `run_id`를 사용해 `/api/backtests/{run_id}` 엔드포인트를 호출하고 상세 결과 로드
  - [ ] (선택) Recharts 라이브러리로 수익률 곡선 차트 추가

**의존성:**
- Task 3 완료 (API가 실제 결과 JSON을 반환해야 프론트 테스트 가능)

**리스크/불확실성:**
- JSON 파일을 프론트에서 직접 읽을 수 없으므로, 백엔드에 `/api/backtests/{run_id}/details` 같은 엔드포인트 추가 필요 가능
- 차트 라이브러리 선택 및 학습 곡선

**검증:**
- 백테스트 실행 후 결과 페이지에서 지표 및 신호 목록 정상 렌더링 확인
- 여러 심볼, 다양한 전략 결과로 UI 레이아웃 깨지지 않는지 테스트

---

### Task 6: End-to-End 통합 테스트 및 파일 구조 점검

**설명:**
전체 파이프라인을 최소 한 번 이상 실행하여 프론트엔드 입력 → 백엔드 실행 → 파일 저장 → UI 표시까지 모든 단계가 정상 작동하는지 검증합니다. 로그, 결과 JSON 파일 구조가 Phase 2 이후에도 확장 가능한지 점검합니다.

**완료 정의 (DoD):**
- [ ] Docker Compose 환경에서 전체 스택 실행 (`docker-compose up`)
- [ ] React 폼에서 전략 선택, 파라미터 입력, 심볼/날짜 설정 후 백테스트 실행
- [ ] 백엔드 로그에서 데이터 로드, 전략 실행, 결과 저장 메시지 확인
- [ ] `DATA_ROOT/results/{run_id}.json` 파일 생성 및 내용 검증
- [ ] 프론트엔드에서 결과 테이블/차트 정상 표시 확인
- [ ] 다른 전략(`volume_zone_breakout`)으로 재실행하여 동일한 플로우 재검증
- [ ] 파일 구조 점검: 결과 JSON 스키마가 Phase 2에서 추가 필드(심볼별 상세, 메타데이터 등) 확장 가능하도록 설계되었는지 확인

**의존성:**
- Task 1~5 모두 완료 필수

**리스크/불확실성:**
- 네트워크 지연, Docker 볼륨 마운트 이슈 등 환경 문제
- 샘플 데이터가 충분하지 않아 테스트 시나리오 제한적

**검증:**
- 2가지 전략 × 2개 이상 심볼로 총 4회 이상 백테스트 실행
- 결과 파일이 누적 저장되고, UI에서 최신 결과 조회 정상 동작
- 로그 파일에 오류 없음

---

## 4. 누락 탐지

Phase 1 작업 플랜을 검토하며 다음 질문들을 고려해야 합니다:

1. **parquet 데이터 파일의 실제 스키마와 저장 위치가 명확히 정의되었는가?**
   - 샘플 데이터 준비 작업(Task 0)이 선행되어야 하며, 파일명 규칙, 디렉토리 구조, 컬럼명이 문서화되어야 합니다.

2. **전략별 시그널 생성 로직의 정확한 수식과 조건이 명세되어 있는가?**
   - `volume_long_candle`, `volume_zone_breakout` 전략의 구체적인 알고리즘(예: 거래량 이동평균 계산 방식, 돌파 판단 기준)이 PDR이나 별도 문서에 정의되어 있어야 합니다.

3. **여러 심볼에 대한 백테스트 결과를 어떻게 집계하고 표현할 것인가?**
   - 현재 Task에서는 심볼별 개별 결과 vs 통합 지표 처리 방식이 불명확합니다. 이를 명확히 하지 않으면 UI 표현이나 JSON 스키마 설계가 일관되지 않을 수 있습니다.

4. **백엔드 API에서 상세 결과 JSON을 프론트엔드에 전달하는 방법은?**
   - Task 5에서 언급했듯이, 파일 경로만 반환하면 프론트에서 읽을 수 없으므로 `/api/backtests/{run_id}/details` 같은 엔드포인트 추가가 필요할 수 있습니다.

5. **에러 핸들링 및 로깅 전략이 Phase 2 이후 확장 가능하도록 설계되었는가?**
   - 현재 Task에는 기본적인 예외 처리만 언급되어 있으나, 구조화된 로깅(JSON 로그), 에러 분류(재시도 가능 vs 치명적 오류) 등 장기적 운영을 위한 설계가 필요합니다.

---

## 5. 리파인 제안

다음 반복에서 플랜을 다듬기 위해 확인하거나 조사해야 할 항목:

1. **샘플 parquet 데이터 준비 및 스키마 문서화 (Task 0)**
   - 실제 데이터 소스(바이낸스 API, 업비트 API 등)에서 샘플 다운로드
   - `DATA_ROOT/parquet/` 디렉토리 구조 및 파일명 규칙 문서 작성
   - 컬럼 타입, 타임존, 누락값 처리 방침 정리

2. **전략 알고리즘 명세 문서 작성**
   - `volume_long_candle`: 이동평균 계산식, 거래량 배수 적용 방법, 장대양봉 판단 기준(몸통 비율 계산)
   - `volume_zone_breakout`: 매물대 산출 방법(가격 구간별 거래량 집계), 상위 백분위 계산, 돌파 버퍼 적용 방식
   - 수익률 계산: 진입 가격, 청산 가격, 수수료율(예: 0.1%), 슬리피지 가정

3. **백엔드 상세 결과 조회 API 추가 검토**
   - `/api/backtests/{run_id}` 엔드포인트로 전체 결과 JSON 반환
   - 또는 `/api/backtests/{run_id}/summary`, `/api/backtests/{run_id}/signals` 분리
   - 파일 I/O 성능 고려 (캐싱 전략)

4. **유닛 테스트 및 통합 테스트 프레임워크 선정**
   - 백엔드: pytest + pytest-mock
   - 프론트엔드: Vitest + React Testing Library
   - 테스트 커버리지 목표 설정 (최소 70%)

5. **로깅 및 모니터링 초기 설계**
   - 구조화된 로깅 라이브러리(예: `structlog`) 도입
   - 백테스트 실행 시간, 데이터 로드 시간, 시그널 생성 시간 측정
   - Phase 3에서 비동기 태스크 큐 도입 시 로그 추적 가능하도록 `run_id` 기반 로그 태깅

6. **Phase 2 전환을 위한 확장 포인트 정의**
   - 결과 JSON 스키마에 `version` 필드 추가 (스키마 변경 추적)
   - 전략 설정 파일(`DATA_ROOT/strategies/{strategy_name}.json`) 구조 초안
   - 시그널 뷰어를 위한 API 엔드포인트 프리뷰 (`/api/signals/active`, `/api/strategies`)

---

## 작업 순서 제안

**병렬 작업 가능:**
- Task 0 (샘플 데이터 준비) → Task 1, Task 4 동시 진행
- Task 2 (전략 엔진) ← Task 1 완료 후 시작
- Task 3 (API 연결) ← Task 1, Task 2 완료 후 시작
- Task 5 (프론트 결과 UI) ← Task 3 완료 후 시작, Task 4와 독립적
- Task 6 (E2E 테스트) ← 모든 Task 완료 후

**예상 소요 시간:**
- Task 0: 2시간
- Task 1: 4시간
- Task 2: 6시간
- Task 3: 4시간
- Task 4: 3시간
- Task 5: 5시간
- Task 6: 4시간
- **총 예상: ~28시간** (병렬 작업 시 ~15시간으로 단축 가능)

---

## 산출물 체크리스트

Phase 1 완료 시 다음 항목이 모두 준비되어야 합니다:

- [ ] `backend/app/data_loader.py` (parquet 로더)
- [ ] `backend/app/strategies/base.py`, `volume_long_candle.py`, `volume_zone_breakout.py` (전략 엔진)
- [ ] `backend/app/main.py` (실제 로직 연결된 `/api/backtests/run`)
- [ ] `frontend/src/validation.js` (입력 검증 유틸)
- [ ] `frontend/src/components/BacktestResults.jsx` (결과 UI)
- [ ] `data/results/` 디렉토리에 샘플 결과 JSON 파일 최소 2개
- [ ] `docs/coin/mvp/strategy_spec.md` (전략 알고리즘 명세)
- [ ] `docs/coin/mvp/data_schema.md` (parquet 데이터 스키마)
- [ ] `docs/coin/mvp/phase1_test_report.md` (E2E 테스트 결과 보고서)

---

## Phase 2 전환 조건

다음 조건을 모두 충족하면 Phase 2로 전환 가능합니다:

1. 2가지 전략 모두 실제 데이터로 백테스트 실행 성공
2. UI에서 지표 및 신호 목록이 정상 표시됨
3. 결과 JSON 스키마가 심볼별 상세 정보 추가 가능하도록 설계됨
4. Docker Compose 환경에서 오류 없이 10회 이상 연속 실행 성공
5. 로그 파일에 실행 흐름 추적 가능한 메시지 존재
6. Phase 1 완료 보고서 작성 및 팀 리뷰 완료
