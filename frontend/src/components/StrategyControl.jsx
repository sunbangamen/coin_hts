import React, { useState, useEffect, useCallback } from 'react';
import '../styles/StrategyControl.css';

/**
 * 전략 제어 컴포넌트
 *
 * 시뮬레이션 중 전략을 모니터링하고 현재 설정을 표시합니다.
 * (시뮬레이션 실행 중에는 읽기 전용)
 *
 * @param {string} apiUrl REST API 서버 URL
 * @param {Object} simulationStatus 시뮬레이션 상태
 * @param {boolean} authenticated WebSocket 인증 여부
 */

const STRATEGIES = {
  volume_long_candle: '거래량 급증 + 장대양봉',
  volume_zone_breakout: '매물대 돌파'
};

const STRATEGY_PARAMS_CONFIG = {
  volume_long_candle: [
    { name: 'vol_ma_window', label: '이동 평균 윈도우', type: 'number', min: 1, max: 200 },
    { name: 'vol_multiplier', label: '거래량 배수', type: 'number', min: 1.0, max: 10.0, step: 0.1 },
    { name: 'body_pct', label: '몸통 비율 (0~1)', type: 'number', min: 0.0, max: 1.0, step: 0.01 }
  ],
  volume_zone_breakout: [
    { name: 'volume_window', label: '거래량 윈도우', type: 'number', min: 1, max: 200 },
    { name: 'top_percentile', label: '상위 백분위수 (0~100%)', type: 'number', min: 0, max: 100, step: 1, isPercent: true },
    { name: 'breakout_buffer', label: '돌파 버퍼 (0~1)', type: 'number', min: 0.0, max: 1.0, step: 0.01 }
  ]
};

const STRATEGY_PRESETS = {
  conservative: {
    label: '보수적 (Low Risk)',
    description: '신호 품질 우선, 높은 성공률',
    strategy: 'volume_long_candle',
    params: {
      vol_ma_window: 20,
      vol_multiplier: 1.5,
      body_pct: 0.01
    }
  },
  balanced: {
    label: '균형잡힌 (Balanced)',
    description: '신호와 성공률 균형',
    strategy: 'volume_zone_breakout',
    params: {
      volume_window: 20,
      top_percentile: 0.20,
      breakout_buffer: 0.0
    }
  },
  aggressive: {
    label: '적극적 (Aggressive)',
    description: '신호량 우선, 다양한 기회 포착',
    strategy: 'volume_zone_breakout',
    params: {
      volume_window: 10,
      top_percentile: 0.30,
      breakout_buffer: 0.0
    }
  }
};

export const StrategyControl = ({ apiUrl = 'http://localhost:8000/api', simulationStatus = null, authenticated = false }) => {
  const [strategies, setStrategies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedSymbol, setExpandedSymbol] = useState(null);

  // 시뮬레이션 전략 조회
  useEffect(() => {
    const fetchStrategies = async () => {
      if (!authenticated) return;

      try {
        setLoading(true);
        setError(null);
        const response = await fetch(`${apiUrl}/simulation/strategies`);
        if (response.ok) {
          const data = await response.json();
          console.log('Simulation strategies:', data);
          setStrategies(data.strategies || []);
        } else {
          setError('전략 정보를 불러올 수 없습니다');
        }
      } catch (err) {
        console.error('Failed to fetch strategies:', err);
        setError('전략 정보 로드 실패');
      } finally {
        setLoading(false);
      }
    };

    fetchStrategies();
  }, [apiUrl, authenticated]);

  // 백분율 변환 함수
  const formatParamValue = (param, value) => {
    if (param.isPercent && value !== null && value !== undefined) {
      return (value * 100).toFixed(0);
    }
    if (typeof value === 'number') {
      return value.toFixed(param.step === 0.01 ? 2 : 1);
    }
    return value;
  };

  // 전략별 심볼 그룹화
  const getStrategiesBySymbol = useCallback(() => {
    const grouped = {};
    strategies.forEach(stratConfig => {
      if (!grouped[stratConfig.symbol]) {
        grouped[stratConfig.symbol] = [];
      }
      grouped[stratConfig.symbol].push(stratConfig);
    });
    return grouped;
  }, [strategies]);

  const strategiesBySymbol = getStrategiesBySymbol();
  const symbols = Object.keys(strategiesBySymbol).sort();

  return (
    <div className="strategy-control">
      <div className="strategy-header">
        <h2>📊 전략 설정</h2>
        {simulationStatus && (
          <span className="strategy-status">
            {simulationStatus.is_running ? '실행 중 (읽기 전용)' : '준비 중'}
          </span>
        )}
      </div>

      {error && (
        <div className="strategy-error">
          <span className="error-icon">⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {loading && (
        <div className="strategy-loading">
          <span>전략 정보 로딩 중...</span>
        </div>
      )}

      {!loading && strategies.length === 0 && !error && (
        <div className="strategy-empty">
          <span>⚙️ 시뮬레이션을 시작하면 전략이 표시됩니다</span>
        </div>
      )}

      {!loading && symbols.length > 0 && (
        <div className="strategy-list">
          {symbols.map(symbol => (
            <div key={symbol} className="strategy-group">
              <div
                className="strategy-group-header"
                onClick={() => setExpandedSymbol(expandedSymbol === symbol ? null : symbol)}
              >
                <div className="strategy-group-title">
                  <span className="symbol-badge">{symbol}</span>
                  <span className="strategy-count">
                    {strategiesBySymbol[symbol].length}개 전략
                  </span>
                </div>
                <span className={`expand-icon ${expandedSymbol === symbol ? 'expanded' : ''}`}>
                  ▼
                </span>
              </div>

              {expandedSymbol === symbol && (
                <div className="strategy-details">
                  {strategiesBySymbol[symbol].map((stratConfig, idx) => {
                    const paramConfig = STRATEGY_PARAMS_CONFIG[stratConfig.strategy_name] || [];
                    return (
                      <div key={idx} className="strategy-item">
                        <div className="strategy-name">
                          <strong>{STRATEGIES[stratConfig.strategy_name] || stratConfig.strategy_name}</strong>
                        </div>

                        {paramConfig.length > 0 && (
                          <div className="strategy-params">
                            {paramConfig.map(param => {
                              const value = stratConfig.params[param.name];
                              return (
                                <div key={param.name} className="param-item">
                                  <span className="param-label">{param.label}</span>
                                  <span className="param-value">
                                    {formatParamValue(param, value)}
                                    {param.isPercent ? '%' : ''}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 전략 프리셋 참조 */}
      <div className="strategy-presets-info">
        <h3>📌 전략 프리셋 참고</h3>
        <div className="presets-grid">
          {Object.entries(STRATEGY_PRESETS).map(([key, preset]) => (
            <div key={key} className="preset-card">
              <div className="preset-title">{preset.label}</div>
              <div className="preset-desc">{preset.description}</div>
              <div className="preset-strategy">
                {STRATEGIES[preset.strategy]}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default StrategyControl;
