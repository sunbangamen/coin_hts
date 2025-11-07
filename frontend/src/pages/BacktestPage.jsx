import { useState } from 'react'
import axios from 'axios'
import '../App.css'
import BacktestResults from '../components/BacktestResults'
import StrategyPresetModal from '../components/StrategyPresetModal'
import {
  validateSymbols,
  validateDateRange,
  validateParams,
  validateBacktestRequest,
  percentToDecimal,
  decimalToPercent
} from '../validation'

const STRATEGIES = {
  volume_long_candle: '거래량 급증 + 장대양봉',
  volume_zone_breakout: '매물대 돌파'
}

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
}

const TIMEFRAMES = ['1d', '1h', '5m']

// Strategy Presets (from Phase 2 optimization analysis)
// 출처: docs/coin/mvp/phase2_strategy_optimization.md
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
}

/**
 * Generate a summary of validation errors
 * @param {object} errors - Validation errors object
 * @returns {string[]} Array of error messages
 */
function generateErrorSummary(errors) {
  const summaryErrors = []

  // Add top-level errors
  if (errors.symbols) summaryErrors.push(errors.symbols)
  if (errors.dates) summaryErrors.push(errors.dates)
  if (errors.strategy) summaryErrors.push(errors.strategy)

  // Add parameter-level errors
  if (errors.params && typeof errors.params === 'object') {
    Object.values(errors.params).forEach(paramError => {
      if (paramError) summaryErrors.push(paramError)
    })
  }

  return summaryErrors
}

