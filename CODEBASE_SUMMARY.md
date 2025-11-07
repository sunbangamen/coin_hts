# Cryptocurrency Backtesting Platform - Codebase Summary

## Overview
This is a comprehensive chart implementation and backtest history management system built with React (Frontend) and FastAPI (Backend) using Recharts for visualizations.

---

## Key Files & Locations

### Frontend - Chart Components
```
/home/limeking/projects/worktree/coin-23/frontend/src/
├── components/
│   ├── BacktestResults.jsx ✓ MAIN CHART COMPONENT
│   │   └── Features: Equity Curve, Signal Markers, Metrics Summary
│   │   └── Chart Lines: 161-294
│   │   └── Using: Recharts LineChart, ReferenceDot
│   │
│   ├── CompareResultsModal.jsx ✓ COMPARISON CHART
│   │   └── Features: Multi-run comparison, Average returns
│   │   └── Chart Lines: 57-82, 215-246
│   │   └── Using: Recharts LineChart
│   │
│   ├── ProfitChart.jsx ✓ METRICS DISPLAY
│   │   └── Features: CSS-based metric cards, Mini bar chart
│   │   └── 4 Key metrics displayed
│   │   └── Using: CSS only (no Recharts)
│   │
│   ├── AdvancedFilterPanel.jsx ✓ FILTER UI
│   │   └── Features: Range filters, Date filters, Validation
│   │   └── Return/Signal/Date filtering
│   │   └── Real-time application via SWR
│   │
│   └── SignalStream.jsx, SignalsTable.jsx, PositionTable.jsx
│       └── Supporting components for signal visualization
│
├── pages/
│   ├── BacktestPage.jsx ✓ EXECUTION PAGE
│   │   └── Form: Strategy selection, Parameters, Symbols, Dates
│   │   └── Results: BacktestResults component integration
│   │   └── Validation: Real-time with visual feedback
│   │
│   └── SignalViewerPage.jsx ✓ HISTORY & ANALYSIS PAGE
│       └── Latest results card
│       └── History table with pagination
│       └── Advanced filtering
│       └── Comparison modal
│
├── services/
│   └── backtestApi.js ✓ API SERVICE
│       ├── fetchLatestBacktest()
│       ├── fetchBacktestHistory(params) - With advanced filters
│       ├── fetchBacktestDetail(runId)
│       └── Download functions
│
├── styles/
│   ├── App.css (1230 lines) - Global styles
│   ├── CompareResultsModal.css (370 lines) - Modal styling
│   ├── ProfitChart.css (129 lines) - Metrics styling
│   ├── AdvancedFilterPanel.css (297 lines) - Filter styling
│   └── Other component styles
│
└── utils/
    ├── formatters.js - Number/Date/Percent formatting
    └── validation.js - Form validation logic
```

### Backend - API & Data Management
```
/home/limeking/projects/worktree/coin-23/backend/app/
├── main.py ✓ MAIN API FILE
│   ├── Lines 775-880: GET /api/backtests/history (Advanced filtering)
│   ├── Lines 465-540: POST /api/backtests/run (Execute)
│   ├── Lines 686-774: GET /api/backtests/latest (Latest result)
│   ├── Lines 883-930: GET /api/backtests/{run_id}/download (Details)
│   └── Lines 936-980: GET /api/backtests/{run_id} (Alternative)
│
├── result_manager.py ✓ RESULT HANDLING
│   ├── save_result_file() - Save backtest JSON
│   ├── get_result() - Retrieve result by run_id
│   ├── get_history() - Get filtered history
│   ├── save_manifest_file() - Metadata management
│   └── cleanup_old_results() - File maintenance
│
├── routers/
│   └── data.py - Data management API
│       └── Inventory, Upload, Refresh endpoints
│
├── jobs.py - Background job processing
├── task_manager.py - Task status tracking
├── strategy_factory.py - Strategy instantiation
├── scheduler.py - Scheduled data collection
└── database.py - Database operations
```

---

