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
# Expert Profile & Auth Schemas
# ---------------------------------------------------------
class ExpertLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class ExpertProfileResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: EmailStr
    phone_number: Optional[str] = None
    qualification: str
    specialization: str
    experience: int
    state: str
    district: str
    areas_of_expertise: Optional[Any] = None
    profile_image: Optional[str] = None
    approval_status: str
    availability_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExpertProfileUpdateRequest(BaseModel):
    qualification: Optional[str] = None
    specialization: Optional[str] = None
    experience: Optional[int] = None
    state: Optional[str] = None
    district: Optional[str] = None
    areas_of_expertise: Optional[List[str]] = None
    availability_status: Optional[str] = Field(None, description="available, busy, unavailable")


class ExpertDashboardStats(BaseModel):
    total_assigned_cases: int
    pending_cases: int
    in_progress_cases: int
    resolved_cases: int
    total_responses_provided: int


# ---------------------------------------------------------
# Expert Case Schemas
# ---------------------------------------------------------
class ExpertResponseDetail(BaseModel):
    id: int
    case_id: int
    expert_id: int
    expert_name: Optional[str] = None
    response: str
    diagnosis: Optional[str] = None
    recommended_actions: Optional[Any] = None
    precautions: Optional[Any] = None
    additional_suggestions: Optional[str] = None
    supporting_references: Optional[Any] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExpertCaseFollowupDetail(BaseModel):
    id: int
    case_id: int
    sender_id: int
    sender_name: Optional[str] = None
    sender_role: Optional[str] = None
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExpertCaseHistoryDetail(BaseModel):
    id: int
    case_id: int
    previous_status: Optional[str] = None
    new_status: str
    changed_by: int
    changer_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExpertCaseItemResponse(BaseModel):
    id: int
    farmer_id: int
    farmer_name: str
    farmer_email: str
    farmer_location: Optional[str] = None
    expert_id: Optional[int] = None
    expert_name: Optional[str] = None
    message_id: Optional[int] = None
    conversation_id: Optional[int] = None
    crop_name: str
    category: str
    question: str
    priority: str
    status: str
    title: Optional[str] = None
    farmer_question: Optional[str] = None
    ai_response_snapshot: Optional[str] = None
    source_references: Optional[Any] = None
    expert_response: Optional[str] = None
    recommendations: Optional[Any] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExpertCaseDetailResponse(ExpertCaseItemResponse):
    farmer_phone: Optional[str] = None
    farmer_farm_size: Optional[str] = None
    farmer_soil_type: Optional[str] = None
    farmer_crops: Optional[Any] = None
    responses: List[ExpertResponseDetail] = []
    followups: List[ExpertCaseFollowupDetail] = []
    history: List[ExpertCaseHistoryDetail] = []


class PaginatedCasesResponse(BaseModel):
    total: int
    page: int
    size: int
    items: List[ExpertCaseItemResponse]


class ExpertCaseRespondRequest(BaseModel):
    expert_response: str = Field(..., min_length=5, max_length=5000, description="Agronomic guidance or correction")
    diagnosis: Optional[str] = Field(None, max_length=2000)
    recommended_actions: Optional[Union[List[str], str]] = None
    precautions: Optional[Union[List[str], str]] = None
    additional_suggestions: Optional[str] = None
    supporting_references: Optional[Union[List[str], str]] = None
    recommendations: Optional[Union[List[str], Dict[str, Any]]] = None
    mark_resolved: bool = Field(True, description="Whether to immediately mark the case as resolved/answered")
    status: Optional[str] = Field("answered", description="Status: answered, in_progress, resolved")


class ExpertCaseStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Target status: pending, assigned, in_progress, answered, closed, resolved")


class ExpertCaseFollowupRequest(BaseModel):
    message: str = Field(..., min_length=2, max_length=2000)


# ---------------------------------------------------------
# Farmer Assistance Schemas
# ---------------------------------------------------------
class FarmerExpertCaseCreateRequest(BaseModel):
    crop_name: str = Field("Paddy / Rice", max_length=128)
    category: str = Field("Pest & Disease", max_length=128)
    question: str = Field(..., min_length=5, max_length=5000)
    priority: Optional[str] = Field("medium", description="low, medium, high, urgent")
    conversation_id: Optional[int] = None
    message_id: Optional[int] = None
    ai_response_snapshot: Optional[str] = None
    source_references: Optional[List[str]] = None


# ---------------------------------------------------------
# Admin Expert Management Schemas
# ---------------------------------------------------------
class AdminExpertCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6)
    phone_number: Optional[str] = None
    qualification: str = Field(..., min_length=2, max_length=255)
    specialization: str = Field(..., min_length=2, max_length=128)
    experience: int = Field(5, ge=0, le=60)
    state: str = Field("Telangana", max_length=128)
    district: str = Field("Hyderabad", max_length=128)
    areas_of_expertise: Optional[List[str]] = None
    approval_status: str = Field("approved", description="approved, pending, rejected")


class AdminExpertUpdateRequest(BaseModel):
    qualification: Optional[str] = None
    specialization: Optional[str] = None
    experience: Optional[int] = None
    state: Optional[str] = None
    district: Optional[str] = None
    areas_of_expertise: Optional[List[str]] = None
    approval_status: Optional[str] = Field(None, description="pending, approved, rejected")
    availability_status: Optional[str] = Field(None, description="available, busy, unavailable")


class AdminCaseAssignRequest(BaseModel):
    expert_id: int


# ---------------------------------------------------------
# Notifications Schemas
# ---------------------------------------------------------
class NotificationItemResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: str
    is_read: bool
    link: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationPreferences(BaseModel):
    pest_alerts: bool = True
    weather_advisories: bool = True
    document_updates: bool = True
    expert_responses: bool = True
    scheme_alerts: bool = True
