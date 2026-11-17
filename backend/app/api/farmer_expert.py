from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.models.user import User
from app.api.deps import require_farmer_or_admin, get_current_user
from app.schemas.admin_expert import (
    FarmerExpertCaseCreateRequest,
    ExpertCaseDetailResponse,
    ExpertCaseFollowupRequest,
)
from app.services.admin_expert_service import FarmerExpertService, ExpertService

router = APIRouter(prefix="/api/farmer/expert-requests", tags=["Farmer Expert Assistance"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Farmer Submits Case to Agricultural Specialists",
    description="Escalates an AI response or direct farming problem to verified agronomic specialists with field and soil context.",
)
async def create_expert_request(
    payload: FarmerExpertCaseCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await FarmerExpertService.create_expert_request(db, current_user, payload)


@router.get(
    "",
    summary="List Farmer's Submitted Expert Inquiries",
)
async def list_farmer_requests(
    status: Optional[str] = Query(None, description="pending, assigned, in_progress, answered, closed"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await FarmerExpertService.list_farmer_requests(
        db=db,
        farmer_user=current_user,
        status_filter=status,
        page=page,
        size=size,
    )


@router.get(
    "/{case_id}",
    response_model=ExpertCaseDetailResponse,
    summary="Get Farmer Consultation Detail with Expert Recommendations",
)
async def get_farmer_request(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ExpertService.get_case_detail(db, current_user, case_id)


@router.post(
    "/{case_id}/follow-up",
    summary="Farmer Sends Clarification or Follow-up Question",
)
async def send_followup(
    case_id: int,
    payload: ExpertCaseFollowupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ExpertService.add_followup(db, current_user, case_id, payload.message)
