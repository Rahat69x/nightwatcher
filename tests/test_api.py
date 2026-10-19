"""
NightWatcher Tests — Full End-to-End API Integration
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db import init_db


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()


@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_event_ingest_and_auto_block():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Submit brute force event
        resp = await client.post(
            "/api/events/",
            json={
                "type": "brute_force",
                "source": "pytest",
                "details": {
                    "source_ip": "198.51.100.99",
                    "failed_attempts": 10,
                    "username": "admin",
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["severity"] == "medium"
        alert_id = data["alert_id"]

        # Verify alert appears in /api/alerts/
        alerts_resp = await client.get("/api/alerts/")
        assert alerts_resp.status_code == 200
        alerts = alerts_resp.json()
        assert any(a["id"] == alert_id for a in alerts)

        # Verify IP is blocked in /api/alerts/blocklist/active
        block_resp = await client.get("/api/alerts/blocklist/active")
        assert block_resp.status_code == 200
        blocked_ips = [b["ip"] for b in block_resp.json()]
        assert "198.51.100.99" in blocked_ips

        # Acknowledge the alert
        ack_resp = await client.post(f"/api/alerts/{alert_id}/acknowledge?by=test_runner")
        assert ack_resp.status_code == 200
        assert ack_resp.json()["status"] == "acknowledged"


@pytest.mark.asyncio
async def test_twilio_webhooks():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create an alert first
        event_res = await client.post(
            "/api/events/",
            json={
                "type": "login_success_after_brute",
                "source": "pytest_voice",
                "details": {"source_ip": "198.51.100.77", "username": "admin"},
            },
        )
        alert_id = event_res.json()["alert_id"]

        # Voice TwiML
        twiml_res = await client.get(f"/api/twilio/voice-twiml?alert_id={alert_id}")
        assert twiml_res.status_code == 200
        assert "<Say" in twiml_res.text
        assert "<Gather" in twiml_res.text

        # Voice Gather action (Press 1 = ACK)
        action_res = await client.post(
            f"/api/twilio/voice-action?alert_id={alert_id}",
            data={"Digits": "1"},
        )
        assert action_res.status_code == 200
        assert "acknowledged" in action_res.text.lower()

        # Inbound SMS reply (Text 'STATUS')
        sms_res = await client.post(
            "/api/twilio/sms-reply",
            data={"From": "+1234567890", "Body": "STATUS"},
        )
        assert sms_res.status_code == 200
        assert "NightWatcher Status" in sms_res.text
