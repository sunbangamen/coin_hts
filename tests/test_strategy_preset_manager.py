"""전략 프리셋 관리자 테스트"""
import pytest
import tempfile
import shutil
import os
import json
from backend.app.strategy_preset_manager import StrategyPresetManager


class TestStrategyPresetManager:
    """StrategyPresetManager 테스트"""

    @pytest.fixture
    def temp_data_root(self):
        """임시 데이터 루트 디렉토리 생성"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_save_preset(self, temp_data_root):
        """프리셋 저장 테스트"""
        preset_data = {
            "name": "conservative",
            "strategy": "volume_long_candle",
            "params": {"vol_ma_window": 20, "vol_multiplier": 1.5, "body_pct": 0.01},
            "description": "보수적 전략 프리셋"
        }

        # 프리셋 저장
        result = StrategyPresetManager.save_preset(
            data_root=temp_data_root,
            name=preset_data["name"],
            strategy=preset_data["strategy"],
            params=preset_data["params"],
            description=preset_data["description"]
        )

        # 검증
        assert result["name"] == "conservative"
        assert result["strategy"] == "volume_long_candle"
        assert result["params"] == preset_data["params"]
        assert result["description"] == "보수적 전략 프리셋"
        assert "created_at" in result
        assert "updated_at" in result

        # 파일이 생성되었는지 확인
        presets_file = os.path.join(temp_data_root, "strategies", "presets.json")
        assert os.path.exists(presets_file)

        # 파일 내용 검증
        with open(presets_file, "r") as f:
            data = json.load(f)
        assert "conservative" in data

    def test_get_preset(self, temp_data_root):
        """프리셋 조회 테스트"""
        # 프리셋 저장
        StrategyPresetManager.save_preset(
            data_root=temp_data_root,
            name="balanced",
            strategy="volume_zone_breakout",
            params={"volume_window": 20, "top_percentile": 0.20, "breakout_buffer": 0.0}
        )

        # 프리셋 조회
        preset = StrategyPresetManager.get_preset(temp_data_root, "balanced")

        # 검증
        assert preset is not None
        assert preset["name"] == "balanced"
        assert preset["strategy"] == "volume_zone_breakout"

    def test_get_preset_nonexistent(self, temp_data_root):
        """존재하지 않는 프리셋 조회 테스트"""
        preset = StrategyPresetManager.get_preset(temp_data_root, "nonexistent")
        assert preset is None

    def test_get_all_presets(self, temp_data_root):
        """모든 프리셋 조회 테스트"""
        # 3개의 프리셋 저장
        presets = [
            {"name": "conservative", "strategy": "volume_long_candle"},
            {"name": "balanced", "strategy": "volume_zone_breakout"},
            {"name": "aggressive", "strategy": "volume_zone_breakout"}
        ]

        for p in presets:
            StrategyPresetManager.save_preset(
                data_root=temp_data_root,
                name=p["name"],
                strategy=p["strategy"],
                params={}
            )

        # 모든 프리셋 조회
        all_presets = StrategyPresetManager.get_all_presets(temp_data_root)

        # 검증
        assert len(all_presets) == 3
        names = [p["name"] for p in all_presets]
        assert "conservative" in names
        assert "balanced" in names
        assert "aggressive" in names

    def test_update_preset(self, temp_data_root):
        """프리셋 업데이트 테스트"""
        # 프리셋 저장
        StrategyPresetManager.save_preset(
            data_root=temp_data_root,
            name="test_preset",
            strategy="volume_long_candle",
            params={"vol_ma_window": 20, "vol_multiplier": 1.5, "body_pct": 0.01},
            description="원본 설명"
        )

        # 프리셋 업데이트
        updated = StrategyPresetManager.update_preset(
            data_root=temp_data_root,
            name="test_preset",
            strategy="volume_zone_breakout",
            params={"volume_window": 25, "top_percentile": 0.25, "breakout_buffer": 0.0},
            description="업데이트된 설명"
        )

        # 검증
        assert updated["name"] == "test_preset"
        assert updated["strategy"] == "volume_zone_breakout"
        assert updated["params"]["volume_window"] == 25
        assert updated["description"] == "업데이트된 설명"

    def test_update_preset_nonexistent(self, temp_data_root):
        """존재하지 않는 프리셋 업데이트 테스트"""
        with pytest.raises(ValueError, match="not found"):
            StrategyPresetManager.update_preset(
                data_root=temp_data_root,
                name="nonexistent",
                strategy="volume_long_candle",
                params={}
            )

    def test_delete_preset(self, temp_data_root):
        """프리셋 삭제 테스트"""
        # 프리셋 저장
        StrategyPresetManager.save_preset(
            data_root=temp_data_root,
            name="to_delete",
            strategy="volume_long_candle",
            params={}
        )

        # 프리셋 삭제
        result = StrategyPresetManager.delete_preset(temp_data_root, "to_delete")
        assert result is True

        # 삭제 확인
        preset = StrategyPresetManager.get_preset(temp_data_root, "to_delete")
        assert preset is None

    def test_delete_preset_nonexistent(self, temp_data_root):
        """존재하지 않는 프리셋 삭제 테스트"""
        with pytest.raises(ValueError, match="not found"):
            StrategyPresetManager.delete_preset(temp_data_root, "nonexistent")

    def test_save_preset_invalid_name(self, temp_data_root):
        """유효하지 않은 이름으로 프리셋 저장 테스트"""
        with pytest.raises(ValueError):
            StrategyPresetManager.save_preset(
                data_root=temp_data_root,
                name="",  # 빈 이름
                strategy="volume_long_candle",
                params={}
            )

    def test_save_preset_invalid_strategy(self, temp_data_root):
        """유효하지 않은 전략으로 프리셋 저장 테스트"""
        with pytest.raises(ValueError):
            StrategyPresetManager.save_preset(
                data_root=temp_data_root,
                name="test",
                strategy="",  # 빈 전략
                params={}
            )

    def test_save_preset_invalid_params(self, temp_data_root):
        """유효하지 않은 파라미터로 프리셋 저장 테스트"""
        with pytest.raises(ValueError):
            StrategyPresetManager.save_preset(
                data_root=temp_data_root,
                name="test",
                strategy="volume_long_candle",
                params=[]  # dict가 아님
            )

    def test_get_preset_by_strategy(self, temp_data_root):
        """전략별 프리셋 조회 테스트"""
        # 여러 전략의 프리셋 저장
        StrategyPresetManager.save_preset(
            data_root=temp_data_root,
            name="preset1",
            strategy="volume_long_candle",
            params={}
        )
        StrategyPresetManager.save_preset(
            data_root=temp_data_root,
            name="preset2",
            strategy="volume_long_candle",
            params={}
        )
        StrategyPresetManager.save_preset(
            data_root=temp_data_root,
            name="preset3",
            strategy="volume_zone_breakout",
            params={}
        )

        # volume_long_candle 프리셋 조회
        presets = StrategyPresetManager.get_preset_by_strategy(
            temp_data_root,
            "volume_long_candle"
        )

        # 검증
        assert len(presets) == 2
        names = [p["name"] for p in presets]
        assert "preset1" in names
        assert "preset2" in names

    def test_idempotent_save(self, temp_data_root):
        """동일한 이름으로 여러 번 저장 테스트 (중복 방지)"""
        # 첫 번째 저장
        StrategyPresetManager.save_preset(
            data_root=temp_data_root,
            name="duplicate_test",
            strategy="volume_long_candle",
            params={"vol_ma_window": 20}
        )

        # 두 번째 저장 (업데이트)
        StrategyPresetManager.save_preset(
            data_root=temp_data_root,
            name="duplicate_test",
            strategy="volume_zone_breakout",
            params={"volume_window": 25}
        )

        # 모든 프리셋 조회
        all_presets = StrategyPresetManager.get_all_presets(temp_data_root)

        # 검증: duplicate_test가 1개만 있어야 함
        matching = [p for p in all_presets if p["name"] == "duplicate_test"]
        assert len(matching) == 1
        assert matching[0]["strategy"] == "volume_zone_breakout"

    def test_preset_timestamps(self, temp_data_root):
        """프리셋 타임스탬프 테스트"""
        # 프리셋 저장
        preset = StrategyPresetManager.save_preset(
            data_root=temp_data_root,
            name="timestamp_test",
            strategy="volume_long_candle",
            params={}
        )

        created_at = preset["created_at"]

        # 프리셋 업데이트
        import time
        time.sleep(0.1)  # 시간 차이 생성
        updated_preset = StrategyPresetManager.update_preset(
            data_root=temp_data_root,
            name="timestamp_test",
            params={"vol_ma_window": 30}
        )

        updated_at = updated_preset["updated_at"]

        # 검증: created_at은 동일, updated_at은 다름
        assert preset["created_at"] == created_at
        assert updated_at != created_at
