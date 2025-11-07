/**
 * Chart Data Transformation Utilities
 *
 * 차트 렌더링을 위한 데이터 변환 함수들
 * 재사용 가능한 유틸리티로 설계
 */

/**
 * PerformancePoint 타입 정의
 */
export interface PerformancePoint {
  timestamp: string;
  equity: number;
  drawdown?: number;
}

/**
 * Drawdown 차트 데이터 계산
 *
 * 누적 수익률(equity)로부터 낙폭(drawdown)을 계산합니다.
 * 낙폭 = (현재 수익률 - 최고 수익률) / 최고 수익률
 *
 * @param performanceData - 성과곡선 데이터 배열
 * @returns 낙폭 계산된 데이터 배열
 *
 * @example
 * const data = [
 *   { timestamp: "2024-01-01", equity: 1.05 },
 *   { timestamp: "2024-01-02", equity: 1.10 },
 *   { timestamp: "2024-01-03", equity: 1.08 }
 * ];
 * const drawdownData = calculateDrawdownData(data);
 * // [
 * //   { timestamp: "2024-01-01", drawdown: 0, equity: 1.05 },
 * //   { timestamp: "2024-01-02", drawdown: 0, equity: 1.10 },
 * //   { timestamp: "2024-01-03", drawdown: -1.82, equity: 1.08 }
 * // ]
 */
export const calculateDrawdownData = (
  performanceData: PerformancePoint[]
): Array<{ timestamp: string; drawdown: number; equity: number }> => {
  if (!performanceData || performanceData.length === 0) {
    return [];
  }

  let maxEquity = 1.0;
  return performanceData.map((point) => {
    if (point.equity > maxEquity) {
      maxEquity = point.equity;
    }
    // 낙폭을 퍼센트로 변환
    const drawdown = ((point.equity - maxEquity) / maxEquity) * 100;

    return {
      timestamp: point.timestamp,
      drawdown: parseFloat(drawdown.toFixed(2)),
      equity: point.equity,
    };
  });
};

/**
 * Bin 개수 자동 조정
 *
 * 신호 개수에 따라 최적의 bin 개수를 결정합니다.
 *
 * @param signalCount - 신호 개수
 * @returns 권장 bin 개수
 */
export const getBinCount = (signalCount: number): number => {
  if (signalCount < 30) return 5;
  if (signalCount <= 100) return 10;
  if (signalCount <= 500) return 15;
  return 20;
};

/**
 * 신호 타입 정의
 */
export interface APISignal {
  symbol: string;
  type: string;
  timestamp: string;
  entry_price: number;
  exit_price: number;
  return_pct: number;
}

/**
 * Returns Distribution 차트 데이터 계산
 *
 * 거래 신호의 수익률을 구간(bin)으로 분류하여 히스토그램 데이터를 생성합니다.
 *
 * @param signals - 거래 신호 배열
 * @returns 분포 데이터 배열
 *
 * @example
 * const signals = [
 *   { return_pct: 0.03 }, // 3%
 *   { return_pct: 0.05 }, // 5%
 *   { return_pct: -0.02 } // -2%
 * ];
 * const distribution = calculateReturnsDistribution(signals);
 */
export const calculateReturnsDistribution = (
  signals: APISignal[]
): Array<{ range: string; count: number; percentage: number }> => {
  if (!signals || signals.length === 0) {
    return [];
  }

  // 수익률을 퍼센트로 변환
  const returns = signals.map((s) => s.return_pct * 100);

  const minReturn = Math.min(...returns);
  const maxReturn = Math.max(...returns);

  // 특수 케이스: 모든 값이 동일한 경우
  if (minReturn === maxReturn) {
    return [
      {
        range: `${minReturn.toFixed(1)}%`,
        count: signals.length,
        percentage: 100,
      },
    ];
  }

  const binCount = getBinCount(signals.length);
  const binWidth = (maxReturn - minReturn) / binCount;

  // 구간별 카운트 초기화
  const distribution = Array(binCount).fill(0);

  // 각 신호를 해당 구간에 분류
  returns.forEach((ret) => {
    let binIndex = Math.floor((ret - minReturn) / binWidth);
    // 마지막 bin 처리 (edge case: maxReturn에 정확히 해당하는 값)
    binIndex = Math.min(binIndex, binCount - 1);
    distribution[binIndex]++;
  });

  // 차트 데이터로 변환
  return distribution.map((count, i) => {
    const rangeStart = minReturn + i * binWidth;
    const rangeEnd = minReturn + (i + 1) * binWidth;

    // 마지막 구간은 maxReturn까지 포함
    const rangeLabel =
      i === binCount - 1
        ? `${rangeStart.toFixed(1)}% ~ ${rangeEnd.toFixed(1)}%`
        : `${rangeStart.toFixed(1)}% ~ ${rangeEnd.toFixed(1)}%`;

    return {
      range: rangeLabel,
      count: count,
      percentage: parseFloat(((count / signals.length) * 100).toFixed(1)),
    };
  });
};

