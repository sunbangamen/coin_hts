import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * 실시간 시뮬레이션 WebSocket 연결 관리 훅
 *
 * 신호, 포지션, 성과 지표를 실시간으로 수신하고 상태를 관리합니다.
 *
 * @param {string} wsUrl WebSocket 서버 URL (기본값: ws://localhost:8001)
 * @param {Object} options 옵션
 *   @param {string} options.token JWT 인증 토큰 (선택사항)
 *   @param {number} options.authTimeout 인증 타임아웃 (ms, 기본값: 5000)
 */
export const useSimulation = (wsUrl = 'ws://localhost:8001', options = {}) => {
  const { token = null, authTimeout = 5000 } = options;

  const [connected, setConnected] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [hasRealtimeData, setHasRealtimeData] = useState(false); // WebSocket 데이터 유효성 플래그
  const [signals, setSignals] = useState([]);
  const [positions, setPositions] = useState([]);
  const [performance, setPerformance] = useState(null);
  const [error, setError] = useState(null);
  const [simulationStatus, setSimulationStatus] = useState(null);

  const ws = useRef(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  const authTimeoutRef = useRef(null);
  const shouldStopReconnecting = useRef(false); // 재연결 중단 플래그

  /**
   * WebSocket 연결 설정
   */
  const connect = useCallback(() => {
    try {
      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = () => {
        console.log('WebSocket connected');
        setConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
        setAuthenticated(false); // 재연결 시 인증 상태 리셋

        // 인증 메시지 전송
        if (token) {
          ws.current.send(JSON.stringify({
            type: 'auth',
            token: token,
          }));

          // 인증 타임아웃 설정
          authTimeoutRef.current = setTimeout(() => {
            setError('인증 타임아웃: 서버에서 응답이 없습니다');
            setConnected(false);
            ws.current?.close();
          }, authTimeout);
        } else {
          // 토큰 없으면 명시적으로 에러 표시 및 재연결 중단
          setError('JWT 토큰이 필요합니다. 토큰을 설정한 후 다시 시도하세요.');
          setConnected(false);
          shouldStopReconnecting.current = true; // 재연결 중단
          ws.current?.close();
        }
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // 인증 확인 후 타임아웃 정리
          if (data.type === 'connection_established' || data.type === 'error') {
            if (authTimeoutRef.current) {
              clearTimeout(authTimeoutRef.current);
              authTimeoutRef.current = null;
            }
          }

          handleMessage(data);
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('WebSocket 연결 오류');
      };

      ws.current.onclose = () => {
        console.log('WebSocket disconnected');
        setConnected(false);
        setAuthenticated(false); // 재연결 시 인증 상태 리셋
        setHasRealtimeData(false); // WebSocket 데이터 무효화

        // WebSocket 데이터 초기화 (REST fallback 사용)
        setSignals([]);
        setPositions([]);
        setPerformance(null);
        // simulationStatus는 REST에서 갱신되도록 유지

        // 타임아웃 정리
        if (authTimeoutRef.current) {
          clearTimeout(authTimeoutRef.current);
          authTimeoutRef.current = null;
        }

        // 재연결 시도 (토큰이 있고, 재연결 중단 플래그가 없을 때만)
        if (
          !shouldStopReconnecting.current &&
          token &&
          reconnectAttempts.current < maxReconnectAttempts
        ) {
          reconnectAttempts.current += 1;
          const delay = Math.pow(2, reconnectAttempts.current) * 1000;
          console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})`);
          setTimeout(connect, delay);
        } else if (shouldStopReconnecting.current) {
          // 재연결 중단 플래그가 설정되었으면 에러 메시지 유지
          console.log('Reconnection stopped due to authentication or token issues');
        } else if (!token) {
          setError('JWT 토큰이 필요합니다. 토큰을 설정한 후 다시 시도하세요.');
        } else {
          setError('WebSocket 연결 실패: 최대 재연결 시도 횟수 초과');
        }
      };
    } catch (err) {
      console.error('Failed to connect WebSocket:', err);
      setError('WebSocket 연결 실패');
    }
  }, [wsUrl, token, authTimeout]);

  /**
   * WebSocket 메시지 처리
   */
  const handleMessage = useCallback((data) => {
    const { type, data: payload } = data;

    switch (type) {
      case 'connection_established':
        // 인증 성공
        console.log('Authentication successful');
        setAuthenticated(true);
        setHasRealtimeData(true); // WebSocket 데이터 유효화
        setError(null);
        shouldStopReconnecting.current = false; // 재연결 중단 플래그 해제
        break;

      case 'error':
        // 에러 처리
        if (payload?.code === 'AUTH_FAILED') {
          console.error('Authentication failed:', payload?.message);
          setError('인증 실패: ' + (payload?.message || '토큰이 유효하지 않습니다'));
          setConnected(false);
          shouldStopReconnecting.current = true; // 인증 실패 시 재연결 중단
          ws.current?.close();
        } else {
          setError('서버 오류: ' + (payload?.message || 'Unknown error'));
        }
        break;

      case 'signal_created':
        // 새로운 신호 추가
        setSignals((prev) => [payload, ...prev].slice(0, 100)); // 최대 100개 유지
        break;

      case 'position_opened':
        // 새로운 포지션 추가
        setPositions((prev) => [...prev, payload]);
        break;

      case 'position_closed':
        // 닫힌 포지션 제거
        setPositions((prev) =>
          prev.filter((pos) => pos.position_id !== payload.position_id)
        );
        break;

      case 'position_updated':
        // 포지션 업데이트 (미실현 손익 등)
        setPositions((prev) =>
          prev.map((pos) =>
            pos.position_id === payload.position_id ? payload : pos
          )
        );
        break;

      case 'performance_snapshot':
        // 성과 스냅샷 업데이트
        setPerformance(payload);
        break;

      case 'simulation_status':
        // 시뮬레이션 상태 업데이트
        setSimulationStatus(payload);
        break;

      case 'heartbeat':
        // 하트비트 (상태 확인용)
        console.debug('Heartbeat received');
        break;

      default:
        console.warn('Unknown message type:', type);
    }
  }, []);

  /**
   * WebSocket 연결 종료
   */
  const disconnect = useCallback(() => {
    if (ws.current) {
      ws.current.close();
      ws.current = null;
      setConnected(false);
    }
  }, []);

  /**
   * WebSocket 메시지 전송
   */
  const send = useCallback((message) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      try {
        ws.current.send(JSON.stringify(message));
      } catch (err) {
        console.error('Failed to send WebSocket message:', err);
        setError('메시지 전송 실패');
      }
    } else {
      setError('WebSocket이 연결되지 않았습니다');
    }
  }, []);

  /**
   * 심볼 구독
   */
  const subscribe = useCallback((symbols) => {
    send({
      type: 'subscribe',
      symbols: Array.isArray(symbols) ? symbols : [symbols],
    });
  }, [send]);

  /**
   * 신호 초기화
   */
  const clearSignals = useCallback(() => {
    setSignals([]);
  }, []);

  /**
   * 포지션 초기화
   */
  const clearPositions = useCallback(() => {
    setPositions([]);
  }, []);

  // 컴포넌트 마운트 시 연결, 언마운트 시 종료
  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    // 상태
    connected,
    authenticated,
    hasRealtimeData, // WebSocket 데이터 유효성
    signals,
    positions,
    performance,
    error,
    simulationStatus,

    // 메서드
    send,
    subscribe,
    disconnect,
    clearSignals,
    clearPositions,
  };
};

export default useSimulation;
