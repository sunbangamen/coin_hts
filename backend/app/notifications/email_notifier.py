"""
Email 알림 구현

SMTP를 통한 이메일 전송
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List
from datetime import datetime


class EmailNotifier:
    """
    Email 알림 전송자

    SMTP를 통해 이메일을 전송합니다.
    """

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_addr: Optional[str] = None,
        use_tls: bool = True,
    ):
        """
        EmailNotifier 초기화

        Args:
            smtp_host: SMTP 서버 주소 (환경변수 SMTP_HOST)
            smtp_port: SMTP 포트 (환경변수 SMTP_PORT)
            smtp_user: SMTP 사용자명 (환경변수 SMTP_USER)
            smtp_password: SMTP 비밀번호 (환경변수 SMTP_PASSWORD)
            from_addr: 발신 이메일 (환경변수 SMTP_FROM_ADDR)
            use_tls: TLS 사용 여부
        """
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = smtp_user or os.getenv("SMTP_USER")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.from_addr = from_addr or os.getenv("SMTP_FROM_ADDR") or self.smtp_user
        self.use_tls = use_tls

        if not self.smtp_host:
            raise ValueError("SMTP 설정이 완료되지 않았습니다. 환경변수를 확인하세요.")

    def send(
        self,
        to_addresses: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> bool:
        """
        이메일 전송

        Args:
            to_addresses: 수신자 이메일 주소 리스트
            subject: 제목
            body: 본문 (텍스트)
            html_body: 본문 (HTML, 선택사항)

        Returns:
            성공 여부
        """
        try:
            # 메일 메시지 생성
            msg = MIMEMultipart("alternative")
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(to_addresses)
            msg["Subject"] = subject
            msg["Date"] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

            # 텍스트 부분
            part1 = MIMEText(body, "plain", "utf-8")
            msg.attach(part1)

            # HTML 부분 (있으면)
            if html_body:
                part2 = MIMEText(html_body, "html", "utf-8")
                msg.attach(part2)

            # SMTP 서버 연결
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                if self.use_tls:
                    server.starttls()

                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)

                # 메일 전송
                server.sendmail(self.from_addr, to_addresses, msg.as_string())

            print(f"✅ 이메일 전송 성공: {', '.join(to_addresses)}")
            return True

        except Exception as e:
            print(f"❌ 이메일 전송 실패: {e}")
            return False

    def send_health_check_alert(
        self,
        to_addresses: List[str],
        status: str,
        checks: Dict[str, Any],
        alerts: Optional[List[str]] = None,
    ) -> bool:
        """
        헬스 체크 알림 이메일 전송

        Args:
            to_addresses: 수신자 이메일 주소
            status: 상태 (HEALTHY, WARNING, CRITICAL)
            checks: 체크 결과
            alerts: 알림 목록

        Returns:
            성공 여부
        """
        subject = f"[{status.upper()}] Health Check Alert"

        # 텍스트 본문
        body = f"""
System Health Check Report
==========================

Status: {status}
Timestamp: {datetime.utcnow().isoformat()}Z

Checks:
"""

        for check, result in checks.items():
            body += f"  - {check}: {result}\n"

        if alerts:
            body += "\nAlerts:\n"
            for alert in alerts:
                body += f"  - {alert}\n"

        body += """
