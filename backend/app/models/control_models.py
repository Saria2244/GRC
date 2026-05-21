# backend/app/models/control_models.py

import uuid
import datetime
from sqlalchemy import (
    Column, String, Integer, Text, Boolean,
    DateTime, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import ControlBase


class Tenant(ControlBase):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    default_country = Column(String, default="PK")
    status = Column(String, default="PROVISIONING")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)


class TenantDatabase(ControlBase):
    __tablename__ = "tenant_databases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True),
                       ForeignKey("tenants.id"), unique=True, nullable=False)
    db_name = Column(String, unique=True, nullable=False)
    db_host = Column(String, default="localhost")
    db_port = Column(Integer, default=5432)
    db_user = Column(String, nullable=False)
    db_password_enc = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)


class Job(ControlBase):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True),
                       ForeignKey("tenants.id"), nullable=False)
    job_type = Column(String, nullable=False)
    status = Column(String, default="QUEUED")
    payload = Column(JSONB, default=dict)
    priority = Column(Integer, default=100)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    scheduled_at = Column(DateTime, default=datetime.datetime.utcnow)
    locked_at = Column(DateTime, nullable=True)
    locked_by = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)