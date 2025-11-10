"""
구조화된 JSON 로거 구현

모든 로그를 JSON 형식으로 기록하여 분석 및 검색을 용이하게 합니다.
"""

import os
import json
import logging
import logging.handlers
from datetime import datetime
from typing import Optional, Dict, Any
from pythonjsonlogger import jsonlogger


class StructuredFormatter(jsonlogger.JsonFormatter):
    """
    구조화된 JSON 로깅 포매터

    로그 레코드를 JSON 형식으로 변환합니다.
    추가 컨텍스트 정보를 포함할 수 있습니다.
    """

    def __init__(self, fmt=None, style='%', *args, **kwargs):
        super().__init__(fmt, style=style, *args, **kwargs)
        self.default_fields = {
            'timestamp': lambda: datetime.utcnow().isoformat() + 'Z',
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'service': 'coin-hts',
            'version': os.getenv('APP_VERSION', '3.0'),
        }

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """
        로그 레코드에 필드 추가

        Args:
            log_record: 로그 레코드 딕셔너리
            record: Python 로그 레코드
            message_dict: 메시지 딕셔너리
        """
        super().add_fields(log_record, record, message_dict)

        # 기본 필드 추가
        for key, value in self.default_fields.items():
            if key not in log_record:
                log_record[key] = value() if callable(value) else value

        # 로거 이름 추가
        if 'name' not in log_record:
            log_record['logger'] = record.name

        # 로그 레벨 추가
        if 'levelname' not in log_record:
            log_record['level'] = record.levelname.upper()

        # 모듈 정보 추가
        if 'pathname' not in log_record:
            log_record['module'] = f"{record.filename}:{record.lineno}"

        # 함수명 추가
        if 'funcName' not in log_record:
            log_record['function'] = record.funcName

        # 추가 컨텍스트 정보 추가 (LoggerAdapter에서 제공)
        if hasattr(record, 'context') and record.context:
            log_record['context'] = record.context

        # 예외 정보 추가
        if record.exc_info:
            log_record['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': record.exc_text or '',
            }

        # 타임스탐프 추가
        if 'asctime' not in log_record:
            log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'


class ContextFilter(logging.Filter):
    """
    로그 컨텍스트 필터

    LoggerAdapter의 추가 정보를 필터를 통해 전달합니다.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """필터 적용"""
        return True


class StructuredLogger:
    """
    구조화된 JSON 로거

    파일 및 콘솔 출력을 지원하고, 추가 컨텍스트를 포함할 수 있습니다.
    """

    _loggers: Dict[str, logging.Logger] = {}
    _configured = False

    def __init__(self, name: str, log_dir: Optional[str] = None):
        """
        StructuredLogger 초기화

        Args:
            name: 로거 이름
            log_dir: 로그 파일 디렉토리 (기본값: ./logs)
        """
        self.name = name
        self.log_dir = log_dir or os.path.join(os.getcwd(), "logs")

        # 로그 디렉토리 생성
        os.makedirs(self.log_dir, exist_ok=True)

        # 로거 생성 또는 재사용
        if name not in self._loggers:
            self.logger = self._create_logger(name)
            self._loggers[name] = self.logger
        else:
            self.logger = self._loggers[name]

        # LoggerAdapter로 컨텍스트 정보 지원
        self.adapter = logging.LoggerAdapter(self.logger, {})

    def _create_logger(self, name: str) -> logging.Logger:
        """
        로거 생성

        Args:
            name: 로거 이름

        Returns:
            구성된 로거
        """
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        # 기존 핸들러 제거 (중복 방지)
        logger.handlers = []

        # JSON 포매터 생성
        json_formatter = StructuredFormatter()

        # 파일 핸들러 (JSON 형식)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(self.log_dir, f"{name}.log"),
            maxBytes=10485760,  # 10MB
            backupCount=10,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(json_formatter)
        logger.addHandler(file_handler)

        # 콘솔 핸들러 (JSON 형식, INFO 레벨 이상)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(json_formatter)
        logger.addHandler(console_handler)

        # 필터 추가
        logger.addFilter(ContextFilter())

        # 로거 전파 비활성화
        logger.propagate = False

        return logger

    def debug(self, message: str, **kwargs) -> None:
        """DEBUG 레벨 로깅"""
        self._log_with_context(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """INFO 레벨 로깅"""
        self._log_with_context(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """WARNING 레벨 로깅"""
        self._log_with_context(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """ERROR 레벨 로깅"""
        self._log_with_context(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """CRITICAL 레벨 로깅"""
        self._log_with_context(logging.CRITICAL, message, **kwargs)

    def _log_with_context(self, level: int, message: str, **kwargs) -> None:
        """
        컨텍스트 정보를 포함하여 로깅

        Args:
            level: 로그 레벨
            message: 로그 메시지
            **kwargs: 추가 컨텍스트 정보
        """
        if kwargs:
            # LoggerAdapter의 extra 딕셔너리로 컨텍스트 전달
            self.adapter.log(level, message, extra={'context': kwargs})
        else:
            self.logger.log(level, message)

    def get_logger(self) -> logging.Logger:
        """내부 로거 반환"""
        return self.logger


# 전역 로거 인스턴스
_global_loggers: Dict[str, StructuredLogger] = {}


def get_logger(name: str, log_dir: Optional[str] = None) -> StructuredLogger:
    """
    구조화된 로거 인스턴스 반환

    Args:
        name: 로거 이름 (일반적으로 __name__ 사용)
        log_dir: 로그 파일 디렉토리

    Returns:
        StructuredLogger 인스턴스
    """
    if name not in _global_loggers:
        _global_loggers[name] = StructuredLogger(name, log_dir)
    return _global_loggers[name]


def configure_root_logger(log_dir: Optional[str] = None, level: int = logging.INFO) -> None:
    """
    루트 로거 설정

    Args:
        log_dir: 로그 파일 디렉토리
        level: 로그 레벨
    """
    root_logger = get_logger("coin_hts", log_dir)
    root_logger.get_logger().setLevel(level)
