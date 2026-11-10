from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.models.user import User
from app.api.deps import get_current_user, require_admin
from app.schemas.admin_expert import (
    AdminDashboardStats,
    AdminUserItem,
    PaginatedUsersResponse,
    AdminUserUpdateRequest,
    FeedbackCreate,
    FeedbackItemResponse,
    PaginatedFeedbackResponse,
    PaginatedAuditLogsResponse,
)
from app.services.admin_expert_service import AdminService

router = APIRouter(tags=["Admin & Feedback"])


# ---------------------------------------------------------
# Admin Dashboard & System Operations
# ---------------------------------------------------------
@router.get(
    "/api/admin/dashboard",
    response_model=AdminDashboardStats,
    summary="Get aggregated live administrative system statistics",
)
async def get_admin_dashboard(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns real database aggregations: user roles, document processing status,
    conversations, reported responses, expert case resolution, and farm metrics.
    """
    return await AdminService.get_dashboard_stats(db=db)


@router.get(
    "/api/admin/users",
    response_model=PaginatedUsersResponse,
    summary="List all registered platform users with search and role filters",
)
async def list_admin_users(
    search: Optional[str] = Query(None, description="Search by name or email"),
    role: Optional[str] = Query(None, description="Filter by role: farmer, expert, admin"),
    status: Optional[str] = Query(None, description="Filter by status: active, suspended, inactive"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves paginated user directory for administrative auditing and management."""
    return await AdminService.list_users(
        db=db,
        search=search,
        role=role,
        status_filter=status,
        page=page,
        size=size,
    )


@router.patch(
    "/api/admin/users/{user_id}",
    response_model=AdminUserItem,
    summary="Update user role or activate/deactivate account",
)
async def update_user_status_or_role(
    user_id: int,
    payload: AdminUserUpdateRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Allows administrator to assign roles (farmer, expert, admin) or toggle account status.
    Protects against self-demotion or self-deactivation.
    """
    return await AdminService.update_user(
        db=db,
        admin_user=current_user,
        target_user_id=user_id,
        payload=payload,
    )


@router.get(
    "/api/admin/feedback",
    response_model=PaginatedFeedbackResponse,
    summary="Review farmer and user platform feedback",
)
async def get_admin_feedback(
    is_reviewed: Optional[bool] = Query(None),
    feedback_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves farmer feedback on advice accuracy, bug reports, and features."""
    return await AdminService.list_feedback(
        db=db,
        is_reviewed=is_reviewed,
        feedback_type=feedback_type,
        page=page,
        size=size,
    )


@router.get(
    "/api/admin/audit-logs",
    response_model=PaginatedAuditLogsResponse,
    summary="Audit trail for security and data modifications",
)
async def get_admin_audit_logs(
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves system activity audit logs."""
    return await AdminService.list_audit_logs(
        db=db,
        action=action,
        resource_type=resource_type,
        page=page,
        size=size,
    )


# ---------------------------------------------------------
# Public / Farmer Feedback Submission
# ---------------------------------------------------------
@router.post(
    "/api/feedback",
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback on AI advice or agricultural guidance",
)
async def submit_feedback(
    payload: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Allows authenticated farmers to submit ratings and feedback."""
    fb = await AdminService.create_feedback(db=db, user=current_user, payload=payload)
    return {"id": fb.id, "detail": "Thank you for your feedback! It helps improve AI Smart Farming Assistant."}

