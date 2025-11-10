"""
저장소 제공자 (S3, NFS, OneDrive 등) 및 결과 저장 인터페이스
"""

from backend.app.storage.base import StorageProvider
from backend.app.storage.s3_provider import S3StorageProvider
from backend.app.storage.result_storage import ResultStorage, SQLiteResultStorage, PostgreSQLResultStorage

__all__ = [
    "StorageProvider",
    "S3StorageProvider",
    "ResultStorage",
    "SQLiteResultStorage",
    "PostgreSQLResultStorage",
]
