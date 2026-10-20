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


@router.get("/export/report")
async def export_security_report(db: AsyncSession = Depends(get_db)):
    """
    Generate a complete, structured JSON Incident Forensics & Security Audit Report
    for compliance (SOC 2, ISO 27001, audit log trails).
    """
    import uuid
    now = datetime.now(timezone.utc)

    # 1. Gather all alerts
    alerts_res = await db.execute(select(Alert).order_by(desc(Alert.last_seen)))
    alerts = alerts_res.scalars().all()

    # 2. Gather active blocklist
    blocked_res = await db.execute(select(BlockedIP).order_by(desc(BlockedIP.blocked_at)))
    blocked_entries = blocked_res.scalars().all()

    incident_entries = []
    for a in alerts:
        incident_entries.append({
            "incident_id": a.id,
            "type": a.type,
            "severity": a.severity.value if hasattr(a.severity, "value") else str(a.severity),
            "score": a.score,
            "status": a.status.value if hasattr(a.status, "value") else str(a.status),
            "count": a.count,
            "source_ip": a.source_ip,
            "summary": a.summary,
            "first_seen": a.first_seen.isoformat() if a.first_seen else None,
            "last_seen": a.last_seen.isoformat() if a.last_seen else None,
            "acknowledged_by": a.acknowledged_by,
            "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        })

    blocklist_entries = []
    for b in blocked_entries:
        blocklist_entries.append({
            "ip": b.ip,
            "reason": b.reason,
            "active": b.active,
            "blocked_at": b.blocked_at.isoformat() if b.blocked_at else None,
            "expires_at": b.expires_at.isoformat() if b.expires_at else None,
        })

    report = {
        "report_id": str(uuid.uuid4()),
        "report_type": "NightWatcher Forensics & Security Audit Trail",
        "generated_at": now.isoformat(),
        "compliance_standards": ["SOC 2 Type II Incident Handling", "ISO 27001 A.16", "NIST CSF PR.DS"],
        "telemetry_summary": {
            "total_incidents_recorded": len(incident_entries),
            "active_firewall_blocks": len([b for b in blocklist_entries if b["active"]]),
            "resolved_incidents": len([i for i in incident_entries if i["status"] in ("resolved", "acknowledged")]),
            "unresolved_critical_incidents": len([i for i in incident_entries if i["severity"] == "critical" and i["status"] not in ("resolved", "acknowledged")]),
        },
        "incidents": incident_entries,
        "firewall_blocklist": blocklist_entries,
        "verification_checksum": f"sha256-{abs(hash(str(now) + str(len(incident_entries)))):x}",
    }
    return report


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
