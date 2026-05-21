# backend/app/api/routes/risks.py

from fastapi import (
    APIRouter, Depends, HTTPException,
    UploadFile, File, Form
)
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_tenant_db
from app.core.dependencies import (
    any_authenticated_user,
    auditor_or_admin,
    risk_manager_or_above
)
from app.core.enums import UserRole
from app.models.tenant_models import Risk, RiskEvidence, AuditLog
from app.schemas.risk_schemas import (
    RiskResponse, RiskDetailResponse, RiskEvidenceResponse,
    AssignRiskRequest, SubmitEvidenceRequest, RiskSummary,
    EditRiskRequest, AddDiscussionCommentRequest, CloseRiskRequest
)
from app.services.risk_service import (
    get_risks_for_user, assign_risk,
    submit_text_evidence, submit_file_evidence,
    close_risk, get_risk_summary,
    edit_risk, add_closure_comment
)
from app.core.dependencies import admin_only

router = APIRouter(prefix="/risks", tags=["Risk Management"])


@router.get("", response_model=List[RiskResponse])
def list_risks(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    current_user=Depends(any_authenticated_user)
):
    """
    List all risks.
    EMPLOYEE: sees only risks assigned to them.
    Everyone else: sees all risks.
    Optionally filter by status or severity.
    """
    tenant_db = get_tenant_db(current_user.tenant_db_url)
    risks = get_risks_for_user(
        tenant_db=tenant_db,
        user_id=str(current_user.id),
        user_role=current_user.role,
        status_filter=status,
        severity_filter=severity
    )
    return risks


@router.get("/summary", response_model=RiskSummary)
def get_risks_summary(
    current_user=Depends(any_authenticated_user)
):
    """
    Returns risk counts by status and severity.
    Used for the dashboard charts.
    """
    tenant_db = get_tenant_db(current_user.tenant_db_url)
    summary = get_risk_summary(
        tenant_db=tenant_db,
        user_id=str(current_user.id),
        user_role=current_user.role
    )
    return summary


@router.get("/{risk_id}", response_model=RiskDetailResponse)
def get_risk(
    risk_id: str,
    current_user=Depends(any_authenticated_user)
):
    """
    Get full risk details including all submitted evidence.
    EMPLOYEE: can only view risks assigned to them.
    """
    tenant_db = get_tenant_db(current_user.tenant_db_url)
    risk = tenant_db.query(Risk).filter_by(id=risk_id).first()

    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    # Employee can only see their assigned risks
    if (current_user.role == UserRole.EMPLOYEE and
            str(risk.assigned_to) != str(current_user.id)):
        raise HTTPException(status_code=403, detail="Access denied")

    # Load all evidence for this risk
    evidence_list = tenant_db.query(RiskEvidence).filter_by(
        risk_id=risk_id
    ).order_by(RiskEvidence.created_at.desc()).all()

    return RiskDetailResponse(
        id=risk.id,
        title=risk.title,
        severity=risk.severity,
        description=risk.description,
        suggested_fix=risk.suggested_fix,
        status=risk.status,
        country=risk.country,
        framework=risk.framework,
        assigned_to=risk.assigned_to,
        resolved_at=risk.resolved_at,
        closed_at=risk.closed_at,
        created_at=risk.created_at,
        updated_at=risk.updated_at,
        evidence=evidence_list
    )


@router.put("/{risk_id}/assign")
def assign_risk_to_user(
    risk_id: str,
    request: AssignRiskRequest,
    current_user=Depends(auditor_or_admin)
):
    """
    Auditor/Admin assigns a risk to a specific user.
    This is how Employees get tasks assigned to them.
    """
    tenant_db = get_tenant_db(current_user.tenant_db_url)

    # Verify the user being assigned exists
    from app.models.tenant_models import User
    assignee = tenant_db.query(User).filter_by(
        id=request.assigned_to
    ).first()
    if not assignee:
        raise HTTPException(
            status_code=404,
            detail="User to assign not found"
        )

    try:
        risk = assign_risk(
            tenant_db=tenant_db,
            risk_id=risk_id,
            assigned_to_user_id=str(request.assigned_to),
            actor_id=str(current_user.id)
        )
        return {
            "message": f"Risk assigned to {assignee.email}",
            "risk_id": str(risk.id),
            "assigned_to": str(risk.assigned_to),
            "status": risk.status
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{risk_id}/evidence/text",
             response_model=RiskEvidenceResponse)
def submit_text_evidence_route(
    risk_id: str,
    request: SubmitEvidenceRequest,
    current_user=Depends(risk_manager_or_above)
):
    """
    Submit text evidence for a risk.
    AI immediately verifies if it resolves the risk.
    If AI recommends CLOSE, risk status becomes RESOLVED.
    """
    tenant_db = get_tenant_db(current_user.tenant_db_url)

    # Check risk exists and user has access
    risk = tenant_db.query(Risk).filter_by(id=risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    if risk.status == "CLOSED":
        raise HTTPException(
            status_code=400,
            detail="Risk is already closed"
        )

    try:
        evidence = submit_text_evidence(
            tenant_db=tenant_db,
            risk_id=risk_id,
            evidence_text=request.evidence_text,
            submitted_by_id=str(current_user.id),
            framework=risk.framework
        )
        return evidence
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            raise HTTPException(
                status_code=429,
                detail="Gemini API rate limit. Please wait and retry."
            )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{risk_id}/evidence/file",
             response_model=RiskEvidenceResponse)
