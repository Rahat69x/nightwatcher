"""
NightWatcher Engine — Actions
Auto-responses: block IP, log action, optional firewall (ufw/iptables as opt-in).
"""
from __future__ import annotations
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Action, BlockedIP
from app.config import get_settings

settings = get_settings()


async def block_ip(
    db: AsyncSession,
    ip: str,
    reason: str,
    alert_id: Optional[int] = None,
    duration_minutes: Optional[int] = None,
) -> BlockedIP:
    """Add IP to blocklist. Returns the BlockedIP record."""
    duration = duration_minutes or settings.auto_block_duration_minutes
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=duration)

    # Check if already blocked
    result = await db.execute(select(BlockedIP).where(BlockedIP.ip == ip))
    existing = result.scalar_one_or_none()
    if existing:
        existing.active = True
        existing.expires_at = expires_at
        existing.reason = reason
        await db.commit()
        return existing

    blocked = BlockedIP(
        ip=ip,
        reason=reason,
        alert_id=alert_id,
        expires_at=expires_at,
        active=True,
    )
    db.add(blocked)
    await db.commit()
    await db.refresh(blocked)
    return blocked


async def unblock_expired_ips(db: AsyncSession) -> int:
    """Called by scheduler — unblock IPs whose timer has expired."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(BlockedIP).where(BlockedIP.active == True, BlockedIP.expires_at <= now)
    )
    expired = result.scalars().all()
    for entry in expired:
        entry.active = False
    await db.commit()
    return len(expired)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def is_ip_blocked(db: AsyncSession, ip: str) -> bool:
    """Check blocklist — used by the demo login app."""
    result = await db.execute(
        select(BlockedIP).where(
            BlockedIP.ip == ip,
            BlockedIP.active == True,
        )
    )
    entry = result.scalar_one_or_none()
    if entry and entry.expires_at:
        exp = _ensure_utc(entry.expires_at)
        if exp and exp < datetime.now(timezone.utc):
            entry.active = False
            await db.commit()
            return False
    return entry is not None


async def log_action(
    db: AsyncSession,
    alert_id: int,
    action_type: str,
    target: str,
    detail: str = "",
) -> Action:
    """Persist an automated action record."""
    action = Action(
        alert_id=alert_id,
        action_type=action_type,
        target=target,
        detail=detail,
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return action


def try_firewall_block(ip: str) -> bool:
    """
    Optional: actually block via ufw/iptables.
    Only works on Linux with admin rights — safe to call; returns False if unavailable.
    """
    try:
        subprocess.run(
            ["ufw", "deny", "from", ip, "to", "any"],
            capture_output=True, timeout=5, check=True,
        )
        return True
    except Exception:
        pass
    try:
        subprocess.run(
            ["iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"],
            capture_output=True, timeout=5, check=True,
        )
        return True
    except Exception:
        return False
