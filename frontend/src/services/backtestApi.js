/**
 * Backtest API Service (Phase 2)
 *
 * 백테스트 결과 조회 및 히스토리 관리 API와 통신하는 서비스 모듈
 */

import axios from 'axios'

const API_BASE = '/api/backtests'

/**
 * 최신 백테스트 결과 조회
 *
 * @returns {Promise<Object>} 최신 백테스트 결과 (BacktestResponse)
 * @throws {Error} API 요청 실패
 */
export async function fetchLatestBacktest() {
  try {
    const response = await axios.get(`${API_BASE}/latest`)
    return response.data
  } catch (error) {
    console.error('Failed to fetch latest backtest:', error)
    throw error
  }
}

/**
 * 백테스트 히스토리 조회
 *
 * @param {Object} params - 조회 파라미터
 * @param {number} params.limit - 조회 개수 (기본값: 10, 최대: 100)
 * @param {number} params.offset - 시작 위치 (기본값: 0)
 * @param {string} params.strategy - 전략명 필터 (선택사항)
 * @returns {Promise<Object>} 히스토리 데이터 (BacktestHistoryResponse)
 * @throws {Error} API 요청 실패
 */
export async function fetchBacktestHistory({
  limit = 10,
  offset = 0,
  strategy = null
}) {
  try {
    const params = new URLSearchParams()

    params.append('limit', Math.min(Math.max(limit, 1), 100))
    params.append('offset', Math.max(offset, 0))

    if (strategy) params.append('strategy', strategy)

    const response = await axios.get(`${API_BASE}/history?${params.toString()}`)
    return response.data
  } catch (error) {
    console.error('Failed to fetch backtest history:', error)
    throw error
  }
}

/**
 * 백테스트 결과 파일 다운로드
 *
 * @param {string} runId - 실행 ID
 * @returns {Promise<void>} 파일 다운로드 트리거
 * @throws {Error} 다운로드 실패
 */
export async function downloadBacktestResult(runId) {
  try {
    const response = await axios.get(`${API_BASE}/${runId}/download`, {
      responseType: 'blob'
    })

    // Blob을 URL로 변환하여 다운로드 트리거
    const url = window.URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `backtest_${runId}.json`)
    document.body.appendChild(link)
    link.click()
    link.parentNode.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error('Failed to download backtest result:', error)
    throw error
  }
}

/**
 * 백테스트 결과를 CSV로 변환하여 다운로드
 *
 * @param {string} runId - 실행 ID
 * @returns {Promise<void>} CSV 다운로드 트리거
 * @throws {Error} 변환 또는 다운로드 실패
 */
export async function downloadBacktestAsCSV(runId) {
  try {
    const response = await axios.get(`${API_BASE}/${runId}/download`)
    const data = response.data

    // 신호 데이터를 CSV로 변환 (symbols[0].signals 기준)
    if (!data.symbols || data.symbols.length === 0) {
      throw new Error('No symbols found in backtest result')
    }

    const signals = data.symbols[0]?.signals || []
    let csv = 'Symbol,Signal,Entry,Exit,Return,HoldBars\n'

    signals.forEach(signal => {
      csv += `${signal.symbol || ''},${signal.signal || ''},${signal.entry || ''},${signal.exit || ''},${signal.return || ''},${signal.hold_bars || ''}\n`
    })

    // CSV 다운로드
    const url = window.URL.createObjectURL(new Blob([csv]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `backtest_${runId}.csv`)
    document.body.appendChild(link)
    link.click()
    link.parentNode.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error('Failed to download backtest as CSV:', error)
    throw error
  }
}
