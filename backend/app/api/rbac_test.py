from typing import Optional
from fastapi import APIRouter, Depends
from app.api.deps import (
    get_current_user,
    require_admin,
    require_expert,
    require_expert_strict,
    require_farmer,
    require_farmer_strict,
    verify_ownership,
    verify_expert_case_access,
)
from app.models.user import User

router = APIRouter(prefix="/rbac", tags=["Role-Based Access Control"])


@router.get("/admin-only")
async def test_admin_only(admin_user: User = Depends(require_admin)):
    return {
        "success": True,
        "message": "Admin authorization verified",
        "user_id": admin_user.id,
        "role": admin_user.role,
    }


@router.get("/expert-only")
async def test_expert_only(expert_user: User = Depends(require_expert_strict)):
    return {
        "success": True,
        "message": "Expert authorization verified",
        "user_id": expert_user.id,
        "role": expert_user.role,
    }


@router.get("/farmer-only")
async def test_farmer_only(farmer_user: User = Depends(require_farmer_strict)):
    return {
        "success": True,
        "message": "Farmer authorization verified",
        "user_id": farmer_user.id,
        "role": farmer_user.role,
    }


@router.get("/farmer-resource/{owner_id}")
async def test_farmer_ownership(
    owner_id: int,
    current_user: User = Depends(get_current_user),
):
    verify_ownership(owner_id, current_user)
    return {
        "success": True,
        "message": "Resource ownership verified",
        "owner_id": owner_id,
        "accessed_by": current_user.id,
        "role": current_user.role,
    }


@router.get("/expert-case/{farmer_id}/{expert_id}")
async def test_case_access(
    farmer_id: int,
    expert_id: int,
    current_user: User = Depends(get_current_user),
):
    verify_expert_case_access(farmer_id, expert_id, current_user)
    return {
        "success": True,
        "message": "Case access authorization verified",
        "farmer_id": farmer_id,
        "expert_id": expert_id,
        "accessed_by": current_user.id,
        "role": current_user.role,
    }

