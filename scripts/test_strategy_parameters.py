#!/usr/bin/env python3
"""
전략 파라미터 튜닝 테스트 스크립트

volume_zone_breakout 전략의 다양한 파라미터 조합을 테스트하여
최적의 신호 생성 설정을 찾습니다.
"""

import requests
import json
import itertools
from datetime import datetime

API_URL = "http://localhost:8000"

def print_results_table(results, headers=None):
    """간단한 테이블 출력"""
    if not results:
        print("결과 없음")
        return

    if not headers:
        headers = list(results[0].keys())

    # 헤더 출력
    col_widths = {h: max(len(h), max(len(str(r.get(h, ''))) for r in results)) for h in headers}
    header_line = " | ".join(f"{h:^{col_widths[h]}}" for h in headers)
    separator = "-+-".join("-" * col_widths[h] for h in headers)

    print(f"\n{header_line}")
    print(separator)

    # 데이터 행 출력
    for row in results:
        row_line = " | ".join(f"{str(row.get(h, '')):{col_widths[h]}}" for h in headers)
        print(row_line)

# 테스트할 파라미터 조합
PARAMETER_GRID = {
    # 기본값 기준으로 다양한 조합 생성
    "vol_ma_window": [10, 20, 30, 60],  # 기본: 60
    "vol_multiplier": [1.0, 1.5, 2.0],  # 기본: 1.5
    "breakout_pct": [0.0, 0.005, 0.01, 0.02],  # 기본: 0.01 (기본값이 없어서 유추)
}

# Volume Zone Breakout 고유 파라미터
VZB_PARAMETER_GRID = {
    "volume_window": [10, 20, 30, 40, 60],  # 윈도우 크기
    "top_percentile": [0.05, 0.1, 0.15, 0.2, 0.3],  # 상위 5%, 10%, 15%, 20%, 30%
    "breakout_buffer": [0.0, 0.005, 0.01, 0.02],  # 돌파 버퍼 0%, 0.5%, 1%, 2%
}

