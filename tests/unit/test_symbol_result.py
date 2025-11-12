"""
SymbolResult 모델 및 결과 관리 유닛 테스트 (Phase 2)

심볼별 백테스트 결과의 is_active 필드 추가와 하위 호환성을 검증합니다.
"""

import pytest
import tempfile
import json
import os
from typing import Dict, Any
from backend.app.main import SymbolResult, APISignal
from backend.app.result_manager import ResultManager


class TestSymbolResult:
    """SymbolResult 모델 테스트"""

    def test_symbol_result_with_is_active_field(self):
        """is_active 필드가 포함된 SymbolResult 생성 및 검증"""
        symbol_data = {
            "symbol": "BTC_KRW",
            "is_active": True,
            "signals": [],
            "win_rate": 0.55,
            "avg_return": 2.5,
            "max_drawdown": -5.0,
            "avg_hold_bars": 5.0,
        }

        # SymbolResult 모델 생성
        symbol_result = SymbolResult(**symbol_data)

        # 검증: is_active 필드가 올바르게 설정됨
        assert symbol_result.symbol == "BTC_KRW"
        assert symbol_result.is_active is True
        assert symbol_result.win_rate == 0.55

    def test_symbol_result_is_active_default_true(self):
        """is_active 필드의 기본값이 True인지 검증"""
        symbol_data = {
            "symbol": "ETH_KRW",
            "signals": [],
            "win_rate": 0.45,
            "avg_return": 1.5,
            "max_drawdown": -3.0,
            "avg_hold_bars": 3.0,
        }

        # is_active를 명시하지 않으면 기본값 True가 적용됨
        symbol_result = SymbolResult(**symbol_data)

        assert symbol_result.is_active is True

    def test_symbol_result_is_active_false(self):
        """is_active를 False로 설정한 SymbolResult 생성"""
        symbol_data = {
            "symbol": "XRP_KRW",
            "is_active": False,
            "signals": [],
            "win_rate": 0.50,
            "avg_return": 0.5,
            "max_drawdown": -2.0,
            "avg_hold_bars": 4.0,
        }

        symbol_result = SymbolResult(**symbol_data)

        assert symbol_result.is_active is False
        assert symbol_result.symbol == "XRP_KRW"

    def test_symbol_result_to_dict(self):
        """SymbolResult를 dict로 변환 시 is_active 필드 포함"""
        symbol_data = {
            "symbol": "DOGE_KRW",
            "is_active": True,
            "signals": [],
            "win_rate": 0.40,
            "avg_return": -1.0,
            "max_drawdown": -10.0,
            "avg_hold_bars": 2.0,
        }

        symbol_result = SymbolResult(**symbol_data)
        result_dict = symbol_result.model_dump()

        # 검증: dict에 is_active 필드가 포함됨
        assert "is_active" in result_dict
        assert result_dict["is_active"] is True


