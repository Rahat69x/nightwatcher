"""
NightWatcher Tests — Watchers & Heuristics
"""
import pytest
from app.watchers.phishing_watcher import analyze_url
from app.watchers.breach_watcher import check_password_pwned


@pytest.mark.asyncio
async def test_phishing_lookalike_detection():
    # paypa1 with digit 1 instead of l or edit distance
    result = await analyze_url("http://paypa1-security.xyz/login")
    assert result["phish_score"] >= 40
    assert any("paypal" in r.lower() or "lookalike" in r.lower() or "tld" in r.lower() for r in result["reasons"])


@pytest.mark.asyncio
async def test_phishing_raw_ip_detection():
    result = await analyze_url("http://192.168.1.100:8080/auth")
    assert any("raw IP" in r for r in result["reasons"])
    assert result["phish_score"] >= 30


@pytest.mark.asyncio
async def test_pwned_password_k_anonymity_live():
    # Common known breached password 'password' should return positive count via free HIBP API
    count = await check_password_pwned("password")
    assert count > 1000
