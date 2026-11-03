import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime
from app.main import app
from app.database.connection import AsyncSessionLocal
from app.models.user import User
from app.core.security import hash_password, create_access_token


async def create_user_with_role(role: str) -> tuple[User, str]:
    """Helper to create a user with a given role and generate an access token."""
    ts = int(datetime.now().timestamp() * 1000)
    email = f"user_{role}_{ts}@krishiguide.org"
    async with AsyncSessionLocal() as session:
        user = User(
            full_name=f"Test {role.capitalize()}",
            email=email,
            hashed_password=hash_password("Password123!"),
            role=role,
            account_status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        token = create_access_token(subject=user.id, role=user.role)
        return user, token


@pytest.mark.asyncio
async def test_unauthenticated_requests_return_401():
    """Verify unauthenticated requests to protected endpoints return 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res1 = await ac.get("/api/rbac/admin-only")
        assert res1.status_code == 401

        res2 = await ac.get("/api/rbac/expert-only")
        assert res2.status_code == 401

        res3 = await ac.get("/api/rbac/farmer-only")
        assert res3.status_code == 401


@pytest.mark.asyncio
async def test_farmer_permissions_and_unauthorized_rejections():
    """Verify farmer can access farmer endpoints, but is rejected from admin/expert endpoints."""
    farmer, token = await create_user_with_role("farmer")
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Authorized access
        farmer_res = await ac.get("/api/rbac/farmer-only", headers=headers)
        assert farmer_res.status_code == 200
        assert farmer_res.json()["role"] == "farmer"

        # Unauthorized access to admin endpoint
        admin_res = await ac.get("/api/rbac/admin-only", headers=headers)
        assert admin_res.status_code == 403
        assert "forbidden" in admin_res.json()["error"]["message"].lower()

        # Unauthorized access to expert endpoint
        expert_res = await ac.get("/api/rbac/expert-only", headers=headers)
        assert expert_res.status_code == 403


@pytest.mark.asyncio
async def test_expert_permissions_and_unauthorized_rejections():
    """Verify expert can access expert endpoints, but is rejected from admin endpoints."""
    expert, token = await create_user_with_role("expert")
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Authorized access
        expert_res = await ac.get("/api/rbac/expert-only", headers=headers)
        assert expert_res.status_code == 200
        assert expert_res.json()["role"] == "expert"

        # Unauthorized access to admin endpoint
        admin_res = await ac.get("/api/rbac/admin-only", headers=headers)
        assert admin_res.status_code == 403

        # Unauthorized access to strictly farmer endpoint
        farmer_res = await ac.get("/api/rbac/farmer-only", headers=headers)
        assert farmer_res.status_code == 403


@pytest.mark.asyncio
async def test_admin_permissions():
    """Verify admin has authorized access to admin endpoints."""
    admin, token = await create_user_with_role("admin")
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin_res = await ac.get("/api/rbac/admin-only", headers=headers)
        assert admin_res.status_code == 200
        assert admin_res.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_farmer_resource_ownership_protection():
    """Verify farmers can only access their own records, and cross-farmer access is blocked."""
    farmer1, token1 = await create_user_with_role("farmer")
    farmer2, token2 = await create_user_with_role("farmer")
    admin, admin_token = await create_user_with_role("admin")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Farmer 1 accesses own resource -> 200
        res1 = await ac.get(
            f"/api/rbac/farmer-resource/{farmer1.id}",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert res1.status_code == 200
        assert res1.json()["owner_id"] == farmer1.id

        # Farmer 2 attempts to access Farmer 1's resource -> 403 Forbidden
        res2 = await ac.get(
            f"/api/rbac/farmer-resource/{farmer1.id}",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert res2.status_code == 403
        assert "forbidden" in res2.json()["error"]["message"].lower()

        # Admin accesses Farmer 1's resource -> 200 (admin override)
        res_admin = await ac.get(
            f"/api/rbac/farmer-resource/{farmer1.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_admin.status_code == 200


@pytest.mark.asyncio
async def test_expert_case_access_control():
    """Verify expert case isolation rules between assigned experts and farmers."""
    farmer, farmer_token = await create_user_with_role("farmer")
    other_farmer, other_farmer_token = await create_user_with_role("farmer")
    expert1, expert1_token = await create_user_with_role("expert")
    expert2, expert2_token = await create_user_with_role("expert")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Assigned expert accesses case -> 200
        res_expert1 = await ac.get(
            f"/api/rbac/expert-case/{farmer.id}/{expert1.id}",
            headers={"Authorization": f"Bearer {expert1_token}"},
        )
        assert res_expert1.status_code == 200

        # 2. Different expert attempts to access case -> 403 Forbidden
        res_expert2 = await ac.get(
            f"/api/rbac/expert-case/{farmer.id}/{expert1.id}",
            headers={"Authorization": f"Bearer {expert2_token}"},
        )
        assert res_expert2.status_code == 403

        # 3. Owner farmer accesses case -> 200
        res_farmer = await ac.get(
            f"/api/rbac/expert-case/{farmer.id}/{expert1.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert res_farmer.status_code == 200

        # 4. Different farmer attempts to access case -> 403 Forbidden
        res_other_farmer = await ac.get(
            f"/api/rbac/expert-case/{farmer.id}/{expert1.id}",
            headers={"Authorization": f"Bearer {other_farmer_token}"},
        )
        assert res_other_farmer.status_code == 403

