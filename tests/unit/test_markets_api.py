"""
Task 1, 2: 마켓 및 시세 API 단위 테스트 (Feature Breakdown #23)

테스트 대상:
- GET /api/markets/krw: KRW 마켓 목록 조회
- GET /api/markets/krw/tickers: KRW 마켓 실시간 시세 조회
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import json
from datetime import datetime

from backend.app.main import app
from backend.app.routers.markets import (
    fetch_krw_markets_from_upbit,
    fetch_krw_tickers_from_upbit,
    MarketInfo,
    TickerInfo,
    MIN_KRW_MARKETS
)

# FastAPI 테스트 클라이언트
client = TestClient(app)


class TestGetKRWMarkets:
    """GET /api/markets/krw 테스트"""

    @patch('backend.app.routers.markets.fetch_krw_markets_from_upbit')
    async def test_get_krw_markets_success(self, mock_fetch):
        """성공 케이스: KRW 마켓 목록 반환"""
        # Mock 데이터
        mock_markets = [
            {"market": "KRW-BTC", "korean_name": "비트코인", "english_name": "Bitcoin"},
            {"market": "KRW-ETH", "korean_name": "이더리움", "english_name": "Ethereum"},
            {"market": "KRW-ADA", "korean_name": "에이다", "english_name": "Cardano"},
        ]
        mock_fetch.return_value = mock_markets

        # API 호출
        response = client.get("/api/markets/krw")

        # 검증
        assert response.status_code == 200
        data = response.json()
        assert len(data["markets"]) >= 3
        assert all(m["market"].startswith("KRW-") for m in data["markets"])
        assert "count" in data
        assert "last_updated" in data

    @patch('backend.app.routers.markets.fetch_krw_markets_from_upbit')
    async def test_get_krw_markets_minimum_count(self, mock_fetch):
        """최소 마켓 수 검증"""
        # 최소 개수보다 많은 마켓 생성
        mock_markets = [
            {"market": f"KRW-{i}", "korean_name": f"코인{i}", "english_name": f"Coin{i}"}
            for i in range(MIN_KRW_MARKETS + 10)
        ]
        mock_fetch.return_value = mock_markets

        response = client.get("/api/markets/krw")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= MIN_KRW_MARKETS

    @patch('backend.app.routers.markets.fetch_krw_markets_from_upbit')
    async def test_get_krw_markets_api_failure(self, mock_fetch):
        """API 호출 실패 케이스 (캐시도 없음)"""
        # API 호출 실패
        mock_fetch.side_effect = Exception("API error")

        response = client.get("/api/markets/krw")

        # 캐시도 없으면 503 반환
        assert response.status_code == 503

    @patch('backend.app.routers.markets.fetch_krw_markets_from_upbit')
    async def test_get_krw_markets_response_format(self, mock_fetch):
        """응답 형식 검증"""
        mock_markets = [
            {"market": "KRW-BTC", "korean_name": "비트코인", "english_name": "Bitcoin"},
        ]
        mock_fetch.return_value = mock_markets

        response = client.get("/api/markets/krw")

        assert response.status_code == 200
        data = response.json()

        # 필드 검증
        assert "markets" in data
        assert "count" in data
        assert "last_updated" in data

        # 각 마켓 정보 필드 검증
        for market in data["markets"]:
            assert "market" in market
            assert "korean_name" in market
            assert "english_name" in market


class TestGetKRWTickers:
    """GET /api/markets/krw/tickers 테스트"""

    @patch('backend.app.routers.markets.fetch_krw_tickers_from_upbit')
    @patch('backend.app.routers.markets.fetch_krw_markets_from_upbit')
    async def test_get_krw_tickers_success(self, mock_fetch_markets, mock_fetch_tickers):
        """성공 케이스: 실시간 시세 반환"""
        # Mock 데이터
        mock_markets = [
            {"market": "KRW-BTC", "korean_name": "비트코인", "english_name": "Bitcoin"},
            {"market": "KRW-ETH", "korean_name": "이더리움", "english_name": "Ethereum"},
        ]
        mock_fetch_markets.return_value = mock_markets

        mock_tickers = [
            {
                "market": "KRW-BTC",
                "trade_price": 50000000.0,
                "change_rate": 0.05,
                "acc_trade_volume_24h": 1000.0,
                "acc_trade_price_24h": 50000000000.0
            },
            {
                "market": "KRW-ETH",
                "trade_price": 3000000.0,
                "change_rate": 0.02,
                "acc_trade_volume_24h": 5000.0,
                "acc_trade_price_24h": 15000000000.0
            },
        ]
        mock_fetch_tickers.return_value = mock_tickers

        # API 호출
        response = client.get("/api/markets/krw/tickers")

        # 검증
        assert response.status_code == 200
        data = response.json()
        assert len(data["tickers"]) == 2
        assert "count" in data
        assert data["count"] == 2
        assert "last_updated" in data

    @patch('backend.app.routers.markets.fetch_krw_tickers_from_upbit')
    @patch('backend.app.routers.markets.fetch_krw_markets_from_upbit')
    async def test_get_krw_tickers_response_format(self, mock_fetch_markets, mock_fetch_tickers):
        """응답 형식 검증"""
        mock_markets = [
            {"market": "KRW-BTC", "korean_name": "비트코인", "english_name": "Bitcoin"},
        ]
        mock_fetch_markets.return_value = mock_markets

        mock_tickers = [
            {
                "market": "KRW-BTC",
                "trade_price": 50000000.0,
                "change_rate": 0.05,
                "acc_trade_volume_24h": 1000.0,
                "acc_trade_price_24h": 50000000000.0
            },
        ]
        mock_fetch_tickers.return_value = mock_tickers

        response = client.get("/api/markets/krw/tickers")

        assert response.status_code == 200
        data = response.json()

        # 필드 검증
        assert "tickers" in data
        assert "count" in data
        assert "last_updated" in data

        # 각 시세 정보 필드 검증
        for ticker in data["tickers"]:
            assert "market" in ticker
            assert "trade_price" in ticker
            assert "change_rate" in ticker
            assert "acc_trade_volume_24h" in ticker
            assert "acc_trade_price_24h" in ticker

    @patch('backend.app.routers.markets.fetch_krw_tickers_from_upbit')
    @patch('backend.app.routers.markets.fetch_krw_markets_from_upbit')
    async def test_get_krw_tickers_partial_failure(self, mock_fetch_markets, mock_fetch_tickers):
        """부분 실패: 일부 틱커만 조회"""
        mock_markets = [
            {"market": "KRW-BTC", "korean_name": "비트코인", "english_name": "Bitcoin"},
            {"market": "KRW-ETH", "korean_name": "이더리움", "english_name": "Ethereum"},
        ]
        mock_fetch_markets.return_value = mock_markets

        # 하나의 틱커만 반환 (부분 실패)
        mock_tickers = [
            {
                "market": "KRW-BTC",
                "trade_price": 50000000.0,
                "change_rate": 0.05,
                "acc_trade_volume_24h": 1000.0,
                "acc_trade_price_24h": 50000000000.0
            },
        ]
        mock_fetch_tickers.return_value = mock_tickers

        response = client.get("/api/markets/krw/tickers")

        assert response.status_code == 200
        data = response.json()
        assert len(data["tickers"]) == 1  # 하나의 틱커만 반환

    @patch('backend.app.routers.markets.fetch_krw_tickers_from_upbit')
    @patch('backend.app.routers.markets.fetch_krw_markets_from_upbit')
    async def test_get_krw_tickers_market_fetch_failure(self, mock_fetch_markets, mock_fetch_tickers):
        """마켓 목록 조회 실패"""
        mock_fetch_markets.side_effect = Exception("Market API error")

        response = client.get("/api/markets/krw/tickers")

        # 마켓 목록을 가져올 수 없으면 503 반환
        assert response.status_code == 503


class TestMarketInfo:
    """MarketInfo Pydantic 모델 테스트"""

    def test_market_info_creation(self):
        """MarketInfo 객체 생성"""
        market = MarketInfo(
            market="KRW-BTC",
            korean_name="비트코인",
            english_name="Bitcoin"
        )

        assert market.market == "KRW-BTC"
        assert market.korean_name == "비트코인"
        assert market.english_name == "Bitcoin"

    def test_market_info_json_schema(self):
        """MarketInfo JSON 스키마"""
        market = MarketInfo(
            market="KRW-BTC",
            korean_name="비트코인",
            english_name="Bitcoin"
        )

        # dict로 변환 가능
        market_dict = market.dict()
        assert market_dict["market"] == "KRW-BTC"


class TestTickerInfo:
    """TickerInfo Pydantic 모델 테스트"""

    def test_ticker_info_creation(self):
        """TickerInfo 객체 생성"""
        ticker = TickerInfo(
            market="KRW-BTC",
            trade_price=50000000.0,
            change_rate=0.05,
            acc_trade_volume_24h=1000.0,
            acc_trade_price_24h=50000000000.0
        )

        assert ticker.market == "KRW-BTC"
        assert ticker.trade_price == 50000000.0
        assert ticker.change_rate == 0.05
        assert ticker.acc_trade_volume_24h == 1000.0
        assert ticker.acc_trade_price_24h == 50000000000.0

    def test_ticker_info_numeric_conversion(self):
        """TickerInfo 숫자 변환"""
        # 문자열도 float로 변환 가능
        ticker = TickerInfo(
            market="KRW-BTC",
            trade_price="50000000",
            change_rate="0.05",
            acc_trade_volume_24h="1000",
            acc_trade_price_24h="50000000000"
        )

        assert isinstance(ticker.trade_price, float)
        assert isinstance(ticker.change_rate, float)


# ============================================================================
# 통합 테스트 (실제 API 호출, 환경 설정 필요)
# ============================================================================

@pytest.mark.integration
class TestMarketAPIIntegration:
    """실제 Upbit API와의 통합 테스트"""

    def test_get_krw_markets_live(self):
        """실제 Upbit API에서 마켓 목록 조회 (실시간 테스트, 선택사항)"""
        # NOTE: 이 테스트는 실제 Upbit API에 접근합니다.
        # pytest -m integration으로 실행하세요.

        response = client.get("/api/markets/krw")

        # 상태 코드 검증
        assert response.status_code in [200, 503]  # 503은 네트워크 오류 시

        if response.status_code == 200:
            data = response.json()
            # 기본 구조 검증
            assert "markets" in data
            assert "count" in data
            assert isinstance(data["markets"], list)

    def test_get_krw_tickers_live(self):
        """실제 Upbit API에서 시세 조회 (실시간 테스트, 선택사항)"""
        # NOTE: 이 테스트는 실제 Upbit API에 접근합니다.
        # pytest -m integration으로 실행하세요.

        response = client.get("/api/markets/krw/tickers")

        # 상태 코드 검증
        assert response.status_code in [200, 503]  # 503은 네트워크 오류 시

        if response.status_code == 200:
            data = response.json()
            # 기본 구조 검증
            assert "tickers" in data
            assert "count" in data
            assert isinstance(data["tickers"], list)
