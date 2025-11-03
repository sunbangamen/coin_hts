import React from 'react';
import { formatPercent, formatNumber } from '../utils/formatters';
import SignalsTable from './SignalsTable';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceDot,
  ComposedChart,
} from 'recharts';

/**
 * 백테스트 결과를 표시하는 컴포넌트
 * - 지표 요약 (전체 및 심볼별)
 * - Equity Curve 차트 (Phase 3)
 * - 신호 목록 테이블
 */
const BacktestResults = ({ result = null, loading = false, error = null }) => {

  // 로딩 상태
  if (loading) {
    return (
      <div className="backtest-results loading">
        <div className="spinner"></div>
        <p>백테스트 결과를 로드 중입니다...</p>
      </div>
    );
  }

  // 에러 상태
  if (error) {
    return (
      <div className="backtest-results error">
        <h3>오류 발생</h3>
        <p>{error}</p>
      </div>
    );
  }

  // 데이터 없음
  if (!result) {
    return (
      <div className="backtest-results empty">
        <p>실행 결과가 없습니다.</p>
        <p className="hint">왼쪽 폼에서 백테스트를 실행하면 결과가 여기 표시됩니다.</p>
      </div>
    );
  }

  // 지표 섹션
  const renderMetricsSection = () => {
    if (!result.symbols || result.symbols.length === 0) {
      return (
        <div className="metrics-section">
          <h3>지표</h3>
          <p className="no-data">신호 데이터가 없습니다.</p>
        </div>
      );
    }

    return (
      <div className="metrics-section">
        <h3>지표 요약</h3>
        <div className="metrics-grid">
          {result.symbols.map((symbol) => (
            <div key={symbol.symbol} className="metric-card">
              <h4>{symbol.symbol}</h4>
              <div className="metric-item">
                <span className="label">샘플 수:</span>
                <span className="value">
                  {formatNumber(symbol.signals && symbol.signals.length ? symbol.signals.length : 0)}
                </span>
              </div>
              <div className="metric-item">
                <span className="label">승률:</span>
                <span className="value">{formatPercent(symbol.win_rate)}</span>
              </div>
              <div className="metric-item">
                <span className="label">평균 수익률:</span>
                <span className={`value ${symbol.avg_return >= 0 ? 'positive' : 'negative'}`}>
                  {formatPercent(symbol.avg_return)}
                </span>
              </div>
              <div className="metric-item">
                <span className="label">최대 낙폭:</span>
                <span className={`value ${symbol.max_drawdown >= 0 ? 'positive' : 'negative'}`}>
                  {formatPercent(symbol.max_drawdown)}
                </span>
              </div>
              <div className="metric-item">
                <span className="label">평균 보유 기간:</span>
                <span className="value">{symbol.avg_hold_bars.toFixed(1)} 봉</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // 메타데이터 섹션 (Phase 2 확장)
  const renderMetadataSection = () => {
    if (!result.metadata) {
      return null;
    }

    const formatDate = (dateString) => {
      if (!dateString) return '-';
      try {
        return new Date(dateString).toLocaleString('ko-KR', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          timeZoneName: 'short'
        });
      } catch (e) {
        return dateString;
      }
    };

    return (
      <div className="metadata-section">
        <h3>메타데이터 (Phase 2)</h3>
        <div className="metadata-grid">
          <div className="metadata-item">
            <span className="label">API 버전:</span>
            <span className="value">{result.version || '1.0.0'}</span>
          </div>
          <div className="metadata-item">
            <span className="label">실행 시간:</span>
            <span className="value">{formatDate(result.metadata.execution_date)}</span>
          </div>
          <div className="metadata-item">
            <span className="label">환경:</span>
            <span className="value">{result.metadata.environment}</span>
          </div>
          <div className="metadata-item">
            <span className="label">실행 호스트:</span>
            <span className="value">{result.metadata.execution_host}</span>
          </div>
          {result.description && (
            <div className="metadata-item full-width">
              <span className="label">설명:</span>
              <span className="value">{result.description}</span>
            </div>
          )}
        </div>
      </div>
    );
  };

  // Equity Curve 차트 (Phase 3)
  const renderEquityCurveChart = () => {
    if (!result.symbols || result.symbols.length === 0) {
      return null;
    }

    // 성과곡선 데이터가 있는 심볼 찾기
    const symbolWithCurve = result.symbols.find(s => s.performance_curve && s.performance_curve.length > 0);

    if (!symbolWithCurve) {
      return null;
    }

    const performanceData = symbolWithCurve.performance_curve.map(point => ({
      timestamp: point.timestamp,
      equity: parseFloat((point.equity * 100).toFixed(2)), // 퍼센트로 변환 (100 = 100%)
      equityValue: point.equity,
    }));

    const signalMarkers = symbolWithCurve.signals.map(signal => {
      // performance_curve에서 신호 시점 찾기
      const matchingPoint = performanceData.find(
        p => p.timestamp === signal.timestamp.split('T')[0]
      );

      return matchingPoint ? {
        timestamp: matchingPoint.timestamp,
        equity: matchingPoint.equity,
        signal: signal.type.toUpperCase(),
        price: signal.entry_price,
      } : null;
    }).filter(Boolean);

    // 차트 데이터에 신호 정보 추가
    const chartData = performanceData.map(point => {
      const signal = signalMarkers.find(s => s.timestamp === point.timestamp);
      return {
        ...point,
        ...signal,
      };
    });

    const minEquity = Math.min(...performanceData.map(p => p.equity));
    const maxEquity = Math.max(...performanceData.map(p => p.equity));

    return (
      <div className="chart-section">
        <h3>📈 Equity Curve (누적 수익률)</h3>
        <div className="chart-info">
          <span>시작: 100% | 종료: {performanceData[performanceData.length - 1].equity.toFixed(2)}%</span>
        </div>

        <ResponsiveContainer width="100%" height={400}>
          <LineChart
            data={chartData}
            margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
            <XAxis
              dataKey="timestamp"
              tick={{ fontSize: 12 }}
              interval={Math.floor(chartData.length / 8)}
            />
            <YAxis
              domain={[Math.floor(minEquity * 0.95), Math.ceil(maxEquity * 1.05)]}
              label={{ value: '수익률 (%)', angle: -90, position: 'insideLeft' }}
              tick={{ fontSize: 12 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #ccc',
                borderRadius: '4px',
                padding: '8px',
              }}
              formatter={(value, name) => {
                if (name === 'equity') {
                  return `${value.toFixed(2)}%`;
                }
                return value;
              }}
              labelFormatter={(label) => `날짜: ${label}`}
            />
            <Legend wrapperStyle={{ paddingTop: '20px' }} />

            {/* Equity Line */}
            <Line
              type="monotone"
              dataKey="equity"
              stroke="#2c3e50"
              strokeWidth={2}
              dot={false}
              name="Equity (%)"
              isAnimationActive={false}
            />

            {/* 신호 마커 */}
            {signalMarkers.map((marker, idx) => (
              <ReferenceDot
                key={idx}
                x={marker.timestamp}
                y={marker.equity}
                r={5}
                fill={marker.signal === 'BUY' ? '#28a745' : '#dc3545'}
                stroke="white"
                strokeWidth={2}
                name={`${marker.signal} @ ${marker.price.toFixed(0)}`}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>

        <div className="chart-legend">
          <div className="legend-item buy">
            <span className="legend-marker">●</span>
            <span>매수 신호</span>
          </div>
          <div className="legend-item sell">
            <span className="legend-marker">●</span>
            <span>매도 신호</span>
          </div>
        </div>
      </div>
    );
  };

  // 백테스트 정보 섹션
  const renderInfoSection = () => {
    return (
      <div className="info-section">
        <h3>백테스트 정보</h3>
        <div className="info-grid">
          <div className="info-item">
            <span className="label">실행 ID:</span>
            <span className="value">{result.run_id}</span>
          </div>
          <div className="info-item">
            <span className="label">전략:</span>
            <span className="value">{result.strategy}</span>
          </div>
          <div className="info-item">
            <span className="label">기간:</span>
            <span className="value">
              {result.start_date} ~ {result.end_date}
            </span>
          </div>
          <div className="info-item">
            <span className="label">타임프레임:</span>
            <span className="value">{result.timeframe}</span>
          </div>
          <div className="info-item">
            <span className="label">전체 신호 수:</span>
            <span className="value">{formatNumber(result.total_signals)}</span>
          </div>
          <div className="info-item">
            <span className="label">실행 시간:</span>
            <span className="value">{result.execution_time.toFixed(2)}초</span>
          </div>
        </div>
      </div>
    );
  };

  // 신호 목록 섹션 (Step 4 구현 완료)
  const renderSignalsSection = () => {
    if (!result.symbols || result.symbols.length === 0) {
      return null;
    }

    const hasAnySignals = result.symbols.some(
      (symbol) => symbol.signals && symbol.signals.length > 0
    );

    if (!hasAnySignals) {
      return (
        <div className="signals-section">
          <h3>신호 목록</h3>
          <p className="no-data">신호가 없습니다.</p>
        </div>
      );
    }

    return (
      <div className="signals-section">
        <h3>신호 목록</h3>
        {result.symbols.map((symbol) => (
          <div key={symbol.symbol} className="symbol-signals-group">
            <h4>{symbol.symbol}</h4>
            {symbol.signals && symbol.signals.length > 0 ? (
              <SignalsTable symbol={symbol.symbol} signals={symbol.signals} />
            ) : (
              <p className="no-signals-for-symbol">신호 없음</p>
            )}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="backtest-results">
      {renderMetadataSection()}
      {renderInfoSection()}
      {renderMetricsSection()}
      {renderEquityCurveChart()}
      {renderSignalsSection()}
    </div>
  );
};

export default BacktestResults;
