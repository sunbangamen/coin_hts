"""JSON to Parquet converter for backtest results

This module provides utilities to convert between JSON and Parquet formats
for efficient storage and retrieval of backtest results.

Task 3.5.4: JSON → Parquet 변환 유틸리티
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)


# ============ PyArrow Schemas ============

def get_symbol_summary_schema() -> pa.Schema:
    """Get PyArrow schema for symbol_summary table"""
    return pa.schema([
        pa.field("symbol", pa.string()),
        pa.field("win_rate", pa.float64()),
        pa.field("avg_return", pa.float64()),
        pa.field("max_return", pa.float64()),
        pa.field("min_return", pa.float64()),
        pa.field("max_drawdown", pa.float64()),
        pa.field("avg_hold_bars", pa.float64()),
        pa.field("total_signals", pa.int32()),
        pa.field("winning_signals", pa.int32()),
        pa.field("losing_signals", pa.int32()),
        pa.field("total_pnl", pa.float64()),
        pa.field("total_pnl_pct", pa.float64()),
    ])


def get_symbol_signals_schema() -> pa.Schema:
    """Get PyArrow schema for symbol_signals table"""
    return pa.schema([
        pa.field("symbol", pa.string()),
        pa.field("signal_index", pa.int32()),
        pa.field("timestamp", pa.timestamp('us')),
        pa.field("type", pa.string()),
        pa.field("entry_price", pa.float64()),
        pa.field("exit_price", pa.float64()),
        pa.field("quantity", pa.float64()),
        pa.field("return_pct", pa.float64()),
        pa.field("hold_bars", pa.int32()),
        pa.field("fee_amount", pa.float64()),
        pa.field("slippage_amount", pa.float64()),
        pa.field("status", pa.string()),
    ])


def get_performance_curve_schema() -> pa.Schema:
    """Get PyArrow schema for performance_curve table"""
    return pa.schema([
        pa.field("symbol", pa.string()),
        pa.field("idx", pa.int32()),
        pa.field("timestamp", pa.timestamp('us')),
        pa.field("equity", pa.float64()),
        pa.field("drawdown", pa.float64()),
        pa.field("cumulative_pnl", pa.float64()),
        pa.field("cumulative_pnl_pct", pa.float64()),
    ])


# ============ Conversion Functions ============

def _safe_float(value: Any) -> Optional[float]:
    """Safely convert value to float"""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> Optional[int]:
    """Safely convert value to int"""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse ISO format timestamp string"""
    if not timestamp_str:
        return None
    try:
        # Handle ISO 8601 format with 'Z' suffix
        ts_str = timestamp_str.replace('Z', '+00:00')
        return datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        logger.warning(f"Failed to parse timestamp: {timestamp_str}")
        return None


