"""
StrategyRunner 유닛 테스트

StrategyRunner의 전략 등록, 초기화, 캔들 처리, 신호 생성을 검증합니다.
"""

import pytest
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from backend.app.simulation.strategy_runner import StrategyRunner, StrategyConfig
from backend.app.market_data.candle_builder import CandleData
from backend.app.strategies.base import Signal
from backend.app.database import DatabaseManager


class TestStrategyConfig:
    """StrategyConfig 클래스 테스트"""

    def test_strategy_config_initialization(self):
        """전략 설정 초기화 검증"""
        config = StrategyConfig(
            symbol='KRW-BTC',
            strategy_name='volume_zone_breakout',
            params={'volume_window': 10}
        )

        assert config.symbol == 'KRW-BTC'
        assert config.strategy_name == 'volume_zone_breakout'
        assert config.params == {'volume_window': 10}
        assert config.strategy_instance is None
        assert config.is_initialized is False

    def test_strategy_config_repr(self):
        """전략 설정 문자열 표현 검증"""
        config = StrategyConfig(
            symbol='KRW-ETH',
            strategy_name='volume_long_candle',
            params={}
        )

        assert repr(config) == "StrategyConfig(KRW-ETH:volume_long_candle)"


class TestStrategyRunnerInitialization:
    """StrategyRunner 초기화 테스트"""

    def test_strategy_runner_init(self):
        """StrategyRunner 초기화 검증"""
        runner = StrategyRunner()

        assert runner.strategies == {}
        assert runner.db is None
        assert runner.is_running is False
        assert runner.on_signal is None
        assert runner.session_id is None

    @pytest.mark.asyncio
    async def test_strategy_runner_async_initialize(self):
        """StrategyRunner 비동기 초기화 검증"""
        runner = StrategyRunner()

        with patch('backend.app.simulation.strategy_runner.get_db') as mock_get_db:
            mock_db = Mock(spec=DatabaseManager)
            mock_get_db.return_value = mock_db

            await runner.initialize('test-session-123')

            assert runner.db is mock_db
            assert runner.session_id == 'test-session-123'

    def test_set_signal_callback(self):
        """신호 콜백 설정 검증"""
        runner = StrategyRunner()
        mock_callback = Mock()

        runner.set_signal_callback(mock_callback)

        assert runner.on_signal is mock_callback


class TestStrategyRegistration:
    """전략 등록 테스트"""

    @pytest.mark.asyncio
    async def test_register_strategy(self):
        """전략 등록 검증"""
        runner = StrategyRunner()

        with patch('backend.app.simulation.strategy_runner.StrategyFactory.create') as mock_create:
            mock_strategy = Mock()
            mock_strategy.min_history_window = 10
            mock_create.return_value = mock_strategy

            await runner.register_strategy(
                symbol='KRW-BTC',
                strategy_name='volume_zone_breakout',
                params={'volume_window': 10}
            )

            # 전략이 등록되었는지 확인
            assert 'KRW-BTC:volume_zone_breakout' in runner.strategies
            config = runner.strategies['KRW-BTC:volume_zone_breakout']
            assert config.symbol == 'KRW-BTC'
            assert config.strategy_name == 'volume_zone_breakout'
            assert config.params == {'volume_window': 10}
            assert config.strategy_instance is mock_strategy

    @pytest.mark.asyncio
    async def test_register_strategy_multiple(self):
        """여러 전략 등록 검증"""
        runner = StrategyRunner()

        with patch('backend.app.simulation.strategy_runner.StrategyFactory.create') as mock_create:
            mock_strategy1 = Mock()
            mock_strategy1.min_history_window = 10
            mock_strategy2 = Mock()
            mock_strategy2.min_history_window = 20

            mock_create.side_effect = [mock_strategy1, mock_strategy2]

            await runner.register_strategy('KRW-BTC', 'volume_zone_breakout', {'volume_window': 10})
            await runner.register_strategy('KRW-BTC', 'volume_long_candle', {'vol_ma_window': 20})

            assert len(runner.strategies) == 2
            assert 'KRW-BTC:volume_zone_breakout' in runner.strategies
            assert 'KRW-BTC:volume_long_candle' in runner.strategies

    @pytest.mark.asyncio
    async def test_register_strategy_different_symbols(self):
        """다른 심볼에 같은 전략 등록 검증"""
        runner = StrategyRunner()

        with patch('backend.app.simulation.strategy_runner.StrategyFactory.create') as mock_create:
            mock_strategy1 = Mock()
            mock_strategy1.min_history_window = 10
            mock_strategy2 = Mock()
            mock_strategy2.min_history_window = 10

            mock_create.side_effect = [mock_strategy1, mock_strategy2]

            await runner.register_strategy('KRW-BTC', 'volume_zone_breakout', {})
            await runner.register_strategy('KRW-ETH', 'volume_zone_breakout', {})

            assert 'KRW-BTC:volume_zone_breakout' in runner.strategies
            assert 'KRW-ETH:volume_zone_breakout' in runner.strategies
            assert len(runner.strategies) == 2


