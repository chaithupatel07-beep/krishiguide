from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.models.user import User
from app.models.audit import AuditLog
from app.schemas.auth import UserRegisterRequest, UserLoginRequest, TokenResponse, UserResponse
from app.core.security import hash_password, verify_password, create_access_token
from app.core.config import settings
from app.core.logging import logger


class AuthService:
    @staticmethod
    async def register_user(
        db: AsyncSession,
        req: UserRegisterRequest,
        ip_address: Optional[str] = None,
    ) -> User:
        """Registers a new user. Public registration is strictly restricted to the 'farmer' role."""
        # Enforce role restriction: public registrations cannot create admin or expert accounts
        requested_role = (req.role or "farmer").strip().lower()
        if requested_role in ["admin", "expert"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Public registration as admin or expert is not permitted. Only authorized administrators can grant elevated roles.",
            )

        # Validate duplicate email
        normalized_email = req.email.strip().lower()
        existing = await db.execute(
            select(User).where(func.lower(User.email) == normalized_email)
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email address already exists.",
            )

        # Secure password hashing
        hashed_pwd = hash_password(req.password)

        # Create user record
        user = User(
            full_name=req.full_name.strip(),
            email=normalized_email,
            phone_number=req.phone_number.strip() if req.phone_number else None,
            hashed_password=hashed_pwd,
            role="farmer",
            account_status="active",
        )
        db.add(user)
        await db.flush()

        # Audit log registration
        audit = AuditLog(
            user_id=user.id,
            action="USER_REGISTER",
            resource_type="user",
            resource_id=str(user.id),
            details={"email": user.email, "role": user.role},
            ip_address=ip_address,
        )
        db.add(audit)
        await db.commit()
        await db.refresh(user)

        logger.info(f"Registered new farmer: {user.email} (ID: {user.id})")
        return user

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        req: UserLoginRequest,
        ip_address: Optional[str] = None,
    ) -> TokenResponse:
        """Validates credentials, verifies account activation, and returns a signed JWT access token."""
        normalized_email = req.email.strip().lower()
        result = await db.execute(
            select(User).where(func.lower(User.email) == normalized_email)
        )
        user = result.scalars().first()

        # Secure password verification
        if not user or not verify_password(req.password, user.hashed_password):
            logger.warning(f"Failed login attempt for: {normalized_email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Account status check
        if user.account_status != "active":
            logger.warning(f"Login blocked for non-active account: {normalized_email} (status: {user.account_status})")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account is {user.account_status}. Please contact support or an administrator.",
            )

        # Generate JWT token
        token = create_access_token(
            subject=user.id,
            role=user.role,
        )

        # Audit log login
        audit = AuditLog(
            user_id=user.id,
            action="USER_LOGIN",
            resource_type="auth",
            resource_id=str(user.id),
            details={"email": user.email, "role": user.role},
            ip_address=ip_address,
        )
        db.add(audit)
        await db.commit()

        logger.info(f"User logged in successfully: {user.email} (Role: {user.role})")
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        )
