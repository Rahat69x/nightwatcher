"""NightWatcher — Email notifier (smtplib, no extra library needed)"""
from __future__ import annotations
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import get_settings
from app.models import Alert

log = logging.getLogger(__name__)
settings = get_settings()

SEVERITY_EMOJI = {
    "low": "🔵",
    "medium": "🟡",
    "high": "🟠",
    "critical": "🔴",
}


def _build_html(alert: Alert) -> str:
    emoji = SEVERITY_EMOJI.get(alert.severity.value, "⚪")
    color = {"low": "#3b82f6", "medium": "#f59e0b",
              "high": "#f97316", "critical": "#ef4444"}.get(alert.severity.value, "#6b7280")
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px;">
  <div style="max-width:600px;margin:auto;background:#1e293b;border-radius:12px;
              border-left:6px solid {color};padding:24px;">
    <h2 style="margin:0 0 8px;color:{color};">{emoji} NightWatcher Alert</h2>
    <p style="font-size:20px;font-weight:bold;margin:0 0 16px;">{alert.summary}</p>
    <table style="width:100%;border-collapse:collapse;">
      <tr><td style="padding:6px 0;color:#94a3b8;">Severity</td>
          <td style="font-weight:bold;color:{color};">{alert.severity.value.upper()}</td></tr>
      <tr><td style="padding:6px 0;color:#94a3b8;">Score</td>
          <td>{alert.score:.0f}/100</td></tr>
      <tr><td style="padding:6px 0;color:#94a3b8;">Type</td>
          <td>{alert.type}</td></tr>
      <tr><td style="padding:6px 0;color:#94a3b8;">Source IP</td>
          <td>{alert.source_ip or 'N/A'}</td></tr>
      <tr><td style="padding:6px 0;color:#94a3b8;">First seen</td>
          <td>{alert.first_seen.strftime('%Y-%m-%d %H:%M UTC') if alert.first_seen else 'N/A'}</td></tr>
      <tr><td style="padding:6px 0;color:#94a3b8;">Count</td>
          <td>{alert.count}</td></tr>
    </table>
    <div style="margin-top:20px;text-align:center;">
      <a href="{settings.base_url}/dashboard/alerts/{alert.id}"
         style="background:{color};color:white;padding:10px 24px;border-radius:8px;
                text-decoration:none;font-weight:bold;">View on Dashboard</a>
    </div>
    <p style="margin-top:16px;font-size:12px;color:#475569;text-align:center;">
      NightWatcher — Always watching. Loudest when it matters.
    </p>
  </div>
</body>
</html>
"""


async def send_email_alert(alert: Alert, escalation: bool = False) -> None:
    """Send alert as a styled HTML email. Silently fails if SMTP not configured."""
    if not settings.smtp_user or not settings.alert_to_email_list:
        log.warning("Email not configured — skipping email notification")
        return

    subject_prefix = "🚨 ESCALATED: " if escalation else f"[NightWatcher] "
    subject = f"{subject_prefix}{alert.severity.value.upper()} — {alert.type.replace('_', ' ').title()}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.alert_from_email
    msg["To"] = ", ".join(settings.alert_to_email_list)
    msg.attach(MIMEText(alert.summary, "plain"))
    msg.attach(MIMEText(_build_html(alert), "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.sendmail(
                settings.alert_from_email,
                settings.alert_to_email_list,
                msg.as_string(),
            )
        log.info(f"Email sent for alert {alert.id}")
    except Exception as e:
        log.error(f"Email failed for alert {alert.id}: {e}")
        raise
