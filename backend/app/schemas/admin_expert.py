from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, EmailStr, ConfigDict


# ---------------------------------------------------------
# Admin Schemas
# ---------------------------------------------------------
class AdminDashboardStats(BaseModel):
    # Users
    total_users: int
    farmers_count: int
    experts_count: int
    admins_count: int

    # Documents
    total_documents: int
    processed_documents_count: int
    pending_documents_count: int
    failed_documents_count: int

    # RAG / Conversations
    total_conversations: int
    total_messages: int
    reported_messages_count: int

    # Expert Cases
    total_cases: int
    pending_cases_count: int
    resolved_cases_count: int

    # Farm Management
    total_expenses_recorded: int
    total_expenses_amount: Decimal
    total_tasks_scheduled: int
    completed_tasks_count: int


class AdminUserItem(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone_number: Optional[str] = None
    role: str
    account_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedUsersResponse(BaseModel):
    total: int
    page: int
    size: int
    items: List[AdminUserItem]


class AdminUserUpdateRequest(BaseModel):
    role: Optional[str] = Field(None, description="New role: farmer, expert, admin")
    account_status: Optional[str] = Field(None, description="New status: active, suspended, inactive")


class FeedbackCreate(BaseModel):
    feedback_type: Optional[str] = Field("general", description="general, ai_accuracy, bug_report, feature_request")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Star rating 1 to 5")
    comments: Optional[str] = Field(None, max_length=2000)
    message_id: Optional[int] = None


class FeedbackItemResponse(BaseModel):
    id: int
    user_id: int
    user_name: str
    user_email: str
    message_id: Optional[int] = None
    feedback_type: str
    rating: Optional[int] = None
    comments: Optional[str] = None
    is_reviewed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedFeedbackResponse(BaseModel):
    total: int
    page: int
    size: int
    items: List[FeedbackItemResponse]


class AuditLogItemResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[Any] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedAuditLogsResponse(BaseModel):
    total: int
    page: int
    size: int
    items: List[AuditLogItemResponse]


# ---------------------------------------------------------
# Expert Schemas
# ---------------------------------------------------------
class ExpertCaseItemResponse(BaseModel):
    id: int
    farmer_id: int
    farmer_name: str
    farmer_email: str
    expert_id: Optional[int] = None
    expert_name: Optional[str] = None
    message_id: Optional[int] = None
    title: str
    farmer_question: str
    ai_response_snapshot: Optional[str] = None
    expert_response: Optional[str] = None
    status: str
    recommendations: Optional[Any] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedCasesResponse(BaseModel):
    total: int
    page: int
    size: int
    items: List[ExpertCaseItemResponse]


class ExpertCaseRespondRequest(BaseModel):
    expert_response: str = Field(..., min_length=5, max_length=5000, description="Agronomic guidance or correction")
    recommendations: Optional[Union[List[str], Dict[str, Any]]] = None
    mark_resolved: bool = Field(True, description="Whether to immediately mark the case as resolved")


class ExpertCaseStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Target status: pending, assigned, in_review, resolved, closed")

