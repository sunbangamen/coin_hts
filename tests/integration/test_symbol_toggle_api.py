"""
심볼 토글 API 통합 테스트 (Phase 2)

PATCH /api/backtests/{run_id}/symbols/{symbol} 엔드포인트를 검증합니다.
동시성, 에러 처리, 데이터 무결성 등을 테스트합니다.
"""

import pytest
import json
import tempfile
import os
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.result_manager import ResultManager


@pytest.fixture
def client():
    """FastAPI 테스트 클라이언트"""
    return TestClient(app)


@pytest.fixture
def temp_data_root(monkeypatch):
    """임시 데이터 디렉토리 및 환경변수 설정"""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("DATA_ROOT", tmpdir)
        # 모듈 레벨에서 DATA_ROOT를 재로드하기 위해 app의 전역 변수 직접 수정
        import backend.app.main
        original_data_root = backend.app.main.DATA_ROOT
        backend.app.main.DATA_ROOT = tmpdir
        yield tmpdir
        # 복원
        backend.app.main.DATA_ROOT = original_data_root


@pytest.fixture
def sample_backtest_result():
    """샘플 백테스트 결과"""
    return {
        "version": "1.1.0",
        "run_id": "test-toggle-001",
        "strategy": "volume_zone_breakout",
        "params": {"volume_window": 10, "top_percentile": 0.2, "breakout_buffer": 0.0},
        "start_date": "2025-01-01",
        "end_date": "2025-01-31",
        "timeframe": "1d",
        "symbols": [
            {
                "symbol": "BTC_KRW",
                "is_active": True,
                "signals": [],
                "win_rate": 0.55,
                "avg_return": 2.5,
                "max_drawdown": -5.0,
                "avg_hold_bars": 5.0,
            },
            {
                "symbol": "ETH_KRW",
                "is_active": True,
                "signals": [],
                "win_rate": 0.45,
                "avg_return": 1.5,
                "max_drawdown": -3.0,
                "avg_hold_bars": 3.0,
            },
            {
                "symbol": "XRP_KRW",
                "is_active": True,
                "signals": [],
                "win_rate": 0.50,
                "avg_return": 0.5,
                "max_drawdown": -2.0,
                "avg_hold_bars": 4.0,
            },
        ],
        "total_signals": 100,
        "execution_time": 10.5,
    }


class TestSymbolToggleBasic:
    """심볼 토글 기본 기능 테스트"""

    def test_toggle_symbol_to_inactive(self, client, temp_data_root, sample_backtest_result):
        """심볼을 활성에서 비활성으로 변경"""
        # 1. 샘플 결과 저장
        run_id = "test-toggle-001"
        ResultManager.save_result(temp_data_root, run_id, sample_backtest_result)

        # 2. BTC_KRW 비활성화
        response = client.patch(
            f"/api/backtests/{run_id}/symbols/BTC_KRW",
            json={"is_active": False},
        )

        # 3. 응답 검증
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTC_KRW"
        assert data["is_active"] is False

        # 4. 파일에서 변경사항 확인
        updated_result = ResultManager.get_result(temp_data_root, run_id)
        btc_symbol = next((s for s in updated_result["symbols"] if s["symbol"] == "BTC_KRW"), None)
        assert btc_symbol is not None
        assert btc_symbol["is_active"] is False

    def test_toggle_symbol_to_active(self, client, temp_data_root, sample_backtest_result):
        """심볼을 비활성에서 활성으로 변경"""
        # 1. 초기값을 비활성으로 설정
        sample_backtest_result["symbols"][0]["is_active"] = False
        run_id = "test-toggle-002"
        ResultManager.save_result(temp_data_root, run_id, sample_backtest_result)

        # 2. BTC_KRW 활성화
        response = client.patch(
            f"/api/backtests/{run_id}/symbols/BTC_KRW",
            json={"is_active": True},
        )

        # 3. 응답 검증
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTC_KRW"
        assert data["is_active"] is True

    def test_toggle_multiple_symbols_sequentially(self, client, temp_data_root, sample_backtest_result):
        """여러 심볼을 순차적으로 변경"""
        run_id = "test-toggle-003"
        ResultManager.save_result(temp_data_root, run_id, sample_backtest_result)

        # BTC_KRW 비활성화
        response1 = client.patch(
            f"/api/backtests/{run_id}/symbols/BTC_KRW",
            json={"is_active": False},
        )
        assert response1.status_code == 200

        # ETH_KRW 비활성화
        response2 = client.patch(
            f"/api/backtests/{run_id}/symbols/ETH_KRW",
            json={"is_active": False},
        )
        assert response2.status_code == 200

        # XRP_KRW 활성 유지
        response3 = client.patch(
            f"/api/backtests/{run_id}/symbols/XRP_KRW",
            json={"is_active": True},
        )
        assert response3.status_code == 200

        # 최종 상태 검증
        updated_result = ResultManager.get_result(temp_data_root, run_id)
        assert updated_result["symbols"][0]["is_active"] is False  # BTC_KRW
        assert updated_result["symbols"][1]["is_active"] is False  # ETH_KRW
        assert updated_result["symbols"][2]["is_active"] is True   # XRP_KRW