---
This is an automated alert from Coin HTS Monitoring System.
Please do not reply to this email.
"""

        # HTML 본문
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; }}
        .header {{ background-color: #f5f5f5; padding: 20px; text-align: center; }}
        .status-{status.lower()} {{
            color: {'#27ae60' if status == 'HEALTHY' else '#f39c12' if status == 'WARNING' else '#e74c3c'};
            font-weight: bold;
            font-size: 18px;
        }}
        .checks {{ margin: 20px 0; }}
        .check-item {{ padding: 10px; border-left: 4px solid #3498db; margin: 5px 0; }}
        .footer {{ color: #999; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>System Health Check Report</h1>
        </div>

        <div class="status-{status.lower()}">Status: {status}</div>
        <p>Timestamp: {datetime.utcnow().isoformat()}Z</p>

        <div class="checks">
            <h3>Checks:</h3>
"""

        for check, result in checks.items():
            html_body += f'            <div class="check-item">{check}: {result}</div>\n'

        if alerts:
            html_body += """            <h3>Alerts:</h3>
"""
            for alert in alerts:
                html_body += f'            <div class="check-item">⚠️ {alert}</div>\n'

        html_body += """        </div>

        <div class="footer">
            <p>This is an automated alert from Coin HTS Monitoring System.</p>
            <p>Please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""

        return self.send(to_addresses, subject, body, html_body)

    def send_backup_alert(
        self,
        to_addresses: List[str],
        backup_type: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        백업 알림 이메일 전송

        Args:
            to_addresses: 수신자 이메일 주소
            backup_type: 백업 유형
            status: 상태 (success, failure, warning)
            details: 상세 정보

        Returns:
            성공 여부
        """
        subject = f"[{status.upper()}] Backup Alert: {backup_type}"

        # 텍스트 본문
        body = f"""
Backup Alert
============

Type: {backup_type}
Status: {status}
Timestamp: {datetime.utcnow().isoformat()}Z

"""

        if details:
            body += "Details:\n"
            for key, value in details.items():
                body += f"  {key}: {value}\n"

        body += """
---
This is an automated alert from Coin HTS Monitoring System.
"""

        # HTML 본문
        status_color = '#27ae60' if status == 'success' else '#f39c12' if status == 'warning' else '#e74c3c'
        status_emoji = '✅' if status == 'success' else '⚠️' if status == 'warning' else '❌'

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; }}
        .header {{ background-color: {status_color}; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; }}
        .details {{ background-color: #f5f5f5; padding: 15px; margin: 10px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{status_emoji} Backup Alert: {backup_type}</h1>
        </div>

        <div class="content">
            <p><strong>Status:</strong> {status.upper()}</p>
            <p><strong>Timestamp:</strong> {datetime.utcnow().isoformat()}Z</p>
"""

        if details:
            html_body += '            <div class="details">\n'
            html_body += "                <h3>Details:</h3>\n"
            for key, value in details.items():
                html_body += f"                <p><strong>{key}:</strong> {value}</p>\n"
            html_body += "            </div>\n"

        html_body += """        </div>
    </div>
</body>
</html>
"""

        return self.send(to_addresses, subject, body, html_body)

    def send_performance_alert(
        self,
        to_addresses: List[str],
        metric: str,
        value: float,
        threshold: float,
        unit: str = "",
    ) -> bool:
        """
        성능 알림 이메일 전송

        Args:
            to_addresses: 수신자 이메일 주소
            metric: 메트릭 이름
            value: 현재 값
            threshold: 임계값
            unit: 단위

        Returns:
            성공 여부
        """
        exceeded = value > threshold
        subject = f"[{'ALERT' if exceeded else 'INFO'}] Performance Alert: {metric}"

        body = f"""
Performance Alert
=================

Metric: {metric}
Current Value: {value}{unit}
Threshold: {threshold}{unit}
Status: {'EXCEEDED' if exceeded else 'NORMAL'}
Timestamp: {datetime.utcnow().isoformat()}Z
"""

        status_color = '#e74c3c' if exceeded else '#27ae60'
        status_text = 'EXCEEDED ⚠️' if exceeded else 'NORMAL ✅'

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; }}
        .header {{ background-color: {status_color}; color: white; padding: 20px; text-align: center; }}
        .metric {{ font-size: 24px; font-weight: bold; color: {status_color}; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Performance Alert: {metric}</h1>
        </div>

        <p><strong>Current Value:</strong> <span class="metric">{value}{unit}</span></p>
        <p><strong>Threshold:</strong> {threshold}{unit}</p>
        <p><strong>Status:</strong> {status_text}</p>
        <p><strong>Timestamp:</strong> {datetime.utcnow().isoformat()}Z</p>
    </div>
</body>
</html>
"""

        return self.send(to_addresses, subject, body, html_body)
