"""
마켓 데이터 API Router (Feature Breakdown #23)

업비트 KRW 마켓의 전체 종목 정보 및 실시간 시세를 제공하는 API 엔드포인트입니다.

Task 1: GET /api/markets/krw - 업비트 KRW 마켓 전체 종목 목록 조회
Task 2: GET /api/tickers/krw - 실시간 시세 조회
Task 7: WS /ws/tickers/krw - WebSocket 실시간 시세 스트림 (업비트 중계)
"""

from fastapi import APIRouter, HTTPException, status, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
import logging
import httpx
import asyncio
import json
import websockets
from functools import lru_cache

# Redis import (캐싱용)
try:
    from redis import Redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/markets", tags=["markets"])

# ============================================================================
# 상수 및 설정
# ============================================================================

UPBIT_API_BASE = "https://api.upbit.com/v1"
MARKET_LIST_ENDPOINT = f"{UPBIT_API_BASE}/market/all"
TICKER_ENDPOINT = f"{UPBIT_API_BASE}/ticker"

# 캐싱 설정
MARKET_CACHE_KEY = "markets:krw"
MARKET_CACHE_TTL = 3600  # 1시간
TICKER_CACHE_KEY = "tickers:krw"
TICKER_CACHE_TTL = 3  # 3초

# 최소 KRW 마켓 수 (설정값으로 관리)
MIN_KRW_MARKETS = 80  # 업비트 실제 수량이 변할 수 있으므로 설정값으로 관리

# Redis 클라이언트
redis_client: Optional[Redis] = None

# HTTP 클라이언트 (비동기)
http_client: Optional[httpx.AsyncClient] = None


# ============================================================================
# Pydantic 모델
# ============================================================================

class MarketInfo(BaseModel):
    """마켓 정보"""
    market: str = Field(..., description="마켓 코드 (예: KRW-BTC)")
    korean_name: str = Field(..., description="한글명 (예: 비트코인)")
    english_name: str = Field(..., description="영문명 (예: Bitcoin)")


class TickerInfo(BaseModel):
    """실시간 시세 정보"""
    market: str = Field(..., description="마켓 코드 (예: KRW-BTC)")
    trade_price: float = Field(..., description="현재가")
    change_rate: float = Field(..., description="등락률 (소수점, 예: 0.05 = 5%)")
    acc_trade_volume_24h: float = Field(..., description="24시간 거래량")
    acc_trade_price_24h: float = Field(..., description="24시간 거래대금")


class MarketListResponse(BaseModel):
    """마켓 목록 응답"""
    markets: List[MarketInfo] = Field(..., description="마켓 목록")
    count: int = Field(..., description="마켓 개수")
    last_updated: str = Field(..., description="마지막 업데이트 시간 (ISO 8601)")


class TickerListResponse(BaseModel):
    """시세 목록 응답"""
    tickers: List[TickerInfo] = Field(..., description="시세 목록")
    count: int = Field(..., description="시세 개수")
    last_updated: str = Field(..., description="마지막 업데이트 시간 (ISO 8601)")


# ============================================================================
# 초기화 및 정리
# ============================================================================

async def init_redis():
    """Redis 클라이언트 초기화"""
    global redis_client
    if HAS_REDIS and redis_client is None:
        try:
            redis_client = Redis(
                host="localhost",
                port=6379,
                db=0,
                decode_responses=True,
                socket_keepalive=True
            )
            # 연결 테스트
            redis_client.ping()
            logger.info("Redis client initialized for markets API")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis: {e}")
            redis_client = None


async def init_http_client():
    """HTTP 클라이언트 초기화"""
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=10.0)
        logger.info("HTTP client initialized for markets API")


async def close_http_client():
    """HTTP 클라이언트 정리"""
    global http_client
    if http_client:
        await http_client.aclose()
        http_client = None
        logger.info("HTTP client closed")


# ============================================================================
# Upbit API 호출 함수
# ============================================================================

async def fetch_krw_markets_from_upbit() -> List[Dict[str, str]]:
    """
    업비트 REST API에서 KRW 마켓 목록 조회

    Returns:
        KRW 마켓 목록 (market, korean_name, english_name)

    Raises:
        HTTPException: API 호출 실패 시
    """
    global http_client

    try:
        await init_http_client()

        logger.info("Fetching KRW markets from Upbit API")
        response = await http_client.get(MARKET_LIST_ENDPOINT)
        response.raise_for_status()

        data = response.json()

        # KRW 마켓만 필터링
        krw_markets = [
            {
                "market": item["market"],
                "korean_name": item.get("korean_name", ""),
                "english_name": item.get("english_name", "")
            }
            for item in data
            if item.get("market", "").startswith("KRW-")
        ]

        logger.info(f"Fetched {len(krw_markets)} KRW markets from Upbit API")

        if len(krw_markets) < MIN_KRW_MARKETS:
            logger.warning(
                f"Number of KRW markets ({len(krw_markets)}) is less than "
                f"minimum threshold ({MIN_KRW_MARKETS})"
            )

        return krw_markets

    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching markets: {e}")
        raise
    except Exception as e:
        logger.error(f"Error fetching markets from Upbit: {e}")
        raise


