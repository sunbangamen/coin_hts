# Task 3.5: 결과 저장 스키마 설계

**PostgreSQL + Parquet 저장소 데이터베이스 스키마 및 구조 정의**

---

## 1. PostgreSQL 스키마

### 1.1 backtest_results 테이블

메타데이터를 저장하는 메인 테이블입니다. 각 백테스트 실행 결과의 메타정보를 기록합니다.

```sql
-- backtest_results 테이블: 메타데이터 저장
CREATE TABLE backtest_results (
    task_id UUID PRIMARY KEY,
    strategy VARCHAR(100) NOT NULL,
    symbols JSONB NOT NULL,                          -- ["BTC/USDT", "ETH/USDT", ...]
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    timeframe VARCHAR(10),                           -- "1h", "4h", "1d" 등
    status VARCHAR(20) NOT NULL,                     -- "completed", "failed", "running"

    -- 파일 관리
    parquet_path VARCHAR(500) NOT NULL UNIQUE,       -- "backtests/{task_id}/"
    file_size BIGINT,                                -- Parquet 파일 전체 크기 (bytes)
    record_count INTEGER,                            -- 저장된 신호 개수

    -- 메타데이터
    metadata JSONB DEFAULT '{}',                     -- 확장 가능한 메타데이터
                                                      -- {"compression": "snappy", "schema_version": "1.0", ...}

    -- 타임스탬프
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- 제약조건
    CONSTRAINT status_valid CHECK (status IN ('completed', 'failed', 'running')),
    CONSTRAINT date_order CHECK (start_date <= end_date)
);

-- 인덱스 생성
CREATE INDEX idx_backtest_results_created_at ON backtest_results(created_at DESC);
CREATE INDEX idx_backtest_results_strategy ON backtest_results(strategy);
CREATE INDEX idx_backtest_results_status ON backtest_results(status);
CREATE INDEX idx_backtest_results_symbols ON backtest_results USING GIN (symbols);
CREATE INDEX idx_backtest_results_task_id ON backtest_results(task_id);

-- updated_at 자동 갱신 트리거
CREATE OR REPLACE FUNCTION update_backtest_results_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER backtest_results_update_timestamp
BEFORE UPDATE ON backtest_results
FOR EACH ROW
EXECUTE FUNCTION update_backtest_results_timestamp();
```

### 1.2 컬럼 상세 설명

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| task_id | UUID | 백테스트 실행 ID (PK) |
| strategy | VARCHAR(100) | 전략명 (e.g., "volume_zone_breakout") |
| symbols | JSONB | 백테스트 대상 심볼 배열 |
| start_date | DATE | 백테스트 시작 날짜 |
| end_date | DATE | 백테스트 종료 날짜 |
| timeframe | VARCHAR(10) | 캔들 타임프레임 |
| status | VARCHAR(20) | 실행 상태 (completed/failed/running) |
| parquet_path | VARCHAR(500) | Parquet 파일 저장 디렉토리 |
| file_size | BIGINT | 저장된 Parquet 파일 크기 |
| record_count | INTEGER | 신호 데이터 개수 |
| metadata | JSONB | 확장 메타데이터 (JSON 포맷) |
| created_at | TIMESTAMP | 생성 시간 (UTC) |
| updated_at | TIMESTAMP | 마지막 수정 시간 (UTC) |

---

## 2. Parquet 스키마

Parquet은 대용량 신호 데이터를 효율적으로 저장합니다. **3개 테이블**로 정규화됩니다:

### 2.1 symbol_summary.parquet

각 심볼별 통계 정보를 저장합니다.

```python
# PyArrow 스키마
import pyarrow as pa

symbol_summary_schema = pa.schema([
    pa.field("symbol", pa.string()),                        # "BTC/USDT"
    pa.field("win_rate", pa.float64()),                     # 승률 (%)
    pa.field("avg_return", pa.float64()),                   # 평균 수익률 (%)
    pa.field("max_return", pa.float64()),                   # 최대 수익률 (%)
    pa.field("min_return", pa.float64()),                   # 최소 수익률 (%)
    pa.field("max_drawdown", pa.float64()),                 # 최대 낙폭 (%)
    pa.field("avg_hold_bars", pa.float64()),                # 평균 보유 기간 (캔들 수)
    pa.field("total_signals", pa.int32()),                  # 총 신호 개수
    pa.field("winning_signals", pa.int32()),                # 수익 신호 개수
    pa.field("losing_signals", pa.int32()),                 # 손실 신호 개수
    pa.field("total_pnl", pa.float64()),                    # 총 손익
    pa.field("total_pnl_pct", pa.float64()),                # 총 손익률 (%)
])
```

**예시 데이터**:
```
symbol        | win_rate | avg_return | max_drawdown | total_signals
BTC/USDT      | 58.5     | 2.15       | 8.3          | 200
ETH/USDT      | 55.2     | 1.85       | 6.5          | 180
```

