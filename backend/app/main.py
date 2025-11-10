"""
Coin Backtesting API

거래 전략을 과거 데이터에 대해 실행하고 성과를 분석할 수 있는 RESTful API입니다.
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
from backend.app.task_manager import TaskManager, TaskStatus
from backend.app.result_manager import ResultManager
from backend.app.strategy_preset_manager import StrategyPresetManager
# from backend.app.jobs import run_backtest_job  # Removed: not used in new architecture
from rq import Queue
from backend.app.config import redis_conn
from backend.app.simulation.simulation_orchestrator import get_orchestrator, close_orchestrator
from backend.app.simulation.position_manager import get_position_manager
from backend.app.market_data.market_data_service import get_market_data_service
from backend.app.routers import data as data_router
from backend.app.routers import monitoring as monitoring_router
from backend.app.scheduler import (
    start_scheduler,
    stop_scheduler,
    schedule_daily_collection,
    get_scheduler_status,
    trigger_immediate_batch
)

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

# 라우터 등록
app.include_router(data_router.router)
app.include_router(monitoring_router.router)

# 환경변수
DATA_ROOT = os.getenv("DATA_ROOT", "/data")
RESULTS_DIR = os.path.join(DATA_ROOT, "results")
ENABLE_SCHEDULER = os.getenv('ENABLE_SCHEDULER', 'true').lower() == 'true'

# RQ 큐 초기화
rq_queue = Queue(connection=redis_conn)

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


class AsyncBacktestResponse(BaseModel):
    """비동기 백테스트 응답 모델"""

    task_id: str = Field(..., description="작업 ID (UUID)")
    status: str = Field(..., description="작업 상태 (queued, running, completed, failed, cancelled)")
    created_at: str = Field(..., description="작업 생성 시간 (ISO 8601)")


class TaskStatusResponse(BaseModel):
    """작업 상태 조회 응답 모델"""

    task_id: str = Field(..., description="작업 ID")
    status: str = Field(..., description="작업 상태 (queued, running, completed, failed, cancelled)")
    progress: float = Field(..., description="진행률 (0.0 ~ 1.0)")
    result: Optional[Dict[str, Any]] = Field(default=None, description="백테스트 결과 (완료 시)")
    error: Optional[str] = Field(default=None, description="에러 메시지 (실패 또는 취소 시)")


# ============================================================================
# 실시간 시뮬레이션 관련 Pydantic 모델 (Phase 2)
# ============================================================================

class StrategyConfig(BaseModel):
    """전략 설정 모델 (실시간 시뮬레이션용)"""
    strategy_name: str = Field(..., description="전략 이름 (예: 'volume_zone_breakout')")
    params: Dict[str, Any] = Field(default_factory=dict, description="전략 파라미터")


class SimulationStartRequest(BaseModel):
    """실시간 시뮬레이션 시작 요청"""
    symbols: List[str] = Field(..., min_items=1, description="모니터링할 심볼 목록 (예: ['KRW-BTC', 'KRW-ETH'])")
    strategies: Dict[str, List[StrategyConfig]] = Field(
        ...,
        description="""각 심볼의 전략 설정
        예: {
            'KRW-BTC': [
                {'strategy_name': 'volume_zone_breakout', 'params': {'volume_window': 10}},
                {'strategy_name': 'volume_long_candle', 'params': {'vol_ma_window': 10}}
            ]
        }"""
    )


class SimulationStatusResponse(BaseModel):
    """시뮬레이션 상태 응답"""
    session_id: Optional[str] = Field(None, description="세션 ID")
    is_running: bool = Field(..., description="실행 여부")
    market_data_status: Optional[Dict[str, Any]] = Field(None, description="마켓 데이터 서비스 상태")
    strategy_runner_status: Optional[Dict[str, Any]] = Field(None, description="전략 실행 엔진 상태")
    websocket_clients: int = Field(..., description="연결된 WebSocket 클라이언트 수")


class SimulationStrategyResponse(BaseModel):
    """등록된 전략 정보"""
    symbol: str = Field(..., description="심볼")
    strategy_name: str = Field(..., description="전략 이름")
    params: Dict[str, Any] = Field(..., description="전략 파라미터")
    is_initialized: bool = Field(..., description="초기화 여부")


class SimulationStrategiesResponse(BaseModel):
    """시뮬레이션 등록 전략 목록 응답"""
    session_id: Optional[str] = Field(None, description="세션 ID")
    strategies: List[SimulationStrategyResponse] = Field(default_factory=list, description="전략 목록")
    count: int = Field(..., description="전략 개수")


# ============================================================================
# 포지션 관리 관련 Pydantic 모델 (Phase 3)
# ============================================================================

class PositionResponse(BaseModel):
    """오픈 포지션 정보"""
    position_id: int = Field(..., description="포지션 ID")
    symbol: str = Field(..., description="거래 심볼")
    strategy_name: str = Field(..., description="전략 이름")
    entry_time: str = Field(..., description="진입 시간 (ISO 8601)")
    entry_price: float = Field(..., description="진입 가격")
    quantity: float = Field(..., description="포지션 수량")
    current_price: float = Field(..., description="현재 가격")
    unrealized_pnl: float = Field(..., description="미실현 손익")
    unrealized_pnl_pct: float = Field(..., description="미실현 손익률 (%)")
    fee_amount: float = Field(..., description="수수료")


class PositionListResponse(BaseModel):
    """포지션 목록 응답"""
    session_id: Optional[str] = Field(None, description="세션 ID")
    positions: List[PositionResponse] = Field(default_factory=list, description="포지션 목록")
    count: int = Field(..., description="포지션 개수")
    total_unrealized_pnl: float = Field(..., description="총 미실현 손익")


class TradeResponse(BaseModel):
    """거래(클로즈된 포지션) 정보"""
    id: int = Field(..., description="거래 ID")
    symbol: str = Field(..., description="거래 심볼")
    strategy_name: str = Field(..., description="전략 이름")
    entry_time: str = Field(..., description="진입 시간 (ISO 8601)")
    entry_price: float = Field(..., description="진입 가격")
    exit_time: str = Field(..., description="청산 시간 (ISO 8601)")
    exit_price: float = Field(..., description="청산 가격")
    quantity: float = Field(..., description="수량")
    realized_pnl: float = Field(..., description="실현 손익")
    realized_pnl_pct: float = Field(..., description="실현 손익률 (%)")
    fee_amount: float = Field(..., description="수수료")
    slippage_amount: float = Field(..., description="슬리피지 금액")
    hold_duration: Optional[str] = Field(None, description="보유 기간")


class TradeHistoryResponse(BaseModel):
    """거래 이력 응답"""
    session_id: Optional[str] = Field(None, description="세션 ID")
    trades: List[TradeResponse] = Field(default_factory=list, description="거래 목록")
    count: int = Field(..., description="거래 개수")
    total_realized_pnl: float = Field(..., description="총 실현 손익")
    win_count: int = Field(..., description="수익 거래 개수")
    lose_count: int = Field(..., description="손실 거래 개수")
    win_rate: float = Field(..., description="승률 (0.0 ~ 1.0, 예: 0.65 = 65%)")


class CandleResponse(BaseModel):
    """캔들(시장 데이터) 정보"""
    symbol: str = Field(..., description="심볼")
    timeframe: str = Field(..., description="타임프레임")
    timestamp: str = Field(..., description="타임스탬프 (ISO 8601)")
    open: float = Field(..., description="시가")
    high: float = Field(..., description="고가")
    low: float = Field(..., description="저가")
    close: float = Field(..., description="종가")
    volume: float = Field(..., description="거래량")


class MarketDataResponse(BaseModel):
    """시장 데이터 응답"""
    session_id: Optional[str] = Field(None, description="세션 ID")
    candles: List[CandleResponse] = Field(default_factory=list, description="캔들 데이터 목록")
    count: int = Field(..., description="캔들 개수")


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
            "POST /api/backtests/run": "Run backtest (synchronous)",
            "POST /api/backtests/run-async": "Run backtest (asynchronous, returns task_id)",
            "GET /api/backtests/{run_id}": "Get backtest result",
            "GET /api/backtests/latest": "Get latest backtest result (Phase 2)",
            "GET /api/backtests/history": "Get backtest history with pagination (Phase 2)",
            "GET /api/backtests/{run_id}/download": "Download backtest result as JSON (Phase 2)",
            "GET /api/backtests/status/{task_id}": "Get async task status",
            "GET /api/strategies": "List supported strategies",
            "GET /health": "Health check",
            "POST /api/simulation/start": "Start real-time simulation (Phase 2)",
            "POST /api/simulation/stop": "Stop real-time simulation (Phase 2)",
            "GET /api/simulation/status": "Get simulation status (Phase 2)",
            "GET /api/simulation/strategies": "Get registered simulation strategies (Phase 2)",
            "GET /api/simulation/market-data": "Get market data (candles) (Phase 4)",
            "GET /api/simulation/positions": "Get current open positions (Phase 3)",
            "GET /api/simulation/history": "Get closed trades history (Phase 3)",
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


@app.get("/api/health")
async def api_health_check():
    """API 헬스체크 엔드포인트"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


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

        # 결과를 JSON 파일로 저장 및 인덱스 업데이트
        try:
            if not ResultManager.save_result(DATA_ROOT, run_id, response.dict()):
                logger.error(f"[{run_id}] Failed to save result via ResultManager")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to save result",
                )
            logger.info(f"[{run_id}] Result saved and indexed")
        except HTTPException:
            raise
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
    "/api/backtests/latest",
    response_model=BacktestResponse,
    status_code=status.HTTP_200_OK,
)
async def get_latest_backtest():
    """
    최신 백테스트 결과 조회 (Phase 2)

    가장 최근에 실행된 백테스트 결과를 반환합니다.

    Returns:
        BacktestResponse: 최신 백테스트 결과

    Raises:
        HTTPException: 결과를 찾을 수 없음 (404)
    """
    try:
        latest_run_id = ResultManager.get_latest_run_id(DATA_ROOT)

        if not latest_run_id:
            logger.warning("No backtest results found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No backtest results found",
            )

        logger.info(f"Retrieving latest backtest: {latest_run_id}")

        result_data = ResultManager.get_result(DATA_ROOT, latest_run_id)
        if not result_data:
            logger.warning(f"Latest result not found: {latest_run_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Latest backtest result not found",
            )

        logger.info(f"Latest result retrieved: {latest_run_id}")
        return BacktestResponse(**result_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving latest backtest: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve latest backtest: {str(e)}",
        )