async def fetch_krw_tickers_from_upbit(markets: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    업비트 REST API에서 KRW 마켓의 실시간 시세 조회

    Args:
        markets: 마켓 목록 (market 필드 포함)

    Returns:
        실시간 시세 정보 목록

    Raises:
        HTTPException: API 호출 실패 시
    """
    global http_client

    try:
        await init_http_client()

        if not markets:
            return []

        # 마켓 코드 추출
        market_codes = [m["market"] for m in markets]

        # Upbit API는 한 번에 최대 100개 마켓만 조회 가능
        tickers = []
        batch_size = 100

        for i in range(0, len(market_codes), batch_size):
            batch = market_codes[i:i+batch_size]
            markets_param = ",".join(batch)

            logger.info(f"Fetching tickers for batch {i//batch_size + 1} ({len(batch)} markets)")

            try:
                response = await http_client.get(
                    TICKER_ENDPOINT,
                    params={"markets": markets_param}
                )
                response.raise_for_status()

                data = response.json()
                tickers.extend(data)

                # Rate limit 준수: 초당 10회 정도로 제한
                if i + batch_size < len(market_codes):
                    await asyncio.sleep(0.5)

            except httpx.HTTPError as e:
                logger.error(f"HTTP error fetching tickers for batch: {e}")
                # 배치 실패해도 계속 진행 (부분 실패 허용)
                continue

        logger.info(f"Fetched {len(tickers)} tickers from Upbit API")

        return tickers

    except Exception as e:
        logger.error(f"Error fetching tickers from Upbit: {e}")
        raise


# ============================================================================
# 캐싱 함수
# ============================================================================

async def get_cached_markets() -> Optional[List[Dict[str, str]]]:
    """Redis에서 캐시된 마켓 목록 조회"""
    if not redis_client:
        return None

    try:
        data = redis_client.get(MARKET_CACHE_KEY)
        if data:
            logger.info("Markets retrieved from cache")
            import json
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Error retrieving markets from cache: {e}")

    return None


async def cache_markets(markets: List[Dict[str, str]]) -> None:
    """마켓 목록을 Redis에 캐시"""
    if not redis_client:
        return

    try:
        import json
        redis_client.setex(
            MARKET_CACHE_KEY,
            MARKET_CACHE_TTL,
            json.dumps(markets)
        )
        logger.info(f"Markets cached for {MARKET_CACHE_TTL}s")
    except Exception as e:
        logger.warning(f"Error caching markets: {e}")


async def get_cached_tickers() -> Optional[List[Dict[str, Any]]]:
    """Redis에서 캐시된 시세 목록 조회"""
    if not redis_client:
        return None

    try:
        data = redis_client.get(TICKER_CACHE_KEY)
        if data:
            logger.info("Tickers retrieved from cache")
            import json
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Error retrieving tickers from cache: {e}")

    return None


async def cache_tickers(tickers: List[Dict[str, Any]]) -> None:
    """시세 목록을 Redis에 캐시"""
    if not redis_client:
        return

    try:
        import json
        redis_client.setex(
            TICKER_CACHE_KEY,
            TICKER_CACHE_TTL,
            json.dumps(tickers)
        )
        logger.info(f"Tickers cached for {TICKER_CACHE_TTL}s")
    except Exception as e:
        logger.warning(f"Error caching tickers: {e}")


# ============================================================================
# API 엔드포인트
# ============================================================================

@router.on_event("startup")
async def startup_event():
    """라우터 시작 이벤트"""
    await init_redis()
    await init_http_client()


@router.on_event("shutdown")
async def shutdown_event():
    """라우터 종료 이벤트"""
    await close_http_client()


@router.get(
    "/krw",
    response_model=MarketListResponse,
    status_code=status.HTTP_200_OK,
    summary="KRW 마켓 목록 조회",
    description="업비트 KRW 마켓의 전체 종목 목록을 조회합니다. (캐시: 1시간)"
)
async def get_krw_markets():
    """
    Task 1: 업비트 KRW 마켓 전체 종목 목록 조회

    업비트 REST API `/v1/market/all`을 호출하여 KRW 마켓 전체 종목 목록을 반환합니다.
    1시간 캐싱으로 성능을 향상시킵니다.

    Returns:
        MarketListResponse: 마켓 목록 및 메타데이터

    Raises:
        HTTPException:
            - 503: API 호출 실패 또는 캐시 데이터도 없음
    """
    try:
        await init_redis()

        # 1. 캐시에서 조회
        cached_markets = await get_cached_markets()
        if cached_markets:
            return MarketListResponse(
                markets=[MarketInfo(**m) for m in cached_markets],
                count=len(cached_markets),
                last_updated=datetime.now().isoformat()
            )

        # 2. 캐시 미스: Upbit API에서 조회
        logger.info("Cache miss: fetching markets from Upbit API")
        markets = await fetch_krw_markets_from_upbit()

        # 3. 결과 캐시
        await cache_markets(markets)

        # 4. 응답 반환
        return MarketListResponse(
            markets=[MarketInfo(**m) for m in markets],
            count=len(markets),
            last_updated=datetime.now().isoformat()
        )

    except httpx.HTTPError as e:
        logger.error(f"HTTP error in get_krw_markets: {e}")

        # Upbit API 장애 시 캐시된 데이터 반환
        try:
            cached_markets = await get_cached_markets()
            if cached_markets:
                logger.info("Upbit API failed, returning cached markets")
                return MarketListResponse(
                    markets=[MarketInfo(**m) for m in cached_markets],
                    count=len(cached_markets),
                    last_updated=datetime.now().isoformat()
                )
        except Exception as cache_error:
            logger.error(f"Error retrieving cached markets: {cache_error}")

        # 캐시도 없으면 에러 반환
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upbit API unavailable and no cached data available"
        )

    except Exception as e:
        logger.error(f"Unexpected error in get_krw_markets: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve KRW markets: {str(e)}"
        )


@router.get(
    "/krw/tickers",
    response_model=TickerListResponse,
    status_code=status.HTTP_200_OK,
    summary="KRW 마켓 실시간 시세 조회",
    description="업비트 KRW 마켓의 실시간 시세를 조회합니다. (캐시: 3초)"
)
async def get_krw_tickers():
    """
    Task 2: 업비트 KRW 마켓 전체 종목 실시간 시세 조회

    업비트 REST API `/v1/ticker`를 호출하여 KRW 마켓의 실시간 시세를 반환합니다.
    3초 캐싱으로 실시간성을 유지합니다.

    Returns:
        TickerListResponse: 시세 목록 및 메타데이터

    Raises:
        HTTPException:
            - 503: API 호출 실패 또는 캐시 데이터도 없음
    """
    try:
        await init_redis()

        # 1. 캐시에서 조회
        cached_tickers = await get_cached_tickers()
        if cached_tickers:
            return TickerListResponse(
                tickers=[TickerInfo(**t) for t in cached_tickers],
                count=len(cached_tickers),
                last_updated=datetime.now().isoformat()
            )

        # 2. 캐시 미스: 마켓 목록 조회
        logger.info("Cache miss: fetching tickers from Upbit API")
        markets = await fetch_krw_markets_from_upbit()

        if not markets:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No KRW markets available"
            )

        # 3. 시세 조회
        ticker_data = await fetch_krw_tickers_from_upbit(markets)

        # 응답 포맷 변환
        tickers = []
        for ticker in ticker_data:
            try:
                tickers.append({
                    "market": ticker.get("market", ""),
                    "trade_price": float(ticker.get("trade_price", 0)),
                    "change_rate": float(ticker.get("change_rate", 0)),
                    "acc_trade_volume_24h": float(ticker.get("acc_trade_volume_24h", 0)),
                    "acc_trade_price_24h": float(ticker.get("acc_trade_price_24h", 0))
                })
            except (ValueError, KeyError) as e:
                logger.warning(f"Error parsing ticker data: {e}")
                continue

        # 4. 결과 캐시
        await cache_tickers(tickers)

        # 5. 응답 반환
        return TickerListResponse(
            tickers=[TickerInfo(**t) for t in tickers],
            count=len(tickers),
            last_updated=datetime.now().isoformat()
        )

    except httpx.HTTPError as e:
        logger.error(f"HTTP error in get_krw_tickers: {e}")

        # Upbit API 장애 시 캐시된 데이터 반환
        try:
            cached_tickers = await get_cached_tickers()
            if cached_tickers:
                logger.info("Upbit API failed, returning cached tickers")
                return TickerListResponse(
                    tickers=[TickerInfo(**t) for t in cached_tickers],
                    count=len(cached_tickers),
                    last_updated=datetime.now().isoformat()
                )
        except Exception as cache_error:
            logger.error(f"Error retrieving cached tickers: {cache_error}")

        # 캐시도 없으면 에러 반환
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upbit API unavailable and no cached data available"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_krw_tickers: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve KRW tickers: {str(e)}"
        )


# ============================================================================
# Task 7: WebSocket 실시간 시세 스트림 (선택사항)
# ============================================================================

@router.websocket("/ws/tickers/krw")
async def websocket_tickers_krw(websocket: WebSocket):
    """
    WebSocket 엔드포인트: 실시간 시세 스트림 (업비트 중계)

    연결 시:
    1. 캐시된 시세 데이터 먼저 전송
    2. 업비트 WebSocket 연결하여 실시간 데이터 중계

    메시지 형식:
    {
        "type": "ticker",
        "market": "KRW-BTC",
        "trade_price": 65000000,
        "change_rate": 0.05,
        "acc_trade_volume_24h": 1234.56,
        "acc_trade_price_24h": 80000000000
    }
    """
    await websocket.accept()
    upbit_ws = None

    try:
        logger.info(f"WebSocket client connected: {websocket.client}")

        # 1. 캐시된 시세 데이터 먼저 전송
        try:
            cached_tickers = await get_cached_tickers()
            if cached_tickers:
                logger.debug(f"Sending {len(cached_tickers)} cached tickers")
                for ticker in cached_tickers[:10]:  # 처음 10개만 전송
                    try:
                        await websocket.send_json({
                            "type": "cached",
                            "market": ticker.get("market"),
                            "trade_price": float(ticker.get("trade_price", 0)),
                            "change_rate": float(ticker.get("change_rate", 0)),
                            "acc_trade_volume_24h": float(ticker.get("acc_trade_volume_24h", 0)),
                            "acc_trade_price_24h": float(ticker.get("acc_trade_price_24h", 0))
                        })
                    except Exception as e:
                        logger.warning(f"Error sending cached ticker: {e}")
                        continue

                # 캐시 완료 신호
                await websocket.send_json({"type": "cached_complete"})
        except Exception as e:
            logger.warning(f"Error sending cached data: {e}")

        # 2. 업비트 KRW 마켓 목록 조회
        markets = await get_krw_markets_for_websocket()
        if not markets:
            logger.error("No markets available for WebSocket")
            await websocket.send_json({"type": "error", "message": "No markets available"})
            return

        market_codes = [m["market"] for m in markets]
        logger.info(f"Connecting to Upbit WebSocket with {len(market_codes)} markets")

        # 3. 업비트 WebSocket 연결
        async with websockets.connect("wss://api.upbit.com/websocket/v1") as upbit_ws:
            # 3-1. 구독 메시지 전송
            subscription_message = [
                {"ticket": "unique-ticket"},
                {
                    "type": "ticker",
                    "codes": market_codes,
                    "isOnlyRealtime": True
                }
            ]

            await upbit_ws.send(json.dumps(subscription_message))
            logger.info("Subscription message sent to Upbit WebSocket")

            # 3-2. 업비트에서 메시지 수신 및 클라이언트에 중계
            async for message in upbit_ws:
                try:
                    data = json.loads(message)

                    # 티커 데이터만 처리
                    if data.get("type") == "ticker":
                        ticker = {
                            "type": "ticker",
                            "market": data.get("code"),
                            "trade_price": float(data.get("trade_price", 0)),
                            "change_rate": float(data.get("change_rate", 0)),
                            "acc_trade_volume_24h": float(data.get("acc_trade_volume_24h", 0)),
                            "acc_trade_price_24h": float(data.get("acc_trade_price_24h", 0))
                        }

                        # 클라이언트에 전송
                        await websocket.send_json(ticker)

                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON from Upbit: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing Upbit message: {e}")
                    continue

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {websocket.client}")

    except websockets.exceptions.WebSocketException as e:
        logger.error(f"Upbit WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Connection to market data failed"
            })
        except Exception:
            pass

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except Exception:
            pass

    finally:
        # 정리
        try:
            await websocket.close()
        except Exception:
            pass

        if upbit_ws:
            await upbit_ws.close()

        logger.info(f"WebSocket connection closed: {websocket.client}")


async def get_krw_markets_for_websocket() -> List[Dict[str, str]]:
    """
    WebSocket용 KRW 마켓 목록 조회 (간단화된 버전)

    Returns:
        마켓 정보 목록
    """
    try:
        # 캐시 확인
        cached_markets = await get_cached_markets()
        if cached_markets:
            logger.debug(f"Using cached markets for WebSocket: {len(cached_markets)} items")
            return cached_markets

        # 캐시 없으면 API 호출
        logger.info("Fetching markets from Upbit API for WebSocket")
        markets = await fetch_krw_markets_from_upbit()

        if markets:
            await cache_markets(markets)

        return markets

    except Exception as e:
        logger.error(f"Error getting markets for WebSocket: {e}")
        return []
