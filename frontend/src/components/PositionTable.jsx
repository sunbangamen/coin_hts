import React from 'react';
import '../styles/PositionTable.css';

/**
 * 현재 오픈 포지션 테이블 컴포넌트
 *
 * 실시간으로 업데이트되는 포지션 목록을 표시합니다.
 */
export const PositionTable = ({ positions = [] }) => {
  const formatPrice = (price) => {
    if (typeof price !== 'number') return '-';
    return price.toLocaleString('ko-KR', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    });
  };

  const formatPnL = (pnl) => {
    if (typeof pnl !== 'number') return '-';
    const sign = pnl >= 0 ? '+' : '';
    return sign + pnl.toLocaleString('ko-KR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  const formatPnLPercent = (pct) => {
    if (typeof pct !== 'number') return '-';
    const sign = pct >= 0 ? '+' : '';
    return sign + pct.toFixed(2) + '%';
  };

  const getPnLColor = (pnl) => {
    if (pnl === null || pnl === undefined) return '#888';
    return pnl >= 0 ? '#00d084' : '#ff3456';
  };

  const getTotalUnrealizedPnL = () => {
    return positions.reduce((sum, pos) => sum + (pos.unrealized_pnl || 0), 0);
  };

  return (
    <div className="position-table">
      <div className="position-table-header">
        <h2>현재 포지션</h2>
        <div className="position-stats">
          <span className="position-count">{positions.length}개 오픈</span>
          <span
            className="total-unrealized-pnl"
            style={{ color: getPnLColor(getTotalUnrealizedPnL()) }}
          >
            총 미실현손익: ₩{formatPrice(getTotalUnrealizedPnL())}
          </span>
        </div>
      </div>

      <div className="position-table-content">
        {positions.length === 0 ? (
          <div className="position-empty">오픈 포지션이 없습니다</div>
        ) : (
          <table className="position-list">
            <thead>
              <tr>
                <th>심볼</th>
                <th>전략</th>
                <th>수량</th>
                <th>진입가</th>
                <th>현재가</th>
                <th>미실현손익</th>
                <th>손익률</th>
                <th>진입시간</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((position) => (
                <tr key={position.position_id} className="position-row">
                  <td className="position-symbol">{position.symbol}</td>
                  <td className="position-strategy">{position.strategy}</td>
                  <td className="position-quantity">
                    {position.quantity ? position.quantity.toFixed(4) : '-'}
                  </td>
                  <td className="position-entry-price">
                    ₩{formatPrice(position.entry_price)}
                  </td>
                  <td className="position-current-price">
                    ₩{formatPrice(position.current_price)}
                  </td>
                  <td
                    className="position-unrealized-pnl"
                    style={{ color: getPnLColor(position.unrealized_pnl) }}
                  >
                    ₩{formatPnL(position.unrealized_pnl)}
                  </td>
                  <td
                    className="position-unrealized-pnl-pct"
                    style={{ color: getPnLColor(position.unrealized_pnl) }}
                  >
                    {formatPnLPercent(position.unrealized_pnl_pct)}
                  </td>
                  <td className="position-entry-time">
                    {new Date(position.entry_time).toLocaleTimeString('ko-KR')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default PositionTable;
