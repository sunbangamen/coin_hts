/**
 * Chart Data Transformation Functions - Unit Tests
 *
 * Task 3.3-4: Unit tests for chart data transformation utilities
 * Tests for calculateDrawdownData, calculateReturnsDistribution, and mergeSymbolData
 */

import { describe, it, expect } from 'vitest';
import {
  calculateDrawdownData,
  calculateReturnsDistribution,
  mergeSymbolData,
  getBinCount,
  getDrawdownStats,
  getTradeStats,
} from '../../utils/charts';

/**
 * ============================================
 * calculateDrawdownData Tests
 * ============================================
 */
describe('calculateDrawdownData', () => {
  it('should return empty array for empty input', () => {
    expect(calculateDrawdownData([])).toEqual([]);
    expect(calculateDrawdownData(null as any)).toEqual([]);
  });

  it('should calculate drawdown correctly for single point', () => {
    const data = [{ timestamp: '2024-01-01', equity: 1.0, drawdown: undefined }];
    const result = calculateDrawdownData(data);

    expect(result).toHaveLength(1);
    expect(result[0].drawdown).toBe(0);
  });

  it('should calculate drawdown correctly for increasing equity', () => {
    const data = [
      { timestamp: '2024-01-01', equity: 1.0 },
      { timestamp: '2024-01-02', equity: 1.05 },
      { timestamp: '2024-01-03', equity: 1.10 },
    ];
    const result = calculateDrawdownData(data);

    expect(result).toHaveLength(3);
    expect(result[0].drawdown).toBe(0); // First point is always 0
    expect(result[1].drawdown).toBe(0); // Still at max
    expect(result[2].drawdown).toBe(0); // Still at max
  });

  it('should calculate drawdown correctly for decreasing equity', () => {
    const data = [
      { timestamp: '2024-01-01', equity: 1.0 },
      { timestamp: '2024-01-02', equity: 1.10 },
      { timestamp: '2024-01-03', equity: 1.00 }, // Back to start
    ];
    const result = calculateDrawdownData(data);

    expect(result).toHaveLength(3);
    expect(result[0].drawdown).toBe(0);
    expect(result[1].drawdown).toBe(0);
    expect(result[2].drawdown).toBeCloseTo(-9.09, 1); // (1.00 - 1.10) / 1.10 * 100
  });

  it('should preserve timestamp and equity values', () => {
    const data = [
      { timestamp: '2024-01-01', equity: 1.05 },
      { timestamp: '2024-01-02', equity: 1.10 },
    ];
    const result = calculateDrawdownData(data);

    expect(result[0].timestamp).toBe('2024-01-01');
    expect(result[0].equity).toBe(1.05);
    expect(result[1].timestamp).toBe('2024-01-02');
    expect(result[1].equity).toBe(1.10);
  });

  it('should handle large drawdowns', () => {
    const data = [
      { timestamp: '2024-01-01', equity: 1.0 },
      { timestamp: '2024-01-02', equity: 2.0 },
      { timestamp: '2024-01-03', equity: 0.5 }, // 75% drawdown
    ];
    const result = calculateDrawdownData(data);

    expect(result[2].drawdown).toBeCloseTo(-75, 0);
  });
});

/**
 * ============================================
 * getBinCount Tests
 * ============================================
 */
describe('getBinCount', () => {
  it('should return 5 bins for signals < 30', () => {
    expect(getBinCount(0)).toBe(5);
    expect(getBinCount(29)).toBe(5);
  });

  it('should return 10 bins for signals 30-100', () => {
    expect(getBinCount(30)).toBe(10);
    expect(getBinCount(100)).toBe(10);
  });

  it('should return 15 bins for signals 101-500', () => {
    expect(getBinCount(101)).toBe(15);
    expect(getBinCount(500)).toBe(15);
  });

  it('should return 20 bins for signals > 500', () => {
    expect(getBinCount(501)).toBe(20);
    expect(getBinCount(1000)).toBe(20);
  });
});

/**
 * ============================================
 * calculateReturnsDistribution Tests
 * ============================================
 */