class BacktestHistoryItem(BaseModel):
    """백테스트 히스토리 항목 (Phase 2)"""
    run_id: str = Field(..., description="실행 ID")
    strategy: str = Field(..., description="전략명")
    symbols: List[str] = Field(..., description="심볼 목록")
    start_date: str = Field(..., description="시작 날짜")
    end_date: str = Field(..., description="종료 날짜")
    timeframe: str = Field(..., description="타임프레임")
    total_signals: int = Field(..., description="총 신호 개수")
    execution_time: float = Field(..., description="실행 시간 (초)")
    timestamp: str = Field(..., description="실행 시간 (ISO 8601, UTC)")


class BacktestHistoryResponse(BaseModel):
    """백테스트 히스토리 응답 (Phase 2)"""
    total: int = Field(..., description="전체 항목 수")
    limit: int = Field(..., description="페이지 크기")
    offset: int = Field(..., description="시작 위치")
    items: List[BacktestHistoryItem] = Field(..., description="히스토리 항목 배열")


class StrategyPreset(BaseModel):
    """전략 프리셋 (Phase 3)"""
    name: str = Field(..., description="프리셋 이름", min_length=1, max_length=100)
    strategy: str = Field(..., description="전략명")
    params: Dict[str, Any] = Field(..., description="전략 파라미터")
    description: str = Field("", description="프리셋 설명")


