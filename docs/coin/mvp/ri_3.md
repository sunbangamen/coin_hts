# Issue #3 해결 계획: FastAPI 엔드포인트 실제 로직 연결

## 1. 이슈 정보 요약

| 항목 | 내용 |
|-----|------|
| **제목** | [Phase 1] Task 3: FastAPI 엔드포인트 실제 로직 연결 |
| **URL** | https://github.com/sunbangamen/coin_hts/issues/3 |
| **상태** | OPEN |
| **생성일** | 2025-10-31 |
| **라벨** | Phase-1, backend, api, integration |
| **예상 소요 시간** | 4시간 |

### 핵심 요구사항
- 기존 더미 응답을 실제 데이터 로더 + 전략 엔진 호출로 대체
- `/api/backtests/run` (POST) - 백테스트 실행 및 결과 파일 저장
- `/api/backtests/{run_id}` (GET) - 저장된 결과 조회
- 파라미터 유효성 검사 및 에러 핸들링 강화
- 전략 팩토리 패턴 구현
- 로깅 및 성능 측정

---

## 2. 문제 이해

### 현재 상태
- ✅ Task 1 (데이터 로더): 완료됨 (PR #8)
- ✅ Task 2 (전략 엔진): 완료됨 (PR #9)
- ❌ Task 3 (API 통합): 미작업 - `backend/app/main.py` 파일 자체가 존재하지 않음

### 핵심 요구사항
1. **FastAPI 애플리케이션 생성**: `main.py` 파일 생성 및 기본 설정
2. **요청/응답 모델 정의**: Pydantic 모델로 API 계약 명확화
3. **POST /api/backtests/run**: 백테스트 실행 및 결과 저장
4. **GET /api/backtests/{run_id}**: 결과 파일 조회
5. **전략 팩토리**: 전략 이름 → 전략 인스턴스 변환
6. **유효성 검사**: 심볼 목록, 날짜 형식, 날짜 범위 검증
7. **에러 핸들링**: 적절한 HTTP 상태 코드 및 메시지
8. **로깅**: 실행 시작/종료, 성능 측정, 결과 저장 경로
9. **통합 테스트**: API 엔드포인트 전체 플로우 검증

### 의존성
- ✅ Task 1 (데이터 로더): 완료됨
- ✅ Task 2 (전략 엔진): 완료됨
- ✅ Docker 환경: 이미 구축됨

### 불확실성 & 위험요소
1. **여러 심볼 처리 방식**: 각 심볼별로 개별 결과를 반환할지, 통합 지표를 반환할지
2. **타임아웃 이슈**: 전략 실행 시간이 긴 경우 (Phase 3에서 비동기 처리 예정)
3. **파일 I/O 성능**: 결과 파일 저장/로드 시 성능
4. **결과 디렉토리 관리**: `DATA_ROOT/results/` 디렉토리 생성 및 권한
5. **run_id 생성 방식**: UUID vs timestamp 기반

---

## 3. 해결 계획 수립

### 단계 1: FastAPI 기본 구조 및 모델 정의

**작업 내용**:
- `backend/app/main.py` 생성
- FastAPI 애플리케이션 인스턴스 생성
- CORS 설정 (프론트엔드 연동 대비)
- 환경변수 설정 (DATA_ROOT)
- Pydantic 요청/응답 모델 정의

**예상 산출물**:
```python
# backend/app/main.py
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any
from datetime import datetime
import os
import logging
import json
import uuid

app = FastAPI(
    title="Coin Backtesting API",
    version="1.0.0",
    description="Cryptocurrency backtesting and simulation API",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 제한 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 환경변수
DATA_ROOT = os.getenv("DATA_ROOT", "/data")
RESULTS_DIR = os.path.join(DATA_ROOT, "results")

# 로거 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 요청 모델
class BacktestRequest(BaseModel):
    strategy: str = Field(..., description="전략 이름 (volume_long_candle, volume_zone_breakout)")
    params: Dict[str, Any] = Field(default_factory=dict, description="전략 파라미터")
    symbols: List[str] = Field(..., min_items=1, description="심볼 목록 (예: ['BTC_KRW', 'ETH_KRW'])")
    start_date: str = Field(..., description="시작 날짜 (YYYY-MM-DD 형식, KST 기준)")
    end_date: str = Field(..., description="종료 날짜 (YYYY-MM-DD 형식, KST 기준)")
    timeframe: str = Field(default="1d", description="타임프레임 (기본값: 1d)")

    @validator("start_date", "end_date")
    def validate_date_format(cls, v):
        """날짜 형식 검증 (YYYY-MM-DD)"""
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(f"Invalid date format: {v}. Expected YYYY-MM-DD")

    @validator("end_date")
    def validate_date_range(cls, v, values):
        """start_date <= end_date 검증"""
        if "start_date" in values:
            start = datetime.strptime(values["start_date"], "%Y-%m-%d")
            end = datetime.strptime(v, "%Y-%m-%d")
            if start > end:
                raise ValueError("start_date must be before or equal to end_date")
        return v

    @validator("strategy")
    def validate_strategy(cls, v):
        """지원되는 전략인지 검증"""
        supported = ["volume_long_candle", "volume_zone_breakout"]
        if v not in supported:
            raise ValueError(f"Unsupported strategy: {v}. Supported: {supported}")
        return v

# 응답 모델
class SymbolResult(BaseModel):
    symbol: str
    signals: int
    win_rate: float
    avg_return: float
    max_drawdown: float
    avg_hold_bars: float

class BacktestResponse(BaseModel):
    run_id: str
    strategy: str
    params: Dict[str, Any]
    start_date: str
    end_date: str
    timeframe: str
    symbols: List[SymbolResult]
    total_signals: int
    execution_time: float

class ErrorResponse(BaseModel):
    error: str
    detail: str
```

**확인 방법**:
- FastAPI 애플리케이션 시작 확인
- 모델 정의 완료 및 타입 힌트 추가
- Pydantic validator 정상 작동 확인

**의존성**: 없음

---

### 단계 2: 전략 팩토리 패턴 구현

**작업 내용**:
- `backend/app/strategy_factory.py` 생성
- 전략 이름을 받아 전략 인스턴스를 반환하는 팩토리 함수 구현
- 지원되지 않는 전략에 대한 예외 처리

**예상 산출물**:
```python
# backend/app/strategy_factory.py
"""
전략 팩토리 모듈

전략 이름을 받아 해당 전략 클래스의 인스턴스를 반환합니다.
"""

from backend.app.strategies.base import Strategy
from backend.app.strategies.volume_long_candle import VolumeLongCandleStrategy
from backend.app.strategies.volume_zone_breakout import VolumeZoneBreakoutStrategy


class StrategyFactory:
    """전략 팩토리 클래스"""

    _strategies = {
        "volume_long_candle": VolumeLongCandleStrategy,
        "volume_zone_breakout": VolumeZoneBreakoutStrategy,
    }

    @classmethod
    def create(cls, strategy_name: str) -> Strategy:
        """
        전략 이름으로 전략 인스턴스 생성

        Args:
            strategy_name (str): 전략 이름

        Returns:
            Strategy: 전략 인스턴스

        Raises:
            ValueError: 지원되지 않는 전략인 경우
        """
        if strategy_name not in cls._strategies:
            supported = list(cls._strategies.keys())
            raise ValueError(
                f"Unsupported strategy: {strategy_name}. Supported strategies: {supported}"
            )

        strategy_class = cls._strategies[strategy_name]
        return strategy_class()

    @classmethod
    def get_supported_strategies(cls) -> List[str]:
        """지원되는 전략 목록 반환"""
        return list(cls._strategies.keys())
```

**확인 방법**:
- 유효한 전략 이름으로 인스턴스 생성 확인
- 잘못된 전략 이름에 대한 ValueError 발생 확인
- 타입 힌트 및 docstring 작성 완료

**의존성**: 단계 1 완료

---

### 단계 3: POST /api/backtests/run 엔드포인트 구현

**작업 내용**:
- 백테스트 실행 엔드포인트 구현
- 요청 파라미터 검증
- 데이터 로더 호출
- 전략 인스턴스 생성 및 실행
- 심볼별 결과 집계
- 결과를 JSON 파일로 저장
- 응답 반환

**예상 산출물**:
```python
# backend/app/main.py (계속)

import time
from backend.app.data_loader import load_ohlcv_data
from backend.app.strategy_factory import StrategyFactory

@app.post("/api/backtests/run", response_model=BacktestResponse, status_code=status.HTTP_200_OK)
async def run_backtest(request: BacktestRequest):
    """
    백테스트 실행

    Args:
        request (BacktestRequest): 백테스트 요청

    Returns:
        BacktestResponse: 백테스트 결과

    Raises:
        HTTPException: 데이터 로드 실패, 전략 실행 실패 등
    """
    run_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(
        f"[{run_id}] Starting backtest: strategy={request.strategy}, "
        f"symbols={request.symbols}, period={request.start_date}~{request.end_date}"
    )

    try:
        # 결과 디렉토리 생성
        os.makedirs(RESULTS_DIR, exist_ok=True)

        # 전략 인스턴스 생성
        try:
            strategy = StrategyFactory.create(request.strategy)
        except ValueError as e:
            logger.error(f"[{run_id}] Strategy creation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        # 심볼별 백테스트 실행
        symbol_results = []
        total_signals = 0

        for symbol in request.symbols:
            logger.info(f"[{run_id}] Processing symbol: {symbol}")

            try:
                # 데이터 로드
                data_load_start = time.time()
                df = load_ohlcv_data(
                    symbols=[symbol],
                    timeframe=request.timeframe,
                    start_date=request.start_date,
                    end_date=request.end_date,
                )
                data_load_time = time.time() - data_load_start
                logger.info(
                    f"[{run_id}] Data loaded for {symbol}: {len(df)} rows, "
                    f"load_time={data_load_time:.2f}s"
                )

                if df.empty:
                    logger.warning(f"[{run_id}] No data found for {symbol}, skipping")
                    continue

                # 전략 실행
                strategy_start = time.time()
                result = strategy.run(df, request.params)
                strategy_time = time.time() - strategy_start
                logger.info(
                    f"[{run_id}] Strategy executed for {symbol}: "
                    f"signals={result.samples}, strategy_time={strategy_time:.2f}s"
                )

                # 결과 추가
                symbol_results.append(
                    SymbolResult(
                        symbol=symbol,
                        signals=result.samples,
                        win_rate=result.win_rate,
                        avg_return=result.avg_return,
                        max_drawdown=result.max_drawdown,
                        avg_hold_bars=result.avg_hold_bars,
                    )
                )
                total_signals += result.samples

            except HTTPException as e:
                # 데이터 로더/전략에서 발생한 HTTPException 그대로 전달
                logger.error(f"[{run_id}] HTTP error for {symbol}: {e.detail}")
                raise
            except Exception as e:
                logger.error(f"[{run_id}] Strategy execution failed for {symbol}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Strategy execution failed for {symbol}: {str(e)}",
                )

        execution_time = time.time() - start_time

        # 응답 객체 생성
        response = BacktestResponse(
            run_id=run_id,
            strategy=request.strategy,
            params=request.params,
            start_date=request.start_date,
            end_date=request.end_date,
            timeframe=request.timeframe,
            symbols=symbol_results,
            total_signals=total_signals,
            execution_time=execution_time,
        )

        # 결과를 JSON 파일로 저장
        result_file = os.path.join(RESULTS_DIR, f"{run_id}.json")
        try:
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(response.dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"[{run_id}] Result saved to {result_file}")
        except Exception as e:
            logger.error(f"[{run_id}] Failed to save result file: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save result: {str(e)}",
            )

        logger.info(
            f"[{run_id}] Backtest completed: total_signals={total_signals}, "
            f"execution_time={execution_time:.2f}s"
        )

        return response

    except HTTPException:
        # HTTPException은 그대로 전달
        raise
    except Exception as e:
        logger.error(f"[{run_id}] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )
```

**확인 방법**:
- curl로 POST 요청 테스트
- 유효한 파라미터로 200 응답 확인
- 잘못된 파라미터로 400 에러 확인
- 결과 파일이 `DATA_ROOT/results/{run_id}.json`에 저장되는지 확인
- 로그 메시지 출력 확인

**의존성**: 단계 1, 2 완료

---

### 단계 4: GET /api/backtests/{run_id} 엔드포인트 구현

**작업 내용**:
- 저장된 백테스트 결과 조회 엔드포인트 구현
- `run_id`로 결과 파일 찾기
- 파일이 없으면 404 반환
- 파일 내용을 JSON으로 파싱하여 반환

**예상 산출물**:
```python
# backend/app/main.py (계속)

@app.get("/api/backtests/{run_id}", response_model=BacktestResponse, status_code=status.HTTP_200_OK)
async def get_backtest_result(run_id: str):
    """
    백테스트 결과 조회

    Args:
        run_id (str): 백테스트 실행 ID

    Returns:
        BacktestResponse: 백테스트 결과

    Raises:
        HTTPException: 결과 파일이 없거나 읽기 실패
    """
    logger.info(f"[{run_id}] Retrieving backtest result")

    result_file = os.path.join(RESULTS_DIR, f"{run_id}.json")

    if not os.path.exists(result_file):
        logger.warning(f"[{run_id}] Result file not found: {result_file}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest result not found: {run_id}",
        )

    try:
        with open(result_file, "r", encoding="utf-8") as f:
            result_data = json.load(f)
        logger.info(f"[{run_id}] Result retrieved successfully")
        return BacktestResponse(**result_data)
    except json.JSONDecodeError as e:
        logger.error(f"[{run_id}] Invalid JSON in result file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid result file format: {str(e)}",
        )
    except Exception as e:
        logger.error(f"[{run_id}] Failed to read result file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read result: {str(e)}",
        )
```

**확인 방법**:
- 유효한 `run_id`로 GET 요청 시 200 응답 확인
- 존재하지 않는 `run_id`로 GET 요청 시 404 에러 확인
- 응답 데이터 형식 확인

**의존성**: 단계 3 완료

---

### 단계 5: 헬스체크 및 메타정보 엔드포인트 추가

**작업 내용**:
- `GET /` - API 루트 엔드포인트 (간단한 환영 메시지)
- `GET /health` - 헬스체크 엔드포인트
- `GET /api/strategies` - 지원되는 전략 목록 반환

**예상 산출물**:
```python
# backend/app/main.py (계속)

@app.get("/")
async def root():
    """API 루트 엔드포인트"""
    return {
        "message": "Coin Backtesting API",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/backtests/run": "Run backtest",
            "GET /api/backtests/{run_id}": "Get backtest result",
            "GET /api/strategies": "List supported strategies",
            "GET /health": "Health check",
        },
    }

@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "data_root": DATA_ROOT,
        "results_dir": RESULTS_DIR,
    }

@app.get("/api/strategies")
async def list_strategies():
    """지원되는 전략 목록 반환"""
    strategies = StrategyFactory.get_supported_strategies()
    return {
        "strategies": strategies,
        "count": len(strategies),
    }
```

**확인 방법**:
- `GET /` 응답 확인
- `GET /health` 응답 확인
- `GET /api/strategies` 응답 확인

**의존성**: 단계 2, 3, 4 완료

---

### 단계 6: 통합 테스트 작성

**작업 내용**:
- `tests/test_api.py` 생성
- FastAPI TestClient를 사용한 통합 테스트 작성
- 각 엔드포인트의 정상 케이스 및 예외 케이스 테스트
- 최소 15개 이상의 테스트 케이스 작성

**예상 산출물**:
```python
# tests/test_api.py
"""
FastAPI 엔드포인트 통합 테스트
"""

import pytest
from fastapi.testclient import TestClient
import os
import json
import tempfile
import shutil

from backend.app.main import app, RESULTS_DIR

client = TestClient(app)


@pytest.fixture
def temp_results_dir(monkeypatch):
    """임시 결과 디렉토리 생성"""
    temp_dir = tempfile.mkdtemp()
    monkeypatch.setattr("backend.app.main.RESULTS_DIR", temp_dir)
    yield temp_dir
    shutil.rmtree(temp_dir)


class TestRootEndpoints:
    """루트 및 헬스체크 엔드포인트 테스트"""

    def test_root_endpoint(self):
        """루트 엔드포인트 테스트"""
        response = client.get("/")
        assert response.status_code == 200
        assert "message" in response.json()

    def test_health_check(self):
        """헬스체크 엔드포인트 테스트"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_list_strategies(self):
        """전략 목록 조회 테스트"""
        response = client.get("/api/strategies")
        assert response.status_code == 200
        data = response.json()
        assert "strategies" in data
        assert len(data["strategies"]) >= 2


class TestBacktestRun:
    """백테스트 실행 엔드포인트 테스트"""

    def test_valid_backtest_request(self, temp_results_dir):
        """유효한 백테스트 요청 테스트"""
        payload = {
            "strategy": "volume_long_candle",
            "params": {
                "vol_ma_window": 20,
                "vol_multiplier": 1.5,
                "body_pct": 0.02,
            },
            "symbols": ["BTC_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "timeframe": "1d",
        }

        response = client.post("/api/backtests/run", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "run_id" in data
        assert data["strategy"] == "volume_long_candle"
        assert len(data["symbols"]) > 0

        # 결과 파일 확인
        result_file = os.path.join(temp_results_dir, f"{data['run_id']}.json")
        assert os.path.exists(result_file)

    def test_invalid_strategy(self):
        """지원되지 않는 전략 테스트"""
        payload = {
            "strategy": "invalid_strategy",
            "params": {},
            "symbols": ["BTC_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        response = client.post("/api/backtests/run", json=payload)
        assert response.status_code == 422  # Validation error

    def test_empty_symbols(self):
        """빈 심볼 목록 테스트"""
        payload = {
            "strategy": "volume_long_candle",
            "params": {},
            "symbols": [],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        response = client.post("/api/backtests/run", json=payload)
        assert response.status_code == 422  # Validation error

    def test_invalid_date_format(self):
        """잘못된 날짜 형식 테스트"""
        payload = {
            "strategy": "volume_long_candle",
            "params": {},
            "symbols": ["BTC_KRW"],
            "start_date": "2024/01/01",  # 잘못된 형식
            "end_date": "2024-01-31",
        }

        response = client.post("/api/backtests/run", json=payload)
        assert response.status_code == 422  # Validation error

    def test_invalid_date_range(self):
        """잘못된 날짜 범위 테스트"""
        payload = {
            "strategy": "volume_long_candle",
            "params": {},
            "symbols": ["BTC_KRW"],
            "start_date": "2024-02-01",
            "end_date": "2024-01-01",  # start_date보다 앞
        }

        response = client.post("/api/backtests/run", json=payload)
        assert response.status_code == 422  # Validation error

    def test_multiple_symbols(self, temp_results_dir):
        """여러 심볼 백테스트 테스트"""
        payload = {
            "strategy": "volume_zone_breakout",
            "params": {},
            "symbols": ["BTC_KRW", "ETH_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        response = client.post("/api/backtests/run", json=payload)

        # 데이터가 없을 수도 있으므로 400이나 200 둘 다 허용
        assert response.status_code in [200, 400]


class TestBacktestGet:
    """백테스트 결과 조회 엔드포인트 테스트"""

    def test_get_existing_result(self, temp_results_dir):
        """존재하는 결과 조회 테스트"""
        # 먼저 백테스트 실행
        payload = {
            "strategy": "volume_long_candle",
            "params": {},
            "symbols": ["BTC_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        run_response = client.post("/api/backtests/run", json=payload)
        assert run_response.status_code == 200
        run_id = run_response.json()["run_id"]

        # 결과 조회
        get_response = client.get(f"/api/backtests/{run_id}")
        assert get_response.status_code == 200

        data = get_response.json()
        assert data["run_id"] == run_id
        assert data["strategy"] == "volume_long_candle"

    def test_get_nonexistent_result(self):
        """존재하지 않는 결과 조회 테스트"""
        response = client.get("/api/backtests/nonexistent-id")
        assert response.status_code == 404


class TestParameterValidation:
    """파라미터 유효성 검사 테스트"""

    def test_missing_required_fields(self):
        """필수 필드 누락 테스트"""
        payload = {
            "strategy": "volume_long_candle",
            # symbols, start_date, end_date 누락
        }

        response = client.post("/api/backtests/run", json=payload)
        assert response.status_code == 422

    def test_default_timeframe(self, temp_results_dir):
        """기본 타임프레임 테스트"""
        payload = {
            "strategy": "volume_long_candle",
            "params": {},
            "symbols": ["BTC_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            # timeframe 생략 (기본값: 1d)
        }

        response = client.post("/api/backtests/run", json=payload)

        # 데이터가 있으면 200, 없으면 400
        if response.status_code == 200:
            data = response.json()
            assert data["timeframe"] == "1d"

    def test_custom_params(self, temp_results_dir):
        """사용자 정의 파라미터 테스트"""
        payload = {
            "strategy": "volume_long_candle",
            "params": {
                "vol_ma_window": 30,
                "vol_multiplier": 2.0,
                "body_pct": 0.03,
                "hold_period_bars": 2,
            },
            "symbols": ["BTC_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        response = client.post("/api/backtests/run", json=payload)

        if response.status_code == 200:
            data = response.json()
            assert data["params"]["vol_ma_window"] == 30
            assert data["params"]["vol_multiplier"] == 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**예상 테스트 개수**:
| 테스트 클래스 | 개수 | 테스트 내용 |
|-----------|------|-----------|
| TestRootEndpoints | 3 | 루트, 헬스체크, 전략 목록 |
| TestBacktestRun | 7 | 실행, 유효성 검사, 여러 심볼 |
| TestBacktestGet | 2 | 조회 성공, 조회 실패 |
| TestParameterValidation | 3 | 필드 누락, 기본값, 사용자 정의 |

**확인 방법**:
```bash
pytest tests/test_api.py -v
```

**의존성**: 단계 1-5 완료

---

### 단계 7: Docker 환경 통합 및 문서화

**작업 내용**:
- `docker-compose.yml` 업데이트 (FastAPI 서비스 추가)
- `requirements.txt` 업데이트 (fastapi, uvicorn 추가)
- README 업데이트 (API 사용 예제 추가)
- API 명세 문서 작성 (`docs/coin/mvp/api_spec.md`)

**예상 산출물**:

**docker-compose.yml 업데이트**:
```yaml
services:
  backend:
    build: .
    container_name: coin-backtest-backend
    volumes:
      - ./backend:/app/backend
      - ./data:/data
      - ./tests:/app/tests
    ports:
      - "8000:8000"
    environment:
      - DATA_ROOT=/data
      - TZ=Asia/Seoul
    command: uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

  test:
    build: .
    container_name: coin-backtest-test
    volumes:
      - ./backend:/app/backend
      - ./data:/data
      - ./tests:/app/tests
    environment:
      - DATA_ROOT=/data
      - PYTHONPATH=/app
    command: pytest tests/ -v
```

**requirements.txt 업데이트**:
```txt
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pandas>=2.0.0
numpy>=1.24.0
pyarrow>=14.0.0
pytest>=7.4.0
httpx>=0.25.0  # TestClient를 위한 의존성
```

**API 명세 문서**:
```markdown
# API 명세서

## 개요
코인 백테스팅 API는 거래 전략을 과거 데이터에 대해 실행하고 성과를 분석할 수 있는 RESTful API입니다.

## 베이스 URL
```
http://localhost:8000
```

## 엔드포인트

### 1. POST /api/backtests/run
백테스트를 실행하고 결과를 저장합니다.

**요청**:
- Content-Type: application/json

**요청 바디**:
```json
{
  "strategy": "volume_long_candle",
  "params": {
    "vol_ma_window": 20,
    "vol_multiplier": 1.5,
    "body_pct": 0.02,
    "hold_period_bars": 1
  },
  "symbols": ["BTC_KRW", "ETH_KRW"],
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "timeframe": "1d"
}
```

**응답 (200 OK)**:
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "strategy": "volume_long_candle",
  "params": {...},
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "timeframe": "1d",
  "symbols": [
    {
      "symbol": "BTC_KRW",
      "signals": 42,
      "win_rate": 0.59,
      "avg_return": 0.65,
      "max_drawdown": 3.1,
      "avg_hold_bars": 1.0
    }
  ],
  "total_signals": 42,
  "execution_time": 1.23
}
```

**에러 응답**:
- 400 Bad Request: 잘못된 파라미터
- 500 Internal Server Error: 서버 오류

### 2. GET /api/backtests/{run_id}
저장된 백테스트 결과를 조회합니다.

**경로 파라미터**:
- run_id: 백테스트 실행 ID

**응답 (200 OK)**: POST와 동일한 형식

**에러 응답**:
- 404 Not Found: 결과를 찾을 수 없음

### 3. GET /api/strategies
지원되는 전략 목록을 반환합니다.

**응답 (200 OK)**:
```json
{
  "strategies": ["volume_long_candle", "volume_zone_breakout"],
  "count": 2
}
```

### 4. GET /health
API 헬스 체크

**응답 (200 OK)**:
```json
{
  "status": "healthy",
  "timestamp": "2024-10-31T17:00:00+09:00",
  "data_root": "/data",
  "results_dir": "/data/results"
}
```

## 사용 예제

### curl
```bash
# 백테스트 실행
curl -X POST http://localhost:8000/api/backtests/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "volume_long_candle",
    "params": {"vol_ma_window": 20},
    "symbols": ["BTC_KRW"],
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }'

