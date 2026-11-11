from typing import Optional, List, Any
import json
from sqlalchemy import Integer, String, Text, BigInteger, Boolean, ForeignKey, JSON
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class VectorType(TypeDecorator):
    """
    Platform-independent vector type.
    Uses PostgreSQL's pgvector Vector(dim) when on postgresql dialect,
    and falls back to JSON on SQLite/MySQL engines.
    """
    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 384, *args, **kwargs):
        self.dim = dim
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector
                return dialect.type_descriptor(Vector(self.dim))
            except Exception:
                return dialect.type_descriptor(JSON())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        if isinstance(value, list):
            return value
        return list(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return list(value)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    document_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(64), default="application/pdf", nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # in bytes
    uploaded_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    processing_status: Mapped[str] = mapped_column(String(32), default="pending", index=True, nullable=False)  # pending, processing, completed, failed
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta_info: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationships
    uploader = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base, TimestampMixin):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    meta_info: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    vector_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)  # UUID or vector ID
    embedding: Mapped[Optional[Any]] = mapped_column(VectorType(384), nullable=True)

    # Relationships
    document = relationship("Document", back_populates="chunks")
