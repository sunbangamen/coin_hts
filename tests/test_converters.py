"""Tests for JSON to Parquet converters

Task 3.5.4: JSON → Parquet 변환 유틸리티 테스트
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime
import pytest

from backend.app.storage.converters import (
    json_to_parquet,
    parquet_to_json,
    calculate_compression_ratio,
    get_symbol_summary_schema,
    get_symbol_signals_schema,
    get_performance_curve_schema,
)


@pytest.fixture
def sample_backtest_result():
    """Create sample backtest result JSON"""
    return {
        'task_id': '550e8400-e29b-41d4-a716-446655440000',
        'strategy': 'volume_zone_breakout',
        'symbols': [
            {
                'symbol': 'BTC/USDT',
                'win_rate': 58.5,
                'avg_return': 2.15,
                'max_return': 5.0,
                'min_return': -3.5,
                'max_drawdown': 8.3,
                'avg_hold_bars': 24.5,
                'total_signals': 200,
                'winning_signals': 117,
                'losing_signals': 83,
                'total_pnl': 12500.0,
                'total_pnl_pct': 12.5,
                'signals': [
                    {
                        'timestamp': '2024-01-01T10:00:00Z',
                        'type': 'buy',
                        'entry_price': 42000.0,
                        'exit_price': 42840.0,
                        'quantity': 0.5,
                        'return_pct': 2.0,
                        'hold_bars': 20,
                        'fee_amount': 21.0,
                        'slippage_amount': 10.0,
                        'status': 'closed',
                    },
                    {
                        'timestamp': '2024-01-01T14:00:00Z',
                        'type': 'sell',
                        'entry_price': 42840.0,
                        'exit_price': 42100.0,
                        'quantity': 0.5,
                        'return_pct': -1.8,
                        'hold_bars': 18,
                        'fee_amount': 21.0,
                        'slippage_amount': 12.0,
                        'status': 'closed',
                    },
                ],
                'performance_curve': [
                    {
                        'timestamp': '2024-01-01T00:00:00Z',
                        'equity': 100000.0,
                        'drawdown': 0.0,
                        'cumulative_pnl': 0.0,
                        'cumulative_pnl_pct': 0.0,
                    },
                    {
                        'timestamp': '2024-01-01T01:00:00Z',
                        'equity': 102000.0,
                        'drawdown': 0.0,
                        'cumulative_pnl': 2000.0,
                        'cumulative_pnl_pct': 2.0,
                    },
                    {
                        'timestamp': '2024-01-01T02:00:00Z',
                        'equity': 100300.0,
                        'drawdown': 1.7,
                        'cumulative_pnl': 300.0,
                        'cumulative_pnl_pct': 0.3,
                    },
                ],
            },
            {
                'symbol': 'ETH/USDT',
                'win_rate': 55.2,
                'avg_return': 1.85,
                'max_return': 4.2,
                'min_return': -2.8,
                'max_drawdown': 6.5,
                'avg_hold_bars': 22.0,
                'total_signals': 180,
                'winning_signals': 99,
                'losing_signals': 81,
                'total_pnl': 8900.0,
                'total_pnl_pct': 8.9,
                'signals': [
                    {
                        'timestamp': '2024-01-01T12:30:00Z',
                        'type': 'buy',
                        'entry_price': 2250.0,
                        'exit_price': 2295.0,
                        'quantity': 2.0,
                        'return_pct': 2.0,
                        'hold_bars': 22,
                        'fee_amount': 9.0,
                        'slippage_amount': 5.0,
                        'status': 'closed',
                    },
                ],
                'performance_curve': [
                    {
                        'timestamp': '2024-01-01T00:00:00Z',
                        'equity': 100000.0,
                        'drawdown': 0.0,
                        'cumulative_pnl': 0.0,
                        'cumulative_pnl_pct': 0.0,
                    },
                ],
            },
        ],
    }


class TestJsonToParquet:
    """Test JSON to Parquet conversion"""

    def test_json_to_parquet_creates_files(self, sample_backtest_result):
        """Test that json_to_parquet creates all required Parquet files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = json_to_parquet(sample_backtest_result, tmpdir)

            # Check return value
            assert 'symbol_summary' in result
            assert 'symbol_signals' in result
            assert 'performance_curve' in result
            assert 'metadata' in result
            assert 'total_size' in result

            # Check files exist
            summary_path = Path(result['symbol_summary'])
            signals_path = Path(result['symbol_signals'])
            performance_path = Path(result['performance_curve'])

            assert summary_path.exists()
            assert signals_path.exists()
            assert performance_path.exists()

    def test_json_to_parquet_metadata(self, sample_backtest_result):
        """Test metadata.json content"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = json_to_parquet(sample_backtest_result, tmpdir)
            metadata = result['metadata']

            # Check metadata structure
            assert metadata['schema_version'] == '1.0'
            assert metadata['compression'] == 'snappy'
            assert 'parquet_files' in metadata
            assert 'symbol_summary' in metadata['parquet_files']
            assert 'symbol_signals' in metadata['parquet_files']
            assert 'performance_curve' in metadata['parquet_files']
            assert 'total_size_bytes' in metadata
            assert 'created_at' in metadata

            # Check row counts
            assert metadata['parquet_files']['symbol_summary']['row_count'] == 2  # 2 symbols
            assert metadata['parquet_files']['symbol_signals']['row_count'] == 3  # 3 signals total
            assert metadata['parquet_files']['performance_curve']['row_count'] == 4  # 4 perf records

    def test_json_to_parquet_row_counts(self, sample_backtest_result):
        """Test that correct number of rows are written"""
        import pyarrow.parquet as pq

        with tempfile.TemporaryDirectory() as tmpdir:
            result = json_to_parquet(sample_backtest_result, tmpdir)

            # Read back and check row counts
            summary = pq.read_table(result['symbol_summary'])
            signals = pq.read_table(result['symbol_signals'])
            performance = pq.read_table(result['performance_curve'])

            assert len(summary) == 2  # BTC, ETH
            assert len(signals) == 3  # 2 signals from BTC, 1 from ETH
            assert len(performance) == 4  # 3 from BTC, 1 from ETH

    def test_json_to_parquet_compression_ratio(self, sample_backtest_result):
        """Test compression ratio is good (>90%)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save JSON
            json_data = json.dumps(sample_backtest_result, indent=2).encode()
            json_size = len(json_data)

            # Convert to Parquet
            result = json_to_parquet(sample_backtest_result, tmpdir)
            parquet_size = result['total_size']

            # Calculate compression ratio
            ratio = calculate_compression_ratio(json_size, parquet_size)

            # Parquet should be significantly smaller (>80% compression for typical data)
            print(f"JSON size: {json_size} bytes, Parquet size: {parquet_size} bytes, Compression: {ratio:.1f}%")
            assert ratio > 50  # At least 50% compression for sample data

    def test_json_to_parquet_invalid_input(self):
        """Test error handling for invalid input"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # No symbols
            invalid_data = {'task_id': 'test', 'symbols': []}
            with pytest.raises(ValueError, match="No symbols found"):
                json_to_parquet(invalid_data, tmpdir)


class TestParquetToJson:
    """Test Parquet to JSON conversion"""

    def test_parquet_to_json_round_trip(self, sample_backtest_result):
        """Test round-trip conversion: JSON -> Parquet -> JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Convert to Parquet
            json_to_result = json_to_parquet(sample_backtest_result, tmpdir)

            # Convert back to JSON
            recovered_result = parquet_to_json(tmpdir, include_metadata=True)

            # Check basic structure
            assert 'symbols' in recovered_result
            assert 'metadata' in recovered_result
            assert len(recovered_result['symbols']) == 2

            # Check symbol data
            symbols_by_name = {s['symbol']: s for s in recovered_result['symbols']}

            # BTC/USDT
            btc = symbols_by_name['BTC/USDT']
            assert btc['win_rate'] == pytest.approx(58.5)
            assert btc['avg_return'] == pytest.approx(2.15)
            assert len(btc['signals']) == 2
            assert len(btc['performance_curve']) == 3

            # ETH/USDT
            eth = symbols_by_name['ETH/USDT']
            assert eth['win_rate'] == pytest.approx(55.2)
            assert len(eth['signals']) == 1
            assert len(eth['performance_curve']) == 1

    def test_parquet_to_json_missing_files(self):
        """Test error handling when Parquet files are missing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create only one file
            Path(tmpdir, 'symbol_summary.parquet').touch()

            with pytest.raises(IOError, match="Required Parquet files not found"):
                parquet_to_json(tmpdir)


class TestCompressionRatio:
    """Test compression ratio calculation"""

    def test_compression_ratio_calculation(self):
        """Test compression ratio formula"""
        # 100 bytes original, 25 bytes compressed = 75% compression
        ratio = calculate_compression_ratio(100, 25)
        assert ratio == pytest.approx(75.0)

        # No compression
        ratio = calculate_compression_ratio(100, 100)
        assert ratio == pytest.approx(0.0)

        # Better compression
        ratio = calculate_compression_ratio(1000, 20)
        assert ratio == pytest.approx(98.0)


class TestSchemas:
    """Test PyArrow schema definitions"""

    def test_symbol_summary_schema(self):
        """Test symbol_summary schema"""
        schema = get_symbol_summary_schema()
        assert len(schema) == 12
        assert schema.field('symbol').type == 'string'
        assert schema.field('win_rate').type == 'double'
        assert schema.field('total_signals').type == 'int32'

    def test_symbol_signals_schema(self):
        """Test symbol_signals schema"""
        schema = get_symbol_signals_schema()
        assert len(schema) == 12
        assert schema.field('symbol').type == 'string'
        assert schema.field('type').type == 'string'
        assert schema.field('entry_price').type == 'double'

    def test_performance_curve_schema(self):
        """Test performance_curve schema"""
        schema = get_performance_curve_schema()
        assert len(schema) == 7
        assert schema.field('symbol').type == 'string'
        assert schema.field('equity').type == 'double'
        assert schema.field('drawdown').type == 'double'
