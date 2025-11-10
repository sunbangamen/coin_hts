"""
AWS S3 스토리지 프로바이더

boto3를 사용하여 S3 버킷에 백테스트 결과를 저장/로드합니다.
"""

import logging
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from backend.app.storage.base import StorageProvider

logger = logging.getLogger(__name__)


class S3StorageProvider(StorageProvider):
    """
    AWS S3 스토리지 프로바이더

    백테스트 결과를 S3에 저장하고, 필요시 다운로드하며,
    ETag 기반 무결성 검증을 수행합니다.
    """

    def __init__(
        self,
        bucket_name: str,
        region: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ):
        """
        S3StorageProvider 초기화

        Args:
            bucket_name: S3 버킷 이름
            region: AWS 리전
            aws_access_key_id: AWS 액세스 키 (환경변수 사용 시 선택사항)
            aws_secret_access_key: AWS 비밀 키 (환경변수 사용 시 선택사항)
            endpoint_url: 커스텀 S3 엔드포인트 (moto 등 테스트 용)
        """
        self.bucket_name = bucket_name
        self.region = region

        try:
            # S3 클라이언트 초기화
            session_kwargs = {"region_name": region}
            if aws_access_key_id and aws_secret_access_key:
                session_kwargs["aws_access_key_id"] = aws_access_key_id
                session_kwargs["aws_secret_access_key"] = aws_secret_access_key

            session = boto3.Session(**session_kwargs)
            client_kwargs = {}
            if endpoint_url:
                client_kwargs["endpoint_url"] = endpoint_url

            self.s3_client = session.client("s3", **client_kwargs)
            logger.info(
                f"S3StorageProvider initialized (bucket={bucket_name}, region={region})"
            )
        except Exception as e:
            logger.error(f"Failed to initialize S3StorageProvider: {e}")
            raise

    async def upload(
        self,
        file_path: str,
        remote_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        파일을 S3에 업로드

        Args:
            file_path: 로컬 파일 경로
            remote_path: S3 객체 경로
            metadata: 메타데이터

        Returns:
            업로드 결과
        """
        try:
            local_file = Path(file_path)
            if not local_file.exists():
                return {
                    "success": False,
                    "remote_path": remote_path,
                    "error": f"Local file not found: {file_path}",
                }

            # 파일 크기
            file_size = local_file.stat().st_size

            # 메타데이터 설정
            extra_args = {}
            if metadata:
                extra_args["Metadata"] = {
                    k: str(v) for k, v in metadata.items()
                }

            # S3에 업로드
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                remote_path,
                ExtraArgs=extra_args if extra_args else None,
            )

            # 업로드된 객체의 ETag 조회
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=remote_path,
            )
            etag = response.get("ETag", "").strip('"')

            logger.info(
                f"File uploaded to S3: {remote_path} "
                f"(size={file_size}, etag={etag})"
            )

            return {
                "success": True,
                "remote_path": remote_path,
                "etag": etag,
                "size": file_size,
                "uploaded_at": datetime.utcnow(),
                "error": None,
            }

        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            return {
                "success": False,
                "remote_path": remote_path,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Unexpected error during upload: {e}")
            return {
                "success": False,
                "remote_path": remote_path,
                "error": str(e),
            }

    async def download(
        self,
        remote_path: str,
        local_path: str,
    ) -> Dict[str, Any]:
        """
        S3에서 파일을 다운로드

        Args:
            remote_path: S3 객체 경로
            local_path: 로컬 저장 경로

        Returns:
            다운로드 결과
        """
        try:
            # 로컬 디렉토리 생성
            local_file = Path(local_path)
            local_file.parent.mkdir(parents=True, exist_ok=True)

            # S3에서 다운로드
            self.s3_client.download_file(
                self.bucket_name,
                remote_path,
                local_path,
            )

            # 다운로드된 파일 크기
            file_size = local_file.stat().st_size

            logger.info(
                f"File downloaded from S3: {remote_path} "
                f"(size={file_size}, local={local_path})"
            )

            return {
                "success": True,
                "local_path": local_path,
                "size": file_size,
                "downloaded_at": datetime.utcnow(),
                "error": None,
            }

        except ClientError as e:
            logger.error(f"S3 download error: {e}")
            return {
                "success": False,
                "local_path": local_path,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Unexpected error during download: {e}")
            return {
                "success": False,
                "local_path": local_path,
                "error": str(e),
            }

    async def delete(self, remote_path: str) -> Dict[str, Any]:
        """
        S3 객체 삭제

        Args:
            remote_path: S3 객체 경로

        Returns:
            삭제 결과
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=remote_path,
            )

            logger.info(f"File deleted from S3: {remote_path}")

            return {
                "success": True,
                "remote_path": remote_path,
                "deleted_at": datetime.utcnow(),
                "error": None,
            }

        except ClientError as e:
            logger.error(f"S3 delete error: {e}")
            return {
                "success": False,
                "remote_path": remote_path,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Unexpected error during delete: {e}")
            return {
                "success": False,
                "remote_path": remote_path,
                "error": str(e),
            }

    async def list_files(
        self,
        prefix: str = "",
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        S3 버킷의 객체 목록 조회

        Args:
            prefix: 경로 프리픽스
            limit: 반환 개수 제한

        Returns:
            파일 목록
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=limit,
            )

            files = []
            for obj in response.get("Contents", []):
                files.append({
                    "name": obj["Key"],
                    "size": obj["Size"],
                    "modified": obj["LastModified"],
                    "etag": obj["ETag"].strip('"'),
                })

            logger.info(
                f"Listed {len(files)} files from S3 "
                f"(prefix={prefix}, limit={limit})"
            )

            return {
                "success": True,
                "files": files,
                "error": None,
            }

        except ClientError as e:
            logger.error(f"S3 list error: {e}")
            return {
                "success": False,
                "files": [],
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Unexpected error during list: {e}")
            return {
                "success": False,
                "files": [],
                "error": str(e),
            }

    async def verify_integrity(
        self,
        remote_path: str,
        local_etag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        S3 파일의 무결성 검증 (ETag 비교)

        Args:
            remote_path: S3 객체 경로
            local_etag: 로컬 ETag (선택사항)

        Returns:
            검증 결과
        """
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=remote_path,
            )
            remote_etag = response.get("ETag", "").strip('"')

            # 비교 수행
            matches = True
            if local_etag:
                matches = remote_etag == local_etag
                logger.info(
                    f"Integrity check: {remote_path} "
                    f"(remote={remote_etag}, local={local_etag}, match={matches})"
                )

            return {
                "success": True,
                "remote_etag": remote_etag,
                "local_etag": local_etag,
                "matches": matches,
                "error": None,
            }

        except ClientError as e:
            logger.error(f"S3 integrity check error: {e}")
            return {
                "success": False,
                "remote_etag": None,
                "local_etag": local_etag,
                "matches": False,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Unexpected error during integrity check: {e}")
            return {
                "success": False,
                "remote_etag": None,
                "local_etag": local_etag,
                "matches": False,
                "error": str(e),
            }

    async def get_metadata(
        self,
        remote_path: str,
    ) -> Dict[str, Any]:
        """
        S3 객체의 메타데이터 조회

        Args:
            remote_path: S3 객체 경로

        Returns:
            메타데이터
        """
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=remote_path,
            )

            return {
                "success": True,
                "size": response.get("ContentLength", 0),
                "etag": response.get("ETag", "").strip('"'),
                "modified": response.get("LastModified"),
                "custom_metadata": response.get("Metadata", {}),
                "error": None,
            }

        except ClientError as e:
            logger.error(f"S3 metadata error: {e}")
            return {
                "success": False,
                "size": 0,
                "etag": None,
                "modified": None,
                "custom_metadata": {},
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Unexpected error getting metadata: {e}")
            return {
                "success": False,
                "size": 0,
                "etag": None,
                "modified": None,
                "custom_metadata": {},
                "error": str(e),
            }
