/**
 * WebSocket 훅 (Task 7 + 개선)
 *
 * 실시간 시세 데이터를 WebSocket을 통해 수신하는 커스텀 훅
 * 자동 재연결, 에러 처리, 상태 관리 포함
 *
 * 환경 변수:
 *   - VITE_WS_BASE_URL: WebSocket 서버 주소 (기본: ws://localhost:8000)
 *   - VITE_ENABLE_LIVE_TICKERS: 실시간 기능 활성화 (기본: true)
 *   - VITE_WS_MAX_RETRIES: 최대 재연결 횟수 (기본: 5)
 *
 * 옵션:
 *   - enabled: false면 WebSocket 연결 시도하지 않음
 *   - silent: true면 에러 시 onError 콜백 호출하지 않고 console에만 남김
 *   - maxRetries: 최대 재연결 횟수 (env 설정 무시)
 */

import { useState, useEffect, useCallback, useRef } from 'react'

const WS_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000'
const ENABLE_LIVE_TICKERS = import.meta.env.VITE_ENABLE_LIVE_TICKERS !== 'false'
const ENV_MAX_RETRIES = parseInt(import.meta.env.VITE_WS_MAX_RETRIES || '5', 10)

export function useWebSocket(path, onMessage, onError, options = {}) {
  const {
    enabled = ENABLE_LIVE_TICKERS,
    silent = false,
    maxRetries = ENV_MAX_RETRIES
  } = options

  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)
  const [retryCount, setRetryCount] = useState(0)
  const [status, setStatus] = useState(enabled ? 'idle' : 'disabled')
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)

  const RECONNECT_DELAY = 3000 // 3초

  // ============================================================================
  // WebSocket 연결 관리
  // ============================================================================

  const connect = useCallback(() => {
    // 기능이 비활성화되었거나 이미 연결 중이면 반환
    if (!enabled || wsRef.current) {
      return
    }

    try {
      const wsAddress = `${WS_URL}${path}`
      console.log(`[WebSocket] Connecting to ${wsAddress}`)
      setStatus('connecting')

      const ws = new WebSocket(wsAddress)

      ws.onopen = () => {
        console.log('[WebSocket] Connected')
        setConnected(true)
        setError(null)
        setRetryCount(0)
        setStatus('live')
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessage(data)
        } catch (err) {
          console.error('[WebSocket] Error parsing message:', err)
        }
      }

      ws.onerror = (event) => {
        console.error('[WebSocket] Error:', event)
        const errorMsg = 'WebSocket 연결 오류'
        setError(errorMsg)
        setConnected(false)

        // silent 모드: 에러 콜백 호출 안 함, console에만 남김
        if (!silent && onError) {
          onError(errorMsg)
        }
      }

      ws.onclose = () => {
        console.log('[WebSocket] Disconnected')
        setConnected(false)
        wsRef.current = null

        // 자동 재연결
        if (retryCount < maxRetries) {
          const nextRetry = retryCount + 1
          const delay = RECONNECT_DELAY * Math.pow(1.5, retryCount) // 지수 백오프

          console.log(
            `[WebSocket] Reconnecting in ${Math.round(delay / 1000)}s ` +
            `(attempt ${nextRetry}/${maxRetries})`
          )

          setRetryCount(nextRetry)

          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, delay)
        } else {
          const maxRetriesMsg = `WebSocket: 최대 재연결 횟수 초과 (${maxRetries}회)`
          console.error(`[WebSocket] ${maxRetriesMsg}`)
          setError(maxRetriesMsg)
          setStatus('failed')

          // silent 모드: 에러 콜백 호출 안 함
          if (!silent && onError) {
            onError(maxRetriesMsg)
          }
        }
      }

      wsRef.current = ws
    } catch (err) {
      console.error('[WebSocket] Connection error:', err)
      const errorMsg = `WebSocket 연결 실패: ${err.message}`
      setError(errorMsg)
      setConnected(false)
      setStatus('failed')

      // silent 모드: 에러 콜백 호출 안 함
      if (!silent && onError) {
        onError(errorMsg)
      }
    }
  }, [path, onMessage, onError, enabled, silent, retryCount, maxRetries])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (wsRef.current) {
      console.log('[WebSocket] Closing connection')
      wsRef.current.close()
      wsRef.current = null
    }

    setConnected(false)
    setRetryCount(0)
  }, [])

  // ============================================================================
  // 라이프사이클
  // ============================================================================

  useEffect(() => {
    connect()

    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  // ============================================================================
  // 반환 값
  // ============================================================================

  return {
    connected,
    error,
    retryCount,
    status, // 'idle' | 'connecting' | 'live' | 'disabled' | 'failed'
    enabled,
    ws: wsRef.current,
    reconnect: () => {
      disconnect()
      setRetryCount(0)
      setStatus('idle')
      connect()
    }
  }
}
