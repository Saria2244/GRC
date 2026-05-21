from fastapi import (
    APIRouter, Depends, HTTPException,
    UploadFile, File, Form
)
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_standards_db, get_tenant_db
from app.core.dependencies import (
    auditor_or_admin, any_authenticated_user
)
from app.models.tenant_models import (
    Audit, AuditQuestion, AuditAnswer
)
from app.schemas.audit_schemas import (
    CreateAuditRequest, AuditResponse, AuditDetailResponse,
    AuditAnswerResponse, SubmitTextAnswerRequest, EvaluationResult
)
from app.services.audit_service import (
    create_audit_with_questions,
    evaluate_audit_and_create_risks
)
from app.services.audit_ai_service import (
    analyze_text_answer, analyze_image_answer
)
from app.models.standards_models import StandardChunk

from app.core.enums import AuditType
from app.schemas.audit_schemas import AuditTypeOption
from app.services.embedding_service import get_query_embedding
from sqlalchemy import text as sql_text

router = APIRouter(prefix="/audits", tags=["Audit Engine"])

@router.get("/types", response_model=List[AuditTypeOption])
def get_audit_types(
    current_user=Depends(any_authenticated_user)
):
    """
    Returns all available audit types for the frontend dropdown.
    Frontend calls this to populate the audit type selector.
    """
    return [
        AuditTypeOption(value=t.value, label=t.value)
        for t in AuditType
    ]

