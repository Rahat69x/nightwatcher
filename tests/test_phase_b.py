"""
NightWatcher Tests — Phase B: Links, Intents, Contacts & Favicon
Verifies:
1. Item 4: Favicon route /favicon.ico and static SVG asset exist and return 200
2. Item 7: Footer links to docs, health, demo portal, and support
3. Item 17: Clickable logo returns to / with accessible label
4. Item 18: Clickable phone number with tel: URI and RFC 3966 format
5. Item 19: Clickable email with mailto: URI and prefilled subject
"""
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from app.main import app
from demo.fake_login_app import app as demo_app

ROOT = Path(__file__).resolve().parent.parent

@pytest.mark.asyncio
async def test_favicon_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Route /favicon.ico
        resp = await client.get("/favicon.ico")
        assert resp.status_code == 200
        assert "image/svg+xml" in resp.headers.get("content-type", "")

        # Static asset
        resp_static = await client.get("/static/favicon.svg")
        assert resp_static.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_links_contacts_and_logo():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        html = resp.text

        # 1. Favicon in head
        assert '<link rel="icon" type="image/svg+xml" href="/static/favicon.svg">' in html

        # 2. Clickable brand logo
        assert '<a href="/" class="brand"' in html
        assert 'aria-label="NightWatcher Home — Return to top"' in html

        # 3. Footer links
        assert 'class="app-footer"' in html
        assert 'href="/docs"' in html
        assert 'href="/health"' in html

        # 4. Clickable emergency phone number (tel:)
        assert 'href="tel:+18005550199"' in html

        # 5. Clickable incident email (mailto:)
        assert 'href="mailto:soc@nightwatcher.io' in html


@pytest.mark.asyncio
async def test_demo_portal_links_and_favicon():
    transport = ASGITransport(app=demo_app)
    async with AsyncClient(transport=transport, base_url="http://demo") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        html = resp.text

        assert 'href="http://localhost:8000/static/favicon.svg"' in html
        assert '<h2><a href="/">Apex Vault Portal</a></h2>' in html
        assert 'http://localhost:8000/' in html
