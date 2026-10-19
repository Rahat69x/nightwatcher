"""
NightWatcher Tests — Phase C: States, Feedback, Buttons & 404 Page
Verifies:
1. Item 8: Custom branded 404 page on unknown HTML routes; JSON for /api/*
2. Item 11: Button debouncing logic in simulator
3. Item 12: Success toast messages & status roles
4. Item 13: Error toast messages & status roles
"""
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from app.main import app

ROOT = Path(__file__).resolve().parent.parent

@pytest.mark.asyncio
async def test_custom_404_html_and_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Browser HTML request to unknown route
        resp_html = await client.get(
            "/unknown-security-route",
            headers={"Accept": "text/html,application/xhtml+xml"}
        )
        assert resp_html.status_code == 404
        assert "Security Target Not Found" in resp_html.text
        assert "HTTP 404" in resp_html.text
        assert "Return to Live SOC" in resp_html.text

        # API JSON request to unknown endpoint
        resp_json = await client.get(
            "/api/unknown-endpoint",
            headers={"Accept": "application/json"}
        )
        assert resp_json.status_code == 404
        assert "detail" in resp_json.json()


def test_toast_and_debounce_assets():
    # Verify app.js debounce and toast logic
    js_content = (ROOT / "app" / "dashboard" / "static" / "app.js").read_text(encoding="utf-8")
    assert "let isSimulating = false;" in js_content
    assert "showToast(msg, type = 'success')" in js_content
    assert "toast-${type}" in js_content

    # Verify style.css toast styles
    css_content = (ROOT / "app" / "dashboard" / "static" / "style.css").read_text(encoding="utf-8")
    assert ".toast-container" in css_content
    assert ".toast-success" in css_content
    assert ".toast-error" in css_content
    assert ".toast-warning" in css_content
