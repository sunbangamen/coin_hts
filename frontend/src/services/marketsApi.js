/**
 * Markets API 서비스 (Feature Breakdown #23, Task 3)
 *
 * 업비트 KRW 마켓 정보 및 실시간 시세를 조회하는 API
 */

import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/markets`,
  timeout: 30000,
})

/**
 * KRW 마켓 목록 조회
 * GET /api/markets/krw
 */
export const fetchKRWMarkets = async () => {
  try {
    const response = await api.get('/krw')
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || 'Failed to fetch KRW markets')
  }
}

/**
 * KRW 마켓 실시간 시세 조회
 * GET /api/markets/krw/tickers
 */
export const fetchKRWTickers = async () => {
  try {
    const response = await api.get('/krw/tickers')
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || 'Failed to fetch KRW tickers')
  }
}

/**
 * 시세 정보를 마켓 정보와 병합
 * 마켓 정보 + 시세 정보 = 완전한 종목 정보
 */
export const mergeMarketsAndTickers = (markets, tickers) => {
  const tickerMap = new Map(
    tickers.map(ticker => [ticker.market, ticker])
  )

  return markets.map(market => ({
    ...market,
    trade_price: tickerMap.get(market.market)?.trade_price || 0,
    change_rate: tickerMap.get(market.market)?.change_rate || 0,
    acc_trade_volume_24h: tickerMap.get(market.market)?.acc_trade_volume_24h || 0,
    acc_trade_price_24h: tickerMap.get(market.market)?.acc_trade_price_24h || 0
  }))
}
