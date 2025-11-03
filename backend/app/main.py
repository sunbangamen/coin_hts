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
    """백테스트 요청 모델

    Phase 2 최적화 적용 (2025-11-03)
    - volume_zone_breakout: 기본 윈도우 60 → 10, 버퍼 0.01 → 0.0으로 최적화
    - 출처: docs/coin/mvp/phase2_strategy_optimization.md
    """

    strategy: str = Field(
        ..., description="전략 이름 (volume_long_candle, volume_zone_breakout)"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="""전략 파라미터 (기본값 자동 적용)

        volume_long_candle:
          - vol_ma_window: int (기본값: 10, 범위: 1-200)
          - vol_multiplier: float (기본값: 1.0, 범위: 1.0-10.0)
          - body_pct: float (기본값: 0.01, 범위: 0.0-1.0)

        volume_zone_breakout (Phase 2 최적화됨):
          - volume_window: int (기본값: 10, 범위: 1-200, 이전: 60)
          - top_percentile: float (기본값: 0.2, 범위: 0.0-1.0)
          - breakout_buffer: float (기본값: 0.0, 범위: 0.0-1.0, 이전: 0.01)
        """
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
    timeframe: str = Field(default="1d", description="타임프레임 (기본값: 1d, 옵션: 1d, 1h, 5m)")

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


class APISignal(BaseModel):
    """
    API 응답용 거래 신호 모델 (Step 4 신호 테이블용)

    각 개별 거래 신호의 상세 정보를 포함합니다.
    """

    symbol: str = Field(..., description="거래 심볼 (예: BTC_KRW)")
    type: str = Field(..., description="신호 타입: 'buy' 또는 'sell'")
    timestamp: str = Field(..., description="신호 발생 시간 (ISO 8601, UTC)")
    entry_price: float = Field(..., description="진입 가격 (KRW)")
    exit_price: float = Field(..., description="청산 가격 (KRW)")
    return_pct: float = Field(..., description="거래 수익률 (소수점, 예: 0.05 = 5%)")


class PerformancePoint(BaseModel):
    """성과곡선 포인트 (Phase 3 차트용)

    시간대별 누적 수익률 데이터
    """

    timestamp: str = Field(
        ...,
        description="데이터 포인트 날짜 (YYYY-MM-DD)"
    )
    equity: float = Field(
        ...,
        description="누적 수익률 (소수점, 예: 1.05 = 5% 수익)"
    )
    drawdown: Optional[float] = Field(
        default=None,
        description="해당 시점의 낙폭 (선택사항)"
    )


class SymbolResult(BaseModel):
    """심볼별 백테스트 결과"""

    symbol: str
    signals: List[APISignal] = Field(
        default_factory=list,
        description="개별 거래 신호 목록 (Step 4 신호 테이블용)"
    )
    win_rate: float
    avg_return: float
    max_drawdown: float
    avg_hold_bars: float
    performance_curve: Optional[List[PerformancePoint]] = Field(
        default=None,
        description="성과곡선 데이터 (Phase 3 차트용, Equity Curve 라인 차트)"
    )


class MetadataInfo(BaseModel):
    """메타데이터 정보 (Phase 2 확장)

    백테스트 실행 환경 및 시점 정보를 포함합니다.
    """

    execution_date: str = Field(
        ...,
        description="백테스트 실행 날짜/시간 (ISO 8601 형식, UTC)"
    )
    environment: str = Field(
        default="development",
        description="실행 환경 (development, staging, production)"
    )
    execution_host: str = Field(
        default="local",
        description="실행 호스트 정보 (Docker 컨테이너 ID 또는 호스트명)"
    )


class BacktestResponse(BaseModel):
    """백테스트 응답 모델 (Phase 2 메타데이터 확장)

    JSON 스키마 버전: 1.1.0
    - Phase 1: 9/9 필드 검증 완료
    - Phase 2: version, metadata, description 필드 추가

    하위 호환성: version 필드로 스키마 버전 관리
    """

    version: str = Field(
        default="1.1.0",
        description="API 응답 스키마 버전 (semantic versioning, 예: 1.1.0)"
    )
    run_id: str = Field(..., description="백테스트 실행 ID (UUID)")
    strategy: str = Field(..., description="사용된 전략명")
    params: Dict[str, Any] = Field(..., description="실제 적용된 전략 파라미터")
    start_date: str = Field(..., description="백테스트 시작 날짜 (YYYY-MM-DD)")
    end_date: str = Field(..., description="백테스트 종료 날짜 (YYYY-MM-DD)")
    timeframe: str = Field(..., description="사용된 타임프레임")
    symbols: List[SymbolResult] = Field(..., description="심볼별 백테스트 결과")
    total_signals: int = Field(..., description="총 신호 개수")
    execution_time: float = Field(..., description="백테스트 실행 시간 (초)")
    metadata: Optional[MetadataInfo] = Field(
        default=None,
        description="메타데이터: 실행 환경, 시점 정보 (Phase 2에서 추가됨, 향후 필수화 예정)"
    )
    description: Optional[str] = Field(
        default=None,
        description="백테스트 결과 설명 (선택사항, 예: 테스트 목적, 특이사항 등)"
    )


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
    백테스트 실행 (Phase 2 최적화 적용)

    주요 기능:
    - 여러 심볼에 대한 동시 백테스트 실행
    - 전략별 신호 생성 및 성과 분석
    - 실시간 검증 및 에러 처리

    Phase 2 최적화:
    - volume_zone_breakout 기본 파라미터 최적화 완료
      * volume_window: 60 → 10 (신호 생성: 0개 → 최대 29개)
      * breakout_buffer: 0.01 → 0.0
    - 파라미터 튜닝 분석: 100개 조합 테스트, 80% 신호 생성 성공
    - 참고: docs/coin/mvp/phase2_strategy_optimization.md

    Args:
        request (BacktestRequest): 백테스트 요청
            - strategy: volume_long_candle 또는 volume_zone_breakout
            - params: 전략별 파라미터 (기본값 자동 적용)
            - symbols: 심볼 목록
            - start_date, end_date: 분석 기간
            - timeframe: 봉 주기 (1d, 1h, 5m)

    Returns:
        BacktestResponse: 백테스트 결과
            - run_id: 실행 고유 ID
            - 심볼별 신호 및 성과 지표
            - 실행 시간

    Raises:
        HTTPException: 데이터 로드 실패, 전략 실행 실패, 파라미터 검증 실패 등
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

                # 내부 Signal을 API용 APISignal로 변환 (Step 4 신호 테이블용)
                api_signals: List[APISignal] = []
                if result.signals and result.entry_exit_pairs and result.returns:
                    for i, signal in enumerate(result.signals):
                        if i < len(result.entry_exit_pairs) and i < len(result.returns):
                            entry_price, exit_price = result.entry_exit_pairs[i]
                            return_pct = result.returns[i] / 100.0  # % 형식에서 소수점 형식으로 변환

                            api_signals.append(
                                APISignal(
                                    symbol=symbol,
                                    type=signal.side.lower(),  # BUY -> buy, SELL -> sell
                                    timestamp=signal.timestamp.isoformat(),  # ISO 8601 형식
                                    entry_price=entry_price,
                                    exit_price=exit_price,
                                    return_pct=return_pct,
                                )
                            )

                # Equity Curve (성과곡선) 계산 (Phase 3 차트용)
                performance_curve = None
                if result.signals and result.returns:
                    performance_curve = []
                    cumulative_equity = 1.0

                    for i, signal in enumerate(result.signals):
                        if i < len(result.returns):
                            # 반환률을 소수점 형식으로 변환 (% to decimal)
                            return_pct = result.returns[i] / 100.0
                            cumulative_equity *= (1.0 + return_pct)

                            performance_curve.append(
                                PerformancePoint(
                                    timestamp=signal.timestamp.strftime('%Y-%m-%d'),
                                    equity=cumulative_equity
                                )
                            )

                # 결과 추가
                symbol_results.append(
                    SymbolResult(
                        symbol=symbol,
                        signals=api_signals,
                        win_rate=result.win_rate,
                        avg_return=result.avg_return,
                        max_drawdown=result.max_drawdown,
                        avg_hold_bars=result.avg_hold_bars,
                        performance_curve=performance_curve,
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

        # 메타데이터 수집 (Phase 2 확장)
        environment = os.getenv("ENVIRONMENT", "development")
        execution_host = os.getenv("HOSTNAME", "local")

        metadata = MetadataInfo(
            execution_date=datetime.utcnow().isoformat() + "Z",  # ISO 8601 UTC 형식
            environment=environment,
            execution_host=execution_host,
        )

        # 응답 객체 생성
        response = BacktestResponse(
            version="1.1.0",
            run_id=run_id,
            strategy=request.strategy,
            params=request.params,
            start_date=request.start_date,
            end_date=request.end_date,
            timeframe=request.timeframe,
            symbols=symbol_results,
            total_signals=total_signals,
            execution_time=execution_time,
            metadata=metadata,
            description=None,  # 선택적 필드
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
