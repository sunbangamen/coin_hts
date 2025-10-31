"""
백테스트 전략 엔진

이 모듈은 다양한 거래 전략을 구현하고 실행하는 기능을 제공합니다.

구성:
- base.py: 전략 추상 클래스 및 데이터 모델
- volume_long_candle.py: 거래량 급증 + 장대양봉 전략
- volume_zone_breakout.py: 매물대 돌파 전략
"""

from backend.app.strategies.base import (
    Signal,
    BacktestResult,
    Strategy,
)

__all__ = [
    'Signal',
    'BacktestResult',
    'Strategy',
]
