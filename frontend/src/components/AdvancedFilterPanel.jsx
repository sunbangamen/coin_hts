import { useState } from 'react'
import '../styles/AdvancedFilterPanel.css'

/**
 * AdvancedFilterPanel - 고급 필터링 UI (Task 3.3-3)
 *
 * 백테스트 히스토리를 다음 기준으로 필터링:
 * - 수익률 범위 (min_return ~ max_return)
 * - 신호 개수 범위 (min_signals ~ max_signals)
 * - 기간 범위 (date_from ~ date_to)
 */
export default function AdvancedFilterPanel({ filters, onFiltersChange, onReset }) {
  const [errors, setErrors] = useState({})
  const [touched, setTouched] = useState({})

  const handleInputChange = (e) => {
    const { name, value } = e.target
    const newValue = value === '' ? null : value

    // 숫자 필드는 숫자로 변환
    const finalValue =
      ['min_return', 'max_return', 'min_signals', 'max_signals'].includes(name) &&
      newValue !== null
        ? parseFloat(newValue)
        : newValue

    onFiltersChange({
      ...filters,
      [name]: finalValue,
    })

    // 필드 touched 표시
    setTouched({
      ...touched,
      [name]: true,
    })
  }

  const validateFilters = () => {
    const newErrors = {}

    // 수익률 검증
    if (filters.min_return !== null && filters.max_return !== null) {
      if (filters.min_return > filters.max_return) {
        newErrors.return_range = '최소 수익률이 최대 수익률보다 클 수 없습니다'
      }
    }

    // 신호 개수 검증
    if (filters.min_signals !== null && filters.max_signals !== null) {
      if (filters.min_signals > filters.max_signals) {
        newErrors.signals_range = '최소 신호 개수가 최대 신호 개수보다 클 수 없습니다'
      }
    }

    // 기간 검증
    if (filters.date_from && filters.date_to) {
      if (filters.date_from > filters.date_to) {
        newErrors.date_range = '시작 날짜가 종료 날짜보다 클 수 없습니다'
      }
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleApply = () => {
    if (validateFilters()) {
      // 필터 적용 - 부모 컴포넌트에서 SWR 키 갱신
      // onFiltersChange는 이미 호출됨
    }
  }

  const handleReset = () => {
    onReset()
    setErrors({})
    setTouched({})
  }

  const hasActiveFilters =
    filters.min_return !== null ||
    filters.max_return !== null ||
    filters.min_signals !== null ||
    filters.max_signals !== null ||
    filters.date_from ||
    filters.date_to

  return (
    <div className="advanced-filter-panel">
      <h3>🔍 고급 필터</h3>

      {/* 활성 필터 표시 */}
      {hasActiveFilters && (
        <div className="active-filters-summary">
          <span>활성 필터:</span>
          {filters.min_return !== null && <span className="filter-tag">수익률 ≥ {filters.min_return}%</span>}
          {filters.max_return !== null && <span className="filter-tag">수익률 ≤ {filters.max_return}%</span>}
          {filters.min_signals !== null && <span className="filter-tag">신호 ≥ {filters.min_signals}</span>}
          {filters.max_signals !== null && <span className="filter-tag">신호 ≤ {filters.max_signals}</span>}
          {filters.date_from && <span className="filter-tag">시작일 ≥ {filters.date_from}</span>}
          {filters.date_to && <span className="filter-tag">종료일 ≤ {filters.date_to}</span>}
        </div>
      )}

      <div className="filter-form">
        {/* 수익률 범위 */}
        <div className="filter-group">
          <label>수익률 (%)</label>
          <div className="range-inputs">
            <input
              type="number"
              name="min_return"
              placeholder="최소"
              value={filters.min_return ?? ''}
              onChange={handleInputChange}
              onBlur={() => validateFilters()}
              step="0.1"
              className={errors.return_range ? 'error' : ''}
            />
            <span className="range-separator">~</span>
            <input
              type="number"
              name="max_return"
              placeholder="최대"
              value={filters.max_return ?? ''}
              onChange={handleInputChange}
              onBlur={() => validateFilters()}
              step="0.1"
              className={errors.return_range ? 'error' : ''}
            />
          </div>
          {errors.return_range && <span className="error-message">{errors.return_range}</span>}
        </div>

        {/* 신호 개수 범위 */}
        <div className="filter-group">
          <label>신호 개수</label>
          <div className="range-inputs">
            <input
              type="number"
              name="min_signals"
              placeholder="최소"
              value={filters.min_signals ?? ''}
              onChange={handleInputChange}
              onBlur={() => validateFilters()}
              min="0"
              step="1"
              className={errors.signals_range ? 'error' : ''}
            />
            <span className="range-separator">~</span>
            <input
              type="number"
              name="max_signals"
              placeholder="최대"
              value={filters.max_signals ?? ''}
              onChange={handleInputChange}
              onBlur={() => validateFilters()}
              min="0"
              step="1"
              className={errors.signals_range ? 'error' : ''}
            />
          </div>
          {errors.signals_range && <span className="error-message">{errors.signals_range}</span>}
        </div>

        {/* 기간 범위 */}
        <div className="filter-group">
          <label>분석 기간</label>
          <div className="date-inputs">
            <input
              type="date"
              name="date_from"
              placeholder="시작일"
              value={filters.date_from || ''}
              onChange={handleInputChange}
              onBlur={() => validateFilters()}
              className={errors.date_range ? 'error' : ''}
            />
            <span className="date-separator">~</span>
            <input
              type="date"
              name="date_to"
              placeholder="종료일"
              value={filters.date_to || ''}
              onChange={handleInputChange}
              onBlur={() => validateFilters()}
              className={errors.date_range ? 'error' : ''}
            />
          </div>
          {errors.date_range && <span className="error-message">{errors.date_range}</span>}
        </div>
      </div>

      {/* 버튼 */}
      <div className="filter-buttons">
        <button
          className="filter-btn reset-btn"
          onClick={handleReset}
          title="모든 필터 초기화"
          disabled={!hasActiveFilters}
        >
          🔄 초기화
        </button>
        <button
          className="filter-btn apply-btn"
          onClick={handleApply}
          disabled={Object.keys(errors).length > 0}
          title={
            Object.keys(errors).length > 0
              ? '필터 범위 오류를 수정하세요'
              : '필터 적용'
          }
        >
          ✅ 필터 적용
        </button>
      </div>

      {/* 도움말 */}
      <div className="filter-help">
        <small>💡 팁: 범위 필터는 선택사항입니다. 최소값만, 최대값만, 또는 둘 다 설정할 수 있습니다.</small>
      </div>
    </div>
  )
}
