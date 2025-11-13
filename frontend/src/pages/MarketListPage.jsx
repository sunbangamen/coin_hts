/**
 * Task 3: 전체 종목 리스트 화면 (Feature Breakdown #23)
 * Task 7: WebSocket 실시간 업데이트 (선택사항)
 *
 * 업비트 KRW 마켓 전체 종목을 깔끔한 테이블로 표시
 * - 실시간 시세 표시 (현재가, 등락률, 거래량, 거래대금)
 * - WebSocket을 통한 진정한 실시간 업데이트 (VITE_ENABLE_LIVE_TICKERS에 따라 선택)
 * - REST-only 폴백: WebSocket 서버가 없어도 REST API로 데이터 표시
 * - 정렬 기능 (모든 컬럼)
 * - 검색 기능 (심볼/한글명)
 * - 페이지네이션 (50개씩)
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import '../styles/MarketListPage.css'
import { fetchKRWMarkets, mergeMarketsAndTickers } from '../services/marketsApi'
import { useWebSocket } from '../hooks/useWebSocket'

const ITEMS_PER_PAGE = 50

export default function MarketListPage() {
  // ============================================================================
  // State
  // ============================================================================

  const [markets, setMarkets] = useState([])
  const [displayData, setDisplayData] = useState([])
  const [loading, setLoading] = useState(true)
  const [wsError, setWsError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [cachedTickers, setCachedTickers] = useState({})  // WebSocket으로 받은 시세

  // 검색 및 필터
  const [searchTerm, setSearchTerm] = useState('')
  const [sortConfig, setSortConfig] = useState({
    key: 'market',
    direction: 'asc'
  })

  // 페이지네이션
  const [currentPage, setCurrentPage] = useState(1)

  // ============================================================================
  // WebSocket 연결 및 처리
  // ============================================================================

  /**
   * WebSocket 메시지 처리
   */
  const handleWebSocketMessage = useCallback((data) => {
    if (data.type === 'cached') {
      // 캐시된 데이터 (초기 로드)
      setCachedTickers(prev => ({
        ...prev,
        [data.market]: {
          trade_price: data.trade_price,
          change_rate: data.change_rate,
          acc_trade_volume_24h: data.acc_trade_volume_24h,
          acc_trade_price_24h: data.acc_trade_price_24h
        }
      }))
    } else if (data.type === 'cached_complete') {
      // 캐시 전송 완료 신호 → 마켓 목록 로드
      console.log('[MarketListPage] Cached data complete, loading markets...')
      loadMarketsFromApi({ silent: true })
    } else if (data.type === 'ticker') {
      // 실시간 시세 업데이트
      setCachedTickers(prev => ({
        ...prev,
        [data.market]: {
          trade_price: data.trade_price,
          change_rate: data.change_rate,
          acc_trade_volume_24h: data.acc_trade_volume_24h,
          acc_trade_price_24h: data.acc_trade_price_24h
        }
      }))
      setLastUpdated(new Date().toLocaleTimeString('ko-KR'))
    } else if (data.type === 'error') {
      // 에러 처리
      console.error('[MarketListPage] WebSocket error:', data.message)
      setWsError(data.message)
    }
  }, [])

  /**
   * WebSocket 에러 처리
   */
  const handleWebSocketError = useCallback((error) => {
    console.error('[MarketListPage] WebSocket connection error:', error)
    setWsError(error)
  }, [])

  /**
   * WebSocket 훅 사용 (silent 모드: 에러 메시지를 사용자에게 노출하지 않음)
   * 실시간 기능은 선택사항이므로, WebSocket 서버가 없어도 조용히 폴백
   */
  const { connected: wsConnected, status: wsStatus, enabled: wsEnabled } = useWebSocket(
    '/ws/tickers/krw',
    handleWebSocketMessage,
    handleWebSocketError,
    { silent: true }  // silent 모드: 에러를 console에만 남기고 사용자 UI에는 표시 안 함
  )

  /**
   * API에서 마켓 목록 로드
   */
  const loadMarketsFromApi = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setLoading(true)
    }

    try {
      const marketsData = await fetchKRWMarkets()
      const baseMarkets = marketsData.markets || []

      // 캐시된 시세로 병합
      const merged = baseMarkets.map(market => ({
        ...market,
        trade_price: cachedTickers[market.market]?.trade_price || 0,
        change_rate: cachedTickers[market.market]?.change_rate || 0,
        acc_trade_volume_24h: cachedTickers[market.market]?.acc_trade_volume_24h || 0,
        acc_trade_price_24h: cachedTickers[market.market]?.acc_trade_price_24h || 0
      }))

      setMarkets(merged)
      setWsError(null)
    } catch (err) {
      console.error('[MarketListPage] Error loading markets:', err)
      setWsError(err.message || '마켓 목록 로드 실패')
    } finally {
      if (!silent) {
        setLoading(false)
      }
    }
  }, [cachedTickers])

  /**
   * 초기 마운트 시 최소 한 번은 REST API로 데이터를 로드
   * (WebSocket 연결 실패 시에도 빈 화면을 방지)
   */
  const initialLoadTriggered = useRef(false)

  useEffect(() => {
    if (initialLoadTriggered.current) return
    initialLoadTriggered.current = true

    loadMarketsFromApi().catch((error) => {
      console.error('[MarketListPage] Initial load failed:', error)
    })
  }, [loadMarketsFromApi])

  /**
   * 초기 로드 및 데이터 동기화
   */
  useEffect(() => {
    // 캐시된 시세가 업데이트되면 마켓 목록 동기화
    if (markets.length > 0 && Object.keys(cachedTickers).length > 0) {
      setMarkets(prevMarkets =>
        prevMarkets.map(market => ({
          ...market,
          trade_price: cachedTickers[market.market]?.trade_price || market.trade_price,
          change_rate: cachedTickers[market.market]?.change_rate || market.change_rate,
          acc_trade_volume_24h: cachedTickers[market.market]?.acc_trade_volume_24h || market.acc_trade_volume_24h,
          acc_trade_price_24h: cachedTickers[market.market]?.acc_trade_price_24h || market.acc_trade_price_24h
        }))
      )
    }
  }, [cachedTickers])

  // ============================================================================
  // 필터링 및 정렬
  // ============================================================================

  /**
   * 검색어에 따라 데이터 필터링
   */
  const filteredData = useCallback(() => {
    if (!searchTerm.trim()) {
      return markets
    }

    const term = searchTerm.toLowerCase()
    return markets.filter(item =>
      item.market.toLowerCase().includes(term) ||
      item.korean_name.toLowerCase().includes(term) ||
      item.english_name.toLowerCase().includes(term)
    )
  }, [markets, searchTerm])

  /**
   * 필터링된 데이터를 정렬
   */
  const sortedData = useCallback(() => {
    const data = [...filteredData()]

    if (sortConfig.key) {
      data.sort((a, b) => {
        const aValue = a[sortConfig.key]
        const bValue = b[sortConfig.key]

        // 숫자 비교
        if (typeof aValue === 'number' && typeof bValue === 'number') {
          return sortConfig.direction === 'asc'
            ? aValue - bValue
            : bValue - aValue
        }

        // 문자열 비교
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

  /**
   * 정렬 핸들러
   */
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
    if (rate > 0) return '#e74c3c'  // 빨강 (상승)
    if (rate < 0) return '#3498db'  // 파랑 (하락)
    return '#95a5a6'  // 회색 (동일)
  }

  // ============================================================================
  // 렌더링
  // ============================================================================

  if (loading) {
    return (
      <div className="market-list-container">
        <div className="loading">데이터 로드 중...</div>
      </div>
    )
  }

  return (
    <div className="market-list-container">
      <div className="market-list-header">
        <h1>종목 리스트</h1>
        <div className="header-info">
          <span className="total-count">
            전체 {sorted.length}개 종목 (표시: {pageData.length}개)
          </span>
          {lastUpdated && (
            <span className="last-updated">
              마지막 업데이트: {lastUpdated}
            </span>
          )}
        </div>
      </div>

      {/* 실시간 시세 상태 안내 */}
      {wsEnabled ? (
        // 실시간 기능 활성화 상태
        wsStatus === 'live' ? (
          <div className="ws-status">
            <span className="status-indicator connected">
              ● 실시간 시세 연결됨
            </span>
          </div>
        ) : wsStatus === 'failed' ? (
          <div className="ws-status-alert">
            <span className="status-badge offline">
              📊 실시간 시세 미연결 – 데이터는 REST 기준입니다
            </span>
          </div>
        ) : null
      ) : (
        // 실시간 기능 비활성화 상태
        <div className="ws-status-alert">
          <span className="status-badge disabled">
            📊 실시간 시세가 비활성화되었습니다
          </span>
        </div>
      )}

      <div className="market-list-controls">
        <input
          type="text"
          placeholder="종목명이나 한글명으로 검색 (예: BTC, 비트코인)"
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value)
            setCurrentPage(1)  // 검색 시 첫 페이지로
          }}
          className="search-input"
        />
      </div>

      <div className="market-list-table-wrapper">
        <table className="market-list-table">
          <thead>
            <tr>
              <th
                className="sortable"
                onClick={() => handleSort('market')}
              >
                심볼{getSortIndicator('market')}
              </th>
              <th
                className="sortable"
                onClick={() => handleSort('korean_name')}
              >
                한글명{getSortIndicator('korean_name')}
              </th>
              <th
                className="sortable"
                onClick={() => handleSort('english_name')}
              >
                영문명{getSortIndicator('english_name')}
              </th>
              <th
                className="sortable text-right"
                onClick={() => handleSort('trade_price')}
              >
                현재가{getSortIndicator('trade_price')}
              </th>
              <th
                className="sortable text-right"
                onClick={() => handleSort('change_rate')}
              >
                등락률{getSortIndicator('change_rate')}
              </th>
              <th
                className="sortable text-right"
                onClick={() => handleSort('acc_trade_volume_24h')}
              >
                거래량(24h){getSortIndicator('acc_trade_volume_24h')}
              </th>
              <th
                className="sortable text-right"
                onClick={() => handleSort('acc_trade_price_24h')}
              >
                거래대금(24h){getSortIndicator('acc_trade_price_24h')}
              </th>
            </tr>
          </thead>
          <tbody>
            {pageData.length > 0 ? (
              pageData.map((item, index) => (
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
              ))
            ) : (
              <tr>
                <td colSpan="7" className="no-data">
                  검색 결과가 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* 페이지네이션 */}
      <div className="market-list-pagination">
        <button
          onClick={handlePrevPage}
          disabled={currentPage === 1}
          className="pagination-btn"
        >
          ← 이전
        </button>

        <div className="pagination-info">
          {totalPages > 0 ? (
            <>
              페이지 <span className="current-page">{currentPage}</span> / <span className="total-pages">{totalPages}</span>
            </>
          ) : (
            <span>페이지 0 / 0</span>
          )}
        </div>

        <button
          onClick={handleNextPage}
          disabled={currentPage >= totalPages}
          className="pagination-btn"
        >
          다음 →
        </button>
      </div>
    </div>
  )
}
