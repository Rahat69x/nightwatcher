"""
NightWatcher — Central Application Entry Point
FastAPI + Background Scheduler + Watchdog Engine + Web Dashboard
"""
from __future__ import annotations
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.db import init_db, AsyncSessionLocal
from app.engine.escalation import run_escalations
from app.engine.actions import unblock_expired_ips
from app.watchers.website_watcher import run_uptime_checks
from app.watchers.breach_watcher import run_breach_checks
from app.watchers.login_watcher import tail_log_file
from app.api import events, alerts, twilio_webhooks, watchers

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("nightwatcher")

settings = get_settings()

scheduler = AsyncIOScheduler()


async def scheduled_escalations():
    async with AsyncSessionLocal() as db:
        await run_escalations(db)


async def scheduled_unblocks():
    async with AsyncSessionLocal() as db:
        count = await unblock_expired_ips(db)
        if count > 0:
            log.info(f"Unblocked {count} expired IP(s)")


async def scheduled_uptime():
    async with AsyncSessionLocal() as db:
        await run_uptime_checks(db)


async def scheduled_breaches():
    async with AsyncSessionLocal() as db:
        await run_breach_checks(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("Starting NightWatcher Watchdog Engine...")
    await init_db()

    # Start background scheduler
    scheduler.add_job(scheduled_escalations, "interval", seconds=30, id="escalations")
    scheduler.add_job(scheduled_unblocks, "interval", seconds=60, id="unblocks")
    scheduler.add_job(
        scheduled_uptime,
        "interval",
        minutes=settings.uptime_check_interval_minutes,
        id="uptime",
    )
    scheduler.add_job(scheduled_breaches, "interval", hours=24, id="breaches")
    scheduler.start()
    log.info("APScheduler background tasks running.")

    # Start log tailing if configured file exists
    log_task = None
    if os.path.exists(settings.login_log_file):
        async def _tail_loop():
            async with AsyncSessionLocal() as db:
                await tail_log_file(db)
        log_task = asyncio.create_task(_tail_loop())
        log.info(f"Tailing login log: {settings.login_log_file}")

    yield

    # Shutdown
    log.info("Shutting down NightWatcher scheduler...")
    scheduler.shutdown(wait=False)
    if log_task and not log_task.done():
        log_task.cancel()


app = FastAPI(
    title="NightWatcher",
    description="Automated Security Watchdog Engine — Always watching. Loudest when it matters.",
    version="1.0.0",
    lifespan=lifespan,
)

from app.engine.security import SecurityHeadersMiddleware
from fastapi.responses import JSONResponse
import secrets

# Security & Defense-in-depth Middleware
app.add_middleware(SecurityHeadersMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Layer 04: Don't Leak Information Through Errors.
    Logs diagnostics safely to server logs with an incident ID,
    while returning an opaque, safe message to the client.
    """
    error_id = secrets.token_hex(6)
    log.error(f"Internal error [ref:{error_id}]: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. Incident has been safely logged.",
            "incident_id": error_id,
        },
    )

# Include API Routers
app.include_router(events.router)
app.include_router(alerts.router)
app.include_router(twilio_webhooks.router)
app.include_router(watchers.router)

# Mount Dashboard Static Files & Templates
base_dir = Path(__file__).resolve().parent
static_dir = base_dir / "dashboard" / "static"
templates_dir = base_dir / "dashboard" / "templates"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates = Jinja2Templates(directory=str(templates_dir))


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/dashboard/alerts/{alert_id}", response_class=HTMLResponse)
async def serve_dashboard(request: Request, alert_id: int = None):
    """Serve the real-time security dashboard."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"alert_id": alert_id},
    )


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    fav_file = static_dir / "favicon.svg"
    if fav_file.exists():
        return FileResponse(str(fav_file), media_type="image/svg+xml")
    return Response(status_code=204)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handle HTTP exceptions cleanly.
    Renders branded 404.html for browser users, returns JSON for API requests.
    """
    if exc.status_code == 404:
        accept = request.headers.get("accept", "")
        if "text/html" in accept and not request.url.path.startswith("/api/"):
            template_404 = templates_dir / "404.html"
            if template_404.exists():
                return templates.TemplateResponse(
                    request=request,
                    name="404.html",
                    status_code=404,
                )
        return JSONResponse(status_code=404, content={"detail": exc.detail or "Not Found"})
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": "NightWatcher",
        "version": "1.0.0",
        "tagline": "Always watching. Loudest when it matters.",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
