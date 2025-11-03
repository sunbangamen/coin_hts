#!/usr/bin/env python3
"""
OHLCV 테스트 데이터 생성 스크립트

cryptocurrency backtesting 테스트용 OHLCV 데이터를 생성합니다.
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_ohlcv_data(
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str,
    initial_price: float = 50000000.0,  # BTC_KRW 초기가격
    volatility: float = 0.05,  # 일일 변동성 5% (신호 생성용으로 증가)
    trend: float = 0.001,  # 일일 트렌드 0.1% (상승 트렌드)
    volume_base: int = 5000,  # 기본 거래량 증가
    seed: int = 42
) -> pd.DataFrame:
    """
    OHLCV 테스트 데이터 생성

    Args:
        symbol: 심볼 (예: "BTC_KRW")
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)
        timeframe: 타임프레임 ("1d", "1h" 등)
        initial_price: 초기 가격
        volatility: 일일 변동성 (%)
        trend: 일일 트렌드 (%)
        volume_base: 기본 거래량
        seed: 난수 시드

    Returns:
        pd.DataFrame: OHLCV 데이터
    """
    np.random.seed(seed)

    # 날짜 범위 생성
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    dates = pd.date_range(start=start, end=end, freq='D')

    # OHLCV 데이터 생성
    data = []
    current_price = initial_price

    for i, date in enumerate(dates):
        # 일일 변동
        daily_return = np.random.normal(trend, volatility)
        open_price = current_price

        # 일 중 가격 변동 (5% -> 10%로 증가)
        intra_volatility = volatility  # 일 중 변동성 증가
        high_price = open_price * (1 + np.random.uniform(0.01, intra_volatility))
        low_price = open_price * (1 - np.random.uniform(0, intra_volatility * 0.8))

        # 종가 (트렌드 + 변동성 반영)
        close_price = open_price * (1 + daily_return)

        # 고가/저가 조정
        high_price = max(high_price, close_price)
        low_price = min(low_price, close_price)

        # 거래량 (급증 패턴 포함)
        # 주기적으로 거래량 급증 (20일마다)
        if i % 20 == 10:  # 신호 패턴 생성
            volume = int(volume_base * np.random.uniform(2.5, 4.0))  # 2.5~4배 급증
        else:
            volume = int(volume_base * np.random.uniform(0.7, 1.3))

        data.append({
            'timestamp': date,
            'symbol': symbol,
            'timeframe': timeframe,
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': volume,
        })

        current_price = close_price

    df = pd.DataFrame(data)

    # timestamp를 UTC timezone-aware로 설정
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)

    return df


def save_parquet(df: pd.DataFrame, output_path: str):
    """
    DataFrame을 Parquet 형식으로 저장

    Args:
        df: DataFrame
        output_path: 출력 경로
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_parquet(output_path, index=False, engine='pyarrow')
    print(f"✓ Saved: {output_path}")


def main():
    """메인 함수 - 테스트 데이터 생성"""

    print("=" * 60)
    print("OHLCV 테스트 데이터 생성")
    print("=" * 60)

    # 데이터 저장 경로
    data_root = os.getenv("DATA_ROOT", "/data")

    # 생성할 데이터 설정
    datasets = [
        {
            "symbol": "BTC_KRW",
            "start": "2024-01-01",
            "end": "2024-02-29",
            "timeframe": "1D",  # data_loader가 대문자로 변환하므로 대문자로 저장
            "initial_price": 50000000.0,
            "volume_base": 5000,
        },
        {
            "symbol": "ETH_KRW",
            "start": "2024-01-01",
            "end": "2024-02-29",
            "timeframe": "1D",  # data_loader가 대문자로 변환하므로 대문자로 저장
            "initial_price": 3000000.0,
            "volume_base": 10000,
        },
    ]

    # 각 데이터세트 생성
    for config in datasets:
        print(f"\n생성 중: {config['symbol']} ({config['start']} ~ {config['end']})")

        df = generate_ohlcv_data(
            symbol=config["symbol"],
            start_date=config["start"],
            end_date=config["end"],
            timeframe=config["timeframe"],
            initial_price=config["initial_price"],
            volume_base=config["volume_base"],
        )

        print(f"  - 행 수: {len(df)}")
        print(f"  - 컬럼: {list(df.columns)}")
        print(f"  - 가격 범위: {df['close'].min():.0f} ~ {df['close'].max():.0f}")

        # Parquet 저장
        year = config["start"][:4]
        output_path = os.path.join(
            data_root, config["symbol"], config["timeframe"], f"{year}.parquet"
        )
        save_parquet(df, output_path)

    print("\n" + "=" * 60)
    print("✓ 테스트 데이터 생성 완료!")
    print("=" * 60)

    # 생성된 파일 목록 표시
    print("\n생성된 파일:")
    for root, dirs, files in os.walk(data_root):
        level = root.replace(data_root, "").count(os.sep)
        indent = " " * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = " " * 2 * (level + 1)
        for file in files:
            file_path = os.path.join(root, file)
            file_size = os.path.getsize(file_path)
            print(f"{subindent}{file} ({file_size:,} bytes)")


if __name__ == "__main__":
    main()
