"""NightWatcher — /api/events endpoint with Server-Side Validation & Rate Limiting"""
from __future__ import annotations
import json
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.engine.ingest import ingest_event
from app.engine.security import api_limiter

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])


class EventIn(BaseModel):
    type: str = Field(
        ...,
        min_length=2,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_\-\.]+$",
        description="Event type identifier (alphanumeric, hyphens, underscores)",
    )
    source: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Source identifier (e.g. login_watcher, proxy)",
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Event payload details",
    )

    @field_validator("details")
    @classmethod
    def validate_details_size(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Prevent memory exhaustion by validating payload size."""
        raw = json.dumps(v, default=str)
        if len(raw) > 65_536:  # 64 KB cap
            raise ValueError("Details payload exceeds maximum allowed size (64 KB).")
        return v


class EventOut(BaseModel):
    alert_id: int
    severity: str
    score: float
    summary: str
    is_duplicate: bool


@router.post("/", response_model=EventOut)
async def post_event(
    request: Request,
    event: EventIn,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a raw security event. The engine handles scoring,
    deduplication, auto-block, and routing automatically.
    Protected by server-side schema validation and IP rate limiting.
    """
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = api_limiter.is_allowed(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        alert = await ingest_event(db, event.type, event.source, event.details)
        return EventOut(
            alert_id=alert.id,
            severity=alert.severity.value,
            score=alert.score,
            summary=alert.summary,
            is_duplicate=alert.count > 1,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Event ingestion error: {e}", exc_info=True)
        # Avoid leaking internal stack trace details in the HTTP response (Layer 04)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process security event. Incident has been logged.",
        )
