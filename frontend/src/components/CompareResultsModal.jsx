import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { formatNumber, formatPercent } from '../utils/formatters'
import { fetchBacktestDetail } from '../services/backtestApi'
import '../styles/CompareResultsModal.css'

/**
 * CompareResultsModal - 여러 백테스트 결과 비교
 *
 * @param {boolean} isOpen - 모달 열림 상태
 * @param {Function} onClose - 모달 닫기 콜백
 * @param {Array} results - 비교할 결과 항목 (run_id, strategy, symbols, total_signals, execution_time 등)
 */
export default function CompareResultsModal({ isOpen, onClose, results = [] }) {
  const [detailedResults, setDetailedResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [chartData, setChartData] = useState([])

  // 상세 결과 데이터 로드
  useEffect(() => {
    if (isOpen && results.length > 0) {
      loadDetailedResults()
    }
  }, [isOpen, results])

  const loadDetailedResults = async () => {
    try {
      setLoading(true)
      setError(null)

      const promises = results.map(result =>
        fetchBacktestDetail(result.run_id)
          .then(detail => ({
            ...result,
            detail: detail
          }))
          .catch(err => ({
            ...result,
            detail: null,
            error: err.message
          }))
      )

      const loaded = await Promise.all(promises)
      setDetailedResults(loaded)

      // 차트 데이터 생성
      generateChartData(loaded)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const generateChartData = (results) => {
    // 모든 심볼의 수익률 데이터를 병합하여 시각화
    // 각 결과마다 평균 수익률을 계산하여 라인 차트로 표시

    // 간단한 구현: 각 결과의 전체 수익률을 포인트로 표시
    const data = results.map((result, index) => {
      const item = {
        name: `Run ${index + 1}`,
        runId: result.run_id.substring(0, 8),
      }

      // 심볼별 평균 수익률 계산
      if (result.detail && result.detail.symbols && result.detail.symbols.length > 0) {
        const avgReturn =
          result.detail.symbols.reduce((sum, sym) => sum + (sym.avg_return || 0), 0) /
          result.detail.symbols.length
        item.avgReturn = Math.round(avgReturn * 10000) / 10000
      } else {
        item.avgReturn = 0
      }

      return item
    })

    setChartData(data)
  }

  if (!isOpen) return null

  const colors = ['#667eea', '#764ba2', '#f093fb']

  return (
    <div className="compare-modal-overlay" onClick={onClose}>
      <div className="compare-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="compare-modal-header">
          <h2>🔍 결과 비교</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        {loading && (
          <div className="compare-modal-body loading">
            <div className="spinner"></div>
            <p>결과를 로드 중입니다...</p>
          </div>
        )}

        {error && (
          <div className="compare-modal-body error">
            <p>오류: {error}</p>
          </div>
        )}

        {!loading && !error && detailedResults.length > 0 && (
          <div className="compare-modal-body">
            {/* 메트릭 비교 테이블 */}
            <div className="compare-section">
              <h3>주요 지표 비교</h3>
              <div className="metrics-comparison-table">
                <table>
                  <thead>
                    <tr>
                      <th>지표</th>
                      {detailedResults.map((result, idx) => (
                        <th key={idx}>
                          {result.strategy}
                          <br />
                          <span className="run-id-small">{result.run_id.substring(0, 12)}...</span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="metric-label">신호 수</td>
                      {detailedResults.map((result, idx) => (
                        <td key={idx} className="metric-value">
                          {formatNumber(result.total_signals)}
                        </td>
                      ))}
                    </tr>

                    <tr>
                      <td className="metric-label">심볼 개수</td>
                      {detailedResults.map((result, idx) => (
                        <td key={idx} className="metric-value">
                          {result.symbols?.length || 0}
                        </td>
                      ))}
                    </tr>

                    <tr>
                      <td className="metric-label">평균 수익률</td>
                      {detailedResults.map((result, idx) => {
                        const avgReturn = result.detail?.symbols?.length > 0
                          ? result.detail.symbols.reduce((sum, sym) => sum + (sym.avg_return || 0), 0) /
                            result.detail.symbols.length
                          : 0
                        return (
                          <td key={idx} className={`metric-value ${avgReturn >= 0 ? 'positive' : 'negative'}`}>
                            {formatPercent(avgReturn)}
                          </td>
                        )
                      })}
                    </tr>

                    <tr>
                      <td className="metric-label">평균 승률</td>
                      {detailedResults.map((result, idx) => {
                        const avgWinRate = result.detail?.symbols?.length > 0
                          ? result.detail.symbols.reduce((sum, sym) => sum + (sym.win_rate || 0), 0) /
                            result.detail.symbols.length
                          : 0
                        return (
                          <td key={idx} className="metric-value">
                            {formatPercent(avgWinRate)}
                          </td>
                        )
                      })}
                    </tr>

                    <tr>
                      <td className="metric-label">평균 최대 낙폭</td>
                      {detailedResults.map((result, idx) => {
                        const avgDrawdown = result.detail?.symbols?.length > 0
                          ? result.detail.symbols.reduce((sum, sym) => sum + (sym.max_drawdown || 0), 0) /
                            result.detail.symbols.length
                          : 0
                        return (
                          <td key={idx} className={`metric-value ${avgDrawdown >= 0 ? 'positive' : 'negative'}`}>
                            {formatPercent(avgDrawdown)}
                          </td>
                        )
                      })}
                    </tr>

                    <tr>
                      <td className="metric-label">실행 시간</td>
                      {detailedResults.map((result, idx) => (
                        <td key={idx} className="metric-value">
                          {result.execution_time?.toFixed(2)}초
                        </td>
                      ))}
                    </tr>

                    <tr>
                      <td className="metric-label">분석 기간</td>
                      {detailedResults.map((result, idx) => (
                        <td key={idx} className="metric-value text-small">
                          {result.start_date} ~ {result.end_date}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* 평균 수익률 비교 차트 */}
            {chartData.length > 0 && (
              <div className="compare-section chart-section">
                <h3>평균 수익률 비교</h3>
                <div className="comparison-chart">
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip
                        formatter={(value) => formatPercent(value)}
                        contentStyle={{
                          backgroundColor: 'rgba(255, 255, 255, 0.95)',
                          border: '1px solid #ccc',
                          borderRadius: '4px'
                        }}
                      />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="avgReturn"
                        stroke={colors[0]}
                        strokeWidth={2}
                        dot={{ r: 6 }}
                        activeDot={{ r: 8 }}
                        name="평균 수익률"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* 심볼별 성과 비교 */}
            <div className="compare-section">
              <h3>심볼별 성과</h3>
              <div className="symbol-comparison">
                {detailedResults.map((result, resultIdx) => (
                  <div key={resultIdx} className="symbol-group">
                    <div className="symbol-group-header">
                      <h4>
                        {result.strategy}
                        <span className="run-id-badge">{result.run_id.substring(0, 8)}</span>
                      </h4>
                      <span className="symbol-count">심볼: {result.symbols?.length || 0}개</span>
                    </div>
                    <div className="symbol-cards">
                      {result.detail?.symbols?.map((symbol, symIdx) => (
                        <div key={symIdx} className="symbol-card">
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
                            <span className={`label`}>수익률:</span>
                            <span className={`value ${symbol.avg_return >= 0 ? 'positive' : 'negative'}`}>
                              {formatPercent(symbol.avg_return)}
                            </span>
                          </div>
                          <div className="metric">
                            <span className="label">최대낙폭:</span>
                            <span className={`value ${symbol.max_drawdown >= 0 ? 'positive' : 'negative'}`}>
                              {formatPercent(symbol.max_drawdown)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {!loading && !error && detailedResults.length === 0 && (
          <div className="compare-modal-body empty">
            <p>비교할 결과가 없습니다.</p>
          </div>
        )}
      </div>
    </div>
  )
}
