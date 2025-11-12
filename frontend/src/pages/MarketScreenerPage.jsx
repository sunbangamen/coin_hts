/**
 * Task 6: HTS 스타일 조건 검색 화면 (Feature Breakdown #23)
 *
 * 사용자가 조건을 설정하여 종목을 필터링하는 독립 페이지
 * - 조건 빌더 UI (조건 타입, 연산자, 값, 기간 선택)
 * - 조건 추가/삭제
 * - AND/OR 논리 연산자
 * - 검색 실행 및 결과 표시
 */

import { useState, useCallback } from 'react'
import '../styles/MarketScreenerPage.css'
import {
  searchScreener,
  CONDITION_CONFIG,
  CONDITION_TEMPLATES,
  validateCondition
} from '../services/screenerApi'
import { mergeMarketsAndTickers, fetchKRWMarkets, fetchKRWTickers } from '../services/marketsApi'

const ITEMS_PER_PAGE = 50

export default function MarketScreenerPage() {
  // ============================================================================
  // State
  // ============================================================================

  const [conditions, setConditions] = useState([
    { id: 1, ...CONDITION_TEMPLATES.change_rate }
  ])
  const [logic, setLogic] = useState('AND')
  const [searchResults, setSearchResults] = useState([])
  const [resultsWithData, setResultsWithData] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [searched, setSearched] = useState(false)

  // 검색 결과 필터링
  const [searchTerm, setSearchTerm] = useState('')
  const [sortConfig, setSortConfig] = useState({
    key: 'market',
    direction: 'asc'
  })

  // 페이지네이션
  const [currentPage, setCurrentPage] = useState(1)
  const [nextConditionId, setNextConditionId] = useState(2)

  // ============================================================================
  // 조건 관리 함수
  // ============================================================================

  const addCondition = () => {
    const newId = nextConditionId
    setNextConditionId(newId + 1)
    setConditions([
      ...conditions,
      { id: newId, ...CONDITION_TEMPLATES.change_rate }
    ])
  }

  const removeCondition = (id) => {
    if (conditions.length > 1) {
      setConditions(conditions.filter(c => c.id !== id))
    }
  }

  const updateCondition = (id, field, value) => {
    setConditions(conditions.map(c => {
      if (c.id === id) {
        const updated = { ...c, [field]: value }

        // 조건 타입 변경 시 해당 조건의 기본값으로 초기화
        if (field === 'type') {
          const template = CONDITION_TEMPLATES[value]
          return {
            ...c,
            type: value,
            operator: template.operator,
            value: template.value,
            period: template.period
          }
        }

        return updated
      }
      return c
    }))
  }

  // ============================================================================
  // 조건 검색
  // ============================================================================

  const handleSearch = async () => {
    // 조건 검증
    const invalidCondition = conditions.find(c => !validateCondition(c).valid)
    if (invalidCondition) {
      const { error: validationError } = validateCondition(invalidCondition)
      setError(validationError)
      return
    }

    setLoading(true)
    setError(null)

    try {
      // API 호출
      const response = await searchScreener(
        conditions.map(({ id, label, ...rest }) => rest),
        logic
      )

      setSearchResults(response.matched_markets || [])

      // 마켓 정보와 시세 정보 조회하여 병합
      if (response.matched_markets && response.matched_markets.length > 0) {
        const [marketsData, tickersData] = await Promise.all([
          fetchKRWMarkets(),
          fetchKRWTickers()
        ])

        const marketMap = new Map(
          (marketsData.markets || []).map(m => [m.market, m])
        )

        const merged = (response.matched_markets || [])
          .map(market => {
            const marketInfo = marketMap.get(market) || { market }
            const tickerInfo = (tickersData.tickers || []).find(t => t.market === market) || {}
            return {
              ...marketInfo,
              ...tickerInfo
            }
          })
          .filter(Boolean)

        setResultsWithData(merged)
      } else {
        setResultsWithData([])
      }

      setSearched(true)
      setCurrentPage(1)
    } catch (err) {
      setError(err.message)
      setSearchResults([])
      setResultsWithData([])
    } finally {
      setLoading(false)
    }
  }

  // ============================================================================
  // 필터링 및 정렬
  // ============================================================================

  const filteredData = useCallback(() => {
    if (!searchTerm.trim()) {
      return resultsWithData
    }

    const term = searchTerm.toLowerCase()
    return resultsWithData.filter(item =>
      item.market?.toLowerCase().includes(term) ||
      item.korean_name?.toLowerCase().includes(term) ||
      item.english_name?.toLowerCase().includes(term)
    )
  }, [resultsWithData, searchTerm])

  const sortedData = useCallback(() => {
    const data = [...filteredData()]

    if (sortConfig.key) {
      data.sort((a, b) => {
        const aValue = a[sortConfig.key]
        const bValue = b[sortConfig.key]

        if (typeof aValue === 'number' && typeof bValue === 'number') {
          return sortConfig.direction === 'asc'
            ? aValue - bValue
            : bValue - aValue
        }

        if (typeof aValue === 'string' && typeof bValue === 'string') {
          return sortConfig.direction === 'asc'
            ? aValue.localeCompare(bValue, 'ko-KR')
            : bValue.localeCompare(aValue, 'ko-KR')
        }

        return 0
      })
    }

    return data
  }, [filteredData, sortConfig])

  const handleSort = (key) => {
    setSortConfig(prevConfig => ({
      key,
      direction: prevConfig.key === key && prevConfig.direction === 'asc' ? 'desc' : 'asc'
    }))
  }

  // ============================================================================
  // 페이지네이션
  // ============================================================================

  const sorted = sortedData()
  const totalPages = Math.ceil(sorted.length / ITEMS_PER_PAGE)
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE
  const endIndex = startIndex + ITEMS_PER_PAGE
  const pageData = sorted.slice(startIndex, endIndex)

  const handlePrevPage = () => {
    setCurrentPage(prev => Math.max(1, prev - 1))
  }

  const handleNextPage = () => {
    setCurrentPage(prev => Math.min(totalPages, prev + 1))
  }

  // ============================================================================
  // 포맷 함수
  // ============================================================================

  const formatPrice = (price) => {
    if (!price || price === 0) return '0원'
    return `${price.toLocaleString('ko-KR')}원`
  }

  const formatRate = (rate) => {
    const sign = rate > 0 ? '+' : ''
    const percentage = (rate * 100).toFixed(2)
    return `${sign}${percentage}%`
  }

  const formatVolume = (volume) => {
    if (volume > 1000000) {
      return `${(volume / 1000000).toFixed(2)}M`
    }
    if (volume > 1000) {
      return `${(volume / 1000).toFixed(2)}K`
    }
    return volume.toFixed(2)
  }

  const formatAmount = (amount) => {
    if (amount > 1000000000) {
      return `${(amount / 1000000000).toFixed(2)}B원`
    }
    if (amount > 1000000) {
      return `${(amount / 1000000).toFixed(2)}M원`
    }
    if (amount > 1000) {
      return `${(amount / 1000).toFixed(2)}K원`
    }
    return `${amount.toFixed(0)}원`
  }

  const getSortIndicator = (key) => {
    if (sortConfig.key !== key) return ' ▼'
    return sortConfig.direction === 'asc' ? ' ▲' : ' ▼'
  }

  const getRateColor = (rate) => {
    if (rate > 0) return '#e74c3c'
    if (rate < 0) return '#3498db'
    return '#95a5a6'
  }

  const getConditionLabel = (type) => {
    return CONDITION_CONFIG[type]?.label || type
  }

  // ============================================================================
  // 렌더링
  // ============================================================================

  return (
    <div className="screener-container">
      <div className="screener-header">
        <h1>조건 검색</h1>
        <p>HTS 스타일의 조건 검색으로 매매 기회를 찾으세요</p>
      </div>

      {/* 에러 메시지 */}
      {error && (
        <div className="error-message">
          <strong>오류:</strong> {error}
          <button onClick={() => setError(null)} className="close-error">×</button>
        </div>
      )}

      {/* 조건 빌더 */}
      <div className="screener-builder">
        <div className="builder-header">
          <h2>검색 조건</h2>
          <div className="logic-selector">
            <label>논리 연산:</label>
            <select
              value={logic}
              onChange={(e) => setLogic(e.target.value)}
              className="logic-select"
            >
              <option value="AND">AND (모두 만족)</option>
              <option value="OR">OR (하나 만족)</option>
            </select>
          </div>
        </div>

        {/* 조건 목록 */}
        <div className="conditions-list">
          {conditions.map((condition, index) => (
            <div key={condition.id} className="condition-row">
              {index > 0 && (
                <div className="logic-operator">{logic}</div>
              )}

              <div className="condition-form">
                {/* 조건 타입 선택 */}
                <div className="form-group">
                  <label>조건</label>
                  <select
                    value={condition.type}
                    onChange={(e) => updateCondition(condition.id, 'type', e.target.value)}
                    className="condition-type-select"
                  >
                    {Object.entries(CONDITION_CONFIG).map(([key, config]) => (
                      <option key={key} value={key}>
                        {config.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* 연산자 선택 */}
                <div className="form-group">
                  <label>연산자</label>
                  <select
                    value={condition.operator}
                    onChange={(e) => updateCondition(condition.id, 'operator', e.target.value)}
                    className="operator-select"
                  >
                    {CONDITION_CONFIG[condition.type]?.operators.map(op => (
                      <option key={op} value={op}>{op}</option>
                    ))}
                  </select>
                </div>

                {/* 값 입력 */}
                <div className="form-group">
                  <label>값</label>
                  {CONDITION_CONFIG[condition.type]?.valueType === 'select' ? (
                    <select
                      value={condition.value}
                      onChange={(e) => updateCondition(condition.id, 'value', e.target.value)}
                      className="value-input"
                    >
                      {CONDITION_CONFIG[condition.type]?.options.map(opt => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type={CONDITION_CONFIG[condition.type]?.valueType === 'number' ? 'number' : 'text'}
                      value={condition.value}
                      onChange={(e) => updateCondition(condition.id, 'value', e.target.value)}
                      placeholder={CONDITION_CONFIG[condition.type]?.placeholder}
                      className="value-input"
                    />
                  )}
                  {CONDITION_CONFIG[condition.type]?.unit && (
                    <span className="unit">{CONDITION_CONFIG[condition.type].unit}</span>
                  )}
                </div>

                {/* 기간 선택 (조건에 따라 표시) */}
                {CONDITION_CONFIG[condition.type]?.hasPeriod && (
                  <div className="form-group">
                    <label>기간</label>
                    <select
                      value={condition.period}
                      onChange={(e) => updateCondition(condition.id, 'period', e.target.value)}
                      className="period-select"
                    >
                      {CONDITION_CONFIG[condition.type]?.periods.map(period => (
                        <option key={period} value={period}>{period}</option>
                      ))}
                    </select>
                  </div>
                )}

                {/* 삭제 버튼 */}
                <button
                  onClick={() => removeCondition(condition.id)}
                  disabled={conditions.length === 1}
                  className="delete-condition-btn"
                  title="조건 삭제"
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* 조건 추가 및 검색 버튼 */}
        <div className="builder-actions">
          <button
            onClick={addCondition}
            className="add-condition-btn"
            disabled={conditions.length >= 5}
          >
            + 조건 추가 ({conditions.length}/5)
          </button>

          <button
            onClick={handleSearch}
            disabled={loading}
            className="search-btn"
          >
            {loading ? '검색 중...' : '🔍 검색'}
          </button>
        </div>
      </div>

      {/* 검색 결과 */}
      {searched && (
        <div className="screener-results">
          <div className="results-header">
            <h2>검색 결과</h2>
            <span className="result-count">
              {resultsWithData.length > 0
                ? `${sorted.length}개 종목 매칭 (표시: ${pageData.length}개)`
                : '매칭된 종목 없음'}
            </span>
          </div>

          {/* 결과 검색 및 필터 */}
          {resultsWithData.length > 0 && (
            <div className="results-controls">
              <input
                type="text"
                placeholder="종목명이나 한글명으로 검색"
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value)
                  setCurrentPage(1)
                }}
                className="search-input"
              />
            </div>
          )}

          {/* 결과 테이블 */}
          {resultsWithData.length > 0 ? (
            <>
              <div className="results-table-wrapper">
                <table className="results-table">
                  <thead>
                    <tr>
                      <th className="sortable" onClick={() => handleSort('market')}>
                        심볼{getSortIndicator('market')}
                      </th>
                      <th className="sortable" onClick={() => handleSort('korean_name')}>
                        한글명{getSortIndicator('korean_name')}
                      </th>
                      <th className="sortable" onClick={() => handleSort('english_name')}>
                        영문명{getSortIndicator('english_name')}
                      </th>
                      <th className="sortable text-right" onClick={() => handleSort('trade_price')}>
                        현재가{getSortIndicator('trade_price')}
                      </th>
                      <th className="sortable text-right" onClick={() => handleSort('change_rate')}>
                        등락률{getSortIndicator('change_rate')}
                      </th>
                      <th className="sortable text-right" onClick={() => handleSort('acc_trade_volume_24h')}>
                        거래량(24h){getSortIndicator('acc_trade_volume_24h')}
                      </th>
                      <th className="sortable text-right" onClick={() => handleSort('acc_trade_price_24h')}>
                        거래대금(24h){getSortIndicator('acc_trade_price_24h')}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageData.map((item, index) => (
                      <tr key={item.market} className={index % 2 === 0 ? 'even' : 'odd'}>
                        <td className="market-code">{item.market}</td>
                        <td className="korean-name">{item.korean_name}</td>
                        <td className="english-name">{item.english_name}</td>
                        <td className="text-right">{formatPrice(item.trade_price)}</td>
                        <td
                          className="text-right rate"
                          style={{ color: getRateColor(item.change_rate) }}
                        >
                          {formatRate(item.change_rate)}
                        </td>
                        <td className="text-right">{formatVolume(item.acc_trade_volume_24h)}</td>
                        <td className="text-right">{formatAmount(item.acc_trade_price_24h)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* 페이지네이션 */}
              {totalPages > 1 && (
                <div className="results-pagination">
                  <button
                    onClick={handlePrevPage}
                    disabled={currentPage === 1}
                    className="pagination-btn"
                  >
                    ← 이전
                  </button>

                  <div className="pagination-info">
                    페이지 <span className="current-page">{currentPage}</span> / <span className="total-pages">{totalPages}</span>
                  </div>

                  <button
                    onClick={handleNextPage}
                    disabled={currentPage >= totalPages}
                    className="pagination-btn"
                  >
                    다음 →
                  </button>
                </div>
              )}
            </>
          ) : (
            <div className="no-results">
              <p>검색 조건에 맞는 종목이 없습니다.</p>
              <p className="hint">조건을 수정하여 다시 검색해보세요.</p>
            </div>
          )}
        </div>
      )}

      {/* 초기 안내 메시지 */}
      {!searched && (
        <div className="screener-guide">
          <div className="guide-content">
            <h3>사용 방법</h3>
            <ul>
              <li>왼쪽에서 검색 조건을 설정합니다</li>
              <li>필요한 경우 조건을 추가할 수 있습니다 (최대 5개)</li>
              <li>AND/OR 논리 연산자를 선택합니다</li>
              <li>🔍 검색 버튼을 클릭하여 결과를 확인합니다</li>
            </ul>
            <p className="tip">💡 Tip: 처음에는 상승률 > 5% 정도의 간단한 조건으로 시작해보세요!</p>
          </div>
        </div>
      )}
    </div>
  )
}
