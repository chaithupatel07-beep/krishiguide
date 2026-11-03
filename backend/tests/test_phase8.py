import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.connection import AsyncSessionLocal
from app.models.user import User
from app.models.farm_profile import FarmProfile
from app.models.farm_tool import FarmExpense, CropTask
from app.core.security import hash_password, create_access_token


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_farm_profile_create_and_update():
    """Verify PUT /api/farm/profile creates and updates farmer profile."""
    ts = int(datetime.now().timestamp() * 1000)
    farmer_email = f"farmer_profile_{ts}@krishiguide.org"

    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Farmer Profile Test",
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
        # Initial GET before profile exists -> 404
        r_get404 = await client.get("/api/farm/profile", headers=headers)
        assert r_get404.status_code == 404

        # Create Profile
        payload = {
            "farm_location": "Anantapur District, Andhra Pradesh",
            "farm_size": 4.5,
            "soil_type": "Red sandy loam",
            "crop_details": ["Groundnut", "Paddy"],
            "irrigation_details": ["Drip", "Borewell"],
        }
        r_create = await client.put("/api/farm/profile", json=payload, headers=headers)
        assert r_create.status_code == 200
        data = r_create.json()
        assert data["farm_location"] == "Anantapur District, Andhra Pradesh"
        assert Decimal(str(data["farm_size"])) == Decimal("4.5")
        assert data["soil_type"] == "Red sandy loam"
        assert "Groundnut" in data["crop_details"]

        # Retrieve profile
        r_get = await client.get("/api/farm/profile", headers=headers)
        assert r_get.status_code == 200
        assert r_get.json()["id"] == data["id"]

        # Update profile
        update_payload = {
            "farm_location": "Kadiri, Anantapur District",
            "farm_size": 5.0,
            "soil_type": "Red sandy loam",
            "crop_details": ["Groundnut", "Red Gram"],
            "irrigation_details": ["Drip"],
        }
        r_update = await client.put("/api/farm/profile", json=update_payload, headers=headers)
        assert r_update.status_code == 200
        updated_data = r_update.json()
        assert updated_data["farm_location"] == "Kadiri, Anantapur District"
        assert Decimal(str(updated_data["farm_size"])) == Decimal("5.0")
        assert "Red Gram" in updated_data["crop_details"]


@pytest.mark.asyncio
async def test_cultivation_cost_calculator():
    """Verify cultivation cost calculator with exact Decimal arithmetic."""
    ts = int(datetime.now().timestamp() * 1000)
    farmer_email = f"farmer_calc_{ts}@krishiguide.org"

    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Farmer Calculator Test",
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
        req_body = {
            "crop_name": "Groundnut",
            "land_area": 3.0,
            "seed_cost": 6000.00,
            "fertilizer_cost": 4500.00,
            "labor_cost": 9000.00,
            "irrigation_cost": 1500.00,
            "pesticide_cost": 2000.00,
            "machinery_fuel_cost": 3000.00,
            "post_harvest_transport_cost": 2000.00,
            "expected_yield_per_acre": 8.0,
            "expected_market_price_per_unit": 5500.00,
        }
        response = await client.post("/api/farm/calculate-cost", json=req_body, headers=headers)

    assert response.status_code == 200
    calc = response.json()

    # Total = 6000 + 4500 + 9000 + 1500 + 2000 + 3000 + 2000 = 28000.00
    assert Decimal(str(calc["total_expenditure"])) == Decimal("28000.00")
    # Cost per acre = 28000 / 3 = 9333.33
    assert Decimal(str(calc["cost_per_acre"])) == Decimal("9333.33")
    # Expected yield total = 8.0 * 3 = 24.00
    assert Decimal(str(calc["expected_yield_total"])) == Decimal("24.00")
    # Revenue = 24 * 5500 = 132000.00
    assert Decimal(str(calc["expected_gross_revenue"])) == Decimal("132000.00")
    # Profit = 132000 - 28000 = 104000.00
    assert Decimal(str(calc["expected_net_profit"])) == Decimal("104000.00")
    # Profit margin = (104000 / 132000) * 100 = 78.8%
    assert Decimal(str(calc["profit_margin_percentage"])) == Decimal("78.8")
    assert len(calc["breakdown"]) == 7


