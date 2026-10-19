"""
NightWatcher — Twilio Webhooks & Callbacks
Handles two-way user interactions:
- Twilio Voice call TwiML instructions
- Twilio Voice keypress gather actions (1=ack, 2=block IP, 9=repeat)
- Twilio SMS two-way replies (1/ACK, BLOCK, STATUS)
- Telegram webhook callback actions
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Alert, AlertStatus, BlockedIP, Severity
from app.notifiers.voice import build_twiml_response
from app.engine.actions import block_ip
from app.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/twilio", tags=["twilio"])


@router.get("/voice-twiml")
@router.post("/voice-twiml")
async def voice_twiml_endpoint(
    alert_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Serve TwiML instructions when Twilio places an outbound alert call."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>NightWatcher security alert not found. Goodbye.</Say>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    twiml = build_twiml_response(alert)
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice-action")
async def voice_action_endpoint(
    alert_id: int = Query(...),
    Digits: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle the keypress response from the voice call:
    - Press 1: Acknowledge alert
    - Press 2: Block attacker IP & resolve
    - Press 9: Repeat alert message
    """
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Alert not found. Goodbye.</Say>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    digit = (Digits or "").strip()
    log.info(f"Twilio Voice keypress received for alert {alert_id}: Digits={digit}")

    if digit == "1":
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledged_by = "voice_call"
        alert.next_escalation_at = None
        await db.commit()

        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Amy">
        Alert {alert_id} has been acknowledged. Escalation stopped. Thank you. Goodbye.
    </Say>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    elif digit == "2":
        if alert.source_ip:
            await block_ip(
                db,
                alert.source_ip,
                f"Blocked via phone call keypress for alert #{alert_id}",
                alert_id,
            )
            ip_msg = f"Attacker IP {alert.source_ip} has been blocked."
        else:
            ip_msg = "No source IP found to block."

        alert.status = AlertStatus.RESOLVED
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledged_by = "voice_call_block"
        alert.next_escalation_at = None
        await db.commit()

        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Amy">
        {ip_msg} Alert {alert_id} is now resolved. Goodbye.
    </Say>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    elif digit == "9":
        # Repeat
        twiml = build_twiml_response(alert)
        return Response(content=twiml, media_type="application/xml")

    else:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Amy">
        No valid option selected. The alert remains active. Goodbye.
    </Say>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")


@router.post("/sms-reply")
async def sms_reply_webhook(
    From: Optional[str] = Form(None),
    Body: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle inbound SMS replies:
    - '1' or 'ACK': Acknowledge latest open alert
    - 'BLOCK': Block source IP of latest open alert
    - 'STATUS': Reply with system health & open alerts
    """
    msg_body = (Body or "").strip().upper()
    log.info(f"Inbound SMS from {From}: {msg_body}")

    # Find the most recent active alert
    result = await db.execute(
        select(Alert)
        .where(Alert.status.in_([AlertStatus.NEW, AlertStatus.NOTIFIED]))
        .order_by(desc(Alert.last_seen))
        .limit(1)
    )
    latest_alert = result.scalar_one_or_none()

    if not latest_alert and msg_body in ("1", "ACK", "BLOCK"):
        reply_text = "NightWatcher: No open alerts requiring response right now. All clear!"
    elif msg_body in ("1", "ACK") and latest_alert:
        latest_alert.status = AlertStatus.ACKNOWLEDGED
        latest_alert.acknowledged_at = datetime.now(timezone.utc)
        latest_alert.acknowledged_by = f"sms:{From or 'user'}"
        latest_alert.next_escalation_at = None
        await db.commit()
        reply_text = f"✅ NightWatcher: Alert #{latest_alert.id} ({latest_alert.type}) acknowledged via SMS."
    elif msg_body == "BLOCK" and latest_alert:
        if latest_alert.source_ip:
            await block_ip(
                db,
                latest_alert.source_ip,
                f"Blocked via SMS reply for alert #{latest_alert.id}",
                latest_alert.id,
            )
            latest_alert.status = AlertStatus.RESOLVED
            await db.commit()
            reply_text = f"🚫 NightWatcher: IP {latest_alert.source_ip} blocked & alert #{latest_alert.id} resolved."
        else:
            reply_text = f"NightWatcher: Alert #{latest_alert.id} does not have a source IP to block."
    elif msg_body == "STATUS":
        active_count_res = await db.execute(
            select(Alert).where(Alert.status.in_([AlertStatus.NEW, AlertStatus.NOTIFIED]))
        )
        active_count = len(active_count_res.scalars().all())
        blocked_res = await db.execute(
            select(BlockedIP).where(BlockedIP.active == True)
        )
        blocked_count = len(blocked_res.scalars().all())
        reply_text = f"🛡️ NightWatcher Status:\nActive Alerts: {active_count}\nBlocked IPs: {blocked_count}\nWatchdog: Online"
    else:
        reply_text = (
            "NightWatcher Commands:\n"
            "• Reply '1' or 'ACK' to acknowledge latest alert\n"
            "• Reply 'BLOCK' to block attacker IP\n"
            "• Reply 'STATUS' for watchdog health"
        )

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{reply_text}</Message>
</Response>"""
    return Response(content=twiml, media_type="application/xml")
