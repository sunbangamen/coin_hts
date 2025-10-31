"""
로컬 parquet 파일에서 OHLCV 데이터를 로드하는 모듈

파일 구조: DATA_ROOT/{symbol}/{timeframe}/{year}.parquet
예시: /data/BTC_KRW/1M/2024.parquet

도메인 준수 사항:
- 입력 타임스탬프는 KST로 간주되며, 내부 처리는 UTC로 통일
- symbol, timeframe이 파일 경로에만 포함된 경우, DataFrame에 주입
- 필수 컬럼 검증: open, high, low, close, volume, timestamp
"""

import os
import logging
from datetime import datetime
from typing import List, Optional
import pandas as pd
from pathlib import Path
from fastapi import HTTPException
import pytz

logger = logging.getLogger(__name__)

# 타임존 정의
KST = pytz.timezone('Asia/Seoul')
UTC = pytz.UTC


def _normalize_timezone(date_str: str) -> pd.Timestamp:
    """
    입력 날짜 문자열을 파싱하여 UTC 기준 pd.Timestamp로 변환

    - 타임존 정보가 있으면 그대로 사용 후 UTC로 변환
    - 타임존 정보가 없으면 KST로 간주 후 UTC로 변환

    Args:
        date_str: ISO8601 형식 문자열 (예: "2024-01-01" 또는 "2024-01-01T12:00:00+09:00")

    Returns:
        UTC 기준 pd.Timestamp

    Raises:
        ValueError: 파싱 실패 시
    """
    try:
        ts = pd.to_datetime(date_str)

        # 타임존 정보가 없으면 KST로 간주
        if ts.tz is None:
            ts = ts.tz_localize(KST)

        # UTC로 변환
        return ts.tz_convert(UTC)
    except Exception as e:
        logger.error(f"Failed to parse date: {date_str}, error: {e}")
        raise ValueError(f"Invalid date format: {date_str}") from e


def _extract_years_from_range(start_date_str: str, end_date_str: str) -> List[int]:
    """
    날짜 범위에서 필요한 연도 목록 추출

    Args:
        start_date_str: 시작 날짜 (예: "2024-01-01")
        end_date_str: 종료 날짜 (예: "2024-12-31")

    Returns:
        연도 목록 (예: [2024])

    Raises:
        ValueError: 날짜 파싱 실패 시
    """
    try:
        # 원본 입력 문자열에서 연도 추출 (타임존 변환 전)
        start_ts = pd.to_datetime(start_date_str)
        end_ts = pd.to_datetime(end_date_str)

        # 타임존 변환 후 범위 검증
        start_date = _normalize_timezone(start_date_str)
        end_date = _normalize_timezone(end_date_str)

        if start_date > end_date:
            raise ValueError("start_date must be before end_date")

        # 원본 타임스탐프의 연도로 범위 생성
        years = list(range(start_ts.year, end_ts.year + 1))
        return years
    except ValueError as e:
        logger.error(f"Failed to extract years: {e}")
        raise HTTPException(status_code=422, detail=str(e))


def _validate_dataframe(df: pd.DataFrame, symbol: str, timeframe: str) -> None:
    """
    DataFrame이 필수 컬럼을 가지고 있는지 검증

    Args:
        df: 검증할 DataFrame
        symbol: 심볼명
        timeframe: 타임프레임

    Raises:
        HTTPException: 필수 컬럼 누락 시
    """
    required_columns = {'open', 'high', 'low', 'close', 'volume'}

    # timestamp는 인덱스일 수도 있으므로 별도 체크
    has_timestamp = 'timestamp' in df.columns or isinstance(df.index, pd.DatetimeIndex)

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        error_msg = f"Missing required columns in {symbol}/{timeframe}: {missing_columns}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)

    if not has_timestamp:
        error_msg = f"Missing timestamp column in {symbol}/{timeframe}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)


