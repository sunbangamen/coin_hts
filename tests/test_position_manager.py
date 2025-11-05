"""
PositionManager 유닛 테스트

포지션 진입/청산, 손익 계산, 포지션 조회를 검증합니다.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from backend.app.simulation.position_manager import PositionManager, Position
from backend.app.market_data.candle_builder import CandleData
from backend.app.strategies.base import Signal
from backend.app.database import DatabaseManager


class TestPosition:
    """Position 클래스 테스트"""

    def test_position_initialization(self):
        """포지션 초기화 검증"""
        position = Position(
            position_id=1,
            symbol='KRW-BTC',
            strategy_name='volume_zone_breakout',
            entry_time=datetime(2024, 1, 1, 12, 0, 0),
            entry_price=50000.0,
            quantity=0.1,
            fee_amount=50.0,
        )

        assert position.position_id == 1
        assert position.symbol == 'KRW-BTC'
        assert position.strategy_name == 'volume_zone_breakout'
        assert position.entry_price == 50000.0
        assert position.quantity == 0.1
        assert position.fee_amount == 50.0
        assert position.current_price == 50000.0
        assert position.unrealized_pnl == -50.0

    def test_position_update_price(self):
        """포지션 가격 업데이트 검증"""
        position = Position(
            position_id=1,
            symbol='KRW-BTC',
            strategy_name='strategy1',
            entry_time=datetime.now(),
            entry_price=50000.0,
            quantity=0.1,
            fee_amount=50.0,
        )

        # 가격 상승
        position.update_price(51000.0)

        assert position.current_price == 51000.0
        # unrealized_pnl = 0.1 * (51000 - 50000) - 50 = 100 - 50 = 50
        assert position.unrealized_pnl == 50.0

    def test_position_to_dict(self):
        """포지션을 딕셔너리로 변환 검증"""
        position = Position(
            position_id=1,
            symbol='KRW-BTC',
            strategy_name='strategy1',
            entry_time=datetime(2024, 1, 1, 12, 0, 0),
            entry_price=50000.0,
            quantity=0.1,
            fee_amount=50.0,
        )

        position.update_price(51000.0)
        pos_dict = position.to_dict()

        assert pos_dict['position_id'] == 1
        assert pos_dict['symbol'] == 'KRW-BTC'
        assert pos_dict['strategy_name'] == 'strategy1'
        assert pos_dict['entry_price'] == 50000.0
        assert pos_dict['quantity'] == 0.1
        assert pos_dict['current_price'] == 51000.0
        assert pos_dict['unrealized_pnl'] == 50.0


class TestPositionManagerInitialization:
    """PositionManager 초기화 테스트"""

    def test_position_manager_init(self):
        """PositionManager 초기화 검증"""
        manager = PositionManager()

        assert manager.db is None
        assert manager.session_id is None
        assert manager.positions == {}
        assert manager.fee_rate == 0.001
        assert manager.slippage_rate == 0.0002

    @pytest.mark.asyncio
    async def test_position_manager_async_initialize(self):
        """PositionManager 비동기 초기화 검증"""
        manager = PositionManager()

        with patch('backend.app.simulation.position_manager.get_db') as mock_get_db:
            mock_db = Mock(spec=DatabaseManager)
            mock_get_db.return_value = mock_db

            await manager.initialize('test-session-123')

            assert manager.db is mock_db
            assert manager.session_id == 'test-session-123'


class TestPositionEntry:
    """포지션 진입 테스트"""

    @pytest.mark.asyncio
    async def test_enter_position_success(self):
        """포지션 진입 성공 검증"""
        manager = PositionManager()
        mock_db = Mock(spec=DatabaseManager)
        mock_db.insert_position.return_value = 123

        manager.db = mock_db
        manager.session_id = 'test-session'

        position_id = await manager.enter_position(
            symbol='KRW-BTC',
            strategy_name='volume_zone_breakout',
            entry_price=50000.0,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        )

        assert position_id == 123
        assert 'KRW-BTC:volume_zone_breakout' in manager.positions

        # 포지션 검증
        position = manager.positions['KRW-BTC:volume_zone_breakout']
        assert position.position_id == 123
        assert position.entry_price == 50000.0
        assert position.quantity == 0.1

        # DB 호출 검증
        mock_db.insert_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_enter_position_already_open(self):
        """이미 오픈된 포지션이 있을 때 진입 시도 검증"""
        manager = PositionManager()
        mock_db = Mock(spec=DatabaseManager)

        manager.db = mock_db

        # 이미 오픈된 포지션 설정
        existing_position = Position(
            position_id=100,
            symbol='KRW-BTC',
            strategy_name='volume_zone_breakout',
            entry_time=datetime.now(),
            entry_price=50000.0,
            quantity=0.1,
        )
        manager.positions['KRW-BTC:volume_zone_breakout'] = existing_position

        # 새로운 진입 시도
        position_id = await manager.enter_position(
            symbol='KRW-BTC',
            strategy_name='volume_zone_breakout',
            entry_price=51000.0,
            timestamp=datetime.now(),
        )

        assert position_id is None
        mock_db.insert_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_enter_position_different_symbols(self):
        """다른 심볼에 포지션 진입 검증"""
        manager = PositionManager()
        mock_db = Mock(spec=DatabaseManager)

        manager.db = mock_db
        mock_db.insert_position.side_effect = [123, 124]

        # 첫 번째 포지션 진입 (KRW-BTC)
        await manager.enter_position(
            symbol='KRW-BTC',
            strategy_name='strategy1',
            entry_price=50000.0,
            timestamp=datetime.now(),
        )

        # 두 번째 포지션 진입 (KRW-ETH)
        await manager.enter_position(
            symbol='KRW-ETH',
            strategy_name='strategy1',
            entry_price=3000.0,
            timestamp=datetime.now(),
        )

        assert len(manager.positions) == 2
        assert 'KRW-BTC:strategy1' in manager.positions
        assert 'KRW-ETH:strategy1' in manager.positions


class TestPositionClosing:
    """포지션 청산 테스트"""

    @pytest.mark.asyncio
    async def test_close_position_success(self):
        """포지션 청산 성공 검증"""
        manager = PositionManager()
        mock_db = Mock(spec=DatabaseManager)

        manager.db = mock_db
        mock_db.update_position_on_close.return_value = None
        mock_db.insert_trade.return_value = 456

        # 오픈 포지션 설정
        position = Position(
            position_id=123,
            symbol='KRW-BTC',
            strategy_name='volume_zone_breakout',
            entry_time=datetime(2024, 1, 1, 12, 0, 0),
            entry_price=50000.0,
            quantity=0.1,
            fee_amount=50.0,
        )
        manager.positions['KRW-BTC:volume_zone_breakout'] = position

        # 포지션 청산
        trade_id = await manager.close_position(
            symbol='KRW-BTC',
            strategy_name='volume_zone_breakout',
            exit_price=51000.0,
            timestamp=datetime(2024, 1, 1, 13, 0, 0),
        )

        assert trade_id == 456
        assert 'KRW-BTC:volume_zone_breakout' not in manager.positions

        # DB 호출 검증
        mock_db.update_position_on_close.assert_called_once()
        mock_db.insert_trade.assert_called_once()

        # 거래 정보 검증
        trade_args = mock_db.insert_trade.call_args[1]
        assert trade_args['symbol'] == 'KRW-BTC'
        assert trade_args['strategy_name'] == 'volume_zone_breakout'
        assert trade_args['exit_price'] == 51000.0
        # realized_pnl = 0.1 * (51000 - 50000) - 50 - 0 = 100 - 50 = 50
        assert trade_args['realized_pnl'] == 50.0

    @pytest.mark.asyncio
    async def test_close_position_not_found(self):
        """포지션 없이 청산 시도 검증"""
        manager = PositionManager()
        mock_db = Mock(spec=DatabaseManager)

        manager.db = mock_db

        # 포지션이 없을 때 청산 시도
        trade_id = await manager.close_position(
            symbol='KRW-BTC',
            strategy_name='unknown_strategy',
            exit_price=51000.0,
            timestamp=datetime.now(),
        )

        assert trade_id is None
        mock_db.update_position_on_close.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_position_with_loss(self):
        """손실 포지션 청산 검증"""
        manager = PositionManager()
        mock_db = Mock(spec=DatabaseManager)

        manager.db = mock_db
        mock_db.update_position_on_close.return_value = None
        mock_db.insert_trade.return_value = 456

        # 오픈 포지션 설정
        position = Position(
            position_id=123,
            symbol='KRW-BTC',
            strategy_name='strategy1',
            entry_time=datetime.now(),
            entry_price=50000.0,
            quantity=0.1,
            fee_amount=50.0,
        )
        manager.positions['KRW-BTC:strategy1'] = position

        # 가격 하락 후 청산
        await manager.close_position(
            symbol='KRW-BTC',
            strategy_name='strategy1',
            exit_price=49000.0,  # 1000 하락
            timestamp=datetime.now(),
        )

        # 거래 정보 검증
        trade_args = mock_db.insert_trade.call_args[1]
        # realized_pnl = 0.1 * (49000 - 50000) - 50 = -100 - 50 = -150
        assert trade_args['realized_pnl'] == -150.0

    @pytest.mark.asyncio
    async def test_close_position_with_auto_slippage(self):
        """슬리피지 자동 계산 검증"""
        manager = PositionManager()
        mock_db = Mock(spec=DatabaseManager)

        manager.db = mock_db
        mock_db.update_position_on_close.return_value = None
        mock_db.insert_trade.return_value = 456

        # 오픈 포지션 설정
        position = Position(
            position_id=123,
            symbol='KRW-BTC',
            strategy_name='strategy1',
            entry_time=datetime.now(),
            entry_price=50000.0,
            quantity=0.1,
            fee_amount=50.0,
        )
        manager.positions['KRW-BTC:strategy1'] = position

        # slippage_amount를 명시하지 않음 (자동 계산 테스트)
        await manager.close_position(
            symbol='KRW-BTC',
            strategy_name='strategy1',
            exit_price=51000.0,
            timestamp=datetime.now(),
        )

        # 슬리피지가 자동 계산되었는지 검증
        trade_args = mock_db.insert_trade.call_args[1]

        # 자동 계산된 슬리피지 = exit_price * quantity * slippage_rate
        # = 51000 * 0.1 * 0.0002 = 1.02
        expected_slippage = 51000.0 * 0.1 * 0.0002

        assert abs(trade_args['slippage_amount'] - expected_slippage) < 0.01

        # realized_pnl = 0.1 * (51000 - 50000) - 50 - 1.02 = 100 - 50 - 1.02 = 48.98
        expected_pnl = 100.0 - 50.0 - expected_slippage
        assert abs(trade_args['realized_pnl'] - expected_pnl) < 0.01

    @pytest.mark.asyncio
    async def test_close_position_with_explicit_slippage(self):
        """명시적 슬리피지 값 제공 검증"""
        manager = PositionManager()
        mock_db = Mock(spec=DatabaseManager)

        manager.db = mock_db
        mock_db.update_position_on_close.return_value = None
        mock_db.insert_trade.return_value = 456

        # 오픈 포지션 설정
        position = Position(
            position_id=123,
            symbol='KRW-BTC',
            strategy_name='strategy1',
            entry_time=datetime.now(),
            entry_price=50000.0,
            quantity=0.1,
            fee_amount=50.0,
        )
        manager.positions['KRW-BTC:strategy1'] = position

        # 명시적 슬리피지 값 전달
        explicit_slippage = 5.0
        await manager.close_position(
            symbol='KRW-BTC',
            strategy_name='strategy1',
            exit_price=51000.0,
            timestamp=datetime.now(),
            slippage_amount=explicit_slippage,
        )

        # 전달된 슬리피지가 사용되었는지 검증
        trade_args = mock_db.insert_trade.call_args[1]
        assert trade_args['slippage_amount'] == explicit_slippage

        # realized_pnl = 0.1 * (51000 - 50000) - 50 - 5.0 = 100 - 50 - 5.0 = 45.0
        expected_pnl = 100.0 - 50.0 - explicit_slippage
        assert trade_args['realized_pnl'] == expected_pnl


class TestUnrealizedPnLUpdate:
    """미실현 손익 업데이트 테스트"""

    @pytest.mark.asyncio
    async def test_update_unrealized_pnl(self):
        """미실현 손익 업데이트 검증"""
        manager = PositionManager()
        mock_db = Mock(spec=DatabaseManager)

        manager.db = mock_db

        # 포지션 설정
        position = Position(
            position_id=123,
            symbol='KRW-BTC',
            strategy_name='strategy1',
            entry_time=datetime.now(),
            entry_price=50000.0,
            quantity=0.1,
        )
        manager.positions['KRW-BTC:strategy1'] = position

        # 캔들 데이터로 업데이트
        candle = CandleData(
            symbol='KRW-BTC',
            timestamp=datetime.now(),
            open=50000.0,
            high=51500.0,
            low=49500.0,
            close=51000.0,
            volume=100.0,
        )

        await manager.update_unrealized_pnl(candle)

        # 포지션 미실현 손익 검증
        assert position.current_price == 51000.0
        assert position.unrealized_pnl > 0

        # DB 호출 검증
        mock_db.update_position_unrealized_pnl.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_unrealized_pnl_multiple_positions(self):
        """다중 포지션 미실현 손익 업데이트 검증"""
        manager = PositionManager()
        mock_db = Mock(spec=DatabaseManager)

        manager.db = mock_db

        # 두 개의 포지션 설정
        position1 = Position(
            position_id=1,
            symbol='KRW-BTC',
            strategy_name='strategy1',
            entry_time=datetime.now(),
            entry_price=50000.0,
            quantity=0.1,
        )
        position2 = Position(
            position_id=2,
            symbol='KRW-BTC',
            strategy_name='strategy2',
            entry_time=datetime.now(),
            entry_price=50000.0,
            quantity=0.1,
        )
        manager.positions['KRW-BTC:strategy1'] = position1
        manager.positions['KRW-BTC:strategy2'] = position2

        # 캔들 데이터로 업데이트
        candle = CandleData(
            symbol='KRW-BTC',
            timestamp=datetime.now(),
            open=50000.0,
            high=51500.0,
            low=49500.0,
            close=51000.0,
            volume=100.0,
        )

        await manager.update_unrealized_pnl(candle)

        # 두 포지션 모두 업데이트되었는지 검증
        assert position1.current_price == 51000.0
        assert position2.current_price == 51000.0
        assert mock_db.update_position_unrealized_pnl.call_count == 2


class TestSignalHandling:
    """신호 처리 테스트"""

    @pytest.mark.asyncio
    async def test_on_signal_buy(self):
        """BUY 신호 처리 검증"""
        manager = PositionManager()
        mock_db = Mock(spec=DatabaseManager)

        manager.db = mock_db
        mock_db.insert_position.return_value = 123

        signal = Mock(spec=Signal)
        signal.side = 'BUY'
        signal.price = 50000.0
        signal.timestamp = datetime.now()

        await manager.on_signal(signal, 'KRW-BTC', 'strategy1')

        # 포지션이 진입되었는지 검증
        assert 'KRW-BTC:strategy1' in manager.positions
        mock_db.insert_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_signal_sell(self):
        """SELL 신호 처리 검증"""
        manager = PositionManager()
        mock_db = Mock(spec=DatabaseManager)

        manager.db = mock_db

        # 오픈 포지션 설정
        position = Position(
            position_id=123,
            symbol='KRW-BTC',
            strategy_name='strategy1',
            entry_time=datetime.now(),
            entry_price=50000.0,
            quantity=0.1,
        )
        manager.positions['KRW-BTC:strategy1'] = position

        signal = Mock(spec=Signal)
        signal.side = 'SELL'
        signal.price = 51000.0
        signal.timestamp = datetime.now()

        await manager.on_signal(signal, 'KRW-BTC', 'strategy1')

        # 포지션이 청산되었는지 검증
        assert 'KRW-BTC:strategy1' not in manager.positions
        mock_db.update_position_on_close.assert_called_once()
        mock_db.insert_trade.assert_called_once()


class TestPositionQuerying:
    """포지션 조회 테스트"""

    def test_get_open_positions_all(self):
        """모든 오픈 포지션 조회 검증"""
        manager = PositionManager()

        # 포지션 설정
        position1 = Position(
            position_id=1,
            symbol='KRW-BTC',
            strategy_name='strategy1',
            entry_time=datetime.now(),
            entry_price=50000.0,
            quantity=0.1,
        )
        position2 = Position(
            position_id=2,
            symbol='KRW-ETH',
            strategy_name='strategy1',
            entry_time=datetime.now(),
            entry_price=3000.0,
            quantity=1.0,
        )
        manager.positions['KRW-BTC:strategy1'] = position1
        manager.positions['KRW-ETH:strategy1'] = position2

        positions = manager.get_open_positions()

        assert len(positions) == 2
        assert positions[0]['symbol'] in ['KRW-BTC', 'KRW-ETH']

    def test_get_open_positions_by_symbol(self):
        """심볼별 포지션 조회 검증"""
        manager = PositionManager()

        position1 = Position(
            position_id=1,
            symbol='KRW-BTC',
            strategy_name='strategy1',
            entry_time=datetime.now(),
            entry_price=50000.0,
            quantity=0.1,
        )
        position2 = Position(
            position_id=2,
            symbol='KRW-BTC',
            strategy_name='strategy2',
            entry_time=datetime.now(),
            entry_price=50000.0,
            quantity=0.1,
        )
        position3 = Position(
            position_id=3,
            symbol='KRW-ETH',
            strategy_name='strategy1',
            entry_time=datetime.now(),
            entry_price=3000.0,
            quantity=1.0,
        )
        manager.positions['KRW-BTC:strategy1'] = position1
        manager.positions['KRW-BTC:strategy2'] = position2
        manager.positions['KRW-ETH:strategy1'] = position3

        btc_positions = manager.get_open_positions(symbol='KRW-BTC')

        assert len(btc_positions) == 2
        assert all(p['symbol'] == 'KRW-BTC' for p in btc_positions)

    def test_get_position_summary(self):
        """포지션 요약 통계 검증"""
        manager = PositionManager()

        position1 = Position(
            position_id=1,
            symbol='KRW-BTC',
            strategy_name='strategy1',
            entry_time=datetime.now(),
            entry_price=50000.0,
            quantity=0.1,
        )
        position1.update_price(51000.0)

        position2 = Position(
            position_id=2,
            symbol='KRW-ETH',
            strategy_name='strategy1',
            entry_time=datetime.now(),
            entry_price=3000.0,
            quantity=1.0,
        )
        position2.update_price(2900.0)

        manager.positions['KRW-BTC:strategy1'] = position1
        manager.positions['KRW-ETH:strategy1'] = position2

        summary = manager.get_position_summary()

        assert summary['open_positions_count'] == 2
        assert summary['total_unrealized_pnl'] > 0  # 위에서 정의된 수수료에 따라 달라짐
        assert 'KRW-BTC' in summary['positions_by_symbol']
        assert 'KRW-ETH' in summary['positions_by_symbol']
