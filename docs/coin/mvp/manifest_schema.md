# Manifest JSON 스키마 (Phase 3 - 결과 파일 관리)

## 개요

비동기 백테스트 작업의 결과 메타데이터를 저장하는 JSON 파일입니다.

**저장 경로**: `${DATA_ROOT}/tasks/<task_id>/manifest.json`

**생성 시점**: 비동기 백테스트 작업 완료 시

**용도**:
- 작업 결과 파일 목록 관리
- 작업 실행 정보 기록
- 결과 파일 정리 정책 관리

---

## 스키마 정의

```json
{
  "task_id": "string (UUID)",
  "status": "string (completed | failed)",
  "strategy": "string",
  "params": {
    "key": "any"
  },
  "symbols": ["string"],
  "start_date": "string (YYYY-MM-DD)",
  "end_date": "string (YYYY-MM-DD)",
  "timeframe": "string (1d, 1h, 5m)",
  "result_files": [
    {
      "name": "string",
      "path": "string",
      "size_bytes": "integer",
      "checksum": "string (MD5 해시)"
    }
  ],
  "metadata": {
    "started_at": "string (ISO 8601, UTC)",
    "finished_at": "string (ISO 8601, UTC)",
    "duration_ms": "integer",
    "execution_host": "string",
    "environment": "string",
    "worker_id": "string (optional)"
  },
  "summary": {
    "total_signals": "integer",
    "symbols_processed": "integer",
    "symbols_failed": "integer",
    "average_execution_time_per_symbol_ms": "number"
  },
  "error": {
    "occurred": "boolean",
    "message": "string (if occurred = true)"
  }
}
```

---

## 필드 설명

### 기본 정보

| 필드 | 타입 | 설명 |
|------|------|------|
| `task_id` | string | 작업 고유 ID (UUID) |
| `status` | string | 작업 상태: `completed` 또는 `failed` |
| `strategy` | string | 사용된 전략명 (예: volume_zone_breakout) |
| `params` | object | 실제 적용된 전략 파라미터 |
| `symbols` | array | 처리한 심볼 목록 |
| `start_date` | string | 백테스트 시작 날짜 (YYYY-MM-DD) |
| `end_date` | string | 백테스트 종료 날짜 (YYYY-MM-DD) |
| `timeframe` | string | 사용된 타임프레임 (1d, 1h, 5m) |

### 결과 파일

| 필드 | 타입 | 설명 |
|------|------|------|
| `result_files` | array | 생성된 결과 파일 목록 |
| `.name` | string | 파일명 (예: result.json) |
| `.path` | string | 상대 경로 (예: result.json) |
| `.size_bytes` | integer | 파일 크기 (바이트) |
| `.checksum` | string | MD5 체크섬 (데이터 무결성 검증용) |

### 메타데이터

| 필드 | 타입 | 설명 |
|------|------|------|
| `metadata.started_at` | string | 작업 시작 시간 (ISO 8601, UTC) |
| `metadata.finished_at` | string | 작업 종료 시간 (ISO 8601, UTC) |
| `metadata.duration_ms` | integer | 작업 실행 시간 (밀리초) |
| `metadata.execution_host` | string | 실행 호스트명/IP |
| `metadata.environment` | string | 실행 환경 (development, staging, production) |
| `metadata.worker_id` | string | 워커 ID (선택사항) |

### 요약 정보

| 필드 | 타입 | 설명 |
|------|------|------|
| `summary.total_signals` | integer | 생성된 총 신호 개수 |
| `summary.symbols_processed` | integer | 처리 성공한 심볼 수 |
| `summary.symbols_failed` | integer | 처리 실패한 심볼 수 |
| `summary.average_execution_time_per_symbol_ms` | number | 심볼당 평균 실행 시간 |

### 에러 정보

| 필드 | 타입 | 설명 |
|------|------|------|
| `error.occurred` | boolean | 에러 발생 여부 |
| `error.message` | string | 에러 메시지 (occurred=true일 때만) |

---

## 예시

```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "strategy": "volume_zone_breakout",
  "params": {
    "volume_window": 10,
    "top_percentile": 0.2,
    "breakout_buffer": 0.0
  },
  "symbols": ["BTC_KRW", "ETH_KRW"],
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "timeframe": "1d",
  "result_files": [
    {
      "name": "result.json",
      "path": "result.json",
      "size_bytes": 2048576,
      "checksum": "d8e8fca2dc0f896fd7cb4cb0031ba249"
    }
  ],
  "metadata": {
    "started_at": "2025-11-04T10:30:45.123456Z",
    "finished_at": "2025-11-04T10:35:20.654321Z",
    "duration_ms": 275531,
    "execution_host": "coin-worker-1",
    "environment": "production",
    "worker_id": "worker-0"
  },
  "summary": {
    "total_signals": 45,
    "symbols_processed": 2,
    "symbols_failed": 0,
    "average_execution_time_per_symbol_ms": 137765.5
  },
  "error": {
    "occurred": false,
    "message": null
  }
}
```

---

## 디렉토리 구조

```
${DATA_ROOT}/tasks/
├── <task_id_1>/
│   ├── manifest.json
│   └── result.json
├── <task_id_2>/
│   ├── manifest.json
│   └── result.json
└── <task_id_3>/
    ├── manifest.json
    └── result.json
```

---

## 파일 정리 정책

### TTL (Time-To-Live)

- **기본값**: `TASK_RESULT_TTL_DAYS=7` (7일)
- **정리 스크립트**: `scripts/cleanup_task_results.py`
- **실행 주기**: 일일 (cron job 또는 스케줄러)

### 정리 대상

- 생성 후 7일 이상 된 작업 디렉토리 (manifest.json 생성 시간 기준)
- 실패한 작업 중 1일 이상 된 항목 (에러 발생 시간 기준)

### 보존 예외

- 중요도 태그가 있는 작업 (향후 기능)
- 수동으로 보존 표시된 작업 (향후 기능)

---

## 검증 사항

- ✅ manifest.json은 UTF-8 인코딩
- ✅ result.json과 manifest.json이 동일한 task_id 디렉토리에 위치
- ✅ 모든 result_files 경로는 상대 경로로 표기
- ✅ checksum 필드는 MD5 해시로 생성
- ✅ 타임스탬프는 ISO 8601 UTC 형식
