import React, { useState, useEffect } from 'react';
import useSimulation from '../hooks/useSimulation';
import SignalStream from './SignalStream';
import PositionTable from './PositionTable';
import ProfitChart from './ProfitChart';
import '../styles/SimulationDashboard.css';

/**
 * 실시간 시뮬레이션 대시보드
 *
 * 신호, 포지션, 성과를 실시간으로 모니터링합니다.
 */
export const SimulationDashboard = ({
  wsUrl = 'ws://localhost:8001',
  apiUrl = 'http://localhost:8000/api',
  symbols = ['KRW-BTC', 'KRW-ETH'],
}) => {
  const {
    connected,
    signals,
    positions,
    performance,
    error,
    simulationStatus,
    subscribe,
    disconnect,
    clearSignals,
  } = useSimulation(wsUrl);

  const [selectedSymbols, setSelectedSymbols] = useState(symbols);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [initialDataLoaded, setInitialDataLoaded] = useState(false);
  const [restPollingInterval, setRestPollingInterval] = useState(null);

  // 초기 데이터 로딩 (REST API)
  useEffect(() => {
    const loadInitialData = async () => {
      try {
        // 시뮬레이션 상태 조회
        const statusRes = await fetch(`${apiUrl}/simulation/status`);
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          console.log('Initial simulation status:', statusData);
        }

        // 현재 포지션 조회
        const positionsRes = await fetch(`${apiUrl}/simulation/positions`);
        if (positionsRes.ok) {
          const positionsData = await positionsRes.json();
          console.log('Initial positions:', positionsData);
        }

        // 거래 이력 조회
        const historyRes = await fetch(`${apiUrl}/simulation/history?limit=50`);
        if (historyRes.ok) {
          const historyData = await historyRes.json();
          console.log('Initial trade history:', historyData);
        }

        setInitialDataLoaded(true);
      } catch (err) {
        console.error('Failed to load initial data:', err);
      }
    };

    loadInitialData();
  }, [apiUrl]);

  // 심볼 구독
  useEffect(() => {
    if (connected && selectedSymbols.length > 0) {
      subscribe(selectedSymbols);
    }
  }, [connected, selectedSymbols, subscribe]);

  // 자동 새로고침 (REST 폴링)
  useEffect(() => {
    if (!autoRefresh || !initialDataLoaded) {
      if (restPollingInterval) {
        clearInterval(restPollingInterval);
        setRestPollingInterval(null);
      }
      return;
    }

    // 30초마다 데이터 갱신
    const pollInterval = setInterval(async () => {
      try {
        // 포지션 갱신
        const positionsRes = await fetch(`${apiUrl}/simulation/positions`);
        if (positionsRes.ok) {
          const positionsData = await positionsRes.json();
          console.log('Polled positions:', positionsData);
        }

        // 성과 데이터 갱신
        const historyRes = await fetch(`${apiUrl}/simulation/history?limit=50`);
        if (historyRes.ok) {
          const historyData = await historyRes.json();
          console.log('Polled history:', historyData);
        }
      } catch (err) {
        console.error('Failed to poll data:', err);
      }
    }, 30000);

    setRestPollingInterval(pollInterval);

    return () => {
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [autoRefresh, initialDataLoaded, apiUrl]);

  const handleSymbolToggle = (symbol) => {
    setSelectedSymbols((prev) => {
      if (prev.includes(symbol)) {
        return prev.filter((s) => s !== symbol);
      } else {
        return [...prev, symbol];
      }
    });
  };

  const handleDisconnect = () => {
    disconnect();
  };

  const handleClearSignals = () => {
    clearSignals();
  };

  return (
    <div className="simulation-dashboard">
      <div className="dashboard-header">
        <div className="dashboard-title">
          <h1>실시간 거래 시뮬레이션</h1>
          <div className="connection-status">
            <span
              className={`status-indicator ${connected ? 'connected' : 'disconnected'}`}
            />
            <span className="status-text">
              {connected ? '연결됨' : '연결 끊김'}
            </span>
          </div>
        </div>

        {error && (
          <div className="error-banner">
            <span className="error-icon">⚠️</span>
            <span className="error-message">{error}</span>
          </div>
        )}
      </div>

      <div className="dashboard-controls">
        <div className="control-group">
          <label>모니터링 심볼:</label>
          <div className="symbol-buttons">
            {['KRW-BTC', 'KRW-ETH', 'KRW-XRP'].map((symbol) => (
              <button
                key={symbol}
                className={`symbol-button ${
                  selectedSymbols.includes(symbol) ? 'active' : ''
                }`}
                onClick={() => handleSymbolToggle(symbol)}
                disabled={!connected}
              >
                {symbol}
              </button>
            ))}
          </div>
        </div>

        <div className="control-group">
          <label>
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              disabled={!connected}
            />
            자동 새로고침
          </label>
        </div>

        <div className="control-buttons">
          <button
            className="btn btn-secondary"
            onClick={handleClearSignals}
            disabled={signals.length === 0}
          >
            신호 지우기
          </button>
          <button
            className="btn btn-danger"
            onClick={handleDisconnect}
            disabled={!connected}
          >
            연결 끊기
          </button>
        </div>
      </div>

      {simulationStatus && (
        <div className="simulation-info">
          <div className="info-item">
            <span className="info-label">세션:</span>
            <span className="info-value">{simulationStatus.session_id || '-'}</span>
          </div>
          <div className="info-item">
            <span className="info-label">상태:</span>
            <span className="info-value">
              {simulationStatus.is_running ? '실행 중' : '중지됨'}
            </span>
          </div>
          <div className="info-item">
            <span className="info-label">WebSocket 클라이언트:</span>
            <span className="info-value">
              {simulationStatus.websocket_clients || 0}개
            </span>
          </div>
        </div>
      )}

      <div className="dashboard-grid">
        <div className="dashboard-panel profit-panel">
          <ProfitChart performance={performance} positions={positions} />
        </div>

        <div className="dashboard-panel signals-panel">
          <SignalStream signals={signals} />
        </div>

        <div className="dashboard-panel positions-panel">
          <PositionTable positions={positions} />
        </div>
      </div>

      <div className="dashboard-footer">
        <small>
          마지막 업데이트: {new Date().toLocaleTimeString('ko-KR')}
        </small>
      </div>
    </div>
  );
};

export default SimulationDashboard;