def json_to_parquet(
    json_data: Dict[str, Any],
    output_dir: str,
    compression: str = 'snappy',
    row_group_size: int = 10000,
) -> Dict[str, Any]:
    """
    Convert backtest result JSON to Parquet format

    Splits data into 3 tables:
    1. symbol_summary: Per-symbol statistics
    2. symbol_signals: Individual trade signals
    3. performance_curve: Portfolio equity curve

    Args:
        json_data: BacktestResult dictionary from JSON
        output_dir: Output directory for Parquet files
        compression: Compression codec ('snappy', 'gzip', 'brotli', 'zstd')
        row_group_size: Parquet row group size for optimization

    Returns:
        Dictionary with file paths and metadata:
        {
            'symbol_summary': 'backtests/{task_id}/symbol_summary.parquet',
            'symbol_signals': 'backtests/{task_id}/symbol_signals.parquet',
            'performance_curve': 'backtests/{task_id}/performance_curve.parquet',
            'metadata': {...}
        }

    Raises:
        ValueError: If JSON data structure is invalid
        IOError: If file write fails
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        # Extract data from JSON
        symbols = json_data.get('symbols', [])
        if not symbols:
            raise ValueError("No symbols found in backtest result")

        # Initialize data lists for each table
        summary_data = []
        signals_data = []
        performance_data = []

        # Process each symbol
        for symbol_obj in symbols:
            symbol = symbol_obj.get('symbol', '')
            signal_list = symbol_obj.get('signals', [])
            performance = symbol_obj.get('performance_curve', [])

            # 1. Build symbol_summary row
            summary_row = {
                'symbol': symbol,
                'win_rate': _safe_float(symbol_obj.get('win_rate')),
                'avg_return': _safe_float(symbol_obj.get('avg_return')),
                'max_return': _safe_float(symbol_obj.get('max_return')),
                'min_return': _safe_float(symbol_obj.get('min_return')),
                'max_drawdown': _safe_float(symbol_obj.get('max_drawdown')),
                'avg_hold_bars': _safe_float(symbol_obj.get('avg_hold_bars')),
                'total_signals': _safe_int(symbol_obj.get('total_signals')),
                'winning_signals': _safe_int(symbol_obj.get('winning_signals')),
                'losing_signals': _safe_int(symbol_obj.get('losing_signals')),
                'total_pnl': _safe_float(symbol_obj.get('total_pnl')),
                'total_pnl_pct': _safe_float(symbol_obj.get('total_pnl_pct')),
            }
            summary_data.append(summary_row)

            # 2. Build symbol_signals rows
            for signal_idx, signal in enumerate(signal_list):
                signal_row = {
                    'symbol': symbol,
                    'signal_index': signal_idx,
                    'timestamp': _parse_timestamp(signal.get('timestamp')),
                    'type': signal.get('type', ''),
                    'entry_price': _safe_float(signal.get('entry_price')),
                    'exit_price': _safe_float(signal.get('exit_price')),
                    'quantity': _safe_float(signal.get('quantity')),
                    'return_pct': _safe_float(signal.get('return_pct')),
                    'hold_bars': _safe_int(signal.get('hold_bars')),
                    'fee_amount': _safe_float(signal.get('fee_amount')),
                    'slippage_amount': _safe_float(signal.get('slippage_amount')),
                    'status': signal.get('status', 'closed'),
                }
                signals_data.append(signal_row)

            # 3. Build performance_curve rows
            for idx, perf in enumerate(performance):
                perf_row = {
                    'symbol': symbol,
                    'idx': idx,
                    'timestamp': _parse_timestamp(perf.get('timestamp')),
                    'equity': _safe_float(perf.get('equity')),
                    'drawdown': _safe_float(perf.get('drawdown')),
                    'cumulative_pnl': _safe_float(perf.get('cumulative_pnl')),
                    'cumulative_pnl_pct': _safe_float(perf.get('cumulative_pnl_pct')),
                }
                performance_data.append(perf_row)

        # Create PyArrow tables
        logger.info(f"Creating Parquet tables: summary={len(summary_data)}, signals={len(signals_data)}, performance={len(performance_data)}")

        summary_table = pa.Table.from_pylist(summary_data, schema=get_symbol_summary_schema())
        signals_table = pa.Table.from_pylist(signals_data, schema=get_symbol_signals_schema())
        performance_table = pa.Table.from_pylist(performance_data, schema=get_performance_curve_schema())

        # Write Parquet files
        summary_path = output_path / 'symbol_summary.parquet'
        signals_path = output_path / 'symbol_signals.parquet'
        performance_path = output_path / 'performance_curve.parquet'

        pq.write_table(summary_table, summary_path, compression=compression, row_group_size=row_group_size)
        pq.write_table(signals_table, signals_path, compression=compression, row_group_size=row_group_size)
        pq.write_table(performance_table, performance_path, compression=compression, row_group_size=row_group_size)

        logger.info(f"Parquet files written to {output_dir}")

        # Calculate file sizes
        summary_size = summary_path.stat().st_size
        signals_size = signals_path.stat().st_size
        performance_size = performance_path.stat().st_size
        total_size = summary_size + signals_size + performance_size

        # Write metadata.json
        metadata = {
            'schema_version': '1.0',
            'compression': compression,
            'parquet_files': {
                'symbol_summary': {
                    'row_count': len(summary_data),
                    'file_size_bytes': summary_size,
                },
                'symbol_signals': {
                    'row_count': len(signals_data),
                    'file_size_bytes': signals_size,
                },
                'performance_curve': {
                    'row_count': len(performance_data),
                    'file_size_bytes': performance_size,
                },
            },
            'total_size_bytes': total_size,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'task_id': json_data.get('task_id'),
        }

        metadata_path = output_path / 'metadata.json'
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Metadata written to {metadata_path}")

        return {
            'symbol_summary': str(summary_path),
            'symbol_signals': str(signals_path),
            'performance_curve': str(performance_path),
            'metadata': metadata,
            'total_size': total_size,
        }

    except Exception as e:
        logger.error(f"Error converting JSON to Parquet: {e}", exc_info=True)
        raise


def parquet_to_json(
    parquet_dir: str,
    include_metadata: bool = True,
) -> Dict[str, Any]:
    """
    Convert Parquet format back to JSON (reverse conversion)

    This is useful for validation and debugging.

    Args:
        parquet_dir: Directory containing Parquet files
        include_metadata: Include metadata from metadata.json

    Returns:
        BacktestResult dictionary in JSON format

    Raises:
        IOError: If Parquet files not found
        ValueError: If schema validation fails
    """
    parquet_path = Path(parquet_dir)

    try:
        # Read Parquet files
        summary_path = parquet_path / 'symbol_summary.parquet'
        signals_path = parquet_path / 'symbol_signals.parquet'
        performance_path = parquet_path / 'performance_curve.parquet'

        if not all(p.exists() for p in [summary_path, signals_path, performance_path]):
            raise IOError(f"Required Parquet files not found in {parquet_dir}")

        summary_table = pq.read_table(summary_path)
        signals_table = pq.read_table(signals_path)
        performance_table = pq.read_table(performance_path)

        # Read metadata if available
        metadata = {}
        metadata_path = parquet_path / 'metadata.json'
        if metadata_path.exists() and include_metadata:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

        # Convert to dictionaries
        summary_dict = summary_table.to_pydict()
        signals_dict = signals_table.to_pydict()
        performance_dict = performance_table.to_pydict()

        # Reconstruct JSON format
        symbols = {}

        # Organize by symbol
        for i, symbol in enumerate(summary_dict['symbol']):
            if symbol not in symbols:
                symbols[symbol] = {
                    'symbol': symbol,
                    'win_rate': summary_dict['win_rate'][i],
                    'avg_return': summary_dict['avg_return'][i],
                    'max_return': summary_dict['max_return'][i],
                    'min_return': summary_dict['min_return'][i],
                    'max_drawdown': summary_dict['max_drawdown'][i],
                    'avg_hold_bars': summary_dict['avg_hold_bars'][i],
                    'total_signals': summary_dict['total_signals'][i],
                    'winning_signals': summary_dict['winning_signals'][i],
                    'losing_signals': summary_dict['losing_signals'][i],
                    'total_pnl': summary_dict['total_pnl'][i],
                    'total_pnl_pct': summary_dict['total_pnl_pct'][i],
                    'signals': [],
                    'performance_curve': [],
                }

        # Add signals
        for i, symbol in enumerate(signals_dict['symbol']):
            signal = {
                'timestamp': signals_dict['timestamp'][i].isoformat() if signals_dict['timestamp'][i] else None,
                'type': signals_dict['type'][i],
                'entry_price': signals_dict['entry_price'][i],
                'exit_price': signals_dict['exit_price'][i],
                'quantity': signals_dict['quantity'][i],
                'return_pct': signals_dict['return_pct'][i],
                'hold_bars': signals_dict['hold_bars'][i],
                'fee_amount': signals_dict['fee_amount'][i],
                'slippage_amount': signals_dict['slippage_amount'][i],
                'status': signals_dict['status'][i],
            }
            if symbol in symbols:
                symbols[symbol]['signals'].append(signal)

        # Add performance curve
        for i, symbol in enumerate(performance_dict['symbol']):
            perf = {
                'timestamp': performance_dict['timestamp'][i].isoformat() if performance_dict['timestamp'][i] else None,
                'equity': performance_dict['equity'][i],
                'drawdown': performance_dict['drawdown'][i],
                'cumulative_pnl': performance_dict['cumulative_pnl'][i],
                'cumulative_pnl_pct': performance_dict['cumulative_pnl_pct'][i],
            }
            if symbol in symbols:
                symbols[symbol]['performance_curve'].append(perf)

        result = {
            'symbols': list(symbols.values()),
            'metadata': metadata,
        }

        logger.info(f"Converted Parquet to JSON with {len(symbols)} symbols")
        return result

    except Exception as e:
        logger.error(f"Error converting Parquet to JSON: {e}", exc_info=True)
        raise


def calculate_compression_ratio(json_size: int, parquet_size: int) -> float:
    """Calculate compression ratio percentage

    Args:
        json_size: Original JSON file size in bytes
        parquet_size: Compressed Parquet file size in bytes

    Returns:
        Compression ratio as percentage (0-100)
    """
    if json_size == 0:
        return 0.0
    return ((json_size - parquet_size) / json_size) * 100


def validate_schema(
    table: pa.Table,
    expected_schema: pa.Schema,
) -> bool:
    """Validate PyArrow table schema

    Args:
        table: PyArrow table to validate
        expected_schema: Expected schema

    Returns:
        True if schema matches, raises ValueError otherwise
    """
    if table.schema != expected_schema:
        raise ValueError(
            f"Schema mismatch:\nExpected: {expected_schema}\nActual: {table.schema}"
        )
    return True
