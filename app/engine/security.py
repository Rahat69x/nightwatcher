"""
NightWatcher — Core Security Controls & Defensive Utilities
Implements:
1. Server-side validation helpers (SSRF prevention, URL sanity)
2. Cryptographic password hashing (PBKDF2-HMAC-SHA256 with salt & constant-time check)
3. Sliding-window Token Bucket rate limiter
4. Security response headers middleware
"""
from __future__ import annotations
import hashlib
import ipaddress
import logging
import secrets
import socket
import time
from collections import defaultdict
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

log = logging.getLogger(__name__)

# Cloud metadata addresses that must ALWAYS be blocked
BLOCKED_METADATA_IPS = {
    "169.254.169.254",    # AWS/GCP/Azure instance metadata
    "fd00:ec2::254",       # AWS IPv6 metadata
    "metadata.google.internal",
}


# ── 1. SSRF Prevention ──────────────────────────────────────────────────

def is_safe_url(url: str, allow_local_demo: bool = True) -> Tuple[bool, str]:
    """
    Validates a URL to prevent Server-Side Request Forgery (SSRF).
    Blocks non-HTTP/HTTPS schemes, cloud metadata, and internal/private IP ranges
    unless allow_local_demo is True (used strictly for demoing localhost:8001).
    """
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False, "Malformed URL format"

    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Prohibited scheme '{parsed.scheme}'. Only http:// and https:// are permitted."

    hostname = (parsed.hostname or "").lower().strip()
    if not hostname:
        return False, "Missing hostname in URL"

    if hostname in BLOCKED_METADATA_IPS:
        return False, "Access to cloud metadata endpoints is strictly forbidden (SSRF protection)."

    # Resolve hostname to IP to check for DNS rebinding / private IP targets
    try:
        resolved_ips = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        # If hostname cannot be resolved, return error
        return False, f"Could not resolve hostname '{hostname}'."
    except Exception as e:
        return False, f"DNS resolution failed: {e}"

    for addr in resolved_ips:
        ip_str = addr[4][0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        # Check cloud metadata range (169.254.0.0/16)
        if ip_obj in ipaddress.ip_network("169.254.0.0/16"):
            return False, "Prohibited link-local / metadata address range (SSRF protection)."

        # Check loopback and private ranges
        if ip_obj.is_loopback:
            if not allow_local_demo:
                return False, "Access to loopback interface is restricted (SSRF protection)."

        elif ip_obj.is_private:
            if not allow_local_demo:
                return False, "Access to private internal network addresses is prohibited (SSRF protection)."

        elif ip_obj.is_multicast or ip_obj.is_reserved:
            return False, "Access to multicast or reserved IP address is prohibited."

    return True, "URL is safe"


# ── 2. Cryptographic Password Hashing (PBKDF2-HMAC-SHA256) ───────────────

def hash_password(password: str, iterations: int = 200_000) -> str:
    """
    Hashes a password with a cryptographically secure 16-byte random salt
    using PBKDF2-HMAC-SHA256 with 200,000 iterations.
    Format: 'pbkdf2_sha256$<iterations>$<hex_salt>$<hex_hash>'
    """
    if not password:
        raise ValueError("Password cannot be empty")
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """
    Verifies a password against the stored hash in constant time
    using secrets.compare_digest to prevent timing attacks.
    """
    if not stored_hash or not plain_password:
        return False

    try:
        parts = stored_hash.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False

        iterations = int(parts[1])
        salt = parts[2]
        expected_hex = parts[3]

        computed = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return secrets.compare_digest(computed.hex(), expected_hex)
    except Exception as e:
        log.warning(f"Password verification error: {e}")
        return False


# ── 3. Sliding Window Rate Limiter ──────────────────────────────────────

class RateLimiter:
    """
    In-memory rate limiter using sliding token bucket.
    Tracks requests per IP per minute.
    """
    def __init__(self, requests_per_minute: int = 120, burst: int = 30):
        self.rpm = requests_per_minute
        self.burst = burst
        self.rate = requests_per_minute / 60.0  # tokens per second
        self.tokens: Dict[str, float] = defaultdict(lambda: float(burst))
        self.last_update: Dict[str, float] = defaultdict(time.time)

    def is_allowed(self, client_id: str) -> Tuple[bool, int]:
        """
        Returns (allowed: bool, retry_after_seconds: int).
        """
        now = time.time()
        time_passed = now - self.last_update[client_id]
        self.last_update[client_id] = now

        # Add regenerated tokens up to burst
        self.tokens[client_id] = min(
            float(self.burst),
            self.tokens[client_id] + time_passed * self.rate,
        )

        if self.tokens[client_id] >= 1.0:
            self.tokens[client_id] -= 1.0
            return True, 0
        else:
            wait_seconds = int((1.0 - self.tokens[client_id]) / self.rate) + 1
            return False, wait_seconds


# Global rate limiter instances
api_limiter = RateLimiter(requests_per_minute=180, burst=40)
scan_limiter = RateLimiter(requests_per_minute=30, burst=10)


# ── 4. Security Headers Middleware ──────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Enforces essential security headers on all HTTP responses:
    - Content-Security-Policy (XSS prevention)
    - X-Content-Type-Options: nosniff (MIME-sniffing prevention)
    - X-Frame-Options: DENY (Clickjacking prevention)
    - Referrer-Policy (Information leakage prevention)
    - Strict-Transport-Security (HTTPS enforcement)
    - Permissions-Policy (Feature restriction)
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Standard defense-in-depth headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # HSTS (applied in production or when accessed via HTTPS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content Security Policy (allows Google Fonts and local static assets)
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers["Content-Security-Policy"] = csp

        return response