class TestStrategyInitialization:
    """전략 초기화 (히스토리 로드) 테스트"""

    @pytest.mark.asyncio
    async def test_initialize_strategy_with_history(self):
        """히스토리 데이터로 전략 초기화 검증"""
        runner = StrategyRunner()

        # Mock 설정
        mock_db = AsyncMock(spec=DatabaseManager)
        mock_strategy = Mock()
        mock_strategy.min_history_window = 10
        mock_strategy.initialize_with_history = Mock()

        # 샘플 캔들 데이터
        sample_candles = [
            {
                'timestamp': datetime(2024, 1, i),
                'open': 100.0 + i,
                'high': 101.0 + i,
                'low': 99.0 + i,
                'close': 100.5 + i,
                'volume': 1000.0 * i,
            }
            for i in range(10)
        ]

        mock_db.fetch_all_async.return_value = sample_candles

        # StrategyRunner 설정
        config = StrategyConfig('KRW-BTC', 'volume_zone_breakout', {})
        config.strategy_instance = mock_strategy
        runner.db = mock_db
        runner.strategies['KRW-BTC:volume_zone_breakout'] = config

        # 초기화 실행
        await runner.initialize_strategy('KRW-BTC', 'volume_zone_breakout')

        # 검증
        assert config.is_initialized is True
        mock_db.fetch_all_async.assert_called_once()
        mock_strategy.initialize_with_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_strategy_not_registered(self):
        """등록되지 않은 전략 초기화 시도 검증"""
        runner = StrategyRunner()

        with pytest.raises(ValueError, match="Strategy not registered"):
            await runner.initialize_strategy('KRW-BTC', 'unknown_strategy')

    @pytest.mark.asyncio
    async def test_initialize_strategy_no_history(self):
        """히스토리 없이 전략 초기화 검증"""
        runner = StrategyRunner()

        mock_db = AsyncMock(spec=DatabaseManager)
        mock_strategy = Mock()
        mock_strategy.min_history_window = 10

        mock_db.fetch_all_async.return_value = []

        config = StrategyConfig('KRW-BTC', 'volume_zone_breakout', {})
        config.strategy_instance = mock_strategy
        runner.db = mock_db
        runner.strategies['KRW-BTC:volume_zone_breakout'] = config

        # 히스토리 없이도 초기화 가능
        await runner.initialize_strategy('KRW-BTC', 'volume_zone_breakout')

        assert config.is_initialized is True
        mock_strategy.initialize_with_history.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_strategy_already_initialized(self):
        """이미 초기화된 전략 재초기화 검증"""
        runner = StrategyRunner()

        mock_strategy = Mock()
        config = StrategyConfig('KRW-BTC', 'volume_zone_breakout', {})
        config.strategy_instance = mock_strategy
        config.is_initialized = True
        runner.strategies['KRW-BTC:volume_zone_breakout'] = config

        # 이미 초기화된 경우 재초기화 불필요
        await runner.initialize_strategy('KRW-BTC', 'volume_zone_breakout')

        # initialize_with_history가 호출되지 않아야 함
        mock_strategy.initialize_with_history.assert_not_called()


