from typing import Optional, List, Any
from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class AgriculturalExpert(Base, TimestampMixin):
    __tablename__ = "agricultural_experts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    qualification: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g., Ph.D. Agronomy, M.Sc. Plant Pathology
    specialization: Mapped[str] = mapped_column(String(128), nullable=False, index=True)  # Agronomy, Soil Science, Plant Pathology, etc.
    experience: Mapped[int] = mapped_column(Integer, default=5, nullable=False)  # Years of experience
    state: Mapped[str] = mapped_column(String(128), default="Telangana", nullable=False)
    district: Mapped[str] = mapped_column(String(128), default="Hyderabad", nullable=False)
    areas_of_expertise: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # List of crops/topics
    profile_image: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    approval_status: Mapped[str] = mapped_column(String(32), default="pending", index=True, nullable=False)  # pending, approved, rejected
    availability_status: Mapped[str] = mapped_column(String(32), default="available", index=True, nullable=False)  # available, busy, unavailable

    # Relationships
    user = relationship("User", back_populates="expert_profile")


class ExpertCase(Base, TimestampMixin):
    __tablename__ = "expert_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    farmer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expert_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    message_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True)

    crop_name: Mapped[str] = mapped_column(String(128), default="General / Mixed", nullable=False)
    category: Mapped[str] = mapped_column(String(128), default="Pest & Disease", nullable=False)  # Crop Health, Fertilizer, Irrigation, Pest, Scheme
    question: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(32), default="medium", index=True, nullable=False)  # low, medium, high, urgent
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True, nullable=False)  # pending, assigned, in_progress, answered, closed

    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    farmer_question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_response_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_references: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    expert_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendations: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    farmer = relationship("User", foreign_keys=[farmer_id], back_populates="farmer_cases")
    expert = relationship("User", foreign_keys=[expert_id], back_populates="assigned_expert_cases")
    conversation = relationship("Conversation")
    chat_message = relationship("ChatMessage")
    responses = relationship("ExpertResponse", back_populates="case", cascade="all, delete-orphan", order_by="ExpertResponse.created_at.desc()")
    followups = relationship("ExpertCaseFollowup", back_populates="case", cascade="all, delete-orphan", order_by="ExpertCaseFollowup.created_at.asc()")
    history = relationship("ExpertCaseHistory", back_populates="case", cascade="all, delete-orphan", order_by="ExpertCaseHistory.created_at.desc()")


class ExpertResponse(Base, TimestampMixin):
    __tablename__ = "expert_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("expert_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    expert_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    response: Mapped[str] = mapped_column(Text, nullable=False)
    diagnosis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_actions: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # List or text of actions
    precautions: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # List or text of precautions
    additional_suggestions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supporting_references: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # List of citations

    # Relationships
    case = relationship("ExpertCase", back_populates="responses")
    expert = relationship("User")


class ExpertCaseFollowup(Base, TimestampMixin):
    __tablename__ = "expert_case_followups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("expert_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    case = relationship("ExpertCase", back_populates="followups")
    sender = relationship("User")


class ExpertCaseHistory(Base, TimestampMixin):
    __tablename__ = "expert_case_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("expert_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    changed_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    case = relationship("ExpertCase", back_populates="history")
    changer = relationship("User")
