import { describe, it, expect } from 'vitest'
import {
  validateSymbols,
  validateDateRange,
  validateParams,
  validateBacktestRequest,
  percentToDecimal,
  decimalToPercent
} from './validation'

describe('Validation Functions', () => {
  // ========== validateSymbols Tests ==========
  describe('validateSymbols', () => {
    it('should accept valid symbols', () => {
      const result = validateSymbols('BTC_KRW, ETH_KRW')
      expect(result.isValid).toBe(true)
      expect(result.symbols).toEqual(['BTC_KRW', 'ETH_KRW'])
      expect(result.error).toBeNull()
    })

    it('should accept single symbol', () => {
      const result = validateSymbols('BTC_KRW')
      expect(result.isValid).toBe(true)
      expect(result.symbols).toEqual(['BTC_KRW'])
    })

    it('should trim whitespace around symbols', () => {
      const result = validateSymbols('  BTC_KRW  ,  ETH_KRW  ')
      expect(result.isValid).toBe(true)
      expect(result.symbols).toEqual(['BTC_KRW', 'ETH_KRW'])
    })

    it('should reject empty string', () => {
      const result = validateSymbols('')
      expect(result.isValid).toBe(false)
      expect(result.error).toBe('심볼을 최소 1개 이상 입력하세요')
    })

    it('should reject null or undefined', () => {
      expect(validateSymbols(null).isValid).toBe(false)
      expect(validateSymbols(undefined).isValid).toBe(false)
    })

    it('should reject symbols with whitespace inside', () => {
      const result = validateSymbols('BTC KRW, ETH_KRW')
      expect(result.isValid).toBe(false)
      expect(result.error).toBe('심볼 내에 공백이 포함될 수 없습니다')
    })

    it('should handle multiple commas', () => {
      const result = validateSymbols('BTC_KRW,ETH_KRW,SOL_KRW')
      expect(result.isValid).toBe(true)
      expect(result.symbols).toEqual(['BTC_KRW', 'ETH_KRW', 'SOL_KRW'])
    })
  })

  // ========== validateDateRange Tests ==========
  describe('validateDateRange', () => {
    it('should accept valid date range', () => {
      const result = validateDateRange('2025-01-01', '2025-10-31')
      expect(result.isValid).toBe(true)
      expect(result.error).toBeNull()
    })

    it('should accept same start and end date', () => {
      const result = validateDateRange('2025-10-01', '2025-10-01')
      expect(result.isValid).toBe(true)
    })

    it('should reject empty dates', () => {
      const result = validateDateRange('', '')
      expect(result.isValid).toBe(false)
      expect(result.error).toBe('시작일과 종료일을 모두 입력하세요')
    })

    it('should reject invalid date format', () => {
      let result = validateDateRange('01-01-2025', '2025-10-31')
      expect(result.isValid).toBe(false)
      expect(result.error).toContain('시작일 형식')

      result = validateDateRange('2025-01-01', '31/10/2025')
      expect(result.isValid).toBe(false)
      expect(result.error).toContain('종료일 형식')
    })

    it('should reject when start_date > end_date', () => {
      const result = validateDateRange('2025-10-31', '2025-01-01')
      expect(result.isValid).toBe(false)
      expect(result.error).toBe('시작일은 종료일보다 이전이어야 합니다')
    })

    it('should reject future dates', () => {
      const tomorrow = new Date()
      tomorrow.setDate(tomorrow.getDate() + 1)
      const futureDate = tomorrow.toISOString().split('T')[0]

      const result = validateDateRange('2025-01-01', futureDate)
      expect(result.isValid).toBe(false)
      expect(result.error).toBe('종료일은 오늘 이전이어야 합니다')
    })

    it('should accept today as end date', () => {
      const today = new Date().toISOString().split('T')[0]
      const result = validateDateRange('2024-01-01', today)
      expect(result.isValid).toBe(true)
    })
  })

  // ========== validateParams Tests ==========
  describe('validateParams', () => {
    describe('volume_long_candle strategy', () => {
      it('should accept valid parameters', () => {
        const params = {
          vol_ma_window: 20,
          vol_multiplier: 1.5,
          body_pct: 0.02
        }
        const result = validateParams('volume_long_candle', params)
        expect(result.isValid).toBe(true)
        expect(Object.keys(result.errors)).toHaveLength(0)
      })

      it('should reject vol_ma_window < 1', () => {
        const params = {
          vol_ma_window: 0,
          vol_multiplier: 1.5,
          body_pct: 0.02
        }
        const result = validateParams('volume_long_candle', params)
        expect(result.isValid).toBe(false)
        expect(result.errors.vol_ma_window).toContain('1 이상')
      })

      it('should reject vol_ma_window > 200', () => {
        const params = {
          vol_ma_window: 201,
          vol_multiplier: 1.5,
          body_pct: 0.02
        }
        const result = validateParams('volume_long_candle', params)
        expect(result.isValid).toBe(false)
        expect(result.errors.vol_ma_window).toContain('200 이하')
      })

      it('should reject vol_multiplier < 1.0', () => {
        const params = {
          vol_ma_window: 20,
          vol_multiplier: 0.5,
          body_pct: 0.02
        }
        const result = validateParams('volume_long_candle', params)
        expect(result.isValid).toBe(false)
        expect(result.errors.vol_multiplier).toContain('1 이상')
      })

      it('should reject body_pct > 1.0', () => {
        const params = {
          vol_ma_window: 20,
          vol_multiplier: 1.5,
          body_pct: 1.5
        }
        const result = validateParams('volume_long_candle', params)
        expect(result.isValid).toBe(false)
        expect(result.errors.body_pct).toContain('1 이하')
      })

      it('should reject non-numeric values', () => {
        const params = {
          vol_ma_window: 'abc',
          vol_multiplier: 1.5,
          body_pct: 0.02
        }
        const result = validateParams('volume_long_candle', params)
        expect(result.isValid).toBe(false)
        expect(result.errors.vol_ma_window).toContain('숫자')
      })

      it('should reject non-integer vol_ma_window', () => {
        const params = {
          vol_ma_window: 20.5,
          vol_multiplier: 1.5,
          body_pct: 0.02
        }
        const result = validateParams('volume_long_candle', params)
        expect(result.isValid).toBe(false)
        expect(result.errors.vol_ma_window).toContain('정수')
      })

      it('should reject missing parameters', () => {
        const result = validateParams('volume_long_candle', {})
        expect(result.isValid).toBe(false)
        expect(Object.keys(result.errors).length).toBe(3)
      })
    })

    describe('volume_zone_breakout strategy', () => {
      it('should accept valid parameters', () => {
        const params = {
          volume_window: 60,
          top_percentile: 0.2,
          breakout_buffer: 0.01
        }
        const result = validateParams('volume_zone_breakout', params)
        expect(result.isValid).toBe(true)
      })

      it('should reject top_percentile <= 0', () => {
        const params = {
          volume_window: 60,
          top_percentile: 0,
          breakout_buffer: 0.01
        }
        const result = validateParams('volume_zone_breakout', params)
        expect(result.isValid).toBe(false)
        expect(result.errors.top_percentile).toContain('0보다')
      })

      it('should reject top_percentile > 1.0', () => {
        const params = {
          volume_window: 60,
          top_percentile: 1.5,
          breakout_buffer: 0.01
        }
        const result = validateParams('volume_zone_breakout', params)
        expect(result.isValid).toBe(false)
        expect(result.errors.top_percentile).toContain('1 이하')
      })

      it('should accept top_percentile = 1.0', () => {
        const params = {
          volume_window: 60,
          top_percentile: 1.0,
          breakout_buffer: 0.01
        }
        const result = validateParams('volume_zone_breakout', params)
        expect(result.isValid).toBe(true)
      })

      it('should reject invalid strategy', () => {
        const result = validateParams('unknown_strategy', {})
        expect(result.isValid).toBe(false)
        expect(result.errors.strategy).toContain('지원하지 않는 전략')
      })
    })
  })

  // ========== validateBacktestRequest Tests ==========
  describe('validateBacktestRequest', () => {
    it('should accept valid complete request', () => {
      const request = {
        symbols: 'BTC_KRW, ETH_KRW',
        start_date: '2025-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_long_candle',
        params: {
          vol_ma_window: 20,
          vol_multiplier: 1.5,
          body_pct: 0.02
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(true)
    })

    it('should aggregate multiple errors', () => {
      const request = {
        symbols: '',
        start_date: '2025-10-31',
        end_date: '2025-01-01',
        strategy: 'volume_long_candle',
        params: {
          vol_ma_window: 20,
          vol_multiplier: 0.5,
          body_pct: 0.02
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(false)
      expect(result.errors.symbols).toBeDefined()
      expect(result.errors.dates).toBeDefined()
      expect(result.errors.params).toBeDefined()
    })

    it('should validate missing strategy', () => {
      const request = {
        symbols: 'BTC_KRW',
        start_date: '2025-01-01',
        end_date: '2025-10-31'
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(false)
      expect(result.errors.strategy).toBeDefined()
    })
  })

  // ========== Percentage Conversion Tests ==========
  describe('Percentage Conversion', () => {
    it('should convert percentage to decimal correctly', () => {
      expect(percentToDecimal(0)).toBe(0)
      expect(percentToDecimal(50)).toBe(0.5)
      expect(percentToDecimal(100)).toBe(1)
      expect(percentToDecimal(20)).toBe(0.2)
    })

    it('should convert decimal to percentage correctly', () => {
      expect(decimalToPercent(0)).toBe(0)
      expect(decimalToPercent(0.5)).toBe(50)
      expect(decimalToPercent(1.0)).toBe(100)
      expect(decimalToPercent(0.2)).toBe(20)
    })

    it('should handle invalid inputs in percentage conversion', () => {
      expect(percentToDecimal(NaN)).toBe(0)
      expect(percentToDecimal(null)).toBe(0)
      expect(decimalToPercent(NaN)).toBe(0)
      expect(decimalToPercent(undefined)).toBe(0)
    })

    it('should round-trip conversion correctly', () => {
      const percent = 75
      const decimal = percentToDecimal(percent)
      const backToPercent = decimalToPercent(decimal)
      expect(backToPercent).toBe(percent)
    })

    it('should handle edge case percentages (1, 99)', () => {
      expect(percentToDecimal(1)).toBe(0.01)
      expect(percentToDecimal(99)).toBe(0.99)
      expect(decimalToPercent(0.01)).toBe(1)
      expect(decimalToPercent(0.99)).toBe(99)
    })
  })

  // ========== Form Behavior Tests (Real-time Validation) ==========
  describe('Form Behavior', () => {
    it('should accumulate multiple errors in validateBacktestRequest', () => {
      const request = {
        symbols: '', // empty
        start_date: '2025-10-31',
        end_date: '2025-01-01', // invalid range
        strategy: 'volume_long_candle',
        params: {
          vol_ma_window: 0, // out of range
          vol_multiplier: 1.5,
          body_pct: 0.5
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(false)
      expect(result.errors.symbols).toBeDefined()
      expect(result.errors.dates).toBeDefined()
      expect(result.errors.params.vol_ma_window).toBeDefined()
    })

    it('should clear errors when all fields become valid', () => {
      let request = {
        symbols: '',
        start_date: '2025-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_long_candle',
        params: { vol_ma_window: 20, vol_multiplier: 1.5, body_pct: 0.5 }
      }
      let result = validateBacktestRequest(request)
      expect(result.isValid).toBe(false)

      // Fix the symbols field
      request.symbols = 'BTC_KRW'
      result = validateBacktestRequest(request)
      expect(result.isValid).toBe(true)
      expect(Object.keys(result.errors).length).toBe(0)
    })

    it('should validate when changing strategy from volume_long_candle to volume_zone_breakout', () => {
      const request = {
        symbols: 'BTC_KRW',
        start_date: '2025-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_zone_breakout',
        params: {
          volume_window: 60,
          top_percentile: 0.5, // decimal form
          breakout_buffer: 0.01
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(true)
    })

    it('should detect when top_percentile is out of range for volume_zone_breakout', () => {
      const request = {
        symbols: 'BTC_KRW',
        start_date: '2025-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_zone_breakout',
        params: {
          volume_window: 60,
          top_percentile: 1.5, // exceeds max of 1.0
          breakout_buffer: 0.01
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(false)
      expect(result.errors.params.top_percentile).toContain('1 이하')
    })

    it('should handle parameter conversion during validation (percentage to decimal)', () => {
      // Simulate user input: 75% → 0.75 decimal
      const userInputPercent = 75
      const decimalValue = percentToDecimal(userInputPercent)

      const request = {
        symbols: 'BTC_KRW',
        start_date: '2025-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_zone_breakout',
        params: {
          volume_window: 60,
          top_percentile: decimalValue, // 0.75
          breakout_buffer: 0.01
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(true)
    })

    it('should validate complex multi-field scenario with multiple errors', () => {
      const request = {
        symbols: 'BTC KRW, ETH_KRW', // space in symbol
        start_date: '2025-12-31',
        end_date: '2025-01-01', // invalid range
        strategy: 'volume_long_candle',
        params: {
          vol_ma_window: 'not_a_number', // type error
          vol_multiplier: 0.5, // below min
          body_pct: 1.5 // above max
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(false)
      expect(Object.keys(result.errors).length).toBeGreaterThan(0)
      expect(result.errors.symbols).toBeDefined()
      expect(result.errors.dates).toBeDefined()
    })

    it('should validate date exactly on today (boundary condition)', () => {
      const today = new Date().toISOString().split('T')[0]
      const result = validateDateRange('2025-01-01', today)
      expect(result.isValid).toBe(true)
    })

    it('should handle min and max boundary values for integers', () => {
      const minRequest = {
        symbols: 'BTC_KRW',
        start_date: '2025-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_long_candle',
        params: {
          vol_ma_window: 1, // minimum
          vol_multiplier: 1.0, // minimum
          body_pct: 0.0 // minimum
        }
      }
      const minResult = validateBacktestRequest(minRequest)
      expect(minResult.isValid).toBe(true)

      const maxRequest = {
        ...minRequest,
        params: {
          vol_ma_window: 200, // maximum
          vol_multiplier: 10.0, // maximum
          body_pct: 1.0 // maximum
        }
      }
      const maxResult = validateBacktestRequest(maxRequest)
      expect(maxResult.isValid).toBe(true)
    })

    it('should validate symbols list with various separators (commas with spaces)', () => {
      const result = validateSymbols('BTC_KRW  ,  ETH_KRW  ,  SOL_KRW')
      expect(result.isValid).toBe(true)
      expect(result.symbols).toEqual(['BTC_KRW', 'ETH_KRW', 'SOL_KRW'])
    })

    it('should detect error when switching from valid to invalid input', () => {
      let request = {
        symbols: 'BTC_KRW, ETH_KRW',
        start_date: '2025-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_long_candle',
        params: { vol_ma_window: 20, vol_multiplier: 1.5, body_pct: 0.5 }
      }
      let result = validateBacktestRequest(request)
      expect(result.isValid).toBe(true)

      // Switch to invalid
      request.symbols = 'BTC KRW' // space in symbol
      result = validateBacktestRequest(request)
      expect(result.isValid).toBe(false)
      expect(result.errors.symbols).toBeDefined()
    })

    it('should handle fractional values for floating-point parameters', () => {
      const request = {
        symbols: 'BTC_KRW',
        start_date: '2025-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_long_candle',
        params: {
          vol_ma_window: 50,
          vol_multiplier: 1.5678, // fractional
          body_pct: 0.0123 // fractional
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(true)
    })

    it('should reject out-of-range floating-point values', () => {
      const request = {
        symbols: 'BTC_KRW',
        start_date: '2025-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_long_candle',
        params: {
          vol_ma_window: 50,
          vol_multiplier: 10.1, // exceeds max
          body_pct: 0.5
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(false)
      expect(result.errors.params.vol_multiplier).toContain('10 이하')
    })

    it('should validate zero as valid boundary value for body_pct', () => {
      const request = {
        symbols: 'BTC_KRW',
        start_date: '2025-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_long_candle',
        params: {
          vol_ma_window: 50,
          vol_multiplier: 1.5,
          body_pct: 0 // minimum boundary
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(true)
    })

    it('should validate one as valid boundary value for vol_ma_window', () => {
      const request = {
        symbols: 'BTC_KRW',
        start_date: '2025-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_long_candle',
        params: {
          vol_ma_window: 1, // minimum boundary
          vol_multiplier: 1.0,
          body_pct: 0.5
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(true)
    })

    it('should handle very long symbol list', () => {
      const symbols = Array(50)
        .fill(0)
        .map((_, i) => `SYM${i}_KRW`)
        .join(', ')
      const result = validateSymbols(symbols)
      expect(result.isValid).toBe(true)
      expect(result.symbols.length).toBe(50)
    })

    it('should validate consecutive commas as separate symbols', () => {
      const result = validateSymbols('BTC_KRW,,,ETH_KRW')
      expect(result.isValid).toBe(true)
      expect(result.symbols).toEqual(['BTC_KRW', 'ETH_KRW'])
    })

    it('should handle date range with single-day difference', () => {
      const result = validateDateRange('2025-10-30', '2025-10-31')
      expect(result.isValid).toBe(true)
    })

    it('should reject dates with one day in future', () => {
      const tomorrow = new Date()
      tomorrow.setDate(tomorrow.getDate() + 1)
      const tomorrowStr = tomorrow.toISOString().split('T')[0]
      const result = validateDateRange('2025-01-01', tomorrowStr)
      expect(result.isValid).toBe(false)
    })

    it('should validate parameter conversion for top_percentile edge cases', () => {
      // 1% → 0.01
      expect(percentToDecimal(1)).toBe(0.01)
      // 99% → 0.99
      expect(percentToDecimal(99)).toBe(0.99)
      // 0% → 0
      expect(percentToDecimal(0)).toBe(0)
      // 100% → 1.0
      expect(percentToDecimal(100)).toBe(1)
    })

    it('should validate all parameters together for volume_zone_breakout', () => {
      const request = {
        symbols: 'BTC_KRW, ETH_KRW, SOL_KRW',
        start_date: '2024-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_zone_breakout',
        params: {
          volume_window: 100,
          top_percentile: 0.25,
          breakout_buffer: 0.005
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(true)
    })

    it('should detect invalid parameter when one field is wrong in multi-param validation', () => {
      const request = {
        symbols: 'BTC_KRW',
        start_date: '2025-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_long_candle',
        params: {
          vol_ma_window: 50,
          vol_multiplier: 1.5,
          body_pct: 1.5 // exceeds max of 1.0
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(false)
      expect(result.errors.params.body_pct).toContain('1 이하')
      expect(result.errors.params.vol_ma_window).toBeUndefined() // other params ok
    })

    it('should validate symbol names with underscores and numbers', () => {
      const result = validateSymbols('BTC_KRW_1, ETH_KRW_2, USDT_KRW_3')
      expect(result.isValid).toBe(true)
      expect(result.symbols).toEqual(['BTC_KRW_1', 'ETH_KRW_2', 'USDT_KRW_3'])
    })

    it('should reject symbol with tab character', () => {
      const result = validateSymbols('BTC\tKRW')
      expect(result.isValid).toBe(false)
    })

    it('should handle empty param object gracefully', () => {
      const request = {
        symbols: 'BTC_KRW',
        start_date: '2025-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_long_candle',
        params: {}
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(false)
      expect(result.errors.params).toBeDefined()
    })

    it('should validate request with minimal valid data', () => {
      const request = {
        symbols: 'BTC_KRW',
        start_date: '2025-10-01',
        end_date: '2025-10-31',
        strategy: 'volume_long_candle',
        params: {
          vol_ma_window: 1,
          vol_multiplier: 1.0,
          body_pct: 0.0
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(true)
    })

    it('should validate request with maximal valid data', () => {
      const request = {
        symbols: 'BTC_KRW, ETH_KRW, SOL_KRW, DOGE_KRW, ADA_KRW',
        start_date: '2024-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_long_candle',
        params: {
          vol_ma_window: 200,
          vol_multiplier: 10.0,
          body_pct: 1.0
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(true)
    })

    it('should identify which parameter fails in complex validation', () => {
      const request = {
        symbols: 'BTC_KRW',
        start_date: '2025-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_zone_breakout',
        params: {
          volume_window: 0, // invalid
          top_percentile: 0.5,
          breakout_buffer: 0.01
        }
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(false)
      expect(result.errors.params.volume_window).toBeDefined()
      expect(result.errors.params.top_percentile).toBeUndefined()
    })

    it('should preserve parameter order in request', () => {
      const params = {
        vol_ma_window: 20,
        vol_multiplier: 1.5,
        body_pct: 0.5
      }
      const request = {
        symbols: 'BTC_KRW',
        start_date: '2025-01-01',
        end_date: '2025-10-31',
        strategy: 'volume_long_candle',
        params
      }
      const result = validateBacktestRequest(request)
      expect(result.isValid).toBe(true)
      // Verify params are unchanged
      expect(request.params.vol_ma_window).toBe(20)
    })

    it('should validate exclusive_min for top_percentile (not equal to 0)', () => {
      const params = {
        volume_window: 60,
        top_percentile: 0, // exactly 0, should fail
        breakout_buffer: 0.01
      }
      const result = validateParams('volume_zone_breakout', params)
      expect(result.isValid).toBe(false)
      expect(result.errors.top_percentile).toContain('0보다')
    })
  })
})
