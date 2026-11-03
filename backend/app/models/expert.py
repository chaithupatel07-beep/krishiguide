from typing import Optional, Any
from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class ExpertCase(Base, TimestampMixin):
    __tablename__ = "expert_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    farmer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expert_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    message_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    farmer_question: Mapped[str] = mapped_column(Text, nullable=False)
    ai_response_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expert_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True, nullable=False)  # pending, assigned, in_review, resolved, closed
    recommendations: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    farmer = relationship("User", foreign_keys=[farmer_id], back_populates="farmer_cases")
    expert = relationship("User", foreign_keys=[expert_id], back_populates="assigned_expert_cases")
    chat_message = relationship("ChatMessage")

