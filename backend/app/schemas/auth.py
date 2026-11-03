from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class UserRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255, description="Full name of the user")
    email: EmailStr = Field(..., description="Valid unique email address")
    password: str = Field(..., min_length=6, max_length=128, description="Password with minimum 6 characters")
    phone_number: Optional[str] = Field(None, max_length=32, description="Optional contact phone number")
    role: Optional[str] = Field("farmer", description="Default public role is farmer. Admins/Experts cannot self-register.")


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered user email")
    password: str = Field(..., min_length=1, description="Account password")


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    phone_number: Optional[str] = None
    role: str
    account_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # in seconds
    user: UserResponse


class ApiResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
