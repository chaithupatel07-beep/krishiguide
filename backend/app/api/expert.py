from typing import Optional, List, Any
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.connection import get_db
from app.models.user import User
from app.api.deps import require_expert, get_current_user
from app.core.security import verify_password, create_access_token
from app.schemas.auth import TokenResponse
from app.schemas.admin_expert import (
    ExpertLoginRequest,
    ExpertProfileResponse,
    ExpertProfileUpdateRequest,
    ExpertDashboardStats,
    PaginatedCasesResponse,
    ExpertCaseItemResponse,
    ExpertCaseDetailResponse,
    ExpertCaseRespondRequest,
    ExpertCaseStatusUpdateRequest,
    ExpertCaseFollowupRequest,
)
from app.services.admin_expert_service import ExpertService

router = APIRouter(prefix="/api/expert", tags=["Agricultural Expert Panel"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Dedicated Agricultural Expert Login",
    description="Authenticates approved agricultural specialist credentials.",
)
async def expert_login(
    payload: ExpertLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.email == payload.email)
    user = (await db.execute(stmt)).scalars().first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid expert credentials.",
        )

    if user.role not in ["expert", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted. Account does not have agricultural expert credentials.",
        )

    token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        full_name=user.full_name,
        email=user.email,
    )


@router.get(
    "/profile",
    response_model=ExpertProfileResponse,
    summary="Get Agricultural Expert Profile",
)
async def get_expert_profile(
    current_user: User = Depends(require_expert),
    db: AsyncSession = Depends(get_db),
):
    return await ExpertService.get_expert_profile(db, current_user)


@router.put(
    "/profile",
    response_model=ExpertProfileResponse,
    summary="Update Agricultural Expert Profile & Availability",
)
async def update_expert_profile(
    payload: ExpertProfileUpdateRequest,
    current_user: User = Depends(require_expert),
    db: AsyncSession = Depends(get_db),
):
    return await ExpertService.update_expert_profile(db, current_user, payload)


@router.get(
    "/dashboard",
    response_model=ExpertDashboardStats,
    summary="Get Expert Consultation Dashboard Metrics",
)
async def get_expert_dashboard(
    current_user: User = Depends(require_expert),
    db: AsyncSession = Depends(get_db),
):
    return await ExpertService.get_dashboard_stats(db, current_user)


@router.get(
    "/cases",
    response_model=PaginatedCasesResponse,
    summary="List Agricultural Cases & Farmer Inquiries",
)
async def list_cases(
    status: Optional[str] = Query(None, description="pending, assigned, in_progress, answered, closed"),
    search: Optional[str] = Query(None, description="Search by crop, question or topic"),
    priority: Optional[str] = Query(None, description="low, medium, high, urgent"),
    assigned_to_me: bool = Query(False, description="Filter only cases assigned to current expert"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_expert),
    db: AsyncSession = Depends(get_db),
):
    return await ExpertService.list_cases(
        db=db,
        user=current_user,
        status_filter=status,
        search=search,
        priority=priority,
        assigned_to_me=assigned_to_me,
        page=page,
        size=size,
    )


@router.get(
    "/cases/{case_id}",
    response_model=ExpertCaseDetailResponse,
    summary="Get Full Case Detail with Soil Context, RAG Sources, and Dialogue History",
)
async def get_case_detail(
    case_id: int,
    current_user: User = Depends(require_expert),
    db: AsyncSession = Depends(get_db),
):
    return await ExpertService.get_case_detail(db, current_user, case_id)


@router.post(
    "/cases/{case_id}/assign",
    summary="Claim or Assign Case to Current Expert",
)
async def assign_case(
    case_id: int,
    current_user: User = Depends(require_expert),
    db: AsyncSession = Depends(get_db),
):
    return await ExpertService.assign_self(db, current_user, case_id)


@router.put(
    "/cases/{case_id}/status",
    summary="Update Case Workflow Status",
)
async def update_status(
    case_id: int,
    payload: ExpertCaseStatusUpdateRequest,
    current_user: User = Depends(require_expert),
    db: AsyncSession = Depends(get_db),
):
    return await ExpertService.update_status(db, current_user, case_id, payload.status)


@router.post(
    "/cases/{case_id}/response",
    summary="Submit Verified Agronomic Guidance, Precautions & Dosages",
)
async def submit_response(
    case_id: int,
    payload: ExpertCaseRespondRequest,
    current_user: User = Depends(require_expert),
    db: AsyncSession = Depends(get_db),
):
    return await ExpertService.respond_to_case(db, current_user, case_id, payload)


@router.get(
    "/responses",
    summary="List Response History for Current Specialist",
)
async def list_responses(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_expert),
    db: AsyncSession = Depends(get_db),
):
    return await ExpertService.list_cases(
        db=db,
        user=current_user,
        status_filter="answered",
        assigned_to_me=True,
        page=page,
        size=size,
    )


@router.post(
    "/cases/{case_id}/follow-up",
    summary="Send Follow-up Advice in Active Consultation Thread",
)
async def add_followup(
    case_id: int,
    payload: ExpertCaseFollowupRequest,
    current_user: User = Depends(require_expert),
    db: AsyncSession = Depends(get_db),
):
    return await ExpertService.add_followup(db, current_user, case_id, payload.message)
