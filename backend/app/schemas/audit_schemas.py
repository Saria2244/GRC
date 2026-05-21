# backend/app/schemas/audit_schemas.py

from pydantic import BaseModel, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.core.enums import AuditType


class CreateAuditRequest(BaseModel):
    title: str
    standards_version_id: str
    audit_type: AuditType       # ← user must pick a type

    @field_validator("audit_type")
    @classmethod
    def validate_audit_type(cls, v):
        if v not in AuditType.__members__.values():
            raise ValueError(f"Invalid audit type: {v}")
        return v


class AuditQuestionResponse(BaseModel):
    id: UUID
    question_index: int
    question_text: str
    question_type: str
    policy_reference: Optional[str]

    class Config:
        from_attributes = True


class AuditResponse(BaseModel):
    id: UUID
    title: str
    audit_type: str
    standards_version_id: UUID
    country: str
    framework: str
    status: str
    final_score: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditDetailResponse(AuditResponse):
    questions: List[AuditQuestionResponse] = []


class SubmitTextAnswerRequest(BaseModel):
    question_id: str
    answer_type: str            # TEXT / YES / NO
    answer_text: Optional[str] = None


class AuditAnswerResponse(BaseModel):
    id: UUID
    question_id: UUID
    answer_type: str
    answer_text: Optional[str]
    ai_score: Optional[float]
    ai_feedback: Optional[str]
    image_analysis: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class EvaluationResult(BaseModel):
    audit_id: str
    final_score: float
    status: str
    total_questions: int
    answered_questions: int
    risks_created: int
    summary: str


class AuditTypeOption(BaseModel):
    value: str
    label: str