---

### 2.2 symbol_signals.parquet

각 신호별 상세 정보를 저장합니다.

```python
symbol_signals_schema = pa.schema([
    pa.field("symbol", pa.string()),                        # "BTC/USDT"
    pa.field("signal_index", pa.int32()),                   # 신호 순번
    pa.field("timestamp", pa.timestamp('us')),              # 신호 발생 시간 (UTC)
    pa.field("type", pa.string()),                          # "buy", "sell"
    pa.field("entry_price", pa.float64()),                  # 진입 가격
    pa.field("exit_price", pa.float64()),                   # 청산 가격 (None if still open)
    pa.field("quantity", pa.float64()),                     # 거래량
    pa.field("return_pct", pa.float64()),                   # 수익률 (%)
    pa.field("hold_bars", pa.int32()),                      # 보유 기간 (캔들 수)
    pa.field("fee_amount", pa.float64()),                   # 수수료
    pa.field("slippage_amount", pa.float64()),              # 슬리피지
    pa.field("status", pa.string()),                        # "closed", "open"
])
```

**예시 데이터**:
```
symbol   | signal_index | timestamp           | type | entry_price | exit_price | return_pct
BTC/USDT | 1            | 2024-01-01 10:00   | buy  | 42000       | 42840      | 2.0
BTC/USDT | 2            | 2024-01-01 14:00   | sell | 42840       | 42100      | -1.8
ETH/USDT | 1            | 2024-01-01 12:30   | buy  | 2250        | 2295       | 2.0
```

---

### 2.3 performance_curve.parquet

시간대별 포트폴리오 성과 곡선을 저장합니다.

```python
performance_curve_schema = pa.schema([
    pa.field("symbol", pa.string()),                        # "BTC/USDT"
    pa.field("idx", pa.int32()),                            # 시계열 인덱스
    pa.field("timestamp", pa.timestamp('us')),              # 시간 (UTC)
    pa.field("equity", pa.float64()),                       # 포트폴리오 자산가 ($)
    pa.field("drawdown", pa.float64()),                     # 낙폭 (%)
    pa.field("cumulative_pnl", pa.float64()),               # 누적 손익 ($)
    pa.field("cumulative_pnl_pct", pa.float64()),           # 누적 손익률 (%)
])
```

**예시 데이터**:
```
symbol   | idx | timestamp           | equity  | drawdown | cumulative_pnl
BTC/USDT | 0   | 2024-01-01 00:00   | 100000  | 0.0      | 0
BTC/USDT | 1   | 2024-01-01 01:00   | 102000  | 0.0      | 2000
BTC/USDT | 2   | 2024-01-01 02:00   | 100300  | 1.7      | 300
```

---

## 3. 저장 구조

### 3.1 파일 시스템 레이아웃

```
backtests/
├── {task_id_1}/
│   ├── symbol_summary.parquet
│   ├── symbol_signals.parquet
│   ├── performance_curve.parquet
│   └── metadata.json                    # 스키마 버전, 압축 정보 등
├── {task_id_2}/
│   ├── symbol_summary.parquet
│   ├── symbol_signals.parquet
│   ├── performance_curve.parquet
│   └── metadata.json
└── ...
```

### 3.2 metadata.json 형식

각 결과 디렉토리의 `metadata.json`은 스키마 버전과 메타정보를 기록합니다.

```json
{
  "schema_version": "1.0",
  "compression": "snappy",
  "parquet_files": {
    "symbol_summary": {
      "row_count": 5,
      "file_size_bytes": 2048
    },
    "symbol_signals": {
      "row_count": 1250,
      "file_size_bytes": 102400
    },
    "performance_curve": {
      "row_count": 720,
      "file_size_bytes": 28672
    }
  },
  "created_at": "2024-01-01T10:30:00Z",
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 4. 데이터 흐름

### 4.1 저장 흐름 (JSON → PostgreSQL + Parquet)

```
BacktestResult (JSON)
    ↓
┌─────────────────────────────────────────┐
│ converters.json_to_parquet()            │
│ - JSON 파싱                             │
│ - symbols 배열 → 3개 Parquet 테이블   │
│ - Snappy 압축                           │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ PostgreSQLResultStorage.save_result()   │
│ 1. PostgreSQL INSERT (메타데이터)       │
│ 2. Parquet 파일 저장                    │
│ 3. 트랜잭션 커밋                        │
└─────────────────────────────────────────┘
    ↓
PostgreSQL: backtest_results 레코드
Parquet: backtests/{task_id}/ 파일들
```

### 4.2 조회 흐름 (PostgreSQL + Parquet → BacktestResult)

```
task_id
    ↓
PostgreSQLResultStorage.get_result()
├─ PostgreSQL SELECT (메타데이터 조회)
├─ Parquet 파일 읽기 (3개 테이블)
└─ 데이터 병합 → BacktestResult dict 반환
    ↓
