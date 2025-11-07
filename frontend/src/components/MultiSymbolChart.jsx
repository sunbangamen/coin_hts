/**
 * MultiSymbolChart Component
 *
 * Task 3.3-4: Multi-Symbol Chart (다중 심볼 비교)
 *
 * 단일 백테스트 실행에서 여러 심볼의 성과곡선을 동시에 표시합니다.
 * 심볼 선택/해제 기능으로 유연한 비교가 가능합니다.
 */

import React, { useState, useMemo } from 'react';
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { mergeSymbolData, getSymbolColor } from '../utils/charts';

/**
 * MultiSymbolChart 컴포넌트
 *
 * @param {Array} symbols - 심볼 결과 배열 (SymbolResult[])
 *   - symbol: string
 *   - performance_curve?: Array
 *     - timestamp: string
 *     - equity: number
 *
 * @returns {JSX.Element|null} Multi-Symbol 차트 또는 null
 */
const MultiSymbolChart = ({ symbols = null }) => {
  // 심볼 수 <= 1일 때는 렌더링하지 않음
  if (!symbols || symbols.length <= 1) {
    return null;
  }

  // 성능곡선 데이터가 있는 심볼만 필터링
  const symbolsWithCurve = symbols.filter(
    (s) => s.performance_curve && s.performance_curve.length > 0
  );

  // 심볼이 1개 이하이면 렌더링하지 않음
  if (symbolsWithCurve.length <= 1) {
    return null;
  }

  // useMemo를 통한 성능 최적화
  const mergedData = useMemo(
    () => mergeSymbolData(symbolsWithCurve),
    [symbolsWithCurve]
  );

  // 심볼 선택 상태 관리 (초기값: 모든 심볼 선택)
  const [selectedSymbols, setSelectedSymbols] = useState(
    symbolsWithCurve.map((s) => s.symbol)
  );

  // 심볼 토글 함수 (최소 1개 이상 선택 유지)
  const toggleSymbol = (symbol) => {
    if (selectedSymbols.includes(symbol)) {
      // 선택 해제하되, 최소 1개 선택 유지
      if (selectedSymbols.length > 1) {
        setSelectedSymbols(selectedSymbols.filter((s) => s !== symbol));
      }
    } else {
      // 선택 추가
      setSelectedSymbols([...selectedSymbols, symbol]);
    }
  };

  // 선택된 심볼 데이터만 필터링
  const filteredData = useMemo(() => {
    if (selectedSymbols.length === 0) {
      return mergedData;
    }
    return mergedData.map((point) => {
      const filtered = { timestamp: point.timestamp };
      selectedSymbols.forEach((symbol) => {
        if (point[symbol] !== undefined) {
          filtered[symbol] = point[symbol];
        }
      });
      return filtered;
    });
  }, [mergedData, selectedSymbols]);

  return (
    <div className="chart-section">
      <h3>🔄 Multi-Symbol Performance Comparison</h3>

      {/* 심볼 선택 체크박스 */}
      <div className="multi-symbol-selector">
        {symbolsWithCurve.map((symbol, index) => (
          <label
            key={symbol.symbol}
            className={`multi-symbol-checkbox ${
              selectedSymbols.length === 1 && selectedSymbols.includes(symbol.symbol)
                ? 'disabled'
                : ''
            }`}
          >
            <input
              type="checkbox"
              checked={selectedSymbols.includes(symbol.symbol)}
              onChange={() => toggleSymbol(symbol.symbol)}
              disabled={
                selectedSymbols.length === 1 &&
                selectedSymbols.includes(symbol.symbol)
              }
            />
            <span
              style={{
                display: 'inline-block',
                width: '12px',
                height: '12px',
                backgroundColor: getSymbolColor(index),
                borderRadius: '2px',
                marginRight: '6px',
              }}
            ></span>
            {symbol.symbol}
          </label>
        ))}
      </div>

      {/* 통계 정보 */}
      <div className="chart-info">
        <span>
          선택된 심볼: <strong>{selectedSymbols.length}개</strong>
        </span>
        <span>
          데이터 포인트: <strong>{filteredData.length}개</strong>
        </span>
      </div>

      {/* 차트 */}
      <div className="multi-symbol-chart-canvas">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={filteredData}
            margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-grid)" />
            <XAxis
              dataKey="timestamp"
              tick={{ fontSize: 12 }}
              interval={Math.floor(filteredData.length / 8)}
            />
            <YAxis
              label={{
                value: '누적 수익률 (%)',
                angle: -90,
                position: 'insideLeft',
              }}
              tick={{ fontSize: 12 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid var(--color-grid)',
                borderRadius: '4px',
                padding: '8px',
              }}
              formatter={(value) => {
                if (typeof value === 'number') {
                  return `${value.toFixed(2)}%`;
                }
                return value;
              }}
              labelFormatter={(label) => `날짜: ${label}`}
            />
            <Legend wrapperStyle={{ paddingTop: '20px' }} />

            {/* 선택된 심볼별 Line */}
            {selectedSymbols.map((symbol, index) => (
              <Line
                key={`line-${symbol}`}
                type="monotone"
                dataKey={symbol}
                stroke={getSymbolColor(
                  symbolsWithCurve.findIndex((s) => s.symbol === symbol)
                )}
                strokeWidth={2}
                dot={false}
                name={symbol}
                isAnimationActive={false}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* 차트 설명 */}
      <div style={{ marginTop: '15px' }}>
        <p style={{ fontSize: '12px', color: '#666', margin: '0' }}>
          💡 <strong>다중 심볼 비교:</strong> 체크박스로 심볼을 선택/해제하여
          비교할 수 있습니다. 최소 1개 심볼은 항상 표시됩니다.
        </p>
      </div>
    </div>
  );
};

export default MultiSymbolChart;
