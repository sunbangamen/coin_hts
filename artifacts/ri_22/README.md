# Issue #37 백테스트 워크플로 검증 아티팩트

**관련 이슈**: #37 - [Feature] 실전 백테스트 기준 타임프레임/심볼 통일화

이 디렉터리에는 백테스트 워크플로 검증 과정의 실행 결과 및 증거 자료가 저장됩니다.

## 파일 구조

```
artifacts/ri_22/
├── README.md (이 파일)
├── .gitkeep
├── workflow_validation_YYYYMMDD.log       # 전체 워크플로 실행 로그
├── step3_manual_ingest_YYYYMMDD.log       # Step 3: 수동 수집 로그 + Job ID
├── step4_parquet_validation_YYYYMMDD.json # Step 4: Parquet 파일 검증 결과
└── step5_backtest_response_YYYYMMDD.json  # Step 5: 백테스트 API 응답
```

## 파일 설명

### workflow_validation_YYYYMMDD.log
- **생성**: `scripts/run_backtest_workflow_validation.sh` 실행 시
- **내용**: Step 1~5 전체 워크플로 실행 로그
- **주요 정보**: 시간, 각 Step 결과, 오류 메시지

### step3_manual_ingest_YYYYMMDD.log
- **생성**: Step 3 수동 수집 요청
- **내용**: Job ID, 요청된 심볼/타임프레임, 상태
- **예시**:
  ```
  [2025-11-12T14:20:35.431Z] Job ID: 6004ad9c-5057-427f-bf3d-245550a624f3
  [2025-11-12T14:20:35.431Z] Symbols: KRW-BTC
  [2025-11-12T14:20:35.431Z] Timeframes: 1M
  [2025-11-12T14:20:35.431Z] Status: success
  ```

### step4_parquet_validation_YYYYMMDD.json
- **생성**: Step 4 파일 검증
- **내용**: 파일 경로, 행 수, 컬럼, 데이터 타입, 샘플 데이터
- **예시**:
  ```json
  {
    "file_path": "/data/KRW-BTC/1M/2025.parquet",
    "row_count": 1762,
    "columns": ["timestamp", "open", "high", "low", "close", "volume"],
    "dtypes": {
      "timestamp": "datetime64[ns, UTC]",
      "open": "float64",
      "close": "float64",
      "volume": "float64"
    },
    "first_row": {...},
    "last_row": {...}
  }
  ```

### step5_backtest_response_YYYYMMDD.json
- **생성**: Step 5 백테스트 실행
- **내용**: 백테스트 API 응답 (축약본)
- **예시**:
  ```json
  {
    "version": "1.1.0",
    "run_id": "b3cf36a4-dbb7-45d8-83c7-f4291098463c",
    "strategy": "volume_long_candle",
    "total_signals": 0,
    "execution_time": 0.054,
    "metadata": {
      "execution_date": "2025-11-12T05:22:56.825142Z",
      "environment": "development"
    }
  }
  ```

## 생성 및 검증 방법

### 자동 생성 (권장)
```bash
# 전체 워크플로 실행 및 로그 생성
./scripts/run_backtest_workflow_validation.sh

# 아티팩트 검증
./scripts/verify_workflow_artifacts.py
```

### 수동 생성
각 Step별로 개별 실행하고 결과를 수동으로 저장할 수 있습니다.
(자세한 방법은 docs/coin/mvp/BACKTEST_WORKFLOW_VALIDATION.md 참고)

## 주의사항

- **Parquet 파일**: 전체 파일은 git에 커밋하지 않습니다 (크기 제약). 메타데이터만 기록합니다.
- **민감 정보**: API 응답에서 민감한 정보는 제거하고 요약만 저장합니다.
- **시간대**: 모든 로그는 UTC 기준입니다.

## CI/CD 통합

GitHub Actions 등의 CI 파이프라인에서:
1. `./scripts/run_backtest_workflow_validation.sh` 실행
2. `./scripts/verify_workflow_artifacts.py` 검증
3. 아티팩트 업로드 (optional)

이를 통해 배포 전마다 워크플로가 정상 작동하는지 자동 확인할 수 있습니다.
