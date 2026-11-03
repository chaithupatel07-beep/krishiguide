from typing import Optional
from sqlalchemy import Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True, index=True)
    feedback_type: Mapped[str] = mapped_column(String(50), default="general", index=True, nullable=False)  # general, ai_accuracy, bug_report, feature_request
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1 to 5
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="feedbacks")
    chat_message = relationship("ChatMessage")
