# Task 4.5: 통합 검증 (Integration Validation)

**목표**: Phase 4 백엔드 + 프론트엔드 완성도를 검증하고 프로덕션 준비 상태 확인

**예상 시간**: 2-3시간
**상태**: IN PROGRESS

---

## 1️⃣ 백엔드 통합 검증

### 1.1 E2E + 유닛 테스트 풀스위트

```bash
# 1단계: 테스트 실행
./scripts/run_e2e_tests.sh --with-unit

# 2단계: 결과 분석
tail -200 test_results_v3.log
docker-compose logs coin-backend | tail -100
```

**예상 결과**:
- ✅ 백엔드 유닛 테스트: 126/145 통과 (19개 기존 이슈 허용)
- ✅ E2E 통합 테스트: 8/8 통과
- ✅ Docker Compose: 정상 시작/종료

**확인 항목**:
- [ ] 유닛 테스트 결과에서 새로운 실패 없음
- [ ] 모든 E2E 시나리오 정상 통과
- [ ] 컨테이너 정상 정리
- [ ] 로그에 심각한 에러 없음

### 1.2 추가 QA 시나리오 (선택)

```bash
# 시뮬레이션 시작
curl -X POST http://localhost:8000/api/simulation/start \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["KRW-BTC", "KRW-ETH"],
    "strategies": {
      "KRW-BTC": [{"strategy_name": "volume_zone_breakout", "params": {"volume_window": 10, "top_percentile": 0.2, "breakout_buffer": 0.0}}],
      "KRW-ETH": [{"strategy_name": "volume_zone_breakout", "params": {"volume_window": 10, "top_percentile": 0.2, "breakout_buffer": 0.0}}]
    }
  }'

# 상태 확인
curl http://localhost:8000/api/simulation/status

# 포지션 조회
curl http://localhost:8000/api/simulation/positions

# 거래 이력 조회
curl http://localhost:8000/api/simulation/history

# 시뮬레이션 중지
curl -X POST http://localhost:8000/api/simulation/stop
```

**확인 항목**:
- [ ] 시뮬레이션 시작 정상 (session_id 반환)
- [ ] 상태 조회 is_running=true
- [ ] 위치션/거래 이력 응답 200 OK
- [ ] 중지 후 is_running=false

---

## 2️⃣ 프론트엔드 통합 검증

### 2.1 유닛 테스트 및 코드 품질

```bash
# 1단계: 프론트엔드 디렉토리 이동
cd frontend

# 2단계: 의존성 설치
npm install

# 3단계: Vitest 단위 테스트 실행
npm run test

# 4단계: ESLint 체크 (있으면)
npm run lint 2>/dev/null || echo "ESLint not configured"

# 5단계: 빌드 테스트
npm run build
```

**예상 결과**:
- ✅ Vitest: 14/14 통과
- ✅ npm run build: 0 에러
- ✅ 번들 크기 합리적

**확인 항목**:
- [ ] 모든 유닛 테스트 통과
- [ ] 빌드 에러 없음
- [ ] 경고 메시지 최소화
- [ ] 번들 생성 성공

### 2.2 실시간 데이터 연동 확인

```bash
# 1단계: 개발 서버 시작
npm run dev

# 2단계: http://localhost:5173 접속
# 3단계: 아래 QA 체크리스트 실행
```

**QA 체크리스트**:

| 기능 | 테스트 | 결과 |
|------|--------|------|
| **토큰 입력** | JWT 토큰 입력 → "저장 & 연결" | ☐ 통과 |
| **연결 상태** | WebSocket 연결 표시기 (✓ 인증됨) | ☐ 통과 |
| **심볼 선택** | KRW-BTC, KRW-ETH 선택 가능 | ☐ 통과 |
| **신호 스트림** | 신호 생성 시 실시간 표시 | ☐ 통과 |
| **포지션 테이블** | 포지션 진입/청산 표시 | ☐ 통과 |
| **수익 차트** | 누적 수익률 그래프 표시 | ☐ 통과 |
| **전략 제어** | 시뮬레이션 시작/중지 버튼 | ☐ 통과 |
| **REST Fallback** | WebSocket 끊을 시 REST 폴링 | ☐ 통과 |
| **자동 새로고침** | 체크박스 토글 작동 | ☐ 통과 |
| **localStorage** | 토큰 저장 및 자동 로드 | ☐ 통과 |
| **연결 복구** | 연결 끊김 → 자동 재연결 | ☐ 통과 |
| **에러 처리** | 잘못된 토큰 시 경고 표시 | ☐ 통과 |

---

## 3️⃣ 문서 및 배포 준비

### 3.1 문서 검증

```bash
# 1. 주요 문서 확인
ls -la docs/coin/mvp/ | grep -E "ri_12|testing"
cat TESTING_GUIDE.md | head -20
cat README.md | grep -A 5 "테스트"

# 2. 환경 설정 확인
cat frontend/.env.example
diff frontend/.env.example frontend/.env 2>/dev/null || echo ".env not found (ok for .gitignore)"
```

**확인 항목**:
- [ ] ri_12.md: Task 4.1-4.4 완료 표시
- [ ] TESTING_GUIDE.md: 최신 상태
- [ ] README.md: 실행 명령어 명확
- [ ] .env.example: 모든 필수 항목 포함

### 3.2 배포 준비 체크리스트

- [ ] Docker Compose: 모든 서비스 정상 시작/종료
- [ ] 환경 변수: 프로덕션용 예시 (.env.example)
- [ ] 보안: JWT 토큰 처리, CORS 설정 확인
- [ ] 로깅: 의미있는 로그 메시지
- [ ] 에러 핸들링: 사용자 친화적 메시지
- [ ] 성능: E2E 테스트 완료 시간 < 5분

