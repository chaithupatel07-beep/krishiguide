from typing import Optional, Any
from sqlalchemy import Integer, String, Text, Boolean, ForeignKey, JSON, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class SavedAnswer(Base, TimestampMixin):
    __tablename__ = "saved_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    category: Mapped[str] = mapped_column(String(64), default="general", index=True)
    tags: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationship
    user = relationship("User")


class CropRecommendationHistory(Base, TimestampMixin):
    __tablename__ = "crop_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    soil_type: Mapped[str] = mapped_column(String(64), nullable=False)
    soil_ph: Mapped[Optional[float]] = mapped_column(Numeric(4, 2), nullable=True)
    rainfall: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    season: Mapped[str] = mapped_column(String(32), default="Kharif")
    nitrogen: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    phosphorus: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    potassium: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    recommendations: Mapped[Any] = mapped_column(JSON, nullable=False)


class AlertNotification(Base, TimestampMixin):
    __tablename__ = "alert_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # pest_risk, low_moisture, high_temp, advisory
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="warning", index=True)  # info, warning, danger
    field_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    meta_info: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