## Architecture Flow Diagrams

### 1. Backtest Execution Flow
```
User Interface (BacktestPage.jsx)
  ↓
Input Validation (validation.js)
  ↓
API Call: POST /api/backtests/run
  ↓ [FastAPI Backend]
  ├─ ParseRequest → validate parameters
  ├─ Strategy Factory → instantiate strategy
  ├─ Data Loader → fetch market data
  ├─ Run Simulation → execute backtest
  ├─ Calculate Metrics → performance metrics
  └─ Result Manager → save result to disk
  ↓
SWR Polling (Frontend)
  ↓
Display Results (BacktestResults.jsx)
  └─ Render Equity Curve Chart with Signal Markers
```

### 2. Results Display & Analysis Flow
```
SignalViewerPage.jsx (Main Hub)
  ├─ Latest Results Card
  │  ├─ API: fetchLatestBacktest()
  │  └─ Display: Key metrics + symbols performance
  │
  ├─ History Table with Pagination
  │  ├─ API: fetchBacktestHistory(limit, offset)
  │  ├─ Support: Strategy, Return, Signal, Date filters
  │  └─ Display: Table with sortable columns
  │
  ├─ Advanced Filter Panel
  │  ├─ Filter State Management
  │  ├─ Validation (range checks)
  │  └─ SWR Key Update → triggers new history fetch
  │
  ├─ Comparison Modal (Modal on demand)
  │  ├─ Multi-select results
  │  ├─ Load Details via: fetchBacktestDetail()
  │  ├─ Display: Metrics table + comparison chart
  │  └─ Chart: LineChart comparing avg returns
  │
  └─ Export Functions
     ├── Download JSON
     └── Download CSV
```

### 3. Chart Rendering Pipeline
```
Backtest Result Data
  ↓
Data Transformation (in component)
  ├─ performance_curve → [{ timestamp, equity }]
  ├─ signals → signal markers
  └─ metrics aggregation
  ↓
Recharts Component
  ├─ LineChart (responsive container)
  ├─ CartesianGrid, XAxis, YAxis
  ├─ Tooltip (formatted)
  ├─ Legend
  ├─ Line (equity curve)
  └─ ReferenceDots (signals)
  ↓
Rendered SVG Canvas
  └─ Interactive visualization
```

---

## API Specification Summary

### Backtest Endpoints

#### 1. Execute Backtest
```
POST /api/backtests/run
Content-Type: application/json

Request:
{
  "strategy": "volume_long_candle",
  "symbols": ["BTC_KRW", "ETH_KRW"],
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "timeframe": "1d",
  "params": {"vol_ma_window": 20, ...}
}

Response: BacktestResponse (full result with equity curve)
```

#### 2. Get Latest Result
```
GET /api/backtests/latest
Response: BacktestResponse
```

#### 3. Get History with Advanced Filtering
```
GET /api/backtests/history?limit=10&offset=0&min_return=-0.05&max_return=0.20&...

Query Parameters:
- limit: 1-100 (default 10)
- offset: >= 0 (default 0)
- strategy: string (optional)
- min_return: float (optional)
- max_return: float (optional)
- min_signals: int (optional)
- max_signals: int (optional)
- date_from: YYYY-MM-DD (optional)
- date_to: YYYY-MM-DD (optional)

Response: BacktestHistoryResponse
{
  "total": 150,
  "limit": 10,
  "offset": 0,
  "items": [
    {
      "run_id": "uuid",
      "strategy": "volume_long_candle",
      "total_signals": 25,
      "execution_time": 2.5,
      "start_date": "2024-01-01",
      "end_date": "2024-12-31",
      "timeframe": "1d",
      "symbols": ["BTC_KRW"],
      "avg_return": 0.15,
      "win_rate": 0.64,
      "max_drawdown": -0.08
    }
  ]
}
```

#### 4. Download Result Details
```
GET /api/backtests/{run_id}/download
Response: Full BacktestResponse with equity curve and signals
```

---

## Data Structure Schemas

