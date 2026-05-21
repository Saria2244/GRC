# backend/app/schemas/standards_schemas.py

from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class StandardsVersionResponse(BaseModel):
    id: UUID
    country: str
    framework: str
    version: str
    title: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class StandardsVersionDetail(StandardsVersionResponse):
    total_chunks: Optional[int] = 0
    file_name: Optional[str] = None
    size_bytes: Optional[int] = None


class StandardChunkResponse(BaseModel):
    id: UUID
    chunk_index: int
    chunk_text: str
    page_no: Optional[int]

    class Config:
        from_attributes = True


class ActivateStandardRequest(BaseModel):
    is_active: bool