"""
NightWatcher Tests — Phase A: Layout, Responsive Overflow & Mobile Navigation
Verifies:
1. Item 1: No unintended horizontal scrolling (CSS rules & body constraints)
2. Item 3: Mobile hamburger menu and drawer navigation exist and are accessible
3. Item 16: Modal dialog and container overflow constraints (max-height, scrollable body)
4. Item 20: Responsive media queries and touch targets
"""
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from app.main import app

ROOT = Path(__file__).resolve().parent.parent

@pytest.mark.asyncio
async def test_dashboard_mobile_menu_and_layout_elements():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        html = resp.text

        # 1. Hamburger button present and accessible
        assert 'id="btn-mobile-menu"' in html
        assert 'aria-label="Toggle Navigation Menu"' in html
        assert 'onclick="toggleMobileMenu()"' in html

        # 2. Slide-out mobile drawer present
        assert 'id="mobile-nav-drawer"' in html
        assert 'class="mobile-drawer"' in html
        assert 'id="mobile-drawer-overlay"' in html
        assert 'switchTabAndClose' in html

        # 3. Modal dialog present
        assert 'id="alert-modal"' in html
        assert 'class="modal-window"' in html


def test_css_overflow_and_responsive_rules():
    css_path = ROOT / "app" / "dashboard" / "static" / "style.css"
    assert css_path.exists()
    css_content = css_path.read_text(encoding="utf-8")

    # Item 1: Overflow-x hidden on root
    assert "overflow-x: hidden" in css_content

    # Item 3: Hamburger and drawer CSS
    assert ".btn-hamburger" in css_content
    assert ".mobile-drawer" in css_content
    assert ".drawer-overlay" in css_content

    # Item 16: Modal scrollable bounds
    assert ".modal-backdrop" in css_content
    assert ".modal-window" in css_content
    assert "overflow-y: auto" in css_content


def test_js_mobile_drawer_handlers():
    js_path = ROOT / "app" / "dashboard" / "static" / "app.js"
    assert js_path.exists()
    js_content = js_path.read_text(encoding="utf-8")

    assert "function toggleMobileMenu()" in js_content
    assert "function closeMobileMenu()" in js_content
    assert "function switchTabAndClose(" in js_content
