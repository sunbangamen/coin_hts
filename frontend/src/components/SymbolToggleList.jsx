/**
 * SymbolToggleList 컴포넌트 (Phase 2)
 *
 * 백테스트 결과에서 각 심볼의 활성/비활성 상태를 토글하는 컴포넌트입니다.
 * 사용자는 체크박스를 클릭하여 각 심볼의 활성 여부를 동적으로 관리할 수 있습니다.
 *
 * Props:
 * - runId: 백테스트 실행 ID
 * - symbols: 심볼 배열 (각 심볼은 { symbol, is_active, ... } 형식)
 * - onToggle: 토글 완료 후 호출되는 콜백 (updated: { symbol, is_active })
 * - onError: 에러 발생 시 호출되는 콜백 (에러 메시지)
 */

import { useState } from 'react'
import '../styles/SymbolToggleList.css'

export default function SymbolToggleList({ runId, symbols, onToggle, onError }) {
  const [isUpdating, setIsUpdating] = useState(false)
  const [updatingSymbol, setUpdatingSymbol] = useState(null)
  const [error, setError] = useState(null)

  const handleToggle = async (symbolItem) => {
    setIsUpdating(true)
    setUpdatingSymbol(symbolItem.symbol)
    setError(null)

    try {
      const newIsActive = !symbolItem.is_active
      const response = await fetch(
        `/api/backtests/${runId}/symbols/${symbolItem.symbol}`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ is_active: newIsActive }),
        }
      )

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }

      const updated = await response.json()

      // 콜백 호출
      if (onToggle) {
        onToggle(updated)
      }

      console.log(`✅ Symbol ${updated.symbol} toggled: is_active=${updated.is_active}`)
    } catch (error) {
      const errorMsg = `Failed to toggle ${symbolItem.symbol}: ${error.message}`
      console.error(errorMsg)
      setError(errorMsg)

      // 에러 콜백 호출
      if (onError) {
        onError(errorMsg)
      }
    } finally {
      setIsUpdating(false)
      setUpdatingSymbol(null)
    }
  }

  if (!symbols || symbols.length === 0) {
    return (
      <div className="symbol-toggle-list">
        <h4>심볼 활성화 관리</h4>
        <p className="no-symbols">심볼이 없습니다.</p>
      </div>
    )
  }

  return (
    <div className="symbol-toggle-list">
      <div className="toggle-list-header">
        <h4>심볼 활성화 관리</h4>
        <span className="toggle-count">
          {symbols.filter(s => s.is_active).length}/{symbols.length} 활성
        </span>
      </div>

      {error && (
        <div className="toggle-error-message">
          <span className="error-icon">⚠️</span>
          <span className="error-text">{error}</span>
          <button
            className="error-close"
            onClick={() => setError(null)}
            aria-label="Close error message"
          >
            ×
          </button>
        </div>
      )}

      <div className="toggle-items-container">
        {symbols.map((symbol) => (
          <div
            key={symbol.symbol}
            className={`symbol-toggle-item ${
              symbol.is_active ? 'active' : 'inactive'
            } ${updatingSymbol === symbol.symbol ? 'updating' : ''}`}
          >
            <label className="toggle-label">
              <input
                type="checkbox"
                checked={symbol.is_active}
                onChange={() => handleToggle(symbol)}
                disabled={isUpdating}
                className="toggle-checkbox"
                aria-label={`Toggle ${symbol.symbol}`}
              />

              <span className="symbol-name">
                {symbol.symbol}
              </span>

              {updatingSymbol === symbol.symbol && isUpdating && (
                <span className="updating-spinner">
                  <span className="spinner"></span>
                </span>
              )}

              <span className={`status-badge ${symbol.is_active ? 'active' : 'inactive'}`}>
                {symbol.is_active ? '활성' : '비활성'}
              </span>
            </label>

            {symbol.signals && symbol.signals.length > 0 && (
              <span className="signal-count">
                {symbol.signals.length} 신호
              </span>
            )}
          </div>
        ))}
      </div>

      <div className="toggle-list-footer">
        <p className="info-text">
          ✓ 비활성 심볼은 성과 분석에서 제외됩니다.
        </p>
      </div>
    </div>
  )
}
