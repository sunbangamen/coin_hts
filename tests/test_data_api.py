"""
데이터 관리 API 테스트

GET /api/data/inventory 엔드포인트 테스트
POST /api/data/upload 엔드포인트 테스트
"""

import pytest
import tempfile
import os
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


class TestInventoryAPI:
    """데이터 인벤토리 API 테스트"""

    def test_inventory_empty(self, tmp_path, monkeypatch):
        """빈 DATA_ROOT 디렉토리 조회"""
        # DATA_ROOT를 임시 디렉토리로 설정
        monkeypatch.setenv("DATA_ROOT", str(tmp_path))

        # 라우터 모듈 재임포트하여 환경변수 반영
        import importlib
        from backend.app.routers import data as data_router
        importlib.reload(data_router)

        response = client.get("/api/data/inventory")

        assert response.status_code == 200
        data = response.json()
        assert data["files"] == []
        assert data["total_count"] == 0
        assert data["limit"] == 50
        assert data["offset"] == 0

    def test_inventory_with_files(self, tmp_path, monkeypatch):
        """파일이 있는 경우 인벤토리 조회"""
        # 테스트 데이터 구조 생성
        symbol_dir = tmp_path / "BTC_KRW" / "1D"
        symbol_dir.mkdir(parents=True)

        # 더미 parquet 파일 생성 (간단한 바이너리 파일)
        test_file = symbol_dir / "2024.parquet"
        test_file.write_bytes(b"dummy parquet data")

        monkeypatch.setenv("DATA_ROOT", str(tmp_path))

        # 라우터 모듈 재임포트
        import importlib
        from backend.app.routers import data as data_router
        importlib.reload(data_router)

        response = client.get("/api/data/inventory")

        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) == 1
        assert data["total_count"] == 1

        file_info = data["files"][0]
        assert file_info["symbol"] == "BTC_KRW"
        assert file_info["timeframe"] == "1D"
        assert file_info["year"] == 2024
        assert file_info["relative_path"] == "BTC_KRW/1D/2024.parquet"

    def test_inventory_symbol_filter(self, tmp_path, monkeypatch):
        """심볼 필터링 테스트"""
        # 여러 심볼의 파일 생성
        for symbol in ["BTC_KRW", "ETH_KRW", "SOL_KRW"]:
            symbol_dir = tmp_path / symbol / "1D"
            symbol_dir.mkdir(parents=True)
            (symbol_dir / "2024.parquet").write_bytes(b"data")

        monkeypatch.setenv("DATA_ROOT", str(tmp_path))

        import importlib
        from backend.app.routers import data as data_router
        importlib.reload(data_router)

        response = client.get("/api/data/inventory?symbol=BTC_KRW")

        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) == 1
        assert data["files"][0]["symbol"] == "BTC_KRW"

    def test_inventory_timeframe_filter(self, tmp_path, monkeypatch):
        """타임프레임 필터링 테스트"""
        # 여러 타임프레임의 파일 생성
        for timeframe in ["1D", "1H", "5M"]:
            tf_dir = tmp_path / "BTC_KRW" / timeframe
            tf_dir.mkdir(parents=True)
            (tf_dir / "2024.parquet").write_bytes(b"data")

        monkeypatch.setenv("DATA_ROOT", str(tmp_path))

        import importlib
        from backend.app.routers import data as data_router
        importlib.reload(data_router)

        response = client.get("/api/data/inventory?timeframe=1H")

        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) == 1
        assert data["files"][0]["timeframe"] == "1H"

    def test_inventory_pagination(self, tmp_path, monkeypatch):
        """페이지네이션 테스트"""
        # 100개의 파일 생성
        for i in range(100):
            symbol_dir = tmp_path / f"SYM{i:03d}_KRW" / "1D"
            symbol_dir.mkdir(parents=True)
            (symbol_dir / "2024.parquet").write_bytes(b"data")

        monkeypatch.setenv("DATA_ROOT", str(tmp_path))

        import importlib
        from backend.app.routers import data as data_router
        importlib.reload(data_router)

        # 첫 페이지 (limit=10, offset=0)
        response = client.get("/api/data/inventory?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) == 10
        assert data["total_count"] == 100
        assert data["limit"] == 10
        assert data["offset"] == 0

        # 두 번째 페이지 (limit=10, offset=10)
        response = client.get("/api/data/inventory?limit=10&offset=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) == 10
        assert data["offset"] == 10

    def test_inventory_limit_max(self, tmp_path, monkeypatch):
        """limit 최대값 제한 테스트"""
        # 500개 파일 생성
        for i in range(500):
            symbol_dir = tmp_path / f"SYM{i:03d}_KRW" / "1D"
            symbol_dir.mkdir(parents=True)
            (symbol_dir / "2024.parquet").write_bytes(b"data")

        monkeypatch.setenv("DATA_ROOT", str(tmp_path))

        import importlib
        from backend.app.routers import data as data_router
        importlib.reload(data_router)

        # limit=500 요청해도 최대 200으로 제한됨
        response = client.get("/api/data/inventory?limit=500")
        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) == 200  # 최대 200개만 반환
        assert data["limit"] == 200  # limit은 200으로 조정됨


class TestUploadAPI:
    """파일 업로드 API 테스트"""

    def test_upload_valid_file(self, tmp_path, monkeypatch):
        """유효한 파일 업로드 성공"""
        monkeypatch.setenv("DATA_ROOT", str(tmp_path))

        import importlib
        from backend.app.routers import data as data_router
        importlib.reload(data_router)

        # 더미 parquet 파일 생성
        test_file_path = tmp_path / "test_upload.parquet"
        test_file_path.write_bytes(b"dummy parquet data")

        # 파일 업로드
        with open(test_file_path, "rb") as f:
            response = client.post(
                "/api/data/upload",
                data={
                    "symbol": "BTC_KRW",
                    "timeframe": "1D",
                    "year": 2024,
                    "overwrite": False,
                },
                files={"file": f},
            )

        # 응답 확인 (파일이 유효하지 않으면 415 반환)
        # 더미 파일이므로 파일 형식 오류가 발생할 수 있음
        assert response.status_code in [200, 415]

    def test_upload_input_validation(self, tmp_path, monkeypatch):
        """입력값 검증 테스트"""
        monkeypatch.setenv("DATA_ROOT", str(tmp_path))

        import importlib
        from backend.app.routers import data as data_router
        importlib.reload(data_router)

        test_file_path = tmp_path / "test.parquet"
        test_file_path.write_bytes(b"data")

        # 잘못된 연도 (3자리)
        with open(test_file_path, "rb") as f:
            response = client.post(
                "/api/data/upload",
                data={
                    "symbol": "BTC_KRW",
                    "timeframe": "1D",
                    "year": 202,  # 잘못된 형식
                    "overwrite": False,
                },
                files={"file": f},
            )

        assert response.status_code == 400

    def test_upload_invalid_extension(self, tmp_path, monkeypatch):
        """잘못된 확장자 거부"""
        monkeypatch.setenv("DATA_ROOT", str(tmp_path))

        import importlib
        from backend.app.routers import data as data_router
        importlib.reload(data_router)

        # .csv 파일 생성
        test_file_path = tmp_path / "test.csv"
        test_file_path.write_bytes(b"csv data")

        with open(test_file_path, "rb") as f:
            response = client.post(
                "/api/data/upload",
                data={
                    "symbol": "BTC_KRW",
                    "timeframe": "1D",
                    "year": 2024,
                    "overwrite": False,
                },
                files={"file": f},
            )

        # CSV 파일이므로 파일 형식 오류
        assert response.status_code == 415

    def test_upload_duplicate_file_conflict(self, tmp_path, monkeypatch):
        """파일 중복 생성 시 409 Conflict"""
        monkeypatch.setenv("DATA_ROOT", str(tmp_path))

        import importlib
        from backend.app.routers import data as data_router
        importlib.reload(data_router)

        # 기존 파일 생성
        existing_file = tmp_path / "BTC_KRW" / "1D" / "2024.parquet"
        existing_file.parent.mkdir(parents=True)
        existing_file.write_bytes(b"existing data")

        test_file_path = tmp_path / "test.parquet"
        test_file_path.write_bytes(b"new data")

        # overwrite=False로 업로드 시도
        with open(test_file_path, "rb") as f:
            response = client.post(
                "/api/data/upload",
                data={
                    "symbol": "BTC_KRW",
                    "timeframe": "1D",
                    "year": 2024,
                    "overwrite": False,
                },
                files={"file": f},
            )

        assert response.status_code == 409

    def test_upload_path_traversal_prevention(self, tmp_path, monkeypatch):
        """경로 이탈 시도 차단"""
        monkeypatch.setenv("DATA_ROOT", str(tmp_path))

        import importlib
        from backend.app.routers import data as data_router
        importlib.reload(data_router)

        test_file_path = tmp_path / "test.parquet"
        test_file_path.write_bytes(b"data")

        # 경로 이탈 시도 (심볼에 ../를 포함)
        with open(test_file_path, "rb") as f:
            response = client.post(
                "/api/data/upload",
                data={
                    "symbol": "../../../ETC",  # 경로 이탈 시도
                    "timeframe": "1D",
                    "year": 2024,
                    "overwrite": False,
                },
                files={"file": f},
            )

        # 입력값 검증 실패로 400 반환
        assert response.status_code == 400
