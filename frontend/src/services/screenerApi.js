/**
 * Screener API 서비스 (Feature Breakdown #23, Task 5)
 *
 * 조건 검색 API를 호출하여 조건에 맞는 종목을 필터링하는 서비스
 */

import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/screener`,
  timeout: 30000,
})

/**
 * 조건 검색 실행
 * POST /api/screener/filter
 *
 * @param {Array} conditions - 검색 조건 목록
 * @param {string} logic - 'AND' 또는 'OR'
 * @returns {Promise} 매칭된 종목 목록
 */
export const searchScreener = async (conditions, logic = 'AND') => {
  try {
    const response = await api.post('/filter', {
      conditions,
      logic
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || '조건 검색 실패')
  }
}

/**
 * 검색 가능한 심볼 목록 조회
 * GET /api/screener/symbols
 *
 * @returns {Promise} 검색 가능한 심볼 목록
 */
export const fetchAvailableSymbols = async () => {
  try {
    const response = await api.get('/symbols')
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || '심볼 목록 조회 실패')
  }
}

/**
 * 기본 조건 템플릿
 */
export const CONDITION_TEMPLATES = {
  change_rate: {
    type: 'change_rate',
    operator: '>',
    value: 5,
    period: '1D',
    label: '상승률'
  },
  volume: {
    type: 'volume',
    operator: '>',
    value: 1000,
    period: '1D',
    label: '거래량'
  },
  trade_amount: {
    type: 'trade_amount',
    operator: '>',
    value: 100000000,
    period: '1D',
    label: '거래대금'
  },
  ma_divergence: {
    type: 'ma_divergence',
    operator: '>',
    value: 5,
    period: '1D',
    label: 'MA 이격도'
  },
  ma_alignment: {
    type: 'ma_alignment',
    operator: '==',
    value: 'golden_cross',
    period: '1D',
    label: 'MA 정배열/역배열'
  }
}

/**
 * 조건 타입별 설정 메타데이터
 */
export const CONDITION_CONFIG = {
  change_rate: {
    label: '상승률',
    operators: ['>', '<', '>=', '<=', '=='],
    hasPeriod: true,
    periods: ['1D', '1W', '1M'],
    valueType: 'number',
    placeholder: '예: 5 (5%)',
    unit: '%'
  },
  volume: {
    label: '거래량',
    operators: ['>', '<', '>=', '<=', '=='],
    hasPeriod: true,
    periods: ['1D', '1W', '1M'],
    valueType: 'number',
    placeholder: '예: 1000',
    unit: ''
  },
  trade_amount: {
    label: '거래대금',
    operators: ['>', '<', '>=', '<=', '=='],
    hasPeriod: true,
    periods: ['1D', '1W', '1M'],
    valueType: 'number',
    placeholder: '예: 100000000 (1억)',
    unit: '원'
  },
  ma_divergence: {
    label: 'MA 이격도',
    operators: ['>', '<', '>=', '<=', '=='],
    hasPeriod: false,
    periods: [],
    valueType: 'number',
    placeholder: '예: 5 (5%)',
    unit: '%'
  },
  ma_alignment: {
    label: 'MA 정배열/역배열',
    operators: ['=='],
    hasPeriod: false,
    periods: [],
    valueType: 'select',
    options: [
      { value: 'golden_cross', label: '정배열 (상승)' },
      { value: 'dead_cross', label: '역배열 (하락)' },
      { value: 'mixed', label: '혼조' }
    ]
  }
}

/**
 * 조건 유효성 검증
 */
export const validateCondition = (condition) => {
  const { type, operator, value } = condition

  // 타입 검증
  if (!type || !CONDITION_CONFIG[type]) {
    return { valid: false, error: '유효하지 않은 조건 타입입니다' }
  }

  const config = CONDITION_CONFIG[type]

  // 연산자 검증
  if (!operator || !config.operators.includes(operator)) {
    return { valid: false, error: '유효하지 않은 연산자입니다' }
  }

  // 값 검증
  if (value === null || value === undefined || value === '') {
    return { valid: false, error: '값을 입력해주세요' }
  }

  if (config.valueType === 'number' && isNaN(value)) {
    return { valid: false, error: '숫자를 입력해주세요' }
  }

  return { valid: true }
}
