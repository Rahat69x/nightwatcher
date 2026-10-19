"""
NightWatcher — Website Watcher
Checks: uptime, SSL expiry, HTTPS redirect, security headers, response time.
Only alerts when something CHANGES or breaks.
"""
from __future__ import annotations
import asyncio
import logging
import socket
import ssl
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from urllib.parse import urlparse

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

REQUIRED_HEADERS = [
    "strict-transport-security",
    "content-security-policy",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
]


async def check_site(db, url: str) -> Dict[str, Any]:
    """Full check for one URL. Returns a report dict."""
    from app.engine.security import is_safe_url
    report = {"url": url, "checked_at": datetime.now(timezone.utc).isoformat()}

    # ── SSRF Validation ──────────────────────────────────────────
    safe, msg = is_safe_url(url, allow_local_demo=settings.debug)
    if not safe:
        report["up"] = False
        report["error"] = f"Blocked by SSRF filter: {msg}"
        return report

    # ── 1. Uptime / response time ──────────────────────────────────
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=15.0,
            verify=True,
        ) as client:
            start = asyncio.get_event_loop().time()
            resp = await client.get(url)
            ms = (asyncio.get_event_loop().time() - start) * 1000

        report["status_code"] = resp.status_code
        report["response_ms"] = ms
        report["up"] = resp.status_code < 500

        # ── 2. HTTPS redirect check ────────────────────────────────
        parsed = urlparse(url)
        if parsed.scheme == "https":
            try:
                async with httpx.AsyncClient(
                    follow_redirects=False, timeout=10.0
                ) as nc:
                    http_url = url.replace("https://", "http://", 1)
                    r2 = await nc.get(http_url)
                    if r2.status_code in (301, 302, 307, 308):
                        report["https_redirect"] = True
                    else:
                        report["https_redirect"] = False
            except Exception:
                report["https_redirect"] = None

        # ── 3. Security headers ────────────────────────────────────
        missing_headers = []
        for h in REQUIRED_HEADERS:
            if h not in {k.lower() for k in resp.headers}:
                missing_headers.append(h)
        report["missing_headers"] = missing_headers

    except httpx.ConnectError:
        report["up"] = False
        report["error"] = "connection_refused"
    except httpx.TimeoutException:
        report["up"] = False
        report["error"] = "timeout"
    except Exception as e:
        report["up"] = False
        report["error"] = str(e)

    # ── 4. SSL expiry ──────────────────────────────────────────────
    parsed = urlparse(url)
    if parsed.scheme == "https":
        days = await _ssl_days_remaining(parsed.hostname, parsed.port or 443)
        report["ssl_days_remaining"] = days

    # ── 5. Generate events ─────────────────────────────────────────
    await _emit_events(db, report)
    return report


async def _ssl_days_remaining(hostname: str, port: int) -> Optional[int]:
    """Return days until SSL certificate expires, or None on error."""
    try:
        ctx = ssl.create_default_context()
        loop = asyncio.get_event_loop()

        def _check():
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    expiry_str = cert["notAfter"]
                    expiry = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
                    expiry = expiry.replace(tzinfo=timezone.utc)
                    delta = expiry - datetime.now(timezone.utc)
                    return max(delta.days, 0)

        return await loop.run_in_executor(None, _check)
    except Exception as e:
        log.warning(f"SSL check failed for {hostname}: {e}")
        return None


async def _emit_events(db, report: Dict[str, Any]) -> None:
    """Translate report findings into NightWatcher events."""
    from app.engine.ingest import ingest_event
    url = report["url"]

    if not report.get("up", True):
        # Handled via consecutive_failures in the scheduler
        pass

    # SSL expiry events
    days = report.get("ssl_days_remaining")
    if days is not None and days < 30:
        await ingest_event(db, "ssl_expiry", f"website_watcher:{url}", {
            "url": url, "days_remaining": days,
        })

    # Missing headers
    for header in report.get("missing_headers", []):
        await ingest_event(db, "missing_security_header", f"website_watcher:{url}", {
            "url": url, "header": header,
        })

    # No HTTPS redirect
    if report.get("https_redirect") is False:
        await ingest_event(db, "no_https_redirect", f"website_watcher:{url}", {
            "url": url,
        })

    # Slow response
    ms = report.get("response_ms", 0)
    if ms and ms > 3000:
        await ingest_event(db, "slow_response", f"website_watcher:{url}", {
            "url": url, "response_ms": ms,
        })


async def run_uptime_checks(db) -> None:
    """Check all configured URLs for uptime (called by scheduler)."""
    from sqlalchemy import select
    from app.models import WatchedSite
    from app.engine.ingest import ingest_event

    # Check URLs from config
    urls = settings.website_url_list

    # Also check URLs in DB
    result = await db.execute(select(WatchedSite).where(WatchedSite.active == True))
    db_sites = result.scalars().all()
    db_urls = [s.url for s in db_sites]

    all_urls = list(set(urls + db_urls))

    for url in all_urls:
        try:
            report = await check_site(db, url)

            # Update DB record if exists
            for site in db_sites:
                if site.url == url:
                    was_up = site.consecutive_failures == 0
                    if not report.get("up", True):
                        site.consecutive_failures += 1
                        if site.consecutive_failures >= 2:
                            await ingest_event(db, "site_down", f"website_watcher:{url}", {
                                "url": url,
                                "consecutive_failures": site.consecutive_failures,
                            })
                    else:
                        site.consecutive_failures = 0
                    site.last_checked_at = datetime.now(timezone.utc)
                    site.last_status_code = report.get("status_code")
                    site.last_response_ms = report.get("response_ms")
                    await db.commit()

        except Exception as e:
            log.error(f"Site check failed for {url}: {e}")