@router.post("", response_model=AuditDetailResponse)
def create_audit(
    request: CreateAuditRequest,
    standards_db: Session = Depends(get_standards_db),
    current_user=Depends(auditor_or_admin)
):
    """
    Create a new audit. AI immediately generates 10 questions
    from the selected standard.
    """
    tenant_db = get_tenant_db(current_user.tenant_db_url)

    try:
        audit = create_audit_with_questions(
            tenant_db=tenant_db,
            standards_db=standards_db,
            standards_version_id=request.standards_version_id,
            title=request.title,
            audit_type=request.audit_type,
            created_by_id=str(current_user.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Audit creation failed: {str(e)}"
        )

    # Load questions to return
    questions = tenant_db.query(AuditQuestion).filter_by(
        audit_id=audit.id
    ).order_by(AuditQuestion.question_index).all()

    return AuditDetailResponse(
        id=audit.id,
        title=audit.title,
        audit_type=audit.audit_type,
        standards_version_id=audit.standards_version_id,
        country=audit.country,
        framework=audit.framework,
        status=audit.status,
        final_score=audit.final_score,
        created_at=audit.created_at,
        questions=questions
    )


@router.get("", response_model=List[AuditResponse])
def list_audits(
    current_user=Depends(any_authenticated_user)
):
    """List all audits for this tenant."""
    tenant_db = get_tenant_db(current_user.tenant_db_url)
    audits = tenant_db.query(Audit).order_by(
        Audit.created_at.desc()
    ).all()
    return audits


@router.get("/{audit_id}", response_model=AuditDetailResponse)
def get_audit(
    audit_id: str,
    current_user=Depends(any_authenticated_user)
):
    """Get audit details with all questions."""
    tenant_db = get_tenant_db(current_user.tenant_db_url)
    audit = tenant_db.query(Audit).filter_by(id=audit_id).first()

    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    questions = tenant_db.query(AuditQuestion).filter_by(
        audit_id=audit_id
    ).order_by(AuditQuestion.question_index).all()

    return AuditDetailResponse(
        id=audit.id,
        title=audit.title,
        audit_type=audit.audit_type,
        standards_version_id=audit.standards_version_id,
        country=audit.country,
        framework=audit.framework,
        status=audit.status,
        final_score=audit.final_score,
        created_at=audit.created_at,
        questions=questions
    )

def get_relevant_context(
    standards_db,
    standards_version_id: str,
    question_text: str,
    policy_reference: str,
    top_k: int = 3
) -> str:
    """
    Use pgvector to find the most relevant standard chunks
    for a specific question. Much more accurate than
    always using the first 5 chunks.
    """
    # Create a search query combining question + topic
    search_query = f"{policy_reference}: {question_text}"

    # Get embedding for this search query
    query_embedding = get_query_embedding(search_query)

    # Find most similar chunks using cosine similarity
    result = standards_db.execute(
        sql_text("""
            SELECT chunk_text,
                   1 - (embedding <=> CAST(:q AS vector)) AS similarity
            FROM standard_chunks
            WHERE standards_version_id = CAST(:version_id AS uuid)
            ORDER BY embedding <=> CAST(:q AS vector)
            LIMIT :top_k
        """),
        {
            "q": str(query_embedding),
            "version_id": str(standards_version_id),
            "top_k": top_k
        }
    ).fetchall()

    if not result:
        # Fallback to first chunks if no results
        chunks = standards_db.query(StandardChunk).filter_by(
            standards_version_id=str(standards_version_id)
        ).order_by(StandardChunk.chunk_index).limit(3).all()
        return "\n\n".join([c.chunk_text[:400] for c in chunks])

    return "\n\n".join([
        f"[Relevance: {row.similarity:.0%}]\n{row.chunk_text[:400]}"
        for row in result
    ])

@router.post("/{audit_id}/answers/text",
             response_model=AuditAnswerResponse)
def submit_text_answer(
    audit_id: str,
    request: SubmitTextAnswerRequest,
    standards_db: Session = Depends(get_standards_db),
    current_user=Depends(any_authenticated_user)
):
    tenant_db = get_tenant_db(current_user.tenant_db_url)

    audit = tenant_db.query(Audit).filter_by(id=audit_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    if audit.status == "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="Audit is already completed"
        )

    question = tenant_db.query(AuditQuestion).filter_by(
        id=request.question_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # ── Get relevant context using pgvector ───────────────
    # This finds the chunks most relevant to THIS specific question
    # instead of always using the same first 5 chunks
    standard_context = get_relevant_context(
        standards_db=standards_db,
        standards_version_id=str(audit.standards_version_id),
        question_text=question.question_text,
        policy_reference=question.policy_reference or ""
    )

    # Build the answer text
    if request.answer_type in ["YES", "NO"]:
        answer_text = request.answer_type
    else:
        answer_text = request.answer_text or ""

    # AI scores the answer against relevant context
    try:
        ai_result = analyze_text_answer(
            question_text=question.question_text,
            answer_text=answer_text,
            standard_context=standard_context,
            question_type=question.question_type
        )
        ai_score = ai_result.get("score", 0.0)
        ai_feedback = ai_result.get("feedback", "")

    except Exception as e:
        error_msg = str(e)
        print(f"AI scoring error: {error_msg}")
        if "429" in error_msg or "quota" in error_msg.lower():
            raise HTTPException(
                status_code=429,
                detail="Gemini API rate limit reached. Please wait 1-2 minutes and try again."
            )
        raise HTTPException(
            status_code=500,
            detail=f"AI scoring failed: {error_msg}"
        )

    # Save or update the answer
    existing = tenant_db.query(AuditAnswer).filter_by(
        audit_id=audit_id,
        question_id=request.question_id
    ).first()

    if existing:
        existing.answer_type = request.answer_type
        existing.answer_text = answer_text
        existing.ai_score = ai_score
        existing.ai_feedback = ai_feedback
        answer = existing
    else:
        answer = AuditAnswer(
            audit_id=audit_id,
            question_id=request.question_id,
            answer_type=request.answer_type,
            answer_text=answer_text,
            ai_score=ai_score,
            ai_feedback=ai_feedback,
            answered_by=str(current_user.id)
        )
        tenant_db.add(answer)

    tenant_db.commit()
    tenant_db.refresh(answer)
    return answer

@router.post("/{audit_id}/answers/image",
             response_model=AuditAnswerResponse)
async def submit_image_answer(
    audit_id: str,
    question_id: str = Form(...),
    image: UploadFile = File(...),
    standards_db: Session = Depends(get_standards_db),
    current_user=Depends(any_authenticated_user)
):
    """
    Submit an image as evidence for a question.
    Gemini Vision analyzes the image and scores it.
    """
    tenant_db = get_tenant_db(current_user.tenant_db_url)

    audit = tenant_db.query(Audit).filter_by(id=audit_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    if audit.status == "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="Audit is already completed"
        )

    question = tenant_db.query(AuditQuestion).filter_by(
        id=question_id
    ).first()
    if not question:
        raise HTTPException(
            status_code=404, detail="Question not found"
        )

    # Validate image type
    allowed = ["image/jpeg", "image/png",
               "image/jpg", "image/webp"]
    if image.content_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Only JPEG, PNG and WebP images are supported"
        )

    image_bytes = await image.read()

    # Get standard context
    chunks = standards_db.query(StandardChunk).filter_by(
        standards_version_id=str(audit.standards_version_id)
    ).order_by(StandardChunk.chunk_index).limit(5).all()

    standard_context = "\n".join([
        c.chunk_text[:300] for c in chunks
    ])

    # Gemini Vision analyzes the image
    try:
        ai_result = analyze_image_answer(
            question_text=question.question_text,
            image_bytes=image_bytes,
            standard_context=standard_context
        )
        ai_score = ai_result.get("score", 0.0)
        ai_feedback = ai_result.get("feedback", "")
        image_analysis = ai_result.get("image_analysis", "")
    except Exception as e:
        print(f"Image analysis failed: {e}")
        ai_score = 0.0
        ai_feedback = "Image analysis failed"
        image_analysis = str(e)

    # Save or update the answer
    existing = tenant_db.query(AuditAnswer).filter_by(
        audit_id=audit_id,
        question_id=question_id
    ).first()

    if existing:
        existing.answer_type = "IMAGE"
        existing.image_bytes = image_bytes
        existing.image_analysis = image_analysis
        existing.ai_score = ai_score
        existing.ai_feedback = ai_feedback
        answer = existing
    else:
        answer = AuditAnswer(
            audit_id=audit_id,
            question_id=question_id,
            answer_type="IMAGE",
            image_bytes=image_bytes,
            image_analysis=image_analysis,
            ai_score=ai_score,
            ai_feedback=ai_feedback,
            answered_by=str(current_user.id)
        )
        tenant_db.add(answer)

    tenant_db.commit()
    tenant_db.refresh(answer)
    return answer


@router.post("/{audit_id}/submit",
             response_model=EvaluationResult)
def submit_audit(
    audit_id: str,
    standards_db: Session = Depends(get_standards_db),
    current_user=Depends(auditor_or_admin)
):
    """
    Submit the completed audit for final evaluation.
    AI creates risk tickets for all low-scoring answers.
    """
    tenant_db = get_tenant_db(current_user.tenant_db_url)

    audit = tenant_db.query(Audit).filter_by(id=audit_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    if audit.status == "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="Audit is already completed"
        )

    try:
        result = evaluate_audit_and_create_risks(
            tenant_db=tenant_db,
            standards_db=standards_db,
            audit_id=audit_id
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}"
        )


