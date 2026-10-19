"""
NightWatcher Engine — Deduplication / Fingerprinting
Same event within the dedupe window -> update count, don't create new alert.
"""
from __future__ import annotations
import hashlib
import json
from typing import Any, Dict


def make_fingerprint(event_type: str, details: Dict[str, Any]) -> str:
    """
    Stable fingerprint for grouping duplicate events.
    Groups on: type + the most discriminating fields per event type.
    """
    key_fields = _key_fields(event_type, details)
    raw = json.dumps({"type": event_type, **key_fields}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _key_fields(event_type: str, d: Dict[str, Any]) -> Dict[str, Any]:
    """Return only the fields that define uniqueness for this event type."""

    if event_type in ("brute_force", "login_success_after_brute", "credential_stuffing"):
        return {"source_ip": d.get("source_ip", "")}

    if event_type in ("site_down", "ssl_expiry", "missing_security_header",
                      "no_https_redirect", "slow_response"):
        return {"url": d.get("url", "")}

    if event_type == "phishing_url":
        return {"url": d.get("url", "")}

    if event_type in ("email_breach", "password_pwned"):
        return {"email": d.get("email", "")}

    # Generic: hash type + source_ip + url
    return {
        "source_ip": d.get("source_ip", ""),
        "url": d.get("url", ""),
    }
