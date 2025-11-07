# Cryptocurrency Backtesting Platform - Chart Implementation Analysis

## Executive Summary

The platform currently uses **Recharts** as its primary charting library and has implemented basic equity curve visualization with signal markers. This document provides a comprehensive analysis of the existing chart implementations, architecture, and recommendations for extending the charting capabilities.

---

## 1. Current Chart Implementations

### 1.1 Recharts Integration

**Package:** recharts v2.10.0 (from frontend/package.json)
**Location:** `/home/limeking/projects/worktree/coin-23/frontend/src`

#### Components Using Recharts:

1. **BacktestResults.jsx** - Equity Curve Chart
   - File: `/home/limeking/projects/worktree/coin-23/frontend/src/components/BacktestResults.jsx`
   - Charts Used:
     - LineChart with equity performance curve
     - ReferenceDot for buy/sell signal markers
   - Features:
     - Time-series equity curve visualization
     - Signal overlay (buy/sell points marked as dots)
     - Customizable domain and tooltip formatting
     - Legend with signal explanation

2. **CompareResultsModal.jsx** - Comparison Chart
   - File: `/home/limeking/projects/worktree/coin-23/frontend/src/components/CompareResultsModal.jsx`
   - Charts Used:
     - LineChart for average return comparison
   - Features:
     - Multi-run comparison visualization
     - Average return metrics plotting
     - Tooltip with percentage formatting

3. **ProfitChart.jsx** - Metrics Display (Non-Recharts)
   - File: `/home/limeking/projects/worktree/coin-23/frontend/src/components/ProfitChart.jsx`
   - Implementation: CSS-based mini bar chart
   - Features:
     - Simple metric cards (Total P&L, Open Positions, Win Rate, Unrealized P&L)
     - CSS-based vertical bar visualization
     - Color-coded profit/loss indicators

### 1.2 Chart Components Detailed Analysis

#### BacktestResults Equity Curve Chart
```jsx
// Key Components:
- LineChart: Main container
- CartesianGrid: Grid background
- XAxis/YAxis: Axes with custom labels
- Tooltip: Formatted tooltips showing equity percentage
- Legend: Symbol explanation
- Line: Equity curve line
- ReferenceDot: Signal markers (buy=green, sell=red)

// Data Structure:
const chartData = {
  timestamp: string,
  equity: number (as percentage),
  equityValue: number,
  signal?: string (BUY/SELL),
  price?: number
}

// Styling:
- Line color: #2c3e50 (dark blue-gray)
- Buy signal: #28a745 (green)
- Sell signal: #dc3545 (red)
- Height: 400px
```

#### CompareResultsModal Chart
```jsx
// Key Components:
- LineChart: Comparison visualization
- Line: Average return per run
- Single metric visualization

// Data Structure:
const chartData = {
  name: string (Run 1, Run 2, etc.),
  runId: string,
  avgReturn: number (percentage)
}

// Styling:
- Primary color: #667eea
- Height: 300px
- Responsive container
```

#### ProfitChart Metrics
```jsx
// CSS-based implementation
// Metric Cards: 4 cards in grid layout
// Mini Chart: Simple bar chart

// Metrics Displayed:
- 총 실현손익 (Total Realized P&L)
- 오픈 포지션 (Open Positions)
- 승률 (Win Rate)
- 총 미실현손익 (Total Unrealized P&L)
```

---

## 2. Backtest History Feature Structure

### 2.1 Backend API Architecture

**File:** `/home/limeking/projects/worktree/coin-23/backend/app/main.py`

#### Key Endpoints:
1. `GET /api/backtests/latest` - Latest backtest result
2. `GET /api/backtests/history` - Backtest history with advanced filtering
3. `GET /api/backtests/{run_id}/download` - Backtest result details
4. `POST /api/backtests/run` - Execute backtest

#### Advanced Filtering Capabilities (Task 3.3-3)
```python
# Query Parameters:
- limit: int (1-100, default: 10)
- offset: int (default: 0) - Pagination
- strategy: str (optional) - Filter by strategy name
- min_return: float (optional) - Minimum average return %
- max_return: float (optional) - Maximum average return %
- min_signals: int (optional) - Minimum signal count
- max_signals: int (optional) - Maximum signal count
- date_from: str (YYYY-MM-DD, optional) - Start date filter
- date_to: str (YYYY-MM-DD, optional) - End date filter
```