@router.get("/{audit_id}/answers",
            response_model=List[AuditAnswerResponse])
def get_audit_answers(
    audit_id: str,
    current_user=Depends(any_authenticated_user)
):
    """Get all answers submitted for an audit."""
    tenant_db = get_tenant_db(current_user.tenant_db_url)

    audit = tenant_db.query(Audit).filter_by(id=audit_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    answers = tenant_db.query(AuditAnswer).filter_by(
        audit_id=audit_id
    ).all()
    return answers

@router.post("/{audit_id}/answers/combined",
             response_model=AuditAnswerResponse)
async def submit_combined_answer(
    audit_id: str,
    question_id: str = Form(...),
    answer_text: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    standards_db: Session = Depends(get_standards_db),
    current_user=Depends(any_authenticated_user)
):
    """
    Submit both text and image together for a question.
    User can provide:
      - Text only
      - Image only
      - Both text and image together
    AI scores the combined evidence.
    """
    tenant_db = get_tenant_db(current_user.tenant_db_url)

    audit = tenant_db.query(Audit).filter_by(id=audit_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    if audit.status == "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="Audit is already completed"
        )

    question = tenant_db.query(AuditQuestion).filter_by(
        id=question_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    if not answer_text and not image:
        raise HTTPException(
            status_code=400,
            detail="Please provide at least a text answer or an image"
        )

    # Get relevant standard context using pgvector
    standard_context = get_relevant_context(
        standards_db=standards_db,
        standards_version_id=str(audit.standards_version_id),
        question_text=question.question_text,
        policy_reference=question.policy_reference or ""
    )

    # Determine answer type
    image_bytes = None
    image_analysis = None
    answer_type = "TEXT"

    if image and answer_text:
        answer_type = "BOTH"
    elif image:
        answer_type = "IMAGE"

    # Process image if provided
    if image:
        allowed = ["image/jpeg", "image/jpg",
                   "image/png", "image/webp"]
        if image.content_type not in allowed:
            raise HTTPException(
                status_code=400,
                detail="Only JPEG, PNG and WebP images supported"
            )
        image_bytes = await image.read()

        # Get image analysis from Gemini Vision
        try:
            img_result = analyze_image_answer(
                question_text=question.question_text,
                image_bytes=image_bytes,
                standard_context=standard_context
            )
            image_analysis = img_result.get("image_analysis", "")
        except Exception as e:
            image_analysis = f"Image analysis failed: {str(e)}"

    # Build combined evidence for scoring
    combined_evidence = ""
    if answer_text:
        combined_evidence += f"Written Response:\n{answer_text}\n\n"
    if image_analysis:
        combined_evidence += f"Image Evidence:\n{image_analysis}"

    # AI scores the combined evidence
    try:
        ai_result = analyze_text_answer(
            question_text=question.question_text,
            answer_text=combined_evidence,
            standard_context=standard_context,
            question_type="OPEN_TEXT"
        )
        ai_score = ai_result.get("score", 0.0)
        ai_feedback = ai_result.get("feedback", "")

    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            raise HTTPException(
                status_code=429,
                detail="Gemini API rate limit. Please wait and retry."
            )
        raise HTTPException(
            status_code=500,
            detail=f"AI scoring failed: {error_msg}"
        )

    # Save or update answer
    existing = tenant_db.query(AuditAnswer).filter_by(
        audit_id=audit_id,
        question_id=question_id
    ).first()

    if existing:
        existing.answer_type = answer_type
        existing.answer_text = answer_text
        existing.image_bytes = image_bytes
        existing.image_analysis = image_analysis
        existing.ai_score = ai_score
        existing.ai_feedback = ai_feedback
        answer = existing
    else:
        answer = AuditAnswer(
            audit_id=audit_id,
            question_id=question_id,
            answer_type=answer_type,
            answer_text=answer_text,
            image_bytes=image_bytes,
            image_analysis=image_analysis,
            ai_score=ai_score,
            ai_feedback=ai_feedback,
            answered_by=str(current_user.id)
        )
        tenant_db.add(answer)

    tenant_db.commit()
    tenant_db.refresh(answer)
    return answer