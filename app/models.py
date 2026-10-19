"""NightWatcher — ORM models (all 8 tables)"""
from __future__ import annotations
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


# ── Enums ──────────────────────────────────────────────────────────────

class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    NEW = "new"
    NOTIFIED = "notified"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class NotifChannel(str, enum.Enum):
    EMAIL = "email"
    TELEGRAM = "telegram"
    SMS = "sms"
    VOICE = "voice"


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


# ── events ─────────────────────────────────────────────────────────────

class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(128))
    details: Mapped[str] = mapped_column(Text, default="{}")
    raw_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    alert_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("alerts.id"), nullable=True, index=True
    )
    alert: Mapped[Optional["Alert"]] = relationship("Alert", back_populates="events")


# ── alerts ─────────────────────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[Severity] = mapped_column(Enum(Severity), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus), default=AlertStatus.NEW, index=True
    )
    count: Mapped[int] = mapped_column(Integer, default=1)
    summary: Mapped[str] = mapped_column(Text)
    source_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    source_host: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    extra: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Escalation tracking
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    next_escalation_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    events: Mapped[list["Event"]] = relationship("Event", back_populates="alert")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="alert")
    actions: Mapped[list["Action"]] = relationship("Action", back_populates="alert")


# ── notifications ──────────────────────────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), index=True)
    channel: Mapped[NotifChannel] = mapped_column(Enum(NotifChannel))
    recipient: Mapped[str] = mapped_column(String(256))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus), default=DeliveryStatus.PENDING
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    alert: Mapped["Alert"] = relationship("Alert", back_populates="notifications")


# ── contacts ───────────────────────────────────────────────────────────

class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    email: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    role: Mapped[str] = mapped_column(String(64), default="admin")
    escalation_level: Mapped[int] = mapped_column(Integer, default=1)
    quiet_hours_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quiet_hours_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── actions ────────────────────────────────────────────────────────────

class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(256))
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    alert: Mapped["Alert"] = relationship("Alert", back_populates="actions")


# ── blocklist ──────────────────────────────────────────────────────────

class BlockedIP(Base):
    __tablename__ = "blocklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    reason: Mapped[str] = mapped_column(String(256))
    alert_id: Mapped[Optional[int]] = mapped_column(ForeignKey("alerts.id"), nullable=True)
    blocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── watched_sites ──────────────────────────────────────────────────────

class WatchedSite(Base):
    __tablename__ = "watched_sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    owner_note: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_response_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ssl_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)


# ── watched_emails ─────────────────────────────────────────────────────

class WatchedEmail(Base):
    __tablename__ = "watched_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    owner_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
