/**
 * ReturnsDistributionChart Component
 *
 * Task 3.3-4: Returns Distribution Chart (수익률 분포 히스토그램)
 *
 * 각 거래의 수익률을 구간별로 분류하여 히스토그램으로 표시합니다.
 * 수익성 분포를 한눈에 파악할 수 있습니다.
 */

import React, { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import {
  calculateReturnsDistribution,
  getTradeStats,
} from '../utils/charts';

/**
 * ReturnsDistributionChart 컴포넌트
 *
 * @param {Array} signals - 거래 신호 배열 (APISignal[])
 *   - symbol: string
 *   - type: string
 *   - timestamp: string
 *   - entry_price: number
 *   - exit_price: number
 *   - return_pct: number (수익률, 예: 0.03 = 3%)
 *
 * @returns {JSX.Element|null} Returns Distribution 차트 또는 null
 */
const ReturnsDistributionChart = ({ signals = null }) => {
  // 신호가 없으면 "데이터 없음" 카드 표시
  if (!signals || signals.length === 0) {
    return (
      <div className="chart-section">
        <h3>📊 Returns Distribution (수익률 분포)</h3>
        <div className="chart-empty">
          거래 신호가 없습니다.
        </div>
      </div>
    );
  }

  // useMemo를 통한 성능 최적화
  // signals이 변경될 때만 distributionData를 재계산
  const distributionData = useMemo(
    () => calculateReturnsDistribution(signals),
    [signals]
  );

  // 거래 통계 계산
  const stats = useMemo(() => getTradeStats(signals), [signals]);

  // 색상 결정 (양수/음수)
  const getBarColor = (dataPoint) => {
    const rangeValue = parseFloat(dataPoint.range);
    return rangeValue >= 0
      ? 'var(--color-profit)'
      : 'var(--color-loss)';
  };

  return (
    <div className="chart-section">
      <h3>📊 Returns Distribution (수익률 분포)</h3>

      {/* 통계 정보 */}
      <div className="chart-info">
        <span>
          총 거래: <strong>{stats.totalTrades}건</strong>
        </span>
        <span>
          평균 수익률:
          <strong
            style={{
              color:
                stats.avgReturn >= 0
                  ? 'var(--color-profit)'
                  : 'var(--color-loss)',
            }}
          >
            {stats.avgReturn >= 0 ? '+' : ''}
            {stats.avgReturn.toFixed(2)}%
          </strong>
        </span>
        <span>
          승률: <strong>{stats.winRate.toFixed(1)}%</strong>
        </span>
      </div>

      {/* 차트 */}
      <div className="returns-distribution-container">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={distributionData}
            margin={{ top: 5, right: 30, left: 0, bottom: 50 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-grid)" />
            <XAxis
              dataKey="range"
              angle={-45}
              textAnchor="end"
              height={80}
              tick={{ fontSize: 11 }}
            />
            <YAxis
              label={{
                value: '거래 수 (건)',
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
              formatter={(value, name) => {
                if (name === 'count') {
                  return [`${value}건`, '거래 수'];
                } else if (name === 'percentage') {
                  return [`${value}%`, '비율'];
                }
                return value;
              }}
              labelFormatter={(label) => `수익률: ${label}`}
            />
            <Legend wrapperStyle={{ paddingTop: '20px' }} />

            {/* Bar with conditional colors */}
            <Bar dataKey="count" name="거래 수 (건)" radius={[8, 8, 0, 0]}>
              {distributionData.map((dataPoint, idx) => (
                <Cell
                  key={`cell-${idx}`}
                  fill={getBarColor(dataPoint)}
                  opacity={0.8}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 차트 설명 */}
      <div style={{ marginTop: '15px' }}>
        <p style={{ fontSize: '12px', color: '#666', margin: '0' }}>
          💡 <strong>수익률 분포:</strong> 각 거래의 수익률을 구간별로 분류한
          히스토그램입니다. 녹색(수익)과 빨강(손실) 바로 분포를 확인할 수
          있습니다.
        </p>
      </div>
    </div>
  );
};

export default ReturnsDistributionChart;