#### Backend Result Management
**File:** `/home/limeking/projects/worktree/coin-23/backend/app/result_manager.py`
- Saves backtest results as JSON files
- Manages task directories and file organization
- Supports result history retrieval with filtering
- Implements checksum calculation and file integrity

### 2.2 Frontend API Service

**File:** `/home/limeking/projects/worktree/coin-23/frontend/src/services/backtestApi.js`

```javascript
// Key Functions:
- fetchLatestBacktest()
- fetchBacktestHistory(params)
- fetchBacktestDetail(runId)
- downloadBacktestResult(runId)
- downloadBacktestAsCSV(runId)
```

### 2.3 Frontend Pages & Components

**Main Page:** `SignalViewerPage.jsx`
- File: `/home/limeking/projects/worktree/coin-23/frontend/src/pages/SignalViewerPage.jsx`
- Uses SWR for data fetching and caching
- Features:
  - Latest result card
  - Backtest history table with pagination
  - Advanced filtering panel
  - Results comparison modal
  - CSV/JSON download capabilities

**Advanced Filter Panel:** `AdvancedFilterPanel.jsx`
- File: `/home/limeking/projects/worktree/coin-23/frontend/src/components/AdvancedFilterPanel.jsx`
- Features:
  - Return range filtering (min/max)
  - Signal count range filtering
  - Date range filtering
  - Form validation
  - Real-time filter application via SWR key updates

**Comparison Modal:** `CompareResultsModal.jsx`
- File: `/home/limeking/projects/worktree/coin-23/frontend/src/components/CompareResultsModal.jsx`
- Features:
  - Multi-run result loading
  - Metrics comparison table
  - Symbol-by-symbol performance breakdown
  - Visualization of average returns

---

## 3. Data Flow Architecture

### 3.1 Backtest Execution Flow
```
User Input (BacktestPage) 
  ↓
Validation (validation.js)
  ↓
API POST /api/backtests/run
  ↓
Backend Processing (run_backtest_job)
  ↓
Result Manager (save_result_file)
  ↓
Frontend Retrieval (fetchLatestBacktest)
  ↓
Display in BacktestResults Component
```

### 3.2 Results Display Flow
```
SignalViewerPage
  ├─ LatestResultCard (fetchLatestBacktest)
  ├─ BacktestHistoryTable (fetchBacktestHistory)
  ├─ AdvancedFilterPanel (SWR key manager)
  ├─ CompareResultsModal (fetchBacktestDetail)
  └─ BacktestResults (renderEquityCurveChart)
```

---

## 4. Current Styling Architecture

### 4.1 CSS Files & Styling Approach

**Main Application Styles:** `/home/limeking/projects/worktree/coin-23/frontend/src/App.css` (1230 lines)
- Global layout and form styles
- Responsive grid systems
- Card layouts and spacing

**Component-Specific Styles:**
- BacktestResults: App.css (generic)
- CompareResultsModal.css (370 lines) - Modal and table styles
- ProfitChart.css (129 lines) - Metric cards and mini charts
- AdvancedFilterPanel.css (297 lines) - Filter UI components

### 4.2 Color Scheme
```
Primary Colors:
- Success/Positive: #28a745 (green)
- Error/Negative: #dc3545 (red)
- Neutral: #2c3e50 (dark blue-gray)
- Accent: #667eea (purple-blue)

Background:
- Primary: white
- Secondary: #f8f9fa (light gray)
- Tertiary: #f9f9f9 (very light gray)

Border:
- Primary: #e0e0e0
- Secondary: #dee2e6
```

### 4.3 Responsive Design
- Mobile breakpoint: 768px
- Grid layouts use auto-fit
- Charts use ResponsiveContainer for fluid sizing

---

## 5. Results Data Structure

### 5.1 Backtest Result Schema
```javascript
{
  run_id: string,
  strategy: string,
  symbols: [{
    symbol: string,
    signals: [{
      timestamp: string (ISO 8601),
      type: string (BUY/SELL),
      entry_price: number,
      exit_price?: number,
      return?: number (%),
      hold_bars: number
    }],
    performance_curve: [{
      timestamp: string,
      equity: number (0-1 as percentage)
    }],
    win_rate: number (0-1),
    avg_return: number (as decimal),
    max_drawdown: number (as decimal),
    avg_hold_bars: number
  }],
  total_signals: number,
  start_date: string (YYYY-MM-DD),
  end_date: string (YYYY-MM-DD),
  timeframe: string (1d, 1h, 5m),
  execution_time: number (seconds),
  metadata: {
    execution_date: string,
    environment: string,
    execution_host: string
  },
  version: string,
  description?: string
}
```