def load_ohlcv_data(
    symbols: List[str],
    start_date: str,
    end_date: str,
    timeframe: str = "1d",
    data_root: Optional[str] = None
) -> pd.DataFrame:
    """
    로컬 parquet 파일에서 OHLCV 데이터를 로드합니다.

    파일 구조: DATA_ROOT/{symbol}/{timeframe}/{year}.parquet

    Args:
        symbols: 조회할 심볼 목록 (예: ["BTC_KRW", "XRP_KRW"])
        start_date: 시작 날짜 (ISO8601, 예: "2024-01-01" 또는 "2024-01-01T00:00:00+09:00")
        end_date: 종료 날짜 (ISO8601, 예: "2024-12-31")
        timeframe: 타임프레임 (기본값: "1d", 예: "1M", "5M", "1H", "1D")
        data_root: 데이터 루트 디렉토리 (기본값: 환경변수 DATA_ROOT 또는 ./data)

    Returns:
        DataFrame: 컬럼 [timestamp, symbol, timeframe, open, high, low, close, volume]
                  timestamp는 UTC 기준

    Raises:
        HTTPException(422): 입력 파라미터 오류 (타임존 누락 등)
        HTTPException(404): 조회 가능한 데이터 파일이 없음
        HTTPException(400): 파일 스키마 오류 (필수 컬럼 누락)

    Examples:
        >>> df = load_ohlcv_data(
        ...     symbols=["BTC_KRW"],
        ...     start_date="2024-01-01",
        ...     end_date="2024-01-31",
        ...     timeframe="1d"
        ... )
        >>> assert all(col in df.columns for col in ["open", "high", "low", "close", "volume"])
    """
    # 데이터 루트 설정
    if data_root is None:
        data_root = os.getenv('DATA_ROOT', './data')

    data_root_path = Path(data_root)

    if not data_root_path.exists():
        error_msg = f"DATA_ROOT directory not found: {data_root_path}"
        logger.error(error_msg)
        raise HTTPException(status_code=404, detail=error_msg)

    # 날짜 범위 정규화
    try:
        start_date_utc = _normalize_timezone(start_date)
        end_date_utc = _normalize_timezone(end_date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 필요한 연도 추출
    try:
        years = _extract_years_from_range(start_date, end_date)
    except HTTPException:
        raise

    if not years:
        error_msg = "No years to process"
        logger.error(error_msg)
        raise HTTPException(status_code=422, detail=error_msg)

    # 타임프레임 정규화 (대문자)
    timeframe_upper = timeframe.upper()

    # 각 심볼별로 데이터 로드
    dfs = []
    files_loaded = 0

    for symbol in symbols:
        symbol_upper = symbol.upper()

        for year in years:
            file_path = data_root_path / symbol_upper / timeframe_upper / f"{year}.parquet"

            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                continue

            try:
                # Parquet 파일 읽기
                df = pd.read_parquet(file_path)

                # 필수 컬럼 검증
                _validate_dataframe(df, symbol_upper, timeframe_upper)

                # timestamp 컬럼 준비
                if 'timestamp' not in df.columns:
                    if isinstance(df.index, pd.DatetimeIndex):
                        df['timestamp'] = df.index
                    else:
                        error_msg = f"No timestamp column or index in {file_path}"
                        logger.error(error_msg)
                        raise HTTPException(status_code=400, detail=error_msg)

                # timestamp를 UTC로 정규화
                if df['timestamp'].dt.tz is None:
                    # 타임존 정보 없음 -> KST로 간주
                    df['timestamp'] = df['timestamp'].dt.tz_localize(KST).dt.tz_convert(UTC)
                else:
                    # 타임존 정보 있음 -> UTC로 변환
                    df['timestamp'] = df['timestamp'].dt.tz_convert(UTC)

                # symbol과 timeframe 주입 (파일 경로에서만 정보 있는 경우)
                if 'symbol' not in df.columns:
                    df['symbol'] = symbol_upper
                if 'timeframe' not in df.columns:
                    df['timeframe'] = timeframe_upper

                # 날짜 범위 필터링
                df = df[(df['timestamp'] >= start_date_utc) & (df['timestamp'] <= end_date_utc)]

                if not df.empty:
                    dfs.append(df)
                    files_loaded += 1
                    logger.info(f"Loaded {file_path}: {len(df)} rows")

            except HTTPException:
                raise
            except Exception as e:
                error_msg = f"Failed to read {file_path}: {e}"
                logger.error(error_msg)
                raise HTTPException(status_code=400, detail=error_msg)

    # 데이터 병합
    if not dfs:
        error_msg = f"No data found for symbols {symbols} in range {start_date} ~ {end_date}"
        logger.warning(error_msg)
        raise HTTPException(status_code=404, detail=error_msg)

    result_df = pd.concat(dfs, ignore_index=True)

    # 필수 컬럼만 선택 및 정렬
    required_cols = ['timestamp', 'symbol', 'timeframe', 'open', 'high', 'low', 'close', 'volume']
    available_cols = [col for col in required_cols if col in result_df.columns]
    result_df = result_df[available_cols].sort_values('timestamp').reset_index(drop=True)

    logger.info(f"Loaded {files_loaded} files, total {len(result_df)} rows")

    return result_df
