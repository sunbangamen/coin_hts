"""
S3 스토리지 프로바이더 테스트

moto를 사용하여 S3 mock 환경에서 테스트합니다.
"""

import pytest
import json
import asyncio
from pathlib import Path
from datetime import datetime

from moto import mock_aws
import boto3

from backend.app.storage.s3_provider import S3StorageProvider


@pytest.fixture
def tmp_test_file(tmp_path):
    """임시 테스트 파일 생성"""
    test_file = tmp_path / "test_backtest_result.json"
    test_data = {
        "symbol": "KRW-BTC",
        "strategy": "volume_zone_breakout",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "total_trades": 42,
        "win_rate": 0.714,
        "profit_factor": 2.15,
    }
    test_file.write_text(json.dumps(test_data, indent=2))
    return test_file


class TestS3StorageProviderInitialization:
    """S3 프로바이더 초기화 테스트"""

    @mock_aws
    def test_s3_provider_init(self):
        """S3 프로바이더 초기화 검증"""
        # moto S3 버킷 생성
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket="test-backtest-bucket")

        provider = S3StorageProvider(
            bucket_name="test-backtest-bucket",
            region="us-east-1",
        )

        assert provider.bucket_name == "test-backtest-bucket"
        assert provider.region == "us-east-1"
        assert provider.s3_client is not None


class TestS3StorageUpload:
    """S3 업로드 테스트"""

    @mock_aws
    def test_upload_success(self, tmp_test_file):
        """파일 업로드 성공 검증"""
        # moto S3 버킷 생성
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket="test-backtest-bucket")

        provider = S3StorageProvider(
            bucket_name="test-backtest-bucket",
            region="us-east-1",
        )

        result = asyncio.run(provider.upload(
            file_path=str(tmp_test_file),
            remote_path="backtests/2024-01-01/result.json",
            metadata={"strategy": "volume_zone_breakout"},
        ))

        assert result["success"] is True
        assert result["remote_path"] == "backtests/2024-01-01/result.json"
        assert result["size"] == tmp_test_file.stat().st_size
        assert result["etag"] is not None
        assert result["error"] is None

    @mock_aws
    def test_upload_file_not_found(self):
        """파일 없음 에러 검증"""
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket="test-backtest-bucket")

        provider = S3StorageProvider(
            bucket_name="test-backtest-bucket",
            region="us-east-1",
        )

        result = asyncio.run(provider.upload(
            file_path="/nonexistent/file.json",
            remote_path="backtests/result.json",
        ))

        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestS3StorageDownload:
    """S3 다운로드 테스트"""

    @mock_aws
    def test_download_success(self, tmp_test_file, tmp_path):
        """파일 다운로드 성공 검증"""
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket="test-backtest-bucket")

        provider = S3StorageProvider(
            bucket_name="test-backtest-bucket",
            region="us-east-1",
        )

        # 먼저 파일 업로드
        asyncio.run(provider.upload(
            file_path=str(tmp_test_file),
            remote_path="backtests/result.json",
        ))

        # 파일 다운로드
        download_path = tmp_path / "downloaded_result.json"
        result = asyncio.run(provider.download(
            remote_path="backtests/result.json",
            local_path=str(download_path),
        ))

        assert result["success"] is True
        assert result["local_path"] == str(download_path)
        assert download_path.exists()
        assert result["size"] == tmp_test_file.stat().st_size


class TestS3StorageDelete:
    """S3 삭제 테스트"""

    @mock_aws
    def test_delete_success(self, tmp_test_file):
        """파일 삭제 성공 검증"""
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket="test-backtest-bucket")

        provider = S3StorageProvider(
            bucket_name="test-backtest-bucket",
            region="us-east-1",
        )

        # 먼저 파일 업로드
        asyncio.run(provider.upload(
            file_path=str(tmp_test_file),
            remote_path="backtests/result.json",
        ))

        # 파일 삭제
        result = asyncio.run(provider.delete(remote_path="backtests/result.json"))

        assert result["success"] is True
        assert result["remote_path"] == "backtests/result.json"
        assert result["deleted_at"] is not None


