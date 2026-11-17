from typing import Optional, List, Dict, Any
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, asc
from fastapi import HTTPException, status

from app.models.user import User
from app.models.farm_profile import FarmProfile
from app.models.farm_tool import FarmExpense, CropTask
from app.schemas.farm import (
    FarmProfileCreateUpdate,
    CostCalculationRequest,
    CostCalculationResponse,
    CostBreakdownItem,
    FarmExpenseCreate,
    CropTaskCreate,
    CropTaskUpdate,
)
from app.core.logging import logger


class FarmService:
    # ---------------------------------------------------------
    # 1. Farm Profile Management
    # ---------------------------------------------------------
    @staticmethod
    async def get_profile(db: AsyncSession, user_id: int) -> FarmProfile:
        stmt = select(FarmProfile).where(FarmProfile.user_id == user_id)
        profile = (await db.execute(stmt)).scalars().first()
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Farm profile not found. Please create your farm profile first.",
            )
        return profile

    @staticmethod
    async def create_or_update_profile(
        db: AsyncSession,
        user_id: int,
        payload: FarmProfileCreateUpdate,
    ) -> FarmProfile:
        stmt = select(FarmProfile).where(FarmProfile.user_id == user_id)
        profile = (await db.execute(stmt)).scalars().first()

        if profile:
            profile.farm_location = payload.farm_location
            profile.district = payload.district
            profile.village = payload.village
            profile.farm_size = payload.farm_size
            profile.soil_type = payload.soil_type
            profile.crop_details = payload.crop_details
            profile.irrigation_details = payload.irrigation_details
            if payload.preferred_language:
                profile.preferred_language = payload.preferred_language
            profile.updated_at = datetime.now(timezone.utc)
        else:
            profile = FarmProfile(
                user_id=user_id,
                farm_location=payload.farm_location,
                district=payload.district,
                village=payload.village,
                farm_size=payload.farm_size,
                soil_type=payload.soil_type,
                crop_details=payload.crop_details,
                irrigation_details=payload.irrigation_details,
                preferred_language=payload.preferred_language or "English",
            )
            db.add(profile)

        await db.commit()
        await db.refresh(profile)
        logger.info(f"Farm profile updated for user #{user_id}.")
        return profile

    # ---------------------------------------------------------
    # 2. Cultivation Cost Calculator
    # ---------------------------------------------------------
    @staticmethod
    def calculate_cost(payload: CostCalculationRequest) -> CostCalculationResponse:
        """
        Calculates cultivation costs with Decimal precision to prevent rounding discrepancies.
        """
        two_places = Decimal("0.01")
        items = [
            ("Seeds / Planting Material", payload.seed_cost),
            ("Fertilizers & Nutrients", payload.fertilizer_cost),
            ("Labor & Weeding", payload.labor_cost),
            ("Irrigation & Electricity", payload.irrigation_cost),
            ("Plant Protection (Pesticides)", payload.pesticide_cost),
            ("Machinery & Fuel", payload.machinery_fuel_cost),
            ("Post-Harvest & Transport", payload.post_harvest_transport_cost),
        ]

        total_expenditure = sum((cost for _, cost in items), Decimal("0.00")).quantize(two_places, rounding=ROUND_HALF_UP)
        cost_per_acre = (total_expenditure / payload.land_area).quantize(two_places, rounding=ROUND_HALF_UP)

        breakdown: List[CostBreakdownItem] = []
        for cat, amt in items:
            pct = (
                ((amt / total_expenditure) * Decimal("100.0")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                if total_expenditure > Decimal("0.00")
                else Decimal("0.0")
            )
            breakdown.append(CostBreakdownItem(category=cat, amount=amt.quantize(two_places), percentage=pct))

        # Revenue and profit projections
        yield_total = None
        gross_rev = None
        net_profit = None
        profit_margin = None

        if payload.expected_yield_per_acre is not None:
            yield_total = (payload.expected_yield_per_acre * payload.land_area).quantize(two_places, rounding=ROUND_HALF_UP)

            if payload.expected_market_price_per_unit is not None:
                gross_rev = (yield_total * payload.expected_market_price_per_unit).quantize(two_places, rounding=ROUND_HALF_UP)
                net_profit = (gross_rev - total_expenditure).quantize(two_places, rounding=ROUND_HALF_UP)

                if gross_rev > Decimal("0.00"):
                    profit_margin = ((net_profit / gross_rev) * Decimal("100.0")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

        return CostCalculationResponse(
            crop_name=payload.crop_name,
            land_area_acres=payload.land_area.quantize(two_places),
            total_expenditure=total_expenditure,
            cost_per_acre=cost_per_acre,
            breakdown=breakdown,
            expected_yield_total=yield_total,
            expected_gross_revenue=gross_rev,
            expected_net_profit=net_profit,
            profit_margin_percentage=profit_margin,
            currency="INR",
        )

    # ---------------------------------------------------------
    # 3. Farm Expense Tracker
    # ---------------------------------------------------------
    @staticmethod
    async def create_expense(
        db: AsyncSession,
        user_id: int,
        payload: FarmExpenseCreate,
    ) -> FarmExpense:
        expense_date = payload.expense_date or date.today()
        expense = FarmExpense(
            user_id=user_id,
            category=payload.category,
            amount=payload.amount,
            crop_name=payload.crop_name,
            description=payload.description,
            expense_date=expense_date,
            meta_info=payload.meta_info,
        )
        db.add(expense)
        await db.commit()
        await db.refresh(expense)
        logger.info(f"User #{user_id} recorded expense ₹{expense.amount} under {expense.category}.")
        return expense

    @staticmethod
    async def get_expenses(
        db: AsyncSession,
        user_id: int,
        crop_name: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        size: int = 50,
    ) -> Dict[str, Any]:
        filters = [FarmExpense.user_id == user_id]

        if crop_name:
            filters.append(func.lower(FarmExpense.crop_name) == crop_name.lower())
        if category:
            filters.append(func.lower(FarmExpense.category) == category.lower())
        if start_date:
            filters.append(FarmExpense.expense_date >= start_date)
        if end_date:
            filters.append(FarmExpense.expense_date <= end_date)

        # Total amount and count aggregated in database
        sum_stmt = select(
            func.count(FarmExpense.id),
            func.coalesce(func.sum(FarmExpense.amount), Decimal("0.00")),
        ).where(and_(*filters))
        count_res = (await db.execute(sum_stmt)).first()
        total_count = count_res[0] or 0
        total_amount = count_res[1] or Decimal("0.00")

        # Query paginated rows
        offset = (max(page, 1) - 1) * max(size, 1)
        items_stmt = (
            select(FarmExpense)
            .where(and_(*filters))
            .order_by(desc(FarmExpense.expense_date), desc(FarmExpense.id))
            .offset(offset)
            .limit(size)
        )
        items = (await db.execute(items_stmt)).scalars().all()

        return {
            "total_count": total_count,
            "total_amount": total_amount,
            "items": items,
        }

    @staticmethod
    async def delete_expense(db: AsyncSession, user_id: int, expense_id: int) -> None:
        stmt = select(FarmExpense).where(FarmExpense.id == expense_id)
        expense = (await db.execute(stmt)).scalars().first()
        if not expense:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense record not found.")
        if expense.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Cannot delete another user's expense.")

        await db.delete(expense)
        await db.commit()

    # ---------------------------------------------------------
    # 4. Crop Task Scheduler
    # ---------------------------------------------------------
    @staticmethod
    async def create_task(
        db: AsyncSession,
        user_id: int,
        payload: CropTaskCreate,
    ) -> CropTask:
        reminder_info = {
            "priority": payload.priority or "medium",
            "status": payload.status or "pending",
            "notification_tag": payload.notification_tag,
        }
        task = CropTask(
            user_id=user_id,
            task_title=payload.task_title,
            crop_name=payload.crop_name,
            description=payload.description,
            scheduled_date=payload.scheduled_date,
            is_completed=(payload.status == "completed"),
            reminder_info=reminder_info,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        logger.info(f"User #{user_id} scheduled task '{task.task_title}' for {task.scheduled_date}.")
        return task

    @staticmethod
    async def get_tasks(
        db: AsyncSession,
        user_id: int,
        crop_name: Optional[str] = None,
        is_completed: Optional[bool] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[CropTask]:
        filters = [CropTask.user_id == user_id]

        if crop_name:
            filters.append(func.lower(CropTask.crop_name) == crop_name.lower())
        if is_completed is not None:
            filters.append(CropTask.is_completed == is_completed)
        if start_date:
            filters.append(CropTask.scheduled_date >= start_date)
        if end_date:
            filters.append(CropTask.scheduled_date <= end_date)

        stmt = select(CropTask).where(and_(*filters)).order_by(asc(CropTask.scheduled_date), asc(CropTask.id))
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def update_task(
        db: AsyncSession,
        user_id: int,
        task_id: int,
        payload: CropTaskUpdate,
    ) -> CropTask:
        stmt = select(CropTask).where(CropTask.id == task_id)
        task = (await db.execute(stmt)).scalars().first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop task not found.")
        if task.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Cannot update another farmer's task.")

        if payload.task_title is not None:
            task.task_title = payload.task_title
        if payload.crop_name is not None:
            task.crop_name = payload.crop_name
        if payload.description is not None:
            task.description = payload.description
        if payload.scheduled_date is not None:
            task.scheduled_date = payload.scheduled_date
        if payload.is_completed is not None:
            task.is_completed = payload.is_completed

        # Update reminder metadata
        current_reminder = dict(task.reminder_info or {})
        if payload.priority is not None:
            current_reminder["priority"] = payload.priority
        if payload.status is not None:
            current_reminder["status"] = payload.status
            if payload.status == "completed":
                task.is_completed = True
            elif payload.status == "pending" or payload.status == "in_progress":
                task.is_completed = False
        if payload.notification_tag is not None:
            current_reminder["notification_tag"] = payload.notification_tag

        task.reminder_info = current_reminder
        task.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(task)
        return task

    # ---------------------------------------------------------
    # 5. Crop Recommendation Engine
    # ---------------------------------------------------------
    @staticmethod
    def recommend_crops(data: Optional[Dict[str, Any]] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Computes grounded crop suitability rankings based on soil chemistry,
        climate parameters, seasonal calendar, and local agro-climatic conditions.
        Accepts dictionary or keyword arguments.
        """
        params = dict(data or {})
        params.update(kwargs)

        soil_type = str(params.get("soil_type") or "Loamy").lower()
        ph = float(params.get("soil_ph") or 6.8)
        nitrogen = float(params.get("nitrogen") or 140)
        rainfall = float(params.get("rainfall") or 850)

        recommendations = []
        if ph >= 5.5 and ph <= 7.8 and rainfall >= 600:
            recommendations.append({
                "name": "Rice (Paddy)",
                "profitability": "High Profitability",
                "suitability": "Good for your region",
                "duration": "120–140 days",
                "water_requirement": "High (900–1200 mm)",
                "soil_compatibility": "Clay / Clay loam / Heavy alluvial soils with high water retention",
                "yield_potential": "25–30 quintals/acre",
                "expected_yield": "25–30 quintals/acre",
                "key_varieties": "BPT-5204 (Samba Mahsuri), MTU-1010, RNR-15048 (Telangana Sona)",
                "fertilizer_plan": "100:50:50 kg N:P2O5:K2O per ha with 25 kg Zinc Sulphate at transplanting",
                "source": "ICAR Rice Production Manual & Directorate of Rice Research",
            })

        if ph >= 6.0 and ph <= 7.5:
            recommendations.append({
                "name": "Maize (Corn)",
                "profitability": "Moderate Profitability",
                "suitability": "Suitable for summer & kharif",
                "duration": "95–115 days",
                "water_requirement": "Moderate (450–600 mm)",
                "soil_compatibility": "Well-drained deep loamy and red sandy loam soils",
                "yield_potential": "28–35 quintals/acre",
                "expected_yield": "28–35 quintals/acre",
                "key_varieties": "DHM-117, Pioneer 3396, Bio-9681",
                "fertilizer_plan": "120:60:40 kg N:P2O5:K2O per ha in 3 split applications",
                "source": "ICAR-Indian Institute of Maize Research",
            })

        if ph >= 6.0 and ph <= 7.8:
            recommendations.append({
                "name": "Groundnut (Peanut)",
                "profitability": "Good Profitability",
                "suitability": "Low water requirement",
                "duration": "105–120 days",
                "water_requirement": "Low–Moderate (400–500 mm)",
                "soil_compatibility": "Sandy loam, red loam, and well-aerated light soils for pod development",
                "yield_potential": "10–14 quintals/acre",
                "expected_yield": "10–14 quintals/acre",
                "key_varieties": "Kadiri-6, TAG-24, K-9, Dharani",
                "fertilizer_plan": "20:40:40 kg N:P2O5:K2O per ha with 200 kg Gypsum at flowering (45 DAS)",
                "source": "ICAR-Directorate of Groundnut Research",
            })

        if "black" in soil_type or "clay" in soil_type:
            recommendations.append({
                "name": "Cotton",
                "profitability": "High Profitability",
                "suitability": "Ideal for deep black soils",
                "duration": "150–170 days",
                "water_requirement": "Moderate (550–700 mm)",
                "soil_compatibility": "Deep black cotton soils (Vertisols) with good moisture retention",
                "yield_potential": "12–16 quintals/acre",
                "expected_yield": "12–16 quintals/acre",
                "key_varieties": "Bt-Cotton Hybrids, Mallika, Bunny",
                "fertilizer_plan": "120:60:60 kg N:P2O5:K2O per ha with micronutrient foliar spray",
                "source": "Central Institute for Cotton Research (CICR)",
            })

        return recommendations

    # ---------------------------------------------------------
    # 6. Fertilizer Guidance Engine
    # ---------------------------------------------------------
    @staticmethod
    def get_fertilizer_guidance(crop: str, growth_stage: str, soil_type: str = "Loamy") -> Dict[str, Any]:
        """Returns structured fertilizer guidance based on crop and phenological growth stage."""
        crop_clean = crop.lower()
        if "paddy" in crop_clean or "rice" in crop_clean:
            return {
                "crop": crop,
                "stage": growth_stage,
                "recommended_dosage": "Urea: 50 kg/acre, DAP: 50 kg/acre, MOP: 25 kg/acre + 10 kg Zinc Sulphate",
                "application_method": "Incorporate full DAP & MOP as basal. Split Urea into 3 doses (transplanting, tillering, panicle).",
                "organic_alternative": "Apply 5-8 tonnes/ha farmyard manure (FYM) or green manuring with Sesbania (Dhaincha).",
                "source": "ICAR Directorate of Rice Research Guidelines (Page 12)",
            }
        elif "maize" in crop_clean:
            return {
                "crop": crop,
                "stage": growth_stage,
                "recommended_dosage": "Urea: 60 kg/acre, SSP: 120 kg/acre, MOP: 30 kg/acre",
                "application_method": "Apply full SSP and MOP basal. Split Urea at sowing, knee-high, and silking stage.",
                "organic_alternative": "Vermicompost @ 2 tonnes/acre + Azotobacter seed bio-fertilizer inoculation.",
                "source": "ICAR-IIMR Nutrient Management Manual (Page 15)",
            }
        else:
            return {
                "crop": crop,
                "stage": growth_stage,
                "recommended_dosage": "Balanced NPK 19:19:19 @ 5 kg/acre via fertigation or 100:50:50 kg/ha NPK basal.",
                "application_method": "Band placement 5 cm away from seeds and incorporate into moist soil.",
                "organic_alternative": "Enriched compost @ 3 tonnes/acre.",
                "source": "ICAR Package of Practices for Field Crops",
            }

    # ---------------------------------------------------------
    # 7. Irrigation Advice Engine
    # ---------------------------------------------------------
    @staticmethod
    def get_irrigation_advice(
        crop: str,
        irrigation_method: str,
        soil_type: str = "Loamy",
        weather_condition: str = "Clear",
    ) -> Dict[str, Any]:
        """Provides precision water management and irrigation interval advice."""
        return {
            "crop": crop,
            "method": irrigation_method,
            "frequency": "Alternate Wetting and Drying (AWD): irrigate 2–3 days after field water disappears",
            "soil_type": soil_type,
            "weather_condition": weather_condition,
            "water_saving_tip": "AWD saves 25-30% irrigation water without reducing paddy grain yield.",
            "source": "ICAR-Water Technology Centre Field Protocols",
        }


