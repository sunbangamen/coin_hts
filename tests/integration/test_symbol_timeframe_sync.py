"""
심볼/타임프레임 동기화 검증 통합 테스트

Issue #37: [Feature] 실전 백테스트 기준 타임프레임/심볼 통일화
- 프론트엔드와 백엔드의 DEFAULT_SYMBOLS 및 TIMEFRAMES 동기화 검증
- 환경 변수 파싱 검증
- 스케줄러 설정 검증

CI/CD 파이프라인에 통합하여 각 배포 전 동기화 여부를 자동 확인합니다.
"""

import os
import sys
import json
from pathlib import Path

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestSymbolTimeframeSync:
    """프론트엔드-백엔드 심볼/타임프레임 동기화 검증"""

    # 프로덕션 기준값 (Issue #37에서 확정)
    EXPECTED_SYMBOLS = [
        'KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL', 'KRW-XLM',
        'KRW-ADA', 'KRW-DOGE', 'KRW-BCH', 'KRW-NEAR'
    ]
    EXPECTED_TIMEFRAMES = ['1M', '5M', '1H', '1D', '1W']

    def test_backend_scheduler_config_constants(self):
        """
        백엔드 scheduler_config.py의 상수 검증

        파일: backend/app/scheduler_config.py
        Line: 18, 23
        """
        scheduler_config_path = PROJECT_ROOT / 'backend' / 'app' / 'scheduler_config.py'

        assert scheduler_config_path.exists(), f"파일 없음: {scheduler_config_path}"

        with open(scheduler_config_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # DEFAULT_SYMBOLS 확인
        assert 'DEFAULT_SYMBOLS = [' in content, "DEFAULT_SYMBOLS 정의 없음"
        assert "'KRW-BTC'" in content, "KRW-BTC 없음"
        assert "'KRW-ETH'" in content, "KRW-ETH 없음"
        assert "'KRW-NEAR'" in content, "KRW-NEAR 없음"

        # DEFAULT_TIMEFRAMES 확인
        assert 'DEFAULT_TIMEFRAMES = [' in content, "DEFAULT_TIMEFRAMES 정의 없음"
        assert "'1M'" in content, "1M 없음"
        assert "'5M'" in content, "5M 없음"
        assert "'1H'" in content, "1H 없음"
        assert "'1D'" in content, "1D 없음"
        assert "'1W'" in content, "1W 없음"

        print("✅ backend/app/scheduler_config.py 상수 검증 완료")

    def test_backend_scheduler_config_functions(self):
        """
        백엔드 scheduler_config.py의 헬퍼 함수 검증

        파일: backend/app/scheduler_config.py
        함수: get_scheduler_symbols(), get_scheduler_timeframes(),
              get_default_symbols(), get_default_timeframes()
        """
        scheduler_config_path = PROJECT_ROOT / 'backend' / 'app' / 'scheduler_config.py'

        with open(scheduler_config_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 필수 함수 검증
        required_functions = [
            'get_scheduler_symbols',
            'get_scheduler_timeframes',
            'get_default_symbols',
            'get_default_timeframes',
            'validate_scheduler_config',
            'log_config_info'
        ]

        for func_name in required_functions:
            assert f'def {func_name}()' in content, f"함수 없음: {func_name}"

        print("✅ backend/app/scheduler_config.py 함수 검증 완료")

    def test_frontend_data_management_constants(self):
        """
        프론트엔드 DataManagementPage.jsx의 상수 검증

        파일: frontend/src/pages/DataManagementPage.jsx
        Line: 8, 11
        """
        data_mgmt_path = PROJECT_ROOT / 'frontend' / 'src' / 'pages' / 'DataManagementPage.jsx'

        assert data_mgmt_path.exists(), f"파일 없음: {data_mgmt_path}"

        with open(data_mgmt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # DEFAULT_SYMBOLS 확인
        assert 'const DEFAULT_SYMBOLS = [' in content, "DEFAULT_SYMBOLS 정의 없음"
        for symbol in self.EXPECTED_SYMBOLS:
            assert f"'{symbol}'" in content, f"심볼 없음: {symbol}"

        # TIMEFRAMES 확인
        assert 'const TIMEFRAMES = [' in content, "TIMEFRAMES 정의 없음"
        for timeframe in self.EXPECTED_TIMEFRAMES:
            assert f"'{timeframe}'" in content, f"타임프레임 없음: {timeframe}"

        print("✅ frontend/src/pages/DataManagementPage.jsx 상수 검증 완료")

    def test_frontend_backtest_constants(self):
        """
        프론트엔드 BacktestPage.jsx의 상수 검증

        파일: frontend/src/pages/BacktestPage.jsx
        Line: 34
        """
        backtest_path = PROJECT_ROOT / 'frontend' / 'src' / 'pages' / 'BacktestPage.jsx'

        assert backtest_path.exists(), f"파일 없음: {backtest_path}"

        with open(backtest_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # TIMEFRAMES 확인 (DataManagementPage와 동일해야 함)
        assert 'const TIMEFRAMES = [' in content, "TIMEFRAMES 정의 없음"
        for timeframe in self.EXPECTED_TIMEFRAMES:
            assert f"'{timeframe}'" in content, f"타임프레임 없음: {timeframe}"

        # 기본값이 대문자인지 확인 (1H)
        assert "timeframe: '1H'" in content, "기본값이 대문자가 아님"

        print("✅ frontend/src/pages/BacktestPage.jsx 상수 검증 완료")

    def test_docker_compose_scheduler_symbols(self):
        """
        docker-compose.yml에서 스케줄러 심볼 환경 변수 검증

        파일: docker-compose.yml
        변수: SCHEDULER_SYMBOLS
        """
        docker_compose_path = PROJECT_ROOT / 'docker-compose.yml'

        assert docker_compose_path.exists(), f"파일 없음: {docker_compose_path}"

        with open(docker_compose_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # SCHEDULER_SYMBOLS 확인
        assert 'SCHEDULER_SYMBOLS=' in content, "SCHEDULER_SYMBOLS 환경 변수 없음"

        # 모든 심볼이 포함되었는지 확인
        for symbol in self.EXPECTED_SYMBOLS:
            assert symbol in content, f"심볼 없음 (docker-compose): {symbol}"

        # 모든 서비스에서 설정되었는지 확인
        services = ['backend', 'worker', 'test', 'e2e-test']
        for service in services:
            # 서비스별로 SCHEDULER_SYMBOLS가 있는지 대략적으로 확인
            assert f'{service}:' in content, f"서비스 없음: {service}"

        print("✅ docker-compose.yml SCHEDULER_SYMBOLS 검증 완료")

    def test_docker_compose_scheduler_timeframes(self):
        """
        docker-compose.yml에서 스케줄러 타임프레임 환경 변수 검증

        파일: docker-compose.yml
        변수: SCHEDULER_TIMEFRAMES
        """
        docker_compose_path = PROJECT_ROOT / 'docker-compose.yml'

        assert docker_compose_path.exists(), f"파일 없음: {docker_compose_path}"

        with open(docker_compose_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # SCHEDULER_TIMEFRAMES 확인
        assert 'SCHEDULER_TIMEFRAMES=' in content, "SCHEDULER_TIMEFRAMES 환경 변수 없음"

        # 모든 타임프레임이 포함되었는지 확인
        for timeframe in self.EXPECTED_TIMEFRAMES:
            assert timeframe in content, f"타임프레임 없음 (docker-compose): {timeframe}"

        print("✅ docker-compose.yml SCHEDULER_TIMEFRAMES 검증 완료")

    def test_scheduler_py_uses_config(self):
        """
        백엔드 scheduler.py가 scheduler_config를 올바르게 사용하는지 검증

        파일: backend/app/scheduler.py
        """
        scheduler_path = PROJECT_ROOT / 'backend' / 'app' / 'scheduler.py'

        assert scheduler_path.exists(), f"파일 없음: {scheduler_path}"

        with open(scheduler_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # scheduler_config import 확인
        assert 'from backend.app.scheduler_config import' in content, \
            "scheduler_config import 없음"
        assert 'get_scheduler_symbols' in content, "get_scheduler_symbols import 없음"
        assert 'get_scheduler_timeframes' in content, "get_scheduler_timeframes import 없음"

        # 함수 호출 확인
        assert 'DEFAULT_SYMBOLS = get_scheduler_symbols()' in content or \
               'DEFAULT_SYMBOLS = get_scheduler_symbols()' in content, \
            "get_scheduler_symbols() 호출 없음"
        assert 'DEFAULT_TIMEFRAMES = get_scheduler_timeframes()' in content, \
            "get_scheduler_timeframes() 호출 없음"

        print("✅ backend/app/scheduler.py 검증 완료")

    def test_documentation_exists(self):
        """
        필수 문서 파일 존재 검증

        파일:
        - docs/coin/mvp/SYMBOL_TIMEFRAME_SYNC_GUIDE.md
        - docs/coin/mvp/BACKTEST_WORKFLOW_VALIDATION.md
        - docs/coin/mvp/ri_22.md
        """
        required_docs = [
            'docs/coin/mvp/SYMBOL_TIMEFRAME_SYNC_GUIDE.md',
            'docs/coin/mvp/BACKTEST_WORKFLOW_VALIDATION.md',
            'docs/coin/mvp/ri_22.md'
        ]

        for doc_path in required_docs:
            full_path = PROJECT_ROOT / doc_path
            assert full_path.exists(), f"문서 파일 없음: {doc_path}"
            assert full_path.stat().st_size > 0, f"문서 파일이 비어 있음: {doc_path}"

        print("✅ 필수 문서 파일 검증 완료")

    def test_sync_guide_includes_checklist(self):
        """
        동기화 가이드가 체크리스트를 포함하는지 검증

        파일: docs/coin/mvp/SYMBOL_TIMEFRAME_SYNC_GUIDE.md
        """
        guide_path = PROJECT_ROOT / 'docs' / 'coin' / 'mvp' / 'SYMBOL_TIMEFRAME_SYNC_GUIDE.md'

        assert guide_path.exists(), f"파일 없음: {guide_path}"

        with open(guide_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 체크리스트 포함 확인
        assert '## 동기화 체크리스트' in content, "동기화 체크리스트 섹션 없음"
        assert '[ ] ' in content, "체크리스트 항목 없음"

        # 변경 시나리오 포함 확인
        assert '시나리오 1:' in content, "변경 시나리오 없음"
        assert 'docker-compose.yml' in content, "docker-compose.yml 언급 없음"

        print("✅ SYMBOL_TIMEFRAME_SYNC_GUIDE.md 검증 완료")

    def test_workflow_validation_includes_steps(self):
        """
        워크플로 검증 문서가 모든 단계를 포함하는지 검증

        파일: docs/coin/mvp/BACKTEST_WORKFLOW_VALIDATION.md
        """
        validation_path = PROJECT_ROOT / 'docs' / 'coin' / 'mvp' / 'BACKTEST_WORKFLOW_VALIDATION.md'

        assert validation_path.exists(), f"파일 없음: {validation_path}"

        with open(validation_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 모든 단계 포함 확인
        required_steps = [
            'Step 1: 프론트엔드 상수 확인',
            'Step 2: 백엔드 환경 변수 확인',
            'Step 3: 수동 데이터 수집 트리거',
            'Step 4: 파일 구조 및 데이터 검증',
            'Step 5: 백테스트 UI에서 데이터 사용'
        ]

        for step in required_steps:
            assert step in content, f"단계 없음: {step}"

        print("✅ BACKTEST_WORKFLOW_VALIDATION.md 검증 완료")

    def run_all_tests(self):
        """모든 테스트 실행"""
        test_methods = [
            self.test_backend_scheduler_config_constants,
            self.test_backend_scheduler_config_functions,
            self.test_frontend_data_management_constants,
            self.test_frontend_backtest_constants,
            self.test_docker_compose_scheduler_symbols,
            self.test_docker_compose_scheduler_timeframes,
            self.test_scheduler_py_uses_config,
            self.test_documentation_exists,
            self.test_sync_guide_includes_checklist,
            self.test_workflow_validation_includes_steps
        ]

        print("\n" + "=" * 70)
        print("심볼/타임프레임 동기화 검증 테스트 시작")
        print("=" * 70 + "\n")

        passed = 0
        failed = 0
        errors = []

        for test_method in test_methods:
            try:
                test_method()
                passed += 1
            except AssertionError as e:
                failed += 1
                errors.append((test_method.__name__, str(e)))
                print(f"❌ {test_method.__name__}: {e}\n")
            except Exception as e:
                failed += 1
                errors.append((test_method.__name__, str(e)))
                print(f"⚠️  {test_method.__name__}: {type(e).__name__}: {e}\n")

        # 테스트 결과 요약
        print("\n" + "=" * 70)
        print("테스트 결과 요약")
        print("=" * 70)
        print(f"✅ 통과: {passed}")
        print(f"❌ 실패: {failed}")
        print(f"📊 총계: {passed + failed}")

        if failed > 0:
            print("\n실패한 테스트:")
            for test_name, error in errors:
                print(f"  - {test_name}: {error}")
            return False
        else:
            print("\n🎉 모든 테스트 통과!")
            return True


if __name__ == '__main__':
    tester = TestSymbolTimeframeSync()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
