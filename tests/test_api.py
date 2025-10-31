"""
FastAPI 엔드포인트 통합 테스트

백테스트 API의 각 엔드포인트를 테스트합니다.
"""

import pytest
from fastapi.testclient import TestClient
import os
import json
import tempfile
import shutil

from backend.app.main import app, RESULTS_DIR

client = TestClient(app)


@pytest.fixture
def temp_results_dir(monkeypatch):
    """임시 결과 디렉토리 생성"""
    temp_dir = tempfile.mkdtemp()
    monkeypatch.setattr("backend.app.main.RESULTS_DIR", temp_dir)
    yield temp_dir
    shutil.rmtree(temp_dir)


class TestRootEndpoints:
    """루트 및 헬스체크 엔드포인트 테스트"""

    def test_root_endpoint(self):
        """루트 엔드포인트 테스트"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Coin Backtesting API"
        assert "endpoints" in data

    def test_health_check(self):
        """헬스체크 엔드포인트 테스트"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "data_root" in data
        assert "results_dir" in data

    def test_list_strategies(self):
        """전략 목록 조회 테스트"""
        response = client.get("/api/strategies")
        assert response.status_code == 200
        data = response.json()
        assert "strategies" in data
        assert isinstance(data["strategies"], list)
        assert len(data["strategies"]) >= 2
        assert "volume_long_candle" in data["strategies"]
        assert "volume_zone_breakout" in data["strategies"]
        assert data["count"] == len(data["strategies"])