class TestSymbolToggleErrorHandling:
    """에러 처리 테스트"""

    def test_toggle_nonexistent_run_id(self, client, temp_data_root):
        """존재하지 않는 run_id에 대한 토글 시도"""
        response = client.patch(
            "/api/backtests/nonexistent-run/symbols/BTC_KRW",
            json={"is_active": False},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_toggle_nonexistent_symbol(self, client, temp_data_root, sample_backtest_result):
        """존재하지 않는 심볼에 대한 토글 시도"""
        run_id = "test-toggle-004"
        ResultManager.save_result(temp_data_root, run_id, sample_backtest_result)

        response = client.patch(
            f"/api/backtests/{run_id}/symbols/UNKNOWN_KRW",
            json={"is_active": False},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_toggle_with_invalid_json(self, client, temp_data_root, sample_backtest_result):
        """잘못된 JSON 형식으로 토글 시도"""
        run_id = "test-toggle-005"
        ResultManager.save_result(temp_data_root, run_id, sample_backtest_result)

        response = client.patch(
            f"/api/backtests/{run_id}/symbols/BTC_KRW",
            json={"invalid_field": "value"},  # is_active 필드 누락
        )

        # Pydantic 검증 오류로 422 반환
        assert response.status_code == 422


class TestSymbolToggleDataIntegrity:
    """데이터 무결성 테스트"""

    def test_toggle_preserves_other_symbols(self, client, temp_data_root, sample_backtest_result):
        """한 심볼 변경 시 다른 심볼 데이터 보존"""
        run_id = "test-toggle-006"
        ResultManager.save_result(temp_data_root, run_id, sample_backtest_result)

        original_eth = next((s for s in sample_backtest_result["symbols"] if s["symbol"] == "ETH_KRW"), None)

        # BTC_KRW만 변경
        client.patch(
            f"/api/backtests/{run_id}/symbols/BTC_KRW",
            json={"is_active": False},
        )

        # ETH_KRW가 변경되지 않았는지 확인
        updated_result = ResultManager.get_result(temp_data_root, run_id)
        updated_eth = next((s for s in updated_result["symbols"] if s["symbol"] == "ETH_KRW"), None)

        assert updated_eth["win_rate"] == original_eth["win_rate"]
        assert updated_eth["avg_return"] == original_eth["avg_return"]
        assert updated_eth["is_active"] == original_eth["is_active"]

    def test_toggle_preserves_other_fields(self, client, temp_data_root, sample_backtest_result):
        """심볼 토글 시 다른 필드 보존"""
        run_id = "test-toggle-007"
        ResultManager.save_result(temp_data_root, run_id, sample_backtest_result)

        original_btc = next((s for s in sample_backtest_result["symbols"] if s["symbol"] == "BTC_KRW"), None)

        # BTC_KRW 비활성화
        client.patch(
            f"/api/backtests/{run_id}/symbols/BTC_KRW",
            json={"is_active": False},
        )

        # BTC_KRW의 다른 필드가 보존되었는지 확인
        updated_result = ResultManager.get_result(temp_data_root, run_id)
        updated_btc = next((s for s in updated_result["symbols"] if s["symbol"] == "BTC_KRW"), None)

        assert updated_btc["symbol"] == original_btc["symbol"]
        assert updated_btc["win_rate"] == original_btc["win_rate"]
        assert updated_btc["avg_return"] == original_btc["avg_return"]
        assert updated_btc["max_drawdown"] == original_btc["max_drawdown"]
        assert updated_btc["avg_hold_bars"] == original_btc["avg_hold_bars"]
        assert len(updated_btc["signals"]) == len(original_btc["signals"])

    def test_toggle_preserves_result_metadata(self, client, temp_data_root, sample_backtest_result):
        """결과의 메타데이터 보존"""
        run_id = "test-toggle-008"
        ResultManager.save_result(temp_data_root, run_id, sample_backtest_result)

        original_metadata = {
            "version": sample_backtest_result["version"],
            "strategy": sample_backtest_result["strategy"],
            "start_date": sample_backtest_result["start_date"],
            "end_date": sample_backtest_result["end_date"],
            "total_signals": sample_backtest_result["total_signals"],
        }

        # 심볼 변경
        client.patch(
            f"/api/backtests/{run_id}/symbols/BTC_KRW",
            json={"is_active": False},
        )

        # 메타데이터 검증
        updated_result = ResultManager.get_result(temp_data_root, run_id)
        assert updated_result["version"] == original_metadata["version"]
        assert updated_result["strategy"] == original_metadata["strategy"]
        assert updated_result["start_date"] == original_metadata["start_date"]
        assert updated_result["end_date"] == original_metadata["end_date"]
        assert updated_result["total_signals"] == original_metadata["total_signals"]


class TestSymbolToggleLegacyCompat:
    """레거시 호환성 테스트 (Phase 2)"""

    def test_toggle_legacy_result_without_is_active(self, client, temp_data_root):
        """is_active 필드가 없는 레거시 결과에 대한 토글"""
        # 레거시 결과 (is_active 필드 없음)
        legacy_result = {
            "version": "1.0.0",
            "run_id": "test-legacy-001",
            "strategy": "volume_zone_breakout",
            "params": {},
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "timeframe": "1d",
            "symbols": [
                {
                    "symbol": "BTC_KRW",
                    # is_active 필드 없음
                    "signals": [],
                    "win_rate": 0.55,
                    "avg_return": 2.5,
                    "max_drawdown": -5.0,
                    "avg_hold_bars": 5.0,
                },
            ],
            "total_signals": 100,
            "execution_time": 10.5,
        }

        run_id = "test-legacy-001"
        ResultManager.save_result(temp_data_root, run_id, legacy_result)

        # 레거시 결과에 대한 토글
        response = client.patch(
            f"/api/backtests/{run_id}/symbols/BTC_KRW",
            json={"is_active": False},
        )

        # 토글이 성공해야 함
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTC_KRW"
        assert data["is_active"] is False

        # 저장된 결과에서 is_active가 추가되어야 함
        updated_result = ResultManager.get_result(temp_data_root, run_id)
        btc_symbol = next((s for s in updated_result["symbols"] if s["symbol"] == "BTC_KRW"), None)
        assert "is_active" in btc_symbol
        assert btc_symbol["is_active"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
