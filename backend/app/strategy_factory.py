"""
전략 팩토리 모듈

전략 이름을 받아 해당 전략 클래스의 인스턴스를 반환합니다.
"""

from typing import List
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
                f"Unsupported strategy: {strategy_name}. "
                f"Supported strategies: {supported}"
            )

        strategy_class = cls._strategies[strategy_name]
        return strategy_class()

    @classmethod
    def get_supported_strategies(cls) -> List[str]:
        """지원되는 전략 목록 반환"""
        return list(cls._strategies.keys())
