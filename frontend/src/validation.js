/**
 * Coin Backtesting Frontend - Validation Module
 *
 * This module provides validation functions for backtest requests,
 * ensuring input data conforms to backend API requirements and business rules.
 */

/**
 * Validates symbol list input
 * @param {string} symbolsText - Comma-separated symbol string (e.g., "BTC_KRW, ETH_KRW")
 * @returns {object} Validation result { isValid: boolean, error: string | null, symbols: string[] }
 */
export function validateSymbols(symbolsText) {
  if (!symbolsText || symbolsText.trim() === '') {
    return {
      isValid: false,
      error: '심볼을 최소 1개 이상 입력하세요',
      symbols: []
    }
  }

  const symbols = symbolsText
    .split(',')
    .map(s => s.trim())
    .filter(s => s.length > 0)

  if (symbols.length === 0) {
    return {
      isValid: false,
      error: '심볼을 최소 1개 이상 입력하세요',
      symbols: []
    }
  }

  // Check for whitespace within symbols
  for (const symbol of symbols) {
    if (/\s/.test(symbol)) {
      return {
        isValid: false,
        error: '심볼 내에 공백이 포함될 수 없습니다',
        symbols: []
      }
    }
  }

  return {
    isValid: true,
    error: null,
    symbols
  }
}

/**
 * Validates date range input
 * @param {string} startDate - Start date in YYYY-MM-DD format
 * @param {string} endDate - End date in YYYY-MM-DD format
 * @returns {object} Validation result { isValid: boolean, error: string | null }
 */
export function validateDateRange(startDate, endDate) {
  // Check if dates are provided
  if (!startDate || !endDate) {
    return {
      isValid: false,
      error: '시작일과 종료일을 모두 입력하세요'
    }
  }

  // Validate date format (YYYY-MM-DD)
  const dateRegex = /^\d{4}-\d{2}-\d{2}$/
  if (!dateRegex.test(startDate)) {
    return {
      isValid: false,
      error: '시작일 형식이 올바르지 않습니다 (YYYY-MM-DD)'
    }
  }

  if (!dateRegex.test(endDate)) {
    return {
      isValid: false,
      error: '종료일 형식이 올바르지 않습니다 (YYYY-MM-DD)'
    }
  }

  // Parse dates
  const startDateObj = new Date(startDate)
  const endDateObj = new Date(endDate)

  // Check for invalid dates
  if (isNaN(startDateObj.getTime())) {
    return {
      isValid: false,
      error: '시작일이 올바른 날짜가 아닙니다'
    }
  }

  if (isNaN(endDateObj.getTime())) {
    return {
      isValid: false,
      error: '종료일이 올바른 날짜가 아닙니다'
    }
  }

  // Check if start_date <= end_date
  if (startDateObj > endDateObj) {
    return {
      isValid: false,
      error: '시작일은 종료일보다 이전이어야 합니다'
    }
  }

  // Check for future dates (KST basis)
  const today = new Date()
  // Set time to midnight to compare only dates
  today.setHours(0, 0, 0, 0)
  endDateObj.setHours(0, 0, 0, 0)

  if (endDateObj > today) {
    return {
      isValid: false,
      error: '종료일은 오늘 이전이어야 합니다'
    }
  }

  return {
    isValid: true,
    error: null
  }
}

/**
 * Strategy parameter definitions and validation rules
 */
const STRATEGY_PARAMS = {
  volume_long_candle: {
    vol_ma_window: { type: 'integer', min: 1, max: 200, description: '이동 평균 윈도우' },
    vol_multiplier: { type: 'float', min: 1.0, max: 10.0, description: '거래량 배수' },
    body_pct: { type: 'float', min: 0.0, max: 1.0, description: '몸통 비율' }
  },
  volume_zone_breakout: {
    volume_window: { type: 'integer', min: 1, max: 200, description: '거래량 윈도우' },
    top_percentile: { type: 'float', min: 0, max: 1.0, exclusive_min: true, description: '상위 백분위수 (0~1)' },
    breakout_buffer: { type: 'float', min: 0.0, max: 1.0, description: '돌파 버퍼' }
  }
}

/**
 * Validates strategy parameters
 * @param {string} strategy - Strategy name
 * @param {object} params - Parameters object
 * @returns {object} Validation result { isValid: boolean, errors: { [field]: string } }
 */
export function validateParams(strategy, params) {
  const errors = {}

  // Check if strategy is supported
  if (!STRATEGY_PARAMS[strategy]) {
    return {
      isValid: false,
      errors: {
        strategy: `지원하지 않는 전략입니다: ${strategy}`
      }
    }
  }

  const paramDefinitions = STRATEGY_PARAMS[strategy]

  // Validate each parameter
  for (const [paramName, definition] of Object.entries(paramDefinitions)) {
    const value = params[paramName]

    // Check if parameter is provided
    if (value === undefined || value === null || value === '') {
      errors[paramName] = `${definition.description}을(를) 입력하세요`
      continue
    }

    const numValue = parseFloat(value)

    // Check if value is a valid number
    if (isNaN(numValue)) {
      errors[paramName] = `${definition.description}은(는) 숫자여야 합니다`
      continue
    }

    // Type-specific validation
    if (definition.type === 'integer') {
      if (!Number.isInteger(numValue)) {
        errors[paramName] = `${definition.description}은(는) 정수여야 합니다`
        continue
      }
    }

    // Range validation
    if (definition.exclusive_min && numValue <= definition.min) {
      errors[paramName] = `${definition.description}은(는) ${definition.min}보다 커야 합니다`
      continue
    }

    if (numValue < definition.min) {
      errors[paramName] = `${definition.description}은(는) ${definition.min} 이상이어야 합니다`
      continue
    }

    if (numValue > definition.max) {
      errors[paramName] = `${definition.description}은(는) ${definition.max} 이하여야 합니다`
      continue
    }
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors
  }
}

/**
 * Validates complete backtest request
 * @param {object} request - Backtest request object
 * @returns {object} Validation result { isValid: boolean, errors: { [field]: string | object } }
 */
export function validateBacktestRequest(request) {
  const errors = {}

  // Validate symbols
  const symbolValidation = validateSymbols(request.symbols || '')
  if (!symbolValidation.isValid) {
    errors.symbols = symbolValidation.error
  }

  // Validate date range
  const dateValidation = validateDateRange(request.start_date, request.end_date)
  if (!dateValidation.isValid) {
    errors.dates = dateValidation.error
  }

  // Validate strategy
  if (!request.strategy) {
    errors.strategy = '전략을 선택하세요'
  }

  // Validate parameters
  if (request.strategy && request.params) {
    const paramValidation = validateParams(request.strategy, request.params)
    if (!paramValidation.isValid) {
      errors.params = paramValidation.errors
    }
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors
  }
}

/**
 * Converts percentage (0-100) to decimal (0-1)
 * @param {number} percentValue - Value in percentage (0-100)
 * @returns {number} Value as decimal (0-1)
 */
export function percentToDecimal(percentValue) {
  if (typeof percentValue !== 'number' || isNaN(percentValue)) {
    return 0
  }
  return percentValue / 100
}

/**
 * Converts decimal (0-1) to percentage (0-100)
 * @param {number} decimalValue - Value as decimal (0-1)
 * @returns {number} Value in percentage (0-100)
 */
export function decimalToPercent(decimalValue) {
  if (typeof decimalValue !== 'number' || isNaN(decimalValue)) {
    return 0
  }
  return decimalValue * 100
}
