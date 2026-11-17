from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.models.user import User
from app.api.deps import get_current_user
from app.schemas.admin_expert import (
    NotificationItemResponse,
    NotificationPreferences,
)
from app.services.admin_expert_service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["In-App Notifications"])


@router.get(
    "",
    summary="List In-App Notifications for Current User",
)
async def list_notifications(
    unread_only: bool = Query(False, description="Filter unread notifications only"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await NotificationService.list_notifications(
        db=db,
        user_id=current_user.id,
        unread_only=unread_only,
        page=page,
        size=size,
    )


@router.patch(
    "/{notification_id}/read",
    summary="Mark Specific Notification as Read",
)
async def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    success = await NotificationService.mark_as_read(db, current_user.id, notification_id)
    return {"success": success, "id": notification_id}


@router.post(
    "/mark-all-read",
    summary="Mark All Notifications as Read",
)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await NotificationService.mark_all_as_read(db, current_user.id)
    return {"success": True, "marked_count": count}


@router.get(
    "/preferences",
    response_model=NotificationPreferences,
    summary="Get User Notification Preferences",
)
async def get_preferences(
    current_user: User = Depends(get_current_user),
):
    return NotificationPreferences()


@router.put(
    "/preferences",
    response_model=NotificationPreferences,
    summary="Update User Notification Preferences",
)
async def update_preferences(
    payload: NotificationPreferences,
    current_user: User = Depends(get_current_user),
):
    return payload
