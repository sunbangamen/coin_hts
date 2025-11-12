"""
조건 검색 API Router (Feature Breakdown #23, Task 5)

HTS 스타일의 조건 검색으로 매매 기회를 찾는 API 엔드포인트입니다.

개선 사항:
- 서비스 계층 활용 (심볼 변환, 데이터 로딩, 캐싱)
- 병렬 처리로 성능 향상
- Graceful degradation (폴백 로직)
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal
from datetime import datetime
import logging

from backend.app.services.screener_service import ScreenerService, init_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/screener", tags=["screener"])

# ============================================================================
# 라우터 이벤트 (Redis 초기화)
# ============================================================================

@router.on_event("startup")
async def startup_event():
    """라우터 시작 시 Redis 초기화"""
    logger.info("Initializing Redis for screener service")
    await init_redis()

# ============================================================================
# 싱글톤 서비스 인스턴스
# ============================================================================

_screener_service: Optional[ScreenerService] = None


def get_screener_service() -> ScreenerService:
    """스크리너 서비스 싱글톤 인스턴스 획득"""
    global _screener_service
    if _screener_service is None:
        _screener_service = ScreenerService()
    return _screener_service


# ============================================================================
# Pydantic 모델
# ============================================================================

class ScreenerCondition(BaseModel):
    """검색 조건"""
    type: Literal[
        'change_rate',
        'volume',
        'trade_amount',
        'ma_divergence',
        'ma_alignment'
    ] = Field(..., description="조건 타입")
    operator: Optional[Literal['>', '<', '>=', '<=', '==']] = Field(
        default='>',
        description="연산자 (기본: '>')"
    )
    value: Optional[float] = Field(
        default=None,
        description="조건값 (예: 5, 1000, 등)"
    )
    period: Optional[Literal['1D', '1W', '1M']] = Field(
        default='1D',
        description="기간 (기본: 1D)"
    )
    ma_periods: Optional[List[int]] = Field(
        default=None,
        description="이동평균선 기간 목록 (기본: [5, 20, 60])"
    )


class ScreenerRequest(BaseModel):
    """조건 검색 요청"""
    conditions: List[ScreenerCondition] = Field(
        ...,
        description="검색 조건 목록 (최대 5개)",
        min_items=1,
        max_items=5
    )
    logic: Literal['AND', 'OR'] = Field(
        default='AND',
        description="조건 논리 연산자 (기본: AND)"
    )


class ScreenerResponse(BaseModel):
    """조건 검색 응답"""
    matched_markets: List[str] = Field(..., description="매칭된 종목 목록 (마켓 코드)")
    total_count: int = Field(..., description="매칭된 종목 개수")
    conditions_applied: List[Dict[str, Any]] = Field(..., description="적용된 조건")
    timestamp: str = Field(..., description="검색 실행 시간 (ISO 8601)")


class AvailableSymbolsResponse(BaseModel):
    """검색 가능한 심볼 목록"""
    symbols: List[str] = Field(..., description="심볼 목록")
    count: int = Field(..., description="심볼 개수")


# ============================================================================
# API 엔드포인트
# ============================================================================

@router.post(
    "/filter",
    response_model=ScreenerResponse,
    status_code=status.HTTP_200_OK,
    summary="HTS 스타일 조건 검색",
    description="사용자가 지정한 조건에 맞는 종목을 필터링합니다. (캐시: 60초)"
)
async def screener_filter(request: ScreenerRequest):
    """
    Task 5: HTS 스타일 조건 검색 (개선 버전)

    사용자가 지정한 조건(상승률, 거래량, MA 정배열 등)에 맞는 종목을 필터링합니다.
    전체 KRW 마켓을 대상으로 병렬 처리하여 조건을 평가합니다.

    Args:
        request: 검색 요청
            - conditions: 검색 조건 목록 (최대 5개)
            - logic: 'AND' 또는 'OR'

    Returns:
        ScreenerResponse: 매칭된 종목 목록 및 메타데이터

    Example request:
        ```json
        {
            "conditions": [
                {
                    "type": "change_rate",
                    "operator": ">",
                    "value": 5,
                    "period": "1D"
                },
                {
                    "type": "volume",
                    "operator": ">",
                    "value": 1000,
                    "period": "1D"
                }
            ],
            "logic": "AND"
        }
        ```

    Raises:
        HTTPException:
            - 400: 조건 검증 실패 (조건 5개 초과 등)
            - 500: 검색 실행 실패
    """
    try:
        # 조건 검증
        if len(request.conditions) > 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 5 conditions allowed"
            )

        logger.info(
            f"Starting screener filter: {len(request.conditions)} conditions, "
            f"logic: {request.logic}"
        )

        # 서비스 획득
        service = get_screener_service()

        # 조건 딕셔너리로 변환 (서비스 호출용)
        conditions = [c.dict() for c in request.conditions]

        # 필터링 실행 (서비스가 KRW 마켓을 자동으로 가져옴)
        matched = await service.filter_symbols(
            conditions=conditions,
            symbols=None,  # None이면 전체 마켓 사용
            logic=request.logic
        )

        logger.info(f"Screener filter completed: {len(matched)} matches")

        return ScreenerResponse(
            matched_markets=matched,
            total_count=len(matched),
            conditions_applied=conditions,
            timestamp=datetime.now().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in screener_filter: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Screening failed: {str(e)}"
        )


@router.get(
    "/symbols",
    response_model=AvailableSymbolsResponse,
    status_code=status.HTTP_200_OK,
    summary="검색 가능한 심볼 목록",
    description="조건 검색에 사용 가능한 모든 종목 목록을 조회합니다."
)
async def get_available_symbols():
    """
    검색 가능한 심볼 목록 조회

    KRW 마켓의 모든 종목을 반환합니다.
    내부적으로 /api/markets/krw 캐시를 재활용합니다.

    Returns:
        AvailableSymbolsResponse: 심볼 목록 및 개수

    Raises:
        HTTPException: 심볼 목록 조회 실패 (네트워크 오류 등)
    """
    try:
        service = get_screener_service()
        symbols = await service.get_available_symbols()

        logger.info(f"Available symbols: {len(symbols)}")

        return AvailableSymbolsResponse(
            symbols=symbols,
            count=len(symbols)
        )

    except Exception as e:
        logger.error(f"Error getting available symbols: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve available symbols: {str(e)}"
        )
