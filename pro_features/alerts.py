"""
alerts.py — Discord webhooks + email notifications for system events.

Triggers:
- CPU > N% for K minutes
- RAM > N% sustained
- Temperature > N°C
- Disk space < N GB
- New drivers available
- Scheduler job failed
- License expiry within 7 days
"""

from __future__ import annotations

import json
import smtplib
from email.mime.text import MIMEText
from urllib.request import Request, urlopen

from licensing.license_manager import require_pro


@require_pro
def send_discord(webhook_url: str, title: str, message: str,
                 color: int = 0x4f7ef8) -> bool:
    """Send Discord embed via webhook."""
    payload = {
        "embeds": [{
            "title": f"FSD Pro · {title}",
            "description": message,
            "color": color,
            "footer": {"text": "FreeSystemDoctor PRO"},
        }],
    }
    try:
        req = Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urlopen(req, timeout=5)
        return True
    except Exception:
        return False


@require_pro
def send_email(smtp_host: str, smtp_user: str, smtp_pass: str,
               to_addr: str, subject: str, body: str) -> bool:
    """Send email via SMTP."""
    try:
        msg = MIMEText(body)
        msg["Subject"] = f"[FSD Pro] {subject}"
        msg["From"] = smtp_user
        msg["To"] = to_addr
        with smtplib.SMTP_SSL(smtp_host, 465, timeout=10) as s:
            s.login(smtp_user, smtp_pass)
            s.send_message(msg)
        return True
    except Exception:
        return False


@require_pro
def alert_high_cpu(webhook: str, pct: float, duration_min: int):
    send_discord(
        webhook,
        title="🔥 Wysokie CPU",
        message=f"CPU = {pct:.0f}% przez {duration_min} min. Sprawdź procesy.",
        color=0xfbbf24,
    )


@require_pro
def alert_drivers_available(webhook: str, count: int):
    send_discord(
        webhook,
        title="🚗 Nowe drivers",
        message=f"Znaleziono {count} dostępnych aktualizacji driverów.",
        color=0x4f7ef8,
    )


@require_pro
def alert_temp_critical(webhook: str, component: str, temp_c: float):
    send_discord(
        webhook,
        title=f"🌡️ Krytyczna temperatura: {component}",
        message=f"{component} = {temp_c:.1f}°C. Sprawdź chłodzenie.",
        color=0xf87171,
    )
