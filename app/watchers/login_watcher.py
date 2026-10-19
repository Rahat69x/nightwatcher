"""
NightWatcher — Login Watcher
Tails a JSON log file or receives events from the demo app.
Rules:
  - 5+ failed logins from one IP in 60s → brute_force
  - 1 IP trying 3+ different usernames → credential_stuffing
  - Successful login after >= 3 failures from same IP → login_success_after_brute
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Dict, Deque, Set

from app.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

# In-memory state (reset on restart; fine for demo)
_failed: Dict[str, Deque[datetime]] = defaultdict(deque)          # ip -> timestamps
_usernames: Dict[str, Set[str]] = defaultdict(set)                 # ip -> usernames tried
_file_offset: int = 0


async def process_login_event(
    db,
    ip: str,
    username: str,
    success: bool,
    user_agent: str = "",
) -> None:
    """Called by the demo app API and by the log tail loop."""
    from app.engine.ingest import ingest_event

    now = datetime.now(timezone.utc)
    window = timedelta(seconds=settings.brute_force_window_seconds)

    # Record failed attempt
    if not success:
        _failed[ip].append(now)
        _usernames[ip].add(username)
        # Prune old entries
        while _failed[ip] and now - _failed[ip][0] > window:
            _failed[ip].popleft()

        recent = len(_failed[ip])
        unique_users = len(_usernames[ip])

        # Check credential stuffing first (many usernames)
        if unique_users >= 3 and recent >= 2:
            await ingest_event(db, "credential_stuffing", f"login_watcher:{ip}", {
                "source_ip": ip,
                "unique_usernames": unique_users,
                "failed_attempts": recent,
                "off_hours": _is_off_hours(),
            })

        # Brute force (many attempts, same or different user)
        elif recent >= settings.brute_force_threshold:
            await ingest_event(db, "brute_force", f"login_watcher:{ip}", {
                "source_ip": ip,
                "failed_attempts": recent,
                "username": username,
                "off_hours": _is_off_hours(),
            })

    else:
        # Successful login — was this after failed attempts?
        recent = len(_failed.get(ip, []))
        if recent >= 3:
            await ingest_event(db, "login_success_after_brute", f"login_watcher:{ip}", {
                "source_ip": ip,
                "username": username,
                "failed_attempts_before": recent,
                "off_hours": _is_off_hours(),
            })
        # Clear state for this IP
        _failed.pop(ip, None)
        _usernames.pop(ip, None)


def _is_off_hours() -> bool:
    hour = datetime.now().hour
    return hour >= settings.quiet_hours_start or hour < settings.quiet_hours_end


async def tail_log_file(db) -> None:
    """
    Background task: tail the auth log file and process each new JSON line.
    Log format: {"ip": "...", "username": "...", "success": true/false, "ts": "..."}
    """
    global _file_offset
    log_path = settings.login_log_file

    if not os.path.exists(log_path):
        log.warning(f"Login log file not found: {log_path}")
        return

    while True:
        try:
            with open(log_path, "r") as f:
                f.seek(_file_offset)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        await process_login_event(
                            db,
                            ip=data.get("ip", "0.0.0.0"),
                            username=data.get("username", "unknown"),
                            success=bool(data.get("success", False)),
                            user_agent=data.get("user_agent", ""),
                        )
                    except json.JSONDecodeError:
                        pass
                _file_offset = f.tell()
        except Exception as e:
            log.error(f"Log tail error: {e}")

        await asyncio.sleep(2)  # poll every 2 seconds
