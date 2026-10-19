"""
NightWatcher Engine — Plain-language summary generator
Uses Gemini AI when available; falls back to deterministic templates.
"""
from __future__ import annotations
from typing import Any, Dict
from app.models import Severity


# ── Gemini AI summary ───────────────────────────────────────────────────

async def generate_summary(
    event_type: str,
    details: Dict[str, Any],
    severity: Severity,
    gemini_api_key: str = "",
) -> str:
    """Try Gemini first, fall back to template."""
    if gemini_api_key:
        try:
            return await _gemini_summary(event_type, details, severity, gemini_api_key)
        except Exception:
            pass
    return _template_summary(event_type, details, severity)


async def _gemini_summary(
    event_type: str,
    details: Dict[str, Any],
    severity: Severity,
    api_key: str,
) -> str:
    from google import genai
    client = genai.Client(api_key=api_key)
    prompt = (
        f"Write a short (2-sentence max), plain-English security alert summary "
        f"for a non-technical person.\n"
        f"Event type: {event_type}\nSeverity: {severity.value}\nDetails: {details}\n"
        f"Start with what happened, then what was done automatically."
    )
    interaction = client.interactions.create(
        model="gemini-3.8-flash",
        input=prompt,
        store=False,
    )
    return interaction.output_text or _template_summary(event_type, details, severity)


def _template_summary(
    event_type: str,
    details: Dict[str, Any],
    severity: Severity,
) -> str:
    """Hard-coded plain language templates — always works."""
    ip = details.get("source_ip", "an unknown IP")
    url = details.get("url", "a monitored site")
    count = details.get("failed_attempts", details.get("count", "several"))

    templates: Dict[str, str] = {
        "brute_force": (
            f"🔴 {count} failed login attempts from {ip} in under 60 seconds — "
            f"this looks like a brute-force attack. The IP has been automatically blocked."
        ),
        "login_success_after_brute": (
            f"🚨 CRITICAL: An attacker from {ip} succeeded in logging in after {count} failed attempts. "
            f"Immediate action required — check the account for unauthorised changes."
        ),
        "credential_stuffing": (
            f"⚠️ {ip} tried {details.get('unique_usernames','many')} different usernames — "
            f"likely a credential-stuffing attack. IP blocked automatically."
        ),
        "site_down": (
            f"🔴 {url} is not responding. It has been down for at least 2 consecutive checks. "
            f"Please check your hosting immediately."
        ),
        "ssl_expiry": (
            f"⚠️ The SSL certificate for {url} expires in "
            f"{details.get('days_remaining','?')} days. "
            f"Renew it now to avoid visitors seeing a 'Not Secure' warning."
        ),
        "missing_security_header": (
            f"ℹ️ {url} is missing the {details.get('header','a security header')} header. "
            f"This makes the site easier to attack. No immediate action required but fix it soon."
        ),
        "no_https_redirect": (
            f"⚠️ {url} does not redirect HTTP traffic to HTTPS. "
            f"Visitors using plain HTTP are not encrypted."
        ),
        "phishing_url": (
            f"🎣 Suspicious link detected: {url}\n"
            f"Risk score: {details.get('phish_score','?')}/100\n"
            f"Reasons: {', '.join(details.get('reasons', ['suspicious pattern']))}"
        ),
        "email_breach": (
            f"📧 The email {details.get('email','?')} appeared in a data breach "
            f"({'password exposed' if details.get('password_exposed') else 'no password exposed'}). "
            f"Change the password for any site where it was used."
        ),
        "password_pwned": (
            f"🔑 A password you checked has been seen in {details.get('count','?')} "
            f"known data breaches. Do NOT use this password anywhere."
        ),
    }
    return templates.get(
        event_type,
        f"Security event detected: {event_type}. Severity: {severity.value}. "
        f"Details: {details}"
    )
