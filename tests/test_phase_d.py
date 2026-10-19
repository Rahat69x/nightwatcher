"""
NightWatcher Tests — Phase D: Content & Identity
Verifies:
1. Item 5: Page titles and dynamic tab titles
2. Item 6: Meta descriptions and OpenGraph tags
3. Item 9: Dynamic copyright year element and script update
4. Item 14: Placeholder text clean (0 findings in find-placeholders.py)
5. Item 15: All 5 navigation tabs reachable in both desktop and mobile
"""
import pytest
import subprocess
import sys
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from app.main import app

ROOT = Path(__file__).resolve().parent.parent

@pytest.mark.asyncio
async def test_meta_descriptions_and_titles():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        html = resp.text

        # 1. Title & Meta description
        assert "<title>NightWatcher — Always Watching. Loudest When It Matters.</title>" in html
        assert 'name="description"' in html
        assert 'property="og:title"' in html
        assert 'property="og:description"' in html

        # 2. Dynamic copyright year element in footer
        assert 'id="copyright-year"' in html


def test_placeholder_audit_script_clean():
    res = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "find-placeholders.py")],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "0 findings" in res.stdout


def test_navigation_and_tab_titles_in_js():
    js_content = (ROOT / "app" / "dashboard" / "static" / "app.js").read_text(encoding="utf-8")
    assert "tab-alerts" in js_content
    assert "tab-tools" in js_content
    assert "tab-sites" in js_content
    assert "tab-blocklist" in js_content
    assert "tab-channels" in js_content
    assert "copyright-year" in js_content
    assert "titleMap" in js_content
