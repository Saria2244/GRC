# backend/app/services/risk_service.py
from sqlalchemy.orm import Session
from app.models.tenant_models import Risk, RiskEvidence, AuditLog
from app.services.audit_ai_service import verify_evidence
import datetime as dt


def get_risks_for_user(
    tenant_db: Session,
    user_id: str,
    user_role: str,
    status_filter: str = None,
    severity_filter: str = None
) -> list:
    """
    Returns risks filtered by role.
    EMPLOYEE: only sees risks assigned to them.
    Everyone else: sees all risks.
    """
    query = tenant_db.query(Risk)

    # EMPLOYEE data scope — self only
    if user_role == "EMPLOYEE":
        query = query.filter(Risk.assigned_to == user_id)

    if status_filter:
        query = query.filter(Risk.status == status_filter)

    if severity_filter:
        query = query.filter(Risk.severity == severity_filter)

    return query.order_by(Risk.created_at.desc()).all()

def assign_risk(
    tenant_db: Session,
    risk_id: str,
    assigned_to_user_id: str,
    actor_id: str
) -> Risk:
    """Assign a risk to a specific user."""
    risk = tenant_db.query(Risk).filter_by(id=risk_id).first()
    if not risk:
        raise ValueError("Risk not found")

    old_assigned = str(risk.assigned_to) if risk.assigned_to else None
    risk.assigned_to = assigned_to_user_id
    risk.status = "IN_PROGRESS"

    # Log the action
    log = AuditLog(
        actor_id=actor_id,
        action="ASSIGN_RISK",
        entity_type="risk",
        entity_id=risk.id,
        before_json={"assigned_to": old_assigned},
        after_json={"assigned_to": str(assigned_to_user_id)}
    )
    tenant_db.add(log)
    tenant_db.commit()
    return risk

def submit_text_evidence(
    tenant_db: Session,
    risk_id: str,
    evidence_text: str,
    submitted_by_id: str,
    framework: str
) -> RiskEvidence:
    """
    Submit text evidence for a risk.
    AI immediately verifies if the evidence resolves the risk.
    """
    risk = tenant_db.query(Risk).filter_by(id=risk_id).first()
    if not risk:
        raise ValueError("Risk not found")

    if risk.status == "CLOSED":
        raise ValueError("Risk is already closed")

    # AI verifies the evidence
    print(f"Verifying evidence for risk: {risk.title}")
    try:
        verification = verify_evidence(
            risk_title=risk.title,
            risk_description=risk.description,
            suggested_fix=risk.suggested_fix or "",
            evidence_text=evidence_text,
            framework=framework
        )
        ai_verified = verification.get("verified", False)
        ai_confidence = verification.get("confidence", 0.0)
        ai_reasoning = verification.get("reasoning", "")
        ai_recommendation = verification.get("recommendation", "NEEDS_MORE_EVIDENCE")

    except Exception as e:
        print(f"Evidence verification failed: {e}")
        ai_verified = False
        ai_confidence = 0.0
        ai_reasoning = f"AI verification failed: {str(e)}"
        ai_recommendation = "NEEDS_MORE_EVIDENCE"

    # Store evidence record
    evidence = RiskEvidence(
        risk_id=risk_id,
        evidence_type="TEXT",
        evidence_text=evidence_text,
        ai_verified=ai_verified,
        ai_confidence=ai_confidence,
        ai_reasoning=ai_reasoning,
        ai_recommendation=ai_recommendation,
        submitted_by=submitted_by_id
    )
    tenant_db.add(evidence)

    # Auto-update risk status based on AI recommendation
    if ai_recommendation == "CLOSE":
        risk.status = "RESOLVED"
        risk.resolved_at = datetime.datetime.utcnow()
        print(f"  Risk auto-resolved by AI verification")
    elif ai_recommendation == "NEEDS_MORE_EVIDENCE":
        risk.status = "IN_PROGRESS"

    # Log the action
    log = AuditLog(
        actor_id=submitted_by_id,
        action="SUBMIT_EVIDENCE",
        entity_type="risk",
        entity_id=risk.id,
        before_json={"status": risk.status},
        after_json={
            "status": risk.status,
            "ai_recommendation": ai_recommendation
        }
    )
    tenant_db.add(log)
    tenant_db.commit()
    tenant_db.refresh(evidence)
    return evidence

