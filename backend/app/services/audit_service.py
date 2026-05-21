# backend/app/services/audit_service.py

from sqlalchemy.orm import Session
from app.models.tenant_models import (
    Audit, AuditQuestion, AuditAnswer, Risk
)
from app.models.standards_models import StandardsVersion, StandardChunk
from app.services.audit_ai_service import generate_risk_from_answer
from app.core.questions_bank import get_questions_for_audit_type


def create_audit_with_questions(
    tenant_db: Session,
    standards_db: Session,
    standards_version_id: str,
    title: str,
    audit_type: str,
    created_by_id: str
) -> Audit:
    """
    Create a new audit and load the hardcoded questions
    for the selected audit type. No Gemini call needed here.
    """

    # ── 1. Load the standard ──────────────────────────────
    std_version = standards_db.query(StandardsVersion).filter_by(
        id=standards_version_id
    ).first()

    if not std_version:
        raise ValueError("Standard not found")

    # ── 2. Create audit record ────────────────────────────
    audit = Audit(
        title=title,
        audit_type=audit_type,
        standards_version_id=std_version.id,
        country=std_version.country,
        framework=std_version.framework,
        status="IN_PROGRESS",
        created_by=created_by_id
    )
    tenant_db.add(audit)
    tenant_db.flush()

    # ── 3. Load hardcoded questions for this audit type ───
    # No Gemini call. Zero tokens consumed.
    questions_data = get_questions_for_audit_type(audit_type)

    # ── 4. Store questions ────────────────────────────────
    for q in questions_data:
        question = AuditQuestion(
            audit_id=audit.id,
            question_index=q["question_index"],
            question_text=q["question_text"],
            question_type=q["question_type"],
            policy_reference=q["policy_reference"]
        )
        tenant_db.add(question)

    tenant_db.commit()
    tenant_db.refresh(audit)
    return audit


def evaluate_audit_and_create_risks(
    tenant_db: Session,
    standards_db: Session,
    audit_id: str
) -> dict:
    """
    After all answers submitted:
    1. Score each answer with AI
    2. Create risk tickets for low scoring answers
    3. Calculate final compliance score
    4. Mark audit as COMPLETED
    """

    audit = tenant_db.query(Audit).filter_by(id=audit_id).first()
    if not audit:
        raise ValueError("Audit not found")

    questions = tenant_db.query(AuditQuestion).filter_by(
        audit_id=audit_id
    ).all()

    answers = tenant_db.query(AuditAnswer).filter_by(
        audit_id=audit_id
    ).all()

    answer_map = {str(a.question_id): a for a in answers}

    # Load standard chunks for AI context
    chunks = standards_db.query(StandardChunk).filter_by(
        standards_version_id=str(audit.standards_version_id)
    ).order_by(StandardChunk.chunk_index).limit(10).all()

    standard_context = "\n".join([
        c.chunk_text[:300] for c in chunks[:3]
    ])

    risks_created = 0
    total_score = 0.0
    RISK_THRESHOLD = 0.75

    for question in questions:
        answer = answer_map.get(str(question.id))

        if not answer:
            answer_text = "No answer provided"
            ai_score = 0.0
        else:
            answer_text = answer.answer_text or "No answer provided"
            ai_score = answer.ai_score or 0.0

        total_score += ai_score

        # Create risk ticket if answer score is below threshold
        if ai_score < RISK_THRESHOLD:
            try:
                risk_data = generate_risk_from_answer(
                    question_text=question.question_text,
                    answer_text=answer_text,
                    ai_score=ai_score,
                    standard_context=standard_context,
                    framework=audit.framework,
                    country=audit.country
                )

                risk = Risk(
                    title=risk_data["title"],
                    severity=risk_data["severity"],
                    description=risk_data["description"],
                    suggested_fix=risk_data["suggested_fix"],
                    status="OPEN",
                    country=audit.country,
                    framework=audit.framework,
                    standards_version_id=audit.standards_version_id
                )
                tenant_db.add(risk)
                risks_created += 1

            except Exception as e:
                print(
                    f"Risk generation failed for question "
                    f"{question.question_index}: {e}"
                )

    final_score = (
        (total_score / len(questions)) * 100 if questions else 0
    )

    audit.status = "COMPLETED"
    audit.final_score = round(final_score, 1)
    tenant_db.commit()

    return {
        "audit_id": str(audit_id),
        "final_score": round(final_score, 1),
        "status": "COMPLETED",
        "total_questions": len(questions),
        "answered_questions": len(answers),
        "risks_created": risks_created,
        "summary": (
            f"Audit completed with {final_score:.0f}% compliance score. "
            f"{risks_created} risk tickets created."
        )
    }