### 5.2 History Response Schema
```javascript
{
  total: number,
  limit: number,
  offset: number,
  items: [{
    run_id: string,
    strategy: string,
    total_signals: number,
    execution_time: number,
    start_date: string,
    end_date: string,
    timeframe: string,
    symbols: string[],
    avg_return: number,
    win_rate: number,
    max_drawdown: number
  }]
}
```

---

## 6. Charting Libraries & Dependencies

### 6.1 Current Dependencies
```json
{
  "recharts": "^2.10.0",
  "react": "^18.2.0",
  "react-dom": "^18.2.0",
  "react-router-dom": "^6.20.0",
  "axios": "^1.6.0",
  "swr": "^2.3.6"
}
```

### 6.2 Recharts Features Used
- **Responsive Containers:** Fluid chart sizing
- **Line Charts:** Equity curve visualization
- **Reference Dots:** Signal markers
- **Custom Tooltips:** Formatted data display
- **Legend:** Chart annotation
- **Cartesian Grid:** Background grid
- **Axes:** X/Y axis configuration

### 6.3 Why Recharts?
- Lightweight (composable components)
- React-native components
- Responsive out-of-the-box
- Good documentation
- Composable architecture allows custom implementations

---

## 7. Chart Implementation Details

### 7.1 Equity Curve Chart Implementation

**File:** BacktestResults.jsx (lines 161-294)

```jsx
// Data Preparation
const performanceData = symbolWithCurve.performance_curve.map(point => ({
  timestamp: point.timestamp,
  equity: parseFloat((point.equity * 100).toFixed(2)),
  equityValue: point.equity,
}));

// Signal Marker Creation
const signalMarkers = symbolWithCurve.signals.map(signal => {
  const matchingPoint = performanceData.find(
    p => normalizeTimestamp(p.timestamp) === normalizeTimestamp(signal.timestamp)
  );
  return matchingPoint ? {
    timestamp: matchingPoint.timestamp,
    equity: matchingPoint.equity,
    signal: signal.type.toUpperCase(),
    price: signal.entry_price,
  } : null;
}).filter(Boolean);

// Chart Rendering
<ResponsiveContainer width="100%" height={400}>
  <LineChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
    <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
    <XAxis dataKey="timestamp" tick={{ fontSize: 12 }} />
    <YAxis domain={[minEquity, maxEquity]} label={{ value: '수익률 (%)', angle: -90 }} />
    <Tooltip />
    <Legend />
    <Line type="monotone" dataKey="equity" stroke="#2c3e50" strokeWidth={2} />
    {signalMarkers.map(marker => (
      <ReferenceDot x={marker.timestamp} y={marker.equity} r={5} />
    ))}
  </LineChart>
</ResponsiveContainer>
```

### 7.2 Comparison Chart Implementation

**File:** CompareResultsModal.jsx (lines 57-82, 215-246)

```jsx
// Multi-run data aggregation
const data = results.map((result, index) => {
  const avgReturn = result.detail?.symbols?.reduce(
    (sum, sym) => sum + (sym.avg_return || 0), 0
  ) / result.detail.symbols.length;
  return {
    name: `Run ${index + 1}`,
    runId: result.run_id.substring(0, 8),
    avgReturn: Math.round(avgReturn * 10000) / 10000
  }
});

// Chart rendering with single line per run
<LineChart data={chartData}>
  <Line
    type="monotone"
    dataKey="avgReturn"
    stroke={colors[0]}
    strokeWidth={2}
    dot={{ r: 6 }}
    activeDot={{ r: 8 }}
  />
</LineChart>
```

---

## 8. Recommendations for Chart Extension

### 8.1 High-Priority Enhancements

#### 1. Additional Chart Types
```
Priority: HIGH
Effort: MEDIUM

Recommended Charts:
1. Drawdown Curve (Line Chart)
   - Shows cumulative maximum drawdown over time
   - Critical for risk analysis
   - Similar structure to equity curve

2. Returns Distribution (Histogram/Bar Chart)
   - Distribution of returns across trades
   - Performance gap visibility
   - Bar chart with 10-20 bins

3. Win/Loss Timeline (Stacked Area Chart)
   - Cumulative win/loss ratio visualization
   - Shows strategy consistency
   - ComposedChart with Area components

4. Monthly Returns Heatmap
   - Performance by month/year
   - RecurssiveHeatmap (table with color coding)
   - Fast visual pattern recognition
```

