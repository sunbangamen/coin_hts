#!/usr/bin/env python3
"""
Upbit 캔들 데이터 수집 스크립트 (개선 버전)

개선사항:
  - Upbit REST API 엔드포인트 정확한 구현
  - Rate limit 준수 (분당 600, 초당 10)
  - 최대 count=200 제한 처리
  - UTC/KST 시간대 일관성
  - 절대경로 처리
  - 상세한 에러 로깅

사용법:
  python scripts/fetch_upbit_candles.py --symbol KRW-BTC --timeframe 1H --days 7
"""

import requests
import pandas as pd
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional, List, Dict, Tuple
import time

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Upbit API 설정
UPBIT_CANDLES_URL = "https://api.upbit.com/v1/candles"

# 타임프레임 매핑 (Upbit API 규격)
# Upbit API: 1H = /candles/minutes/60, 4H = /candles/minutes/240
TIMEFRAME_CONFIG = {
    # minutes: (unit_type, minutes_value, endpoint_suffix)
    '1M': ('minutes', 1, 1),
    '5M': ('minutes', 5, 5),
    '10M': ('minutes', 10, 10),
    '15M': ('minutes', 15, 15),
    '30M': ('minutes', 30, 30),
    # hours (represented as minutes in Upbit API)
    '1H': ('minutes', 60, 60),
    '4H': ('minutes', 240, 240),
    # days
    '1D': ('days', 1, None),
    # weeks
    '1W': ('weeks', 1, None),
    # months
    '1Mo': ('months', 1, None),
}

# 데이터 저장 경로
DATA_ROOT = os.getenv('DATA_ROOT', '/data')

# Rate limiting
REQUEST_DELAY = 0.12  # 초당 10개 요청 제한 (10개/초 = 0.1초 간격)
MAX_REQUESTS_PER_MINUTE = 600
BATCH_SIZE = 200  # Upbit API 최대 캔들 수


def parse_datetime(dt_str: str) -> datetime:
    """
    문자열을 datetime으로 안전하게 파싱

    Upbit는 ISO 8601 형식을 사용하며, candle_date_time_utc는 naive datetime이므로
    UTC로 명시적으로 설정
    """
    if not dt_str:
        return None

    try:
        # Z를 +00:00으로 변경하여 파싱
        dt_str_with_tz = dt_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(dt_str_with_tz)

        # Naive datetime인 경우 UTC로 설정
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    except (ValueError, TypeError):
        logger.warning(f"DateTime 파싱 실패: {dt_str}")
        return None