### Backtest Result Schema
```javascript
{
  // Metadata
  run_id: string (UUID),
  strategy: string,
  version: string,
  description?: string,

  // Execution Parameters
  start_date: string (YYYY-MM-DD),
  end_date: string (YYYY-MM-DD),
  timeframe: string (1d, 1h, 5m),

  // Results
  total_signals: number,
  execution_time: number (seconds),

  // Per-Symbol Data
  symbols: [{
    symbol: string,
    
    // Signals
    signals: [{
      timestamp: string (ISO 8601),
      type: string (BUY or SELL),
      entry_price: number,
      exit_price?: number,
      return?: number (as percentage),
      hold_bars: number
    }],

    // Performance Curve
    performance_curve: [{
      timestamp: string,
      equity: number (0-1 scale, 1.0 = 100%)
    }],

    // Metrics
    win_rate: number (0-1),
    avg_return: number (as decimal, e.g., 0.15 = 15%),
    max_drawdown: number (as decimal),
    avg_hold_bars: number
  }],

  // Metadata
  metadata: {
    execution_date: string (ISO 8601),
    environment: string,
    execution_host: string
  }
}
```

### Chart Data Format
```javascript
// Equity Curve Chart Data
[
  {
    timestamp: "2024-01-01T00:00:00Z",
    equity: 100.50,          // Percentage (100 = starting capital)
    equityValue: 1.0050,     // Normalized (1.0 = starting capital)
    signal?: "BUY",          // Optional signal marker
    price?: 65000            // Optional signal price
  },
  // ... more points
]

// Comparison Chart Data
[
  {
    name: "Run 1",
    runId: "abc12345",
    avgReturn: 0.15          // 15%
  },
  {
    name: "Run 2",
    runId: "def67890",
    avgReturn: 0.12          // 12%
  }
]
```

---

## Dependencies & Libraries

### Frontend (package.json)
```json
{
  "react": "^18.2.0",           // UI Framework
  "react-dom": "^18.2.0",       // DOM Renderer
  "react-router-dom": "^6.20.0", // Routing
  "recharts": "^2.10.0",         // Charts (PRIMARY)
  "axios": "^1.6.0",             // HTTP Client
  "swr": "^2.3.6"                // Data Fetching & Caching
}
```

### Key Charting Features (Recharts)
- **ResponsiveContainer**: Fluid sizing
- **LineChart**: Time-series visualization
- **BarChart**: Distribution charts (future)
- **ReferenceDot**: Signal markers
- **CartesianGrid**: Background grid
- **XAxis/YAxis**: Customizable axes
- **Tooltip**: Interactive tooltips
- **Legend**: Chart legend

---

## Color Palette

```
Primary Colors (Profit/Loss):
- Success (Green):   #28a745
- Error (Red):       #dc3545

Neutral Colors:
- Dark (Primary):    #2c3e50
- Accent (Purple):   #667eea

Background:
- White:            #ffffff
- Light Gray:       #f8f9fa
- Very Light Gray:  #f9f9f9
- Disabled Gray:    #e0e0e0

Borders:
- Primary Border:   #e0e0e0
- Secondary Border: #dee2e6
```

---

## Component Communication

### State Management Pattern
```
React Hooks (useState, useMemo, useCallback)
  ↓
SWR (for data fetching & caching)
  ↓
Props passing (parent → child)
  ↓
Event handlers (child → parent via callbacks)
```

### SWR Implementation Examples
```javascript
// Fetch with automatic revalidation
const { data: latest, error, isLoading } = useSWR(
  '/api/backtests/latest',
  fetcher,
  { revalidateOnFocus: false, refreshInterval: 5000 }
)

// Conditional fetching with filters
const [filters, setFilters] = useState({})
const { data: history } = useSWR(
  ['/api/backtests/history', filters],
  ([url, f]) => fetchBacktestHistory(f)
)
```

---

## File Statistics