@pytest.mark.asyncio
async def test_farm_expense_tracker_and_filters():
    """Verify adding expenses and querying with filters and totals."""
    ts = int(datetime.now().timestamp() * 1000)
    farmer_email = f"farmer_exp_{ts}@krishiguide.org"

    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Farmer Expense Test",
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

    today = date.today()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create 3 expenses
        e1 = await client.post(
            "/api/farm/expenses",
            json={
                "category": "Seeds",
                "amount": 4000.00,
                "crop_name": "Groundnut",
                "description": "TMV-2 Certified Seeds",
                "expense_date": str(today - timedelta(days=2)),
            },
            headers=headers,
        )
        assert e1.status_code == 201

        e2 = await client.post(
            "/api/farm/expenses",
            json={
                "category": "Fertilizer",
                "amount": 3500.00,
                "crop_name": "Groundnut",
                "description": "Gypsum and SSP bags",
                "expense_date": str(today - timedelta(days=1)),
            },
            headers=headers,
        )
        assert e2.status_code == 201

        e3 = await client.post(
            "/api/farm/expenses",
            json={
                "category": "Labor",
                "amount": 2000.00,
                "crop_name": "Paddy",
                "description": "Transplanting labor",
                "expense_date": str(today),
            },
            headers=headers,
        )
        assert e3.status_code == 201
        e3_id = e3.json()["id"]

        # Query all expenses
        r_all = await client.get("/api/farm/expenses", headers=headers)
        assert r_all.status_code == 200
        all_data = r_all.json()
        assert all_data["total_count"] == 3
        assert Decimal(str(all_data["total_amount"])) == Decimal("9500.00")

        # Filter by crop
        r_crop = await client.get("/api/farm/expenses?crop_name=Groundnut", headers=headers)
        assert r_crop.status_code == 200
        crop_data = r_crop.json()
        assert crop_data["total_count"] == 2
        assert Decimal(str(crop_data["total_amount"])) == Decimal("7500.00")

        # Filter by category
        r_cat = await client.get("/api/farm/expenses?category=Fertilizer", headers=headers)
        assert r_cat.status_code == 200
        cat_data = r_cat.json()
        assert cat_data["total_count"] == 1
        assert Decimal(str(cat_data["total_amount"])) == Decimal("3500.00")

        # Delete expense 3
        r_del = await client.delete(f"/api/farm/expenses/{e3_id}", headers=headers)
        assert r_del.status_code == 200

        # Verify new count
        r_after = await client.get("/api/farm/expenses", headers=headers)
        assert r_after.json()["total_count"] == 2


@pytest.mark.asyncio
async def test_crop_task_scheduler_and_status_update():
    """Verify scheduling tasks, updating status, and filtering."""
    ts = int(datetime.now().timestamp() * 1000)
    farmer_email = f"farmer_task_{ts}@krishiguide.org"

    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Farmer Task Test",
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

    task_date = str(date.today() + timedelta(days=5))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create task
        r_create = await client.post(
            "/api/farm/tasks",
            json={
                "task_title": "Apply Gypsum at 45 DAS",
                "crop_name": "Groundnut",
                "description": "Broadcast 200 kg gypsum per acre at pegging stage",
                "scheduled_date": task_date,
                "priority": "high",
                "status": "pending",
                "notification_tag": "Fertilizer",
            },
            headers=headers,
        )
        assert r_create.status_code == 201
        task_data = r_create.json()
        task_id = task_data["id"]
        assert task_data["is_completed"] is False

        # Retrieve tasks
        r_list = await client.get("/api/farm/tasks", headers=headers)
        assert r_list.status_code == 200
        assert len(r_list.json()) >= 1

        # Mark completed via PATCH
        r_patch = await client.patch(
            f"/api/farm/tasks/{task_id}",
            json={"is_completed": True, "status": "completed"},
            headers=headers,
        )
        assert r_patch.status_code == 200
        assert r_patch.json()["is_completed"] is True

        # Filter completed tasks
        r_completed = await client.get("/api/farm/tasks?is_completed=true", headers=headers)
        assert r_completed.status_code == 200
        assert any(t["id"] == task_id for t in r_completed.json())


@pytest.mark.asyncio
async def test_farmer_isolation_on_farm_tools():
    """Verify farmers cannot delete or modify other farmers' expenses or tasks."""
    ts = int(datetime.now().timestamp() * 1000)
    f1_email = f"f1_tools_{ts}@krishiguide.org"
    f2_email = f"f2_tools_{ts}@krishiguide.org"

    async with AsyncSessionLocal() as session:
        f1 = User(full_name="F1 Tools", email=f1_email, hashed_password=hash_password("Pass123!"), role="farmer", account_status="active")
        f2 = User(full_name="F2 Tools", email=f2_email, hashed_password=hash_password("Pass123!"), role="farmer", account_status="active")
        session.add_all([f1, f2])
        await session.commit()
        await session.refresh(f1)
        await session.refresh(f2)
        f1_id, f2_id = f1.id, f2.id

    token1 = create_access_token(subject=f1_id, role="farmer")
    token2 = create_access_token(subject=f2_id, role="farmer")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Farmer 1 creates expense and task
        e1 = await client.post(
            "/api/farm/expenses",
            json={"category": "Seeds", "amount": 1000.00, "crop_name": "Paddy"},
            headers={"Authorization": f"Bearer {token1}"},
        )
        e1_id = e1.json()["id"]

        t1 = await client.post(
            "/api/farm/tasks",
            json={"task_title": "Private Task", "scheduled_date": str(date.today())},
            headers={"Authorization": f"Bearer {token1}"},
        )
        t1_id = t1.json()["id"]

        # Farmer 2 attempts to delete Farmer 1's expense -> 403 Forbidden
        r_del_exp = await client.delete(
            f"/api/farm/expenses/{e1_id}",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert r_del_exp.status_code == 403

        # Farmer 2 attempts to update Farmer 1's task -> 403 Forbidden
        r_patch_task = await client.patch(
            f"/api/farm/tasks/{t1_id}",
            json={"task_title": "Hacked Title"},
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert r_patch_task.status_code == 403