class TestS3StorageList:
    """S3 파일 목록 조회 테스트"""

    @mock_aws
    def test_list_files_empty(self):
        """빈 버킷 조회 검증"""
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket="test-backtest-bucket")

        provider = S3StorageProvider(
            bucket_name="test-backtest-bucket",
            region="us-east-1",
        )

        result = asyncio.run(provider.list_files(prefix="backtests/"))

        assert result["success"] is True
        assert len(result["files"]) == 0

    @mock_aws
    def test_list_files_with_prefix(self, tmp_test_file):
        """프리픽스가 있는 파일 목록 조회 검증"""
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket="test-backtest-bucket")

        provider = S3StorageProvider(
            bucket_name="test-backtest-bucket",
            region="us-east-1",
        )

        # 파일 2개 업로드
        asyncio.run(provider.upload(
            file_path=str(tmp_test_file),
            remote_path="backtests/2024-01/result1.json",
        ))
        asyncio.run(provider.upload(
            file_path=str(tmp_test_file),
            remote_path="backtests/2024-01/result2.json",
        ))

        result = asyncio.run(provider.list_files(prefix="backtests/2024-01/"))

        assert result["success"] is True
        assert len(result["files"]) == 2
        assert all(f["name"].startswith("backtests/2024-01/") for f in result["files"])


class TestS3StorageIntegrity:
    """S3 무결성 검증 테스트"""

    @mock_aws
    def test_verify_integrity_success(self, tmp_test_file):
        """무결성 검증 성공 검증"""
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket="test-backtest-bucket")

        provider = S3StorageProvider(
            bucket_name="test-backtest-bucket",
            region="us-east-1",
        )

        # 파일 업로드
        upload_result = asyncio.run(provider.upload(
            file_path=str(tmp_test_file),
            remote_path="backtests/result.json",
        ))

        # 무결성 검증
        result = asyncio.run(provider.verify_integrity(
            remote_path="backtests/result.json",
            local_etag=upload_result["etag"],
        ))

        assert result["success"] is True
        assert result["matches"] is True
        assert result["remote_etag"] == upload_result["etag"]

    @mock_aws
    def test_verify_integrity_mismatch(self, tmp_test_file):
        """무결성 검증 불일치 검증"""
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket="test-backtest-bucket")

        provider = S3StorageProvider(
            bucket_name="test-backtest-bucket",
            region="us-east-1",
        )

        # 파일 업로드
        asyncio.run(provider.upload(
            file_path=str(tmp_test_file),
            remote_path="backtests/result.json",
        ))

        # 잘못된 ETag로 검증
        result = asyncio.run(provider.verify_integrity(
            remote_path="backtests/result.json",
            local_etag="wrong-etag",
        ))

        assert result["success"] is True
        assert result["matches"] is False


class TestS3StorageMetadata:
    """S3 메타데이터 조회 테스트"""

    @mock_aws
    def test_get_metadata_success(self, tmp_test_file):
        """메타데이터 조회 성공 검증"""
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket="test-backtest-bucket")

        provider = S3StorageProvider(
            bucket_name="test-backtest-bucket",
            region="us-east-1",
        )

        # 파일 업로드
        asyncio.run(provider.upload(
            file_path=str(tmp_test_file),
            remote_path="backtests/result.json",
            metadata={"strategy": "volume_zone_breakout"},
        ))

        # 메타데이터 조회
        result = asyncio.run(provider.get_metadata(
            remote_path="backtests/result.json",
        ))

        assert result["success"] is True
        assert result["size"] == tmp_test_file.stat().st_size
        assert result["etag"] is not None
        assert result["modified"] is not None
        assert "strategy" in result["custom_metadata"]