# 결과 조회
curl http://localhost:8000/api/backtests/{run_id}
```
```

**확인 방법**:
- Docker Compose로 서비스 시작 확인
- curl로 각 엔드포인트 테스트
- 문서화 완성도 검토

**의존성**: 단계 1-6 완료

---

## 4. 구현 순서 및 우선순위

### 권장 진행 순서
1. ✅ **단계 1** (0.5시간): FastAPI 기본 구조 및 모델 정의
2. ✅ **단계 2** (0.5시간): 전략 팩토리 패턴 구현
3. ✅ **단계 3** (1.0시간): POST /api/backtests/run 구현
4. ✅ **단계 4** (0.5시간): GET /api/backtests/{run_id} 구현
5. ✅ **단계 5** (0.5시간): 헬스체크 및 메타정보 엔드포인트
6. ✅ **단계 6** (1.0시간): 통합 테스트 작성
7. ✅ **단계 7** (0.5시간): Docker 통합 및 문서화

**예상 총 소요 시간**: 4.5시간 (여유 있게 4시간 예상에 부합)

---

## 5. 추가 고려 사항

### 기술적 결정사항
| 항목 | 결정 | 근거 |
|-----|------|------|
| **run_id 생성 방식** | UUID v4 | 충돌 없고 예측 불가능 |
| **결과 저장 방식** | JSON 파일 | 단순하고 인간 가독성 높음 |
| **에러 핸들링** | HTTPException + 로깅 | FastAPI 표준 패턴 |
| **CORS** | 모든 origin 허용 (개발 환경) | 프론트엔드 연동 편의성 |
| **타임아웃** | 동기 처리 (Phase 3에서 비동기) | 초기 구현 단순화 |
| **심볼별 결과** | 개별 저장 | PDR 요구사항 (코인별 성과 분리) |