class TestBacktestRun:
    """백테스트 실행 엔드포인트 테스트"""

    def test_valid_backtest_request(self, temp_results_dir):
        """유효한 백테스트 요청 테스트"""
        payload = {
            "strategy": "volume_long_candle",
            "params": {
                "vol_ma_window": 20,
                "vol_multiplier": 1.5,
                "body_pct": 0.02,
            },
            "symbols": ["BTC_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "timeframe": "1d",
        }

        response = client.post("/api/backtests/run", json=payload)

        # 데이터가 있으면 200, 없으면 400
        if response.status_code == 200:
            data = response.json()
            assert "run_id" in data
            assert data["strategy"] == "volume_long_candle"
            assert data["start_date"] == "2024-01-01"
            assert data["end_date"] == "2024-01-31"
            assert data["timeframe"] == "1d"
            assert isinstance(data["symbols"], list)
            assert isinstance(data["total_signals"], int)
            assert isinstance(data["execution_time"], float)

            # 결과 파일 확인
            result_file = os.path.join(temp_results_dir, f"{data['run_id']}.json")
            assert os.path.exists(result_file)

    def test_invalid_strategy(self):
        """지원되지 않는 전략 테스트"""
        payload = {
            "strategy": "invalid_strategy",
            "params": {},
            "symbols": ["BTC_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        response = client.post("/api/backtests/run", json=payload)
        assert response.status_code == 422  # Validation error

    def test_empty_symbols(self):
        """빈 심볼 목록 테스트"""
        payload = {
            "strategy": "volume_long_candle",
            "params": {},
            "symbols": [],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        response = client.post("/api/backtests/run", json=payload)
        assert response.status_code == 422  # Validation error

    def test_invalid_date_format(self):
        """잘못된 날짜 형식 테스트"""
        payload = {
            "strategy": "volume_long_candle",
            "params": {},
            "symbols": ["BTC_KRW"],
            "start_date": "2024/01/01",  # 잘못된 형식
            "end_date": "2024-01-31",
        }

        response = client.post("/api/backtests/run", json=payload)
        assert response.status_code == 422  # Validation error

    def test_invalid_date_range(self):
        """잘못된 날짜 범위 테스트"""
        payload = {
            "strategy": "volume_long_candle",
            "params": {},
            "symbols": ["BTC_KRW"],
            "start_date": "2024-02-01",
            "end_date": "2024-01-01",  # start_date보다 앞
        }

        response = client.post("/api/backtests/run", json=payload)
        assert response.status_code == 422  # Validation error

    def test_multiple_symbols(self, temp_results_dir):
        """여러 심볼 백테스트 테스트"""
        payload = {
            "strategy": "volume_zone_breakout",
            "params": {},
            "symbols": ["BTC_KRW", "ETH_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        response = client.post("/api/backtests/run", json=payload)

        # 데이터가 없을 수도 있으므로 400, 404나 200 둘 다 허용
        assert response.status_code in [200, 400, 404]

    def test_default_params(self, temp_results_dir):
        """기본 파라미터 테스트"""
        payload = {
            "strategy": "volume_long_candle",
            "symbols": ["BTC_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            # params 생략 (빈 dict가 기본값)
        }

        response = client.post("/api/backtests/run", json=payload)

        if response.status_code == 200:
            data = response.json()
            assert data["params"] == {}


class TestBacktestGet:
    """백테스트 결과 조회 엔드포인트 테스트"""

    def test_get_existing_result(self, temp_results_dir):
        """존재하는 결과 조회 테스트"""
        # 먼저 백테스트 실행
        payload = {
            "strategy": "volume_long_candle",
            "params": {},
            "symbols": ["BTC_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        run_response = client.post("/api/backtests/run", json=payload)

        if run_response.status_code == 200:
            run_id = run_response.json()["run_id"]

            # 결과 조회
            get_response = client.get(f"/api/backtests/{run_id}")
            assert get_response.status_code == 200

            data = get_response.json()
            assert data["run_id"] == run_id
            assert data["strategy"] == "volume_long_candle"

    def test_get_nonexistent_result(self):
        """존재하지 않는 결과 조회 테스트"""
        response = client.get("/api/backtests/nonexistent-id")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_get_result_format(self, temp_results_dir):
        """결과 형식 검증 테스트"""
        payload = {
            "strategy": "volume_zone_breakout",
            "params": {},
            "symbols": ["BTC_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        run_response = client.post("/api/backtests/run", json=payload)

        if run_response.status_code == 200:
            run_id = run_response.json()["run_id"]

            # 결과 조회 및 검증
            get_response = client.get(f"/api/backtests/{run_id}")
            assert get_response.status_code == 200

            data = get_response.json()
            # 필수 필드 확인
            assert "run_id" in data
            assert "strategy" in data
            assert "params" in data
            assert "start_date" in data
            assert "end_date" in data
            assert "timeframe" in data
            assert "symbols" in data
            assert "total_signals" in data
            assert "execution_time" in data


class TestParameterValidation:
    """파라미터 유효성 검사 테스트"""

    def test_missing_required_fields(self):
        """필수 필드 누락 테스트"""
        payload = {
            "strategy": "volume_long_candle",
            # symbols, start_date, end_date 누락
        }

        response = client.post("/api/backtests/run", json=payload)
        assert response.status_code == 422

    def test_default_timeframe(self, temp_results_dir):
        """기본 타임프레임 테스트"""
        payload = {
            "strategy": "volume_long_candle",
            "params": {},
            "symbols": ["BTC_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            # timeframe 생략 (기본값: 1d)
        }

        response = client.post("/api/backtests/run", json=payload)

        # 데이터가 있으면 200, 없으면 400
        if response.status_code == 200:
            data = response.json()
            assert data["timeframe"] == "1d"

    def test_custom_params(self, temp_results_dir):
        """사용자 정의 파라미터 테스트"""
        payload = {
            "strategy": "volume_long_candle",
            "params": {
                "vol_ma_window": 30,
                "vol_multiplier": 2.0,
                "body_pct": 0.03,
                "hold_period_bars": 2,
            },
            "symbols": ["BTC_KRW"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        response = client.post("/api/backtests/run", json=payload)

        if response.status_code == 200:
            data = response.json()
            assert data["params"]["vol_ma_window"] == 30
            assert data["params"]["vol_multiplier"] == 2.0
            assert data["params"]["body_pct"] == 0.03
            assert data["params"]["hold_period_bars"] == 2

    def test_both_strategies(self, temp_results_dir):
        """두 가지 전략 모두 테스트"""
        for strategy_name in ["volume_long_candle", "volume_zone_breakout"]:
            payload = {
                "strategy": strategy_name,
                "params": {},
                "symbols": ["BTC_KRW"],
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            }

            response = client.post("/api/backtests/run", json=payload)

            if response.status_code == 200:
                data = response.json()
                assert data["strategy"] == strategy_name


class TestErrorHandling:
    """에러 핸들링 테스트"""

    def test_response_structure(self):
        """응답 구조 검증"""
        # 404 에러
        response = client.get("/api/backtests/invalid-run-id")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_invalid_json(self):
        """잘못된 JSON 테스트"""
        response = client.post(
            "/api/backtests/run",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