def test_volume_long_candle():
    """volume_long_candle 전략 테스트"""
    print(f"\n{'='*80}")
    print(f"🧪 volume_long_candle 전략 파라미터 테스트")
    print(f"{'='*80}\n")

    results = []
    param_combinations = list(itertools.product(
        PARAMETER_GRID['vol_ma_window'],
        PARAMETER_GRID['vol_multiplier'],
        PARAMETER_GRID['breakout_pct'],
    ))

    print(f"테스트할 조합 수: {len(param_combinations)}\n")

    for idx, (vol_ma_window, vol_multiplier, body_pct) in enumerate(param_combinations, 1):
        payload = {
            "strategy": "volume_long_candle",
            "symbols": ["BTC_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-02-29",
            "timeframe": "1d",
            "params": {
                "vol_ma_window": vol_ma_window,
                "vol_multiplier": vol_multiplier,
                "body_pct": body_pct,
            },
        }

        try:
            response = requests.post(f"{API_URL}/api/backtests/run", json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                symbol_result = result["symbols"][0]

                results.append({
                    "Strategy": "volume_long_candle",
                    "vol_ma_window": vol_ma_window,
                    "vol_multiplier": vol_multiplier,
                    "body_pct": body_pct,
                    "Signals": len(symbol_result["signals"]),
                    "Win Rate": f"{symbol_result['win_rate']*100:.1f}%",
                    "Avg Return": f"{symbol_result['avg_return']*100:.2f}%",
                })

                print(f"[{idx}/{len(param_combinations)}] ✅ vol_ma={vol_ma_window}, vol_mult={vol_multiplier}, body={body_pct} → {len(symbol_result['signals'])} signals")
            else:
                print(f"[{idx}/{len(param_combinations)}] ❌ HTTP {response.status_code}")

        except Exception as e:
            print(f"[{idx}/{len(param_combinations)}] ❌ Error: {e}")

    # 결과 정렬 (신호 수 내림차순)
    results.sort(key=lambda x: x["Signals"], reverse=True)

    print(f"\n📊 테스트 결과 (상위 10개):")
    print_results_table(results[:10])

    return results

def test_volume_zone_breakout():
    """volume_zone_breakout 전략 테스트"""
    print(f"\n{'='*80}")
    print(f"🧪 volume_zone_breakout 전략 파라미터 테스트")
    print(f"{'='*80}\n")

    results = []
    param_combinations = list(itertools.product(
        VZB_PARAMETER_GRID['volume_window'],
        VZB_PARAMETER_GRID['top_percentile'],
        VZB_PARAMETER_GRID['breakout_buffer'],
    ))

    print(f"테스트할 조합 수: {len(param_combinations)}\n")

    for idx, (volume_window, top_percentile, breakout_buffer) in enumerate(param_combinations, 1):
        payload = {
            "strategy": "volume_zone_breakout",
            "symbols": ["BTC_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-02-29",
            "timeframe": "1d",
            "params": {
                "volume_window": volume_window,
                "top_percentile": top_percentile,
                "breakout_buffer": breakout_buffer,
            },
        }

        try:
            response = requests.post(f"{API_URL}/api/backtests/run", json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                symbol_result = result["symbols"][0]

                results.append({
                    "Strategy": "volume_zone_breakout",
                    "volume_window": volume_window,
                    "top_percentile": f"{top_percentile*100:.0f}%",
                    "breakout_buffer": f"{breakout_buffer*100:.1f}%",
                    "Signals": len(symbol_result["signals"]),
                    "Win Rate": f"{symbol_result['win_rate']*100:.1f}%",
                    "Avg Return": f"{symbol_result['avg_return']*100:.2f}%",
                })

                if len(symbol_result["signals"]) > 0:
                    print(f"[{idx}/{len(param_combinations)}] ✅ vw={volume_window}, top={top_percentile*100:.0f}%, buf={breakout_buffer*100:.1f}% → {len(symbol_result['signals'])} signals")
                else:
                    print(f"[{idx}/{len(param_combinations)}] ⏸️  vw={volume_window}, top={top_percentile*100:.0f}%, buf={breakout_buffer*100:.1f}% → 0 signals")
            else:
                print(f"[{idx}/{len(param_combinations)}] ❌ HTTP {response.status_code}")

        except Exception as e:
            print(f"[{idx}/{len(param_combinations)}] ❌ Error: {e}")

    # 결과 정렬 (신호 수 내림차순)
    results.sort(key=lambda x: x["Signals"], reverse=True)

    print(f"\n📊 테스트 결과 (신호 생성 조합):")
    signal_results = [r for r in results if r["Signals"] > 0]
    if signal_results:
        print_results_table(signal_results[:10])
    else:
        print("신호 생성 조합 없음 (모든 조합이 0 신호 생성)")

    print(f"\n📊 전체 결과 (상위 20개):")
    print_results_table(results[:20])

    return results

def save_results(vlc_results, vzb_results):
    """결과를 파일로 저장"""
    output = {
        "timestamp": datetime.now().isoformat(),
        "volume_long_candle": vlc_results,
        "volume_zone_breakout": vzb_results,
    }

    with open("/tmp/strategy_parameter_test_results.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ 결과 저장: /tmp/strategy_parameter_test_results.json")

def main():
    """메인 함수"""
    print(f"🚀 전략 파라미터 튜닝 테스트 시작 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")

    # volume_long_candle 테스트
    vlc_results = test_volume_long_candle()

    # volume_zone_breakout 테스트
    vzb_results = test_volume_zone_breakout()

    # 결과 저장
    save_results(vlc_results, vzb_results)

    # 최종 요약
    print(f"\n{'='*80}")
    print(f"📈 최종 요약")
    print(f"{'='*80}")

    vlc_with_signals = [r for r in vlc_results if r["Signals"] > 0]
    vzb_with_signals = [r for r in vzb_results if r["Signals"] > 0]

    print(f"\nvolume_long_candle:")
    print(f"  - 테스트 조합: {len(vlc_results)}")
    print(f"  - 신호 생성 조합: {len(vlc_with_signals)}")
    if vlc_with_signals:
        best_vlc = vlc_with_signals[0]
        print(f"  - 최고 성능: {best_vlc['Signals']}개 신호 (vol_ma={best_vlc['vol_ma_window']}, mult={best_vlc['vol_multiplier']}, body={best_vlc['body_pct']})")

    print(f"\nvolume_zone_breakout:")
    print(f"  - 테스트 조합: {len(vzb_results)}")
    print(f"  - 신호 생성 조합: {len(vzb_with_signals)}")
    if vzb_with_signals:
        best_vzb = vzb_with_signals[0]
        print(f"  - 최고 성능: {best_vzb['Signals']}개 신호")
        print(f"    Parameters: volume_window={best_vzb['volume_window']}, top_percentile={best_vzb['top_percentile']}, breakout_buffer={best_vzb['breakout_buffer']}")
    else:
        print(f"  - ⚠️  신호 생성 불가: 테스트 데이터의 변동성이 충분하지 않음")

if __name__ == "__main__":
    main()
