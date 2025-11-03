/**
 * 숫자 포맷팅 유틸리티
 */

/**
 * 백분율로 포맷
 * @param {number} value - 소수점 값 (0.05 = 5%)
 * @param {number} digits - 소수점 자릿수 (기본값: 2)
 * @returns {string} 포맷된 백분율 문자열
 */
export const formatPercent = (value, digits = 2) => {
  if (value === undefined || value === null) {
    return 'N/A';
  }
  return (value * 100).toFixed(digits) + '%';
};

/**
 * 정수로 포맷 (천 단위 구분자)
 * @param {number} value - 정수
 * @returns {string} 포맷된 정수 문자열
 */
export const formatNumber = (value) => {
  if (value === undefined || value === null) {
    return 'N/A';
  }
  return Math.round(value).toLocaleString();
};

/**
 * 소수점으로 포맷 (향후 신호 테이블 구현 시 사용)
 * @param {number} value - 숫자
 * @param {number} digits - 소수점 자릿수 (기본값: 2)
 * @returns {string} 포맷된 숫자 문자열
 */
export const formatDecimal = (value, digits = 2) => {
  if (value === undefined || value === null) {
    return 'N/A';
  }
  return value.toFixed(digits);
};

/**
 * 날짜/시간 포맷 (향후 신호 테이블 구현 시 사용)
 * @param {string} dateString - ISO 8601 형식 날짜 문자열
 * @returns {string} YYYY-MM-DD HH:mm 형식
 */
export const formatDateTime = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    const date = new Date(dateString);
    return date.toLocaleString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).replace(/\./g, '-').replace(/\s/, ' ');
  } catch {
    return dateString;
  }
};

/**
 * 시간만 포맷 (향후 신호 테이블 구현 시 사용)
 * @param {string} timeString - ISO 8601 형식 시간 문자열
 * @returns {string} HH:mm:ss 형식
 */
export const formatTime = (timeString) => {
  if (!timeString) return 'N/A';
  try {
    const date = new Date(timeString);
    return date.toLocaleTimeString('ko-KR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return timeString;
  }
};

/**
 * 값의 CSS 클래스 반환 (양수/음수)
 * @param {number} value - 숫자
 * @returns {string} 'positive' 또는 'negative'
 */
export const getValueClass = (value) => {
  if (value === undefined || value === null) {
    return 'neutral';
  }
  return value >= 0 ? 'positive' : 'negative';
};
