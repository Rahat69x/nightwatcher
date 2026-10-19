"""
NightWatcher — Watcher Endpoints & Interactive Tools
Allows dashboard and external callers to:
- Test websites for uptime, SSL expiry, HTTPS redirects, security headers
- Inspect URLs / messages for phishing indicators
- Check passwords via k-anonymity HIBP API
- Check email breach history
- Manage watched sites & emails
- Handle Telegram callbacks (Acknowledge, Block IP, Ignore, Details)
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Alert, AlertStatus, BlockedIP, WatchedSite, WatchedEmail, Event
from app.watchers.website_watcher import check_site
from app.watchers.phishing_watcher import analyze_url, run_phishing_check
from app.watchers.breach_watcher import check_password_pwned, check_email_breaches
from app.engine.actions import block_ip
from app.engine.security import scan_limiter, is_safe_url
from app.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/watchers", tags=["watchers"])


class WebsiteCheckIn(BaseModel):
    url: str = Field(..., min_length=4, max_length=512, description="Target website URL")


class PhishingCheckIn(BaseModel):
    text_or_url: str = Field(..., min_length=1, max_length=10_000, description="Message text or URL to inspect")


class PasswordCheckIn(BaseModel):
    password: str = Field(..., min_length=1, max_length=256, description="Password to test")


class EmailCheckIn(BaseModel):
    email: str = Field(..., min_length=5, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", description="Email address")


class AddSiteIn(BaseModel):
    url: str = Field(..., min_length=4, max_length=512, description="Site URL")
    owner_note: Optional[str] = Field("Monitored website", max_length=256)


def _check_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = scan_limiter.is_allowed(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Scan rate limit exceeded. Retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


@router.post("/website/check")
async def manual_website_check(
    request: Request,
    payload: WebsiteCheckIn,
    db: AsyncSession = Depends(get_db),
):
    """Run an on-demand website security audit with SSRF protection."""
    _check_rate_limit(request)
    url = payload.url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    safe, msg = is_safe_url(url, allow_local_demo=settings.debug)
    if not safe:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"SSRF check failed: {msg}")

    report = await check_site(db, url)
    return report


@router.post("/phishing/check")
async def manual_phishing_check(
    request: Request,
    payload: PhishingCheckIn,
    db: AsyncSession = Depends(get_db),
):
    """Analyze a suspicious message, SMS, or URL for phishing indicators."""
    _check_rate_limit(request)
    results = await run_phishing_check(db, payload.text_or_url, settings.safe_browsing_api_key)
    return {"results": results, "count": len(results)}


@router.post("/breach/check-password")
async def manual_password_check(request: Request, payload: PasswordCheckIn):
    """
    Check if a password has been seen in breaches using k-anonymity (free HIBP API).
    Only the first 5 characters of SHA-1 hash are sent over the network.
    """
    _check_rate_limit(request)
    count = await check_password_pwned(payload.password)
    return {
        "pwned": count > 0,
        "breach_occurrences": count,
        "verdict": (
            f"DANGER: Password found in {count:,} known data breaches! Never use this."
            if count > 0
            else "SAFE: Password not found in known public breach corpora."
        ),
    }


@router.post("/breach/check-email")
async def manual_email_breach_check(request: Request, payload: EmailCheckIn):
    """Check breach history for a consent-given email address."""
    _check_rate_limit(request)
    breaches = await check_email_breaches(payload.email.strip(), settings.hibp_api_key)
    return {
        "email": payload.email.strip(),
        "breach_count": len(breaches),
        "breaches": breaches,
    }


@router.get("/sites")
async def list_watched_sites(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WatchedSite).order_by(WatchedSite.id.desc()))
    return result.scalars().all()


@router.post("/sites")
async def add_watched_site(request: Request, payload: AddSiteIn, db: AsyncSession = Depends(get_db)):
    _check_rate_limit(request)
    url = payload.url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    safe, msg = is_safe_url(url, allow_local_demo=settings.debug)
    if not safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot add site: {msg}",
        )

    result = await db.execute(select(WatchedSite).where(WatchedSite.url == url))
    existing = result.scalar_one_or_none()
    if existing:
        existing.active = True
        existing.owner_note = payload.owner_note
        await db.commit()
        return existing

    site = WatchedSite(url=url, owner_note=payload.owner_note, active=True)
    db.add(site)
    await db.commit()
    await db.refresh(site)
    return site


@router.delete("/sites/{site_id}")
async def delete_watched_site(site_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WatchedSite).where(WatchedSite.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    await db.delete(site)
    await db.commit()
    return {"status": "deleted", "site_id": site_id}


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handle Telegram webhook updates (inline keyboard buttons):
    - ack:<id>
    - block:<id>
    - ignore:<id>
    - detail:<id>
    """
    try:
        body = await request.json()
        callback_query = body.get("callback_query")
        if not callback_query:
            return {"ok": True}

        data = callback_query.get("data", "")
        cq_id = callback_query.get("id")
        user = callback_query.get("from", {}).get("username", "telegram_user")

        if ":" in data:
            action, alert_id_str = data.split(":", 1)
            try:
                alert_id = int(alert_id_str)
                result = await db.execute(select(Alert).where(Alert.id == alert_id))
                alert = result.scalar_one_or_none()
                if alert:
                    if action == "ack":
                        alert.status = AlertStatus.ACKNOWLEDGED
                        alert.acknowledged_at = datetime.now(timezone.utc)
                        alert.acknowledged_by = f"tg:@{user}"
                        alert.next_escalation_at = None
                        await db.commit()
                    elif action == "block":
                        if alert.source_ip:
                            await block_ip(db, alert.source_ip, f"Blocked via Telegram by @{user}", alert.id)
                        alert.status = AlertStatus.RESOLVED
                        alert.acknowledged_at = datetime.now(timezone.utc)
                        alert.acknowledged_by = f"tg_block:@{user}"
                        alert.next_escalation_at = None
                        await db.commit()
                    elif action == "ignore":
                        alert.status = AlertStatus.IGNORED
                        alert.next_escalation_at = None
                        await db.commit()
            except Exception as e:
                log.error(f"Telegram webhook callback error: {e}")

        return {"ok": True}
    except Exception as e:
        log.warning(f"Failed to process Telegram webhook: {e}")
        return {"ok": False}


