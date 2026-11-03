from typing import List, Optional, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.core.logging import logger

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    scheme_name="JWT Bearer",
    description="Provide access token in 'Authorization: Bearer <token>' format",
)

oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    scheme_name="JWT Bearer Optional",
    auto_error=False,
)


async def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Returns the authenticated active user if token is provided, or None if anonymous."""
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    user_id_str: Optional[str] = payload.get("sub")
    if not user_id_str:
        return None

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        return None

    user = await db.get(User, user_id)
    if not user or user.account_status != "active":
        return None

    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validates JWT access token and returns the authenticated active user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token has expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    user_id_str: Optional[str] = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception

    user = await db.get(User, user_id)
    if not user:
        raise credentials_exception

    if user.account_status != "active":
        logger.warning(f"Access denied for inactive user: {user.email} (status: {user.account_status})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user.account_status}. Access restricted.",
        )

    return user


class RoleChecker:
    """Dependency that enforces role-based access control (RBAC)."""

    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = [r.lower() for r in allowed_roles]

    async def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        user_role = (current_user.role or "").lower()
        if user_role not in self.allowed_roles:
            logger.warning(
                f"Unauthorized role access attempt: user {current_user.email} with role '{user_role}' "
                f"attempted to access endpoint requiring {self.allowed_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: role '{user_role}' does not have sufficient permissions.",
            )
        return current_user


# Role-specific dependencies
require_admin = RoleChecker(["admin"])
require_expert = RoleChecker(["expert", "admin"])
require_expert_strict = RoleChecker(["expert"])
require_farmer = RoleChecker(["farmer", "admin"])
require_farmer_strict = RoleChecker(["farmer"])


def verify_ownership(
    resource_user_id: int,
    current_user: User,
    allow_admin: bool = True,
) -> None:
    """Verifies that the current user owns the target resource or is an administrator."""
    if allow_admin and current_user.role == "admin":
        return

    if current_user.id != resource_user_id:
        logger.warning(
            f"Ownership violation: user {current_user.id} ({current_user.email}) attempted to access "
            f"resource owned by user {resource_user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not have permission to access or modify another user's record.",
        )


def verify_expert_case_access(
    case_farmer_id: int,
    case_expert_id: Optional[int],
    current_user: User,
) -> None:
    """Verifies access to expert cases based on role and assignment."""
    if current_user.role == "admin":
        return

    if current_user.role == "farmer":
        if current_user.id != case_farmer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: farmers may only access their own cases.",
            )
        return

    if current_user.role == "expert":
        # Experts can access cases assigned to them or unassigned pending cases in queue
        if case_expert_id is not None and case_expert_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: this case is assigned to another expert.",
            )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access forbidden: unauthorized role.",
    )
