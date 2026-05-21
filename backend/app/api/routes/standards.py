# backend/app/api/routes/standards.py

from fastapi import (
    APIRouter, Depends, HTTPException,
    UploadFile, File, Form
)
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_standards_db
from app.core.dependencies import admin_only, any_authenticated_user
from app.models.standards_models import (
    StandardsVersion, StandardChunk, StandardFileObject
)
from app.schemas.standards_schemas import (
    StandardsVersionResponse, StandardsVersionDetail,
    StandardChunkResponse, ActivateStandardRequest
)
from app.services.standards_service import ingest_standard_document

router = APIRouter(prefix="/standards", tags=["Standards Library"])


@router.post("/upload", response_model=StandardsVersionResponse)
async def upload_standard(
    title: str = Form(...),
    country: str = Form(...),
    framework: str = Form(...),
    version: str = Form(...),
    file: UploadFile = File(...),
    standards_db: Session = Depends(get_standards_db),
    current_user=Depends(admin_only)
):
    """
    Admin only. Upload an official compliance document PDF.
    Triggers full ingestion: extract → chunk → embed → store.
    """
    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )

    # Read file bytes
    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # Max 50MB
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 50MB"
        )

    try:
        std_version = ingest_standard_document(
            standards_db=standards_db,
            file_bytes=file_bytes,
            file_name=file.filename,
            title=title,
            country=country,
            framework=framework,
            version=version
        )
        return std_version

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}"
        )


@router.get("", response_model=List[StandardsVersionDetail])
def list_standards(
    country: str = None,
    framework: str = None,
    standards_db: Session = Depends(get_standards_db),
    current_user=Depends(any_authenticated_user)
):
    """
    List all available compliance standards.
    Optionally filter by country or framework.
    """
    query = standards_db.query(StandardsVersion)

    if country:
        query = query.filter(StandardsVersion.country == country)
    if framework:
        query = query.filter(StandardsVersion.framework == framework)

    versions = query.order_by(StandardsVersion.created_at.desc()).all()

    results = []
    for v in versions:
        # Count chunks for this version
        chunk_count = standards_db.query(StandardChunk).filter_by(
            standards_version_id=v.id
        ).count()

        # Get file info
        file_obj = None
        if v.file_object_id:
            file_obj = standards_db.query(StandardFileObject).filter_by(
                id=v.file_object_id
            ).first()

        detail = StandardsVersionDetail(
            id=v.id,
            country=v.country,
            framework=v.framework,
            version=v.version,
            title=v.title,
            is_active=v.is_active,
            created_at=v.created_at,
            total_chunks=chunk_count,
            file_name=file_obj.file_name if file_obj else None,
            size_bytes=file_obj.size_bytes if file_obj else None
        )
        results.append(detail)

    return results


@router.get("/{standard_id}", response_model=StandardsVersionDetail)
def get_standard(
    standard_id: str,
    standards_db: Session = Depends(get_standards_db),
    current_user=Depends(any_authenticated_user)
):
    """Get details of a specific standard."""
    version = standards_db.query(StandardsVersion).filter_by(
        id=standard_id
    ).first()

    if not version:
        raise HTTPException(status_code=404, detail="Standard not found")

    chunk_count = standards_db.query(StandardChunk).filter_by(
        standards_version_id=version.id
    ).count()

    file_obj = None
    if version.file_object_id:
        file_obj = standards_db.query(StandardFileObject).filter_by(
            id=version.file_object_id
        ).first()

    return StandardsVersionDetail(
        id=version.id,
        country=version.country,
        framework=version.framework,
        version=version.version,
        title=version.title,
        is_active=version.is_active,
        created_at=version.created_at,
        total_chunks=chunk_count,
        file_name=file_obj.file_name if file_obj else None,
        size_bytes=file_obj.size_bytes if file_obj else None
    )


@router.put("/{standard_id}/activate")
def activate_standard(
    standard_id: str,
    request: ActivateStandardRequest,
    standards_db: Session = Depends(get_standards_db),
    current_user=Depends(admin_only)
):
    """
    Admin only. Set a standard as active or inactive.
    Only one version per country+framework can be active at a time.
    """
    version = standards_db.query(StandardsVersion).filter_by(
        id=standard_id
    ).first()

    if not version:
        raise HTTPException(status_code=404, detail="Standard not found")

    if request.is_active:
        # Deactivate all other versions for same country+framework
        standards_db.query(StandardsVersion).filter(
            StandardsVersion.country == version.country,
            StandardsVersion.framework == version.framework,
            StandardsVersion.id != version.id
        ).update({"is_active": False})

    version.is_active = request.is_active
    standards_db.commit()

    return {
        "message": f"Standard {'activated' if request.is_active else 'deactivated'}",
        "id": str(version.id),
        "is_active": version.is_active
    }


@router.get("/{standard_id}/chunks",
            response_model=List[StandardChunkResponse])
def get_standard_chunks(
    standard_id: str,
    limit: int = 20,
    offset: int = 0,
    standards_db: Session = Depends(get_standards_db),
    current_user=Depends(admin_only)
):
    """Admin only. View the text chunks of a standard for debugging."""
    version = standards_db.query(StandardsVersion).filter_by(
        id=standard_id
    ).first()

    if not version:
        raise HTTPException(status_code=404, detail="Standard not found")

    chunks = standards_db.query(StandardChunk).filter_by(
        standards_version_id=version.id
    ).order_by(
        StandardChunk.chunk_index
    ).offset(offset).limit(limit).all()

    return chunks