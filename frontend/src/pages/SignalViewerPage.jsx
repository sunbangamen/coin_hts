import { useState, useEffect } from 'react'
import useSWR from 'swr'
import { formatDateTime, formatNumber, formatPercent } from '../utils/formatters'
import SignalsTable from '../components/SignalsTable'
import {
  fetchLatestBacktest,
  fetchBacktestHistory,
  downloadBacktestResult,
  downloadBacktestAsCSV
} from '../services/backtestApi'
import '../App.css'

/**
 * LatestResultCard - 최신 백테스트 결과를 표시하는 컴포넌트
 */
function LatestResultCard({ data, loading, error }) {
  if (loading) {
    return (
      <div className="card latest-result-card loading">
        <div className="spinner"></div>
        <p>최신 결과를 로드 중입니다...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card latest-result-card error">
        <h3>오류 발생</h3>
        <p>{error.message}</p>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="card latest-result-card empty">
        <p>실행된 백테스트 결과가 없습니다.</p>
        <p className="hint">백테스트를 실행하면 여기에 결과가 표시됩니다.</p>
      </div>
    )
  }

  return (
    <div className="card latest-result-card">
      <h3>최신 결과</h3>
      <div className="latest-info-grid">
        <div className="info-item">
          <span className="label">실행 ID:</span>
          <span className="value mono">{data.run_id}</span>
        </div>
        <div className="info-item">
          <span className="label">전략:</span>
          <span className="value">{data.strategy}</span>
        </div>
        <div className="info-item">
          <span className="label">기간:</span>
          <span className="value">{data.start_date} ~ {data.end_date}</span>
        </div>
        <div className="info-item">
          <span className="label">타임프레임:</span>
          <span className="value">{data.timeframe}</span>
        </div>
        <div className="info-item">
          <span className="label">신호 수:</span>
          <span className="value">{formatNumber(data.total_signals)}</span>
        </div>
        <div className="info-item">
          <span className="label">실행 시간:</span>
          <span className="value">{data.execution_time?.toFixed(2)}초</span>
        </div>
      </div>

      {/* 심볼별 성과 */}
      {data.symbols && data.symbols.length > 0 && (
        <div className="symbols-performance">
          <h4>심볼별 성과</h4>
          <div className="performance-grid">
            {data.symbols.map(symbol => (
              <div key={symbol.symbol} className="performance-card">
                <h5>{symbol.symbol}</h5>
                <div className="metric">
                  <span className="label">신호:</span>
                  <span className="value">{formatNumber(symbol.signals?.length || 0)}</span>
                </div>
                <div className="metric">
                  <span className="label">승률:</span>
                  <span className="value">{formatPercent(symbol.win_rate)}</span>
                </div>
                <div className="metric">
                  <span className="label">평균 수익률:</span>
                  <span className={`value ${symbol.avg_return >= 0 ? 'positive' : 'negative'}`}>
                    {formatPercent(symbol.avg_return)}
                  </span>
                </div>
                <div className="metric">
                  <span className="label">최대 낙폭:</span>
                  <span className={`value ${symbol.max_drawdown >= 0 ? 'positive' : 'negative'}`}>
                    {formatPercent(symbol.max_drawdown)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="latest-timestamp">
        자동 갱신됨: {data.metadata?.execution_date ? formatDateTime(data.metadata.execution_date) : '대기 중'}
      </div>
    </div>
  )
}

/**
 * HistoryTable - 백테스트 히스토리를 페이지네이션과 함께 표시
 */
function HistoryTable({ historyData, loading, error, onPageChange }) {
  const [selectedResult, setSelectedResult] = useState(null)

  if (loading) {
    return (
      <div className="card history-table loading">
        <div className="spinner"></div>
        <p>히스토리를 로드 중입니다...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card history-table error">
        <h3>오류 발생</h3>
        <p>{error.message}</p>
      </div>
    )
  }

  const items = historyData?.items || []
  const total = historyData?.total || 0
  const limit = historyData?.limit || 10
  const offset = historyData?.offset || 0

  if (items.length === 0) {
    return (
      <div className="card history-table empty">
        <h3>히스토리</h3>
        <p>실행 이력이 없습니다.</p>
      </div>
    )
  }

  const currentPage = Math.floor(offset / limit) + 1
  const totalPages = Math.ceil(total / limit)

  const handlePrevious = () => {
    if (offset >= limit) {
      onPageChange(offset - limit)
    }
  }

  const handleNext = () => {
    if (offset + limit < total) {
      onPageChange(offset + limit)
    }
  }

  return (
    <div className="card history-table">
      <h3>히스토리 ({total}개)</h3>
      <div className="table-container">
        <table className="history-table-content">
          <thead>
            <tr>
              <th>실행 ID</th>
              <th>전략</th>
              <th>심볼</th>
              <th>시작일</th>
              <th>종료일</th>
              <th>신호 수</th>
              <th>실행 시간</th>
              <th>작업</th>
            </tr>
          </thead>
          <tbody>
            {items.map(item => (
              <tr key={item.run_id} onClick={() => setSelectedResult(item)}>
                <td className="mono">{item.run_id.substring(0, 12)}...</td>
                <td>{item.strategy}</td>
                <td>{item.symbols?.join(', ') || '-'}</td>
                <td>{item.start_date}</td>
                <td>{item.end_date}</td>
                <td className="number">{formatNumber(item.total_signals)}</td>
                <td className="number">{item.execution_time?.toFixed(2)}초</td>
                <td className="actions">
                  <button
                    className="download-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      downloadBacktestResult(item.run_id)
                    }}
                    title="JSON 다운로드"
                  >
                    JSON
                  </button>
                  <button
                    className="download-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      downloadBacktestAsCSV(item.run_id)
                    }}
                    title="CSV 다운로드"
                  >
                    CSV
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 페이지네이션 */}
      <div className="pagination">
        <button
          onClick={handlePrevious}
          disabled={offset === 0}
          className="pagination-btn"
        >
          이전
        </button>
        <span className="pagination-info">
          {currentPage} / {totalPages} (총 {total}개)
        </span>
        <button
          onClick={handleNext}
          disabled={offset + limit >= total}
          className="pagination-btn"
        >
          다음
        </button>
      </div>

      {/* 행 클릭 시 상세 신호 표시 */}
      {selectedResult && selectedResult.symbols && selectedResult.symbols.length > 0 && (
        <div className="selected-result-detail">
          <h4>신호 상세 ({selectedResult.run_id.substring(0, 12)}...)</h4>
          <div className="close-btn" onClick={() => setSelectedResult(null)}>×</div>
          {selectedResult.symbols.map(symbol => (
            <div key={symbol.symbol} className="symbol-signals">
              <h5>{symbol.symbol}</h5>
              {symbol.signals && symbol.signals.length > 0 ? (
                <SignalsTable symbol={symbol.symbol} signals={symbol.signals} />
              ) : (
                <p className="no-signals">신호 없음</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * SignalViewerPage - 메인 페이지 컴포넌트
 */
export default function SignalViewerPage() {
  const [historyOffset, setHistoryOffset] = useState(0)
  const [historyLimit] = useState(10)
  const [selectedStrategy, setSelectedStrategy] = useState(null)

  // useSWR을 사용한 최신 결과 폴링 (5초 간격)
  const { data: latestData, error: latestError, isLoading: latestLoading } = useSWR(
    '/api/backtests/latest',
    fetchLatestBacktest,
    {
      refreshInterval: 5000, // 5초마다 갱신
      dedupingInterval: 3000, // 3초 이내 중복 요청 제거
      revalidateOnFocus: true
    }
  )

  // useSWR을 사용한 히스토리 조회
  const historyParams = new URLSearchParams()
  historyParams.append('limit', historyLimit)
  historyParams.append('offset', historyOffset)
  if (selectedStrategy) historyParams.append('strategy', selectedStrategy)

  const { data: historyData, error: historyError, isLoading: historyLoading } = useSWR(
    `/api/backtests/history?${historyParams.toString()}`,
    () => fetchBacktestHistory({
      limit: historyLimit,
      offset: historyOffset,
      strategy: selectedStrategy
    }),
    {
      dedupingInterval: 2000
    }
  )

  const handleHistoryPageChange = (newOffset) => {
    setHistoryOffset(newOffset)
  }

  return (
    <div className="app">
      <main>
        <div className="page-header">
          <h2>시그널 뷰어</h2>
          <p className="subtitle">백테스트 결과 조회 및 히스토리 관리</p>
        </div>

        <div className="viewer-container">
          {/* 최신 결과 섹션 */}
          <section className="latest-section">
            <LatestResultCard
              data={latestData}
              loading={latestLoading}
              error={latestError}
            />
          </section>

          {/* 히스토리 섹션 */}
          <section className="history-section">
            <HistoryTable
              historyData={historyData}
              loading={historyLoading}
              error={historyError}
              onPageChange={handleHistoryPageChange}
            />
          </section>
        </div>
      </main>
    </div>
  )
}
