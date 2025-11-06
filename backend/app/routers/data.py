"""
Data Management API Router

데이터 인벤토리 조회 및 파일 업로드를 담당하는 API 엔드포인트입니다.

파일 구조: DATA_ROOT/{symbol}/{timeframe}/{year}.parquet
예시: /data/BTC_KRW/1D/2024.parquet
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple
from datetime import datetime
import os
import logging
from pathlib import Path
import re
import tempfile
import shutil
try:
    import pyarrow.parquet as pq
except ImportError:
    pq = None

logger = logging.getLogger(__name__)

# 환경변수
DATA_ROOT = os.getenv("DATA_ROOT", "/data")

router = APIRouter(prefix="/api/data", tags=["data"])

# ============================================================================
# Pydantic 모델
# ============================================================================


class DataFileInfo(BaseModel):
    """데이터 파일 정보"""
    symbol: str = Field(..., description="심볼 (예: BTC_KRW)")
    timeframe: str = Field(..., description="타임프레임 (예: 1D, 1H, 5M)")
    year: int = Field(..., description="연도 (예: 2024)")
    relative_path: str = Field(..., description="상대 경로 (절대 경로 비노출)")
    size_bytes: int = Field(..., description="파일 크기 (바이트)")
    modified_at: str = Field(..., description="수정일 (ISO 8601)")


class InventoryResponse(BaseModel):
    """인벤토리 조회 응답"""
    files: List[DataFileInfo] = Field(default_factory=list, description="파일 목록")
    total_count: int = Field(..., description="전체 파일 수")
    limit: int = Field(..., description="조회 limit")
    offset: int = Field(..., description="조회 offset")


class UploadResponse(BaseModel):
    """파일 업로드 응답"""
    success: bool = Field(..., description="업로드 성공 여부")
    message: str = Field(..., description="응답 메시지")
    file_path: Optional[str] = Field(None, description="저장된 상대 경로")


# ============================================================================
# 헬퍼 함수
# ============================================================================

# 정규식 패턴 정의
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9_]+$")  # 대문자, 숫자, 언더스코어
TIMEFRAME_PATTERN = re.compile(r"^[A-Z0-9_]+$")  # 대문자, 숫자, 언더스코어
YEAR_PATTERN = re.compile(r"^\d{4}$")  # 4자리 숫자

# 파일 크기 제한 (200MB)
MAX_FILE_SIZE = 200 * 1024 * 1024

# 필수 컬럼
REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume", "timestamp"}


def _validate_input(
    symbol: str, timeframe: str, year: int
) -> Tuple[bool, Optional[str]]:
    """
    입력값 검증 (화이트리스트 정규식)

    Args:
        symbol: 심볼 (예: BTC_KRW)
        timeframe: 타임프레임 (예: 1D)
        year: 연도 (예: 2024)

    Returns:
        (유효 여부, 에러 메시지) 튜플
    """
    # 심볼 검증
    if not symbol or len(symbol) > 20:
        return False, "심볼은 1~20자 사이여야 합니다"

    symbol_upper = symbol.upper()
    if not SYMBOL_PATTERN.match(symbol_upper):
        return False, "심볼은 대문자, 숫자, 언더스코어만 포함해야 합니다"

    # 타임프레임 검증
    if not timeframe or len(timeframe) > 10:
        return False, "타임프레임은 1~10자 사이여야 합니다"

    timeframe_upper = timeframe.upper()
    if not TIMEFRAME_PATTERN.match(timeframe_upper):
        return False, "타임프레임은 대문자, 숫자, 언더스코어만 포함해야 합니다"

    # 연도 검증
    if not YEAR_PATTERN.match(str(year)):
        return False, "연도는 4자리 숫자여야 합니다 (예: 2024)"

    return True, None


def _validate_parquet_file(file_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Parquet 파일 검증

    Args:
        file_path: 파일 경로

    Returns:
        (유효 여부, 에러 메시지) 튜플
    """
    # 확장자 검증
    if file_path.suffix.lower() != ".parquet":
        return False, "파일 확장자는 .parquet이어야 합니다"

    # 파일 크기 검증
    file_size = file_path.stat().st_size
    if file_size > MAX_FILE_SIZE:
        return False, f"파일 크기가 {MAX_FILE_SIZE / 1024 / 1024:.0f}MB를 초과합니다"

    # Parquet 메타데이터 검증
    if pq is None:
        logger.warning("PyArrow not available, skipping column validation")
        return True, None

    try:
        # Parquet 파일의 스키마만 읽기 (전체 데이터 읽지 않음)
        parquet_file = pq.ParquetFile(file_path)
        column_names = set(parquet_file.schema.names)

        # 필수 컬럼 확인
        missing_columns = REQUIRED_COLUMNS - column_names
        if missing_columns:
            return (
                False,
                f"필수 컬럼 누락: {', '.join(sorted(missing_columns))}",
            )

        return True, None

    except Exception as e:
        logger.error(f"Parquet validation failed: {e}")
        return False, f"Parquet 파일 검증 실패: {str(e)}"


