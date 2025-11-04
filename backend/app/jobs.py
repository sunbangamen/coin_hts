"""비동기 백테스트 작업 함수들"""
import logging
import json
import os
from typing import Dict, Any, Callable, Optional
from datetime import datetime

from .data_loader import load_ohlcv_data
from .strategy_factory import StrategyFactory
from .task_manager import TaskManager, TaskStatus
from .result_manager import ResultManager

logger = logging.getLogger(__name__)


def create_progress_callback(task_id: str) -> Callable[[float, str], None]:
    """
    진행률 콜백 함수 생성

    Args:
        task_id: 작업 ID

    Returns:
        진행률 콜백 함수
    """
    def callback(progress: float, message: str = "") -> None:
        """
        진행률 업데이트 콜백

        Args:
            progress: 진행률 (0.0 ~ 1.0)
            message: 진행 상황 메시지 (선택사항)
        """
        TaskManager.set_progress(task_id, progress)
        if message:
            logger.info(f"[Task {task_id}] {message} (progress: {progress:.0%})")

    return callback


def run_backtest_job(
    task_id: str,
    strategy: str,
    params: Dict[str, Any],
    symbols: list,
    start_date: str,
    end_date: str,
    timeframe: str = "1d",
) -> Dict[str, Any]:
    """
    비동기 백테스트 작업

    Args:
        task_id: 작업 ID
        strategy: 전략명
        params: 전략 파라미터
        symbols: 심볼 목록
        start_date: 시작 날짜
        end_date: 종료 날짜
        timeframe: 타임프레임

    Returns:
        백테스트 결과 (BacktestResponse 호환)
    """
    data_root = os.getenv("DATA_ROOT", "/data")
    started_at = datetime.utcnow().isoformat() + "Z"

    try:
        logger.info(f"[Task {task_id}] Starting backtest: {strategy}")

        # 상태 업데이트: RUNNING
        TaskManager.update_status(task_id, TaskStatus.RUNNING)
        TaskManager.set_progress(task_id, 0.0)

        # 데이터 로드
        logger.info(f"[Task {task_id}] Loading data for {len(symbols)} symbols...")
        TaskManager.set_progress(task_id, 0.1)

        df = load_ohlcv_data(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )

        logger.info(f"[Task {task_id}] Data loaded: {len(df)} rows")

        # 전략 인스턴스 생성
        strategy_instance = StrategyFactory.create(strategy)
        TaskManager.set_progress(task_id, 0.2)

        # 심볼별 백테스트 실행
        symbols_result = []
        total_signals = 0
        progress_callback = create_progress_callback(task_id)

        for idx, symbol in enumerate(symbols):
            # 진행률 계산: 0.2 (데이터 로드) ~ 0.95 (완료 전)
            symbol_progress = 0.2 + (0.75 * idx / len(symbols))
            progress_callback(symbol_progress, f"Processing {symbol} ({idx + 1}/{len(symbols)})")

            logger.info(f"[Task {task_id}] Running backtest for {symbol}...")

            try:
                # 심볼별 데이터 필터링
                symbol_df = df[df["symbol"] == symbol].copy()

                if len(symbol_df) == 0:
                    logger.warning(f"[Task {task_id}] No data for {symbol}")
                    continue

                # 전략 실행
                result = strategy_instance.run(symbol_df, params)

                # API 응답 포맷 변환
                symbol_result = {
                    "symbol": symbol,
                    "signals": [
                        {
                            "symbol": symbol,
                            "type": "buy" if sig.side == "BUY" else "sell",
                            "timestamp": sig.timestamp.isoformat() + "Z",
                            "entry_price": float(sig.price),
                            "exit_price": None,
                            "return_pct": None,
                        }
                        for sig in result.signals
                    ],
                    "win_rate": float(result.win_rate),
                    "avg_return": float(result.avg_return),
                    "max_drawdown": float(result.max_drawdown),
                    "avg_hold_bars": float(result.avg_hold_bars),
                    "performance_curve": None,  # Step 4에서 추가
                }

                symbols_result.append(symbol_result)
                total_signals += len(result.signals)

                logger.info(
                    f"[Task {task_id}] {symbol} backtest completed: "
                    f"{len(result.signals)} signals, win_rate={result.win_rate:.2%}"
                )

            except Exception as e:
                logger.error(f"[Task {task_id}] Error in {symbol}: {str(e)}")
                TaskManager.set_error(task_id, f"Error processing {symbol}: {str(e)}")
                raise

        TaskManager.set_progress(task_id, 0.95)

        # 결과 조합
        finished_at = datetime.utcnow().isoformat() + "Z"
        result_data = {
            "version": "1.1.0",
            "run_id": task_id,
            "strategy": strategy,
            "params": params,
            "start_date": start_date,
            "end_date": end_date,
            "timeframe": timeframe,
            "symbols": symbols_result,
            "total_signals": total_signals,
            "execution_time": None,  # API에서 계산
            "metadata": {
                "execution_date": finished_at,
                "environment": os.getenv("ENVIRONMENT", "development"),
            },
        }

        # 결과 파일 저장 (${DATA_ROOT}/tasks/<task_id>/result.json)
        result_file = ResultManager.save_result_file(
            data_root=data_root,
            task_id=task_id,
            result_data=result_data,
            filename="result.json",
        )

        # Manifest 파일 저장 (${DATA_ROOT}/tasks/<task_id>/manifest.json)
        result_files = [
            {
                "name": "result.json",
                "path": "result.json",
                "size_bytes": os.path.getsize(result_file),
                "checksum": ResultManager.calculate_checksum(result_file),
            }
        ]

        manifest_file = ResultManager.save_manifest_file(
            data_root=data_root,
            task_id=task_id,
            strategy=strategy,
            params=params,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            result_files=result_files,
            started_at=started_at,
            finished_at=finished_at,
            total_signals=total_signals,
            symbols_processed=len(symbols_result),
            symbols_failed=len(symbols) - len(symbols_result),
            status="completed",
        )

        # Redis에 결과도 저장 (폴링 응답용)
        TaskManager.set_result(task_id, result_data)
        TaskManager.set_progress(task_id, 1.0)

        logger.info(
            f"[Task {task_id}] Backtest completed successfully. "
            f"Result: {result_file}, Manifest: {manifest_file}"
        )

        return result_data

    except Exception as e:
        error_msg = f"Backtest failed: {str(e)}"
        logger.error(f"[Task {task_id}] {error_msg}", exc_info=True)
        finished_at = datetime.utcnow().isoformat() + "Z"

        # manifest 파일에 에러 정보 저장
        try:
            manifest_file = ResultManager.save_manifest_file(
                data_root=data_root,
                task_id=task_id,
                strategy=strategy,
                params=params,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
                result_files=[],
                started_at=started_at,
                finished_at=finished_at,
                total_signals=0,
                symbols_processed=0,
                symbols_failed=len(symbols),
                status="failed",
                error_message=error_msg,
            )
            logger.info(f"[Task {task_id}] Error manifest saved: {manifest_file}")
        except Exception as manifest_error:
            logger.error(
                f"[Task {task_id}] Failed to save error manifest: {manifest_error}",
                exc_info=True
            )

        TaskManager.set_error(task_id, error_msg)
        raise