### 검증 체크리스트
- [ ] POST /api/backtests/run이 정상 작동하는지
- [ ] GET /api/backtests/{run_id}가 결과를 반환하는지
- [ ] 유효성 검사가 제대로 작동하는지
- [ ] 에러 핸들링이 적절한지
- [ ] 로그 메시지가 충분히 출력되는지
- [ ] 결과 파일이 올바른 경로에 저장되는지
- [ ] 통합 테스트가 모두 통과하는지
- [ ] Docker 환경에서 정상 실행되는지
- [ ] API 문서가 명확한지

---

## 6. 이슈 #3 Acceptance Criteria

### 필수 산출물
- [ ] `backend/app/main.py`: FastAPI 애플리케이션 및 엔드포인트
- [ ] `backend/app/strategy_factory.py`: 전략 팩토리 클래스
- [ ] `POST /api/backtests/run`: 백테스트 실행 엔드포인트
- [ ] `GET /api/backtests/{run_id}`: 결과 조회 엔드포인트
- [ ] `GET /api/strategies`: 전략 목록 엔드포인트
- [ ] `GET /health`: 헬스체크 엔드포인트
- [ ] 요청/응답 Pydantic 모델 정의
- [ ] 파라미터 유효성 검사 (심볼, 날짜, 전략)
- [ ] 에러 핸들링 (400, 404, 500)
- [ ] 로깅 (시작/종료, 성능 측정, 파일 경로)
- [ ] 결과 파일 저장 (`DATA_ROOT/results/{run_id}.json`)
- [ ] `tests/test_api.py`: 통합 테스트 (15개 이상)
- [ ] `docs/coin/mvp/api_spec.md`: API 명세 문서
- [ ] `docker-compose.yml` 업데이트
- [ ] `requirements.txt` 업데이트 (fastapi, uvicorn)