class TestCandleProcessing:
    """캔들 처리 테스트"""

    @pytest.mark.asyncio
    async def test_process_candle_single_strategy(self):
        """단일 전략 캔들 처리 검증"""
        runner = StrategyRunner()
        runner.is_running = True
        runner.on_signal = AsyncMock()

        # Mock 전략 설정
        mock_strategy = Mock()
        mock_signal = Mock(spec=Signal)
        mock_signal.timestamp = datetime.now()
        mock_signal.side = 'BUY'
        mock_signal.price = 100.0
        mock_signal.confidence = 0.9

        mock_strategy.process_candle.return_value = mock_signal

        config = StrategyConfig('KRW-BTC', 'volume_zone_breakout', {})
        config.strategy_instance = mock_strategy
        config.is_initialized = True
        runner.strategies['KRW-BTC:volume_zone_breakout'] = config

        # 캔들 데이터 생성
        candle = CandleData(
            symbol='KRW-BTC',
            timestamp=datetime.now(),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000.0
        )

        # 캔들 처리
        await runner.process_candle(candle)

        # 검증
        mock_strategy.process_candle.assert_called_once()
        runner.on_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_candle_multiple_strategies(self):
        """여러 전략 캔들 처리 검증"""
        runner = StrategyRunner()
        runner.is_running = True
        runner.on_signal = AsyncMock()

        # Mock 전략들 설정
        mock_strategy1 = Mock()
        mock_signal1 = Mock(spec=Signal)
        mock_signal1.timestamp = datetime.now()
        mock_signal1.side = 'BUY'
        mock_strategy1.process_candle.return_value = mock_signal1

        mock_strategy2 = Mock()
        mock_signal2 = Mock(spec=Signal)
        mock_signal2.timestamp = datetime.now()
        mock_signal2.side = 'SELL'
        mock_strategy2.process_candle.return_value = mock_signal2

        config1 = StrategyConfig('KRW-BTC', 'strategy1', {})
        config1.strategy_instance = mock_strategy1
        config1.is_initialized = True
        runner.strategies['KRW-BTC:strategy1'] = config1

        config2 = StrategyConfig('KRW-BTC', 'strategy2', {})
        config2.strategy_instance = mock_strategy2
        config2.is_initialized = True
        runner.strategies['KRW-BTC:strategy2'] = config2

        candle = CandleData(
            symbol='KRW-BTC',
            timestamp=datetime.now(),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000.0
        )

        await runner.process_candle(candle)

        # 두 전략 모두 처리되어야 함
        assert mock_strategy1.process_candle.call_count == 1
        assert mock_strategy2.process_candle.call_count == 1
        assert runner.on_signal.call_count == 2

    @pytest.mark.asyncio
    async def test_process_candle_no_signal(self):
        """신호 없음 캔들 처리 검증"""
        runner = StrategyRunner()
        runner.is_running = True
        runner.on_signal = AsyncMock()

        mock_strategy = Mock()
        mock_strategy.process_candle.return_value = None  # 신호 없음

        config = StrategyConfig('KRW-BTC', 'volume_zone_breakout', {})
        config.strategy_instance = mock_strategy
        config.is_initialized = True
        runner.strategies['KRW-BTC:volume_zone_breakout'] = config

        candle = CandleData(
            symbol='KRW-BTC',
            timestamp=datetime.now(),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000.0
        )

        await runner.process_candle(candle)

        # 신호가 없으면 콜백이 호출되지 않음
        runner.on_signal.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_candle_uninitialized_strategy(self):
        """초기화되지 않은 전략 처리 검증"""
        runner = StrategyRunner()
        runner.is_running = True
        runner.on_signal = AsyncMock()

        mock_strategy = Mock()
        config = StrategyConfig('KRW-BTC', 'volume_zone_breakout', {})
        config.strategy_instance = mock_strategy
        config.is_initialized = False  # 초기화 안 됨
        runner.strategies['KRW-BTC:volume_zone_breakout'] = config

        candle = CandleData(
            symbol='KRW-BTC',
            timestamp=datetime.now(),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000.0
        )

        await runner.process_candle(candle)

        # 초기화되지 않은 전략은 처리하지 않음
        mock_strategy.process_candle.assert_not_called()
        runner.on_signal.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_candle_different_symbol(self):
        """다른 심볼 캔들 처리 검증"""
        runner = StrategyRunner()
        runner.is_running = True
        runner.on_signal = AsyncMock()

        mock_strategy = Mock()
        config = StrategyConfig('KRW-BTC', 'volume_zone_breakout', {})
        config.strategy_instance = mock_strategy
        config.is_initialized = True
        runner.strategies['KRW-BTC:volume_zone_breakout'] = config

        # KRW-ETH 캔들 처리
        candle = CandleData(
            symbol='KRW-ETH',  # 다른 심볼
            timestamp=datetime.now(),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000.0
        )

        await runner.process_candle(candle)

        # KRW-BTC 전략은 처리되지 않음
        mock_strategy.process_candle.assert_not_called()


