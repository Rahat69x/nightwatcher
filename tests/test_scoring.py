"""
NightWatcher Tests — Scoring Engine
"""
from app.engine.scoring import score_event, _to_severity
from app.models import Severity


def test_brute_force_scoring():
    # 5 attempts: 40 + 10 = 50 -> Medium
    score, sev = score_event("brute_force", {"failed_attempts": 5})
    assert score == 50.0
    assert sev == Severity.MEDIUM

    # 15 attempts + bad reputation + off hours: 40 + 30 + 10 + 5 = 85 -> High
    score, sev = score_event("brute_force", {
        "failed_attempts": 15,
        "abuse_confidence_score": 90,
        "off_hours": True,
    })
    assert score == 85.0
    assert sev == Severity.HIGH


def test_login_success_after_brute():
    # Success after attack is always critical (score 95)
    score, sev = score_event("login_success_after_brute", {"failed_attempts_before": 10})
    assert score == 95.0
    assert sev == Severity.CRITICAL


def test_credential_stuffing_scoring():
    score, sev = score_event("credential_stuffing", {"unique_usernames": 8})
    assert score == 74.0
    assert sev == Severity.HIGH


def test_ssl_expiry_tiers():
    # Expired: Critical
    score, sev = score_event("ssl_expiry", {"days_remaining": 0})
    assert score == 95.0
    assert sev == Severity.CRITICAL

    # 2 days: High
    score, sev = score_event("ssl_expiry", {"days_remaining": 2})
    assert score == 80.0
    assert sev == Severity.HIGH

    # 10 days: Medium
    score, sev = score_event("ssl_expiry", {"days_remaining": 10})
    assert score == 50.0
    assert sev == Severity.MEDIUM

    # 45 days: Low
    score, sev = score_event("ssl_expiry", {"days_remaining": 45})
    assert score == 20.0
    assert sev == Severity.LOW


def test_site_down_scoring():
    score, sev = score_event("site_down", {"url": "https://example.com"})
    assert score == 95.0
    assert sev == Severity.CRITICAL
