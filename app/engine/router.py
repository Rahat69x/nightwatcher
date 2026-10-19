"""
NightWatcher Engine — Router
Decides which notifiers to call based on severity.
Score 0-39 = email only
Score 40-69 = email + Telegram
Score 70-89 = Telegram + SMS
Score 90-100 = Telegram + voice call
"""
from __future__ import annotations
import asyncio
import logging
from typing import TYPE_CHECKING

from app.models import Alert, Severity

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


async def route_alert(alert: Alert) -> None:
    """Dispatch notifications based on alert severity. Each channel is independent."""
    from app.notifiers.email import send_email_alert
    from app.notifiers.telegram import send_telegram_alert
    from app.notifiers.sms import send_sms_alert
    from app.notifiers.voice import place_voice_call

    tasks = []
    severity = alert.severity

    if severity == Severity.LOW:
        tasks.append(send_email_alert(alert))

    elif severity == Severity.MEDIUM:
        tasks.extend([
            send_email_alert(alert),
            send_telegram_alert(alert),
        ])

    elif severity == Severity.HIGH:
        tasks.extend([
            send_telegram_alert(alert),
            send_sms_alert(alert),
        ])

    elif severity == Severity.CRITICAL:
        tasks.extend([
            send_telegram_alert(alert),
            place_voice_call(alert),
        ])

    # Run all channels concurrently; a failure in one does NOT stop others
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            log.error(f"Notifier {i} failed for alert {alert.id}: {result}")