class TestSignalGeneration:
    """신호 생성 테스트"""

    @pytest.mark.asyncio
    async def test_on_signal_generated_with_db_save(self):
        """신호 생성 및 DB 저장 검증"""
        runner = StrategyRunner()
        mock_db = Mock(spec=DatabaseManager)
        mock_db.insert_signal.return_value = 123

        runner.db = mock_db
        runner.on_signal = AsyncMock()

        signal = Mock(spec=Signal)
        signal.timestamp = datetime(2024, 1, 1, 12, 0, 0)
        signal.side = 'BUY'
        signal.price = 100.0
        signal.confidence = 0.9

        await runner._on_signal_generated(signal, 'KRW-BTC', 'volume_zone_breakout')

        # DB에 저장되었는지 확인
        mock_db.insert_signal.assert_called_once()
        # 콜백 호출 확인
        runner.on_signal.assert_called_once_with(signal, 'KRW-BTC', 'volume_zone_breakout')

    @pytest.mark.asyncio
    async def test_on_signal_generated_no_db(self):
        """DB 없이 신호 생성 검증"""
        runner = StrategyRunner()
        runner.db = None
        runner.on_signal = AsyncMock()

        signal = Mock(spec=Signal)
        signal.timestamp = datetime(2024, 1, 1, 12, 0, 0)
        signal.side = 'BUY'
        signal.price = 100.0
        signal.confidence = 0.9

        await runner._on_signal_generated(signal, 'KRW-BTC', 'volume_zone_breakout')

        # DB가 없어도 콜백은 호출됨
        runner.on_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_signal_generated_no_callback(self):
        """콜백 없이 신호 생성 검증"""
        runner = StrategyRunner()
        mock_db = Mock(spec=DatabaseManager)
        runner.db = mock_db
        runner.on_signal = None

        signal = Mock(spec=Signal)
        signal.timestamp = datetime.now()
        signal.side = 'BUY'

        # 콜백 없어도 에러 없음
        await runner._on_signal_generated(signal, 'KRW-BTC', 'volume_zone_breakout')

        mock_db.insert_signal.assert_called_once()


class TestStrategyRunnerLifecycle:
    """StrategyRunner 생명주기 테스트"""

    @pytest.mark.asyncio
    async def test_start_engine(self):
        """엔진 시작 검증"""
        runner = StrategyRunner()

        assert runner.is_running is False

        await runner.start()

        assert runner.is_running is True

    @pytest.mark.asyncio
    async def test_stop_engine(self):
        """엔진 중지 검증"""
        runner = StrategyRunner()
        runner.is_running = True

        await runner.stop()

        assert runner.is_running is False


class TestStrategyRetrieval:
    """전략 조회 테스트"""

    def test_get_strategies_all(self):
        """모든 전략 조회 검증"""
        runner = StrategyRunner()

        mock_strategy1 = Mock()
        mock_strategy2 = Mock()

        config1 = StrategyConfig('KRW-BTC', 'strategy1', {'param1': 10})
        config1.strategy_instance = mock_strategy1
        config1.is_initialized = True

        config2 = StrategyConfig('KRW-ETH', 'strategy2', {'param2': 20})
        config2.strategy_instance = mock_strategy2
        config2.is_initialized = False

        runner.strategies['KRW-BTC:strategy1'] = config1
        runner.strategies['KRW-ETH:strategy2'] = config2

        strategies = runner.get_strategies()

        assert len(strategies) == 2
        assert strategies[0]['symbol'] == 'KRW-BTC'
        assert strategies[0]['strategy_name'] == 'strategy1'
        assert strategies[1]['symbol'] == 'KRW-ETH'

    def test_get_strategies_by_symbol(self):
        """심볼별 전략 조회 검증"""
        runner = StrategyRunner()

        mock_strategy1 = Mock()
        mock_strategy2 = Mock()

        config1 = StrategyConfig('KRW-BTC', 'strategy1', {})
        config1.strategy_instance = mock_strategy1
        config1.is_initialized = True

        config2 = StrategyConfig('KRW-BTC', 'strategy2', {})
        config2.strategy_instance = mock_strategy2
        config2.is_initialized = True

        config3 = StrategyConfig('KRW-ETH', 'strategy1', {})
        config3.strategy_instance = mock_strategy1
        config3.is_initialized = True

        runner.strategies['KRW-BTC:strategy1'] = config1
        runner.strategies['KRW-BTC:strategy2'] = config2
        runner.strategies['KRW-ETH:strategy1'] = config3

        btc_strategies = runner.get_strategies(symbol='KRW-BTC')

        assert len(btc_strategies) == 2
        assert all(s['symbol'] == 'KRW-BTC' for s in btc_strategies)

    def test_get_status(self):
        """엔진 상태 조회 검증"""
        runner = StrategyRunner()
        runner.is_running = True
        runner.session_id = 'test-session-456'

        mock_strategy = Mock()
        config = StrategyConfig('KRW-BTC', 'strategy1', {})
        config.strategy_instance = mock_strategy
        runner.strategies['KRW-BTC:strategy1'] = config

        status = runner.get_status()

        assert status['is_running'] is True
        assert status['session_id'] == 'test-session-456'
        assert status['strategy_count'] == 1
        assert len(status['strategies']) == 1
