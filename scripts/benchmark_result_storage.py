#!/usr/bin/env python3
"""
Benchmark Result Storage Performance

Task 3.5.6: 성능 검증 및 통합 테스트

This script benchmarks JSON vs Parquet storage performance.
It measures:
  - File size comparison
  - Compression ratio
  - Read/write performance
  - Memory usage

Usage:
    python scripts/benchmark_result_storage.py \\
        --num-signals 10000 \\
        --output-dir benchmark_results
"""

import argparse
import json
import os
import sys
import time
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.storage.converters import (
    json_to_parquet,
    parquet_to_json,
    calculate_compression_ratio,
)


def generate_sample_result(num_signals: int = 1000, num_symbols: int = 5) -> Dict[str, Any]:
    """
    Generate sample backtest result with specified number of signals

    Args:
        num_signals: Total number of signals across all symbols
        num_symbols: Number of symbols

    Returns:
        Backtest result dictionary
    """
    import uuid
    from random import uniform, randint, choice

    task_id = str(uuid.uuid4())
    signals_per_symbol = num_signals // num_symbols

    symbols_data = []

    for sym_idx in range(num_symbols):
        symbol = f"SYM{sym_idx:03d}/USDT"
        signals = []
        base_price = 1000.0

        for sig_idx in range(signals_per_symbol):
            timestamp = datetime.utcnow() - timedelta(hours=signals_per_symbol - sig_idx)
            entry_price = base_price + uniform(-50, 50)
            exit_price = entry_price + uniform(-20, 50)
            return_pct = ((exit_price - entry_price) / entry_price) * 100

            signals.append({
                'timestamp': timestamp.isoformat() + 'Z',
                'type': choice(['buy', 'sell']),
                'entry_price': float(round(entry_price, 2)),
                'exit_price': float(round(exit_price, 2)),
                'quantity': round(uniform(0.1, 10.0), 4),
                'return_pct': float(round(return_pct, 2)),
                'hold_bars': randint(1, 100),
                'fee_amount': float(round(uniform(0.1, 10.0), 2)),
                'slippage_amount': float(round(uniform(0.0, 5.0), 2)),
                'status': 'closed',
            })

        # Calculate statistics
        returns = [s['return_pct'] for s in signals]
        winning = [r for r in returns if r > 0]
        losing = [r for r in returns if r <= 0]

        symbols_data.append({
            'symbol': symbol,
            'win_rate': (len(winning) / len(signals) * 100) if signals else 0.0,
            'avg_return': sum(returns) / len(returns) if returns else 0.0,
            'max_return': max(returns) if returns else 0.0,
            'min_return': min(returns) if returns else 0.0,
            'max_drawdown': abs(min(returns)) if returns else 0.0,
            'avg_hold_bars': sum(s['hold_bars'] for s in signals) / len(signals) if signals else 0.0,
            'total_signals': len(signals),
            'winning_signals': len(winning),
            'losing_signals': len(losing),
            'total_pnl': sum(returns) * 1000 / len(returns) if returns else 0.0,
            'total_pnl_pct': sum(returns) if returns else 0.0,
            'signals': signals,
            'performance_curve': [
                {
                    'timestamp': (datetime.utcnow() - timedelta(hours=i)).isoformat() + 'Z',
                    'equity': 100000 + (i * sum(returns) / len(returns) * 10) if returns else 100000,
                    'drawdown': max(0, -min(returns) * (i / len(signals))) if returns else 0.0,
                    'cumulative_pnl': i * sum(returns) / len(returns) * 100 if returns else 0.0,
                    'cumulative_pnl_pct': i * sum(returns) / len(returns) if returns else 0.0,
                }
                for i in range(min(100, signals_per_symbol // 10 + 1))
            ],
        })

    return {
        'task_id': task_id,
        'strategy': 'benchmark_strategy',
        'start_date': '2024-01-01',
        'end_date': '2024-01-31',
        'symbols': symbols_data,
    }


def benchmark_json_storage(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Benchmark JSON storage

    Returns:
        Metrics dictionary
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(data, f)
        json_file = f.name

    try:
        json_size = os.path.getsize(json_file)

        # Measure read time
        start = time.time()
        with open(json_file, 'r') as f:
            loaded = json.load(f)
        read_time = time.time() - start

        return {
            'format': 'JSON',
            'file_size': json_size,
            'file_size_mb': json_size / (1024 * 1024),
            'read_time': read_time,
        }
    finally:
        os.unlink(json_file)


def benchmark_parquet_storage(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Benchmark Parquet storage

    Returns:
        Metrics dictionary
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Measure conversion time
        start = time.time()
        parquet_result = json_to_parquet(data, tmpdir)
        conversion_time = time.time() - start

        total_size = parquet_result['total_size']

        # Measure read time
        start = time.time()
        recovered = parquet_to_json(tmpdir)
        read_time = time.time() - start

        return {
            'format': 'Parquet',
            'file_size': total_size,
            'file_size_mb': total_size / (1024 * 1024),
            'conversion_time': conversion_time,
            'read_time': read_time,
        }


def run_benchmark(
    num_signals: int = 1000,
    output_dir: str = 'benchmark_results',
):
    """
    Run full benchmark suite

    Args:
        num_signals: Number of signals to generate
        output_dir: Output directory for results
    """
    logger.info("Generating sample backtest result...")
    data = generate_sample_result(num_signals=num_signals)

    logger.info("Benchmarking JSON storage...")
    json_metrics = benchmark_json_storage(data)

    logger.info("Benchmarking Parquet storage...")
    parquet_metrics = benchmark_parquet_storage(data)

    # Calculate metrics
    compression_ratio = calculate_compression_ratio(
        json_metrics['file_size'],
        parquet_metrics['file_size']
    )

    size_reduction = (1 - parquet_metrics['file_size'] / json_metrics['file_size']) * 100

    # Print results
    print("\n" + "=" * 80)
    print("STORAGE PERFORMANCE BENCHMARK")
    print("=" * 80)

    print(f"\nTest Configuration:")
    print(f"  Total Signals: {num_signals:,}")
    print(f"  Number of Symbols: {len(data['symbols'])}")

    print(f"\nJSON Storage:")
    print(f"  File Size: {json_metrics['file_size_mb']:.2f} MB ({json_metrics['file_size']:,} bytes)")
    print(f"  Read Time: {json_metrics['read_time']:.4f} seconds")

    print(f"\nParquet Storage:")
    print(f"  File Size: {parquet_metrics['file_size_mb']:.2f} MB ({parquet_metrics['file_size']:,} bytes)")
    print(f"  Conversion Time: {parquet_metrics['conversion_time']:.4f} seconds")
    print(f"  Read Time: {parquet_metrics['read_time']:.4f} seconds")

    print(f"\nComparison:")
    print(f"  Compression Ratio: {compression_ratio:.1f}%")
    print(f"  Size Reduction: {size_reduction:.1f}%")
    print(f"  Read Speedup: {json_metrics['read_time'] / parquet_metrics['read_time']:.2f}x")

    # Save report
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    report = {
        'timestamp': datetime.utcnow().isoformat(),
        'config': {
            'num_signals': num_signals,
            'num_symbols': len(data['symbols']),
        },
        'metrics': {
            'json': json_metrics,
            'parquet': parquet_metrics,
            'comparison': {
                'compression_ratio': compression_ratio,
                'size_reduction_percent': size_reduction,
                'read_speedup': json_metrics['read_time'] / parquet_metrics['read_time'],
            },
        },
    }

    report_file = Path(output_dir) / f"benchmark_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    logger.info(f"Report saved to: {report_file}")

    print("=" * 80 + "\n")

    return report


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Benchmark JSON vs Parquet storage performance'
    )

    parser.add_argument(
        '--num-signals',
        type=int,
        default=1000,
        help='Number of signals to generate (default: 1000)'
    )

    parser.add_argument(
        '--num-symbols',
        type=int,
        default=5,
        help='Number of symbols (default: 5)'
    )

    parser.add_argument(
        '--output-dir',
        default='benchmark_results',
        help='Output directory for benchmark results (default: benchmark_results)'
    )

    args = parser.parse_args()

    logger.info(f"Starting benchmark with {args.num_signals} signals...")
    report = run_benchmark(
        num_signals=args.num_signals,
        output_dir=args.output_dir,
    )

    # Check if compression ratio meets goal
    compression = report['metrics']['comparison']['compression_ratio']
    if compression >= 95:
        logger.info(f"✓ Compression ratio {compression:.1f}% meets goal (≥95%)")
        return 0
    else:
        logger.warning(f"✗ Compression ratio {compression:.1f}% below goal (≥95%)")
        return 1


if __name__ == '__main__':
    sys.exit(main())
