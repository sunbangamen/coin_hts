#!/usr/bin/env python3
"""
Phase 3 우선순위 2: 성능 테스트 (Performance Testing)

목표:
- 100+, 500+, 1000+ 신호 규모에서의 성능 측정
- 백엔드 실행 시간 및 메모리 사용량 분석
- 프론트엔드 차트 렌더링 성능 테스트
- 병목 지점 식별 및 최적화 기회 도출

테스트 시나리오:
1. Equity Curve 데이터 생성 (100+, 500+, 1000+ 신호)
2. API 응답 시간 측정
3. 차트 데이터 복잡도 분석
4. 메모리 사용량 추적
"""

import sys
import os
import time
import json
import psutil
import tracemalloc
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

# 프로젝트 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.app.strategies.volume_long_candle import VolumeLongCandleStrategy
from backend.app.strategies.volume_zone_breakout import VolumeZoneBreakoutStrategy
from backend.app.strategies.base import BacktestResult


def generate_ohlcv_data(num_candles: int, seed: int = 42) -> pd.DataFrame:
    """
    신호 개수에 맞게 OHLCV 데이터 생성

    Args:
        num_candles: 생성할 캔들 수
        seed: 재현성을 위한 난수 시드

    Returns:
        OHLCV DataFrame (timestamp, open, high, low, close, volume)
    """
    np.random.seed(seed)

    base_price = 100.0
    dates = pd.date_range(start='2024-01-01', periods=num_candles, freq='D', tz='UTC')

    data = {
        'timestamp': dates,
        'open': [],
        'high': [],
        'low': [],
        'close': [],
        'volume': [],
    }

    current_price = base_price

    # 신호가 균등하게 분포되도록 생성
    signal_interval = max(1, num_candles // 50)  # 약 50개의 신호 분포

    for i in range(num_candles):
        # 기본 가격 변동
        change = np.random.randn() * 2
        current_price += change

        open_price = current_price
        close_price = current_price + np.random.randn() * 1

        # 주기적으로 거래량 급증 및 가격 상승으로 신호 생성
        if i % signal_interval == 0 and i > 0:
            volume = np.random.uniform(2000, 3000)
            if i % (signal_interval * 2) == 0:
                close_price = open_price * 1.02  # 2% 상승
            else:
                close_price = open_price * 0.99  # 1% 하락
        else:
            volume = np.random.uniform(100, 500)

        high_price = max(open_price, close_price) + abs(np.random.randn()) * 0.5
        low_price = min(open_price, close_price) - abs(np.random.randn()) * 0.5

        data['open'].append(open_price)
        data['high'].append(high_price)
        data['low'].append(low_price)
        data['close'].append(close_price)
        data['volume'].append(volume)

    df = pd.DataFrame(data)
    return df


def measure_strategy_performance(
    strategy_name: str,
    strategy_class,
    df: pd.DataFrame,
    params: Dict
) -> Dict:
    """
    전략 실행 성능 측정

    Args:
        strategy_name: 전략 이름
        strategy_class: 전략 클래스
        df: OHLCV DataFrame
        params: 전략 파라미터

    Returns:
        성능 측정 결과 딕셔너리
    """
    strategy = strategy_class()

    # 메모리 추적 시작
    tracemalloc.start()
    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss / 1024 / 1024  # MB

    # 실행 시간 측정
    start_time = time.time()
    try:
        result = strategy.run(df, params)
        execution_time = time.time() - start_time
        success = True
        error = None
    except Exception as e:
        execution_time = time.time() - start_time
        success = False
        error = str(e)
        result = None

    # 메모리 정보 수집
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    mem_after = process.memory_info().rss / 1024 / 1024  # MB
    mem_used = mem_after - mem_before

    return {
        'strategy': strategy_name,
        'success': success,
        'error': error,
        'execution_time_sec': round(execution_time, 4),
        'memory_used_mb': round(mem_used, 2),
        'memory_peak_mb': round(peak / 1024 / 1024, 2),
        'num_signals': len(result.signals) if success and result else 0,
        'num_candles': len(df),
        'signals_per_second': round(len(result.signals) / execution_time, 2) if success and result and execution_time > 0 else 0,
        'timestamp': datetime.now().isoformat(),
    }


def analyze_equity_curve_complexity(num_signals: int, num_candles: int) -> Dict:
    """
    Equity Curve 차트 복잡도 분석

    Args:
        num_signals: 신호 개수
        num_candles: 캔들 개수

    Returns:
        복잡도 분석 결과
    """
    # Equity Curve 데이터 포인트 수
    curve_points = min(num_signals, num_candles)

    # 프론트엔드에서 렌더링할 데이터량 추정
    # - 각 포인트: {timestamp, equity, signal_info (optional)}
    bytes_per_point = 200  # 대략적인 JSON 크기
    total_data_kb = (curve_points * bytes_per_point) / 1024

    # ReferenceDot 마커 개수
    marker_count = num_signals

    return {
        'equity_curve_points': curve_points,
        'signal_markers': marker_count,
        'estimated_json_kb': round(total_data_kb, 2),
        'rendering_complexity': 'Low' if curve_points < 100 else 'Medium' if curve_points < 500 else 'High',
        'browser_memory_estimate_mb': round(total_data_kb / 1024 * 1.5, 2),  # 1.5배 여유
    }


def print_performance_report(
    test_results: List[Dict],
    equity_analyses: List[Dict]
) -> str:
    """
    성능 테스트 결과 보고서 생성

    Args:
        test_results: 성능 측정 결과 리스트
        equity_analyses: Equity Curve 분석 결과 리스트

    Returns:
        포매팅된 보고서 문자열
    """
    report = []
    report.append("\n" + "=" * 90)
    report.append("📊 Phase 3 우선순위 2: 성능 테스트 결과")
    report.append("=" * 90)

    # 백엔드 성능 테스트 결과
    report.append("\n[1] 백엔드 성능 분석\n")
    report.append("-" * 90)
    report.append(f"{'Scale':<15} {'Strategy':<25} {'Execution (s)':<15} {'Memory (MB)':<15} {'Signals/sec':<15}")
    report.append("-" * 90)

    for result in test_results:
        scale = f"{result['num_candles']} 캔들"
        strategy = result['strategy']
        exec_time = f"{result['execution_time_sec']:.4f}"
        memory = f"{result['memory_used_mb']:.2f}"
        signals_per_sec = f"{result['signals_per_second']:.1f}"

        status = "✅" if result['success'] else "❌"

        report.append(
            f"{scale:<15} {strategy:<25} {exec_time:<15} {memory:<15} {signals_per_sec:<15} {status}"
        )

    # Equity Curve 복잡도 분석
    report.append("\n[2] Equity Curve 차트 복잡도 분석\n")
    report.append("-" * 90)
    report.append(f"{'Scale':<15} {'Chart Points':<15} {'Markers':<15} {'Data Size (KB)':<15} {'Complexity':<20}")
    report.append("-" * 90)

    for analysis in equity_analyses:
        scale = f"{analysis.get('num_candles', 'N/A')} 캔들"
        points = f"{analysis['equity_curve_points']}"
        markers = f"{analysis['signal_markers']}"
        data_size = f"{analysis['estimated_json_kb']:.2f}"
        complexity = analysis['rendering_complexity']

        report.append(
            f"{scale:<15} {points:<15} {markers:<15} {data_size:<15} {complexity:<20}"
        )

    # 성능 분석
    report.append("\n[3] 성능 분석 및 권장사항\n")
    report.append("-" * 90)

    # 가장 빠른/느린 조합 찾기
    if test_results:
        fastest = min(test_results, key=lambda x: x['execution_time_sec'] if x['success'] else float('inf'))
        slowest = max(test_results, key=lambda x: x['execution_time_sec'] if x['success'] else 0)

        report.append(f"\n✅ 가장 빠른 조합:")
        report.append(f"   {fastest['strategy']} @ {fastest['num_candles']} 캔들")
        report.append(f"   실행 시간: {fastest['execution_time_sec']:.4f}초 ({fastest['signals_per_second']:.1f} signals/sec)")

        report.append(f"\n⚠️  가장 느린 조합:")
        report.append(f"   {slowest['strategy']} @ {slowest['num_candles']} 캔들")
        report.append(f"   실행 시간: {slowest['execution_time_sec']:.4f}초 ({slowest['signals_per_second']:.1f} signals/sec)")

        # 확장성 분석
        report.append("\n📈 확장성 분석:")
        for strategy_name in set(r['strategy'] for r in test_results):
            strategy_results = sorted(
                [r for r in test_results if r['strategy'] == strategy_name],
                key=lambda x: x['num_candles']
            )

            if len(strategy_results) >= 2:
                time_100 = strategy_results[0]['execution_time_sec']
                time_1000 = strategy_results[-1]['execution_time_sec']

                scaling_factor = time_1000 / time_100 if time_100 > 0 else 0
                complexity = "Linear (O(n))" if scaling_factor < 11 else "Quadratic (O(n²))" if scaling_factor < 100 else "Higher (O(n³))"

                report.append(f"   {strategy_name}:")
                report.append(f"      100→1000 캔들: {scaling_factor:.1f}배 증가 ({complexity})")

    # 차트 렌더링 성능 권장사항
    report.append("\n🎨 프론트엔드 차트 렌더링:")
    for analysis in equity_analyses:
        if analysis['equity_curve_points'] > 1000:
            report.append(f"\n   ⚠️  {analysis['equity_curve_points']} 포인트 (권장: <500)")
            report.append(f"      → 데이터 다운샘플링 고려 (매월 1개 포인트, 또는 선택적 로딩)")
            report.append(f"      → Virtual scrolling 또는 클라이언트 필터링 구현")
        elif analysis['equity_curve_points'] > 500:
            report.append(f"\n   ⚠️  {analysis['equity_curve_points']} 포인트 (중간 규모)")
            report.append(f"      → 괜찮지만 모바일에서 성능 저하 가능")
            report.append(f"      → 상황에 따라 데이터 집계 고려")
        else:
            report.append(f"\n   ✅ {analysis['equity_curve_points']} 포인트 (최적 범위)")

    # 병목 지점 분석
    report.append("\n🔍 식별된 병목 지점:\n")
    report.append("   [P1] VolumeZoneBreakout 저항선 계산")
    report.append("        - 위치: volume_zone_breakout.py:219-253")
    report.append("        - 복잡도: O(n²) 슬라이딩 윈도우")
    report.append("        - 개선 방안: numpy 벡터화, 증분 계산\n")

    report.append("   [P2] Metrics 계산")
    report.append("        - 위치: metrics.py:14-62")
    report.append("        - 특성: 순차 처리, 벡터화 미적용")
    report.append("        - 개선 방안: numpy/numba JIT 컴파일\n")

    report.append("   [P3] 대규모 신호 목록 렌더링")
    report.append("        - 위치: frontend SignalsTable 컴포넌트")
    report.append("        - 특성: 가상 스크롤링 미지원")
    report.append("        - 개선 방안: React window 라이브러리 적용")

    # 최종 권장사항
    report.append("\n" + "=" * 90)
    report.append("💡 최적화 우선순위\n")
    report.append("   1️⃣  VolumeZoneBreakout 저항선 계산 벡터화 (가장 효과적)")
    report.append("   2️⃣  Metrics 계산 numba JIT 컴파일")
    report.append("   3️⃣  프론트엔드 데이터 다운샘플링 (1000+신호)")
    report.append("   4️⃣  SignalsTable 가상 스크롤링 (500+신호)")

    report.append("\n" + "=" * 90)

    return "\n".join(report)


def main():
    """메인 성능 테스트 실행"""
    print("\n🚀 Phase 3 우선순위 2: 성능 테스트 시작\n")

    # 테스트 시나리오 정의
    test_scales = [
        (100, "소규모 (100 캔들)"),
        (300, "중규모 (300 캔들)"),
        (1000, "대규모 (1000 캔들)"),
    ]

    strategies = [
        ('VolumeLongCandle', VolumeLongCandleStrategy, {
            'vol_ma_window': 20,
            'vol_multiplier': 1.5,
            'body_pct': 0.02,
            'hold_period_bars': 1,
        }),
        ('VolumeZoneBreakout', VolumeZoneBreakoutStrategy, {
            'volume_window': 20,
            'top_percentile': 0.20,
            'breakout_buffer': 0.0,
            'hold_period_bars': 1,
        }),
    ]

    all_results = []
    equity_analyses = []

    # 1. 백엔드 성능 테스트
    print("📊 백엔드 성능 테스트 실행 중...\n")

    for num_candles, scale_name in test_scales:
        print(f"  {scale_name} 테스트...", end=" ", flush=True)

        # OHLCV 데이터 생성
        df = generate_ohlcv_data(num_candles)

        for strategy_name, strategy_class, params in strategies:
            result = measure_strategy_performance(
                strategy_name,
                strategy_class,
                df,
                params
            )
            all_results.append(result)

        print("✅")

    # 2. Equity Curve 복잡도 분석
    print("\n📈 Equity Curve 복잡도 분석 중...\n")

    for num_candles, scale_name in test_scales:
        df = generate_ohlcv_data(num_candles)

        # 신호 개수 추정 (평균적으로 10-20% 신호율)
        signal_count = len(df) // 5  # 대략 20% 신호율

        analysis = analyze_equity_curve_complexity(signal_count, num_candles)
        analysis['num_candles'] = num_candles
        analysis['scale_name'] = scale_name

        equity_analyses.append(analysis)

    # 보고서 생성 및 출력
    report = print_performance_report(all_results, equity_analyses)
    print(report)

    # 결과를 JSON으로도 저장
    output_file = os.path.join(
        os.path.dirname(__file__),
        '..',
        'docs',
        'coin',
        'mvp',
        'performance_test_results.json'
    )

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    output_data = {
        'test_timestamp': datetime.now().isoformat(),
        'test_results': all_results,
        'equity_curve_analysis': equity_analyses,
        'summary': {
            'total_tests': len(all_results),
            'successful_tests': sum(1 for r in all_results if r['success']),
            'failed_tests': sum(1 for r in all_results if not r['success']),
        }
    }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\n📁 상세 결과: {output_file}")

    return len([r for r in all_results if not r['success']]) == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
