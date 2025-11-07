"""전략 프리셋 관리 모듈"""
import json
import os
import logging
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional
import fcntl

logger = logging.getLogger(__name__)


class StrategyPresetManager:
    """전략 프리셋 저장/조회 관리"""

    @staticmethod
    def _get_presets_file_path(data_root: str) -> str:
        """
        프리셋 파일 경로 반환

        Args:
            data_root: 데이터 루트 디렉토리 (예: /data)

        Returns:
            프리셋 파일 경로 (예: /data/strategies/presets.json)
        """
        return os.path.join(data_root, "strategies", "presets.json")

    @staticmethod
    def _ensure_presets_dir(data_root: str) -> None:
        """
        프리셋 디렉토리 생성

        Args:
            data_root: 데이터 루트 디렉토리
        """
        presets_dir = os.path.join(data_root, "strategies")
        os.makedirs(presets_dir, exist_ok=True)

    @staticmethod
    def _read_presets(data_root: str) -> Dict[str, Any]:
        """
        프리셋 파일 읽기 (파일 잠금 포함)

        Args:
            data_root: 데이터 루트 디렉토리

        Returns:
            {name: preset} 형식의 딕셔너리
        """
        presets_file = StrategyPresetManager._get_presets_file_path(data_root)

        # 파일이 없으면 빈 딕셔너리 반환
        if not os.path.exists(presets_file):
            return {}

        try:
            with open(presets_file, "r", encoding="utf-8") as f:
                # 공유 잠금 (읽기 전용)
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                data = json.load(f)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading presets file: {e}")
            return {}

    @staticmethod
    def _write_presets(data_root: str, presets: Dict[str, Any]) -> None:
        """
        프리셋 파일 쓰기 (원자적 쓰기)

        Args:
            data_root: 데이터 루트 디렉토리
            presets: 저장할 프리셋 데이터
        """
        StrategyPresetManager._ensure_presets_dir(data_root)
        presets_file = StrategyPresetManager._get_presets_file_path(data_root)

        # 임시 파일에 쓰기
        temp_fd, temp_path = tempfile.mkstemp(
            dir=os.path.dirname(presets_file),
            prefix=".presets_",
            suffix=".json"
        )

        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                # 배타적 잠금
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(presets, f, indent=2, ensure_ascii=False, default=str)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # 원자적 이름 변경
            os.replace(temp_path, presets_file)
            logger.info(f"Presets saved to {presets_file}")
        except Exception as e:
            # 임시 파일 정리
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"Error writing presets file: {e}")
            raise

    @staticmethod
    def save_preset(
        data_root: str,
        name: str,
        strategy: str,
        params: Dict[str, Any],
        description: str = ""
    ) -> Dict[str, Any]:
        """
        프리셋 저장

        Args:
            data_root: 데이터 루트 디렉토리
            name: 프리셋 이름
            strategy: 전략명
            params: 파라미터 딕셔너리
            description: 설명 (선택사항)

        Returns:
            저장된 프리셋 데이터

        Raises:
            ValueError: 유효하지 않은 입력
        """
        if not name or not isinstance(name, str):
            raise ValueError("Preset name must be a non-empty string")
        if not strategy or not isinstance(strategy, str):
            raise ValueError("Strategy must be a non-empty string")
        if not isinstance(params, dict):
            raise ValueError("Params must be a dictionary")

        # 기존 프리셋 읽기
        presets = StrategyPresetManager._read_presets(data_root)

        # 새 프리셋 생성
        preset_data = {
            "name": name,
            "strategy": strategy,
            "params": params,
            "description": description,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        # 기존 프리셋이면 updated_at만 업데이트
        if name in presets:
            preset_data["created_at"] = presets[name].get("created_at", preset_data["created_at"])

        presets[name] = preset_data

        # 저장
        StrategyPresetManager._write_presets(data_root, presets)

        return preset_data

    @staticmethod
    def get_preset(data_root: str, name: str) -> Optional[Dict[str, Any]]:
        """
        특정 프리셋 조회

        Args:
            data_root: 데이터 루트 디렉토리
            name: 프리셋 이름

        Returns:
            프리셋 데이터 또는 None
        """
        presets = StrategyPresetManager._read_presets(data_root)
        return presets.get(name)

    @staticmethod
    def get_all_presets(data_root: str) -> List[Dict[str, Any]]:
        """
        모든 프리셋 조회

        Args:
            data_root: 데이터 루트 디렉토리

        Returns:
            프리셋 리스트 (생성일 역순 정렬)
        """
        presets = StrategyPresetManager._read_presets(data_root)
        preset_list = list(presets.values())

        # 생성일 역순 정렬
        preset_list.sort(
            key=lambda p: p.get("created_at", ""),
            reverse=True
        )

        return preset_list

    @staticmethod
    def update_preset(
        data_root: str,
        name: str,
        strategy: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        프리셋 업데이트

        Args:
            data_root: 데이터 루트 디렉토리
            name: 프리셋 이름
            strategy: 새 전략명 (선택사항)
            params: 새 파라미터 (선택사항)
            description: 새 설명 (선택사항)

        Returns:
            업데이트된 프리셋 데이터

        Raises:
            ValueError: 프리셋이 없음
        """
        presets = StrategyPresetManager._read_presets(data_root)

        if name not in presets:
            raise ValueError(f"Preset '{name}' not found")

        preset = presets[name]

        # 선택적 업데이트
        if strategy is not None:
            preset["strategy"] = strategy
        if params is not None:
            preset["params"] = params
        if description is not None:
            preset["description"] = description

        preset["updated_at"] = datetime.utcnow().isoformat()

        # 저장
        StrategyPresetManager._write_presets(data_root, presets)

        return preset

    @staticmethod
    def delete_preset(data_root: str, name: str) -> bool:
        """
        프리셋 삭제

        Args:
            data_root: 데이터 루트 디렉토리
            name: 프리셋 이름

        Returns:
            삭제 성공 여부

        Raises:
            ValueError: 프리셋이 없음
        """
        presets = StrategyPresetManager._read_presets(data_root)

        if name not in presets:
            raise ValueError(f"Preset '{name}' not found")

        del presets[name]

        # 저장
        StrategyPresetManager._write_presets(data_root, presets)

        return True

    @staticmethod
    def get_preset_by_strategy(
        data_root: str,
        strategy: str
    ) -> List[Dict[str, Any]]:
        """
        전략별 프리셋 조회

        Args:
            data_root: 데이터 루트 디렉토리
            strategy: 전략명

        Returns:
            해당 전략의 프리셋 리스트
        """
        presets = StrategyPresetManager._read_presets(data_root)
        matching_presets = [
            p for p in presets.values()
            if p.get("strategy") == strategy
        ]

        # 생성일 역순 정렬
        matching_presets.sort(
            key=lambda p: p.get("created_at", ""),
            reverse=True
        )

        return matching_presets