def fetch_upbit_candles(
    symbol: str,
    timeframe: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Upbit에서 캔들 데이터 수집 (Upbit API 규격에 맞게 재구현)

    Args:
        symbol: 심볼 (예: KRW-BTC)
        timeframe: 타임프레임 (1M, 5M, 1H, 1D, 1W)
        start_date: 시작 날짜 (UTC)
        end_date: 종료 날짜 (UTC)

    Returns:
        캔들 데이터 DataFrame
    """
    if timeframe not in TIMEFRAME_CONFIG:
        raise ValueError(f"지원하지 않는 타임프레임: {timeframe}")

    if not start_date:
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
    if not end_date:
        end_date = datetime.now(timezone.utc)

    # UTC 시간대로 정규화
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)

    logger.info(f"수집 시작: {symbol} {timeframe}")
    logger.info(f"  기간: {start_date.date()} ~ {end_date.date()}")

    unit_type, unit_value, unit_suffix = TIMEFRAME_CONFIG[timeframe]
    all_candles = []
    current_to = end_date
    request_count = 0
    request_time = datetime.now()
    minute_start = datetime.now()
    requests_per_minute = 0

    while current_to > start_date:
        try:
            # Rate limit 체크 및 대기
            request_count += 1
            now = datetime.now()
            elapsed = (now - request_time).total_seconds()

            # 초당 10개 제한: 0.12초마다 1개
            if elapsed < REQUEST_DELAY:
                sleep_time = REQUEST_DELAY - elapsed
                time.sleep(sleep_time)
                elapsed = REQUEST_DELAY

            # 분당 600회 제한 체크
            minute_elapsed = (now - minute_start).total_seconds()
            if minute_elapsed >= 60:
                # 1분 경과, 카운터 초기화
                requests_per_minute = 0
                minute_start = now

            requests_per_minute += 1
            if requests_per_minute >= MAX_REQUESTS_PER_MINUTE:
                # 분당 600회 도달, 대기
                wait_time = 60 - minute_elapsed
                logger.warning(f"⚠️  분당 제한(600회) 도달, {wait_time:.1f}초 대기 중...")
                time.sleep(wait_time)
                requests_per_minute = 0
                minute_start = datetime.now()

            # 엔드포인트 구성
            if unit_type == 'minutes':
                endpoint = f"{UPBIT_CANDLES_URL}/minutes/{unit_suffix}"
            elif unit_type == 'days':
                endpoint = f"{UPBIT_CANDLES_URL}/days"
            elif unit_type == 'weeks':
                endpoint = f"{UPBIT_CANDLES_URL}/weeks"
            elif unit_type == 'months':
                endpoint = f"{UPBIT_CANDLES_URL}/months"
            else:
                raise ValueError(f"Unknown unit type: {unit_type}")

            # 파라미터 구성
            params = {
                'market': symbol,
                'count': BATCH_SIZE,
                'to': current_to.isoformat(),  # ISO 8601 형식
            }

            # 상세 로깅
            logger.debug(f"  API 호출: {endpoint}")
            logger.debug(f"    Params: {params}")
            logger.debug(f"    간격: {elapsed:.3f}초, 분당 요청: {requests_per_minute}/{MAX_REQUESTS_PER_MINUTE}")

            # API 호출
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()

            # request_time 갱신
            request_time = datetime.now()

            data = response.json()
            if not data:
                logger.info(f"더 이상 데이터 없음. 수집 완료.")
                break

            # 시작 날짜보다 이전 데이터 필터링
            filtered_data = []
            for candle in data:
                candle_time = parse_datetime(candle.get('candle_date_time_utc'))
                if candle_time and candle_time > start_date:
                    filtered_data.append(candle)

            all_candles.extend(filtered_data)
            last_date = parse_datetime(data[-1].get('candle_date_time_utc')).date() if data else 'N/A'
            logger.info(f"  수집: {len(filtered_data)}개 캔들 "
                       f"({last_date} 기준, 누적: {len(all_candles)})")

            # 다음 반복을 위해 to를 조정
            if len(filtered_data) < len(data):
                # 시작 날짜에 도달함
                break

            # 마지막 데이터의 timestamp를 다음 반복의 to로 설정
            last_candle = data[-1]
            current_to = parse_datetime(last_candle.get('candle_date_time_utc'))

            # 무한 루프 방지
            if not current_to:
                logger.warning("Timestamp 파싱 실패, 수집 종료")
                break

            # 중복 방지: 1분 단위로 before 설정
            current_to = current_to - timedelta(seconds=1)

            logger.debug(f"    다음 to: {current_to.isoformat()}")

        except requests.exceptions.RequestException as e:
            logger.error(f"API 요청 실패: {e}")
            raise
        except Exception as e:
            logger.error(f"오류 발생: {e}", exc_info=True)
            raise

    if not all_candles:
        logger.warning("수집된 데이터가 없습니다.")
        return pd.DataFrame()

    # DataFrame 변환
    logger.info(f"총 {len(all_candles)}개 캔들 수집 완료")

    df = pd.DataFrame(all_candles)

    # 컬럼 정리 (필수: open, high, low, close, volume, timestamp)
    df['timestamp'] = pd.to_datetime(
        df['candle_date_time_utc'].apply(lambda x: x.replace('Z', '+00:00'))
    )
    df['open'] = df['opening_price'].astype(float)
    df['high'] = df['high_price'].astype(float)
    df['low'] = df['low_price'].astype(float)
    df['close'] = df['trade_price'].astype(float)
    df['volume'] = df['candle_acc_trade_volume'].astype(float)

    # 필요한 컬럼만 선택
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

    # 시간순으로 정렬 (오래된 순)
    df = df.sort_values('timestamp').reset_index(drop=True)

    logger.info(f"최종 데이터: {len(df)}개 행, "
               f"{df['timestamp'].min().date()} ~ {df['timestamp'].max().date()}")

    return df


def save_to_parquet_by_year(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    overwrite: bool = False,
    log_file: Optional[str] = None
) -> List[str]:
    """
    데이터를 연도별로 Parquet 파일에 저장

    Args:
        df: 저장할 DataFrame (timestamp는 UTC여야 함)
        symbol: 심볼
        timeframe: 타임프레임
        overwrite: 기존 파일 덮어쓰기 여부
        log_file: 로그 파일 경로 (선택사항)

    Returns:
        저장된 파일 경로 리스트
    """
    if df.empty:
        logger.warning("저장할 데이터가 없습니다.")
        return []

    symbol = symbol.upper()
    saved_files = []

    # timestamp가 UTC임을 명시
    if df['timestamp'].dt.tz is None:
        df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')

    # 연도별로 그룹화
    df['year'] = df['timestamp'].dt.year

    for year, year_df in df.groupby('year'):
        # 저장 경로
        save_dir = Path(DATA_ROOT) / symbol / timeframe
        save_dir.mkdir(parents=True, exist_ok=True)

        file_path = save_dir / f"{year}.parquet"

        # 기존 파일 처리
        if file_path.exists() and not overwrite:
            logger.info(f"기존 파일과 병합: {file_path}")
            existing_df = pd.read_parquet(file_path)

            # timestamp 일관성 체크 (UTC 기준)
            if existing_df['timestamp'].dt.tz is None:
                existing_df['timestamp'] = existing_df['timestamp'].dt.tz_localize('UTC')

            # 시간대 통일 (모두 UTC로)
            year_df_copy = year_df.copy()
            year_df_copy['timestamp'] = year_df_copy['timestamp'].dt.tz_convert('UTC')
            existing_df['timestamp'] = existing_df['timestamp'].dt.tz_convert('UTC')

            # 병합 및 중복 제거
            combined_df = pd.concat([existing_df, year_df_copy])
            combined_df = combined_df.drop_duplicates(
                subset=['timestamp'],
                keep='last'  # 최신 데이터 우선
            )
            combined_df = combined_df.sort_values('timestamp').reset_index(drop=True)
            year_df_save = combined_df
        else:
            year_df_save = year_df.copy()

        # year 컬럼 제거 후 저장
        year_df_save = year_df_save.drop('year', axis=1)
        year_df_save.to_parquet(file_path, index=False)

        saved_files.append(str(file_path))
        logger.info(f"저장 완료: {file_path} ({len(year_df_save)}개 행)")

        # 로그 파일에도 기록
        if log_file:
            with open(log_file, 'a') as f:
                f.write(f"{datetime.now().isoformat()} - 저장: {file_path} ({len(year_df_save)}개 행)\n")

    return saved_files


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description='Upbit 캔들 데이터 수집 및 저장 (개선 버전)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--symbol', required=True, help='심볼 (예: KRW-BTC)')
    parser.add_argument('--timeframe', required=True, help='타임프레임 (1M/5M/1H/4H/1D/1W)')
    parser.add_argument('--start', type=str, help='시작 날짜 (YYYY-MM-DD, UTC)')
    parser.add_argument('--end', type=str, help='종료 날짜 (YYYY-MM-DD, UTC)')
    parser.add_argument('--days', type=int, default=30, help='최근 N일 (--start 미지정 시)')
    parser.add_argument('--overwrite', action='store_true', help='기존 파일 덮어쓰기')
    parser.add_argument('--verbose', action='store_true', help='상세 로깅')
    parser.add_argument('--log-file', type=str, help='로그 파일 경로')

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # 날짜 파싱
    start_date = None
    end_date = None

    if args.start:
        try:
            start_date = datetime.strptime(args.start, '%Y-%m-%d')
            start_date = start_date.replace(tzinfo=timezone.utc)
        except ValueError:
            logger.error(f"시작 날짜 형식 오류: {args.start}")
            sys.exit(1)

    if args.end:
        try:
            end_date = datetime.strptime(args.end, '%Y-%m-%d')
            # 하루의 끝으로 설정
            end_date = end_date.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        except ValueError:
            logger.error(f"종료 날짜 형식 오류: {args.end}")
            sys.exit(1)

    # start_date가 없으면 최근 N일로 설정
    if not start_date:
        start_date = datetime.now(timezone.utc) - timedelta(days=args.days)

    try:
        # 데이터 수집
        df = fetch_upbit_candles(
            symbol=args.symbol,
            timeframe=args.timeframe,
            start_date=start_date,
            end_date=end_date
        )

        if df.empty:
            logger.warning("수집된 데이터가 없습니다.")
            sys.exit(1)

        # 저장
        saved_files = save_to_parquet_by_year(
            df,
            symbol=args.symbol,
            timeframe=args.timeframe,
            overwrite=args.overwrite,
            log_file=args.log_file
        )

        logger.info(f"✅ 총 {len(saved_files)}개 파일 저장 완료")
        for file in saved_files:
            logger.info(f"   - {file}")

        sys.exit(0)

    except Exception as e:
        logger.error(f"❌ 오류 발생: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
