# Coin Trading MVP · Phase Plan

## Phase 0. MVP Kickoff
- FastAPI + React 스캐폴딩 생성, Docker Compose(`web`, `api`) 기본 구성.
- `DATA_ROOT` 환경 변수 정의, 로컬 `./data` 볼륨 마운트 확인.
- 샘플 전략 설정/결과 JSON을 수동으로 저장해 API/프론트 파이프라인 흐름 검증.

## Phase 1. 전략 입력 & 백테스트 실행
- 전략 목록(`volume_long_candle`, `volume_zone_breakout`)과 파라미터 프리셋을 React 폼으로 노출.
- FastAPI에서 로컬 parquet 데이터를 읽어 동기 백테스트 실행 → 결과 JSON 생성.
- 결과 지표(승률, 평균 수익률, 최대 낙폭, 샘플 수, 신호 목록)를 React 테이블/차트로 표현.
- 실행 로그/결과 JSON을 `DATA_ROOT/results`에 기록하고, UI에서 가장 최근 실행 내역을 조회.

## Phase 2. 시그널 뷰어 & 관리
- FastAPI에 최신 실행 결과 요약/디테일 조회 API 추가.
- React에서 폴링 기반 시그널 뷰어 구현, 심볼별 활성/비활성 토글 UI 제공.
- 전략 설정, 실행 히스토리를 `DATA_ROOT/strategies` 등 파일로 관리하고 다운로드 가능하도록 지원.

## Phase 3. 운영 보완
- 장시간 실행 대비 비동기 태스크 큐(예: Celery/RQ) 설계 초안 마련, 적용 시나리오 정의.
- Docker Compose로 외부 스토리지(`/data`, 원드라이브 마운트 등) 전환 테스트.
- README/운영 가이드 작성, 마이그레이션 체크리스트(데이터 이전, 환경 변수 설정, 보안 항목) 정리.