def submit_file_evidence(
    tenant_db: Session,
    risk_id: str,
    file_bytes: bytes,
    file_name: str,
    evidence_text: str,
    submitted_by_id: str,
    framework: str
) -> RiskEvidence:
    """
    Submit file evidence (PDF/image) for a risk.
    Uses the text description for AI verification.
    """
    risk = tenant_db.query(Risk).filter_by(id=risk_id).first()
    if not risk:
        raise ValueError("Risk not found")

    if risk.status == "CLOSED":
        raise ValueError("Risk is already closed")

    # Use the text description for AI verification
    # (file content verification added later)
    combined_evidence = (
        f"File submitted: {file_name}\n"
        f"Description: {evidence_text}"
    )

    try:
        verification = verify_evidence(
            risk_title=risk.title,
            risk_description=risk.description,
            suggested_fix=risk.suggested_fix or "",
            evidence_text=combined_evidence,
            framework=framework
        )
        ai_verified = verification.get("verified", False)
        ai_confidence = verification.get("confidence", 0.0)
        ai_reasoning = verification.get("reasoning", "")
        ai_recommendation = verification.get("recommendation",
                                             "NEEDS_MORE_EVIDENCE")
    except Exception as e:
        print(f"Evidence verification failed: {e}")
        ai_verified = False
        ai_confidence = 0.0
        ai_reasoning = f"AI verification failed: {str(e)}"
        ai_recommendation = "NEEDS_MORE_EVIDENCE"

    evidence = RiskEvidence(
        risk_id=risk_id,
        evidence_type="FILE",
        evidence_text=evidence_text,
        file_bytes=file_bytes,
        file_name=file_name,
        ai_verified=ai_verified,
        ai_confidence=ai_confidence,
        ai_reasoning=ai_reasoning,
        ai_recommendation=ai_recommendation,
        submitted_by=submitted_by_id
    )
    tenant_db.add(evidence)

    if ai_recommendation == "CLOSE":
        risk.status = "RESOLVED"
        risk.resolved_at = datetime.datetime.utcnow()

    log = AuditLog(
        actor_id=submitted_by_id,
        action="SUBMIT_FILE_EVIDENCE",
        entity_type="risk",
        entity_id=risk.id,
        before_json={"status": "OPEN"},
        after_json={
            "status": risk.status,
            "file": file_name,
            "ai_recommendation": ai_recommendation
        }
    )
    tenant_db.add(log)
    tenant_db.commit()
    tenant_db.refresh(evidence)
    return evidence

def get_risk_summary(tenant_db: Session, user_id: str,
                     user_role: str) -> dict:
    """
    Returns risk counts for the dashboard.
    Respects role-based data scope.
    """
    query = tenant_db.query(Risk)
    if user_role == "EMPLOYEE":
        query = query.filter(Risk.assigned_to == user_id)

    all_risks = query.all()

    return {
        "total": len(all_risks),
        "open": sum(1 for r in all_risks if r.status == "OPEN"),
        "in_progress": sum(
            1 for r in all_risks if r.status == "IN_PROGRESS"
        ),
        "resolved": sum(
            1 for r in all_risks if r.status == "RESOLVED"
        ),
        "closed": sum(
            1 for r in all_risks if r.status == "CLOSED"
        ),
        "critical": sum(
            1 for r in all_risks if r.severity == "CRITICAL"
        ),
        "high": sum(
            1 for r in all_risks if r.severity == "HIGH"
        ),
        "medium": sum(
            1 for r in all_risks if r.severity == "MEDIUM"
        ),
        "low": sum(
            1 for r in all_risks if r.severity == "LOW"
        ),
    }

