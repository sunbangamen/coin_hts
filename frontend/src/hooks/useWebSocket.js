/**
 * WebSocket 훅 (Task 7)
 *
 * 실시간 시세 데이터를 WebSocket을 통해 수신하는 커스텀 훅
 * 자동 재연결, 에러 처리, 상태 관리 포함
 */

import { useState, useEffect, useCallback, useRef } from 'react'

const WS_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000'

export function useWebSocket(path, onMessage, onError) {
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)
  const [retryCount, setRetryCount] = useState(0)
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)

  const MAX_RETRIES = 5
  const RECONNECT_DELAY = 3000 // 3초

  // ============================================================================
  // WebSocket 연결 관리
  // ============================================================================

  const connect = useCallback(() => {
    if (wsRef.current) {
      return // 이미 연결 중
    }

    try {
      const wsAddress = `${WS_URL}${path}`
      console.log(`[WebSocket] Connecting to ${wsAddress}`)

      const ws = new WebSocket(wsAddress)

      ws.onopen = () => {
        console.log('[WebSocket] Connected')
        setConnected(true)
        setError(null)
        setRetryCount(0)
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

        if (onError) {
          onError(errorMsg)
        }
      }

      ws.onclose = () => {
        console.log('[WebSocket] Disconnected')
        setConnected(false)
        wsRef.current = null

        // 자동 재연결
        if (retryCount < MAX_RETRIES) {
          const nextRetry = retryCount + 1
          const delay = RECONNECT_DELAY * Math.pow(1.5, retryCount) // 지수 백오프

          console.log(
            `[WebSocket] Reconnecting in ${Math.round(delay / 1000)}s ` +
            `(attempt ${nextRetry}/${MAX_RETRIES})`
          )

          setRetryCount(nextRetry)

          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, delay)
        } else {
          const maxRetriesMsg = `WebSocket: 최대 재연결 횟수 초과 (${MAX_RETRIES}회)`
          console.error(`[WebSocket] ${maxRetriesMsg}`)
          setError(maxRetriesMsg)

          if (onError) {
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

      if (onError) {
        onError(errorMsg)
      }
    }
  }, [path, onMessage, onError, retryCount])

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
    ws: wsRef.current,
    reconnect: () => {
      disconnect()
      setRetryCount(0)
      connect()
    }
  }
}