async def submit_file_evidence_route(
    risk_id: str,
    description: str = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(risk_manager_or_above)
):
    """
    Submit a file (PDF/image) as evidence for a risk.
    Include a text description explaining what the file shows.
    """
    tenant_db = get_tenant_db(current_user.tenant_db_url)

    risk = tenant_db.query(Risk).filter_by(id=risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    if risk.status == "CLOSED":
        raise HTTPException(
            status_code=400,
            detail="Risk is already closed"
        )

    allowed_types = [
        "application/pdf",
        "image/jpeg", "image/jpg",
        "image/png", "image/webp"
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and image files are supported"
        )

    file_bytes = await file.read()

    try:
        evidence = submit_file_evidence(
            tenant_db=tenant_db,
            risk_id=risk_id,
            file_bytes=file_bytes,
            file_name=file.filename,
            evidence_text=description,
            submitted_by_id=str(current_user.id),
            framework=risk.framework
        )
        return evidence
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            raise HTTPException(
                status_code=429,
                detail="Gemini API rate limit. Please wait and retry."
            )
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{risk_id}/edit")
def edit_risk_route(
    risk_id: str,
    request: EditRiskRequest,
    current_user=Depends(admin_only)
):
    """
    ADMIN ONLY.
    Edit risk fields before closing.
    Admin can update title, description, suggested fix,
    severity, and add admin notes.
    Returns updated risk with all current fields.
    """
    tenant_db = get_tenant_db(current_user.tenant_db_url)

    try:
        risk = edit_risk(
            tenant_db=tenant_db,
            risk_id=risk_id,
            edits=request.model_dump(exclude_none=True),
            actor_id=str(current_user.id)
        )
        # Load evidence too
        evidence_list = tenant_db.query(RiskEvidence).filter_by(
            risk_id=risk_id
        ).order_by(RiskEvidence.created_at.desc()).all()

        return RiskDetailResponse(
            id=risk.id,
            title=risk.title,
            severity=risk.severity,
            description=risk.description,
            suggested_fix=risk.suggested_fix,
            status=risk.status,
            country=risk.country,
            framework=risk.framework,
            assigned_to=risk.assigned_to,
            admin_notes=risk.admin_notes,
            auditor_comment=risk.auditor_comment,
            closure_discussion=risk.closure_discussion,
            resolved_at=risk.resolved_at,
            closed_at=risk.closed_at,
            created_at=risk.created_at,
            updated_at=risk.updated_at,
            evidence=evidence_list
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{risk_id}/discussion")
def add_discussion_comment(
    risk_id: str,
    request: AddDiscussionCommentRequest,
    current_user=Depends(auditor_or_admin)
):
    """
    Admin or Auditor adds a comment to the closure
    discussion thread.
    This is the discussion that happens before Admin
    formally closes the risk.

    Both Admin and Auditor can comment.
    Only Admin can close.
    """
    tenant_db = get_tenant_db(current_user.tenant_db_url)

    try:
        risk = add_closure_comment(
            tenant_db=tenant_db,
            risk_id=risk_id,
            comment=request.comment,
            actor_id=str(current_user.id),
            actor_role=current_user.role
        )
        return {
            "message": "Comment added to discussion",
            "risk_id": str(risk.id),
            "discussion": risk.closure_discussion
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{risk_id}/close")
def close_risk_route(
    risk_id: str,
    request: CloseRiskRequest,
    current_user=Depends(admin_only)
):
    """
    ADMIN ONLY — formally closes a risk.

    Before closing, Admin should:
    1. Review the risk detail (GET /{risk_id})
    2. Edit any fields if needed (PUT /{risk_id}/edit)
    3. Discuss with Auditor (POST /{risk_id}/discussion)
    4. Then close with a final closure note (this endpoint)

    Risk must be RESOLVED or IN_PROGRESS to be closed.
    """
    tenant_db = get_tenant_db(current_user.tenant_db_url)

    try:
        risk = close_risk(
            tenant_db=tenant_db,
            risk_id=risk_id,
            closed_by_id=str(current_user.id),
            closure_note=request.closure_note
        )
        return {
            "message": "Risk successfully closed",
            "risk_id": str(risk.id),
            "status": risk.status,
            "closed_at": risk.closed_at.isoformat(),
            "closure_note": request.closure_note,
            "full_discussion": risk.closure_discussion
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{risk_id}/audit-trail")
def get_audit_trail(
    risk_id: str,
    current_user=Depends(auditor_or_admin)
):
    """
    Returns the full action history for a risk.
    Shows who did what and when.
    """
    tenant_db = get_tenant_db(current_user.tenant_db_url)

    risk = tenant_db.query(Risk).filter_by(id=risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    logs = tenant_db.query(AuditLog).filter_by(
        entity_type="risk",
        entity_id=risk_id
    ).order_by(AuditLog.created_at.asc()).all()

    return {
        "risk_id": risk_id,
        "risk_title": risk.title,
        "current_status": risk.status,
        "audit_trail": [
            {
                "action": log.action,
                "actor_id": str(log.actor_id),
                "before": log.before_json,
                "after": log.after_json,
                "timestamp": log.created_at.isoformat()
            }
            for log in logs
        ]
    }