describe('calculateReturnsDistribution', () => {
  it('should return empty array for empty signals', () => {
    expect(calculateReturnsDistribution([])).toEqual([]);
    expect(calculateReturnsDistribution(null as any)).toEqual([]);
  });

  it('should handle single signal', () => {
    const signals = [
      {
        symbol: 'BTC',
        type: 'buy',
        timestamp: '2024-01-01',
        entry_price: 100,
        exit_price: 110,
        return_pct: 0.10,
      },
    ];
    const result = calculateReturnsDistribution(signals);

    expect(result).toHaveLength(1);
    expect(result[0].count).toBe(1);
    expect(result[0].percentage).toBe(100);
  });

  it('should handle all same return values', () => {
    const signals = Array(10).fill(null).map((_, i) => ({
      symbol: 'BTC',
      type: 'buy',
      timestamp: `2024-01-${String(i + 1).padStart(2, '0')}`,
      entry_price: 100,
      exit_price: 105,
      return_pct: 0.05, // All 5%
    }));
    const result = calculateReturnsDistribution(signals);

    expect(result).toHaveLength(1);
    expect(result[0].count).toBe(10);
  });

  it('should classify returns into bins correctly', () => {
    const signals = [
      { return_pct: -0.05 }, // -5%
      { return_pct: 0.0 },   // 0%
      { return_pct: 0.05 },  // 5%
    ].map((s, i) => ({
      ...s,
      symbol: 'BTC',
      type: 'buy',
      timestamp: `2024-01-${String(i + 1).padStart(2, '0')}`,
      entry_price: 100,
      exit_price: 100 * (1 + (s.return_pct || 0)),
    })) as any;

    const result = calculateReturnsDistribution(signals);

    // Should have 5 bins for 3 signals
    expect(result.length).toBeGreaterThan(0);
    const totalCount = result.reduce((sum, bin) => sum + bin.count, 0);
    expect(totalCount).toBe(3);
  });

  it('should calculate percentages correctly', () => {
    const signals = Array(20).fill(null).map((_, i) => ({
      symbol: 'BTC',
      type: 'buy',
      timestamp: `2024-01-${String(i + 1).padStart(2, '0')}`,
      entry_price: 100,
      exit_price: 105 + (i % 5) * 0.5,
      return_pct: 0.05 + (i % 5) * 0.005,
    }));

    const result = calculateReturnsDistribution(signals);
    const totalPercentage = result.reduce((sum, bin) => sum + bin.percentage, 0);

    // Total percentage should be approximately 100
    expect(totalPercentage).toBeCloseTo(100, 0);
  });
});

/**
 * ============================================
 * mergeSymbolData Tests
 * ============================================
 */
describe('mergeSymbolData', () => {
  it('should return empty array for empty symbols', () => {
    expect(mergeSymbolData([])).toEqual([]);
    expect(mergeSymbolData(null as any)).toEqual([]);
  });

  it('should handle single symbol', () => {
    const symbols = [
      {
        symbol: 'BTC_KRW',
        performance_curve: [
          { timestamp: '2024-01-01', equity: 1.05 },
          { timestamp: '2024-01-02', equity: 1.10 },
        ],
      },
    ];

    const result = mergeSymbolData(symbols as any);

    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({
      timestamp: '2024-01-01',
      'BTC_KRW': 105, // 1.05 * 100
    });
    expect(result[1]).toEqual({
      timestamp: '2024-01-02',
      'BTC_KRW': 110, // 1.10 * 100
    });
  });

  it('should merge multiple symbols correctly', () => {
    const symbols = [
      {
        symbol: 'BTC_KRW',
        performance_curve: [
          { timestamp: '2024-01-01', equity: 1.05 },
          { timestamp: '2024-01-02', equity: 1.10 },
        ],
      },
      {
        symbol: 'ETH_KRW',
        performance_curve: [
          { timestamp: '2024-01-01', equity: 1.02 },
          { timestamp: '2024-01-02', equity: 1.08 },
        ],
      },
    ];

    const result = mergeSymbolData(symbols as any);

    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({
      timestamp: '2024-01-01',
      'BTC_KRW': 105,
      'ETH_KRW': 102,
    });
    expect(result[1]).toEqual({
      timestamp: '2024-01-02',
      'BTC_KRW': 110,
      'ETH_KRW': 108,
    });
  });

  it('should handle symbols with different timestamps', () => {
    const symbols = [
      {
        symbol: 'BTC_KRW',
        performance_curve: [
          { timestamp: '2024-01-01', equity: 1.05 },
          { timestamp: '2024-01-03', equity: 1.15 },
        ],
      },
      {
        symbol: 'ETH_KRW',
        performance_curve: [
          { timestamp: '2024-01-02', equity: 1.02 },
          { timestamp: '2024-01-04', equity: 1.12 },
        ],
      },
    ];

    const result = mergeSymbolData(symbols as any);

    // Should have 4 unique timestamps
    expect(result.length).toBe(4);
    expect(result.map((p) => p.timestamp)).toEqual([
      '2024-01-01',
      '2024-01-02',
      '2024-01-03',
      '2024-01-04',
    ]);
  });

  it('should sort timestamps correctly', () => {
    const symbols = [
      {
        symbol: 'BTC_KRW',
        performance_curve: [
          { timestamp: '2024-01-03', equity: 1.15 },
          { timestamp: '2024-01-01', equity: 1.05 },
        ],
      },
    ];

    const result = mergeSymbolData(symbols as any);

    expect(result[0].timestamp).toBe('2024-01-01');
    expect(result[1].timestamp).toBe('2024-01-03');
  });
});

