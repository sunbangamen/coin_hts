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
 *
 * @param {string} wsUrl WebSocket 서버 URL
 * @param {string} apiUrl REST API 서버 URL
 * @param {string[]} symbols 모니터링 심볼 목록
 * @param {string} token JWT 인증 토큰 (props 또는 localStorage에서 자동 읽음)
 */
export const SimulationDashboard = ({
  wsUrl = 'ws://localhost:8001',
  apiUrl = 'http://localhost:8000/api',
  symbols = ['KRW-BTC', 'KRW-ETH'],
  token: tokenProp = null,
}) => {
  // 토큰 관리: props > localStorage > null
  const [token, setToken] = useState(() => {
    if (tokenProp) {
      return tokenProp;
    }
    try {
      const stored = localStorage.getItem('simulation_token');
      return stored || null;
    } catch (err) {
      console.warn('Failed to read token from localStorage:', err);
      return null;
    }
  });

  // 토큰 입력 필드 상태 (배너가 유지되도록 별도 관리)
  const [tokenInput, setTokenInput] = useState('');

  const {
    connected,
    authenticated,
    hasRealtimeData,
    signals,
    positions,
    performance,
    error,
    simulationStatus,
    subscribe,
    disconnect,
    clearSignals,
  } = useSimulation(wsUrl, { token });

  const [selectedSymbols, setSelectedSymbols] = useState(symbols);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [initialDataLoaded, setInitialDataLoaded] = useState(false);
  const [restPollingInterval, setRestPollingInterval] = useState(null);

  // REST/WebSocket 통합 상태
  const [restStatus, setRestStatus] = useState(null);
  const [restPositions, setRestPositions] = useState([]);
  const [restHistory, setRestHistory] = useState([]);
  const [restPerformance, setRestPerformance] = useState(null);

  // 통합 포지션 데이터 (WebSocket 유효하면 사용, 아니면 REST 사용)
  const mergedPositions = hasRealtimeData && positions.length > 0 ? positions : restPositions;

  // 통합 성과 데이터 (WebSocket 유효하면 사용, 아니면 REST 사용)
  const mergedPerformance = hasRealtimeData && performance ? performance : restPerformance;

  // 통합 시뮬레이션 상태 (WebSocket 유효하면 사용, 아니면 REST 사용)
  const mergedSimulationStatus = hasRealtimeData && simulationStatus ? simulationStatus : restStatus;

  // 초기 데이터 로딩 (REST API)
  useEffect(() => {
    const loadInitialData = async () => {
      try {
        // 시뮬레이션 상태 조회
        const statusRes = await fetch(`${apiUrl}/simulation/status`);
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          console.log('Initial simulation status:', statusData);
          setRestStatus(statusData);
        }

        // 현재 포지션 조회
        const positionsRes = await fetch(`${apiUrl}/simulation/positions`);
        if (positionsRes.ok) {
          const positionsData = await positionsRes.json();
          console.log('Initial positions:', positionsData);
          // positions 배열이 있으면 저장, 아니면 data 필드 확인
          const positionList = Array.isArray(positionsData) ? positionsData : positionsData.positions || [];
          setRestPositions(positionList);
        }

        // 거래 이력 조회
        const historyRes = await fetch(`${apiUrl}/simulation/history?limit=50`);
        if (historyRes.ok) {
          const historyData = await historyRes.json();
          console.log('Initial trade history:', historyData);
          // trades 배열이 있으면 저장, 아니면 data 필드 확인
          const tradeList = Array.isArray(historyData) ? historyData : historyData.trades || [];
          setRestHistory(tradeList);

          // REST 거래 이력으로부터 성과 지표 계산
          if (tradeList.length > 0) {
            const totalPnl = tradeList.reduce((sum, trade) => sum + (trade.realized_pnl || 0), 0);
            const winCount = tradeList.filter((t) => t.realized_pnl > 0).length;
            const loseCount = tradeList.filter((t) => t.realized_pnl < 0).length;
            const winRate = (winCount / tradeList.length) * 100;

            setRestPerformance({
              timestamp: new Date().toISOString(),
              total_pnl: Math.round(totalPnl * 100) / 100,
              total_pnl_pct: Math.round((totalPnl / (tradeList.length * 100)) * 100) / 100,
              win_rate: Math.round(winRate * 100) / 100,
              max_drawdown: 0, // 간단한 계산
              total_trades: tradeList.length,
              win_count: winCount,
              lose_count: loseCount,
            });
          }
        }

        setInitialDataLoaded(true);
      } catch (err) {
        console.error('Failed to load initial data:', err);
        // 초기 로딩 실패해도 진행 (WebSocket으로 데이터 수신 가능)
        setInitialDataLoaded(true);
      }
    };

    loadInitialData();
  }, [apiUrl]);

  // 재연결 시 데이터 복구 (REST 상태로 초기화)
  useEffect(() => {
    if (connected && !authenticated) {
      // 연결 중이지만 아직 인증되지 않은 상태
      console.log('Waiting for authentication...');
    } else if (authenticated && restPositions.length > 0) {
      // 인증 완료되면 초기 REST 데이터를 기반으로 복구
      console.log('Authentication complete, ready to receive WebSocket events');
    }
  }, [connected, authenticated, restPositions.length]);

  // 심볼 구독
  useEffect(() => {
    if (authenticated && selectedSymbols.length > 0) {
      subscribe(selectedSymbols);
    }
  }, [authenticated, selectedSymbols, subscribe]);

  // 자동 새로고침 (REST 폴링) - WebSocket 이벤트가 없을 때 사용
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
        // 시뮬레이션 상태 갱신
        const statusRes = await fetch(`${apiUrl}/simulation/status`);
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          console.log('Polled simulation status:', statusData);
          setRestStatus(statusData);
        }

        // 포지션 갱신 (WebSocket 데이터가 없을 때만 사용)
        if (!hasRealtimeData) {
          const positionsRes = await fetch(`${apiUrl}/simulation/positions`);
          if (positionsRes.ok) {
            const positionsData = await positionsRes.json();
            console.log('Polled positions:', positionsData);
            const positionList = Array.isArray(positionsData) ? positionsData : positionsData.positions || [];
            setRestPositions(positionList);
          }
        }

        // 거래 이력 갱신 (항상 갱신)
        const historyRes = await fetch(`${apiUrl}/simulation/history?limit=50`);
        if (historyRes.ok) {
          const historyData = await historyRes.json();
          console.log('Polled history:', historyData);
          const tradeList = Array.isArray(historyData) ? historyData : historyData.trades || [];
          setRestHistory(tradeList);

          // REST 거래 이력으로부터 성과 지표 갱신
          if (tradeList.length > 0 && !hasRealtimeData) {
            const totalPnl = tradeList.reduce((sum, trade) => sum + (trade.realized_pnl || 0), 0);
            const winCount = tradeList.filter((t) => t.realized_pnl > 0).length;
            const loseCount = tradeList.filter((t) => t.realized_pnl < 0).length;
            const winRate = (winCount / tradeList.length) * 100;

            setRestPerformance({
              timestamp: new Date().toISOString(),
              total_pnl: Math.round(totalPnl * 100) / 100,
              total_pnl_pct: Math.round((totalPnl / (tradeList.length * 100)) * 100) / 100,
              win_rate: Math.round(winRate * 100) / 100,
              max_drawdown: 0,
              total_trades: tradeList.length,
              win_count: winCount,
              lose_count: loseCount,
            });
          }
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
  }, [autoRefresh, initialDataLoaded, apiUrl, hasRealtimeData]);

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
              className={`status-indicator ${
                authenticated ? 'connected' : connected ? 'connecting' : 'disconnected'
              }`}
            />
            <span className="status-text">
              {authenticated
                ? '인증됨 ✓'
                : connected
                ? '연결 중 (인증 대기)'
                : '연결 끊김'}
            </span>
          </div>
        </div>

        {/* 토큰 입력 필드 */}
        {!token || !authenticated ? (
          <div className="token-input-banner">
            <span className="info-icon">ℹ️</span>
            <span className="info-text">
              {!token ? 'JWT 토큰이 필요합니다.' : '인증 대기 중...'}
            </span>
            {!token && (
              <>
                <input
                  type="password"
                  placeholder="JWT 토큰 입력..."
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      // Enter 키로도 저장 가능
                      if (tokenInput) {
                        setToken(tokenInput);
                        localStorage.setItem('simulation_token', tokenInput);
                        setTokenInput('');
                      }
                    }
                  }}
                  className="token-input"
                />
                <button
                  onClick={() => {
                    if (tokenInput) {
                      setToken(tokenInput);
                      localStorage.setItem('simulation_token', tokenInput);
                      setTokenInput('');
                    }
                  }}
                  disabled={!tokenInput}
                  className="btn btn-sm btn-success"
                >
                  저장 & 연결
                </button>
              </>
            )}
          </div>
        ) : null}

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

      {mergedSimulationStatus && (
        <div className="simulation-info">
          <div className="info-item">
            <span className="info-label">세션:</span>
            <span className="info-value">{mergedSimulationStatus.session_id || '-'}</span>
          </div>
          <div className="info-item">
            <span className="info-label">상태:</span>
            <span className="info-value">
              {mergedSimulationStatus.is_running ? '실행 중' : '중지됨'}
            </span>
          </div>
          <div className="info-item">
            <span className="info-label">WebSocket 클라이언트:</span>
            <span className="info-value">
              {mergedSimulationStatus.websocket_clients || 0}개
            </span>
          </div>
        </div>
      )}

      <div className="dashboard-grid">
        <div className="dashboard-panel profit-panel">
          <ProfitChart performance={mergedPerformance} positions={mergedPositions} />
        </div>

        <div className="dashboard-panel signals-panel">
          <SignalStream signals={signals} hasRealtimeData={hasRealtimeData} />
        </div>

        <div className="dashboard-panel positions-panel">
          <PositionTable positions={mergedPositions} />
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
