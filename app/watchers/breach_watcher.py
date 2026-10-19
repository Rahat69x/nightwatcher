"""
NightWatcher — Breach Watcher
- Email breach check via HIBP API (paid key required) or mock feed
- Password check via HIBP Pwned Passwords k-anonymity range API (free, no key)
"""
from __future__ import annotations
import hashlib
import logging
from typing import List, Dict, Any, Optional

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

# Mock breach feed for demo (used when HIBP key is unavailable)
MOCK_BREACHES = [
    {
        "Name": "MockBreach2024",
        "Domain": "fakeshop.example.com",
        "BreachDate": "2024-03-15",
        "PwnCount": 1_400_000,
        "Description": "Demo breach for NightWatcher hackathon.",
        "DataClasses": ["Email addresses", "Passwords", "Names"],
        "IsVerified": False,
    },
    {
        "Name": "TestLeak2023",
        "Domain": "testsite.example.com",
        "BreachDate": "2023-11-01",
        "PwnCount": 500_000,
        "Description": "Another mock breach.",
        "DataClasses": ["Email addresses", "Usernames"],
        "IsVerified": False,
    },
]


async def check_email_breaches(email: str, hibp_key: str = "") -> List[Dict[str, Any]]:
    """
    Check if email appears in HIBP breaches.
    Falls back to mock feed if no API key.
    Returns list of breach dicts.
    """
    if not hibp_key:
        log.info("No HIBP key — using mock breach feed for demo")
        # Simulate: flag the first mock breach
        return MOCK_BREACHES[:1]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
                headers={
                    "hibp-api-key": hibp_key,
                    "User-Agent": "NightWatcher/1.0",
                },
                params={"truncateResponse": "false"},
            )
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 404:
                return []   # Not found — email is clean
            else:
                log.error(f"HIBP error {resp.status_code}: {resp.text}")
                return MOCK_BREACHES[:1]   # fallback
    except Exception as e:
        log.error(f"HIBP request failed: {e}")
        return MOCK_BREACHES[:1]  # fallback


async def check_password_pwned(password: str) -> int:
    """
    k-anonymity check via Pwned Passwords API (free, no key).
    Returns number of times the password has been seen in breaches (0 = safe).
    Only sends first 5 chars of SHA-1 hash.
    """
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                headers={"User-Agent": "NightWatcher/1.0"},
            )
            if resp.status_code == 200:
                for line in resp.text.splitlines():
                    hash_suffix, count = line.split(":")
                    if hash_suffix == suffix:
                        return int(count)
            return 0
    except Exception as e:
        log.error(f"Pwned Passwords API failed: {e}")
        return 0


async def run_breach_checks(db) -> None:
    """Called by scheduler. Checks all consent-given watched emails."""
    from app.engine.ingest import ingest_event
    from sqlalchemy import select
    from app.models import WatchedEmail
    from datetime import datetime, timezone

    result = await db.execute(
        select(WatchedEmail).where(
            WatchedEmail.active == True,
            WatchedEmail.consent_given == True,
        )
    )
    emails = result.scalars().all()

    for entry in emails:
        try:
            breaches = await check_email_breaches(entry.email, settings.hibp_api_key)
            if breaches:
                has_password = any(
                    "Passwords" in b.get("DataClasses", []) for b in breaches
                )
                await ingest_event(db, "email_breach", f"breach_watcher:{entry.email}", {
                    "email": entry.email,
                    "breach_count": len(breaches),
                    "breach_names": [b.get("Name") for b in breaches],
                    "password_exposed": has_password,
                })

            entry.last_checked_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as e:
            log.error(f"Breach check failed for {entry.email}: {e}")
