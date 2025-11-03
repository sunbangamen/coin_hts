import React, { useState } from 'react'
import { formatPercent, formatNumber, formatDateTime } from '../utils/formatters'

/**
 * SignalsTable - 거래 신호를 테이블로 렌더링하는 컴포넌트
 *
 * Props:
 *   - symbol (string): 심볼 (예: "BTC_KRW")
 *   - signals (array): 신호 배열
 */
export default function SignalsTable({ symbol, signals = [] }) {
  const [sortKey, setSortKey] = useState('timestamp')
  const [sortOrder, setSortOrder] = useState('desc') // 'asc' or 'desc'

  // 신호가 없는 경우
  if (!signals || signals.length === 0) {
    return (
      <div className="signals-empty-state">
        <p>신호 없음</p>
      </div>
    )
  }

  /**
   * 정렬 함수
   */
  const sortSignals = (data, key, order) => {
    const sorted = [...data].sort((a, b) => {
      let aVal = a[key]
      let bVal = b[key]

      // 숫자 타입 비교
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return order === 'asc' ? aVal - bVal : bVal - aVal
      }

      // 문자열/타임스탐프 비교
      if (aVal < bVal) return order === 'asc' ? -1 : 1
      if (aVal > bVal) return order === 'asc' ? 1 : -1
      return 0
    })

    return sorted
  }

  /**
   * 정렬 헤더 클릭 핸들러
   */
  const handleSort = (key) => {
    if (sortKey === key) {
      // 같은 컬럼이면 정렬 방향 토글
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      // 다른 컬럼이면 오름차순으로 시작
      setSortKey(key)
      setSortOrder('asc')
    }
  }

  /**
   * 정렬 아이콘 렌더링
   */
  const renderSortIcon = (key) => {
    if (sortKey !== key) return ' ⇅'
    return sortOrder === 'asc' ? ' ↑' : ' ↓'
  }

  /**
   * 수익률 클래스 결정
   */
  const getReturnClass = (returnPct) => {
    if (returnPct > 0) return 'positive'
    if (returnPct < 0) return 'negative'
    return 'neutral'
  }

  /**
   * 신호 타입 표시 텍스트
   */
  const getTypeLabel = (type) => {
    return type === 'buy' ? '매수' : '매도'
  }

  const sortedSignals = sortSignals(signals, sortKey, sortOrder)

  return (
    <div className="signals-table-container">
      <table className="signals-table">
        <thead>
          <tr>
            <th onClick={() => handleSort('symbol')}>
              심볼{renderSortIcon('symbol')}
            </th>
            <th onClick={() => handleSort('type')}>
              타입{renderSortIcon('type')}
            </th>
            <th onClick={() => handleSort('timestamp')}>
              시간{renderSortIcon('timestamp')}
            </th>
            <th onClick={() => handleSort('entry_price')}>
              진입가{renderSortIcon('entry_price')}
            </th>
            <th onClick={() => handleSort('exit_price')}>
              청산가{renderSortIcon('exit_price')}
            </th>
            <th onClick={() => handleSort('return_pct')}>
              수익률{renderSortIcon('return_pct')}
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedSignals.map((signal, idx) => (
            <tr key={idx} className={`signal-row ${signal.type}`}>
              <td className="symbol">{signal.symbol}</td>
              <td className={`type ${signal.type}`}>
                {getTypeLabel(signal.type)}
              </td>
              <td className="timestamp">
                {formatDateTime(signal.timestamp)}
              </td>
              <td className="price">
                {formatNumber(signal.entry_price)}
              </td>
              <td className="price">
                {formatNumber(signal.exit_price)}
              </td>
              <td className={`return ${getReturnClass(signal.return_pct)}`}>
                {formatPercent(signal.return_pct)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
