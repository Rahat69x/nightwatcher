"""NightWatcher — SMS notifier via Twilio"""
from __future__ import annotations
import logging
from app.config import get_settings
from app.models import Alert

log = logging.getLogger(__name__)
settings = get_settings()


async def send_sms_alert(alert: Alert) -> None:
    """Send short SMS to all configured numbers. Skips if Twilio not configured."""
    if not all([
        settings.twilio_account_sid,
        settings.twilio_auth_token,
        settings.twilio_from_number,
        settings.twilio_to_number_list,
    ]):
        log.warning("Twilio SMS not configured — skipping")
        return

    body = (
        f"🚨 NightWatcher [{alert.severity.value.upper()}]\n"
        f"{alert.summary[:140]}\n"
        f"Alert #{alert.id} — {settings.base_url}/dashboard/alerts/{alert.id}"
    )

    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        for number in settings.twilio_to_number_list:
            client.messages.create(
                body=body,
                from_=settings.twilio_from_number,
                to=number,
            )
        log.info(f"SMS sent for alert {alert.id}")
    except Exception as e:
        log.error(f"SMS failed for alert {alert.id}: {e}")
        raise