def _save_uploaded_file(
    file_content: bytes,
    symbol: str,
    timeframe: str,
    year: int,
    overwrite: bool = False,
) -> Tuple[bool, str, Optional[str]]:
    """
    업로드된 파일을 저장합니다.

    Args:
        file_content: 파일 내용 (바이트)
        symbol: 심볼
        timeframe: 타임프레임
        year: 연도
        overwrite: 기존 파일 덮어쓰기 여부

    Returns:
        (성공 여부, 메시지, 상대 경로) 튜플
    """
    # 입력값 검증
    valid, error_msg = _validate_input(symbol, timeframe, year)
    if not valid:
        return False, error_msg, None

    # 대문자 정규화
    symbol_upper = symbol.upper()
    timeframe_upper = timeframe.upper()

    # 목표 경로 계산
    target_path = Path(DATA_ROOT) / symbol_upper / timeframe_upper / f"{year}.parquet"

    # 경로 이탈 방지 (os.path.normpath + 루트 경로 비교)
    try:
        normalized_target = os.path.normpath(target_path)
        normalized_root = os.path.normpath(Path(DATA_ROOT))

        # 정규화된 경로가 DATA_ROOT 아래인지 확인
        if not normalized_target.startswith(normalized_root + os.sep) and normalized_target != normalized_root:
            return False, "경로 이탈 시도가 감지되었습니다", None
    except Exception as e:
        logger.error(f"Path validation failed: {e}")
        return False, "경로 검증 실패", None

    # 파일이 이미 존재하는지 확인
    if target_path.exists() and not overwrite:
        return False, "파일이 이미 존재합니다. overwrite=true를 설정하세요", None

    # 임시 파일에 저장
    temp_dir = tempfile.gettempdir()
    temp_file = Path(temp_dir) / f"upload_{os.urandom(8).hex()}.parquet"

    try:
        # 임시 파일에 데이터 저장
        temp_file.write_bytes(file_content)

        # Parquet 파일 검증
        valid, error_msg = _validate_parquet_file(temp_file)
        if not valid:
            temp_file.unlink()  # 임시 파일 삭제
            return False, error_msg, None

        # 대상 디렉토리 생성
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # 원자적 이동 (임시 파일 → 최종 위치)
        os.replace(temp_file, target_path)

        # 상대 경로 반환
        relative_path = f"{symbol_upper}/{timeframe_upper}/{year}.parquet"
        logger.info(f"File saved successfully: {relative_path}")

        return True, "파일이 성공적으로 업로드되었습니다", relative_path

    except Exception as e:
        logger.error(f"File save failed: {e}")
        # 임시 파일이 존재하면 삭제
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup temp file: {cleanup_error}")

        return False, f"파일 저장 실패: {str(e)}", None


def build_inventory(
    symbol_filter: Optional[str] = None,
    timeframe_filter: Optional[str] = None,
    year_filter: Optional[int] = None,
) -> Tuple[List[DataFileInfo], int]:
    """
    DATA_ROOT 디렉토리를 스캔하여 데이터 파일 목록을 생성합니다.

    파일 구조: DATA_ROOT/{symbol}/{timeframe}/{year}.parquet

    Args:
        symbol_filter: 심볼 필터 (선택사항)
        timeframe_filter: 타임프레임 필터 (선택사항)
        year_filter: 연도 필터 (선택사항)

    Returns:
        (파일 정보 목록, 전체 파일 수) 튜플
        최근 수정일 내림차순으로 정렬됨

    Raises:
        HTTPException: DATA_ROOT가 없거나 읽기 불가
    """
    data_root_path = Path(DATA_ROOT)

    if not data_root_path.exists():
        logger.warning(f"DATA_ROOT not found: {DATA_ROOT}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DATA_ROOT directory not found: {DATA_ROOT}",
        )

    files: List[DataFileInfo] = []

    try:
        # DATA_ROOT 디렉토리 탐색
        for symbol_dir in data_root_path.iterdir():
            if not symbol_dir.is_dir():
                continue

            symbol = symbol_dir.name.upper()

            # 심볼 필터 확인
            if symbol_filter and symbol != symbol_filter.upper():
                continue

            # timeframe 디렉토리 탐색
            for timeframe_dir in symbol_dir.iterdir():
                if not timeframe_dir.is_dir():
                    continue

                timeframe = timeframe_dir.name.upper()

                # 타임프레임 필터 확인
                if timeframe_filter and timeframe != timeframe_filter.upper():
                    continue

                # parquet 파일 탐색
                for file_path in timeframe_dir.glob("*.parquet"):
                    if not file_path.is_file():
                        continue

                    # 파일명에서 연도 추출 (예: 2024.parquet → 2024)
                    try:
                        year = int(file_path.stem)
                    except ValueError:
                        logger.warning(f"Invalid filename format: {file_path.name}")
                        continue

                    # 연도 필터 확인
                    if year_filter and year != year_filter:
                        continue

                    # 상대 경로 생성 (절대 경로 비노출)
                    relative_path = f"{symbol}/{timeframe}/{year}.parquet"

                    # 파일 메타데이터 수집
                    stat_info = file_path.stat()
                    size_bytes = stat_info.st_size
                    modified_at = datetime.fromtimestamp(stat_info.st_mtime).isoformat()

                    files.append(
                        DataFileInfo(
                            symbol=symbol,
                            timeframe=timeframe,
                            year=year,
                            relative_path=relative_path,
                            size_bytes=size_bytes,
                            modified_at=modified_at,
                        )
                    )

    except PermissionError as e:
        logger.error(f"Permission denied reading DATA_ROOT: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied reading DATA_ROOT: {DATA_ROOT}",
        )
    except Exception as e:
        logger.error(f"Error scanning DATA_ROOT: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error scanning DATA_ROOT: {str(e)}",
        )

    # 최근 수정일 내림차순 정렬
    files.sort(key=lambda f: f.modified_at, reverse=True)

    total_count = len(files)
    logger.info(
        f"Built inventory: total={total_count}, "
        f"symbol_filter={symbol_filter}, "
        f"timeframe_filter={timeframe_filter}, "
        f"year_filter={year_filter}"
    )

    return files, total_count