export default function BacktestPage() {
  // Form state
  const [formData, setFormData] = useState({
    strategy: 'volume_long_candle',
    symbols: '',
    start_date: '',
    end_date: '',
    timeframe: '1d',
    params: {}
  })

  // Error state
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState(null)

  // Loading and result state
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [showResult, setShowResult] = useState(false)

  // Preset modal state
  const [isPresetModalOpen, setIsPresetModalOpen] = useState(false)

  /**
   * Perform real-time validation and update errors
   * Called after form data changes
   */
  const performRealTimeValidation = (updatedFormData) => {
    const validation = validateBacktestRequest({
      symbols: updatedFormData.symbols,
      start_date: updatedFormData.start_date,
      end_date: updatedFormData.end_date,
      strategy: updatedFormData.strategy,
      params: updatedFormData.params
    })

    setErrors(validation.errors)
  }

  // Handle strategy change
  const handleStrategyChange = (e) => {
    const newStrategy = e.target.value
    const updatedFormData = {
      ...formData,
      strategy: newStrategy,
      params: {}
    }
    setFormData(updatedFormData)
    setApiError(null)
    performRealTimeValidation(updatedFormData)
  }

  // Handle preset selection
  const handlePresetClick = (presetKey) => {
    const preset = STRATEGY_PRESETS[presetKey]
    const updatedFormData = {
      ...formData,
      strategy: preset.strategy,
      params: { ...preset.params }
    }
    setFormData(updatedFormData)
    setApiError(null)
    performRealTimeValidation(updatedFormData)
  }

  // Handle preset modal selection
  const handlePresetSelect = (presetName, presetData) => {
    const updatedFormData = {
      ...formData,
      strategy: presetData.strategy,
      params: { ...presetData.params }
    }
    setFormData(updatedFormData)
    setApiError(null)
    performRealTimeValidation(updatedFormData)
    setIsPresetModalOpen(false)
  }

  // Handle preset run immediately (프리셋으로 바로 실행)
  const handlePresetRunImmediately = async (preset) => {
    try {
      setApiError(null)

      // 프리셋 데이터를 폼에 적용
      const updatedFormData = {
        ...formData,
        strategy: preset.strategy,
        params: { ...preset.params }
      }
      setFormData(updatedFormData)

      // 유효성 검증
      const validation = validateBacktestRequest({
        symbols: formData.symbols,
        start_date: formData.start_date,
        end_date: formData.end_date,
        strategy: preset.strategy,
        params: preset.params
      })

      if (!validation.isValid) {
        setApiError('프리셋 적용 후 필수 항목을 확인하세요: 심볼, 기간이 필요합니다')
        setIsPresetModalOpen(false)
        return
      }

      // 백테스트 실행
      setLoading(true)
      const symbolList = validateSymbols(formData.symbols).symbols
      const requestData = {
        strategy: preset.strategy,
        symbols: symbolList,
        start_date: formData.start_date,
        end_date: formData.end_date,
        timeframe: formData.timeframe,
        params: preset.params
      }

      const response = await axios.post('/api/backtests/run', requestData)
      setResult(response.data)
      setShowResult(true)
      setIsPresetModalOpen(false)
    } catch (error) {
      setApiError(
        error.response?.data?.detail ||
        error.message ||
        '프리셋 실행 중 오류가 발생했습니다'
      )
    } finally {
      setLoading(false)
    }
  }

  // Handle general input change with real-time validation
  const handleInputChange = (e) => {
    const { name, value } = e.target
    const updatedFormData = {
      ...formData,
      [name]: value
    }
    setFormData(updatedFormData)
    performRealTimeValidation(updatedFormData)
  }

  // Handle parameter input change with real-time validation
  const handleParamChange = (e) => {
    const { name, value } = e.target
    const paramConfig = STRATEGY_PARAMS_CONFIG[formData.strategy]
    const fieldConfig = paramConfig.find(p => p.name === name)

    let finalValue = value
    // Convert percentage to decimal for top_percentile
    if (fieldConfig && fieldConfig.isPercent && value !== '') {
      finalValue = percentToDecimal(parseFloat(value))
    }

    const updatedFormData = {
      ...formData,
      params: {
        ...formData.params,
        [name]: finalValue
      }
    }
    setFormData(updatedFormData)
    performRealTimeValidation(updatedFormData)
  }

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault()
    setApiError(null)

    // Final validation before submission
    const validation = validateBacktestRequest({
      symbols: formData.symbols,
      start_date: formData.start_date,
      end_date: formData.end_date,
      strategy: formData.strategy,
      params: formData.params
    })

    if (!validation.isValid) {
      setErrors(validation.errors)
      return
    }

    // Build API request
    const symbolList = validateSymbols(formData.symbols).symbols
    const requestData = {
      strategy: formData.strategy,
      symbols: symbolList,
      start_date: formData.start_date,
      end_date: formData.end_date,
      timeframe: formData.timeframe,
      params: formData.params
    }

    try {
      setLoading(true)
      const response = await axios.post('/api/backtests/run', requestData)
      setResult(response.data)
      setShowResult(true)
    } catch (error) {
      setApiError(
        error.response?.data?.detail ||
        error.message ||
        '백테스트 실행 중 오류가 발생했습니다'
      )
    } finally {
      setLoading(false)
    }
  }

  const currentStrategyParams = STRATEGY_PARAMS_CONFIG[formData.strategy] || []

  // Check if form is valid
  const hasErrors = Object.values(errors).some(e => e !== null && e !== undefined)
  const isFormValid = !hasErrors && formData.symbols && formData.start_date && formData.end_date

  // Generate error summary
  const errorSummary = generateErrorSummary(errors)
  const summaryErrorId = 'form-error-summary'
  const symbolsErrorId = 'symbols-error'
  const datesErrorId = 'dates-error'

  return (
    <div className="app">
      <main>
        <div className="form-container">
          <h2>백테스트 설정</h2>

          {/* API Error Message */}
          {apiError && <div className="summary-error">{apiError}</div>}

          {/* Form Error Summary */}
          {errorSummary.length > 0 && (
            <div
              id={summaryErrorId}
              className="summary-error"
              role="alert"
              aria-live="polite"
            >
              <strong>다음 오류를 수정하세요:</strong>
              <ul>
                {errorSummary.map((error, idx) => (
                  <li key={idx}>{error}</li>
                ))}
              </ul>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {/* Strategy Selection */}
            <div className="form-group">
              <label htmlFor="strategy">전략 *</label>
              <select
                id="strategy"
                name="strategy"
                value={formData.strategy}
                onChange={handleStrategyChange}
                aria-describedby={errors.strategy ? 'strategy-error' : undefined}
                aria-invalid={!!errors.strategy}
              >
                {Object.entries(STRATEGIES).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
              {errors.strategy && (
                <div id="strategy-error" className="error-message" role="alert">
                  {errors.strategy}
                </div>
              )}
            </div>

            {/* Strategy Presets */}
            <div className="presets-section">
              <div className="presets-header">
                <label>🎯 추천 프리셋 (파라미터 자동 설정)</label>
                <button
                  type="button"
                  className="preset-manage-btn"
                  onClick={() => setIsPresetModalOpen(true)}
                  title="저장된 프리셋 관리"
                >
                  ⚙️ 프리셋 관리
                </button>
              </div>
              <div className="presets-buttons">
                {Object.entries(STRATEGY_PRESETS).map(([key, preset]) => (
                  <button
                    key={key}
                    type="button"
                    className={`preset-btn ${formData.strategy === preset.strategy &&
                      JSON.stringify(formData.params) === JSON.stringify(preset.params) ? 'active' : ''}`}
                    onClick={() => handlePresetClick(key)}
                    title={preset.description}
                    aria-label={`${preset.label} 프리셋 적용: ${preset.description}`}
                  >
                    <div className="preset-label">{preset.label}</div>
                    <div className="preset-description">{preset.description}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Symbols Input */}
            <div className={`form-group ${errors.symbols ? 'error' : ''}`}>
              <label htmlFor="symbols">심볼 (쉼표로 구분) *</label>
              <textarea
                id="symbols"
                name="symbols"
                value={formData.symbols}
                onChange={handleInputChange}
                placeholder="예: BTC_KRW, ETH_KRW, SOL_KRW"
                aria-describedby={errors.symbols ? symbolsErrorId : undefined}
                aria-invalid={!!errors.symbols}
              />
              {errors.symbols && (
                <div id={symbolsErrorId} className="error-message" role="alert">
                  {errors.symbols}
                </div>
              )}
              <div className="info-text">쉼표로 구분하여 여러 심볼을 입력할 수 있습니다 (공백 허용 안 함)</div>
            </div>

            {/* Date Range */}
            <div className="form-row">
              <div className={`form-group ${errors.dates ? 'error' : ''}`}>
                <label htmlFor="start_date">시작일 (YYYY-MM-DD) *</label>
                <input
                  id="start_date"
                  type="date"
                  name="start_date"
                  value={formData.start_date}
                  onChange={handleInputChange}
                  aria-describedby={errors.dates ? datesErrorId : undefined}
                  aria-invalid={!!errors.dates}
                />
              </div>
              <div className={`form-group ${errors.dates ? 'error' : ''}`}>
                <label htmlFor="end_date">종료일 (YYYY-MM-DD) *</label>
                <input
                  id="end_date"
                  type="date"
                  name="end_date"
                  value={formData.end_date}
                  onChange={handleInputChange}
                  aria-describedby={errors.dates ? datesErrorId : undefined}
                  aria-invalid={!!errors.dates}
                />
                {errors.dates && (
                  <div id={datesErrorId} className="error-message" role="alert">
                    {errors.dates}
                  </div>
                )}
              </div>
            </div>

            {/* Timeframe Selection */}
            <div className="form-group">
              <label htmlFor="timeframe">타임프레임</label>
              <select
                id="timeframe"
                name="timeframe"
                value={formData.timeframe}
                onChange={handleInputChange}
              >
                {TIMEFRAMES.map(tf => (
                  <option key={tf} value={tf}>
                    {tf}
                  </option>
                ))}
              </select>
            </div>

            {/* Strategy Parameters */}
            {currentStrategyParams.length > 0 && (
              <div>
                <h3>전략 파라미터</h3>
                {currentStrategyParams.map(param => {
                  const paramValue = formData.params[param.name]
                  // Show percentage value for percentage fields
                  const displayValue = param.isPercent && paramValue !== ''
                    ? decimalToPercent(paramValue)
                    : paramValue

                  const paramErrorId = `${param.name}-error`

                  return (
                    <div
                      key={param.name}
                      className={`form-group ${
                        errors.params && errors.params[param.name] ? 'error' : ''
                      }`}
                    >
                      <label htmlFor={param.name}>{param.label} *</label>
                      <input
                        id={param.name}
                        type={param.type}
                        name={param.name}
                        value={displayValue}
                        onChange={handleParamChange}
                        min={param.min}
                        max={param.max}
                        step={param.step}
                        aria-describedby={
                          (errors.params && errors.params[param.name]) ? paramErrorId : undefined
                        }
                        aria-invalid={!!(errors.params && errors.params[param.name])}
                      />
                      {errors.params && errors.params[param.name] && (
                        <div id={paramErrorId} className="error-message" role="alert">
                          {errors.params[param.name]}
                        </div>
                      )}
                      {param.isPercent && (
                        <div className="info-text">0~100의 퍼센트 값으로 입력하세요</div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              className={`submit-btn ${loading ? 'loading' : ''}`}
              disabled={!isFormValid || loading}
              aria-busy={loading}
              aria-disabled={!isFormValid || loading}
              aria-describedby={errorSummary.length > 0 ? summaryErrorId : undefined}
            >
              {loading ? '실행 중...' : '백테스트 실행'}
            </button>
          </form>
        </div>

        {/* Results Section */}
        <div className="results-container">
          <h2>백테스트 결과</h2>
          <BacktestResults
            result={showResult ? result : null}
            loading={loading}
            error={apiError}
          />
        </div>
      </main>

      {/* Preset Modal */}
      <StrategyPresetModal
        isOpen={isPresetModalOpen}
        onClose={() => setIsPresetModalOpen(false)}
        onPresetSelect={handlePresetSelect}
        onPresetRunImmediately={handlePresetRunImmediately}
        currentStrategy={formData.strategy}
        currentParams={formData.params}
      />
    </div>
  )
}
