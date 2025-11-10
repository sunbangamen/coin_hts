"""
스토리지 프로바이더 추상 기본 클래스
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime


class StorageProvider(ABC):
    """
    외부 스토리지 프로바이더 추상 클래스

    로컬 백테스트 결과를 외부 스토리지에 저장/로드하기 위한
    통일된 인터페이스를 제공합니다.
    """

    @abstractmethod
    async def upload(
        self,
        file_path: str,
        remote_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        파일을 원격 스토리지에 업로드

        Args:
            file_path: 로컬 파일 경로
            remote_path: 원격 스토리지 경로
            metadata: 메타데이터 (선택사항)

        Returns:
            업로드 결과 정보
            {
                'success': bool,
                'remote_path': str,
                'etag': str,  # 무결성 검증용
                'size': int,
                'uploaded_at': datetime,
                'error': str or None
            }
        """
        pass

    @abstractmethod
    async def download(
        self,
        remote_path: str,
        local_path: str,
    ) -> Dict[str, Any]:
        """
        원격 스토리지에서 파일을 다운로드

        Args:
            remote_path: 원격 스토리지 경로
            local_path: 로컬 저장 경로

        Returns:
            다운로드 결과 정보
            {
                'success': bool,
                'local_path': str,
                'size': int,
                'downloaded_at': datetime,
                'error': str or None
            }
        """
        pass

    @abstractmethod
    async def delete(self, remote_path: str) -> Dict[str, Any]:
        """
        원격 스토리지 파일 삭제

        Args:
            remote_path: 원격 스토리지 경로

        Returns:
            삭제 결과 정보
            {
                'success': bool,
                'remote_path': str,
                'deleted_at': datetime,
                'error': str or None
            }
        """
        pass

    @abstractmethod
    async def list_files(
        self,
        prefix: str = "",
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        원격 스토리지의 파일 목록 조회

        Args:
            prefix: 경로 프리픽스
            limit: 반환 개수 제한

        Returns:
            파일 목록
            {
                'success': bool,
                'files': [
                    {
                        'name': str,
                        'size': int,
                        'modified': datetime,
                        'etag': str,
                    }
                ],
                'error': str or None
            }
        """
        pass

    @abstractmethod
    async def verify_integrity(
        self,
        remote_path: str,
        local_etag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        파일 무결성 검증 (ETag 기반)

        Args:
            remote_path: 원격 스토리지 경로
            local_etag: 로컬 ETag (선택사항)

        Returns:
            검증 결과
            {
                'success': bool,
                'remote_etag': str,
                'local_etag': str or None,
                'matches': bool,
                'error': str or None
            }
        """
        pass

    @abstractmethod
    async def get_metadata(
        self,
        remote_path: str,
    ) -> Dict[str, Any]:
        """
        파일 메타데이터 조회

        Args:
            remote_path: 원격 스토리지 경로

        Returns:
            메타데이터
            {
                'success': bool,
                'size': int,
                'etag': str,
                'modified': datetime,
                'custom_metadata': dict,
                'error': str or None
            }
        """
        pass
