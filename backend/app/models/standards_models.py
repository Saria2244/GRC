# backend/app/models/standards_models.py

import uuid
import datetime
from sqlalchemy import (
    Column, String, Integer, Text, Boolean,
    DateTime, BigInteger, LargeBinary, CHAR, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from app.core.database import StandardsBase


class StandardFileObject(StandardsBase):
    __tablename__ = "file_objects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(CHAR(64), unique=True, nullable=False)
    content = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class StandardsVersion(StandardsBase):
    __tablename__ = "standards_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country = Column(String, nullable=False)
    framework = Column(String, nullable=False)
    version = Column(String, nullable=False)
    title = Column(String, nullable=False)
    file_object_id = Column(UUID(as_uuid=True),
                            ForeignKey("file_objects.id"), nullable=True)
    sha256 = Column(CHAR(64), nullable=False)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class StandardChunk(StandardsBase):
    __tablename__ = "standard_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    standards_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("standards_versions.id"), nullable=False
    )
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    page_no = Column(Integer, nullable=True)
    # embedding = Column(Vector(3072), nullable=True)
    embedding = Column(Text, nullable=True)
    meta = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)