def edit_risk(
    tenant_db: Session,
    risk_id: str,
    edits: dict,
    actor_id: str
) -> Risk:
    """
    Admin edits risk fields before closing.
    All fields optional — only updates what is provided.
    """
    risk = tenant_db.query(Risk).filter_by(id=risk_id).first()
    if not risk:
        raise ValueError("Risk not found")

    if risk.status == "CLOSED":
        raise ValueError("Cannot edit a closed risk")

    # Track what changed for audit log
    before = {}
    after = {}

    allowed_fields = [
        "title", "description",
        "suggested_fix", "severity", "admin_notes"
    ]

    for field in allowed_fields:
        if field in edits and edits[field] is not None:
            before[field] = getattr(risk, field)
            setattr(risk, field, edits[field])
            after[field] = edits[field]

    if after:
        log = AuditLog(
            actor_id=actor_id,
            action="EDIT_RISK",
            entity_type="risk",
            entity_id=risk.id,
            before_json=before,
            after_json=after
        )
        tenant_db.add(log)

    tenant_db.commit()
    return risk

def add_closure_comment(
    tenant_db: Session,
    risk_id: str,
    comment: str,
    actor_id: str,
    actor_role: str
) -> Risk:
    """
    Admin or Auditor adds a comment to the closure
    discussion thread. This is the discussion before
    Admin formally closes the risk.
    """
    risk = tenant_db.query(Risk).filter_by(id=risk_id).first()
    if not risk:
        raise ValueError("Risk not found")

    if risk.status == "CLOSED":
        raise ValueError("Cannot comment on a closed risk")

    # Build discussion thread entry
    new_comment = {
        "user_id": str(actor_id),
        "role": actor_role,
        "comment": comment,
        "timestamp": dt.datetime.utcnow().isoformat()
    }

    # Append to existing discussion
    current_discussion = risk.closure_discussion or []
    current_discussion.append(new_comment)
    risk.closure_discussion = current_discussion

    # If Auditor adds comment, store as auditor_comment too
    if actor_role == "AUDITOR":
        risk.auditor_comment = comment

    log = AuditLog(
        actor_id=actor_id,
        action="ADD_CLOSURE_COMMENT",
        entity_type="risk",
        entity_id=risk.id,
        before_json=None,
        after_json={"comment": comment, "role": actor_role}
    )
    tenant_db.add(log)
    tenant_db.commit()
    return risk

def close_risk(
    tenant_db: Session,
    risk_id: str,
    closed_by_id: str,
    closure_note: str
) -> Risk:
    """
    ADMIN ONLY — formally closes a risk.
    Risk must be RESOLVED or IN_PROGRESS.
    Admin provides a final closure note.
    """
    risk = tenant_db.query(Risk).filter_by(id=risk_id).first()
    if not risk:
        raise ValueError("Risk not found")

    if risk.status == "CLOSED":
        raise ValueError("Risk is already closed")

    if risk.status not in ["RESOLVED", "IN_PROGRESS"]:
        raise ValueError(
            f"Risk must be RESOLVED or IN_PROGRESS to close. "
            f"Current status: {risk.status}"
        )

    # Add final closure note to discussion thread
    final_comment = {
        "user_id": str(closed_by_id),
        "role": "ADMIN",
        "comment": f"CLOSURE NOTE: {closure_note}",
        "timestamp": dt.datetime.utcnow().isoformat()
    }
    current_discussion = risk.closure_discussion or []
    current_discussion.append(final_comment)
    risk.closure_discussion = current_discussion

    # Store admin notes
    risk.admin_notes = closure_note
    risk.status = "CLOSED"
    risk.closed_at = dt.datetime.utcnow()
    risk.closed_by = closed_by_id

    log = AuditLog(
        actor_id=closed_by_id,
        action="CLOSE_RISK",
        entity_type="risk",
        entity_id=risk.id,
        before_json={"status": "RESOLVED"},
        after_json={
            "status": "CLOSED",
            "closure_note": closure_note
        }
    )
    tenant_db.add(log)
    tenant_db.commit()
    return risk