#!/usr/bin/env python3
"""
Task 3.6: 성능 벤치마킹 스크립트

목적: 백테스트 시스템의 성능을 측정하고 추적

사용법:
    ./scripts/benchmark.py              # 기본 벤치마크 (100, 300, 1000 캔들)
    ./scripts/benchmark.py --strategy volume_zone_breakout --candles 500
    ./scripts/benchmark.py --compare     # 이전 결과와 비교
    ./scripts/benchmark.py --export csv  # CSV로 내보내기
    ./scripts/benchmark.py --monitor     # 지속 모니터링 (5분 간격)

기능:
    1. VolumeZoneBreakout 전략 성능 측정
    2. 다양한 캔들 크기에서의 성능 추적
    3. 결과 저장 및 비교
    4. CSV/JSON 내보내기
    5. 성능 저하 감지
    6. 성능 추적 대시보드
"""

import os
import sys
import json
import csv
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging

# ═══════════════════════════════════════════════════════════════════════════
# 로깅 설정
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('benchmark.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# 색상 정의
# ═══════════════════════════════════════════════════════════════════════════

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def colored(text: str, color: str) -> str:
    """텍스트에 색상 추가"""
    return f"{color}{text}{Colors.RESET}"

# ═══════════════════════════════════════════════════════════════════════════
# 벤치마크 클래스
# ═══════════════════════════════════════════════════════════════════════════

class Benchmark:
    """벤치마크 실행 및 결과 관리"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.benchmark_dir = project_root / "benchmarks"
        self.benchmark_dir.mkdir(exist_ok=True)

        self.results: List[Dict] = []
        self.timestamp = datetime.now().isoformat()

    def run_backtest(self, candle_size: int, symbol: str = "KRW-BTC") -> Tuple[bool, float, Dict]:
        """
        백테스트 실행 및 성능 측정

        Args:
            candle_size: 캔들 크기
            symbol: 거래 심볼

        Returns:
            (성공 여부, 실행 시간, 결과 딕셔너리)
        """
        logger.info(f"백테스트 실행 중: {symbol} ({candle_size}캔들)...")

        start_time = time.time()

        try:
            # Python 백테스트 성능 측정 (동기 API)
            code = f"""
import sys
import time
sys.path.insert(0, '{self.project_root}')

from backend.app.simulation.strategy_runner import StrategyRunner
from backend.app.simulation.position_manager import PositionManager
from backend.app.strategies.volume_zone_breakout import VolumeZoneBreakout

# 전략 실행
runner = StrategyRunner()
strategy = VolumeZoneBreakout()

# 더미 캔들 데이터 생성
import pandas as pd
from datetime import datetime, timedelta

dates = pd.date_range(start='2024-01-01', periods={candle_size}, freq='1H')
df = pd.DataFrame({{
    'timestamp': dates,
    'open': 100.0 + (i * 0.1) for i in range({candle_size}),
    'high': 101.0 + (i * 0.1) for i in range({candle_size}),
    'low': 99.0 + (i * 0.1) for i in range({candle_size}),
    'close': 100.5 + (i * 0.1) for i in range({candle_size}),
    'volume': 1000.0 * (i + 1) for i in range({candle_size}),
}})

# 전략 초기화
start = time.time()
strategy.initialize_with_history(df, {{}})
end = time.time()

print(f"Execution time: {{end - start}}")
print(f"Total candles: {candle_size}")
"""

            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=60
            )

            elapsed_time = time.time() - start_time

            if result.returncode == 0:
                # 결과 파싱
                lines = result.stdout.strip().split('\n')
                execution_time = float([l for l in lines if 'Execution time:' in l][0].split(':')[1])

                logger.info(f"백테스트 완료: {execution_time:.4f}초")
                return True, elapsed_time, {
                    "candle_size": candle_size,
                    "symbol": symbol,
                    "execution_time": execution_time,
                    "wall_clock_time": elapsed_time,
                    "status": "success"
                }
            else:
                logger.error(f"백테스트 실패: {result.stderr}")
                return False, elapsed_time, {
                    "candle_size": candle_size,
                    "symbol": symbol,
                    "execution_time": -1,
                    "wall_clock_time": elapsed_time,
                    "status": "failed",
                    "error": result.stderr[:200]
                }

        except subprocess.TimeoutExpired:
            logger.error(f"백테스트 타임아웃 (60초)")
            return False, time.time() - start_time, {
                "candle_size": candle_size,
                "symbol": symbol,
                "execution_time": -1,
                "wall_clock_time": time.time() - start_time,
                "status": "timeout"
            }
        except Exception as e:
            logger.error(f"백테스트 실행 오류: {e}")
            return False, time.time() - start_time, {
                "candle_size": candle_size,
                "symbol": symbol,
                "execution_time": -1,
                "wall_clock_time": time.time() - start_time,
                "status": "error",
                "error": str(e)[:200]
            }

    def run_sla_benchmark(self) -> None:
        """SLA 기준 벤치마크 실행"""
        logger.info("=" * 80)
        logger.info("SLA 성능 벤치마크 시작")
        logger.info("=" * 80)
        logger.info("")

        # SLA 기준값
        sla_targets = {
            100: 0.1,    # 100캔들: 100ms
            300: 0.5,    # 300캔들: 500ms
            1000: 1.0,   # 1000캔들: 1000ms
        }

        for candle_size, sla_target in sla_targets.items():
            success, wall_time, result = self.run_backtest(candle_size)

            if success and result["execution_time"] > 0:
                exec_time = result["execution_time"]
                status = "✅ PASS" if exec_time < sla_target else "⚠️  WARN"
                efficiency = (sla_target / exec_time * 100) if exec_time > 0 else 0

                print(
                    f"{colored(f'[{candle_size:4d}캔들]', Colors.CYAN)} "
                    f"목표: {sla_target:.3f}s | "
                    f"실제: {exec_time:.4f}s | "
                    f"효율: {efficiency:.0f}% | "
                    f"{status}"
                )
                logger.info(f"캔들 {candle_size}: {exec_time:.4f}s (목표: {sla_target}s)")
            else:
                print(
                    f"{colored(f'[{candle_size:4d}캔들]', Colors.CYAN)} "
                    f"실패: {result.get('status', 'unknown')}"
                )
                logger.error(f"캔들 {candle_size}: 벤치마크 실패")

            self.results.append(result)
            logger.info("")

    def save_results(self) -> None:
        """결과를 JSON 파일로 저장"""
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = self.benchmark_dir / f"benchmark_{timestamp_str}.json"

        result_data = {
            "timestamp": self.timestamp,
            "date": datetime.now().isoformat(),
            "results": self.results,
            "summary": self._calculate_summary()
        }

        with open(result_file, 'w') as f:
            json.dump(result_data, f, indent=2)

        logger.info(f"벤치마크 결과 저장: {result_file}")
        return result_file

    def _calculate_summary(self) -> Dict:
        """결과 요약 계산"""
        successful = [r for r in self.results if r.get("status") == "success"]

        if not successful:
            return {"success_count": 0, "failure_count": len(self.results)}

        avg_time = sum(r["execution_time"] for r in successful) / len(successful)
        max_time = max(r["execution_time"] for r in successful)
        min_time = min(r["execution_time"] for r in successful)

        return {
            "success_count": len(successful),
            "failure_count": len(self.results) - len(successful),
            "average_time": avg_time,
            "min_time": min_time,
            "max_time": max_time,
        }

    def compare_with_previous(self) -> None:
        """이전 결과와 비교"""
        # 가장 최근의 두 벤치마크 파일 찾기
        files = sorted(self.benchmark_dir.glob("benchmark_*.json"), reverse=True)

        if len(files) < 2:
            logger.warn("비교할 이전 결과가 없습니다")
            return

        with open(files[0]) as f:
            current = json.load(f)
        with open(files[1]) as f:
            previous = json.load(f)

        print("\n" + colored("═" * 80, Colors.BOLD))
        print(colored("성능 비교 (현재 vs 이전)", Colors.BOLD))
        print(colored("═" * 80, Colors.RESET))
        print("")

        for curr_result in current.get("results", []):
            candle_size = curr_result.get("candle_size")
            prev_result = next(
                (r for r in previous.get("results", []) if r.get("candle_size") == candle_size),
                None
            )

            if prev_result and curr_result.get("status") == "success" and prev_result.get("status") == "success":
                curr_time = curr_result.get("execution_time", 0)
                prev_time = prev_result.get("execution_time", 0)
                diff_pct = ((curr_time - prev_time) / prev_time * 100) if prev_time > 0 else 0

                arrow = "📈" if diff_pct > 5 else "📉" if diff_pct < -5 else "→"
                color = Colors.RED if diff_pct > 5 else Colors.GREEN if diff_pct < -5 else Colors.YELLOW

                print(
                    f"[{candle_size:4d}캔들] "
                    f"이전: {prev_time:.4f}s | "
                    f"현재: {curr_time:.4f}s | "
                    f"변화: {colored(f'{diff_pct:+.1f}%', color)} {arrow}"
                )

    def export_csv(self, output_file: Optional[str] = None) -> None:
        """결과를 CSV로 내보내기"""
        if not output_file:
            output_file = self.benchmark_dir / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        else:
            output_file = Path(output_file)

        with open(output_file, 'w', newline='') as f:
            if self.results:
                fieldnames = self.results[0].keys()
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.results)

        logger.info(f"CSV 내보내기 완료: {output_file}")

    def print_summary(self) -> None:
        """결과 요약 출력"""
        summary = self._calculate_summary()

        print("\n" + colored("═" * 80, Colors.BOLD))
        print(colored("벤치마크 요약", Colors.BOLD))
        print(colored("═" * 80, Colors.RESET))
        print("")
        print(f"  성공: {summary['success_count']} | 실패: {summary['failure_count']}")

        if summary['success_count'] > 0:
            print(f"  평균 시간: {summary['average_time']:.4f}s")
            print(f"  최소 시간: {summary['min_time']:.4f}s")
            print(f"  최대 시간: {summary['max_time']:.4f}s")

        print("")
        print(colored("═" * 80, Colors.RESET))

# ═══════════════════════════════════════════════════════════════════════════
# 메인 함수
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Task 3.6: 성능 벤치마킹 스크립트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  ./scripts/benchmark.py                    # 기본 SLA 벤치마크
  ./scripts/benchmark.py --compare          # 이전 결과와 비교
  ./scripts/benchmark.py --export csv       # CSV로 내보내기
  ./scripts/benchmark.py --monitor          # 지속 모니터링
        """
    )

    parser.add_argument(
        "--candles",
        type=int,
        default=100,
        help="벤치마크할 캔들 크기 (기본: 100)"
    )
    parser.add_argument(
        "--symbol",
        default="KRW-BTC",
        help="거래 심볼 (기본: KRW-BTC)"
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="이전 결과와 비교"
    )
    parser.add_argument(
        "--export",
        type=str,
        choices=["csv", "json"],
        help="결과 내보내기 (csv/json)"
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="지속 모니터링 (5분 간격)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="상세 로그 출력"
    )

    args = parser.parse_args()

    # 프로젝트 경로
    project_root = Path(__file__).parent.parent

    # 벤치마크 객체 생성
    benchmark = Benchmark(project_root)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        if args.monitor:
            # 지속 모니터링 모드
            print(colored("📡 벤치마크 모니터링 시작 (5분 간격, Ctrl+C로 중지)", Colors.BOLD))
            iteration = 0
            while True:
                iteration += 1
                print(f"\n🔄 반복 #{iteration}")
                benchmark.results = []
                benchmark.run_sla_benchmark()
                benchmark.save_results()
                benchmark.print_summary()

                print("다음 벤치마크까지 5분 대기...")
                time.sleep(300)  # 5분

        else:
            # 일반 벤치마크
            benchmark.run_sla_benchmark()
            result_file = benchmark.save_results()
            benchmark.print_summary()

            if args.compare:
                benchmark.compare_with_previous()

            if args.export == "csv":
                benchmark.export_csv()
            elif args.export == "json":
                print(f"JSON 결과: {result_file}")

    except KeyboardInterrupt:
        print("\n벤치마크 중단됨")
        sys.exit(0)
    except Exception as e:
        logger.error(f"벤치마크 실행 중 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