---

## 4️⃣ 결과 보고 및 회고

### 4.1 실행 결과 요약

```markdown
## Phase 4 통합 검증 결과

**실행 일시**: [날짜 시간]

### 백엔드
- E2E 테스트: __/8 통과
- 유닛 테스트: __/145 통과 (기존 19개 제외)
- Docker Compose: ✅ / ❌
- 추가 QA: ✅ / ⚠️ / ❌

### 프론트엔드
- Vitest: __/14 통과
- npm run build: ✅ / ❌
- 수동 QA: __/12 통과

### 통합
- 실시간 데이터 연동: ✅ / ❌
- REST Fallback: ✅ / ❌
- 재연결 처리: ✅ / ❌

### 이슈 및 권고사항
[발견된 이슈 목록]
```

### 4.2 QA 체크리스트 완성

```bash
# 체크리스트 결과 저장
cat > QA_CHECKLIST_RESULTS.md << 'EOF'
# QA 검증 체크리스트

## 백엔드 (Task 4.1-4.3)
- [ ] 데이터 수집: WebSocket 연결 확인
- [ ] 전략 실행: BUY/SELL 신호 생성
- [ ] 포지션 관리: 진입/청산 기록
- [ ] 손익 계산: 수익률 정확성

## 프론트엔드 (Task 4.4)
- [ ] WebSocket 연결: JWT 인증 통과
- [ ] 실시간 신호: UI 업데이트
- [ ] 포지션 테이블: 최신 상태 표시
- [ ] 차트: 수익 트렌드 표시

## 통합
- [ ] 초기 로드: REST API 데이터
- [ ] 실시간: WebSocket 이벤트
- [ ] Fallback: REST 폴링 작동
- [ ] 재연결: 자동 재시도

## 문서
- [ ] 실행 가이드: 명확함
- [ ] API 문서: 완전함
- [ ] 테스트 가이드: 재현 가능함

## 배포 준비
- [ ] 환경 변수: 명확함
- [ ] 보안: 적절함
- [ ] 로깅: 충분함
- [ ] 에러 처리: 사용자 친화적
EOF

cat QA_CHECKLIST_RESULTS.md
```

### 4.3 다음 스텝 제안

```
## Phase 4 검증 완료 후 다음 액션

### 즉시 (1주일)
1. [ ] 성능 측정
   - E2E 테스트 완료 시간
   - WebSocket 메시지 처리량
   - 메모리/CPU 사용률

2. [ ] 보안 검토
   - JWT 토큰 만료 처리
   - CORS 정책 검증
   - 입력 검증 확인

### 단기 (2-4주)
1. [ ] 프로덕션 배포 준비
   - CI/CD 파이프라인 구성
   - 환경별 설정 분리
   - 모니터링 대시보드 구성

2. [ ] 운영 인수인계
   - 배포 가이드 작성
   - 트러블슈팅 매뉴얼
   - 성과 지표 정의

### 중기 (1-3개월)
1. [ ] 추가 기능
   - 레버리지 거래
   - 수익/손실 알림
   - 성과 분석 보고서

2. [ ] 최적화
   - 프론트엔드 번들 크기
   - 백엔드 응답 시간
   - 데이터베이스 쿼리
```

---

## 📋 실행 예시

```bash
# 1. 전체 프로세스 자동 실행
echo "=== Phase 4 통합 검증 시작 ===" && \
echo "1. 백엔드 E2E 테스트" && \
./scripts/run_e2e_tests.sh --with-unit && \
echo "2. 프론트엔드 테스트" && \
cd frontend && npm install && npm run test && npm run build && cd .. && \
echo "=== 검증 완료 ===" && \
echo "결과: test_results_v3.log 확인"

# 2. 수동 QA 시나리오 (선택)
# 별도의 터미널에서:
# npm run dev (프론트엔드)
# 브라우저로 http://localhost:5173 접속
# 위의 QA 체크리스트 항목 확인
```

---

## 🎯 완료 기준

✅ **모두 통과**: Phase 4 완료로 간주
- 백엔드 E2E: 8/8 통과
- 백엔드 유닛: 126+/145 통과 (19개 기존 이슈 제외)
- 프론트엔드 Vitest: 14/14 통과
- 프론트엔드 빌드: 성공
- 수동 QA: 12/12 항목 통과

⚠️ **부분 통과**: 이슈 수정 후 재검증
- E2E 실패 항목 확인
- 새로운 유닛 테스트 실패 (19개 기존 제외)
- QA 실패 항목 < 3개

❌ **불통과**: 원인 분석 및 수정 필요
- E2E 2개 이상 실패
- 새로운 유닛 테스트 실패 > 3개
- QA 실패 항목 >= 4개

---

## 📞 문제 해결

### 백엔드 문제
```bash
# 1. Docker 컨테이너 상태 확인
docker-compose ps

# 2. 로그 확인
docker-compose logs backend | tail -50

# 3. 컨테이너 재시작
docker-compose down --remove-orphans && docker-compose up -d
```

### 프론트엔드 문제
```bash
# 1. npm 캐시 정리
rm -rf node_modules package-lock.json
npm install

# 2. Vitest 상세 로그
npm run test -- --reporter=verbose

# 3. 개발 서버 디버그
npm run dev -- --debug
```

---

**최종 업데이트**: 2025-11-05
**상태**: 검증 절차 준비 완료
