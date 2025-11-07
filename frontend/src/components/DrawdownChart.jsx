/**
 * DrawdownChart Component
 *
 * Task 3.3-4: Drawdown Chart (최대낙폭 차트)
 *
 * 시간에 따른 누적 낙폭(Underwater Plot)을 보여주는 영역 차트입니다.
 * 포트폴리오가 최고점에서 얼마나 내려갔는지 시각화합니다.
 */

import React, { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { calculateDrawdownData, getDrawdownStats } from '../utils/charts';

/**
 * DrawdownChart 컴포넌트
 *
 * @param {Array} performanceData - 성과곡선 데이터 (PerformancePoint[])
 *   - timestamp: string (YYYY-MM-DD)
 *   - equity: number (누적 수익률, 예: 1.05 = 5% 수익)
 *   - drawdown?: number (선택사항)
 *
 * @returns {JSX.Element|null} Drawdown 차트 또는 null
 */
const DrawdownChart = ({ performanceData = null }) => {
  // performanceData가 없으면 렌더링하지 않음
  if (!performanceData || performanceData.length === 0) {
    return null;
  }

  // useMemo를 통한 성능 최적화
  // performanceData가 변경될 때만 drawdownData를 재계산
  const drawdownData = useMemo(
    () => calculateDrawdownData(performanceData),
    [performanceData]
  );

  // 통계 정보 계산
  const stats = useMemo(
    () => getDrawdownStats(drawdownData),
    [drawdownData]
  );

  // 차트 레이아웃용 설정
  const minDrawdown = Math.min(
    0,
    Math.min(...drawdownData.map((d) => d.drawdown))
  );
  const maxDrawdown = 0;

  return (
    <div className="chart-section">
      <h3>📉 Drawdown Chart (최대낙폭)</h3>

      {/* 통계 정보 */}
      <div className="chart-info">
        <span>
          최대 낙폭: <strong>{stats.maxDrawdown.toFixed(2)}%</strong>
        </span>
        <span>
          현재 낙폭: <strong>{stats.currentDrawdown.toFixed(2)}%</strong>
        </span>
      </div>

      {/* 차트 */}
      <div className="drawdown-chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={drawdownData}
            margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-grid)" />
            <XAxis
              dataKey="timestamp"
              tick={{ fontSize: 12 }}
              interval={Math.floor(drawdownData.length / 8)}
            />
            <YAxis
              domain={[
                Math.floor(minDrawdown * 1.05),
                Math.ceil(maxDrawdown * 1.05),
              ]}
              label={{ value: '낙폭 (%)', angle: -90, position: 'insideLeft' }}
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
                if (name === 'drawdown') {
                  return `${value.toFixed(2)}%`;
                }
                return value;
              }}
              labelFormatter={(label) => `날짜: ${label}`}
            />
            <Legend wrapperStyle={{ paddingTop: '20px' }} />

            {/* 낙폭 영역 */}
            <Area
              type="monotone"
              dataKey="drawdown"
              stroke="#dc3545"
              fill="rgba(220, 53, 69, 0.3)"
              strokeWidth={2}
              dot={false}
              name="Drawdown (%)"
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* 차트 설명 */}
      <div className="chart-legend" style={{ marginTop: '15px' }}>
        <p style={{ fontSize: '12px', color: '#666', margin: '0' }}>
          💡 <strong>낙폭(Drawdown):</strong> 최고 수익률에서 얼마나 내려갔는지를
          보여줍니다. 음수 값으로 표시되며, 0에 가까울수록 좋습니다.
        </p>
      </div>
    </div>
  );
};

export default DrawdownChart;
