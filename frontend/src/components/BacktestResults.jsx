import React from 'react';
import { formatPercent, formatNumber } from '../utils/formatters';
import SignalsTable from './SignalsTable';

/**
 * 백테스트 결과를 표시하는 컴포넌트
 * - 지표 요약 (전체 및 심볼별)
 * - 신호 목록 테이블 (향후 추가)
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
      {renderInfoSection()}
      {renderMetricsSection()}
      {renderSignalsSection()}
    </div>
  );
};

export default BacktestResults;
