# Phase 2 메타데이터 필드 확장 - 마이그레이션 가이드

**작성일**: 2025-11-03
**상태**: 📋 구현 완료
**버전**: API 1.1.0

---

## 1. 개요

Phase 2에서 `BacktestResponse` JSON 스키마를 확장하여 메타데이터 필드를 추가했습니다.
이 문서는 API 클라이언트가 새로운 필드를 처리하는 방법을 안내합니다.

### 주요 변경사항

| 항목 | 이전 (v1.0.0) | 현재 (v1.1.0) | 필수여부 |
|------|-------------|------------|--------|
| `version` | ❌ | ✅ | 옵션 (기본값: "1.1.0") |
| `metadata` | ❌ | ✅ | 옵션 (Phase 2 이후 필수화 예정) |
| `metadata.execution_date` | - | ✅ | 메타데이터 포함 시 필수 |
| `metadata.environment` | - | ✅ | 옵션 (기본값: "development") |
| `metadata.execution_host` | - | ✅ | 옵션 (기본값: "local") |
| `description` | ❌ | ✅ | 옵션 |

### 하위 호환성 (Backward Compatibility)

✅ **완전 하위 호환**: 새 필드는 모두 선택사항이므로 기존 클라이언트 코드가 정상 작동합니다.
단, 새 필드에 접근할 때는 null 체크가 필요합니다.

---

## 2. API 응답 예제

### Phase 1 (v1.0.0) - 기존 응답

```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "strategy": "volume_zone_breakout",
  "params": {
    "volume_window": 10,
    "top_percentile": 0.2,
    "breakout_buffer": 0.0
  },
  "start_date": "2024-01-01",
  "end_date": "2024-02-29",
  "timeframe": "1d",
  "total_signals": 24,
  "execution_time": 0.234,
  "symbols": [...]
}
```

### Phase 2 (v1.1.0) - 확장된 응답

```json
{
  "version": "1.1.0",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "strategy": "volume_zone_breakout",
  "params": {
    "volume_window": 10,
    "top_percentile": 0.2,
    "breakout_buffer": 0.0
  },
  "start_date": "2024-01-01",
  "end_date": "2024-02-29",
  "timeframe": "1d",
  "total_signals": 24,
  "execution_time": 0.234,
  "metadata": {
    "execution_date": "2025-11-03T16:30:45.123456Z",
    "environment": "development",
    "execution_host": "docker-container-abc123"
  },
  "description": null,
  "symbols": [...]
}
```

---

## 3. 클라이언트 마이그레이션 가이드

### JavaScript/React 클라이언트

#### 기존 코드 (문제 없음)
```javascript
// 기존 코드는 정상 작동
const { run_id, strategy, total_signals, execution_time } = response;
console.log(`Run ID: ${run_id}, Total Signals: ${total_signals}`);
```

#### 새 필드 사용 (null 체크 필수)
```javascript
// 방법 1: null 체크
if (response.metadata) {
  const { execution_date, environment, execution_host } = response.metadata;
  console.log(`실행: ${execution_date}, 환경: ${environment}`);
}

// 방법 2: 옵셔널 체이닝 (권장)
console.log(`API 버전: ${response.version ?? '1.0.0'}`);
console.log(`실행 환경: ${response.metadata?.environment ?? 'development'}`);
console.log(`실행 호스트: ${response.metadata?.execution_host ?? 'unknown'}`);
```

### TypeScript 클라이언트

#### 타입 정의 (v1.1.0)
```typescript
interface MetadataInfo {
  execution_date: string;     // ISO 8601 형식
  environment: string;        // "development", "staging", "production"
  execution_host: string;     // Docker container ID 또는 호스트명
}

interface BacktestResponse {
  version: string;                        // "1.1.0"
  run_id: string;
  strategy: string;
  params: Record<string, any>;
  start_date: string;
  end_date: string;
  timeframe: string;
  total_signals: number;
  execution_time: number;
  metadata?: MetadataInfo;                // 선택사항
  description?: string;                   // 선택사항
  symbols: SymbolResult[];
}
```

#### 사용 예제
```typescript
function handleBacktestResult(response: BacktestResponse) {
  // 버전 확인
  if (response.version >= "1.1.0") {
    console.log("메타데이터 지원");
  }

  // 메타데이터 안전하게 접근
  if (response.metadata) {
    const date = new Date(response.metadata.execution_date);
    console.log(`실행 시간: ${date.toLocaleString()}`);
  }

  // 기존 필드는 그대로 사용
  console.log(`신호 수: ${response.total_signals}`);
}
```

### Python 클라이언트

```python
import requests
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MetadataInfo:
    execution_date: str
    environment: str = "development"
    execution_host: str = "local"

@dataclass
class BacktestResponse:
    version: str
    run_id: str
    strategy: str
    params: dict
    start_date: str
    end_date: str
    timeframe: str
    total_signals: int
    execution_time: float
    symbols: list
    metadata: Optional[MetadataInfo] = None
    description: Optional[str] = None

# 사용
response = requests.post("http://api/backtests/run", json=payload).json()

# 메타데이터 접근
if response.get("metadata"):
    execution_date = datetime.fromisoformat(
        response["metadata"]["execution_date"].replace("Z", "+00:00")
    )
    print(f"실행 시간: {execution_date}")
```

---

## 4. API 버전 관리 정책

### Semantic Versioning

