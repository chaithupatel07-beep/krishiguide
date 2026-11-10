import pytest
from datetime import datetime
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.connection import AsyncSessionLocal
from app.models.user import User
from app.models.expert import ExpertCase
from app.core.security import hash_password, create_access_token


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_admin_dashboard_real_aggregations():
    """Verify GET /api/admin/dashboard returns accurate real SQL aggregated metrics."""
    ts = int(datetime.now().timestamp() * 1000)
    admin_email = f"admin_dash_{ts}@smartfarming.org"

    async with AsyncSessionLocal() as session:
        admin = User(
            full_name="System Administrator",
            email=admin_email,
            hashed_password=hash_password("Pass123!"),
            role="admin",
            account_status="active",
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        admin_id = admin.id

    token = create_access_token(subject=admin_id, role="admin")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/admin/dashboard", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total_users"] >= 1
    assert data["admins_count"] >= 1
    assert "total_documents" in data
    assert "total_conversations" in data
    assert "total_cases" in data
    assert Decimal(str(data["total_expenses_amount"])) >= Decimal("0.00")


@pytest.mark.asyncio
async def test_admin_user_management():
    """Verify admin listing users, promoting roles, deactivating, and preventing self-demotion."""
    ts = int(datetime.now().timestamp() * 1000)
    admin_email = f"admin_mgr_{ts}@smartfarming.org"
    farmer_email = f"farmer_mgr_{ts}@smartfarming.org"

    async with AsyncSessionLocal() as session:
        admin = User(full_name="Admin Mgr", email=admin_email, hashed_password=hash_password("Pass123!"), role="admin", account_status="active")
        farmer = User(full_name="Farmer Target", email=farmer_email, hashed_password=hash_password("Pass123!"), role="farmer", account_status="active")
        session.add_all([admin, farmer])
        await session.commit()
        await session.refresh(admin)
        await session.refresh(farmer)
        admin_id, farmer_id = admin.id, farmer.id

    token = create_access_token(subject=admin_id, role="admin")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. List users
        r_list = await client.get("/api/admin/users", headers=headers)
        assert r_list.status_code == 200
        assert r_list.json()["total"] >= 2

        # 2. Promote farmer to expert
        r_promote = await client.patch(
            f"/api/admin/users/{farmer_id}",
            json={"role": "expert"},
            headers=headers,
        )
        assert r_promote.status_code == 200
        assert r_promote.json()["role"] == "expert"

        # 3. Suspend farmer account
        r_suspend = await client.patch(
            f"/api/admin/users/{farmer_id}",
            json={"account_status": "suspended"},
            headers=headers,
        )
        assert r_suspend.status_code == 200
        assert r_suspend.json()["account_status"] == "suspended"

        # 4. Attempt self-demotion -> 400 Bad Request
        r_self_demote = await client.patch(
            f"/api/admin/users/{admin_id}",
            json={"role": "farmer"},
            headers=headers,
        )
        assert r_self_demote.status_code == 400

        # 5. Attempt self-deactivation -> 400 Bad Request
        r_self_deact = await client.patch(
            f"/api/admin/users/{admin_id}",
            json={"account_status": "inactive"},
            headers=headers,
        )
        assert r_self_deact.status_code == 400


@pytest.mark.asyncio
async def test_expert_case_workflow():
    """Verify expert listing cases, responding with verified agronomic guidance, and resolving."""
    ts = int(datetime.now().timestamp() * 1000)
    expert_email = f"expert_{ts}@smartfarming.org"
    farmer_email = f"farmer_case_{ts}@smartfarming.org"

    async with AsyncSessionLocal() as session:
        expert = User(full_name="Dr. Agricultural Expert", email=expert_email, hashed_password=hash_password("Pass123!"), role="expert", account_status="active")
        farmer = User(full_name="Farmer Ramesh", email=farmer_email, hashed_password=hash_password("Pass123!"), role="farmer", account_status="active")
        session.add_all([expert, farmer])
        await session.commit()
        await session.refresh(expert)
        await session.refresh(farmer)
        expert_id, farmer_id = expert.id, farmer.id

        # Create a pending case
        case = ExpertCase(
            farmer_id=farmer_id,
            title="Clarification on Groundnut Rust dosage",
            farmer_question="What is the exact fungicide dosage for groundnut rust?",
            ai_response_snapshot="Apply Mancozeb 75 WP at 1000g/ha.",
            status="pending",
        )
        session.add(case)
        await session.commit()
        await session.refresh(case)
        case_id = case.id

    token = create_access_token(subject=expert_id, role="expert")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Expert views cases
        r_cases = await client.get("/api/expert/cases", headers=headers)
        assert r_cases.status_code == 200
        assert any(c["id"] == case_id for c in r_cases.json()["items"])

        # 2. Expert responds to case
        r_resp = await client.post(
            f"/api/expert/cases/{case_id}/respond",
            json={
                "expert_response": "Verified standard recommendation: Apply Mancozeb 75% WP @ 1000-1250 g/ha dissolved in 500 liters of water. Spray twice at 10-14 days interval.",
                "recommendations": ["Wear protective gear during spraying", "Avoid spraying in windy conditions"],
                "mark_resolved": True,
            },
            headers=headers,
        )
        assert r_resp.status_code == 200
        case_res = r_resp.json()
        assert case_res["status"] == "resolved"
        assert case_res["expert_id"] == expert_id
        assert case_res["resolved_at"] is not None

        # 3. Update status to closed
        r_close = await client.patch(
            f"/api/expert/cases/{case_id}/status",
            json={"status": "closed"},
            headers=headers,
        )
        assert r_close.status_code == 200
        assert r_close.json()["status"] == "closed"


