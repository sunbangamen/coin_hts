"""
자동 백업 스케줄러 (Task 3.7)

APScheduler 기반으로 정기적인 백업을 자동화합니다.
"""

import os
import subprocess
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


logger = logging.getLogger(__name__)


class BackupScheduler:
    """
    자동 백업 스케줄러

    APScheduler를 사용하여 주기적인 백업 작업을 관리합니다.
    """

    def __init__(self, script_dir: Optional[str] = None):
        """
        BackupScheduler 초기화

        Args:
            script_dir: 백업 스크립트 경로 (기본값: ./scripts)
        """
        self.script_dir = script_dir or os.path.join(os.getcwd(), "scripts")
        self.backup_script = os.path.join(self.script_dir, "backup.sh")

        # APScheduler 생성
        self.scheduler = BackgroundScheduler(daemon=True)
        self.jobs: Dict[str, Any] = {}
        self.is_running = False

        logger.info(f"BackupScheduler 초기화: {self.backup_script}")

    def start(self) -> None:
        """스케줄러 시작"""
        if self.is_running:
            logger.warning("스케줄러가 이미 실행 중입니다")
            return

        try:
            self.scheduler.start()
            self.is_running = True
            logger.info("스케줄러 시작 완료")
        except Exception as e:
            logger.error(f"스케줄러 시작 실패: {e}")

    def stop(self) -> None:
        """스케줄러 정지"""
        if not self.is_running:
            logger.warning("스케줄러가 실행 중이지 않습니다")
            return

        try:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("스케줄러 정지 완료")
        except Exception as e:
            logger.error(f"스케줄러 정지 실패: {e}")

    def add_backup_job(
        self,
        job_id: str,
        backup_type: str,
        trigger: str,
        hour: Optional[int] = None,
        minute: Optional[int] = None,
        day_of_week: Optional[int] = None,
    ) -> bool:
        """
        백업 작업 추가

        Args:
            job_id: 작업 ID (고유값)
            backup_type: 백업 타입 (all, postgres, redis, results, s3)
            trigger: 트리거 타입 ('cron' 또는 'interval')
            hour: 시간 (0-23)
            minute: 분 (0-59)
            day_of_week: 요일 (0-6, 0=월)

        Returns:
            성공 여부
        """
        try:
            if trigger == "cron":
                cron_trigger = CronTrigger(
                    hour=hour or 0,
                    minute=minute or 0,
                    day_of_week=day_of_week,
                )
            else:
                logger.error(f"지원하지 않는 트리거: {trigger}")
                return False

            # 백업 작업 함수
            def backup_job():
                self._run_backup(backup_type)

            # 작업 추가
            job = self.scheduler.add_job(
                backup_job,
                trigger=cron_trigger,
                id=job_id,
                name=f"{backup_type} Backup",
                replace_existing=True,
            )

            self.jobs[job_id] = {
                "backup_type": backup_type,
                "trigger": trigger,
                "hour": hour,
                "minute": minute,
                "day_of_week": day_of_week,
                "next_run_time": job.next_run_time,
            }

            logger.info(f"백업 작업 추가: {job_id} ({backup_type})")
            return True

        except Exception as e:
            logger.error(f"백업 작업 추가 실패: {job_id} - {e}")
            return False

    def remove_backup_job(self, job_id: str) -> bool:
        """
        백업 작업 제거

        Args:
            job_id: 작업 ID

        Returns:
            성공 여부
        """
        try:
            if job_id in self.jobs:
                self.scheduler.remove_job(job_id)
                del self.jobs[job_id]
                logger.info(f"백업 작업 제거: {job_id}")
                return True
            else:
                logger.warning(f"작업을 찾을 수 없음: {job_id}")
                return False

        except Exception as e:
            logger.error(f"백업 작업 제거 실패: {job_id} - {e}")
            return False

    def get_jobs(self) -> Dict[str, Any]:
        """등록된 작업 목록 반환"""
        result = {}
        for job_id, job_info in self.jobs.items():
            result[job_id] = {
                **job_info,
                "status": "scheduled" if self.is_running else "stopped",
            }
        return result

    def _run_backup(self, backup_type: str) -> None:
        """
        백업 작업 실행

        Args:
            backup_type: 백업 타입
        """
        try:
            if not os.path.exists(self.backup_script):
                logger.error(f"백업 스크립트를 찾을 수 없음: {self.backup_script}")
                return

            logger.info(f"백업 작업 시작: {backup_type}")

            # 백업 스크립트 실행
            result = subprocess.run(
                ["/bin/bash", self.backup_script, backup_type],
                capture_output=True,
                text=True,
                timeout=3600,  # 1시간 타임아웃
            )

            if result.returncode == 0:
                logger.info(f"백업 성공: {backup_type}")
            else:
                logger.error(f"백업 실패: {backup_type}\n{result.stderr}")

        except subprocess.TimeoutExpired:
            logger.error(f"백업 타임아웃: {backup_type} (1시간 초과)")
        except Exception as e:
            logger.error(f"백업 실행 중 오류: {backup_type} - {e}")

    def get_status(self) -> Dict[str, Any]:
        """스케줄러 상태 반환"""
        return {
            "is_running": self.is_running,
            "jobs_count": len(self.jobs),
            "jobs": self.get_jobs(),
            "scheduler_state": "running" if self.is_running else "stopped",
        }


# 전역 스케줄러 인스턴스
_global_scheduler: Optional[BackupScheduler] = None


def get_backup_scheduler(script_dir: Optional[str] = None) -> BackupScheduler:
    """
    전역 백업 스케줄러 반환

    Args:
        script_dir: 백업 스크립트 경로

    Returns:
        BackupScheduler 인스턴스
    """
    global _global_scheduler

    if _global_scheduler is None:
        _global_scheduler = BackupScheduler(script_dir)

    return _global_scheduler


def initialize_default_backup_schedule(scheduler: BackupScheduler) -> None:
    """
    기본 백업 스케줄 초기화

    Args:
        scheduler: BackupScheduler 인스턴스
    """
    # 매일 자정에 전체 백업
    scheduler.add_backup_job(
        job_id="daily_full_backup",
        backup_type="all",
        trigger="cron",
        hour=0,
        minute=0,
    )

    # 매주 일요일 오전 1시에 오래된 백업 정리
    scheduler.add_backup_job(
        job_id="weekly_cleanup",
        backup_type="cleanup",
        trigger="cron",
        hour=1,
        minute=0,
        day_of_week=6,  # Sunday
    )

    logger.info("기본 백업 스케줄 초기화 완료")


def start_default_scheduler(script_dir: Optional[str] = None) -> BackupScheduler:
    """
    기본 설정으로 스케줄러 시작

    Args:
        script_dir: 백업 스크립트 경로

    Returns:
        시작된 BackupScheduler 인스턴스
    """
    scheduler = get_backup_scheduler(script_dir)

    if not scheduler.is_running:
        initialize_default_backup_schedule(scheduler)
        scheduler.start()

    return scheduler
