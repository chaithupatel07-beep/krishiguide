from typing import Optional, Any
from decimal import Decimal
from sqlalchemy import Integer, String, Numeric, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class FarmProfile(Base, TimestampMixin):
    __tablename__ = "farm_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    farm_location: Mapped[str] = mapped_column(String(255), nullable=False)
    farm_size: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("1.00"))  # in acres
    soil_type: Mapped[str] = mapped_column(String(100), nullable=False)  # Black soil, Red sandy loam, Alluvial, Clay, etc.
    crop_details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # List or dict of active and planned crops
    irrigation_details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # Drip, sprinkler, borewell, canal, etc.

    # Relationships
    user = relationship("User", back_populates="farm_profile")