@router.get("/system/stats")
async def get_system_stats(db: AsyncSession = Depends(get_db)):
    """Get real-time dashboard counters and metrics."""
    now = datetime.now(timezone.utc)

    # Alerts count
    all_alerts_res = await db.execute(select(Alert))
    all_alerts = all_alerts_res.scalars().all()

    total_alerts = len(all_alerts)
    active_alerts = len([a for a in all_alerts if a.status in (AlertStatus.NEW, AlertStatus.NOTIFIED)])
    critical_alerts = len([a for a in all_alerts if a.severity.value == "critical"])
    high_alerts = len([a for a in all_alerts if a.severity.value == "high"])

    # Blocked IPs
    blocked_res = await db.execute(select(BlockedIP).where(BlockedIP.active == True))
    blocked_count = len(blocked_res.scalars().all())

    # Watched Sites
    sites_res = await db.execute(select(WatchedSite).where(WatchedSite.active == True))
    sites = sites_res.scalars().all()
    sites_up = len([s for s in sites if s.consecutive_failures == 0])

    # Recent events count
    events_res = await db.execute(select(Event))
    total_events = len(events_res.scalars().all())

    return {
        "total_alerts": total_alerts,
        "active_alerts": active_alerts,
        "critical_alerts": critical_alerts,
        "high_alerts": high_alerts,
        "blocked_ips": blocked_count,
        "watched_sites_total": len(sites),
        "watched_sites_up": sites_up,
        "total_events": total_events,
        "server_time": now.isoformat(),
    }
