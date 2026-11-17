from typing import Optional
from datetime import datetime
from sqlalchemy import Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(64), default="system", index=True, nullable=False)  # expert_assigned, expert_response, case_status, alert, document_ready
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    link: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    user = relationship("User", back_populates="notifications")