# ============================================================================
# 엔드포인트
# ============================================================================


@router.get("/inventory", response_model=InventoryResponse)
async def get_inventory(
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    데이터 파일 인벤토리 조회

    Args:
        symbol: 심볼 필터 (선택사항, 예: BTC_KRW)
        timeframe: 타임프레임 필터 (선택사항, 예: 1D)
        year: 연도 필터 (선택사항, 예: 2024)
        limit: 조회 수 제한 (기본값: 50, 최대: 200)
        offset: 오프셋 (기본값: 0)

    Returns:
        InventoryResponse: 파일 목록 및 페이지네이션 정보

    Raises:
        HTTPException: 데이터 루트 디렉토리 없음
    """
    # limit 최대값 제한
    limit = min(limit, 200)

    logger.info(
        f"Getting inventory: symbol={symbol}, timeframe={timeframe}, "
        f"year={year}, limit={limit}, offset={offset}"
    )

    # 전체 파일 목록 조회
    all_files, total_count = build_inventory(symbol, timeframe, year)

    # 페이지네이션 적용
    paginated_files = all_files[offset : offset + limit]

    return InventoryResponse(
        files=paginated_files,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    symbol: str = Form(...),
    timeframe: str = Form(...),
    year: int = Form(...),
    overwrite: bool = Form(False),
):
    """
    파일 업로드 엔드포인트

    Args:
        file: 업로드할 Parquet 파일
        symbol: 심볼 (예: BTC_KRW, 자동으로 대문자 정규화)
        timeframe: 타임프레임 (예: 1D, 자동으로 대문자 정규화)
        year: 연도 (예: 2024)
        overwrite: 기존 파일 덮어쓰기 여부 (기본값: False)

    Returns:
        UploadResponse: 업로드 결과

    Raises:
        HTTPException(400): 입력값 검증 실패
        HTTPException(409): 파일 이미 존재 (overwrite=False)
        HTTPException(413): 파일 크기 초과
        HTTPException(415): 지원하지 않는 파일 형식
        HTTPException(422): 필수 컬럼 누락
        HTTPException(500): 서버 오류
    """
    logger.info(
        f"Uploading file: filename={file.filename}, symbol={symbol}, "
        f"timeframe={timeframe}, year={year}, overwrite={overwrite}"
    )

    try:
        # 파일 내용 읽기
        file_content = await file.read()

        # 파일 저장
        success, message, relative_path = _save_uploaded_file(
            file_content=file_content,
            symbol=symbol,
            timeframe=timeframe,
            year=year,
            overwrite=overwrite,
        )

        # 응답 상태 코드 결정
        if success:
            status_code = status.HTTP_200_OK
        elif "이미 존재" in message:
            # 파일이 이미 존재하는 경우
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=message,
            )
        elif "크기" in message or "대문자" in message or "숫자" in message or "자리" in message:
            # 입력값 검증 실패
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message,
            )
        elif "확장자" in message or "Parquet" in message or "컬럼" in message:
            # 파일 형식 또는 스키마 오류
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=message,
            )
        else:
            # 기타 오류
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message,
            )

        logger.info(f"File uploaded successfully: {relative_path}")

        return UploadResponse(
            success=True,
            message=message,
            file_path=relative_path,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during file upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"파일 업로드 중 오류 발생: {str(e)}",
        )
