import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * 실시간 시뮬레이션 WebSocket 연결 관리 훅
 *
 * 신호, 포지션, 성과 지표를 실시간으로 수신하고 상태를 관리합니다.
 */
export const useSimulation = (wsUrl = 'ws://localhost:8001') => {
  const [connected, setConnected] = useState(false);
  const [signals, setSignals] = useState([]);
  const [positions, setPositions] = useState([]);
  const [performance, setPerformance] = useState(null);
  const [error, setError] = useState(null);
  const [simulationStatus, setSimulationStatus] = useState(null);

  const ws = useRef(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

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

        // 인증 메시지 전송 (필요시)
        // ws.current.send(JSON.stringify({
        //   type: 'auth',
        //   token: 'your-token-here'
        // }));
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
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

        // 재연결 시도
        if (reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current += 1;
          const delay = Math.pow(2, reconnectAttempts.current) * 1000;
          console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})`);
          setTimeout(connect, delay);
        } else {
          setError('WebSocket 연결 실패: 최대 재연결 시도 횟수 초과');
        }
      };
    } catch (err) {
      console.error('Failed to connect WebSocket:', err);
      setError('WebSocket 연결 실패');
    }
  }, [wsUrl]);

  /**
   * WebSocket 메시지 처리
   */
  const handleMessage = useCallback((data) => {
    const { type, data: payload } = data;

    switch (type) {
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
