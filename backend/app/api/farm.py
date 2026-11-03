from typing import Optional, List
from datetime import date
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.models.user import User
from app.api.deps import get_current_user, require_farmer
from app.schemas.farm import (
    FarmProfileCreateUpdate,
    FarmProfileResponse,
    CostCalculationRequest,
    CostCalculationResponse,
    FarmExpenseCreate,
    FarmExpenseResponse,
    PaginatedExpensesResponse,
    CropTaskCreate,
    CropTaskUpdate,
    CropTaskResponse,
)
from app.services.farm_service import FarmService

router = APIRouter(prefix="/api/farm", tags=["Farmer Tools & Farm Management"])


# ---------------------------------------------------------
# 1. Farm Profile Management
# ---------------------------------------------------------
@router.get(
    "/profile",
    response_model=FarmProfileResponse,
    summary="Get authenticated farmer's profile",
)
async def get_farm_profile(
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves the authenticated farmer's soil, location, and crop profile."""
    return await FarmService.get_profile(db=db, user_id=current_user.id)


@router.put(
    "/profile",
    response_model=FarmProfileResponse,
    summary="Create or update farmer profile",
)
async def update_farm_profile(
    payload: FarmProfileCreateUpdate,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db),
):
    """Creates or updates the authenticated farmer's farm profile."""
    return await FarmService.create_or_update_profile(
        db=db,
        user_id=current_user.id,
        payload=payload,
    )


# ---------------------------------------------------------
# 2. Cultivation Cost Calculator
# ---------------------------------------------------------
@router.post(
    "/calculate-cost",
    response_model=CostCalculationResponse,
    summary="Calculate comprehensive crop cultivation cost and projected profit",
)
async def calculate_cultivation_cost(
    payload: CostCalculationRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Calculates detailed agricultural expenditure, per-acre cost breakdown,
    projected yield, and estimated profit margins using exact Decimal arithmetic.
    """
    return FarmService.calculate_cost(payload=payload)


# ---------------------------------------------------------
# 3. Farm Expense Tracker
# ---------------------------------------------------------
@router.get(
    "/expenses",
    response_model=PaginatedExpensesResponse,
    summary="Get farmer's expense records with category and crop filters",
)
async def get_farm_expenses(
    crop_name: Optional[str] = Query(None, description="Filter by crop name (e.g. Groundnut, Paddy)"),
    category: Optional[str] = Query(None, description="Filter by category (Seeds, Fertilizer, Labor, etc.)"),
    start_date: Optional[date] = Query(None, description="Filter expenses from this date"),
    end_date: Optional[date] = Query(None, description="Filter expenses until this date"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves paginated and filtered farm expenses with aggregated total amount."""
    return await FarmService.get_expenses(
        db=db,
        user_id=current_user.id,
        crop_name=crop_name,
        category=category,
        start_date=start_date,
        end_date=end_date,
        page=page,
        size=size,
    )


@router.post(
    "/expenses",
    response_model=FarmExpenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a new farm expense",
)
async def create_farm_expense(
    payload: FarmExpenseCreate,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db),
):
    """Records a new farm expenditure (seed, fertilizer, pesticide, labor, etc.)."""
    return await FarmService.create_expense(
        db=db,
        user_id=current_user.id,
        payload=payload,
    )


@router.delete(
    "/expenses/{expense_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a farm expense entry",
)
async def delete_farm_expense(
    expense_id: int,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db),
):
    """Deletes an expense entry owned by the authenticated farmer."""
    await FarmService.delete_expense(db=db, user_id=current_user.id, expense_id=expense_id)
    return {"detail": f"Expense #{expense_id} deleted successfully."}


# ---------------------------------------------------------
# 4. Crop Task Scheduler
# ---------------------------------------------------------
@router.get(
    "/tasks",
    response_model=List[CropTaskResponse],
    summary="Get scheduled farm and crop tasks",
)
async def get_crop_tasks(
    crop_name: Optional[str] = Query(None, description="Filter by crop name"),
    is_completed: Optional[bool] = Query(None, description="Filter by completion status"),
    start_date: Optional[date] = Query(None, description="Filter tasks from this date"),
    end_date: Optional[date] = Query(None, description="Filter tasks until this date"),
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves the farmer's scheduled crop activities and agronomic reminders."""
    return await FarmService.get_tasks(
        db=db,
        user_id=current_user.id,
        crop_name=crop_name,
        is_completed=is_completed,
        start_date=start_date,
        end_date=end_date,
    )


@router.post(
    "/tasks",
    response_model=CropTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule a new crop task or reminder",
)
async def create_crop_task(
    payload: CropTaskCreate,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db),
):
    """Schedules an agronomic activity (irrigation, fertilization, spraying, weeding)."""
    return await FarmService.create_task(
        db=db,
        user_id=current_user.id,
        payload=payload,
    )


@router.patch(
    "/tasks/{task_id}",
    response_model=CropTaskResponse,
    summary="Update task status or details",
)
async def update_crop_task(
    task_id: int,
    payload: CropTaskUpdate,
    current_user: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db),
):
    """Updates completion status, priority, or execution date for a task."""
    return await FarmService.update_task(
        db=db,
        user_id=current_user.id,
        task_id=task_id,
        payload=payload,
    )