/**
 * Symbol Result 타입 정의
 */
export interface SymbolResult {
  symbol: string;
  signals?: APISignal[];
  performance_curve?: PerformancePoint[];
  win_rate?: number;
  avg_return?: number;
  max_drawdown?: number;
  avg_hold_bars?: number;
}

/**
 * Multi-Symbol 데이터 병합
 *
 * 여러 심볼의 성과곡선 데이터를 하나의 객체로 병합합니다.
 * 모든 타임스탬프를 포함하고, 각 심볼의 equity 값을 추가합니다.
 *
 * @param symbols - 심볼 결과 배열
 * @returns 병합된 데이터 배열
 *
 * @example
 * const symbols = [
 *   {
 *     symbol: "BTC_KRW",
 *     performance_curve: [
 *       { timestamp: "2024-01-01", equity: 1.02 }
 *     ]
 *   },
 *   {
 *     symbol: "ETH_KRW",
 *     performance_curve: [
 *       { timestamp: "2024-01-01", equity: 1.015 }
 *     ]
 *   }
 * ];
 * const merged = mergeSymbolData(symbols);
 */
export const mergeSymbolData = (
  symbols: SymbolResult[]
): Array<{ timestamp: string; [key: string]: any }> => {
  if (!symbols || symbols.length === 0) {
    return [];
  }

  // 모든 타임스탬프 수집
  const timestampSet = new Set<string>();
  symbols.forEach((symbol) => {
    if (symbol.performance_curve) {
      symbol.performance_curve.forEach((point) => {
        timestampSet.add(point.timestamp);
      });
    }
  });

  // 타임스탬프 정렬
  const sortedTimestamps = Array.from(timestampSet).sort();

  // 각 타임스탬프별로 모든 심볼의 데이터 통합
  return sortedTimestamps.map((timestamp) => {
    const dataPoint: { timestamp: string; [key: string]: any } = { timestamp };

    symbols.forEach((symbol) => {
      const point = symbol.performance_curve?.find(
        (p) => p.timestamp === timestamp
      );
      if (point) {
        // equity를 퍼센트로 변환 (1.05 -> 105)
        dataPoint[symbol.symbol] = parseFloat(
          (point.equity * 100).toFixed(2)
        );
      }
    });

    return dataPoint;
  });
};

/**
 * 심볼 색상 팔레트
 */
const colorPalette = [
  '#2c3e50', // BTC_KRW (다크 블루)
  '#667eea', // ETH_KRW (퍼플)
  '#f39c12', // 추가 심볼 (주황)
  '#e74c3c', // 추가 심볼 (빨강)
  '#3498db', // 추가 심볼 (파랑)
];

/**
 * 심볼별 색상 획득
 *
 * 팔레트에서 색상을 가져오거나, 팔레트를 초과할 경우 HSL fallback 사용
 *
 * @param symbolIndex - 심볼 인덱스
 * @returns 색상 코드
 */
export const getSymbolColor = (symbolIndex: number): string => {
  if (symbolIndex < colorPalette.length) {
    return colorPalette[symbolIndex];
  }

  // Fallback: HSL 회전으로 추가 색상 생성
  const hue = (symbolIndex * 60) % 360;
  return `hsl(${hue}, 70%, 50%)`;
};

/**
 * 최대 낙폭과 현재 낙폭 계산
 *
 * Drawdown 차트에 표시할 통계 정보
 *
 * @param drawdownData - Drawdown 차트 데이터
 * @returns { maxDrawdown, currentDrawdown }
 */
export const getDrawdownStats = (
  drawdownData: Array<{ drawdown: number }>
): { maxDrawdown: number; currentDrawdown: number } => {
  if (!drawdownData || drawdownData.length === 0) {
    return { maxDrawdown: 0, currentDrawdown: 0 };
  }

  const maxDrawdown = Math.min(...drawdownData.map((d) => d.drawdown));
  const currentDrawdown = drawdownData[drawdownData.length - 1]?.drawdown || 0;

  return {
    maxDrawdown: parseFloat(maxDrawdown.toFixed(2)),
    currentDrawdown: parseFloat(currentDrawdown.toFixed(2)),
  };
};

/**
 * 거래 통계 계산
 *
 * Returns Distribution 차트에 표시할 통계 정보
 *
 * @param signals - 거래 신호 배열
 * @returns { totalTrades, avgReturn, winRate }
 */
export const getTradeStats = (signals: APISignal[]) => {
  if (!signals || signals.length === 0) {
    return { totalTrades: 0, avgReturn: 0, winRate: 0 };
  }

  const totalTrades = signals.length;
  const avgReturn =
    signals.reduce((sum, s) => sum + s.return_pct * 100, 0) / totalTrades;
  const winningTrades = signals.filter((s) => s.return_pct > 0).length;
  const winRate = (winningTrades / totalTrades) * 100;

  return {
    totalTrades,
    avgReturn: parseFloat(avgReturn.toFixed(2)),
    winRate: parseFloat(winRate.toFixed(1)),
  };
};
