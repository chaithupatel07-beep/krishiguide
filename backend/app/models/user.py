from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="farmer", index=True, nullable=False)  # admin, farmer, expert
    account_status: Mapped[str] = mapped_column(String(32), default="active", index=True, nullable=False)  # active, inactive, suspended

    # Relationships
    farm_profile = relationship("FarmProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="uploader", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    expenses = relationship("FarmExpense", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("CropTask", back_populates="user", cascade="all, delete-orphan")
    farmer_cases = relationship("ExpertCase", foreign_keys="[ExpertCase.farmer_id]", back_populates="farmer", cascade="all, delete-orphan")
    assigned_expert_cases = relationship("ExpertCase", foreign_keys="[ExpertCase.expert_id]", back_populates="expert")
    feedbacks = relationship("Feedback", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")

