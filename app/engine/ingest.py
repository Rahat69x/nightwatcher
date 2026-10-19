"""
NightWatcher Engine — Ingest
Central entry point: event dict -> dedupe -> score -> create/update alert -> route.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.engine.actions import block_ip, log_action
from app.engine.dedupe import make_fingerprint
from app.engine.router import route_alert
from app.engine.scoring import score_event
from app.engine.summarizer import generate_summary
from app.models import Alert, AlertStatus, Event, Severity

log = logging.getLogger(__name__)
settings = get_settings()


async def ingest_event(
    db: AsyncSession,
    event_type: str,
    source: str,
    details: Dict[str, Any],
) -> Alert:
    """
    Full pipeline:
    1. Store raw event
    2. Score severity
    3. Deduplicate / group
    4. Auto-action (block IP if needed)
    5. Generate plain-language summary
    6. Route to notifiers
    """

    # 1. Raw event
    raw_event = Event(
        type=event_type,
        source=source,
        details=json.dumps(details),
    )
    db.add(raw_event)
    await db.flush()  # get raw_event.id

    # 2. Score
    score, severity = score_event(event_type, details)

    # 3. Deduplicate
    fingerprint = make_fingerprint(event_type, details)
    window_start = datetime.now(timezone.utc) - timedelta(
        minutes=settings.dedupe_window_minutes
    )

    result = await db.execute(
        select(Alert).where(
            Alert.fingerprint == fingerprint,
            Alert.last_seen >= window_start,
            Alert.status != AlertStatus.RESOLVED,
        )
    )
    existing_alert = result.scalar_one_or_none()

    if existing_alert:
        # Duplicate — update count, don't re-notify
        existing_alert.count += 1
        existing_alert.last_seen = datetime.now(timezone.utc)
        existing_alert.score = max(existing_alert.score, score)
        severity_order = {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3, Severity.CRITICAL: 4}
        if severity_order.get(severity, 0) > severity_order.get(existing_alert.severity, 0):
            existing_alert.severity = severity
        raw_event.alert_id = existing_alert.id
        await db.commit()
        log.info(f"Grouped event into alert {existing_alert.id} (count={existing_alert.count})")
        return existing_alert

    # 4. Auto-action
    source_ip = details.get("source_ip")
    if source_ip and event_type in (
        "brute_force", "login_success_after_brute", "credential_stuffing"
    ):
        await _do_block(db, source_ip, event_type)

    # 5. Plain-language summary
    summary = await generate_summary(
        event_type, details, severity, settings.gemini_api_key
    )

    # 6. Create alert
    now = datetime.now(timezone.utc)
    alert = Alert(
        type=event_type,
        fingerprint=fingerprint,
        severity=severity,
        score=score,
        status=AlertStatus.NEW,
        summary=summary,
        source_ip=source_ip,
        source_host=details.get("source_host"),
        extra=json.dumps(details),
        first_seen=now,
        last_seen=now,
        next_escalation_at=now + timedelta(seconds=settings.escalation_tier1_seconds),
    )
    db.add(alert)
    await db.flush()
    raw_event.alert_id = alert.id

    # Log auto-block action
    if source_ip and event_type in (
        "brute_force", "login_success_after_brute", "credential_stuffing"
    ):
        await log_action(db, alert.id, "block_ip", source_ip, f"auto-blocked by ingest")

    await db.commit()
    await db.refresh(alert)

    # 7. Route to notifiers
    try:
        await route_alert(alert)
        alert.status = AlertStatus.NOTIFIED
        await db.commit()
    except Exception as e:
        log.error(f"Routing failed for alert {alert.id}: {e}")

    log.info(f"New alert {alert.id} [{severity.value}] score={score:.0f}: {event_type}")
    return alert


async def _do_block(db: AsyncSession, ip: str, reason: str) -> None:
    try:
        await block_ip(db, ip, reason)
    except Exception as e:
        log.error(f"Auto-block failed for {ip}: {e}")
