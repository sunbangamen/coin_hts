"""
Task 3.7: 모니터링 API

로깅, 알림, 백업 상태 조회 엔드포인트
"""

import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
import logging

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 로그 관련 엔드포인트
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/logs")
async def get_logs(
    logger_name: Optional[str] = Query(None, description="로거 이름 필터"),
    level: Optional[str] = Query(None, description="로그 레벨 필터 (INFO, WARNING, ERROR)"),
    limit: int = Query(100, ge=1, le=1000, description="반환할 로그 수"),
) -> Dict[str, Any]:
    """
    최근 로그 조회

    Query Parameters:
    - logger_name: 특정 로거의 로그만 조회
    - level: 특정 레벨의 로그만 조회
    - limit: 반환할 로그 수 (기본값: 100)

    Returns:
        최근 로그 목록
    """
    logs_dir = Path("logs")

    if not logs_dir.exists():
        return {
            "status": "success",
            "logs": [],
            "count": 0,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    all_logs = []

    # 로그 파일 수집
    for log_file in sorted(logs_dir.glob("*.log"), reverse=True):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        log_entry = json.loads(line)

                        # 필터링
                        if logger_name and log_entry.get("logger") != logger_name:
                            continue
                        if level and log_entry.get("level") != level:
                            continue

                        all_logs.append(log_entry)

                        if len(all_logs) >= limit:
                            break
                    except json.JSONDecodeError:
                        continue

            if len(all_logs) >= limit:
                break

        except Exception as e:
            logger.warning(f"로그 파일 읽기 실패: {log_file} - {e}")

    # 시간순으로 정렬
    all_logs.sort(
        key=lambda x: x.get("timestamp", ""),
        reverse=True
    )

    return {
        "status": "success",
        "logs": all_logs[:limit],
        "count": len(all_logs[:limit]),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/logs/summary")
async def get_logs_summary(
    hours: int = Query(24, ge=1, le=168, description="조회 기간 (시간)"),
) -> Dict[str, Any]:
    """
    로그 요약 통계

    Query Parameters:
    - hours: 조회 기간 (기본값: 24시간)

    Returns:
        로그 레벨별 개수
    """
    logs_dir = Path("logs")

    if not logs_dir.exists():
        return {
            "status": "success",
            "summary": {
                "DEBUG": 0,
                "INFO": 0,
                "WARNING": 0,
                "ERROR": 0,
                "CRITICAL": 0,
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    summary = {
        "DEBUG": 0,
        "INFO": 0,
        "WARNING": 0,
        "ERROR": 0,
        "CRITICAL": 0,
    }

    cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"

    try:
        for log_file in logs_dir.glob("*.log"):
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        log_entry = json.loads(line)

                        # 시간 필터링
                        if log_entry.get("timestamp", "") < cutoff_time:
                            continue

                        level = log_entry.get("level", "INFO")
                        if level in summary:
                            summary[level] += 1
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        logger.warning(f"로그 요약 생성 실패: {e}")

    return {
        "status": "success",
        "summary": summary,
        "period_hours": hours,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ═══════════════════════════════════════════════════════════════════════════
# 백업 관련 엔드포인트
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/backups")
async def get_backups(
    backup_type: Optional[str] = Query(None, description="백업 타입 필터"),
) -> Dict[str, Any]:
    """
    백업 상태 조회

    Query Parameters:
    - backup_type: 백업 타입 필터 (postgresql, redis, results, s3)

    Returns:
        백업 파일 목록 및 통계
    """
    backup_dir = Path("backups")

    if not backup_dir.exists():
        return {
            "status": "success",
            "backups": [],
            "total_size_mb": 0.0,
            "count": 0,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    backups = []
    total_size = 0

    try:
        # 백업 파일 수집
        for backup_file in sorted(backup_dir.rglob("*.gz"), reverse=True):
            try:
                # 백업 타입 추출
                file_parts = backup_file.parts
                backup_subtype = file_parts[-2] if len(file_parts) > 1 else "unknown"

                # 필터링
                if backup_type and backup_subtype != backup_type:
                    continue

                # 파일 정보
                stat = backup_file.stat()
                size_mb = stat.st_size / (1024 * 1024)
                total_size += stat.st_size

                backups.append({
                    "type": backup_subtype,
                    "filename": backup_file.name,
                    "size_mb": round(size_mb, 2),
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat() + "Z",
                })
            except Exception as e:
                logger.warning(f"백업 파일 정보 추출 실패: {backup_file} - {e}")

    except Exception as e:
        logger.warning(f"백업 조회 실패: {e}")

    return {
        "status": "success",
        "backups": backups,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "count": len(backups),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/backups/summary")
async def get_backups_summary() -> Dict[str, Any]:
    """백업 요약 통계"""
    backup_dir = Path("backups")

    summary = {
        "postgresql": {"count": 0, "total_size_mb": 0.0},
        "redis": {"count": 0, "total_size_mb": 0.0},
        "results": {"count": 0, "total_size_mb": 0.0},
    }

    if backup_dir.exists():
        try:
            for backup_file in backup_dir.rglob("*.gz"):
                backup_type = backup_file.parts[-2] if len(backup_file.parts) > 1 else "unknown"

                if backup_type in summary:
                    stat = backup_file.stat()
                    size_mb = stat.st_size / (1024 * 1024)

                    summary[backup_type]["count"] += 1
                    summary[backup_type]["total_size_mb"] += size_mb
        except Exception as e:
            logger.warning(f"백업 요약 생성 실패: {e}")

    # 크기 반올림
    for key in summary:
        summary[key]["total_size_mb"] = round(summary[key]["total_size_mb"], 2)

    return {
        "status": "success",
        "summary": summary,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ═══════════════════════════════════════════════════════════════════════════
# 스케줄러 관련 엔드포인트
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/scheduler")
async def get_scheduler_status() -> Dict[str, Any]:
    """
    백업 스케줄러 상태 조회

    Returns:
        스케줄러 상태 및 등록된 작업 목록
    """
    try:
        from backend.app.backup_scheduler import get_backup_scheduler

        scheduler = get_backup_scheduler()
        status = scheduler.get_status()

        return {
            "status": "success",
            "data": status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.error(f"스케줄러 상태 조회 실패: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


# ═══════════════════════════════════════════════════════════════════════════
# 알림 설정 엔드포인트
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/alerts/config")
async def get_alerts_config() -> Dict[str, Any]:
    """
    알림 설정 조회

    Returns:
        Slack, Email 알림 설정 상태
    """
    slack_enabled = bool(os.getenv("SLACK_WEBHOOK_URL"))
    email_enabled = all([
        os.getenv("SMTP_HOST"),
        os.getenv("SMTP_USER"),
        os.getenv("SMTP_PASSWORD"),
    ])

    return {
        "status": "success",
        "alerts": {
            "slack": {
                "enabled": slack_enabled,
                "webhook_url": os.getenv("SLACK_WEBHOOK_URL", "")[:20] + "..." if slack_enabled else "",
            },
            "email": {
                "enabled": email_enabled,
                "smtp_host": os.getenv("SMTP_HOST", ""),
                "from_addr": os.getenv("SMTP_FROM_ADDR", ""),
            },
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ═══════════════════════════════════════════════════════════════════════════
# 헬스 체크 엔드포인트
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/health")
async def get_health() -> Dict[str, Any]:
    """
    시스템 헬스 체크

    Returns:
        시스템 상태 정보
    """
    from psutil import virtual_memory, disk_usage, cpu_percent

    try:
        memory = virtual_memory()
        disk = disk_usage("/")
        cpu = cpu_percent(interval=1)

        health_status = "HEALTHY"
        warnings = []

        if cpu > 80:
            warnings.append(f"CPU 사용률 높음: {cpu}%")
            health_status = "WARNING"

        if memory.percent > 80:
            warnings.append(f"메모리 사용률 높음: {memory.percent}%")
            health_status = "WARNING"

        if disk.percent > 80:
            warnings.append(f"디스크 사용률 높음: {disk.percent}%")
            health_status = "WARNING"

        return {
            "status": "success",
            "health": {
                "overall": health_status,
                "cpu_percent": cpu,
                "memory": {
                    "percent": memory.percent,
                    "available_mb": round(memory.available / (1024 * 1024), 2),
                },
                "disk": {
                    "percent": disk.percent,
                    "free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
                },
            },
            "warnings": warnings,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.error(f"헬스 체크 실패: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