#### 2. Multi-Symbol Visualization
```
Priority: HIGH
Effort: MEDIUM

Recommended Approach:
1. Symbol Selector UI (dropdown/multi-select)
2. Overlaid Line Charts (multiple colors per symbol)
3. Faceted Charts (separate chart per symbol)
4. Symbol Performance Radar Chart

Implementation:
- Extend BacktestResults to iterate symbols
- Use separate ResponsiveContainers for each symbol
- Implement legend toggle for symbol visibility
```

#### 3. Advanced Interactive Features
```
Priority: MEDIUM
Effort: MEDIUM-HIGH

Features:
1. Zooming & Panning
   - Recharts supports custom event handlers
   - Implement state-based domain updates

2. Time Period Selection
   - Slider to select date range
   - Real-time chart updates

3. Trade Annotation
   - Hover effects showing trade details
   - Custom tooltip with entry/exit prices

4. Export to CSV/Image
   - svg-export for chart images
   - Enhanced CSV with detailed metrics
```

### 8.2 Medium-Priority Enhancements

#### 1. Metrics Dashboard
```
Priority: MEDIUM
Effort: LOW-MEDIUM

Metrics to Add:
- Sharpe Ratio (line chart)
- Profit Factor (gauge chart)
- Recovery Factor (line chart)
- Win Rate Trend (area chart)
```

#### 2. Performance Benchmarking
```
Priority: MEDIUM
Effort: MEDIUM

Features:
- Overlay benchmark indices (e.g., buy-and-hold)
- Comparative performance metrics
- Outperformance visualization
```

#### 3. Risk Analytics Charts
```
Priority: MEDIUM
Effort: MEDIUM

Charts:
- Value at Risk (VaR) bands
- Confidence intervals
- Volatility trend chart
```

### 8.3 Low-Priority Enhancements

#### 1. Chart Customization
```
Priority: LOW
Effort: MEDIUM

Options:
- Color scheme selection
- Chart style themes
- Legend positioning
- Grid customization
```

#### 2. Advanced Filtering for Charts
```
Priority: LOW
Effort: LOW

Features:
- Filter by date range in chart
- Signal type filtering in chart
- Equity curve normalization
```

---

## 9. Technical Implementation Guide

### 9.1 Adding New Chart Components

**Template Structure:**
```jsx
import {
  BarChart, Bar,
  LineChart, Line,
  ComposedChart, Composed,
  XAxis, YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area, AreaChart
} from 'recharts'

export const DrawdownChart = ({ symbolWithCurve }) => {
  // Data transformation
  const drawdownData = calculateDrawdownCurve(symbolWithCurve.performance_curve)
  
  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={drawdownData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="timestamp" />
        <YAxis label={{ value: 'Drawdown (%)', angle: -90 }} />
        <Tooltip formatter={(value) => `${(value * 100).toFixed(2)}%`} />
        <Legend />
        <Line
          type="monotone"
          dataKey="drawdown"
          stroke="#dc3545"
          strokeWidth={2}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
```

### 9.2 Integration Pattern

```jsx
// In BacktestResults.jsx
const renderDrawdownChart = () => {
  // Similar to renderEquityCurveChart
  // Check for data availability
  // Return component or null
}

// In render
return (
  <div className="backtest-results">
    {renderEquityCurveChart()}
    {renderDrawdownChart()}
    {renderReturnsDistributionChart()}
    {/* ... other charts ... */}
  </div>
)
```

### 9.3 CSS Patterns for New Charts

```css
/* Chart Section */
.chart-section {
  margin-bottom: 40px;
}

.chart-section h3 {
  margin: 0 0 20px 0;
  color: #2c3e50;
  font-size: 18px;
  font-weight: 600;
  border-bottom: 2px solid #667eea;
  padding-bottom: 10px;
}

.chart-container {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 20px;
}

.chart-info {
  margin-bottom: 15px;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 4px;
  font-size: 14px;
  color: #666;
}

.chart-legend {
  display: flex;
  gap: 20px;
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #e0e0e0;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.legend-marker {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 2px;
  margin-right: 6px;
}
```

