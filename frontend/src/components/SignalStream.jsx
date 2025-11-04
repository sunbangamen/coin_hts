import React from 'react';
import '../styles/SignalStream.css';

/**
 * 실시간 신호 스트림 컴포넌트
 *
 * BUY/SELL 신호를 시간순으로 표시합니다.
 */
export const SignalStream = ({ signals = [] }) => {
  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('ko-KR');
  };

  const formatPrice = (price) => {
    if (typeof price !== 'number') return '-';
    return price.toLocaleString('ko-KR', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    });
  };

  const getSideColor = (side) => {
    return side === 'BUY' ? '#00d084' : '#ff3456';
  };

  return (
    <div className="signal-stream">
      <div className="signal-stream-header">
        <h2>신호 스트림</h2>
        <span className="signal-count">{signals.length}개 신호</span>
      </div>

      <div className="signal-stream-content">
        {signals.length === 0 ? (
          <div className="signal-empty">신호 대기 중...</div>
        ) : (
          <div className="signal-list">
            {signals.map((signal, idx) => (
              <div key={idx} className="signal-item">
                <div className="signal-time">{formatTime(signal.timestamp)}</div>
                <div className="signal-details">
                  <span className="signal-symbol">{signal.symbol}</span>
                  <span className="signal-strategy">{signal.strategy}</span>
                </div>
                <div className="signal-action">
                  <span
                    className={`signal-side ${signal.side.toLowerCase()}`}
                    style={{ color: getSideColor(signal.side) }}
                  >
                    {signal.side}
                  </span>
                </div>
                <div className="signal-info">
                  <span className="signal-price">₩{formatPrice(signal.price)}</span>
                  <span className="signal-confidence">
                    신뢰도: {(signal.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default SignalStream;
