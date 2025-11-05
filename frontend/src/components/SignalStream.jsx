import React from 'react';
import '../styles/SignalStream.css';

/**
 * 실시간 신호 스트림 컴포넌트
 *
 * BUY/SELL 신호를 시간순으로 표시합니다.
 * 신호는 WebSocket 실시간 연결을 통해서만 수신됩니다.
 */
export const SignalStream = ({ signals = [], hasRealtimeData = false }) => {
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
          // 신호가 없을 때: 상태에 따라 다른 메시지 표시
          <div className="signal-empty">
            {hasRealtimeData
              ? '신호 대기 중...'
              : '⚠️ 신호는 WebSocket 실시간 연결 시에만 수신됩니다'}
          </div>
        ) : (
          // 신호가 있을 때: 오프라인 상태 배너 + 신호 목록
          <>
            {!hasRealtimeData && (
              <div className="signal-offline-banner">
                <span className="offline-icon">⚠️</span>
                <span className="offline-message">
                  실시간 연결이 끊겨 마지막 신호만 표시 중입니다. 새로운 신호는 수신되지 않습니다.
                </span>
              </div>
            )}
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
          </>
        )}
      </div>
    </div>
  );
};

export default SignalStream;