BacktestResult (원본 JSON 형식)
```

---

## 5. 성능 최적화

### 5.1 인덱스 전략

| 인덱스 | 대상 컬럼 | 용도 |
|--------|---------|------|
| PK | task_id | ID 기반 조회 (빠름) |
| created_at DESC | created_at | 최신순 조회 (정렬 최적화) |
| strategy | strategy | 전략명 필터링 |
| status | status | 상태 필터링 |
| symbols (GIN) | symbols | JSONB 배열 검색 |

### 5.2 Parquet 최적화

- **압축**: Snappy (빠른 압축/해제, 중간 압축률)
- **Row Group 크기**: 10,000 rows (기본값 1,000에서 증대)
- **정규화**: 3개 테이블로 정규화하여 불필요한 데이터 복사 최소화

### 5.3 예상 압축률

```
원본 JSON 크기:        100 MB
Parquet (Snappy):     2-3 MB
압축률:               97-98%
```

---

## 6. 관계도 (ERD)

```
┌─────────────────────────────────────────────────────────┐
│ backtest_results                                        │
├─────────────────────────────────────────────────────────┤
│ PK  task_id (UUID)                                      │
│     strategy (VARCHAR)                                  │
│     symbols (JSONB)                                     │
│     start_date, end_date (DATE)                         │
│     status (VARCHAR)                                    │
│     parquet_path (VARCHAR) ──┐                          │
│     file_size, record_count  │                          │
│     metadata (JSONB)         │                          │
│     created_at, updated_at   │                          │
└─────────────────────────────────────────────────────────┘
                                │
                                ├──→ 파일 시스템 (backtests/{task_id}/)
                                │
                    ┌───────────┴──────────────┐
                    ↓                          ↓
        ┌──────────────────────┐  ┌──────────────────────┐
        │ symbol_summary       │  │ symbol_signals       │
        │ .parquet            │  │ .parquet            │
        ├──────────────────────┤  ├──────────────────────┤
        │ symbol, win_rate,    │  │ symbol, signal_index │
        │ avg_return,          │  │ timestamp, type,     │
        │ max_drawdown, ...    │  │ entry_price, ...     │
        └──────────────────────┘  └──────────────────────┘

        ┌──────────────────────┐
        │ performance_curve    │
        │ .parquet            │
        ├──────────────────────┤
        │ symbol, idx, time    │
        │ equity, drawdown,    │
        │ cumulative_pnl, ...  │
        └──────────────────────┘
```

---

## 7. 마이그레이션 전략

### 7.1 스키마 버전 관리

```
Version 1.0 (현재):
- symbol_summary: 10개 컬럼
- symbol_signals: 12개 컬럼
- performance_curve: 7개 컬럼

향후 버전 2.0 (예):
- 새로운 지표 추가 시 backward-compatible하게 처리
- metadata.json의 schema_version으로 추적
```

### 7.2 Blue-Green 배포

- **Phase 1 (JSON-only)**: 기존 JSON 저장소 사용
- **Phase 2 (Dual-write)**: PostgreSQL + Parquet + JSON 모두 저장
- **Phase 3 (PostgreSQL/Parquet-only)**: 새 저장소만 사용
- **Phase 4 (JSON Archive)**: JSON은 읽기 전용으로 보관

---

## 8. 데이터 검증

### 8.1 스키마 검증

각 Parquet 파일은 작성 시 정의된 스키마와 비교하여 검증됩니다.

```python
# 예시: converters.py에서
expected_schema = symbol_signals_schema
actual_schema = table.schema
assert expected_schema == actual_schema, "Schema mismatch!"
```

### 8.2 데이터 무결성

- Parquet ETag 저장 (향후 S3 업로드 시 활용)
- 행 개수 검증 (메타데이터 record_count와 실제 행 수 비교)
- 타임스탬프 순서 검증

---

## 9. 쿼리 예제

### 9.1 최신 5개 완료된 백테스트 조회

```sql
SELECT task_id, strategy, symbols, created_at
FROM backtest_results
WHERE status = 'completed'
ORDER BY created_at DESC
LIMIT 5;
```

### 9.2 특정 전략의 최근 실행 결과 조회

```sql
SELECT task_id, start_date, end_date, status, record_count
FROM backtest_results
WHERE strategy = 'volume_zone_breakout'
  AND created_at > NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;
```

### 9.3 7일 이상된 결과 삭제 (cleanup)

```sql
DELETE FROM backtest_results
WHERE created_at < NOW() - INTERVAL '7 days'
RETURNING task_id, parquet_path;
```

---

## 10. 참고 문서

- **이슈**: GitHub #33 (Task 3.5)
- **계획**: `ri_20.md`
- **구현 상태**: `PHASE3_IMPLEMENTATION_STATUS.md`

