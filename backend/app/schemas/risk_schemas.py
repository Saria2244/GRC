# backend/app/schemas/risk_schemas.py

from pydantic import BaseModel
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from app.core.enums import RiskSeverity, RiskStatus


class RiskResponse(BaseModel):
    id: UUID
    title: str
    severity: RiskSeverity
    description: str
    suggested_fix: Optional[str]
    status: RiskStatus
    country: str
    framework: str
    assigned_to: Optional[UUID]
    admin_notes: Optional[str]
    auditor_comment: Optional[str]
    closure_discussion: Optional[List[Any]] = []
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RiskDetailResponse(RiskResponse):
    evidence: List["RiskEvidenceResponse"] = []


class RiskEvidenceResponse(BaseModel):
    id: UUID
    risk_id: UUID
    evidence_type: str
    evidence_text: Optional[str]
    file_name: Optional[str]
    ai_verified: bool
    ai_confidence: Optional[float]
    ai_reasoning: Optional[str]
    ai_recommendation: Optional[str]
    submitted_by: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True


class AssignRiskRequest(BaseModel):
    assigned_to: UUID


class SubmitEvidenceRequest(BaseModel):
    evidence_text: str


class RiskSummary(BaseModel):
    total: int
    open: int
    in_progress: int
    resolved: int
    closed: int
    critical: int
    high: int
    medium: int
    low: int


# ── Edit + Closure schemas ─────────────────────────────────

class EditRiskRequest(BaseModel):
    """
    Admin editable fields before closure.
    All fields are optional — only send what you want to change.
    """
    title: Optional[str] = None
    description: Optional[str] = None
    suggested_fix: Optional[str] = None
    severity: Optional[RiskSeverity] = None
    admin_notes: Optional[str] = None


class AddDiscussionCommentRequest(BaseModel):
    """
    Either Admin or Auditor adds a comment to the
    closure discussion thread.
    """
    comment: str


class CloseRiskRequest(BaseModel):
    """
    Admin submits this to formally close the risk.
    Must include a final closure note.
    """
    closure_note: str
    # Final admin note explaining the closure decision


RiskDetailResponse.model_rebuild()