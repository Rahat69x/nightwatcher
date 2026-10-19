"""
NightWatcher Demo — Fake Login Target App ("Apex Vault")
A vulnerable demo web application to prove the attack -> detect -> auto-block loop.
Runs on port 8001 by default.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx
import uvicorn

from app.db import AsyncSessionLocal
from app.engine.actions import is_ip_blocked
from app.watchers.login_watcher import process_login_event

from app.engine.security import (
    hash_password,
    verify_password,
    RateLimiter,
    SecurityHeadersMiddleware,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("fake_login_app")

app = FastAPI(title="Apex Vault — Customer Portal (Demo Target)")

# Enforce security headers
app.add_middleware(SecurityHeadersMiddleware)

LOG_FILE = Path(__file__).parent / "sample_logs" / "auth.log"
NIGHTWATCHER_API = "http://localhost:8000/api/events/"

# Layer 03: Passwords stored as salted PBKDF2-HMAC-SHA256 hashes (never plain text)
USER_CREDENTIALS_HASHES = {
    "alice": hash_password("SecretPass123!"),
    "bob": hash_password("SuperSafe2026$"),
    "admin": hash_password("Winter2026!"),
}

# Layer 02: Rate limiter for login endpoint (20 attempts/min burst 6)
login_limiter = RateLimiter(requests_per_minute=20, burst=6)


def get_client_ip(request: Request) -> str:
    """Extract real or simulated IP address."""
    if "x-simulated-ip" in request.headers:
        return request.headers["x-simulated-ip"]
    if "x-forwarded-for" in request.headers:
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


@app.middleware("http")
async def blocklist_enforcement_middleware(request: Request, call_next):
    """Enforce NightWatcher autonomous blocklist before serving requests."""
    ip = get_client_ip(request)

    async with AsyncSessionLocal() as db:
        blocked = await is_ip_blocked(db, ip)

    if blocked:
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>403 Forbidden — Blocked by NightWatcher</title>
    <style>
        body {{ background: #0b0f19; color: #f8fafc; font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
        .card {{ background: #161f30; border: 1px solid #ef4444; border-radius: 12px; padding: 32px; max-width: 520px; text-align: center; box-shadow: 0 0 25px rgba(239, 68, 68, 0.3); }}
        h1 {{ color: #ef4444; margin-top: 0; font-size: 1.6rem; }}
        p {{ color: #94a3b8; line-height: 1.6; }}
        .ip-badge {{ background: #261722; color: #f87171; font-family: monospace; padding: 4px 10px; border-radius: 6px; font-weight: bold; }}
        .footer {{ font-size: 0.8rem; color: #64748b; margin-top: 24px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>🚫 Access Blocked</h1>
        <p>Your IP address <span class="ip-badge">{ip}</span> was automatically blocked by <b>NightWatcher Watchdog</b> after suspicious brute force login activity was detected.</p>
        <p>This automated block protects accounts from unauthorized intrusion.</p>
        <div class="footer">Protected by NightWatcher Autonomous Security Watchdog</div>
    </div>
</body>
</html>"""
        return HTMLResponse(content=html, status_code=403)

    return await call_next(request)


@app.get("/", response_class=HTMLResponse)
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    ip = get_client_ip(request)
    error_html = f'<div style="background:rgba(239,68,68,0.2); border:1px solid #ef4444; color:#fca5a5; padding:10px; border-radius:8px; margin-bottom:16px;">{error}</div>' if error else ''

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Apex Vault — Secure Portal</title>
    <style>
        body {{ background: #090d16; color: #f8fafc; font-family: -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
        .box {{ background: #151f32; border: 1px solid #24324c; border-radius: 14px; padding: 36px 32px; width: 360px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
        h2 {{ margin-top: 0; font-size: 1.4rem; color: #38bdf8; }}
        label {{ display: block; font-size: 0.82rem; color: #94a3b8; margin-bottom: 6px; }}
        input {{ width: 100%; box-sizing: border-box; background: #0b111e; border: 1px solid #24324c; color: #fff; padding: 10px; border-radius: 8px; margin-bottom: 16px; outline: none; }}
        input:focus {{ border-color: #38bdf8; }}
        button {{ width: 100%; background: #0284c7; color: white; border: none; padding: 12px; border-radius: 8px; font-weight: bold; cursor: pointer; }}
        button:hover {{ background: #0369a1; }}
        .badge {{ font-size: 0.75rem; color: #64748b; text-align: center; margin-top: 18px; }}
    </style>
</head>
<body>
    <div class="box">
        <h2>Apex Vault Portal</h2>
        <p style="font-size:0.85rem; color:#94a3b8; margin-bottom:20px;">Demo customer system monitored by NightWatcher.</p>
        {error_html}
        <form method="POST" action="/login">
            <label>Username</label>
            <input type="text" name="username" placeholder="e.g. alice, bob, admin" required>
            <label>Password</label>
            <input type="password" name="password" required>
            <button type="submit">Sign In</button>
        </form>
        <div class="badge">Your IP: <span style="font-family:monospace; color:#38bdf8;">{ip}</span></div>
    </div>
</body>
</html>"""


@app.post("/login")
async def do_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    ip = get_client_ip(request)

    # Layer 02: Rate limit login attempts per IP
    allowed, retry_after = login_limiter.is_allowed(ip)
    if not allowed:
        return RedirectResponse(
            url=f"/login?error=Too+many+attempts.+Please+wait+{retry_after}+seconds.",
            status_code=303,
        )

    # Layer 03: Constant-time PBKDF2 hash verification
    stored_hash = USER_CREDENTIALS_HASHES.get(username)
    success = verify_password(password, stored_hash) if stored_hash else False

    # 1. Log to auth.log file
    log_entry = {
        "ip": ip,
        "username": username,
        "success": success,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        log.warning(f"Could not append to auth.log: {e}")

    # 2. Feed directly into login watcher engine
    async with AsyncSessionLocal() as db:
        await process_login_event(db, ip=ip, username=username, success=success)

    # Layer 04: Don't leak whether the username or password was the invalid part (Generic Error)
    if not success:
        return RedirectResponse(
            url="/login?error=Invalid+username+or+password",
            status_code=303,
        )

    return HTMLResponse(f"""
    <html>
    <body style="background:#090d16; color:#10b981; font-family:sans-serif; text-align:center; padding-top:100px;">
        <h1>✅ Login Successful!</h1>
        <p style="color:#e2e8f0;">Welcome back, <b>{username}</b>. You have entered the secured vault area.</p>
        <p><a href="/login" style="color:#38bdf8;">Log Out</a></p>
    </body>
    </html>
    """)


if __name__ == "__main__":
    uvicorn.run("fake_login_app:app", host="0.0.0.0", port=8001, reload=True)
