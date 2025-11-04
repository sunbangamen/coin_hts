import React, { useMemo } from 'react';
import '../styles/ProfitChart.css';

/**
 * 수익률 차트 컴포넌트
 *
 * 시간에 따른 누적 수익률을 시각화합니다.
 * (실제 구현에서는 Chart.js 또는 Recharts 사용 권장)
 */
export const ProfitChart = ({ performance = null, positions = [] }) => {
  const getTotalUnrealizedPnL = useMemo(() => {
    return positions.reduce((sum, pos) => sum + (pos.unrealized_pnl || 0), 0);
  }, [positions]);

  const getPerformanceData = useMemo(() => {
    if (!performance) {
      return {
        totalPnL: getTotalUnrealizedPnL,
        pnlPercent: 0,
        openPositions: positions.length,
        winRate: 0,
      };
    }

    return {
      totalPnL: performance.total_realized_pnl || 0,
      pnlPercent: performance.total_pnl_pct || 0,
      openPositions: positions.length,
      winRate: performance.win_rate || 0,
    };
  }, [performance, positions, getTotalUnrealizedPnL]);

  const formatPrice = (price) => {
    if (typeof price !== 'number') return '-';
    return price.toLocaleString('ko-KR', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    });
  };

  const getPnLColor = (pnl) => {
    if (pnl === null || pnl === undefined) return '#888';
    return pnl >= 0 ? '#00d084' : '#ff3456';
  };

  // 간단한 미니 차트 그리기 (CSS 기반)
  const maxPnL = Math.max(
    Math.abs(getPerformanceData.totalPnL),
    1000
  );
  const chartHeight = 150;
  const barHeight =
    (Math.abs(getPerformanceData.totalPnL) / maxPnL) * chartHeight;

  return (
    <div className="profit-chart">
      <div className="profit-chart-header">
        <h2>성과 지표</h2>
      </div>

      <div className="profit-chart-content">
        <div className="metrics-grid">
          {/* 총 손익 */}
          <div className="metric-card">
            <div className="metric-label">총 실현손익</div>
            <div
              className="metric-value"
              style={{ color: getPnLColor(getPerformanceData.totalPnL) }}
            >
              ₩{formatPrice(getPerformanceData.totalPnL)}
            </div>
            <div className="metric-subtext">
              {getPerformanceData.totalPnL >= 0 ? '+' : ''}
              {getPerformanceData.pnlPercent.toFixed(2)}%
            </div>
          </div>

          {/* 오픈 포지션 수 */}
          <div className="metric-card">
            <div className="metric-label">오픈 포지션</div>
            <div className="metric-value">{getPerformanceData.openPositions}</div>
            <div className="metric-subtext">활성 포지션</div>
          </div>

          {/* 승률 */}
          <div className="metric-card">
            <div className="metric-label">승률</div>
            <div className="metric-value">
              {(getPerformanceData.winRate * 100).toFixed(1)}%
            </div>
            <div className="metric-subtext">성공률</div>
          </div>

          {/* 미실현 손익 */}
          <div className="metric-card">
            <div className="metric-label">총 미실현손익</div>
            <div
              className="metric-value"
              style={{ color: getPnLColor(getTotalUnrealizedPnL) }}
            >
              ₩{formatPrice(getTotalUnrealizedPnL)}
            </div>
            <div className="metric-subtext">현재 포지션</div>
          </div>
        </div>

        {/* 간단한 미니 차트 */}
        <div className="mini-chart">
          <div className="mini-chart-title">손익 변화</div>
          <div className="mini-chart-bar">
            <div
              className="mini-chart-bar-fill"
              style={{
                height: `${barHeight}px`,
                backgroundColor: getPnLColor(getPerformanceData.totalPnL),
                width: '100%',
              }}
            />
          </div>
          <div className="mini-chart-label">
            ₩{formatPrice(getPerformanceData.totalPnL)}
          </div>
        </div>

        {/* 참고 사항 */}
        <div className="chart-note">
          <small>
            💡 실시간 데이터 기반 (최대 1시간 지연될 수 있음)
          </small>
        </div>
      </div>
    </div>
  );
};

export default ProfitChart;
