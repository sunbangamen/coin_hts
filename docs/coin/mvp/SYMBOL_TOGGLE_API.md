# 심볼 활성/비활성 토글 API (Phase 2)

## 개요

백테스트 결과에서 개별 심볼의 활성/비활성 상태를 동적으로 관리하기 위한 API입니다.
사용자는 프론트엔드에서 각 심볼의 체크박스를 통해 활성 여부를 토글할 수 있습니다.

**버전**: 1.0.0
**상태**: 구현 완료 (Phase 2)
**마지막 업데이트**: 2025-11-11

---

## API 엔드포인트

### PATCH /api/backtests/{run_id}/symbols/{symbol}

특정 백테스트 실행의 특정 심볼의 활성 상태를 변경합니다.

#### 요청

**메서드**: `PATCH`
**URL**: `/api/backtests/{run_id}/symbols/{symbol}`
**Content-Type**: `application/json`

**경로 파라미터**:
| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `run_id` | string | ✓ | 백테스트 실행 ID (UUID) |
| `symbol` | string | ✓ | 심볼명 (예: `BTC_KRW`, `ETH_KRW`) |

**요청 본문**:
```json
{
  "is_active": false
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `is_active` | boolean | ✓ | 심볼 활성화 여부 (true: 활성, false: 비활성) |

#### 응답

**성공 (200 OK)**:
```json
{
  "symbol": "BTC_KRW",
  "is_active": false
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `symbol` | string | 심볼명 |
| `is_active` | boolean | 변경된 활성화 여부 |

**오류 응답**:

- **404 Not Found**: run_id 또는 symbol이 존재하지 않음
  ```json
  {
    "detail": "Backtest result not found: {run_id}"
  }
  ```
  또는
  ```json
  {
    "detail": "Symbol 'XYZ_KRW' not found in backtest result"
  }
  ```

- **500 Internal Server Error**: 파일 저장 실패
  ```json
  {
    "detail": "Failed to save updated result"
  }
  ```

---

## 사용 예제

### cURL

```bash
# BTC_KRW 심볼 비활성화
curl -X PATCH http://localhost:8000/api/backtests/test-run-001/symbols/BTC_KRW \
  -H "Content-Type: application/json" \
  -d '{
    "is_active": false
  }'

# ETH_KRW 심볼 활성화
curl -X PATCH http://localhost:8000/api/backtests/test-run-001/symbols/ETH_KRW \
  -H "Content-Type: application/json" \
  -d '{
    "is_active": true
  }'
```

### Python (requests)

```python
import requests

run_id = "test-run-001"
symbol = "BTC_KRW"

response = requests.patch(
    f"http://localhost:8000/api/backtests/{run_id}/symbols/{symbol}",
    json={"is_active": False}
)

if response.status_code == 200:
    data = response.json()
    print(f"Updated {data['symbol']}: is_active={data['is_active']}")
elif response.status_code == 404:
    print(f"Not found: {response.json()['detail']}")
else:
    print(f"Error: {response.status_code}")
```

### JavaScript (fetch)

```javascript
const runId = "test-run-001";
const symbol = "BTC_KRW";

fetch(`/api/backtests/${runId}/symbols/${symbol}`, {
  method: "PATCH",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ is_active: false }),
})
  .then((response) => {
    if (response.ok) {
      return response.json();
    } else {
      throw new Error(`HTTP ${response.status}`);
    }
  })
  .then((data) => {
    console.log(`Updated ${data.symbol}: is_active=${data.is_active}`);
  })
  .catch((error) => {
    console.error("Error:", error);
  });
```

---

## 동시성 보장

이 API는 다음과 같이 동시 호출을 안전하게 처리합니다:

1. **파일 lock**: fcntl.flock()으로 쓰기 잠금을 획득
2. **임시 파일**: 변경사항을 임시 파일에 먼저 기록
3. **원자적 교체**: os.replace()로 원자적으로 파일 교체

따라서 동시에 여러 심볼에 대한 토글 요청이 들어와도 데이터가 손상되지 않습니다.

---

## 하위 호환성

이 API는 기존의 `is_active` 필드가 없는 백테스트 결과도 안전하게 처리합니다:

- 기존 결과 파일 로드 시 `is_active` 필드가 없으면 자동으로 기본값 `true`가 주입됩니다.
- 따라서 이전 버전의 결과도 이 API로 수정할 수 있습니다.

---

## 통합 워크플로우

1. **백테스트 실행**:
   ```
   POST /api/backtests/run
   ```

2. **최신 결과 조회**:
   ```
   GET /api/backtests/latest
   ```

3. **심볼 토글**:
   ```
   PATCH /api/backtests/{run_id}/symbols/BTC_KRW
   ```

4. **결과 재조회** (선택사항):
   ```
   GET /api/backtests/{run_id}
   ```

---

## 상태 코드 요약

| 상태 코드 | 의미 | 원인 |
|----------|------|------|
| 200 | 성공 | 심볼 활성 상태가 성공적으로 변경됨 |
| 404 | 찾을 수 없음 | run_id 또는 symbol이 존재하지 않음 |
| 500 | 서버 오류 | 파일 저장 중 오류 발생 |

---

## 제한사항 및 고려사항

### 현재 제한사항

- **개별 토글만 지원**: 한 번에 하나의 심볼만 변경 가능
- **전역 설정 없음**: 각 run_id별로 독립적인 활성 상태 관리 (Phase 3에서 전역 설정 추가 예정)

### 향후 확장 계획

1. **PUT /api/backtests/{run_id}/symbols** (일괄 업데이트)
   - 여러 심볼을 한 번에 업데이트

2. **GET/PUT /api/strategies/active_symbols** (전역 설정)
   - 전체 전략에 대한 기본 활성 심볼 설정

3. **필터링 강화**
   - 비활성 심볼을 자동으로 차트/테이블에서 제외

---

## 문제 해결

### 404 오류가 발생합니다

**확인 사항**:
1. `run_id`가 정확한가? → `GET /api/backtests/latest`로 최신 run_id 확인
2. `symbol`이 백테스트 결과에 포함되어 있는가? → `GET /api/backtests/{run_id}`로 심볼 목록 확인

### 변경사항이 저장되지 않습니다

**확인 사항**:
1. 응답 상태 코드가 200인가? (200이 아니면 요청 본문 확인)
2. 네트워크 연결이 정상인가?
3. 서버 로그에 오류가 있는가? → 관리자에게 문의

---

## 참고 자료

- [백테스트 API 명세](./api_spec.md)
- [시그널 뷰어 사용 가이드](./SIGNAL_VIEWER_USER_GUIDE.md)
- [Phase 2 구현 계획](./phase2_plan.md)
