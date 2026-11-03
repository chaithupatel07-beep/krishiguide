from typing import Optional, Any
from decimal import Decimal
from datetime import date
from sqlalchemy import Integer, String, Text, Numeric, Date, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class FarmExpense(Base, TimestampMixin):
    __tablename__ = "farm_expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # Seeds, Fertilizer, Pesticides, Labor, Irrigation, Equipment, Transport, Other
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    crop_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    meta_info: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationships
    user = relationship("User", back_populates="expenses")


class CropTask(Base, TimestampMixin):
    __tablename__ = "crop_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_title: Mapped[str] = mapped_column(String(255), nullable=False)
    crop_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    reminder_info: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationships
    user = relationship("User", back_populates="tasks")