class TestResultManagerNormalization:
    """ResultManager의 하위 호환성 테스트"""

    def test_normalize_symbol_result_with_is_active(self):
        """is_active 필드가 있는 경우 정규화되지 않음"""
        symbol_dict = {
            "symbol": "BTC_KRW",
            "is_active": True,
            "signals": [],
            "win_rate": 0.55,
            "avg_return": 2.5,
            "max_drawdown": -5.0,
            "avg_hold_bars": 5.0,
        }

        normalized = ResultManager._normalize_symbol_result(symbol_dict.copy())

        assert normalized["is_active"] is True

    def test_normalize_symbol_result_without_is_active(self):
        """is_active 필드가 없는 경우 기본값(True) 추가"""
        symbol_dict = {
            "symbol": "ETH_KRW",
            "signals": [],
            "win_rate": 0.45,
            "avg_return": 1.5,
            "max_drawdown": -3.0,
            "avg_hold_bars": 3.0,
        }

        normalized = ResultManager._normalize_symbol_result(symbol_dict.copy())

        # 검증: is_active 필드가 기본값 True로 추가됨
        assert "is_active" in normalized
        assert normalized["is_active"] is True

    def test_get_result_with_legacy_json(self):
        """레거시 JSON 파일 로드 시 is_active 필드 정규화"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 레거시 결과 JSON 생성 (is_active 필드 없음)
            legacy_result = {
                "version": "1.1.0",
                "run_id": "test-run-001",
                "strategy": "volume_zone_breakout",
                "params": {},
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
                "timeframe": "1d",
                "symbols": [
                    {
                        "symbol": "BTC_KRW",
                        "signals": [],
                        "win_rate": 0.55,
                        "avg_return": 2.5,
                        "max_drawdown": -5.0,
                        "avg_hold_bars": 5.0,
                    },
                    {
                        "symbol": "ETH_KRW",
                        "signals": [],
                        "win_rate": 0.45,
                        "avg_return": 1.5,
                        "max_drawdown": -3.0,
                        "avg_hold_bars": 3.0,
                    },
                ],
                "total_signals": 100,
                "execution_time": 10.5,
            }

            # 결과 파일 저장
            results_dir = os.path.join(tmpdir, "results")
            os.makedirs(results_dir, exist_ok=True)
            result_file = os.path.join(results_dir, "test-run-001.json")
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(legacy_result, f)

            # 결과 로드
            result_data = ResultManager.get_result(tmpdir, "test-run-001")

            # 검증: 모든 심볼에 is_active 필드가 추가됨
            assert result_data is not None
            assert "symbols" in result_data
            assert len(result_data["symbols"]) == 2

            for symbol in result_data["symbols"]:
                assert "is_active" in symbol
                assert symbol["is_active"] is True

    def test_get_result_with_new_json(self):
        """새로운 JSON 파일 로드 시 is_active 필드 유지"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 새로운 결과 JSON 생성 (is_active 필드 포함)
            new_result = {
                "version": "1.1.0",
                "run_id": "test-run-002",
                "strategy": "volume_zone_breakout",
                "params": {},
                "start_date": "2025-02-01",
                "end_date": "2025-02-28",
                "timeframe": "1d",
                "symbols": [
                    {
                        "symbol": "BTC_KRW",
                        "is_active": False,  # 비활성
                        "signals": [],
                        "win_rate": 0.55,
                        "avg_return": 2.5,
                        "max_drawdown": -5.0,
                        "avg_hold_bars": 5.0,
                    },
                    {
                        "symbol": "ETH_KRW",
                        "is_active": True,  # 활성
                        "signals": [],
                        "win_rate": 0.45,
                        "avg_return": 1.5,
                        "max_drawdown": -3.0,
                        "avg_hold_bars": 3.0,
                    },
                ],
                "total_signals": 100,
                "execution_time": 10.5,
            }

            # 결과 파일 저장
            results_dir = os.path.join(tmpdir, "results")
            os.makedirs(results_dir, exist_ok=True)
            result_file = os.path.join(results_dir, "test-run-002.json")
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(new_result, f)

            # 결과 로드
            result_data = ResultManager.get_result(tmpdir, "test-run-002")

            # 검증: is_active 필드가 원래대로 유지됨
            assert result_data is not None
            assert result_data["symbols"][0]["is_active"] is False
            assert result_data["symbols"][1]["is_active"] is True


class TestResultManagerAtomicWrite:
    """ResultManager의 원자적 쓰기 테스트"""

    def test_save_result_atomic_write(self):
        """원자적 쓰기로 결과 파일이 안전하게 저장됨"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result_data = {
                "version": "1.1.0",
                "run_id": "test-atomic-001",
                "strategy": "volume_zone_breakout",
                "params": {},
                "start_date": "2025-03-01",
                "end_date": "2025-03-31",
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
                ],
                "total_signals": 50,
                "execution_time": 8.5,
            }

            # 결과 저장
            success = ResultManager.save_result(tmpdir, "test-atomic-001", result_data)

            assert success is True

            # 결과 파일 확인
            results_dir = os.path.join(tmpdir, "results")
            result_file = os.path.join(results_dir, "test-atomic-001.json")
            assert os.path.exists(result_file)

            # 임시 파일은 없어야 함
            temp_file = result_file + ".tmp"
            assert not os.path.exists(temp_file)

            # 파일 내용 검증
            with open(result_file, "r", encoding="utf-8") as f:
                saved_data = json.load(f)

            assert saved_data["run_id"] == "test-atomic-001"
            assert len(saved_data["symbols"]) == 1
            assert saved_data["symbols"][0]["is_active"] is True

    def test_save_result_updates_index(self):
        """결과 저장 시 인덱스가 업데이트됨"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result_data = {
                "version": "1.1.0",
                "run_id": "test-index-001",
                "strategy": "volume_zone_breakout",
                "params": {},
                "start_date": "2025-04-01",
                "end_date": "2025-04-30",
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
                ],
                "total_signals": 50,
                "execution_time": 8.5,
            }

            # 결과 저장
            ResultManager.save_result(tmpdir, "test-index-001", result_data)

            # 인덱스 파일 확인
            index_file = os.path.join(tmpdir, "results", "index.json")
            assert os.path.exists(index_file)

            with open(index_file, "r", encoding="utf-8") as f:
                index_data = json.load(f)

            assert "items" in index_data
            assert len(index_data["items"]) > 0
            assert index_data["items"][0]["run_id"] == "test-index-001"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