---

## 10. Performance Considerations

### 10.1 Data Volume Handling
- **Current Limitation:** Equity curves with 1000+ data points can cause sluggish rendering
- **Recommendation:** Implement data decimation for large datasets
- **Solution:** Sample points at regular intervals or use aggregation

### 10.2 Optimization Strategies
```javascript
// Data decimation function
const decimateData = (data, targetPoints = 500) => {
  if (data.length <= targetPoints) return data;
  const step = Math.ceil(data.length / targetPoints);
  return data.filter((_, index) => index % step === 0);
}

// Apply before rendering
const chartData = decimateData(performanceData, 500);
```

### 10.3 Memory Usage
- Large comparison queries (>10 results) can consume significant memory
- Implement pagination in comparison modal
- Consider lazy loading for detailed symbol data

---

## 11. Future Chart Library Considerations

### 11.1 Alternative Libraries
If Recharts proves limiting:

1. **D3.js**
   - Pros: Maximum flexibility, powerful visualizations
   - Cons: Steep learning curve, verbose code

2. **Chart.js**
   - Pros: Simpler API, good documentation
   - Cons: Less React-friendly, limited composability

3. **Victory**
   - Pros: React-native compatible, similar to Recharts
   - Cons: Smaller community

4. **Apache ECharts**
   - Pros: Rich built-in charts, excellent performance
   - Cons: Large bundle size

### 11.2 Recommendation
**Keep Recharts** for current needs. It's sufficient for the roadmap and has good React integration.

---

## 12. Testing Strategy for Charts

### 12.1 Unit Tests
```javascript
// Test data transformation
describe('ChartDataTransformation', () => {
  test('should calculate drawdown correctly', () => {
    // Test data preparation logic
  });
  
  test('should handle missing signals', () => {
    // Test signal marker creation
  });
});
```

### 12.2 Integration Tests
```javascript
// Test chart rendering
describe('EquityCurveChart', () => {
  test('should render with valid data', () => {
    // Render component and verify DOM
  });
  
  test('should update when props change', () => {
    // Test prop updates trigger re-render
  });
});
```

### 12.3 Visual Tests
- Use snapshot testing for chart output
- Manual visual regression testing
- Cross-browser compatibility testing

---

## 13. Documentation & Examples

### 13.1 Code Examples
Already provided in sections above. Key files for reference:
- BacktestResults.jsx: 161-294 (Equity Curve Chart)
- CompareResultsModal.jsx: 57-82, 215-246 (Comparison Chart)
- ProfitChart.jsx: Complete file (Metrics Display)

### 13.2 API Documentation
All endpoints documented with:
- Query parameters and constraints
- Response schemas
- Error handling
- Example requests/responses

---

## 14. Summary Table

| Feature | Current Status | Priority | Effort | Notes |
|---------|---|---|---|---|
| Equity Curve Chart | Implemented | Existing | - | Recharts LineChart |
| Comparison Chart | Implemented | Existing | - | Recharts LineChart |
| Profit Metrics | Implemented | Existing | - | CSS-based |
| Drawdown Chart | Not Implemented | HIGH | MEDIUM | Recommended next |
| Returns Distribution | Not Implemented | HIGH | MEDIUM | Histogram/Bar |
| Multi-Symbol View | Partial | HIGH | MEDIUM | Per-symbol charts |
| Advanced Filtering | Implemented | Existing | - | Backend + UI |
| Signal Visualization | Implemented | Existing | - | ReferenceDots |
| Export Charts | Not Implemented | MEDIUM | LOW-MEDIUM | PNG/SVG export |
| Zooming & Panning | Not Implemented | MEDIUM | MEDIUM | Custom handlers |
| Risk Metrics Charts | Not Implemented | LOW | MEDIUM | VaR, Confidence bands |

---

## 15. Conclusion

The current chart implementation provides a solid foundation using Recharts with:
- Equity curve visualization with signal overlays
- Multi-run comparison capability
- Responsive design and styling consistency
- Integration with advanced filtering and history management

The architecture is extensible and ready for the recommended enhancements, particularly:
1. Drawdown chart implementation
2. Returns distribution visualization
3. Enhanced multi-symbol visualization
4. Interactive features (zooming, export)

The backend filtering infrastructure (Task 3.3-3) is already in place and fully supports the frontend requirements for the roadmap.

