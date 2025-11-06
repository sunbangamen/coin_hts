/**
 * Scheduler API Service
 *
 * 자동 데이터 수집 스케줄러와 통신하는 서비스 모듈
 */

import axios from 'axios'

const API_BASE = '/api/scheduler'

/**
 * 스케줄러 상태 조회
 *
 * @returns {Promise<Object>} 스케줄러 상태 정보
 *   - enabled: 활성화 여부
 *   - running: 실행 중 여부
 *   - redis: Redis 연결 상태
 *   - scheduled_jobs: 예약된 작업 목록
 *   - last_run: 마지막 실행 정보
 *   - job_history: 최근 작업 히스토리
 *   - rq_queue: RQ 큐 상태
 *   - configuration: 현재 설정
 * @throws {Error} API 요청 실패
 */
export async function getSchedulerStatus() {
  try {
    const response = await axios.get(`${API_BASE}/status`)
    return response.data
  } catch (error) {
    console.error('Failed to fetch scheduler status:', error)
    throw new Error(
      error.response?.data?.detail ||
      error.message ||
      '스케줄러 상태 조회 실패'
    )
  }
}

/**
 * 수동으로 데이터 수집 배치 작업 트리거
 *
 * @param {Object} params - 트리거 파라미터
 * @param {Array<string>} params.symbols - 수집할 심볼 (예: ['KRW-BTC', 'KRW-ETH'])
 * @param {Array<string>} params.timeframes - 수집할 타임프레임 (예: ['1H', '1D'])
 * @param {number} params.days - 수집 기간 (기본값: 1)
 * @param {boolean} params.overwrite - 기존 파일 덮어쓰기 여부 (기본값: false)
 * @returns {Promise<Object>} 작업 결과
 *   - success: 성공 여부
 *   - job_id: RQ 작업 ID
 *   - message: 결과 메시지
 * @throws {Error} 트리거 실패
 */
export async function triggerScheduler({
  symbols = [],
  timeframes = [],
  days = 1,
  overwrite = false
}) {
  try {
    const payload = {
      symbols: symbols && symbols.length > 0 ? symbols : undefined,
      timeframes: timeframes && timeframes.length > 0 ? timeframes : undefined,
      days,
      overwrite
    }

    const response = await axios.post(`${API_BASE}/trigger`, payload)
    return response.data
  } catch (error) {
    console.error('Failed to trigger scheduler:', error)
    throw new Error(
      error.response?.data?.detail ||
      error.message ||
      '스케줄러 트리거 실패'
    )
  }
}

/**
 * 타임존 변환 유틸리티
 * UTC 시간을 로컬 시간으로 변환
 *
 * @param {string} utcTime - UTC 시간 문자열 (ISO 형식)
 * @returns {Object} 로컬 시간 정보
 *   - local: 로컬 타임존으로 변환된 시간 문자열
 *   - utc: 원본 UTC 시간 문자열
 */
export function convertUtcToLocal(utcTime) {
  if (!utcTime) return { local: null, utc: null }

  try {
    const date = new Date(utcTime)
    const localTime = new Intl.DateTimeFormat('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    }).format(date)

    return {
      local: localTime,
      utc: utcTime
    }
  } catch (error) {
    console.error('Failed to convert time:', error)
    return { local: utcTime, utc: utcTime }
  }
}

/**
 * 오류 메시지 포맷팅
 *
 * @param {Error} error - 에러 객체
 * @returns {string} 사용자 친화적인 오류 메시지
 */
export function formatErrorMessage(error) {
  if (error.message.includes('스케줄러')) {
    return error.message
  }

  if (error.response?.status === 503) {
    return 'Backend 서버에 연결할 수 없습니다. 나중에 다시 시도하세요.'
  }

  if (error.response?.status === 500) {
    return '서버 오류가 발생했습니다.'
  }

  return error.message || '알 수 없는 오류가 발생했습니다.'
}