class StrategyPresetResponse(BaseModel):
    """전략 프리셋 응답 (Phase 3)"""
    name: str = Field(..., description="프리셋 이름")
    strategy: str = Field(..., description="전략명")
    params: Dict[str, Any] = Field(..., description="전략 파라미터")
    description: str = Field(..., description="프리셋 설명")
    created_at: str = Field(..., description="생성 시간 (ISO 8601, UTC)")
    updated_at: str = Field(..., description="업데이트 시간 (ISO 8601, UTC)")


@app.get(
    "/api/backtests/history",
    response_model=BacktestHistoryResponse,
    status_code=status.HTTP_200_OK,
)
async def get_backtest_history(
    limit: int = 10,
    offset: int = 0,
    strategy: Optional[str] = None,
    min_return: Optional[float] = None,
    max_return: Optional[float] = None,
    min_signals: Optional[int] = None,
    max_signals: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """
    백테스트 히스토리 조회 (Phase 2 + Task 3.3-3 고급 필터링)

    페이지네이션 및 고급 필터링을 지원하는 백테스트 히스토리 목록을 반환합니다.

    Args:
        limit: 조회 개수 (기본: 10, 최대: 100)
        offset: 시작 위치 (기본: 0)
        strategy: 전략명 필터 (선택사항)
        min_return: 최소 평균 수익률 (%, 선택사항)
        max_return: 최대 평균 수익률 (%, 선택사항)
        min_signals: 최소 신호 개수 (선택사항)
        max_signals: 최대 신호 개수 (선택사항)
        date_from: 시작 날짜 필터 (YYYY-MM-DD, 선택사항)
        date_to: 종료 날짜 필터 (YYYY-MM-DD, 선택사항)

    Returns:
        BacktestHistoryResponse: 히스토리 목록 및 메타데이터 (필터 적용됨)

    Raises:
        HTTPException: 쿼리 매개변수 오류 또는 필터 범위 오류
    """
    try:
        # 제한값 설정
        limit = min(max(limit, 1), 100)  # 1 ~ 100
        offset = max(offset, 0)

        # 필터 범위 검증
        if min_return is not None and max_return is not None:
            if min_return > max_return:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="min_return cannot be greater than max_return",
                )

        if min_signals is not None and max_signals is not None:
            if min_signals > max_signals:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="min_signals cannot be greater than max_signals",
                )

        if date_from is not None and date_to is not None:
            if date_from > date_to:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="date_from cannot be greater than date_to",
                )

        logger.info(
            f"Retrieving backtest history with filters: "
            f"limit={limit}, offset={offset}, strategy={strategy}, "
            f"min_return={min_return}, max_return={max_return}, "
            f"min_signals={min_signals}, max_signals={max_signals}, "
            f"date_from={date_from}, date_to={date_to}"
        )

        history = ResultManager.get_history(
            data_root=DATA_ROOT,
            limit=limit,
            offset=offset,
            strategy=strategy,
            min_return=min_return,
            max_return=max_return,
            min_signals=min_signals,
            max_signals=max_signals,
            date_from=date_from,
            date_to=date_to,
        )

        # Pydantic 모델로 변환
        items = [BacktestHistoryItem(**item) for item in history["items"]]

        logger.info(f"History retrieved: total={history['total']}, items={len(items)}")

        return BacktestHistoryResponse(
            total=history["total"],
            limit=history["limit"],
            offset=history["offset"],
            items=items,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving backtest history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve backtest history: {str(e)}",
        )


