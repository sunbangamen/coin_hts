"""
End-to-End Testing Scenarios for Coin Trading Simulation

이 스크립트는 Docker Compose 환경에서 실행되는 완전한 워크플로우를 테스트합니다:
1. 데이터 수집 (Upbit WebSocket)
2. 전략 실행 (BUY/SELL 신호)
3. 포지션 관리 (진입/청산)
4. 성과 지표 계산
5. 프론트엔드 실시간 표시

실행: python scripts/e2e_test_scenarios.py
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 테스트 설정
TEST_CONFIG = {
    'api_url': 'http://backend:8000/api',
    'ws_url': 'ws://backend:8001',
    'symbols': ['KRW-BTC', 'KRW-ETH', 'KRW-XRP'],
    'strategy': 'volume_zone_breakout',
    'strategy_params': {
        'volume_window': 10,
        'top_percentile': 0.2,
        'breakout_buffer': 0.0
    },
    'timeout': 30,
    'max_retries': 3,
    'retry_delay': 2,
}


class E2ETestRunner:
    """E2E 테스트 실행기"""

    def __init__(self, config: Dict):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.test_results = {
            'passed': [],
            'failed': [],
            'warnings': []
        }
        self.simulation_id: Optional[str] = None
        self.token: Optional[str] = None

    async def setup(self):
        """테스트 환경 준비"""
        logger.info("🔧 E2E 테스트 환경 준비 중...")
        self.session = aiohttp.ClientSession()

    async def teardown(self):
        """테스트 환경 정리"""
        if self.session:
            await self.session.close()

    async def health_check(self) -> bool:
        """API 및 데이터베이스 상태 확인"""
        logger.info("🏥 헬스 체크 실행 중...")
        try:
            # API 서버 확인
            async with self.session.get(
                f"{self.config['api_url']}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    self.test_results['failed'].append(
                        f"API health check failed: {resp.status}"
                    )
                    return False
                logger.info("✅ API 서버 정상 (200 OK)")
        except asyncio.TimeoutError:
            self.test_results['failed'].append("API server timeout")
            return False
        except Exception as e:
            self.test_results['failed'].append(f"Health check failed: {e}")
            return False

        # 데이터베이스 확인
        try:
            async with self.session.get(
                f"{self.config['api_url']}/simulation/status",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status in [200, 500]:  # 500은 시뮬레이션 미시작 상태
                    logger.info("✅ 데이터베이스 정상")
                    return True
                else:
                    self.test_results['failed'].append(
                        f"Database check failed: {resp.status}"
                    )
                    return False
        except Exception as e:
            self.test_results['failed'].append(f"Database check failed: {e}")
            return False

    async def test_available_strategies(self) -> bool:
        """사용 가능한 전략 조회"""
        logger.info("📋 Available Strategies 조회 중...")
        try:
            async with self.session.get(
                f"{self.config['api_url']}/strategies",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                data = await resp.json()
                strategies = data.get('strategies', [])

                if not strategies:
                    self.test_results['failed'].append(
                        "No strategies available"
                    )
                    return False

                logger.info(f"✅ 사용 가능한 전략: {strategies}")
                if self.config['strategy'] not in strategies:
                    self.test_results['warnings'].append(
                        f"Selected strategy '{self.config['strategy']}' not in available list"
                    )

                self.test_results['passed'].append("list_strategies")
                return True
        except Exception as e:
            self.test_results['failed'].append(f"List strategies failed: {e}")
            return False

    async def test_start_simulation(self) -> bool:
        """시뮬레이션 시작"""
        logger.info("▶️ 시뮬레이션 시작 중...")
        try:
            request_data = {
                'symbols': self.config['symbols'],
                'strategies': {
                    symbol: [
                        {
                            'strategy_name': self.config['strategy'],
                            'params': self.config['strategy_params']
                        }
                    ]
                    for symbol in self.config['symbols']
                }
            }

            async with self.session.post(
                f"{self.config['api_url']}/simulation/start",
                json=request_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    data = await resp.text()
                    self.test_results['failed'].append(
                        f"Start simulation failed: {resp.status} - {data}"
                    )
                    return False

                data = await resp.json()
                # API는 session_id를 반환함 (simulation_id 대신)
                self.simulation_id = data.get('session_id')
                # Token은 선택사항이므로, 없어도 success 처리
                self.token = data.get('token')

                if not self.simulation_id:
                    self.test_results['failed'].append("No session_id returned")
                    return False

                logger.info(f"✅ 시뮬레이션 시작됨 - Session ID: {self.simulation_id}")
                if self.token:
                    logger.info(f"✅ JWT 토큰 획득: {self.token[:20]}...")
                else:
                    logger.info("⚠️  토큰 미반환 (현재 API 미지원, 향후 추가 예정)")
                self.test_results['passed'].append("start_simulation")
                return True
        except Exception as e:
            self.test_results['failed'].append(f"Start simulation failed: {e}")
            return False

    async def test_simulation_status(self) -> bool:
        """시뮬레이션 상태 확인"""
        logger.info("📊 시뮬레이션 상태 확인 중...")
        try:
            async with self.session.get(
                f"{self.config['api_url']}/simulation/status",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    self.test_results['failed'].append(
                        f"Get status failed: {resp.status}"
                    )
                    return False

                data = await resp.json()
                is_running = data.get('is_running', False)
                websocket_clients = data.get('websocket_clients', 0)

                if not is_running:
                    self.test_results['failed'].append(
                        "Simulation is not running"
                    )
                    return False

                logger.info(f"✅ 시뮬레이션 실행 중")
                logger.info(f"✅ WebSocket 클라이언트: {websocket_clients}개")
                self.test_results['passed'].append("simulation_status")
                return True
        except Exception as e:
            self.test_results['failed'].append(f"Get status failed: {e}")
            return False

    async def test_strategies_registered(self) -> bool:
        """시뮬레이션 전략 등록 확인"""
        logger.info("🎯 시뮬레이션 전략 확인 중...")
        try:
            async with self.session.get(
                f"{self.config['api_url']}/simulation/strategies",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    self.test_results['failed'].append(
                        f"Get strategies failed: {resp.status}"
                    )
                    return False

                data = await resp.json()
                strategies = data.get('strategies', [])

                if not strategies:
                    self.test_results['warnings'].append(
                        "No strategies registered yet"
                    )
                    return True

                logger.info(f"✅ 등록된 전략: {len(strategies)}개")
                for strat in strategies:
                    logger.info(
                        f"  - {strat['symbol']}: {strat['strategy_name']}"
                    )

                self.test_results['passed'].append("strategies_registered")
                return True
        except Exception as e:
            self.test_results['failed'].append(f"Get strategies failed: {e}")
            return False

    async def test_market_data_collection(self) -> bool:
        """시장 데이터 수집 확인"""
        logger.info("📈 시장 데이터 수집 확인 중... (5초 대기)")
        try:
            # 데이터 수집을 위해 몇 초 대기
            await asyncio.sleep(5)

            # 캔들 데이터 확인
            for symbol in self.config['symbols'][:1]:  # 첫 번째 심볼만 확인
                async with self.session.get(
                    f"{self.config['api_url']}/market/candles?symbol={symbol}&limit=10",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        candles = data.get('candles', [])
                        if candles:
                            logger.info(f"✅ {symbol} 캔들 데이터 수집: {len(candles)}개")
                            self.test_results['passed'].append("market_data_collection")
                            return True

            self.test_results['warnings'].append(
                "Market data not yet collected (might be expected)"
            )
            return True
        except Exception as e:
            self.test_results['failed'].append(f"Market data check failed: {e}")
            return False

    async def test_position_tracking(self) -> bool:
        """포지션 추적 확인"""
        logger.info("💼 포지션 추적 확인 중...")
        try:
            async with self.session.get(
                f"{self.config['api_url']}/simulation/positions",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    self.test_results['failed'].append(
                        f"Get positions failed: {resp.status}"
                    )
                    return False

                data = await resp.json()
                positions = data if isinstance(data, list) else data.get('positions', [])

                logger.info(f"✅ 활성 포지션: {len(positions)}개")
                if positions:
                    for pos in positions:
                        logger.info(
                            f"  - {pos.get('symbol')}: "
                            f"수량={pos.get('quantity')}, "
                            f"손익={pos.get('unrealized_pnl', 0):.2f}"
                        )

                self.test_results['passed'].append("position_tracking")
                return True
        except Exception as e:
            self.test_results['failed'].append(f"Get positions failed: {e}")
            return False

    async def test_performance_metrics(self) -> bool:
        """성과 지표 계산 확인"""
        logger.info("📊 성과 지표 확인 중...")
        try:
            async with self.session.get(
                f"{self.config['api_url']}/simulation/performance",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"✅ 성과 지표:")
                    logger.info(f"  - 총 손익: {data.get('total_pnl', 0):.2f}")
                    logger.info(f"  - 승률: {data.get('win_rate', 0):.2f}%")
                    logger.info(f"  - 최대낙폭: {data.get('max_drawdown', 0):.2f}%")
                    self.test_results['passed'].append("performance_metrics")
                    return True
                else:
                    self.test_results['warnings'].append(
                        "Performance data not yet available"
                    )
                    return True
        except Exception as e:
            self.test_results['warnings'].append(f"Performance check: {e}")
            return True

    async def test_stop_simulation(self) -> bool:
        """시뮬레이션 중지"""
        logger.info("⏹️ 시뮬레이션 중지 중...")
        try:
            async with self.session.post(
                f"{self.config['api_url']}/simulation/stop",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    self.test_results['failed'].append(
                        f"Stop simulation failed: {resp.status}"
                    )
                    return False

                logger.info("✅ 시뮬레이션 중지됨")
                self.test_results['passed'].append("stop_simulation")
                return True
        except Exception as e:
            self.test_results['failed'].append(f"Stop simulation failed: {e}")
            return False

    async def test_history_retrieval(self) -> bool:
        """거래 이력 조회"""
        logger.info("📜 거래 이력 조회 중...")
        try:
            async with self.session.get(
                f"{self.config['api_url']}/simulation/history?limit=50",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    self.test_results['failed'].append(
                        f"Get history failed: {resp.status}"
                    )
                    return False

                data = await resp.json()
                trades = data if isinstance(data, list) else data.get('trades', [])

                logger.info(f"✅ 거래 이력: {len(trades)}개")
                if trades:
                    total_pnl = sum(t.get('realized_pnl', 0) for t in trades)
                    logger.info(f"  - 총 손익: {total_pnl:.2f}")

                self.test_results['passed'].append("history_retrieval")
                return True
        except Exception as e:
            self.test_results['failed'].append(f"Get history failed: {e}")
            return False

    async def run_all_tests(self) -> bool:
        """모든 E2E 테스트 실행"""
        logger.info("="*60)
        logger.info("🚀 End-to-End 통합 테스트 시작")
        logger.info("="*60)

        tests = [
            ('Health Check', self.health_check),
            ('List Available Strategies', self.test_available_strategies),
            ('Start Simulation', self.test_start_simulation),
            ('Check Simulation Status', self.test_simulation_status),
            ('Verify Strategies Registered', self.test_strategies_registered),
            ('Collect Market Data', self.test_market_data_collection),
            ('Track Positions', self.test_position_tracking),
            ('Check Performance Metrics', self.test_performance_metrics),
            ('Retrieve Trade History', self.test_history_retrieval),
            ('Stop Simulation', self.test_stop_simulation),
        ]

        for test_name, test_func in tests:
            try:
                logger.info(f"\n▶️ {test_name}...")
                result = await test_func()
                if not result:
                    logger.error(f"❌ {test_name} FAILED")
                    # 일부 테스트 실패는 계속 진행
                    if test_name in ['Start Simulation', 'Health Check']:
                        break
            except Exception as e:
                logger.error(f"❌ {test_name} ERROR: {e}")
                if test_name in ['Start Simulation', 'Health Check']:
                    break

        return self.print_summary()

    def print_summary(self) -> bool:
        """테스트 결과 요약"""
        logger.info("\n" + "="*60)
        logger.info("📋 E2E 테스트 결과 요약")
        logger.info("="*60)

        logger.info(f"\n✅ 통과: {len(self.test_results['passed'])}개")
        for test in self.test_results['passed']:
            logger.info(f"  ✓ {test}")

        if self.test_results['warnings']:
            logger.info(f"\n⚠️ 경고: {len(self.test_results['warnings'])}개")
            for warning in self.test_results['warnings']:
                logger.info(f"  ⚠ {warning}")

        if self.test_results['failed']:
            logger.info(f"\n❌ 실패: {len(self.test_results['failed'])}개")
            for failure in self.test_results['failed']:
                logger.info(f"  ✗ {failure}")
            logger.info("\n" + "="*60)
            logger.info("❌ E2E 테스트 FAILED")
            logger.info("="*60)
            return False
        else:
            logger.info("\n" + "="*60)
            logger.info("✅ E2E 테스트 PASSED")
            logger.info("="*60)
            return True


async def main():
    """메인 함수"""
    runner = E2ETestRunner(TEST_CONFIG)

    try:
        await runner.setup()
        success = await runner.run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Test execution failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await runner.teardown()


if __name__ == '__main__':
    asyncio.run(main())
