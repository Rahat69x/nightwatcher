"""
NightWatcher — Voice call notifier via Twilio
Speaks alert summary, then "Press 1 to acknowledge, press 2 to block the IP."
TwiML response is served by our /api/twilio/voice-twiml endpoint.
"""
from __future__ import annotations
import logging
from app.config import get_settings
from app.models import Alert

log = logging.getLogger(__name__)
settings = get_settings()


async def place_voice_call(alert: Alert) -> None:
    """Place an outbound voice call for critical alerts."""
    if not all([
        settings.twilio_account_sid,
        settings.twilio_auth_token,
        settings.twilio_from_number,
        settings.twilio_to_number_list,
    ]):
        log.warning("Twilio Voice not configured — skipping")
        return

    twiml_url = f"{settings.base_url}/api/twilio/voice-twiml?alert_id={alert.id}"

    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        for number in settings.twilio_to_number_list:
            call = client.calls.create(
                to=number,
                from_=settings.twilio_from_number,
                url=twiml_url,
            )
            log.info(f"Voice call placed for alert {alert.id}: SID={call.sid}")
    except Exception as e:
        log.error(f"Voice call failed for alert {alert.id}: {e}")
        raise


def build_twiml_response(alert: Alert) -> str:
    """
    TwiML XML that reads the alert and collects a keypress.
    Press 1 = acknowledge. Press 2 = block IP.
    """
    summary_text = alert.summary[:300].replace("&", "and").replace("<", "").replace(">", "")
    callback_url = f"{settings.base_url}/api/twilio/voice-action?alert_id={alert.id}"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Amy">
        This is NightWatcher. You have a {alert.severity.value} security alert.
        {summary_text}
        Press 1 to acknowledge this alert.
        Press 2 to block the source IP address.
        Press 9 to repeat this message.
    </Say>
    <Gather numDigits="1" action="{callback_url}" method="POST" timeout="15">
        <Say>Waiting for your input.</Say>
    </Gather>
    <Say>No input received. The alert remains open. Goodbye.</Say>
</Response>"""