```
Frontend Components:     ~5,500 lines (JSX)
Frontend Styles:         ~3,900 lines (CSS)
Frontend Utilities:      ~1,500 lines (JS)
Backend Main API:        ~1,600 lines (Python)
Backend Services:        ~2,000 lines (Python)
Total Project:          ~14,500+ lines
```

---

## Key Implementation Details

### Equity Curve Chart (BacktestResults.jsx)
- **Location**: Lines 161-294
- **Components**: LineChart + ReferenceDot
- **Data Transformation**: equity as percentage
- **Signal Markers**: Buy (green #28a745) / Sell (red #dc3545)
- **Responsive**: 400px height, ResponsiveContainer
- **Tooltip**: Custom formatter for percentage display

### Comparison Chart (CompareResultsModal.jsx)
- **Location**: Lines 57-82 (data), 215-246 (render)
- **Components**: LineChart with single Line
- **Data Structure**: Average return per run
- **Height**: 300px
- **Colors**: Array of 3 predefined colors
- **Tooltip**: Percentage formatted

### Advanced Filtering (AdvancedFilterPanel.jsx)
- **Filters**: min/max return, min/max signals, date range
- **Validation**: Range checking, date comparison
- **Integration**: SWR key update pattern
- **Real-time**: Immediate filter application

---

## Performance Considerations

### Current Optimizations
1. **SWR Caching**: Automatic data deduplication
2. **Pagination**: History limited to 10 items per request
3. **Memoization**: useMemo for expensive calculations
4. **Responsive Containers**: Recharts handles resizing

### Potential Bottlenecks
1. **Large Equity Curves**: >1000 data points may lag
   - Solution: Implement data decimation (every Nth point)
2. **Comparison Modal**: Loading multiple detailed results
   - Solution: Lazy load and paginate
3. **Chart Re-renders**: Check shouldComponentUpdate equivalent

---

## Testing Strategy

### Unit Tests
- Data transformation functions
- Validation logic
- Filter application

### Integration Tests
- API integration
- Component rendering with live data
- State management

### E2E Tests
- Full workflow: Execute → View → Compare → Export

---

## Recommended Enhancements (Priority Order)

### HIGH PRIORITY
1. Drawdown Curve Chart - Risk analysis
2. Returns Distribution - Performance visualization
3. Multi-Symbol Charts - Per-symbol analysis

### MEDIUM PRIORITY
4. Interactive Features (zoom, pan, export)
5. Risk Metrics (Sharpe, Profit Factor, etc.)
6. Benchmark Comparison

### LOW PRIORITY
7. Chart Customization Options
8. Advanced Time Period Selection

---

## Documentation References

### Generated Documents
- **CHART_IMPLEMENTATION_ANALYSIS.md** (21KB) - Comprehensive analysis
- **CHART_QUICK_REFERENCE.md** (7KB) - Quick implementation guide

### Code References
- BacktestResults.jsx: Lines 161-294 (Chart implementation)
- CompareResultsModal.jsx: Lines 57-82, 215-246 (Comparison chart)
- main.py: Lines 775-880 (History API with filtering)
- backtestApi.js: Complete file (API service)

---

## Quick Navigation

```
Git Branch: coin-23
Recent Commits:
- ecf56bd: Advanced filtering UI to backtest history (Frontend)
- fb17b77: Advanced filtering to backtest history API (Backend)
- dce39b2: Results comparison view with charts

Project Root:
/home/limeking/projects/worktree/coin-23/

Frontend:
/home/limeking/projects/worktree/coin-23/frontend/src/

Backend:
/home/limeking/projects/worktree/coin-23/backend/app/
```

---

## Summary

The cryptocurrency backtesting platform has a robust chart implementation using Recharts with:
- Equity curve visualization with signal overlays
- Multi-run comparison capability
- Advanced result filtering (7 parameters)
- Responsive design and consistent styling
- Well-structured component hierarchy
- Clean separation of concerns (components, pages, services)

The architecture is extensible and ready for planned enhancements in risk visualization, multi-symbol analysis, and interactive features.

