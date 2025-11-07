# Chart Implementation - Quick Reference Guide

## Current Implementation Overview

### Charts Currently Implemented
1. **Equity Curve Chart** (BacktestResults.jsx)
   - Recharts LineChart
   - Shows cumulative equity/returns over time
   - Signal markers (buy/sell dots)
   - Height: 400px, Responsive

2. **Comparison Chart** (CompareResultsModal.jsx)
   - Recharts LineChart
   - Compares multiple backtest runs
   - Average return visualization
   - Height: 300px

3. **Profit Metrics** (ProfitChart.jsx)
   - CSS-based metric cards
   - 4 key metrics displayed
   - Simple bar visualization

---

## File Directory Structure

### Frontend Components
```
frontend/src/
├── components/
│   ├── BacktestResults.jsx (Equity Curve + Metrics)
│   ├── CompareResultsModal.jsx (Comparison Chart)
│   ├── ProfitChart.jsx (Metrics Display)
│   ├── AdvancedFilterPanel.jsx (Filter UI)
│   └── ...
├── pages/
│   ├── BacktestPage.jsx (Execution + Results)
│   ├── SignalViewerPage.jsx (History + Comparison)
│   └── ...
├── services/
│   └── backtestApi.js (API calls)
├── styles/
│   ├── App.css (Global)
│   ├── CompareResultsModal.css
│   ├── ProfitChart.css
│   ├── AdvancedFilterPanel.css
│   └── ...
└── utils/
    └── formatters.js (Data formatting)
```

### Backend Endpoints
```
POST /api/backtests/run
GET /api/backtests/latest
GET /api/backtests/history?[params]
GET /api/backtests/{run_id}/download
```

---

## Key Data Structures

### Backtest Result
```javascript
{
  run_id, strategy, symbols: [{
    symbol, signals: [{timestamp, type, entry_price}],
    performance_curve: [{timestamp, equity}],
    win_rate, avg_return, max_drawdown
  }],
  total_signals, start_date, end_date, timeframe, execution_time
}
```

### Chart Data Format
```javascript
// Equity Curve Data
[{timestamp, equity, equityValue, signal?, price?}]

// Comparison Data
[{name, runId, avgReturn}]
```

---

## Adding a New Chart

### Step 1: Create Component
```jsx
// File: src/components/DrawdownChart.jsx
import { LineChart, Line, ... } from 'recharts'

export const DrawdownChart = ({ symbolWithCurve }) => {
  const drawdownData = calculateDrawdown(symbolWithCurve.performance_curve)
  
  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={drawdownData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="timestamp" />
        <YAxis label={{ value: 'Drawdown (%)', angle: -90 }} />
        <Tooltip />
        <Line dataKey="drawdown" stroke="#dc3545" strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  )
}
```

### Step 2: Create CSS (if needed)
```css
/* src/styles/DrawdownChart.css */
.chart-section {
  margin-bottom: 40px;
}

.chart-section h3 {
  color: #2c3e50;
  font-size: 18px;
  border-bottom: 2px solid #667eea;
}
```

### Step 3: Integrate into BacktestResults
```jsx
// In BacktestResults.jsx
import { DrawdownChart } from './DrawdownChart'

const renderDrawdownChart = () => {
  if (!symbolWithCurve) return null
  return (
    <div className="chart-section">
      <h3>Maximum Drawdown</h3>
      <DrawdownChart symbolWithCurve={symbolWithCurve} />
    </div>
  )
}

// In return statement
<div className="backtest-results">
  {renderEquityCurveChart()}
  {renderDrawdownChart()}
  ...
</div>
```

---

## Styling Conventions

### Colors
- Green (Positive): `#28a745`
- Red (Negative): `#dc3545`
- Neutral: `#2c3e50`
- Accent: `#667eea`
- Border: `#e0e0e0`

### Spacing
- Section margin-bottom: `40px`
- Internal padding: `20px`
- Gap between items: `20px`

### Chart Heights
- Main charts: `400px`
- Comparison: `300px`
- Small/secondary: `250px`

### Responsive
- Breakpoint: `768px`
- Mobile adjustments reduce heights by 25%
- Use ResponsiveContainer for width

---

## API Integration

### Fetch Latest
```javascript
const { data, error, isLoading } = useSWR(
  '/api/backtests/latest',
  fetchLatestBacktest
)
```

### Fetch History with Filters
```javascript
const { data, error } = useSWR(
  ['/api/backtests/history', filters],
  ([_, f]) => fetchBacktestHistory(f)
)
```

### Parameters
```javascript
{
  limit: 10,
  offset: 0,
  strategy: 'volume_long_candle',
  min_return: -0.05,  // -5%
  max_return: 0.20,   // +20%
  min_signals: 10,
  max_signals: 100,
  date_from: '2024-01-01',
  date_to: '2024-12-31'
}
```

---

## Performance Tips

1. **Data Decimation** for large datasets (>1000 points)
   ```javascript
   const decimateData = (data, target = 500) => {
     const step = Math.ceil(data.length / target)
     return data.filter((_, i) => i % step === 0)
   }
   ```

2. **Pagination** - Keep history queries limited
3. **Lazy Loading** - Load chart details on demand
4. **Memoization** - Use useMemo for data transformation

---

## Testing Examples

### Unit Test - Data Transformation
```javascript
describe('DrawdownCalculation', () => {
  test('should calculate drawdown correctly', () => {
    const data = [{equity: 1.0}, {equity: 0.8}, {equity: 0.9}]
    const result = calculateDrawdown(data)
    expect(result[1].drawdown).toBe(0.2)
  })
})
```

### Integration Test - Chart Rendering
```javascript
describe('DrawdownChart', () => {
  test('should render with data', () => {
    const { getByText } = render(
      <DrawdownChart symbolWithCurve={mockData} />
    )
    expect(getByText('Maximum Drawdown')).toBeInTheDocument()
  })
})
```

---

## Common Issues & Solutions

### Issue: Chart not responsive
**Solution:** Wrap in ResponsiveContainer
```jsx
<ResponsiveContainer width="100%" height={400}>
  <LineChart data={data}>...</LineChart>
</ResponsiveContainer>
```

### Issue: X-axis labels overlapping
**Solution:** Adjust interval and angle
```jsx
<XAxis 
  dataKey="timestamp" 
  interval={Math.floor(data.length / 8)}
  angle={-45}
  height={80}
/>
```

### Issue: Missing data points on chart
**Solution:** Check data structure and dataKey
```javascript
// Verify data format
console.log(chartData[0]) // Should have 'timestamp' and 'equity' keys
```

### Issue: Tooltip not showing
**Solution:** Verify Tooltip placement and content
```jsx
<Tooltip 
  contentStyle={{ background: '#fff', border: '1px solid #ccc' }}
  formatter={(value, name) => [value.toFixed(2), name]}
/>
```

---

## Next Steps (High Priority)

1. **Drawdown Chart** - Show risk profile
2. **Returns Distribution** - Show trade outcomes spread
3. **Multi-Symbol Charts** - Compare symbols in single backtest
4. **Export Function** - Save charts as PNG/SVG

---

## References

- **Recharts Docs:** https://recharts.org/
- **Backtest Result Format:** Backend schema in result_manager.py
- **API Endpoints:** main.py lines 775-880
- **Component Examples:** BacktestResults.jsx lines 161-294

---

## Quick Commands

### Build
```bash
cd frontend && npm run build
```

### Test
```bash
cd frontend && npm run test
```

### Dev Server
```bash
cd frontend && npm run dev
```

### Check Components
```bash
grep -r "recharts" frontend/src/components/
```

