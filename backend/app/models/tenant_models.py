# backend/app/models/tenant_models.py

import uuid
import datetime
from sqlalchemy import (
    Column, String, Integer, Text, Boolean,
    DateTime, BigInteger, LargeBinary, CHAR,
    Float, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import declarative_base
from app.core.enums import UserRole
from sqlalchemy import UniqueConstraint


# Tenant models use their OWN base — separate from control/standards
TenantBase = declarative_base()


class User(TenantBase):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default=UserRole.EMPLOYEE)
    # Stored as plain string in DB ("ADMIN", "AUDITOR" etc.)
    # but validated as enum everywhere else in the code
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

class FileObject(TenantBase):
    __tablename__ = "file_objects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(CHAR(64), nullable=False)
    content = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Document(TenantBase):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    doc_type = Column(String, default="POLICY")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class DocumentVersion(TenantBase):
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True),
                         ForeignKey("documents.id"), nullable=False)
    version_no = Column(Integer, nullable=False, default=1)
    file_object_id = Column(UUID(as_uuid=True),
                            ForeignKey("file_objects.id"), nullable=True)
    sha256 = Column(CHAR(64), nullable=False)
    status = Column(String, default="UPLOADED")
    # UPLOADED / TEXT_EXTRACTED / CHUNKED / EMBEDDED / READY / FAILED
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)


class DocChunk(TenantBase):
    __tablename__ = "doc_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_version_id = Column(UUID(as_uuid=True),
                            ForeignKey("document_versions.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    page_no = Column(Integer, nullable=True)
    # embedding = Column(Vector(3072), nullable=True)  # pgvector column
    embedding = Column(Text, nullable=True)
    meta = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Risk(TenantBase):
    __tablename__ = "risks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    suggested_fix = Column(Text, nullable=True)
    status = Column(String, default="OPEN")
    country = Column(String, nullable=False)
    framework = Column(String, nullable=False)
    policy_doc_version_id = Column(UUID(as_uuid=True), nullable=True)
    standards_version_id = Column(UUID(as_uuid=True), nullable=True)
    standard_chunk_id = Column(UUID(as_uuid=True), nullable=True)
    matched_policy_chunk_ids = Column(JSONB, default=list)
    best_similarity = Column(Float, nullable=True)
    assigned_to = Column(UUID(as_uuid=True),
                         ForeignKey("users.id"), nullable=True)

    # ── Closure fields ────────────────────────────────────
    admin_notes = Column(Text, nullable=True)
    # Admin's discussion/closure notes
    auditor_comment = Column(Text, nullable=True)
    # Auditor's review comment before closure
    closure_discussion = Column(JSONB, default=list)
    # Full discussion thread before closure
    # [{"user_id": "...", "role": "ADMIN", "comment": "...", "timestamp": "..."}]

    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    closed_by = Column(UUID(as_uuid=True),
                       ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)


class AuditLog(TenantBase):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    before_json = Column(JSONB, nullable=True)
    after_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Audit(TenantBase):
    __tablename__ = "audits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    standards_version_id = Column(UUID(as_uuid=True), nullable=False)
    audit_type = Column(String, nullable=False)
    # UUID from standards_db (no FK — different database)
    country = Column(String, nullable=False)
    framework = Column(String, nullable=False)
    status = Column(String, default="PENDING")
    # PENDING / IN_PROGRESS / COMPLETED
    final_score = Column(Float, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)


class AuditQuestion(TenantBase):
    __tablename__ = "audit_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id = Column(UUID(as_uuid=True),
                      ForeignKey("audits.id"), nullable=False)
    question_index = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String, default="OPEN_TEXT")
    # Always OPEN_TEXT now — no more YES_NO
    accepted_formats = Column(JSONB, default=list)
    # ["TEXT", "IMAGE", "BOTH"]
    standard_chunk_id = Column(UUID(as_uuid=True), nullable=True)
    policy_reference = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AuditAnswer(TenantBase):
    __tablename__ = "audit_answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id = Column(UUID(as_uuid=True),
                      ForeignKey("audits.id"), nullable=False)
    question_id = Column(UUID(as_uuid=True),
                         ForeignKey("audit_questions.id"), nullable=False)
    answer_type = Column(String, nullable=False)
    # TEXT / IMAGE / BOTH
    answer_text = Column(Text, nullable=True)
    image_bytes = Column(LargeBinary, nullable=True)
    image_mime_type = Column(String, nullable=True)
    image_analysis = Column(Text, nullable=True)
    ai_score = Column(Float, nullable=True)
    ai_feedback = Column(Text, nullable=True)
    answered_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)

class RiskEvidence(TenantBase):
    __tablename__ = "risk_evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    risk_id = Column(UUID(as_uuid=True),
                     ForeignKey("risks.id"), nullable=False)
    evidence_type = Column(String, nullable=False)
    # TEXT / IMAGE / PDF
    evidence_text = Column(Text, nullable=True)
    file_bytes = Column(LargeBinary, nullable=True)
    file_name = Column(String, nullable=True)
    ai_verified = Column(Boolean, default=False)
    ai_confidence = Column(Float, nullable=True)
    ai_reasoning = Column(Text, nullable=True)
    ai_recommendation = Column(String, nullable=True)
    # CLOSE / NEEDS_MORE_EVIDENCE / REJECT
    submitted_by = Column(UUID(as_uuid=True),
                          ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)