from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class MessageSourceItem(BaseModel):
    document_id: Optional[int] = None
    document_name: str
    page_number: Optional[int] = None
    similarity_score: Optional[float] = None
    snippet: Optional[str] = None


class ChatQueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000, description="Farmer's agricultural query")
    conversation_id: Optional[int] = Field(None, description="Existing conversation ID for follow-up turns")
    language: Optional[str] = Field("English", description="Response language: English, Hindi, or Telugu")


class FrontendQueryRequest(BaseModel):
    """Payload schema expected by existing React frontend."""
    question: str = Field(..., min_length=2, max_length=2000)
    language: Optional[str] = "English"
    conversation_id: Optional[int] = None


class ChatMessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_role: str
    content: str
    language: str
    is_reported: bool
    meta_info: Optional[Dict[str, Any]] = None
    sources: List[MessageSourceItem] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(BaseModel):
    conversation_id: int
    message_id: int
    answer: str
    sources: List[MessageSourceItem]
    context_found: bool
    language: str
    created_at: datetime


class ConversationItemResponse(BaseModel):
    id: int
    title: str
    language: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationDetailResponse(BaseModel):
    id: int
    title: str
    language: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageResponse]


class PaginatedConversationsResponse(BaseModel):
    total: int
    page: int
    size: int
    items: List[ConversationItemResponse]


class ReportMessageRequest(BaseModel):
    reason: Optional[str] = Field("Inaccurate or unverified agricultural advice", max_length=500)


class ReportMessageResponse(BaseModel):
    message_id: int
    is_reported: bool
    case_id: Optional[int] = None
    detail: str


class FrontendQueryResponse(BaseModel):
    """Response schema expected by existing React frontend."""
    answer: str
    sources: List[Union[str, MessageSourceItem, Dict[str, Any]]]
    conversation_id: Optional[int] = None