/**
 * ============================================
 * getDrawdownStats Tests
 * ============================================
 */
describe('getDrawdownStats', () => {
  it('should return 0 for empty data', () => {
    const result = getDrawdownStats([]);
    expect(result.maxDrawdown).toBe(0);
    expect(result.currentDrawdown).toBe(0);
  });

  it('should calculate stats correctly', () => {
    const drawdownData = [
      { drawdown: 0 },
      { drawdown: -5.5 },
      { drawdown: -10.2 },
      { drawdown: -3.1 },
    ];

    const result = getDrawdownStats(drawdownData);

    expect(result.maxDrawdown).toBe(-10.2); // Minimum drawdown
    expect(result.currentDrawdown).toBe(-3.1); // Last value
  });
});

/**
 * ============================================
 * getTradeStats Tests
 * ============================================
 */
describe('getTradeStats', () => {
  it('should return 0 for empty signals', () => {
    const result = getTradeStats([]);
    expect(result.totalTrades).toBe(0);
    expect(result.avgReturn).toBe(0);
    expect(result.winRate).toBe(0);
  });

  it('should calculate stats for single trade', () => {
    const signals = [
      {
        symbol: 'BTC',
        type: 'buy',
        timestamp: '2024-01-01',
        entry_price: 100,
        exit_price: 110,
        return_pct: 0.10,
      },
    ];

    const result = getTradeStats(signals as any);

    expect(result.totalTrades).toBe(1);
    expect(result.avgReturn).toBe(10); // 0.10 * 100
    expect(result.winRate).toBe(100);
  });

  it('should calculate win rate correctly', () => {
    const signals = [
      { return_pct: 0.05 },  // Win
      { return_pct: -0.03 }, // Loss
      { return_pct: 0.02 },  // Win
      { return_pct: 0.00 },  // Break-even (not a win)
    ].map((s, i) => ({
      ...s,
      symbol: 'BTC',
      type: 'buy',
      timestamp: `2024-01-${String(i + 1).padStart(2, '0')}`,
      entry_price: 100,
      exit_price: 100 * (1 + (s.return_pct || 0)),
    })) as any;

    const result = getTradeStats(signals);

    expect(result.totalTrades).toBe(4);
    expect(result.winRate).toBe(50); // 2 wins out of 4
  });

  it('should calculate average return correctly', () => {
    const signals = [
      { return_pct: 0.10 }, // 10%
      { return_pct: 0.05 }, // 5%
      { return_pct: -0.05 }, // -5%
    ].map((s, i) => ({
      ...s,
      symbol: 'BTC',
      type: 'buy',
      timestamp: `2024-01-${String(i + 1).padStart(2, '0')}`,
      entry_price: 100,
      exit_price: 100 * (1 + (s.return_pct || 0)),
    })) as any;

    const result = getTradeStats(signals);

    // (10 + 5 + (-5)) / 3 = 10 / 3 = 3.33%
    expect(result.avgReturn).toBeCloseTo(3.33, 1);
  });
});
