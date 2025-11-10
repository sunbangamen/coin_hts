"""
Slack 알림 구현

Slack Webhook을 통한 메시지 전송
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import aiohttp
from enum import Enum


class AlertLevel(str, Enum):
    """알림 레벨"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SlackNotifier:
    """
    Slack 알림 전송자

    Slack Webhook URL을 통해 메시지를 전송합니다.
    """

    # 레벨별 색상
    LEVEL_COLORS = {
        AlertLevel.INFO: "#36a64f",      # 녹색
        AlertLevel.WARNING: "#ff9900",   # 주황색
        AlertLevel.ERROR: "#e74c3c",     # 빨강색
        AlertLevel.CRITICAL: "#c0392b",  # 진한 빨강색
    }

    # 레벨별 이모지
    LEVEL_EMOJIS = {
        AlertLevel.INFO: "ℹ️",
        AlertLevel.WARNING: "⚠️",
        AlertLevel.ERROR: "❌",
        AlertLevel.CRITICAL: "🚨",
    }

    def __init__(self, webhook_url: Optional[str] = None):
        """
        SlackNotifier 초기화

        Args:
            webhook_url: Slack Webhook URL (환경변수 SLACK_WEBHOOK_URL에서 로드 가능)
        """
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        if not self.webhook_url:
            raise ValueError("Slack Webhook URL이 설정되지 않았습니다. SLACK_WEBHOOK_URL 환경변수를 확인하세요.")

    async def send(
        self,
        title: str,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
        details: Optional[Dict[str, Any]] = None,
        channel: Optional[str] = None,
    ) -> bool:
        """
        Slack 메시지 전송

        Args:
            title: 메시지 제목
            message: 메시지 본문
            level: 알림 레벨
            details: 추가 상세 정보
            channel: 대상 채널 (선택사항)

        Returns:
            성공 여부
        """
        try:
            payload = self._build_payload(title, message, level, details, channel)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return response.status == 200

        except Exception as e:
            print(f"❌ Slack 메시지 전송 실패: {e}")
            return False

    def send_sync(
        self,
        title: str,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
        details: Optional[Dict[str, Any]] = None,
        channel: Optional[str] = None,
    ) -> bool:
        """
        Slack 메시지 동기 전송

        Args:
            title: 메시지 제목
            message: 메시지 본문
            level: 알림 레벨
            details: 추가 상세 정보
            channel: 대상 채널

        Returns:
            성공 여부
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 이미 실행 중인 이벤트 루프에서는 async 호출 불가
                # 대신 스레드에서 실행
                import threading
                result = [False]

                def run_async():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        result[0] = new_loop.run_until_complete(
                            self.send(title, message, level, details, channel)
                        )
                    finally:
                        new_loop.close()

                thread = threading.Thread(target=run_async)
                thread.daemon = True
                thread.start()
                thread.join(timeout=15)
                return result[0]
            else:
                return loop.run_until_complete(
                    self.send(title, message, level, details, channel)
                )
        except Exception as e:
            print(f"❌ Slack 메시지 동기 전송 실패: {e}")
            return False

    def _build_payload(
        self,
        title: str,
        message: str,
        level: AlertLevel,
        details: Optional[Dict[str, Any]] = None,
        channel: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Slack Webhook 페이로드 생성

        Args:
            title: 제목
            message: 메시지
            level: 레벨
            details: 상세 정보
            channel: 채널

        Returns:
            Webhook 페이로드
        """
        emoji = self.LEVEL_EMOJIS.get(level, "📢")
        color = self.LEVEL_COLORS.get(level, "#808080")

        # 필드 생성
        fields = []
        if details:
            for key, value in details.items():
                fields.append({
                    "title": key,
                    "value": str(value),
                    "short": True if len(str(value)) < 50 else False,
                })

        payload = {
            "text": f"{emoji} {title}",
            "attachments": [
                {
                    "fallback": message,
                    "color": color,
                    "title": title,
                    "text": message,
                    "fields": fields,
                    "footer": "Coin HTS Monitoring",
                    "ts": int(datetime.utcnow().timestamp()),
                }
            ],
        }

        if channel:
            payload["channel"] = channel

        return payload

    async def send_health_check(
        self,
        status: str,
        checks: Dict[str, Any],
        alerts: Optional[list] = None,
    ) -> bool:
        """
        헬스 체크 알림 전송

        Args:
            status: 종합 상태 (HEALTHY, WARNING, CRITICAL)
            checks: 체크 결과
            alerts: 알림 목록

        Returns:
            성공 여부
        """
        if status == "HEALTHY":
            level = AlertLevel.INFO
        elif status == "WARNING":
            level = AlertLevel.WARNING
        else:
            level = AlertLevel.CRITICAL

        message = f"Status: {status}\n"
        for check, result in checks.items():
            message += f"- {check}: {result}\n"

        details = {}
        if alerts:
            details["Alerts"] = "\n".join(alerts)

        return await self.send(
            title="Health Check Report",
            message=message,
            level=level,
            details=details,
        )

    async def send_backup_alert(
        self,
        backup_type: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        백업 알림 전송

        Args:
            backup_type: 백업 유형 (postgresql, redis, results, s3)
            status: 상태 (success, failure, warning)
            details: 상세 정보

        Returns:
            성공 여부
        """
        level_map = {
            "success": AlertLevel.INFO,
            "warning": AlertLevel.WARNING,
            "failure": AlertLevel.ERROR,
        }

        title = f"Backup Alert: {backup_type.upper()}"
        message = f"Status: {status.upper()}"

        if details:
            message += "\n\nDetails:"
            for key, value in details.items():
                message += f"\n- {key}: {value}"

        return await self.send(
            title=title,
            message=message,
            level=level_map.get(status, AlertLevel.WARNING),
            details=details or {},
        )

    async def send_performance_alert(
        self,
        metric: str,
        value: float,
        threshold: float,
        unit: str = "",
    ) -> bool:
        """
        성능 알림 전송

        Args:
            metric: 메트릭 이름
            value: 현재 값
            threshold: 임계값
            unit: 단위

        Returns:
            성공 여부
        """
        exceeded = value > threshold
        level = AlertLevel.WARNING if exceeded else AlertLevel.INFO

        message = f"{metric}: {value}{unit}\nThreshold: {threshold}{unit}"

        details = {
            "Current": f"{value}{unit}",
            "Threshold": f"{threshold}{unit}",
            "Status": "⚠️ Exceeded" if exceeded else "✅ Normal",
        }

        return await self.send(
            title=f"Performance Alert: {metric}",
            message=message,
            level=level,
            details=details,
        )
