/**
 * Data Management API Service
 *
 * 데이터 관리 API와 통신하는 서비스 모듈
 */

import axios from 'axios'

const API_BASE = '/api/data'

/**
 * 데이터 파일 인벤토리 조회
 *
 * @param {Object} params - 조회 파라미터
 * @param {string} params.symbol - 심볼 필터 (선택사항)
 * @param {string} params.timeframe - 타임프레임 필터 (선택사항)
 * @param {number} params.year - 연도 필터 (선택사항)
 * @param {number} params.limit - 조회 수 제한 (기본값: 50)
 * @param {number} params.offset - 오프셋 (기본값: 0)
 * @returns {Promise<Object>} 인벤토리 데이터
 * @throws {Error} API 요청 실패
 */
export async function fetchInventory({
  symbol = null,
  timeframe = null,
  year = null,
  limit = 50,
  offset = 0
}) {
  try {
    const params = new URLSearchParams()

    if (symbol) params.append('symbol', symbol)
    if (timeframe) params.append('timeframe', timeframe)
    if (year) params.append('year', year)

    params.append('limit', limit)
    params.append('offset', offset)

    const response = await axios.get(`${API_BASE}/inventory?${params.toString()}`)
    return response.data
  } catch (error) {
    console.error('Failed to fetch inventory:', error)
    throw error
  }
}

/**
 * 데이터 파일 업로드
 *
 * @param {Object} params - 업로드 파라미터
 * @param {File} params.file - 업로드할 파일
 * @param {string} params.symbol - 심볼 (예: BTC_KRW)
 * @param {string} params.timeframe - 타임프레임 (예: 1D)
 * @param {number} params.year - 연도 (예: 2024)
 * @param {boolean} params.overwrite - 기존 파일 덮어쓰기 여부 (기본값: false)
 * @returns {Promise<Object>} 업로드 결과
 * @throws {Error} 업로드 실패
 */
export async function uploadFile({
  file,
  symbol,
  timeframe,
  year,
  overwrite = false
}) {
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('symbol', symbol)
    formData.append('timeframe', timeframe)
    formData.append('year', year)
    formData.append('overwrite', overwrite)

    const response = await axios.post(`${API_BASE}/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    return response.data
  } catch (error) {
    console.error('Failed to upload file:', error)
    throw error
  }
}
