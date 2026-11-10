import pytest
from datetime import datetime, date
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.connection import AsyncSessionLocal
from app.models.user import User
from app.core.security import hash_password, create_access_token


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_security_password_hashes_never_exposed():
    """Verify that user API responses never leak hashed_password or secrets."""
    ts = int(datetime.now().timestamp() * 1000)
    farmer_email = f"sec_user_{ts}@smartfarming.org"

    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Security Audit User",
            email=farmer_email,
            hashed_password=hash_password("SuperSecret123!"),
            role="farmer",
            account_status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    token = create_access_token(subject=user_id, role="farmer")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check /api/auth/me
        r_me = await client.get("/api/auth/me", headers=headers)
        assert r_me.status_code == 200
        me_json = r_me.json()
        assert "hashed_password" not in me_json
        assert "password" not in me_json
        assert "SuperSecret123!" not in str(me_json)


@pytest.mark.asyncio
async def test_security_sql_injection_resilience():
    """Verify that SQL injection payloads in parameters do not execute or compromise data."""
    ts = int(datetime.now().timestamp() * 1000)
    farmer_email = f"sqli_user_{ts}@smartfarming.org"

    async with AsyncSessionLocal() as session:
        user = User(
            full_name="SQLi Probe User",
            email=farmer_email,
            hashed_password=hash_password("Pass123!"),
            role="farmer",
            account_status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    token = create_access_token(subject=user_id, role="farmer")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # SQL injection payloads in filters and queries
        sqli_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "1 UNION SELECT null, null, null--",
        ]

        for payload in sqli_payloads:
            # Test in expense filters
            r_exp = await client.get(f"/api/farm/expenses?crop_name={payload}", headers=headers)
            assert r_exp.status_code == 200
            assert r_exp.json()["total_count"] == 0

            # Test in chat query
            r_chat = await client.post("/api/chat", json={"question": payload}, headers=headers)
            assert r_chat.status_code in [200, 400]


@pytest.mark.asyncio
async def test_security_admin_endpoint_strict_isolation():
    """Verify all admin endpoints reject non-admin tokens with 403 Forbidden."""
    ts = int(datetime.now().timestamp() * 1000)
    farmer_email = f"f_probe_{ts}@smartfarming.org"
    expert_email = f"e_probe_{ts}@smartfarming.org"

    async with AsyncSessionLocal() as session:
        f = User(full_name="Farmer Probe", email=farmer_email, hashed_password=hash_password("Pass123!"), role="farmer", account_status="active")
        e = User(full_name="Expert Probe", email=expert_email, hashed_password=hash_password("Pass123!"), role="expert", account_status="active")
        session.add_all([f, e])
        await session.commit()
        await session.refresh(f)
        await session.refresh(e)
        f_id, e_id = f.id, e.id

    f_headers = {"Authorization": f"Bearer {create_access_token(subject=f_id, role='farmer')}"}
    e_headers = {"Authorization": f"Bearer {create_access_token(subject=e_id, role='expert')}"}

    admin_endpoints = [
        ("GET", "/api/admin/dashboard"),
        ("GET", "/api/admin/users"),
        ("GET", "/api/admin/feedback"),
        ("GET", "/api/admin/audit-logs"),
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for method, url in admin_endpoints:
            # Farmer probe
            rf = await client.request(method, url, headers=f_headers)
            assert rf.status_code == 403, f"Farmer accessed {url} with status {rf.status_code}"

            # Expert probe
            re = await client.request(method, url, headers=e_headers)
            assert re.status_code == 403, f"Expert accessed {url} with status {re.status_code}"


@pytest.mark.asyncio
async def test_performance_health_and_ready_benchmarks():
    """Verify health and readiness endpoints respond reliably with database status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r_health = await client.get("/api/health")
        assert r_health.status_code == 200
        assert r_health.json()["status"] == "healthy"

        r_ready = await client.get("/api/ready")
        assert r_ready.status_code == 200
        ready_data = r_ready.json()
        assert ready_data["status"] == "ready"
        assert ready_data["database"]["connected"] is True


@pytest.mark.asyncio
async def test_centralized_error_handling_structure():
    """Verify that unhandled / invalid requests return consistent structured JSON errors."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 404 test
        r_404 = await client.get("/api/nonexistent-endpoint-route")
        assert r_404.status_code == 404
        data_404 = r_404.json()
        assert data_404["success"] is False
        assert data_404["error"]["code"] == 404

        # 422 validation test
        r_422 = await client.post("/api/auth/login", json={"email": "not-an-email"})
        assert r_422.status_code == 422
        data_422 = r_422.json()
        assert data_422["success"] is False
        assert data_422["error"]["code"] == 422