- **주 버전 (Major)**: 하위 호환되지 않는 변경 (예: 필드 제거)
- **부 버전 (Minor)**: 하위 호환되는 새 기능 (예: 새 필드 추가)
- **수정 버전 (Patch)**: 버그 수정

### 버전별 변경사항

| 버전 | 날짜 | 주요 변경 | 호환성 |
|------|------|---------|-------|
| 1.0.0 | Phase 1 | 초기 API 정의 | - |
| 1.1.0 | 2025-11-03 | version, metadata, description 필드 추가 | ✅ 하위호환 |
| 1.2.0 | 예정 | 추가 메타데이터 필드 (예: user_id, tags) | ✅ 하위호환 |
| 2.0.0 | 예정 | 주요 스키마 재구성 (구체적 일정 미정) | ❌ 하위호환 불가 |

### 클라이언트 권장사항

```javascript
// 버전 확인 후 분기 처리
const apiVersion = response.version || "1.0.0";

if (apiVersion >= "1.1.0") {
  // v1.1.0+ 기능 사용
  displayMetadata(response.metadata);
} else {
  // v1.0.0 호환 코드
  displayBasicInfo(response);
}
```

---

## 5. 메타데이터 필드 설명

### version
- **타입**: `string`
- **설명**: API 응답 스키마의 버전 (Semantic Versioning)
- **기본값**: "1.1.0"
- **예제**: "1.1.0", "1.2.0", "2.0.0"

### metadata.execution_date
- **타입**: `string` (ISO 8601 UTC 형식)
- **설명**: 백테스트 실행 날짜 및 시간
- **형식**: `YYYY-MM-DDTHH:MM:SS.ffffffZ`
- **예제**: "2025-11-03T16:30:45.123456Z"
- **파싱**: JavaScript `new Date(dateString)`, Python `datetime.fromisoformat(...)`

### metadata.environment
- **타입**: `string`
- **설명**: 백테스트 실행 환경
- **기본값**: "development"
- **가능 값**: "development", "staging", "production"
- **환경변수**: `ENVIRONMENT`

### metadata.execution_host
- **타입**: `string`
- **설명**: 백테스트를 실행한 호스트 정보
- **기본값**: "local"
- **예제**: "docker-abc123def456", "k8s-pod-xyz", "localhost"
- **환경변수**: `HOSTNAME`

### description
- **타입**: `string | null`
- **설명**: 백테스트 결과에 대한 선택적 설명
- **기본값**: `null`
- **용도**: 테스트 목적, 특이사항, 메모 등 기록

---

## 6. 마이그레이션 체크리스트

### API 제공자 (Backend)

- [x] `version` 필드 추가
- [x] `MetadataInfo` 모델 정의
- [x] `metadata` 필드 추가 (선택사항)
- [x] `description` 필드 추가 (선택사항)
- [x] 런타임에 `metadata` 수집 및 설정
- [x] API 문서 업데이트
- [ ] 라이브 환경에 배포 (예정)

### API 소비자 (Frontend/Client)

- [ ] 응답 타입 정의 업데이트
- [ ] null 체크 추가 (메타데이터 접근 시)
- [ ] UI에서 메타데이터 표시 (선택사항)
- [ ] 버전 확인 로직 추가 (선택사항)
- [ ] 테스트 완료
- [ ] 배포

---

## 7. 주의사항 및 FAQ

### Q: 기존 클라이언트가 새 필드를 무시하면 되지 않나요?

**A**: 네, 맞습니다! 새 필드는 모두 선택사항이므로 기존 코드가 정상 작동합니다.
다만 메타데이터를 활용하고 싶다면 위 가이드를 참고하여 업데이트하세요.

### Q: 메타데이터가 항상 반환되나요?

**A**: Phase 2에서는 메타데이터가 항상 포함됩니다. 향후 Phase 3 이후에는 메타데이터를 필수화할 예정입니다.

### Q: 과거 실행 결과(저장된 JSON)는 메타데이터가 없는데?

**A**: 과거 결과는 당시 API 버전으로 생성되었으므로 메타데이터가 없을 수 있습니다.
필요하면 마이그레이션 스크립트를 사용하여 일괄 업데이트할 수 있습니다.

```javascript
// 마이그레이션 예제
function upgradeToV11(oldResponse) {
  return {
    version: "1.1.0",
    ...oldResponse,
    metadata: {
      execution_date: new Date().toISOString(),
      environment: "development",
      execution_host: "migrated"
    }
  };
}
```

### Q: 환경 정보는 어떻게 자동으로 수집되나요?

**A**: 서버가 환경변수를 읽어 자동 설정합니다:
- `ENVIRONMENT`: 실행 환경 (기본값: "development")
- `HOSTNAME`: 호스트명 (기본값: "local")

Docker/Kubernetes 환경에서는 자동으로 올바른 값이 설정됩니다.

---

## 8. 추가 리소스

- **API 문서**: `backend/app/main.py` (BacktestResponse 클래스)
- **Frontend 구현**: `frontend/src/components/BacktestResults.jsx`
- **테스트**: `tests/test_strategies.py` (Phase 2 메타데이터 테스트)

---

## 9. 피드백 및 문의

이 마이그레이션 가이드에 대한 피드백이나 질문이 있으면 이슈를 생성해주세요.

**상태**: ✅ 완료 | **다음**: Phase 2 우선순위 3 (차트 구현)