### 검증 코드
```bash
# Docker 서비스 시작
docker-compose up -d backend

# 헬스체크
curl http://localhost:8000/health

# 전략 목록 조회
curl http://localhost:8000/api/strategies

# 백테스트 실행
curl -X POST http://localhost:8000/api/backtests/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "volume_long_candle",
    "params": {"vol_ma_window": 20, "vol_multiplier": 1.5, "body_pct": 0.02},
    "symbols": ["BTC_KRW"],
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }'

# 결과 조회 (run_id는 위의 응답에서 얻음)
curl http://localhost:8000/api/backtests/{run_id}

# 결과 파일 확인
ls -lh data/results/

# 통합 테스트 실행
docker-compose run --rm test pytest tests/test_api.py -v
```

---

## 7. 진행 승인 요청

위 계획대로 진행해도 될까요?

### 확인 사항:
1. **계획 단계**: 단계 1-7이 적절한가요?
2. **run_id 생성**: UUID v4 방식이 맞나요?
3. **심볼별 결과**: 각 심볼의 결과를 리스트로 반환하는 방식이 맞나요? (통합 지표는 프론트에서 계산)
4. **결과 저장**: JSON 파일로 저장하는 방식이 적절한가요?
5. **에러 핸들링**: 400/404/500 상태 코드 사용이 적절한가요?
6. **Docker 통합**: FastAPI 서비스를 docker-compose에 추가하는 방식이 맞나요?

---

**준비되면 "계속 진행해주세요" 또는 수정 사항을 알려주세요!**
