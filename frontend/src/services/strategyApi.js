/**
 * Strategy Preset API Service (Phase 3)
 *
 * 전략 프리셋 저장/조회 API와 통신하는 서비스 모듈
 */

import axios from 'axios'

const API_BASE = '/api/strategies/presets'

/**
 * 모든 프리셋 조회
 *
 * @returns {Promise<Array>} 프리셋 배열
 * @throws {Error} API 요청 실패
 */
export async function getPresets() {
  try {
    const response = await axios.get(API_BASE)
    return response.data
  } catch (error) {
    console.error('Failed to fetch presets:', error)
    throw error
  }
}

/**
 * 특정 프리셋 조회
 *
 * @param {string} name - 프리셋 이름
 * @returns {Promise<Object>} 프리셋 상세 정보
 * @throws {Error} API 요청 실패 또는 프리셋 없음
 */
export async function getPreset(name) {
  try {
    const response = await axios.get(`${API_BASE}/${name}`)
    return response.data
  } catch (error) {
    console.error(`Failed to fetch preset '${name}':`, error)
    throw error
  }
}

/**
 * 새 프리셋 생성
 *
 * @param {Object} preset - 프리셋 정보
 * @param {string} preset.name - 프리셋 이름
 * @param {string} preset.strategy - 전략명
 * @param {Object} preset.params - 전략 파라미터
 * @param {string} preset.description - 프리셋 설명 (선택사항)
 * @returns {Promise<Object>} 생성된 프리셋
 * @throws {Error} API 요청 실패 또는 유효하지 않은 입력
 */
export async function savePreset(preset) {
  try {
    const response = await axios.post(API_BASE, {
      name: preset.name,
      strategy: preset.strategy,
      params: preset.params,
      description: preset.description || ''
    })
    return response.data
  } catch (error) {
    console.error('Failed to save preset:', error)
    throw error
  }
}

/**
 * 프리셋 업데이트
 *
 * @param {string} name - 프리셋 이름
 * @param {Object} preset - 업데이트할 프리셋 정보
 * @param {string} preset.strategy - 전략명
 * @param {Object} preset.params - 전략 파라미터
 * @param {string} preset.description - 프리셋 설명
 * @returns {Promise<Object>} 업데이트된 프리셋
 * @throws {Error} API 요청 실패 또는 프리셋 없음
 */
export async function updatePreset(name, preset) {
  try {
    const response = await axios.put(`${API_BASE}/${name}`, {
      name: name,
      strategy: preset.strategy,
      params: preset.params,
      description: preset.description
    })
    return response.data
  } catch (error) {
    console.error(`Failed to update preset '${name}':`, error)
    throw error
  }
}

/**
 * 프리셋 삭제
 *
 * @param {string} name - 프리셋 이름
 * @returns {Promise<void>} 삭제 완료
 * @throws {Error} API 요청 실패 또는 프리셋 없음
 */
export async function deletePreset(name) {
  try {
    await axios.delete(`${API_BASE}/${name}`)
  } catch (error) {
    console.error(`Failed to delete preset '${name}':`, error)
    throw error
  }
}
