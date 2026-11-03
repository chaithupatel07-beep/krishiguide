from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class DocumentChunkResponse(BaseModel):
    id: int
    chunk_index: int
    page_number: int
    chunk_text: str
    vector_reference: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    id: int
    document_name: str
    file_type: str
    file_size: Optional[int] = None
    uploaded_by: Optional[int] = None
    is_public: bool
    processing_status: str  # pending, processing, completed, failed
    processing_error: Optional[str] = None
    meta_info: Optional[Any] = None
    total_chunks: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentProcessResponse(BaseModel):
    document_id: int
    processing_status: str
    message: str
    total_chunks: Optional[int] = None