@app.get(
    "/api/backtests/{run_id}/download",
    status_code=status.HTTP_200_OK,
)
async def download_backtest_result(run_id: str):
    """
    백테스트 결과 파일 다운로드 (Phase 2)

    JSON 형식의 결과 파일을 다운로드합니다.

    Args:
        run_id: 실행 ID

    Returns:
        FileResponse: 결과 JSON 파일

    Raises:
        HTTPException: 파일을 찾을 수 없음 (404)
    """
    try:
        result_file = os.path.join(RESULTS_DIR, f"{run_id}.json")

        if not os.path.exists(result_file):
            logger.warning(f"Download file not found: {run_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest result not found: {run_id}",
            )

        logger.info(f"Downloading backtest result: {run_id}")

        return FileResponse(
            path=result_file,
            filename=f"backtest_{run_id}.json",
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="backtest_{run_id}.json"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading backtest result {run_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download backtest result: {str(e)}",
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


# ============================================================================
# 비동기 API 엔드포인트 (Phase 3 - 운영 안정성)
# ============================================================================

@app.post(
    "/api/backtests/run-async",
    response_model=AsyncBacktestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_backtest_async(request: BacktestRequest):
    """
    비동기 백테스트 실행 (Phase 3 비동기 큐 구현)

    장시간 실행되는 백테스트를 비동기로 처리합니다.
    요청이 수락되면 즉시 task_id를 반환하고,
    백그라운드에서 백테스트가 실행됩니다.

    Args:
        request (BacktestRequest): 백테스트 요청

    Returns:
        AsyncBacktestResponse: task_id와 상태 정보
            - task_id: 작업 ID (UUID)
            - status: 작업 상태 (queued)
            - created_at: 작업 생성 시간
    """
    try:
        # 작업 생성
        task_id = TaskManager.create_task(
            strategy=request.strategy,
            params=request.params,
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            timeframe=request.timeframe,
        )

        logger.info(f"[{task_id}] Async backtest task created")

        # RQ 큐에 작업 추가 (Phase 3 구현 완료)
        try:
            from backend.app.jobs import run_backtest_job
            job = rq_queue.enqueue(
                run_backtest_job,
                task_id=task_id,
                strategy=request.strategy,
                params=request.params,
                symbols=request.symbols,
                start_date=request.start_date,
                end_date=request.end_date,
                timeframe=request.timeframe,
                job_id=task_id,  # 작업 ID를 task_id로 설정
                timeout=3600,  # 1시간 타임아웃
            )
            logger.info(f"[{task_id}] Job enqueued to RQ: {job.id}")
        except Exception as e:
            logger.error(f"[{task_id}] Failed to enqueue job: {e}")
            TaskManager.set_error(task_id, f"Failed to enqueue job: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to enqueue backtest job: {str(e)}",
            )

        # 응답
        task = TaskManager.get_task(task_id)
        return AsyncBacktestResponse(
            task_id=task_id,
            status=task.get("status", TaskStatus.QUEUED.value),
            created_at=task.get("created_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in async backtest: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )


@app.delete(
    "/api/backtests/tasks/{task_id}",
    response_model=AsyncBacktestResponse,
    status_code=status.HTTP_200_OK,
)
async def cancel_backtest_task(task_id: str):
    """
    진행 중인 백테스트 작업 취소 (Phase 3 비동기 큐 구현)

    제출되었거나 실행 중인 백테스트 작업을 취소합니다.
    이미 완료되거나 실패한 작업은 취소할 수 없습니다.

    Args:
        task_id (str): 작업 ID (UUID)

    Returns:
        AsyncBacktestResponse: 취소된 작업 정보
            - task_id: 작업 ID
            - status: cancelled
            - created_at: 작업 생성 시간

    Raises:
        HTTPException: 작업을 찾을 수 없거나 이미 완료됨
    """
    try:
        # 작업 정보 조회
        task_status = TaskManager.get_status(task_id)

        if not task_status:
            logger.warning(f"Task not found for cancellation: {task_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}",
            )

        current_status = task_status.get("status")

        # 이미 완료되거나 실패한 작업은 취소 불가
        if current_status in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value]:
            logger.warning(f"Cannot cancel {current_status} task: {task_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel {current_status} task. Only queued or running tasks can be cancelled.",
            )

        # RQ 큐에서 작업 취소 시도
        try:
            job = rq_queue.fetch_job(task_id)
            if job:
                job.cancel()
                logger.info(f"[{task_id}] RQ job cancelled")
        except Exception as e:
            logger.warning(f"[{task_id}] Failed to cancel RQ job: {e}")
            # job이 없거나 이미 시작된 경우도 있으므로 계속 진행

        # TaskManager에서 작업 상태를 cancelled로 업데이트
        TaskManager.cancel_task(task_id, "Task cancelled by user")

        logger.info(f"[{task_id}] Async backtest task cancelled")

        # 취소 확인 응답
        return AsyncBacktestResponse(
            task_id=task_id,
            status="cancelled",
            created_at=task_status.get("created_at", datetime.utcnow().isoformat() + "Z"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{task_id}] Error cancelling task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelling task: {str(e)}",
        )


@app.get(
    "/api/backtests/status/{task_id}",
    response_model=TaskStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_task_status(task_id: str):
    """
    비동기 작업 상태 조회 (Phase 3 비동기 큐 구현)

    진행 중인 백테스트 작업의 상태, 진행률, 결과를 조회합니다.

    Args:
        task_id (str): 작업 ID (UUID)

    Returns:
        TaskStatusResponse: 작업 상태 정보
            - status: queued, running, completed, failed
            - progress: 진행률 (0.0 ~ 1.0)
            - result: 완료 시 백테스트 결과
            - error: 실패 시 에러 메시지

    Raises:
        HTTPException: 작업을 찾을 수 없음
    """
    try:
        task_status = TaskManager.get_status(task_id)

        if not task_status:
            logger.warning(f"Task not found: {task_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}",
            )

        logger.info(f"[{task_id}] Status retrieved: {task_status['status']}")

        return TaskStatusResponse(**task_status)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{task_id}] Error retrieving task status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving task status: {str(e)}",
        )


# ============================================================================
# 실시간 시뮬레이션 API 엔드포인트 (Phase 2)
# ============================================================================

@app.post(
    "/api/simulation/start",
    response_model=SimulationStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def start_simulation(request: SimulationStartRequest):
    """
    실시간 시뮬레이션 시작

    마켓 데이터를 수신하여 등록된 전략들을 실시간으로 실행하고,
    발생한 신호를 WebSocket을 통해 브로드캐스트합니다.

    Args:
        request (SimulationStartRequest):
            - symbols: 모니터링할 심볼 목록
            - strategies: 심볼별 전략 설정

    Returns:
        SimulationStatusResponse: 시뮬레이션 상태 정보 (session_id 포함)

    Raises:
        HTTPException: 시뮬레이션 시작 실패
    """
    try:
        orchestrator = get_orchestrator()

        # 이미 실행 중인 경우 에러
        if orchestrator.is_running:
            logger.warning("Simulation already running")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Simulation is already running",
            )

        # 전략 설정 변환 (Pydantic 모델 → dict)
        strategies_dict = {}
        for symbol, strategy_configs in request.strategies.items():
            strategies_dict[symbol] = [
                {
                    'strategy_name': config.strategy_name,
                    'params': config.params,
                }
                for config in strategy_configs
            ]

        logger.info(
            f"Starting simulation: symbols={request.symbols}, "
            f"strategy_count={sum(len(v) for v in strategies_dict.values())}"
        )

        # 시뮬레이션을 스레드 풀에서 실행하여 이벤트 루프 블로킹 방지
        import asyncio
        asyncio.create_task(asyncio.to_thread(
            lambda: asyncio.run(orchestrator.start_simulation(
                symbols=request.symbols,
                strategies=strategies_dict,
                redis_client=redis_conn,
            ))
        ))

        logger.info(f"Simulation startup scheduled in background thread")

        # 즉시 상태 반환 (세션 ID는 임시)
        return SimulationStatusResponse(
            session_id="initializing",
            is_running=True,
            websocket_clients=0,
            active_positions=0,
            total_realized_pnl=0.0,
            total_unrealized_pnl=0.0,
            closed_trades_count=0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start simulation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start simulation: {str(e)}",
        )


@app.post(
    "/api/simulation/stop",
    response_model=SimulationStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def stop_simulation():
    """
    실시간 시뮬레이션 중지

    모든 서비스를 정리하고 세션을 종료합니다.

    Returns:
        SimulationStatusResponse: 시뮬레이션 상태 정보 (is_running=False)

    Raises:
        HTTPException: 시뮬레이션 중지 실패
    """
    try:
        orchestrator = get_orchestrator()

        # 실행 중이지 않은 경우 에러
        if not orchestrator or not orchestrator.is_running:
            logger.warning("No simulation running")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No simulation is currently running",
            )

        logger.info(f"Stopping simulation: session_id={orchestrator.session_id}")

        # 비동기로 중지 (event loop 양보)
        import asyncio
        asyncio.create_task(orchestrator.stop_simulation())

        logger.info("Simulation stop requested")

        # 즉시 상태 반환
        return orchestrator.get_simulation_status()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop simulation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop simulation: {str(e)}",
        )


@app.get(
    "/api/simulation/status",
    response_model=SimulationStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_simulation_status():
    """
    실시간 시뮬레이션 상태 조회

    현재 시뮬레이션의 실행 상태, 등록된 전략, WebSocket 클라이언트 정보를 반환합니다.

    Returns:
        SimulationStatusResponse: 시뮬레이션 상태 정보

    Raises:
        HTTPException: 상태 조회 실패
    """
    try:
        orchestrator = get_orchestrator()
        status_info = orchestrator.get_simulation_status()

        logger.debug(f"Simulation status retrieved: is_running={status_info['is_running']}")

        return SimulationStatusResponse(**status_info)

    except Exception as e:
        logger.error(f"Failed to get simulation status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get simulation status: {str(e)}",
        )


@app.get(
    "/api/simulation/strategies",
    response_model=SimulationStrategiesResponse,
    status_code=status.HTTP_200_OK,
)
async def get_simulation_strategies():
    """
    등록된 시뮬레이션 전략 목록 조회

    현재 시뮬레이션에 등록된 모든 전략의 목록과 설정을 반환합니다.

    Returns:
        SimulationStrategiesResponse: 전략 목록 및 메타데이터

    Raises:
        HTTPException: 전략 목록 조회 실패
    """
    try:
        orchestrator = get_orchestrator()
        strategy_runner = orchestrator.strategy_runner

        if not strategy_runner:
            logger.warning("Strategy runner not initialized")
            return SimulationStrategiesResponse(
                session_id=orchestrator.session_id,
                strategies=[],
                count=0,
            )

        strategies = strategy_runner.get_strategies()

        # Pydantic 모델로 변환
        strategy_responses = [
            SimulationStrategyResponse(**strategy)
            for strategy in strategies
        ]

        logger.info(f"Strategies retrieved: count={len(strategies)}")

        return SimulationStrategiesResponse(
            session_id=orchestrator.session_id,
            strategies=strategy_responses,
            count=len(strategies),
        )

    except Exception as e:
        logger.error(f"Failed to get simulation strategies: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get simulation strategies: {str(e)}",
        )


@app.get(
    "/api/simulation/market-data",
    response_model=MarketDataResponse,
    status_code=status.HTTP_200_OK,
)
async def get_market_data(symbol: Optional[str] = None, limit: int = 10):
    """
    시장 데이터(캔들) 조회

    현재 수집 중인 시장 데이터(캔들)를 조회합니다.
    시뮬레이션이 실행 중이 아니면 빈 리스트를 반환합니다.

    Args:
        symbol: 심볼 필터 (선택사항, 예: 'KRW-BTC')
        limit: 조회할 캔들 개수 (기본: 10, 최대: 200)

    Returns:
        MarketDataResponse: 캔들 데이터 목록

    Note:
        - 응답이 비어 있으면 시뮬레이션이 아직 데이터를 수집하지 못했거나 실행 중이 아닙니다.
        - 데이터가 있으면 최근 캔들부터 역순으로 정렬됩니다.
    """
    try:
        # Immediately return empty response if service not ready
        # This prevents event loop blocking when simulation is initializing
        market_data_service = get_market_data_service()

        if not market_data_service or not market_data_service.is_running:
            # 시뮬레이션이 실행 중이 아니면 빈 리스트 반환
            return MarketDataResponse(
                session_id=None,
                candles=[],
                count=0,
            )

        # 현재 캔들 조회 (심볼별 진행 중인 캔들)
        candles = []
        symbols_to_query = market_data_service.symbols if not symbol else [symbol]

        for sym in symbols_to_query:
            current_candle = market_data_service.get_current_candle(sym)
            if current_candle:
                # 캔들 데이터를 응답 모델로 변환
                candle_response = CandleResponse(
                    symbol=sym,
                    timeframe=market_data_service.timeframe,
                    timestamp=current_candle.get('timestamp', '').isoformat()
                        if isinstance(current_candle.get('timestamp'), datetime)
                        else str(current_candle.get('timestamp', '')),
                    open=float(current_candle.get('open', 0)),
                    high=float(current_candle.get('high', 0)),
                    low=float(current_candle.get('low', 0)),
                    close=float(current_candle.get('close', 0)),
                    volume=float(current_candle.get('volume', 0)),
                )
                candles.append(candle_response)

        logger.info(f"Market data retrieved: count={len(candles)}, symbols={len(symbols_to_query)}")

        position_manager = get_position_manager()
        session_id = position_manager.session_id if position_manager else None

        return MarketDataResponse(
            session_id=session_id,
            candles=candles,
            count=len(candles),
        )

    except Exception as e:
        logger.error(f"Failed to get market data: {e}", exc_info=True)
        # 예외 발생 시에도 빈 응답으로 graceful handling
        return MarketDataResponse(
            session_id=None,
            candles=[],
            count=0,
        )


@app.get(
    "/api/simulation/positions",
    response_model=PositionListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_positions(symbol: Optional[str] = None):
    """
    현재 오픈 포지션 조회

    현재 시뮬레이션에 오픈되어 있는 모든 포지션을 조회합니다.

    Args:
        symbol: 심볼 필터 (선택사항, 예: 'KRW-BTC')

    Returns:
        PositionListResponse: 포지션 목록 및 통계

    Raises:
        HTTPException: 포지션 조회 실패
    """
    try:
        position_manager = get_position_manager()

        # Return empty positions if manager not ready
        if not position_manager:
            return PositionListResponse(
                session_id=None,
                positions=[],
                count=0,
                total_unrealized_pnl=0.0,
            )

        # Run DB call in thread pool to avoid blocking event loop
        import asyncio
        positions = await asyncio.to_thread(
            position_manager.get_open_positions,
            symbol
        )

        # 총 미실현 손익 계산
        total_unrealized_pnl = sum(
            p['unrealized_pnl'] for p in positions
        )

        # Pydantic 모델로 변환
        position_responses = [
            PositionResponse(**position)
            for position in positions
        ]

        logger.info(f"Positions retrieved: count={len(positions)}")

        return PositionListResponse(
            session_id=position_manager.session_id,
            positions=position_responses,
            count=len(positions),
            total_unrealized_pnl=round(total_unrealized_pnl, 2),
        )

    except Exception as e:
        logger.error(f"Failed to get positions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get positions: {str(e)}",
        )


@app.get(
    "/api/simulation/history",
    response_model=TradeHistoryResponse,
    status_code=status.HTTP_200_OK,
)
async def get_trade_history(
    symbol: Optional[str] = None,
    strategy_name: Optional[str] = None,
    limit: int = 100,
):
    """
    거래 이력 조회

    클로즈된 포지션(완료된 거래)의 이력을 조회합니다.

    Args:
        symbol: 심볼 필터 (선택사항)
        strategy_name: 전략명 필터 (선택사항)
        limit: 조회 개수 제한 (기본: 100, 최대: 1000)

    Returns:
        TradeHistoryResponse: 거래 이력 목록 및 통계

    Raises:
        HTTPException: 거래 이력 조회 실패
    """
    try:
        # limit 최대값 제한
        limit = min(limit, 1000)

        position_manager = get_position_manager()

        # Return empty history if manager not ready
        if not position_manager:
            return TradeHistoryResponse(
                session_id=None,
                trades=[],
                count=0,
                total_realized_pnl=0.0,
                win_rate=0.0,
                win_count=0,
                lose_count=0,
            )

        # Run DB call in thread pool to avoid blocking event loop
        import asyncio
        trades = await asyncio.to_thread(
            position_manager.get_closed_trades,
            symbol,
            strategy_name,
            limit,
        )

        # 통계 계산
        total_realized_pnl = sum(
            t.get('realized_pnl', 0) for t in trades
        )
        win_count = sum(
            1 for t in trades if t.get('realized_pnl', 0) > 0
        )
        lose_count = sum(
            1 for t in trades if t.get('realized_pnl', 0) < 0
        )
        # 승률 계산 (0.0 ~ 1.0)
        win_rate = (win_count / len(trades)) if trades else 0.0

        # Pydantic 모델로 변환
        trade_responses = [
            TradeResponse(**trade)
            for trade in trades
        ]

        logger.info(
            f"Trade history retrieved: count={len(trades)}, "
            f"total_pnl={total_realized_pnl:.2f}, win_rate={win_rate:.2%}, "
            f"wins={win_count}, losses={lose_count}"
        )

        return TradeHistoryResponse(
            session_id=position_manager.session_id,
            trades=trade_responses,
            count=len(trades),
            total_realized_pnl=round(total_realized_pnl, 2),
            win_count=win_count,
            lose_count=lose_count,
            win_rate=round(win_rate, 4),
        )

    except Exception as e:
        logger.error(f"Failed to get trade history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trade history: {str(e)}",
        )


# ============================================================================
# 스케줄러 초기화 (자동 데이터 수집)
# ============================================================================

@app.on_event("startup")
async def startup_scheduler():
    """애플리케이션 시작 시 스케줄러 초기화 (환경 변수 기반)"""
    # Step 1: ENABLE_SCHEDULER 환경 플래그 확인
    if not ENABLE_SCHEDULER:
        logger.warning("⚠️  ENABLE_SCHEDULER=false, 스케줄러를 시작하지 않습니다")
        logger.info("💡 수동 트리거 사용 가능: POST /api/scheduler/trigger")
        return

    try:
        logger.info("🚀 스케줄러 시작 중...")

        # Step 3: 스케줄러 시작 (try/except 분리)
        if not start_scheduler():
            logger.error("❌ 스케줄러 시작 실패")
            return

        # Step 2: 환경 변수 기반 기본값으로 스케줄 설정
        # 인자를 전달하지 않으면 scheduler.py의 DEFAULT_SYMBOLS, SCHEDULER_HOUR 등 사용
        schedule_daily_collection(
            days=1,
            overwrite=False
        )

        logger.info("✅ 스케줄러 준비 완료")
    except Exception as e:
        logger.error(f"❌ 스케줄러 초기화 실패: {e}")
        # 스케줄러 실패해도 앱은 계속 실행


@app.on_event("shutdown")
async def shutdown_scheduler():
    """애플리케이션 종료 시 스케줄러 중지"""
    try:
        logger.info("⛔ 스케줄러 종료 중...")
        stop_scheduler()
        logger.info("✅ 스케줄러 종료 완료")
    except Exception as e:
        logger.error(f"❌ 스케줄러 종료 중 오류: {e}")


@app.get("/api/scheduler/status")
async def get_scheduler_status_endpoint():
    """스케줄러 상태 조회 (상세 정보)

    응답:
        - enabled: 스케줄러 활성화 여부
        - running: 현재 실행 중 여부
        - redis: Redis 연결 상태
        - scheduled_jobs: 등록된 스케줄 작업
        - last_run: 최근 실행 결과
        - job_history: 최근 5개 작업 기록
        - rq_queue: 대기 중인 작업 큐 상태
        - configuration: 현재 설정 (시간, 심볼, 타임프레임)
    """
    return get_scheduler_status()


@app.post("/api/scheduler/trigger")
async def trigger_scheduler_endpoint(
    symbols: list = None,
    timeframes: list = None,
    days: int = 1,
    overwrite: bool = False
):
    """즉시 데이터 수집 배치 작업 실행 (테스트/운영 점검용)

    Parameters:
        symbols: 수집할 심볼 리스트 (기본: DEFAULT_SYMBOLS)
        timeframes: 수집할 타임프레임 리스트 (기본: DEFAULT_TIMEFRAMES)
        days: 수집 기간 (기본: 1)
        overwrite: 기존 파일 덮어쓰기 여부 (기본: False)

    응답:
        - success: 작업 추가 성공 여부
        - job_id: RQ 작업 ID
        - error: 오류 메시지 (실패 시)

    예제:
        curl -X POST http://localhost:8000/api/scheduler/trigger \\
            -H "Content-Type: application/json" \\
            -d '{"symbols": ["KRW-BTC"], "timeframes": ["1H"], "days": 1}'
    """
    result = trigger_immediate_batch(
        symbols=symbols,
        timeframes=timeframes,
        days=days,
        overwrite=overwrite
    )

    if result['success']:
        return {
            'success': True,
            'job_id': result['job_id'],
            'message': f"배치 작업이 큐에 추가되었습니다: {result['job_id']}"
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result['error']
        )


# ============================================================================
# 전략 프리셋 관리 API (Phase 3)
# ============================================================================

@app.get(
    "/api/strategies/presets",
    response_model=List[StrategyPresetResponse],
    status_code=status.HTTP_200_OK,
)
async def list_strategy_presets():
    """
    모든 전략 프리셋 조회 (Phase 3)

    Returns:
        List[StrategyPresetResponse]: 프리셋 목록 (생성일 역순)

    예제:
        curl http://localhost:8000/api/strategies/presets
    """
    try:
        presets = StrategyPresetManager.get_all_presets(DATA_ROOT)
        logger.info(f"Retrieved {len(presets)} strategy presets")
        return [StrategyPresetResponse(**p) for p in presets]
    except Exception as e:
        logger.error(f"Error listing strategy presets: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list presets: {str(e)}",
        )


@app.get(
    "/api/strategies/presets/{name}",
    response_model=StrategyPresetResponse,
    status_code=status.HTTP_200_OK,
)
async def get_strategy_preset(name: str):
    """
    특정 전략 프리셋 조회 (Phase 3)

    Args:
        name (str): 프리셋 이름

    Returns:
        StrategyPresetResponse: 프리셋 상세 정보

    Raises:
        HTTPException: 프리셋을 찾을 수 없음

    예제:
        curl http://localhost:8000/api/strategies/presets/conservative
    """
    try:
        preset = StrategyPresetManager.get_preset(DATA_ROOT, name)
        if not preset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strategy preset '{name}' not found",
            )
        logger.info(f"Retrieved strategy preset: {name}")
        return StrategyPresetResponse(**preset)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting strategy preset '{name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get preset: {str(e)}",
        )


@app.post(
    "/api/strategies/presets",
    response_model=StrategyPresetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_strategy_preset(request: StrategyPreset):
    """
    새 전략 프리셋 생성 (Phase 3)

    Args:
        request (StrategyPreset): 프리셋 정보

    Returns:
        StrategyPresetResponse: 생성된 프리셋

    Raises:
        HTTPException: 유효하지 않은 입력

    예제:
        curl -X POST http://localhost:8000/api/strategies/presets \\
            -H "Content-Type: application/json" \\
            -d '{
              "name": "conservative",
              "strategy": "volume_long_candle",
              "params": {"vol_ma_window": 20, "vol_multiplier": 1.5, "body_pct": 0.01},
              "description": "보수적 전략 프리셋"
            }'
    """
    try:
        preset = StrategyPresetManager.save_preset(
            data_root=DATA_ROOT,
            name=request.name,
            strategy=request.strategy,
            params=request.params,
            description=request.description,
        )
        logger.info(f"Created strategy preset: {request.name}")
        return StrategyPresetResponse(**preset)
    except ValueError as e:
        logger.warning(f"Invalid preset data: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error creating strategy preset: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create preset: {str(e)}",
        )


@app.put(
    "/api/strategies/presets/{name}",
    response_model=StrategyPresetResponse,
    status_code=status.HTTP_200_OK,
)
async def update_strategy_preset(name: str, request: StrategyPreset):
    """
    전략 프리셋 업데이트 (Phase 3)

    Args:
        name (str): 프리셋 이름
        request (StrategyPreset): 업데이트할 정보

    Returns:
        StrategyPresetResponse: 업데이트된 프리셋

    Raises:
        HTTPException: 프리셋을 찾을 수 없음

    예제:
        curl -X PUT http://localhost:8000/api/strategies/presets/conservative \\
            -H "Content-Type: application/json" \\
            -d '{
              "name": "conservative",
              "strategy": "volume_long_candle",
              "params": {"vol_ma_window": 25, "vol_multiplier": 1.8, "body_pct": 0.02},
              "description": "업데이트된 보수적 전략"
            }'
    """
    try:
        preset = StrategyPresetManager.update_preset(
            data_root=DATA_ROOT,
            name=name,
            strategy=request.strategy,
            params=request.params,
            description=request.description,
        )
        logger.info(f"Updated strategy preset: {name}")
        return StrategyPresetResponse(**preset)
    except ValueError as e:
        logger.warning(f"Preset not found or invalid data: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error updating strategy preset '{name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update preset: {str(e)}",
        )


@app.delete(
    "/api/strategies/presets/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_strategy_preset(name: str):
    """
    전략 프리셋 삭제 (Phase 3)

    Args:
        name (str): 프리셋 이름

    Raises:
        HTTPException: 프리셋을 찾을 수 없음

    예제:
        curl -X DELETE http://localhost:8000/api/strategies/presets/conservative
    """
    try:
        StrategyPresetManager.delete_preset(DATA_ROOT, name)
        logger.info(f"Deleted strategy preset: {name}")
        return None
    except ValueError as e:
        logger.warning(f"Preset not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error deleting strategy preset '{name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete preset: {str(e)}",
        )
