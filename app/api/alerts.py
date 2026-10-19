"""NightWatcher — /api/alerts CRUD + acknowledge/ignore/block endpoints"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.models import Alert, AlertStatus, BlockedIP, Severity
from app.engine.security import api_limiter

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    severity: str
    score: float
    status: str
    count: int
    summary: str
    source_ip: Optional[str]
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]
    acknowledged_by: Optional[str]


@router.get("/", response_model=List[AlertOut])
async def list_alerts(
    status: Optional[str] = Query(None, description="Filter by alert status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(50, ge=1, le=200, description="Page limit (1-200)"),
    db: AsyncSession = Depends(get_db),
):
    """List alerts, most recent first. Filter by status or severity with bounded limit."""
    valid_statuses = {s.value for s in AlertStatus}
    valid_severities = {s.value for s in Severity}

    if status and status.lower() not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Must be one of: {sorted(valid_statuses)}",
        )
    if severity and severity.lower() not in valid_severities:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid severity '{severity}'. Must be one of: {sorted(valid_severities)}",
        )

    q = select(Alert).order_by(desc(Alert.last_seen)).limit(limit)
    if status:
        q = q.where(Alert.status == status.lower())
    if severity:
        q = q.where(Alert.severity == severity.lower())
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    by: str = Query("dashboard", max_length=128),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = by
    alert.next_escalation_at = None
    await db.commit()
    return {"status": "acknowledged", "alert_id": alert_id}


@router.post("/{alert_id}/ignore")
async def ignore_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = AlertStatus.IGNORED
    alert.next_escalation_at = None
    await db.commit()
    return {"status": "ignored", "alert_id": alert_id}


@router.post("/{alert_id}/resolve")
async def resolve_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = AlertStatus.RESOLVED
    alert.next_escalation_at = None
    await db.commit()
    return {"status": "resolved", "alert_id": alert_id}


@router.post("/{alert_id}/block-ip")
async def block_ip_from_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    from app.engine.actions import block_ip
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if not alert.source_ip:
        raise HTTPException(status_code=400, detail="Alert has no source IP")

    await block_ip(db, alert.source_ip, f"manually blocked from alert #{alert_id}", alert_id)
    alert.status = AlertStatus.RESOLVED
    await db.commit()
    return {"status": "blocked", "ip": alert.source_ip}


@router.get("/blocklist/active")
async def get_blocklist(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BlockedIP).where(BlockedIP.active == True))
    entries = result.scalars().all()
    return [
        {
            "ip": e.ip,
            "reason": e.reason,
            "blocked_at": e.blocked_at,
            "expires_at": e.expires_at,
        }
        for e in entries
    ]