@pytest.mark.asyncio
async def test_feedback_and_audit_logs():
    """Verify farmer feedback submission and admin audit log retrieval."""
    ts = int(datetime.now().timestamp() * 1000)
    farmer_email = f"farmer_fb_{ts}@smartfarming.org"
    admin_email = f"admin_fb_{ts}@smartfarming.org"

    async with AsyncSessionLocal() as session:
        farmer = User(full_name="Farmer Feedback Test", email=farmer_email, hashed_password=hash_password("Pass123!"), role="farmer", account_status="active")
        admin = User(full_name="Admin Audit Test", email=admin_email, hashed_password=hash_password("Pass123!"), role="admin", account_status="active")
        session.add_all([farmer, admin])
        await session.commit()
        await session.refresh(farmer)
        await session.refresh(admin)
        farmer_id, admin_id = farmer.id, admin.id

    token_farmer = create_access_token(subject=farmer_id, role="farmer")
    token_admin = create_access_token(subject=admin_id, role="admin")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Farmer submits feedback
        r_fb = await client.post(
            "/api/feedback",
            json={
                "feedback_type": "ai_accuracy",
                "rating": 5,
                "comments": "Groundnut soil recommendations were very helpful and accurate.",
            },
            headers={"Authorization": f"Bearer {token_farmer}"},
        )
        assert r_fb.status_code == 201

        # 2. Admin retrieves feedback
        r_get_fb = await client.get("/api/admin/feedback", headers={"Authorization": f"Bearer {token_admin}"})
        assert r_get_fb.status_code == 200
        assert r_get_fb.json()["total"] >= 1

        # 3. Admin retrieves audit logs
        r_audit = await client.get("/api/admin/audit-logs", headers={"Authorization": f"Bearer {token_admin}"})
        assert r_audit.status_code == 200
        assert r_audit.json()["total"] >= 1


@pytest.mark.asyncio
async def test_role_enforcement_on_admin_and_expert():
    """Verify farmers and experts cannot access unauthorized admin or expert endpoints."""
    ts = int(datetime.now().timestamp() * 1000)
    farmer_email = f"f_unauth_{ts}@smartfarming.org"
    expert_email = f"e_unauth_{ts}@smartfarming.org"

    async with AsyncSessionLocal() as session:
        f = User(full_name="Unauthorized Farmer", email=farmer_email, hashed_password=hash_password("Pass123!"), role="farmer", account_status="active")
        e = User(full_name="Specialist Expert", email=expert_email, hashed_password=hash_password("Pass123!"), role="expert", account_status="active")
        session.add_all([f, e])
        await session.commit()
        await session.refresh(f)
        await session.refresh(e)
        f_id, e_id = f.id, e.id

    token_farmer = create_access_token(subject=f_id, role="farmer")
    token_expert = create_access_token(subject=e_id, role="expert")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Farmer cannot access admin dashboard -> 403
        r1 = await client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {token_farmer}"})
        assert r1.status_code == 403

        # Farmer cannot access expert cases -> 403
        r2 = await client.get("/api/expert/cases", headers={"Authorization": f"Bearer {token_farmer}"})
        assert r2.status_code == 403

        # Expert cannot access admin dashboard -> 403
        r3 = await client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {token_expert}"})
        assert r3.status_code == 403

        # Expert cannot modify user roles -> 403
        r4 = await client.patch(f"/api/admin/users/{f_id}", json={"role": "admin"}, headers={"Authorization": f"Bearer {token_expert}"})
        assert r4.status_code == 403

