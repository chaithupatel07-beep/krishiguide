import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime
from app.main import app
from app.database.connection import AsyncSessionLocal
from app.models.user import User


@pytest.mark.asyncio
async def test_register_farmer_success():
    """Verify registration of a new farmer returns 201 and default role 'farmer'."""
    transport = ASGITransport(app=app)
    ts = int(datetime.now().timestamp() * 1000)
    email = f"farmer_test_{ts}@krishiguide.org"

    payload = {
        "full_name": "Sita Ram",
        "email": email,
        "password": "Password123!",
        "phone_number": "+919812345678",
    }
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/auth/register", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email
    assert data["role"] == "farmer"
    assert data["account_status"] == "active"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected():
    """Verify duplicate email registration is rejected with HTTP 400."""
    transport = ASGITransport(app=app)
    ts = int(datetime.now().timestamp() * 1000)
    email = f"duplicate_{ts}@krishiguide.org"

    payload = {
        "full_name": "Original User",
        "email": email,
        "password": "Password123!",
    }
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res1 = await ac.post("/api/auth/register", json=payload)
        assert res1.status_code == 201

        # Attempt to register again with same email
        res2 = await ac.post("/api/auth/register", json=payload)
        assert res2.status_code == 400
        data = res2.json()
        assert "already exists" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_register_admin_role_escalation_rejected():
    """Verify users cannot register themselves as admin or expert (HTTP 403)."""
    transport = ASGITransport(app=app)
    ts = int(datetime.now().timestamp() * 1000)

    # Attempt to self-register as admin
    admin_payload = {
        "full_name": "Hacker Admin",
        "email": f"hacker_admin_{ts}@krishiguide.org",
        "password": "Password123!",
        "role": "admin",
    }
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res_admin = await ac.post("/api/auth/register", json=admin_payload)
    assert res_admin.status_code == 403

    # Attempt to self-register as expert
    expert_payload = {
        "full_name": "Fake Expert",
        "email": f"fake_expert_{ts}@krishiguide.org",
        "password": "Password123!",
        "role": "expert",
    }
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res_expert = await ac.post("/api/auth/register", json=expert_payload)
    assert res_expert.status_code == 403


@pytest.mark.asyncio
async def test_login_success_and_get_me():
    """Verify login with valid credentials returns JWT and /api/auth/me returns profile."""
    transport = ASGITransport(app=app)
    ts = int(datetime.now().timestamp() * 1000)
    email = f"auth_user_{ts}@krishiguide.org"
    password = "CorrectPassword123!"

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Register
        reg_res = await ac.post("/api/auth/register", json={
            "full_name": "Krishna Reddy",
            "email": email,
            "password": password,
        })
        assert reg_res.status_code == 201

        # 2. Login
        login_res = await ac.post("/api/auth/login", json={
            "email": email,
            "password": password,
        })
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        token = token_data["access_token"]

        # 3. Access /api/auth/me with Bearer token
        me_res = await ac.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        user_info = me_res.json()
        assert user_info["email"] == email
        assert user_info["full_name"] == "Krishna Reddy"
        assert user_info["role"] == "farmer"


@pytest.mark.asyncio
async def test_login_incorrect_password_rejected():
    """Verify login with incorrect password returns HTTP 401."""
    transport = ASGITransport(app=app)
    ts = int(datetime.now().timestamp() * 1000)
    email = f"wrong_pwd_{ts}@krishiguide.org"

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/api/auth/register", json={
            "full_name": "Test User",
            "email": email,
            "password": "CorrectPassword123!",
        })

        bad_res = await ac.post("/api/auth/login", json={
            "email": email,
            "password": "WrongPassword999!",
        })
    assert bad_res.status_code == 401
    data = bad_res.json()
    assert "invalid email or password" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_auth_me_rejects_invalid_token():
    """Verify /api/auth/me rejects missing or invalid tokens with HTTP 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # No header
        res1 = await ac.get("/api/auth/me")
        assert res1.status_code == 401

        # Invalid token string
        res2 = await ac.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.payload"})
        assert res2.status_code == 401


@pytest.mark.asyncio
async def test_login_suspended_account_rejected():
    """Verify that deactivated or suspended accounts cannot login (HTTP 403)."""
    transport = ASGITransport(app=app)
    ts = int(datetime.now().timestamp() * 1000)
    email = f"suspended_{ts}@krishiguide.org"
    password = "MyPassword123!"

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        reg_res = await ac.post("/api/auth/register", json={
            "full_name": "Suspended Farmer",
            "email": email,
            "password": password,
        })
        assert reg_res.status_code == 201
        user_id = reg_res.json()["id"]

    # Manually suspend the account in DB
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        user.account_status = "suspended"
        await session.commit()

    # Attempt to login with suspended account
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/api/auth/login", json={
            "email": email,
            "password": password,
        })
    assert login_res.status_code == 403
    assert "suspended" in login_res.json()["error"]["message"].lower()
