"""
NightWatcher Engine — Scoring
Maps event type + details -> 0-100 score -> Severity enum
"""
from __future__ import annotations
import re
from typing import Any, Dict
from app.models import Severity


def score_event(event_type: str, details: Dict[str, Any]) -> tuple[float, Severity]:
    """
    Return (score, severity).
    Score 0-39 = LOW, 40-69 = MEDIUM, 70-89 = HIGH, 90-100 = CRITICAL
    """
    score = _calculate(event_type, details)
    score = max(0.0, min(100.0, score))
    severity = _to_severity(score)
    return score, severity


def _to_severity(score: float) -> Severity:
    if score >= 90:
        return Severity.CRITICAL
    elif score >= 70:
        return Severity.HIGH
    elif score >= 40:
        return Severity.MEDIUM
    return Severity.LOW


def _calculate(event_type: str, d: Dict[str, Any]) -> float:
    """Per-type scoring formulas."""

    # ── Brute Force / Login Attack ──────────────────────────────────
    if event_type == "brute_force":
        attempts = int(d.get("failed_attempts", 0))
        score = 40.0 + min(attempts * 2, 30)           # +2 per attempt, capped at +30
        if d.get("abuse_confidence_score", 0) > 50:
            score += 10                                  # bad IP reputation
        if d.get("off_hours", False):
            score += 5                                   # off-hours bonus
        return score

    if event_type == "login_success_after_brute":
        # Attacker got in after hammering — always critical
        return 95.0

    if event_type == "credential_stuffing":
        # Many different usernames from one IP
        usernames = int(d.get("unique_usernames", 0))
        return min(50 + usernames * 3, 85)

    # ── Website / Infrastructure ────────────────────────────────────
    if event_type == "site_down":
        return 95.0

    if event_type == "ssl_expiry":
        days = int(d.get("days_remaining", 30))
        if days <= 0:
            return 95.0
        elif days <= 3:
            return 80.0
        elif days <= 14:
            return 50.0
        else:
            return 20.0

    if event_type == "missing_security_header":
        return 35.0

    if event_type == "no_https_redirect":
        return 45.0

    if event_type == "slow_response":
        ms = float(d.get("response_ms", 0))
        return min(30 + ms / 100, 55)

    # ── Phishing / Suspicious URL ────────────────────────────────────
    if event_type == "phishing_url":
        return float(d.get("phish_score", 50))

    # ── Breach ───────────────────────────────────────────────────────
    if event_type == "email_breach":
        score = 45.0
        if d.get("password_exposed", False):
            score = 75.0
        return score

    if event_type == "password_pwned":
        return 70.0

    # ── Generic fallback ─────────────────────────────────────────────
    return float(d.get("score", 30))
