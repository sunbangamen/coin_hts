import { useState, useEffect } from 'react'
import { getSchedulerStatus, triggerScheduler, convertUtcToLocal, formatErrorMessage } from '../services/schedulerApi'
import '../styles/SchedulerPanel.css'

export default function SchedulerPanel() {
  // Status state
  const [status, setStatus] = useState(null)
  const [statusLoading, setStatusLoading] = useState(true)
  const [statusError, setStatusError] = useState(null)

  // Manual trigger form state
  const [triggerSymbols, setTriggerSymbols] = useState('')
  const [triggerTimeframes, setTriggerTimeframes] = useState('')
  const [triggerDays, setTriggerDays] = useState(1)
  const [triggerOverwrite, setTriggerOverwrite] = useState(false)
  const [triggering, setTriggering] = useState(false)
  const [triggerError, setTriggerError] = useState(null)
  const [triggerSuccess, setTriggerSuccess] = useState(null)

  // Last trigger job ID (for display)
  const [lastTriggeredJobId, setLastTriggeredJobId] = useState(null)

  /**
   * 스케줄러 상태 조회
   */
  const loadSchedulerStatus = async () => {
    setStatusLoading(true)
    setStatusError(null)

    try {
      const data = await getSchedulerStatus()
      setStatus(data)

      // Form 기본값 설정 (첫 로드 시)
      if (!triggerSymbols && data.configuration?.symbols) {
        setTriggerSymbols(data.configuration.symbols.join(','))
      }
      if (!triggerTimeframes && data.configuration?.timeframes) {
        setTriggerTimeframes(data.configuration.timeframes.join(','))
      }
    } catch (error) {
      const errorMessage = formatErrorMessage(error)
      setStatusError(errorMessage)
      setStatus(null)
    } finally {
      setStatusLoading(false)
    }
  }

  // 초기 로드
  useEffect(() => {
    loadSchedulerStatus()
  }, [])

  /**
   * 수동 트리거 실행
   */
  const handleManualTrigger = async (e) => {
    e.preventDefault()
    setTriggerError(null)
    setTriggerSuccess(null)

    // 유효성 검사
    if (!triggerSymbols.trim()) {
      setTriggerError('심볼을 입력하세요 (쉼표로 구분)')
      return
    }

    if (!triggerTimeframes.trim()) {
      setTriggerError('타임프레임을 입력하세요 (쉼표로 구분)')
      return
    }

    if (triggerDays < 1 || triggerDays > 365) {
      setTriggerError('기간은 1~365일 사이여야 합니다')
      return
    }

    setTriggering(true)

    try {
      const symbols = triggerSymbols
        .split(',')
        .map(s => s.trim().toUpperCase())
        .filter(s => s)

      const timeframes = triggerTimeframes
        .split(',')
        .map(t => t.trim().toUpperCase())
        .filter(t => t)

      const result = await triggerScheduler({
        symbols,
        timeframes,
        days: triggerDays,
        overwrite: triggerOverwrite
      })

      if (result.success) {
        setTriggerSuccess(`✅ 작업이 성공적으로 큐에 추가되었습니다 (Job ID: ${result.job_id})`)
        setLastTriggeredJobId(result.job_id)

        // 2초 후 상태 새로고침
        setTimeout(() => {
          loadSchedulerStatus()
        }, 2000)
      }
    } catch (error) {
      const errorMessage = formatErrorMessage(error)
      setTriggerError(errorMessage)
    } finally {
      setTriggering(false)
    }
  }

  /**
   * 상태 배지 렌더링
   */
  const renderStatusBadge = (label, value, color = 'default') => {
    const colorClass = {
      default: 'badge-default',
      success: 'badge-success',
      error: 'badge-error',
      warning: 'badge-warning',
      info: 'badge-info'
    }[color] || 'badge-default'

    return (
      <div className="status-badge">
        <span className="badge-label">{label}</span>
        <span className={`badge-value ${colorClass}`}>{value}</span>
      </div>
    )
  }

  /**
   * 시간 표시 (UTC → 로컬 타임존)
   * 새로운 API 포맷과 이전 포맷 모두 지원
   */
  const formatTime = (utcTime) => {
    if (!utcTime) return '-'
    const converted = convertUtcToLocal(utcTime)
    return (
      <span title={`UTC: ${converted.utc}`} className="time-with-tooltip">
        {converted.local}
      </span>
    )
  }

  /**
   * 작업 상태 배지 렌더링 (API 포맷 호환성)
   * 새로운 포맷(success boolean) 또는 이전 포맷(status string) 모두 지원
   */
  const getJobSuccessBadge = (job) => {
    // 새로운 포맷: { success, message, timestamp, job_id }
    if (typeof job.success === 'boolean') {
      return job.success ? '✅ 성공' : '❌ 실패'
    }
    // 이전 포맷: { status, job_id, start_time, ... }
    const status = job.status || 'unknown'
    switch (status) {
      case 'queued':
        return '✅ 성공'
      case 'failed':
        return '❌ 실패'
      default:
        return '⚠️ 상태 불명'
    }
  }

  /**
   * 작업 메시지 추출 (API 포맷 호환성)
   */
  const getJobMessage = (job) => {
    // 새로운 포맷: message 필드 사용
    if (job.message) {
      return job.message
    }
    // 이전 포맷: status와 job_id로부터 메시지 구성
    const status = job.status || 'unknown'
    const jobId = job.job_id
    if (status === 'queued' && jobId) {
      return `작업 추가됨 (Job ID: ${jobId})`
    }
    if (status === 'failed') {
      return `작업 실패: ${job.error || '알 수 없는 오류'}`
    }
    return `상태: ${status}`
  }

  /**
   * 작업 시간 추출 (API 포맷 호환성)
   */
  const getJobTimestamp = (job) => {
    // 새로운 포맷: timestamp 필드
    if (job.timestamp) {
      return job.timestamp
    }
    // 이전 포맷: start_time 또는 trigger_time
    return job.start_time || job.trigger_time
  }

  /**
   * 작업 ID 추출 (API 포맷 호환성)
   */
  const getJobId = (job) => {
    return job.job_id || job.id || 'N/A'
  }

  return (
    <div className="scheduler-panel">
      {/* 스케줄러 비활성화 상태 */}
      {status && !status.enabled && (
        <div className="scheduler-disabled-warning">
          ⚠️ 자동 스케줄러가 비활성화되어 있습니다 (ENABLE_SCHEDULER=false)
          <br />
          <small>수동 트리거만 사용 가능합니다</small>
        </div>
      )}

      {/* 로딩 상태 */}
      {statusLoading && (
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>스케줄러 상태를 조회 중입니다...</p>
        </div>
      )}

      {/* 에러 상태 */}
      {statusError && (
        <div className="error-message" role="alert">
          ⚠️ {statusError}
        </div>
      )}

      {/* 정상 상태 - 상태 정보 */}
      {!statusLoading && status && (
        <>
          {/* 상단 상태 요약 */}
          <div className="status-summary">
            <h3>스케줄러 상태</h3>

            <div className="status-grid">
              {renderStatusBadge(
                '활성화',
                status.enabled ? '활성' : '비활성',
                status.enabled ? 'success' : 'warning'
              )}

              {renderStatusBadge(
                '실행 중',
                status.running ? '실행 중' : '정지',
                status.running ? 'success' : 'info'
              )}

              {status.redis && renderStatusBadge(
                'Redis',
                status.redis.connected ? '연결됨' : '연결 안 됨',
                status.redis.connected ? 'success' : 'error'
              )}

              {status.rq_queue && renderStatusBadge(
                '큐 크기',
                `${status.rq_queue.size || 0} 작업`,
                status.rq_queue.size > 0 ? 'warning' : 'success'
              )}
            </div>

            {/* 새로고침 버튼 */}
            <button
              className="refresh-btn"
              onClick={loadSchedulerStatus}
              disabled={statusLoading}
              title="상태 새로고침"
            >
              🔄 새로고침
            </button>
          </div>

          {/* 다음 실행 시간 */}
          {status.enabled && status.scheduled_jobs && status.scheduled_jobs.length > 0 && (
            <div className="next-run-section">
              <h4>다음 실행 일정</h4>
              <div className="next-run-list">
                {status.scheduled_jobs.map((job, idx) => (
                  <div key={idx} className="next-run-item">
                    <div className="job-id">{job.id}</div>
                    <div className="job-trigger">{job.trigger}</div>
                    {job.next_run && (
                      <div className="job-next-run">
                        다음 실행: {formatTime(job.next_run)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 현재 설정 */}
          {status.configuration && (
            <div className="configuration-section">
              <h4>현재 설정</h4>
              <div className="config-grid">
                <div className="config-item">
                  <label>실행 시간 (UTC)</label>
                  <span className="config-value">
                    {String(status.configuration.hour).padStart(2, '0')}:
                    {String(status.configuration.minute).padStart(2, '0')}
                  </span>
                  <small>KST = UTC + 9시간</small>
                </div>

                <div className="config-item">
                  <label>심볼</label>
                  <span className="config-value">
                    {status.configuration.symbols?.join(', ') || '-'}
                  </span>
                </div>

                <div className="config-item">
                  <label>타임프레임</label>
                  <span className="config-value">
                    {status.configuration.timeframes?.join(', ') || '-'}
                  </span>
                </div>

                <div className="config-item">
                  <label>수집 기간</label>
                  <span className="config-value">
                    {status.configuration.days || 1} 일
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* 최근 실행 정보 */}
          {status.last_run && status.last_run.timestamp && (
            <div className="last-run-section">
              <h4>최근 실행 정보</h4>
              <div className="last-run-details">
                <div className="run-item">
                  <span className="run-label">실행 시간:</span>
                  <span className="run-value">{formatTime(status.last_run.timestamp)}</span>
                </div>
                <div className="run-item">
                  <span className="run-label">상태:</span>
                  <span className={`run-status ${typeof status.last_run.success === 'boolean' ? (status.last_run.success ? 'success' : 'error') : 'success'}`}>
                    {getJobSuccessBadge(status.last_run)}
                  </span>
                </div>
                {status.last_run.message && (
                  <div className="run-item">
                    <span className="run-label">메시지:</span>
                    <span className="run-value">{status.last_run.message}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 작업 히스토리 */}
          {status.job_history && status.job_history.length > 0 && (
            <div className="job-history-section">
              <h4>작업 히스토리 (최근 {status.job_history.length}개)</h4>
              <div className="job-history-table">
                <table>
                  <thead>
                    <tr>
                      <th>작업 ID</th>
                      <th>상태</th>
                      <th>실행 시간</th>
                      <th>메시지</th>
                    </tr>
                  </thead>
                  <tbody>
                    {status.job_history.map((job, idx) => {
                      const jobId = getJobId(job)
                      const timestamp = getJobTimestamp(job)
                      const statusBadge = getJobSuccessBadge(job)
                      const message = getJobMessage(job)
                      // 새로운 포맷의 success 또는 이전 포맷의 status로부터 성공 여부 판단
                      const isSuccess = typeof job.success === 'boolean' ? job.success : job.status === 'queued'

                      return (
                        <tr key={idx} className={`history-row ${isSuccess ? 'success' : 'error'}`}>
                          <td className="job-id-cell">
                            <code>{jobId}</code>
                          </td>
                          <td className="status-cell">
                            {statusBadge}
                          </td>
                          <td className="time-cell">
                            {formatTime(timestamp)}
                          </td>
                          <td className="message-cell">
                            {message || '-'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* 수동 트리거 폼 */}
      <div className="manual-trigger-section">
        <h3>수동으로 데이터 수집 실행</h3>

        {/* Success Message */}
        {triggerSuccess && (
          <div className="success-message" role="alert">
            {triggerSuccess}
          </div>
        )}

        {/* Error Message */}
        {triggerError && (
          <div className="error-message" role="alert">
            {triggerError}
          </div>
        )}

        <form onSubmit={handleManualTrigger} className="trigger-form">
          {/* Symbols Input */}
          <div className="form-group">
            <label htmlFor="trigger-symbols">심볼 * (쉼표로 구분)</label>
            <input
              id="trigger-symbols"
              type="text"
              placeholder="예: KRW-BTC, KRW-ETH, KRW-XRP"
              value={triggerSymbols}
              onChange={(e) => setTriggerSymbols(e.target.value)}
              disabled={triggering}
              required
            />
            <div className="info-text">여러 심볼은 쉼표(,)로 구분하세요. 예: KRW-BTC,KRW-ETH</div>
          </div>

          {/* Timeframes Input */}
          <div className="form-group">
            <label htmlFor="trigger-timeframes">타임프레임 * (쉼표로 구분)</label>
            <input
              id="trigger-timeframes"
              type="text"
              placeholder="예: 1H, 1D"
              value={triggerTimeframes}
              onChange={(e) => setTriggerTimeframes(e.target.value)}
              disabled={triggering}
              required
            />
            <div className="info-text">지원: 1M, 5M, 15M, 30M, 1H, 4H, 1D, 1W</div>
          </div>

          {/* Days Input */}
          <div className="form-group form-inline">
            <label htmlFor="trigger-days">수집 기간</label>
            <div className="input-with-unit">
              <input
                id="trigger-days"
                type="number"
                min="1"
                max="365"
                value={triggerDays}
                onChange={(e) => setTriggerDays(parseInt(e.target.value) || 1)}
                disabled={triggering}
              />
              <span className="unit">일</span>
            </div>
          </div>

          {/* Overwrite Checkbox */}
          <div className="form-group checkbox">
            <label htmlFor="trigger-overwrite">
              <input
                id="trigger-overwrite"
                type="checkbox"
                checked={triggerOverwrite}
                onChange={(e) => setTriggerOverwrite(e.target.checked)}
                disabled={triggering}
              />
              <span>기존 파일 덮어쓰기</span>
            </label>
            <div className="info-text">체크하면 이미 수집된 데이터를 덮어씁니다</div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            className={`submit-btn ${triggering ? 'loading' : ''}`}
            disabled={!triggerSymbols.trim() || !triggerTimeframes.trim() || triggering}
            aria-busy={triggering}
          >
            {triggering ? '실행 중...' : '🚀 지금 실행'}
          </button>
        </form>

        {/* Info Box */}
        <div className="info-box">
          <h4>📋 수동 트리거 가이드</h4>
          <ul>
            <li>위의 설정으로 즉시 데이터 수집을 시작합니다</li>
            <li>수집된 데이터는 RQ 큐를 통해 백그라운드에서 처리됩니다</li>
            <li>기간 입력: 현재부터 과거 N일간의 데이터를 수집합니다</li>
            <li>작업은 백그라운드에서 실행되며, 상태 새로고침으로 진행 상황을 확인할 수 있습니다</li>
            <li>대량의 데이터 수집 시 시간이 오래 걸릴 수 있습니다</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
