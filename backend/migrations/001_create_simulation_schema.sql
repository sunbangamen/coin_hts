-- PDR Phase 2 실시간 시뮬레이션 스키마
-- 생성 일시: 2025-11-04

-- PostgreSQL 확장 활성화
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. 시장 캔들 데이터 테이블
CREATE TABLE IF NOT EXISTS market_candles (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,  -- '1m', '5m', '1h', '1d' 등
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    open DECIMAL(18, 8) NOT NULL,
    high DECIMAL(18, 8) NOT NULL,
    low DECIMAL(18, 8) NOT NULL,
    close DECIMAL(18, 8) NOT NULL,
    volume DECIMAL(20, 8) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT market_candles_unique UNIQUE(symbol, timeframe, timestamp)
);

CREATE INDEX idx_market_candles_symbol_time ON market_candles(symbol, timeframe, timestamp DESC);
CREATE INDEX idx_market_candles_timestamp ON market_candles(timestamp DESC);


-- 2. 실시간 거래 신호 테이블
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    price DECIMAL(18, 8) NOT NULL,
    confidence DECIMAL(5, 4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    signal_id UUID DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT signals_unique UNIQUE(symbol, strategy_name, timestamp, side)
);

CREATE INDEX idx_signals_symbol_time ON signals(symbol, timestamp DESC);
CREATE INDEX idx_signals_strategy ON signals(strategy_name, timestamp DESC);
CREATE INDEX idx_signals_signal_id ON signals(signal_id);


-- 3. 가상 포지션 테이블
CREATE TABLE IF NOT EXISTS simulation_positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    entry_price DECIMAL(18, 8) NOT NULL,
    quantity DECIMAL(18, 8) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('OPEN', 'CLOSED', 'LIQUIDATED')),
    exit_time TIMESTAMP WITH TIME ZONE,
    exit_price DECIMAL(18, 8),
    realized_pnl DECIMAL(18, 8),
    realized_pnl_pct DECIMAL(10, 6),
    fee_amount DECIMAL(18, 8) DEFAULT 0,
    slippage_amount DECIMAL(18, 8) DEFAULT 0,
    unrealized_pnl DECIMAL(18, 8),  -- 매 캔들마다 업데이트
    unrealized_pnl_pct DECIMAL(10, 6),  -- 매 캔들마다 업데이트
    last_price DECIMAL(18, 8),  -- 가장 최근 가격 (PnL 계산용)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_simulation_positions_symbol ON simulation_positions(symbol);
CREATE INDEX idx_simulation_positions_strategy ON simulation_positions(strategy_name);
CREATE INDEX idx_simulation_positions_status ON simulation_positions(status);
CREATE INDEX idx_simulation_positions_time ON simulation_positions(entry_time DESC);


-- 4. 거래 이력 테이블 (포지션 종료 시 기록)
CREATE TABLE IF NOT EXISTS simulation_trades (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    entry_price DECIMAL(18, 8) NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_price DECIMAL(18, 8) NOT NULL,
    quantity DECIMAL(18, 8) NOT NULL,
    realized_pnl DECIMAL(18, 8) NOT NULL,
    realized_pnl_pct DECIMAL(10, 6) NOT NULL,
    fee_amount DECIMAL(18, 8) DEFAULT 0,
    slippage_amount DECIMAL(18, 8) DEFAULT 0,
    hold_duration INTERVAL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_simulation_trades_symbol ON simulation_trades(symbol);
CREATE INDEX idx_simulation_trades_strategy ON simulation_trades(strategy_name);
CREATE INDEX idx_simulation_trades_exit_time ON simulation_trades(exit_time DESC);


-- 5. 시뮬레이션 세션 메타데이터 테이블
CREATE TABLE IF NOT EXISTS simulation_sessions (
    id SERIAL PRIMARY KEY,
    session_id UUID DEFAULT gen_random_uuid() UNIQUE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('RUNNING', 'PAUSED', 'STOPPED')),
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    total_pnl DECIMAL(18, 8) DEFAULT 0,
    total_pnl_pct DECIMAL(10, 6) DEFAULT 0,
    total_trades INT DEFAULT 0,
    win_count INT DEFAULT 0,
    lose_count INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_simulation_sessions_status ON simulation_sessions(status);
CREATE INDEX idx_simulation_sessions_start_time ON simulation_sessions(start_time DESC);


-- 6. 실시간 데이터 수집 상태 테이블
CREATE TABLE IF NOT EXISTS market_data_collection_status (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    last_candle_timestamp TIMESTAMP WITH TIME ZONE,
    last_collected_at TIMESTAMP WITH TIME ZONE,
    error_count INT DEFAULT 0,
    last_error_message TEXT,
    status VARCHAR(20) NOT NULL CHECK (status IN ('CONNECTED', 'CONNECTING', 'DISCONNECTED', 'ERROR')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT market_data_collection_status_unique UNIQUE(symbol, timeframe)
);

CREATE INDEX idx_market_data_collection_status_symbol ON market_data_collection_status(symbol);


-- 7. 전략 설정 메타데이터 테이블
CREATE TABLE IF NOT EXISTS strategy_configurations (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    config_json JSONB,  -- 전략별 파라미터 저장
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT strategy_configurations_unique UNIQUE(strategy_name, symbol)
);

CREATE INDEX idx_strategy_configurations_strategy ON strategy_configurations(strategy_name);
CREATE INDEX idx_strategy_configurations_symbol ON strategy_configurations(symbol);


-- 8. 성능 지표 스냅샷 테이블
CREATE TABLE IF NOT EXISTS performance_snapshots (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES simulation_sessions(session_id),
    symbol VARCHAR(20),
    strategy_name VARCHAR(100),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    total_pnl DECIMAL(18, 8),
    total_pnl_pct DECIMAL(10, 6),
    win_count INT,
    lose_count INT,
    win_rate DECIMAL(5, 4),
    max_drawdown DECIMAL(10, 6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_performance_snapshots_session ON performance_snapshots(session_id);
CREATE INDEX idx_performance_snapshots_time ON performance_snapshots(timestamp DESC);
