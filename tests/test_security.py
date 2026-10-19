"""
NightWatcher Tests — Security Layers & Verification
Testing:
1. Server-Side Validation (Payload bounds, schema enforcement, query limits)
2. SSRF Protection (Cloud metadata, loopback, private RFC1918 addresses)
3. Rate Limiting (Token-bucket / sliding window abuse protection)
4. Password Hashing (Salted PBKDF2, constant-time verification)
5. Information Leakage & Security Headers
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db import init_db
from app.engine.security import (
    is_safe_url,
    hash_password,
    verify_password,
    RateLimiter,
)
from demo.fake_login_app import app as demo_app


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()


# ---------------------------------------------------------------------------
# 1. Server-Side Validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_server_validation_rejects_invalid_event_type():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Event type must match regex ^[a-z0-9_]{3,50}$
        resp = await client.post(
            "/api/events/",
            json={
                "type": "INVALID TYPE WITH SPACES",
                "source": "pytest",
                "details": {"test": 123},
            },
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_server_validation_rejects_excessive_pagination():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # limit is capped at 200 max
        resp = await client.get("/api/alerts/?limit=999")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 2. SSRF Protection
# ---------------------------------------------------------------------------
def test_ssrf_validator_blocks_internal_targets():
    # Cloud metadata (always blocked even if allow_local_demo=True)
    safe, _ = is_safe_url("http://169.254.169.254/latest/meta-data/")
    assert safe is False

    # Loopback (blocked in production when allow_local_demo=False)
    safe, _ = is_safe_url("http://127.0.0.1:8000/admin", allow_local_demo=False)
    assert safe is False
    safe, _ = is_safe_url("http://localhost:8000/", allow_local_demo=False)
    assert safe is False

    # Private IP ranges
    safe, _ = is_safe_url("http://10.0.0.1/metrics", allow_local_demo=False)
    assert safe is False
    safe, _ = is_safe_url("http://192.168.1.1/router", allow_local_demo=False)
    assert safe is False
    safe, _ = is_safe_url("http://172.16.0.1/", allow_local_demo=False)
    assert safe is False

    # Invalid schemes
    safe, _ = is_safe_url("file:///etc/passwd")
    assert safe is False
    safe, _ = is_safe_url("gopher://127.0.0.1:25")
    assert safe is False

    # Valid public domains
    safe, _ = is_safe_url("https://example.com")
    assert safe is True
    safe, _ = is_safe_url("https://google.com/test")
    assert safe is True


@pytest.mark.asyncio
async def test_website_watcher_ssrf_prevention():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/watchers/website/check",
            json={"url": "http://169.254.169.254/latest/meta-data/"},
        )
        assert resp.status_code == 400
        assert "ssrf" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. Rate Limiting
# ---------------------------------------------------------------------------
def test_rate_limiter_enforcement():
    limiter = RateLimiter(requests_per_minute=60, burst=3)
    client_key = "192.0.2.1"

    # First 3 requests should pass
    allowed, _ = limiter.is_allowed(client_key)
    assert allowed is True
    allowed, _ = limiter.is_allowed(client_key)
    assert allowed is True
    allowed, _ = limiter.is_allowed(client_key)
    assert allowed is True

    # 4th request must be denied
    allowed, retry_after = limiter.is_allowed(client_key)
    assert allowed is False
    assert retry_after > 0

    # Different client key is not blocked
    allowed_other, _ = limiter.is_allowed("192.0.2.2")
    assert allowed_other is True


# ---------------------------------------------------------------------------
# 4. Salted Password Hashing & Verification
# ---------------------------------------------------------------------------
def test_password_hashing_security():
    password = "SuperSecretPassword123!"
    h1 = hash_password(password)
    h2 = hash_password(password)

    # Hashes must differ due to unique salts
    assert h1 != h2
    assert h1.startswith("pbkdf2_sha256$")

    # Correct password verifies
    assert verify_password(password, h1) is True
    assert verify_password(password, h2) is True

    # Wrong password rejected
    assert verify_password("WrongPassword!", h1) is False


# ---------------------------------------------------------------------------
# 5. Information Leakage Prevention & Security Headers
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_security_headers_present():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert "Content-Security-Policy" in resp.headers


@pytest.mark.asyncio
async def test_demo_fake_login_enumeration_prevention():
    transport = ASGITransport(app=demo_app)
    async with AsyncClient(transport=transport, base_url="http://demo") as client:
        # 1. Non-existent user
        resp1 = await client.post(
            "/login",
            data={"username": "non_existent_user_999", "password": "anypassword"},
            follow_redirects=False,
        )
        assert resp1.status_code == 303
        assert resp1.headers["location"] == "/login?error=Invalid+username+or+password"

        # 2. Existing user with wrong password
        resp2 = await client.post(
            "/login",
            data={"username": "admin", "password": "wrong_password"},
            follow_redirects=False,
        )
        assert resp2.status_code == 303
        # Exactly identical redirect error message, preventing user enumeration
        assert resp2.headers["location"] == "/login?error=Invalid+username+or+password"
