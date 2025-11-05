# End-to-End Testing Guide

Complete guide for running End-to-End (E2E) integration tests for the Coin Trading Simulation system.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Testing Scenarios](#testing-scenarios)
- [Test Execution](#test-execution)
- [Troubleshooting](#troubleshooting)
- [CI/CD Integration](#cicd-integration)

---

## Overview

The E2E testing suite validates the complete workflow of the trading simulation system across all components:

```
┌─────────────────────────────────────────────────────────┐
│            E2E Integration Testing                      │
├─────────────────────────────────────────────────────────┤
│ 1. API Health Check                                     │
│ 2. Strategy Discovery & Registration                    │
│ 3. Simulation Lifecycle (Start → Run → Stop)           │
│ 4. Market Data Collection (Upbit WebSocket)            │
│ 5. Position Management (Entry → Update → Exit)        │
│ 6. Performance Metrics Calculation                      │
│ 7. Trade History Tracking                              │
└─────────────────────────────────────────────────────────┘
```

### Test Coverage

| Component | Coverage | Status |
|-----------|----------|--------|
| Backend API | Health, Strategies, Simulation | ✅ Full |
| Database | Data Persistence, Queries | ✅ Full |
| Redis | Task Queue, Caching | ✅ Full |
| Position Manager | Entry, Update, Exit | ✅ Full |
| Strategy Runner | Signal Generation | ✅ Full |
| Performance Metrics | PnL, Win Rate, Drawdown | ✅ Full |

---

## Prerequisites

### System Requirements

- Docker & Docker Compose (version 1.29+)
- Linux/macOS/WSL2 (Windows)
- At least 4GB RAM available
- 5GB disk space for data volumes
- Internet connection (for Upbit WebSocket)

### Install Docker Compose

```bash
# macOS/Linux
brew install docker-compose

# Ubuntu/Debian
sudo apt-get install docker-compose

# Verify installation
docker-compose --version
```

### Clone and Setup

```bash
# Clone repository
git clone <repository-url>
cd coin-17

# Create data directory
mkdir -p data

# Check environment
docker-compose --version
docker --version
```

---

## Quick Start

### Option 1: Run E2E Tests Only (Recommended)

```bash
# Basic E2E integration tests
./scripts/run_e2e_tests.sh

# With backend unit tests
./scripts/run_e2e_tests.sh --with-unit

# With frontend tests
./scripts/run_e2e_tests.sh --with-frontend

# All tests (unit + integration + e2e)
./scripts/run_e2e_tests.sh --full
```

### Option 2: Manual Docker Compose

```bash
# Start core services (PostgreSQL, Redis, Backend)
docker-compose up -d postgres redis backend

# Wait for backend to be ready (check logs)
docker-compose logs backend

# Run E2E tests in separate window
docker-compose --profile e2e-test up e2e-test

# View test output
docker-compose logs -f e2e-test

# Stop all services
docker-compose down
```

### Option 3: Run Tests with Frontend Development Server

```bash
# Start all services with simulation profile
docker-compose --profile simulation up

# Access frontend at http://localhost:5173
# Access API at http://localhost:8000

# In another terminal, run E2E tests
docker-compose --profile e2e-test up e2e-test
```

---

## Testing Scenarios

### Scenario 1: Basic Simulation Workflow

**Objective**: Validate core simulation lifecycle

**Steps**:
1. API health check (GET `/api/health`)
2. List available strategies (GET `/api/strategies`)
3. Start simulation with strategy config (POST `/api/simulation/start`)
4. Verify simulation status (GET `/api/simulation/status`)
5. Check registered strategies (GET `/api/simulation/strategies`)
6. Stop simulation (POST `/api/simulation/stop`)

**Expected Results**:
- ✅ API responds to all health checks
- ✅ Strategies are properly registered
- ✅ Simulation starts with correct session ID
- ✅ WebSocket connection count is tracked
- ✅ Simulation cleanly stops

**Duration**: ~15 seconds

---

### Scenario 2: Market Data Collection

**Objective**: Validate real-time market data ingestion

**Steps**:
1. Start simulation with symbols [KRW-BTC, KRW-ETH, KRW-XRP]
2. Wait for 5-10 seconds for data collection
3. Query candles from each symbol (GET `/api/market/candles`)
4. Verify candle data format and completeness

**Expected Results**:
- ✅ Candles received from Upbit
- ✅ Proper timestamp, OHLCV data
- ✅ Multiple timeframes available

**Duration**: ~20 seconds

---

### Scenario 3: Position Lifecycle

**Objective**: Validate position entry, update, and exit

**Steps**:
1. Start simulation with volume_zone_breakout strategy
2. Wait for BUY signal generation
3. Track position entry (POST event detection)
4. Monitor unrealized PnL updates
5. Wait for SELL signal
6. Verify position closure and realized PnL

**Expected Results**:
- ✅ Positions enter and exit correctly
- ✅ PnL calculations are accurate
- ✅ Position state transitions are valid

**Duration**: ~30 seconds (depends on signal generation)

---

### Scenario 4: Performance Metrics

**Objective**: Validate performance calculation

**Steps**:
1. Run simulation with multiple trades
2. Query performance metrics (GET `/api/simulation/performance`)
3. Query trade history (GET `/api/simulation/history`)
4. Verify metric calculations:
   - Total PnL = sum of realized PnL
   - Win Rate = wins / total_trades
   - Max Drawdown = largest peak-to-trough decline

**Expected Results**:
- ✅ Metrics reflect actual trades
- ✅ Calculations are mathematically correct
- ✅ Values are within expected ranges

**Duration**: ~10 seconds

---

### Scenario 5: Concurrent Subscriptions

**Objective**: Validate system performance under load

**Steps**:
1. Start simulation with 5 symbols
2. Measure strategy execution latency
3. Monitor WebSocket client count
4. Check for data loss or missed signals

**Expected Results**:
- ✅ All 5 symbols receive updates
- ✅ Strategy latency < 1 second
- ✅ No data loss or dropped signals

**Duration**: ~30 seconds

---

## Test Execution

### Automated Test Execution

```bash
# Basic E2E tests only
./scripts/run_e2e_tests.sh

# With all backend unit tests
./scripts/run_e2e_tests.sh --with-unit

# With all frontend tests
./scripts/run_e2e_tests.sh --with-frontend

# Complete test suite
./scripts/run_e2e_tests.sh --full

# Show help
./scripts/run_e2e_tests.sh --help
```

### Manual Python Test Execution

```bash
# Start core services
docker-compose up -d postgres redis backend

# Wait for backend to start
sleep 10

# Run E2E test script
docker-compose exec -T backend python scripts/e2e_test_scenarios.py

# Or directly
cd /path/to/coin-17
python scripts/e2e_test_scenarios.py
```

### Using Docker Profile

```bash
# Profile: e2e-test
docker-compose --profile e2e-test up

# Profile: simulation (for manual testing)
docker-compose --profile simulation up

# Profile: frontend-dev (development)
docker-compose --profile frontend-dev up

# Multiple profiles
docker-compose --profile simulation --profile e2e-test up
```

---

## Test Output

### Sample E2E Test Output

```
========================================================
🚀 End-to-End 통합 테스트 시작
========================================================

▶️ Health Check...
✅ API 서버 정상 (200 OK)
✅ 데이터베이스 정상

▶️ List Available Strategies...
✅ 사용 가능한 전략: ['volume_long_candle', 'volume_zone_breakout']

▶️ Start Simulation...
✅ 시뮬레이션 시작됨 - ID: sim_12345
✅ JWT 토큰 획득: eyJhbGciOiJIUzI1NiI...

▶️ Check Simulation Status...
✅ 시뮬레이션 실행 중
✅ WebSocket 클라이언트: 1개

▶️ Verify Strategies Registered...
✅ 등록된 전략: 3개
  - KRW-BTC: volume_zone_breakout
  - KRW-ETH: volume_zone_breakout
  - KRW-XRP: volume_zone_breakout

▶️ Collect Market Data...
✅ KRW-BTC 캔들 데이터 수집: 10개

▶️ Track Positions...
✅ 활성 포지션: 2개
  - KRW-BTC: 수량=1.0, 손익=1500.50
  - KRW-ETH: 수량=10.0, 손익=-500.25

▶️ Check Performance Metrics...
✅ 성과 지표:
  - 총 손익: 1234.50
  - 승률: 66.67%
  - 최대낙폭: -5.25%

▶️ Retrieve Trade History...
✅ 거래 이력: 5개
  - 총 손익: 1234.50

▶️ Stop Simulation...
✅ 시뮬레이션 중지됨

========================================================
📋 E2E 테스트 결과 요약
========================================================

✅ 통과: 10개
  ✓ list_strategies
  ✓ start_simulation
  ✓ simulation_status
  ✓ strategies_registered
  ✓ market_data_collection
  ✓ position_tracking
  ✓ performance_metrics
  ✓ history_retrieval
  ✓ stop_simulation

========================================================
✅ E2E 테스트 PASSED
========================================================
```

---

## Troubleshooting

### Common Issues

#### 1. Backend Server Timeout

**Problem**: E2E test fails with "Backend server startup timeout"

**Solution**:
```bash
# Check backend logs
docker-compose logs backend

# Increase timeout in run_e2e_tests.sh
# Change: TIMEOUT=300 to TIMEOUT=600

# Or manually check backend
curl http://localhost:8000/api/health
```

#### 2. Database Connection Error

**Problem**: "PostgreSQL connection failed"

**Solution**:
```bash
# Ensure PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Recreate database
docker-compose down -v
docker-compose up -d postgres
```

#### 3. Redis Connection Failed

**Problem**: "Redis connection failed"

**Solution**:
```bash
# Check Redis status
redis-cli -p 6379 ping

# Or via Docker
docker-compose exec redis redis-cli ping

# Recreate Redis
docker-compose down
docker-compose up -d redis
```

#### 4. Port Already in Use

**Problem**: "Port 8000 already in use"

**Solution**:
```bash
# Find process using port 8000
lsof -i :8000

# Kill existing process
kill -9 <PID>

# Or change port in docker-compose.yml
# ports:
#   - "8001:8000"
```

#### 5. E2E Test Hangs

**Problem**: Test execution never completes

**Solution**:
```bash
# Check service logs
docker-compose logs backend
docker-compose logs redis
docker-compose logs postgres

# Restart services
docker-compose restart

# Or stop and recreate
docker-compose down -v
docker-compose up -d postgres redis backend
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Testing

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: coin_user
          POSTGRES_PASSWORD: coin_password
          POSTGRES_DB: coin_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Start backend
        run: |
          uvicorn backend.app.main:app &
          sleep 5

      - name: Run E2E Tests
        run: python scripts/e2e_test_scenarios.py

      - name: Run Unit Tests
        run: pytest tests/ -v

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: test-results/
```

---

## Performance Benchmarks

### Expected Performance Metrics

| Metric | Target | Status |
|--------|--------|--------|
| API Response Time | < 100ms | ✅ |
| Strategy Latency | < 1s | ✅ |
| Position Entry | < 500ms | ✅ |
| Database Query | < 50ms | ✅ |
| E2E Test Duration | < 2min | ✅ |

### Load Testing

```bash
# Test with 5 concurrent symbols
docker-compose up -d postgres redis backend

# Send test load
python scripts/load_test.py --symbols 5 --duration 60

# Monitor performance
docker stats
```

---

## Advanced Testing

### Custom Test Scenarios

Modify `scripts/e2e_test_scenarios.py`:

```python
# Add custom test
async def test_custom_scenario(self) -> bool:
    """Your custom test scenario"""
    logger.info("Running custom scenario...")
    try:
        # Your test logic
        result = await some_async_operation()
        self.test_results['passed'].append("custom_scenario")
        return True
    except Exception as e:
        self.test_results['failed'].append(f"Custom scenario: {e}")
        return False

# Add to test list in run_all_tests()
tests = [
    # ... existing tests ...
    ('Custom Scenario', self.test_custom_scenario),
]
```

### Debug Mode

```bash
# Run with verbose logging
PYTHONUNBUFFERED=1 python scripts/e2e_test_scenarios.py

# Check individual components
curl http://localhost:8000/api/health
curl http://localhost:8000/api/strategies
curl http://localhost:8000/api/simulation/status
```

---

## Support & Reporting

### Report Issues

When reporting E2E test failures, include:

1. **Test Output**
   ```bash
   docker-compose logs e2e-test > test_failure.log
   ```

2. **System Information**
   ```bash
   docker-compose --version
   docker --version
   uname -a
   ```

3. **Service Status**
   ```bash
   docker-compose ps
   docker-compose logs
   ```

4. **Error Messages**
   - Full error trace from test output
   - Relevant service logs

---

## References

- [Phase 4 Documentation](./coin/mvp/ri_12.md)
- [API Specification](./coin/mvp/api_spec.md)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [pytest Documentation](https://docs.pytest.org/)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Nov 2024 | Initial E2E testing guide |

---

**Last Updated**: November 2024
**Status**: ✅ Active
