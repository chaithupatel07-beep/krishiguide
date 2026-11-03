from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.models.user import User
from app.api.deps import require_expert
from app.schemas.admin_expert import (
    ExpertCaseItemResponse,
    PaginatedCasesResponse,
    ExpertCaseRespondRequest,
    ExpertCaseStatusUpdateRequest,
)
from app.services.admin_expert_service import ExpertService

router = APIRouter(prefix="/api/expert", tags=["Agricultural Expert Panel"])


@router.get(
    "/cases",
    response_model=PaginatedCasesResponse,
    summary="Get agricultural cases and reported AI responses",
)
async def list_expert_cases(
    status: Optional[str] = Query(None, description="Filter by case status: pending, assigned, in_review, resolved, closed"),
    assigned_to_me: bool = Query(False, description="Filter cases specifically assigned to the logged-in expert"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_expert),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves agricultural consultation cases and escalated AI queries for expert verification.
    """
    return await ExpertService.list_cases(
        db=db,
        user=current_user,
        status_filter=status,
        assigned_to_me=assigned_to_me,
        page=page,
        size=size,
    )


@router.post(
    "/cases/{case_id}/respond",
    response_model=ExpertCaseItemResponse,
    summary="Provide verified agronomic recommendation and corrective advice",
)
async def respond_to_expert_case(
    case_id: int,
    payload: ExpertCaseRespondRequest,
    current_user: User = Depends(require_expert),
    db: AsyncSession = Depends(get_db),
):
    """
    Records an expert response, assigns case to expert if unassigned,
    and updates case status to resolved or in_review.
    """
    return await ExpertService.respond_to_case(
        db=db,
        expert_user=current_user,
        case_id=case_id,
        payload=payload,
    )


@router.patch(
    "/cases/{case_id}/status",
    response_model=ExpertCaseItemResponse,
    summary="Update case status (pending, assigned, in_review, resolved, closed)",
)
async def update_case_status(
    case_id: int,
    payload: ExpertCaseStatusUpdateRequest,
    current_user: User = Depends(require_expert),
    db: AsyncSession = Depends(get_db),
):
    """Updates status of an agricultural case."""
    return await ExpertService.update_status(
        db=db,
        expert_user=current_user,
        case_id=case_id,
        new_status=payload.status,
    )

