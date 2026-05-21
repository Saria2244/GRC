# backend/app/services/standards_service.py

import os
from sqlalchemy.orm import Session
from app.models.standards_models import (
    StandardFileObject, StandardsVersion, StandardChunk
)
from app.services.pdf_service import (
    extract_text_from_pdf, chunk_text_with_pages, compute_sha256
)
from app.services.embedding_service import get_embeddings_batch


def ingest_standard_document(
    standards_db: Session,
    file_bytes: bytes,
    file_name: str,
    title: str,
    country: str,
    framework: str,
    version: str
) -> StandardsVersion:
    """
    Full ingestion pipeline for an official compliance document:
    1. Store file bytes
    2. Extract text
    3. Chunk text
    4. Generate embeddings
    5. Store everything in standards_db
    """

    print(f"\nIngesting: {title}")
    sha256 = compute_sha256(file_bytes)

    # ── 1. Check for duplicate ────────────────────────────
    existing = standards_db.query(StandardsVersion).filter_by(
        country=country,
        framework=framework,
        version=version
    ).first()
    if existing:
        raise ValueError(
            f"Standard {framework} {version} for {country} already exists"
        )

    # ── 2. Store file bytes ───────────────────────────────
    print("  Storing file...")
    file_obj = StandardFileObject(
        file_name=file_name,
        mime_type="application/pdf",
        size_bytes=len(file_bytes),
        sha256=sha256,
        content=file_bytes
    )
    standards_db.add(file_obj)
    standards_db.flush()

    # ── 3. Create standards version record ────────────────
    std_version = StandardsVersion(
        country=country,
        framework=framework,
        version=version,
        title=title,
        file_object_id=file_obj.id,
        sha256=sha256,
        is_active=False  # Admin must manually activate
    )
    standards_db.add(std_version)
    standards_db.flush()

    # ── 4. Extract text from PDF ──────────────────────────
    print("  Extracting text...")
    full_text, page_texts = extract_text_from_pdf(file_bytes)

    if not full_text.strip():
        raise ValueError("Could not extract text from PDF.")

    # ── 5. Chunk the text ─────────────────────────────────
    print("  Chunking text...")
    chunks = chunk_text_with_pages(page_texts)
    print(f"  Created {len(chunks)} chunks")

    # ── 6. Generate embeddings ────────────────────────────
    print("  Generating embeddings (this may take a moment)...")
    chunk_texts = [c["chunk_text"] for c in chunks]
    embeddings = get_embeddings_batch(chunk_texts)

    # ── 7. Store chunks with embeddings ───────────────────
    print("  Storing chunks...")
    for chunk, embedding in zip(chunks, embeddings):
        std_chunk = StandardChunk(
            standards_version_id=std_version.id,
            chunk_index=chunk["chunk_index"],
            chunk_text=chunk["chunk_text"],
            page_no=chunk["page_no"],
            embedding=embedding
        )
        standards_db.add(std_chunk)

    standards_db.commit()
    print(f"  Done. Standard ingested successfully.\n")

    return std_version


def get_standard_chunks_for_audit(
    standards_db: Session,
    standards_version_id: str,
    limit: int = 10
) -> list:
    """
    Fetch the first N chunks of a standard.
    Used by the AI to generate audit questions.
    """
    return standards_db.query(StandardChunk).filter_by(
        standards_version_id=standards_version_id
    ).order_by(StandardChunk.chunk_index).limit(limit).all()