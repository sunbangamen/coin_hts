"""
Coin Backtesting API

거래 전략을 과거 데이터에 대해 실행하고 성과를 분석할 수 있는 RESTful API입니다.
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any
from datetime import datetime
import os
import logging
import json
import uuid
import time

from backend.app.data_loader import load_ohlcv_data
from backend.app.strategy_factory import StrategyFactory

# FastAPI 애플리케이션 생성
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


# ============================================================================
# 요청/응답 Pydantic 모델
# ============================================================================

class BacktestRequest(BaseModel):
    """백테스트 요청 모델"""

    strategy: str = Field(
        ..., description="전략 이름 (volume_long_candle, volume_zone_breakout)"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict, description="전략 파라미터"
    )
    symbols: List[str] = Field(
        ..., min_items=1, description="심볼 목록 (예: ['BTC_KRW', 'ETH_KRW'])"
    )
    start_date: str = Field(
        ..., description="시작 날짜 (YYYY-MM-DD 형식, KST 기준)"
    )
    end_date: str = Field(
        ..., description="종료 날짜 (YYYY-MM-DD 형식, KST 기준)"
    )
    timeframe: str = Field(default="1d", description="타임프레임 (기본값: 1d)")

    @validator("start_date", "end_date")
    def validate_date_format(cls, v):
        """날짜 형식 검증 (YYYY-MM-DD)"""
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(
                f"Invalid date format: {v}. Expected YYYY-MM-DD"
            )

    @validator("end_date")
    def validate_date_range(cls, v, values):
        """start_date <= end_date 검증"""
        if "start_date" in values:
            start = datetime.strptime(values["start_date"], "%Y-%m-%d")
            end = datetime.strptime(v, "%Y-%m-%d")
            if start > end:
                raise ValueError(
                    "start_date must be before or equal to end_date"
                )
        return v

    @validator("strategy")
    def validate_strategy(cls, v):
        """지원되는 전략인지 검증"""
        supported = StrategyFactory.get_supported_strategies()
        if v not in supported:
            raise ValueError(
                f"Unsupported strategy: {v}. Supported: {supported}"
            )
        return v


class SymbolResult(BaseModel):
    """심볼별 백테스트 결과"""

    symbol: str
    signals: int
    win_rate: float
    avg_return: float
    max_drawdown: float
    avg_hold_bars: float


class BacktestResponse(BaseModel):
    """백테스트 응답 모델"""

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
    """에러 응답 모델"""

    error: str
    detail: str


# ============================================================================
# 엔드포인트
# ============================================================================

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


@app.post(
    "/api/backtests/run",
    response_model=BacktestResponse,
    status_code=status.HTTP_200_OK,
)
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
                    logger.warning(
                        f"[{run_id}] No data found for {symbol}, skipping"
                    )
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
                logger.error(
                    f"[{run_id}] Strategy execution failed for {symbol}: {e}"
                )
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


@app.get(
    "/api/backtests/{run_id}",
    response_model=BacktestResponse,
    status_code=status.HTTP_200_OK,
)
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
