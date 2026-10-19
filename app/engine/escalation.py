"""
NightWatcher Engine — Escalation
If an alert is not acknowledged within the tier1 window, escalate to the next channel.
Tier 1 (3 min): escalate one level up.
Tier 2 (5 more min): place a voice call regardless of severity.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AlertStatus, Severity

log = logging.getLogger(__name__)


async def run_escalations(db: AsyncSession) -> None:
    """Called every minute by the scheduler."""
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Alert).where(
            Alert.status.in_([AlertStatus.NEW, AlertStatus.NOTIFIED]),
            Alert.next_escalation_at <= now,
        )
    )
    alerts = result.scalars().all()

    for alert in alerts:
        await _escalate(alert, db, now)


async def _escalate(alert: Alert, db: AsyncSession, now: datetime) -> None:
    from app.notifiers.telegram import send_telegram_alert
    from app.notifiers.sms import send_sms_alert
    from app.notifiers.voice import place_voice_call
    from app.notifiers.email import send_email_alert
    from app.config import get_settings

    settings = get_settings()

    alert.escalation_level += 1
    level = alert.escalation_level
    log.info(f"Escalating alert {alert.id} to level {level}")

    try:
        if level == 1:
            # Escalate to Telegram if not already done
            await send_telegram_alert(alert, escalation=True)
            # Next escalation in tier2 seconds
            from datetime import timedelta
            alert.next_escalation_at = now + timedelta(
                seconds=settings.escalation_tier2_seconds
            )
        elif level == 2:
            # Final escalation: voice call
            await place_voice_call(alert)
            # No more automatic escalation after voice
            alert.next_escalation_at = None
        else:
            alert.next_escalation_at = None

        alert.status = AlertStatus.NOTIFIED
        await db.commit()

    except Exception as e:
        log.error(f"Escalation failed for alert {alert.id}: {e}")
