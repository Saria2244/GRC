# backend/app/services/pdf_service.py

import hashlib
import io
from typing import List, Tuple


def extract_text_from_pdf(file_bytes: bytes) -> Tuple[str, List[int]]:
    """
    Extract text from a PDF file.
    Returns:
        - full text as a single string
        - list mapping each word to its page number
    """
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        full_text = ""
        page_texts = []

        for page_num, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            page_texts.append((page_num + 1, text))
            full_text += f"\n{text}"

        return full_text.strip(), page_texts

    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {e}")


def chunk_text_with_pages(
    page_texts: List[Tuple[int, str]],
    chunk_size: int = 500,
    overlap: int = 50
) -> List[dict]:
    """
    Split text into overlapping chunks, tracking page numbers.
    Returns list of dicts with chunk_text, chunk_index, page_no.
    """
    chunks = []
    chunk_index = 0

    # Flatten all words with their page numbers
    word_page_pairs = []
    for page_no, text in page_texts:
        words = text.split()
        for word in words:
            word_page_pairs.append((word, page_no))

    if not word_page_pairs:
        return chunks

    total_words = len(word_page_pairs)
    step = chunk_size - overlap

    for start in range(0, total_words, step):
        end = min(start + chunk_size, total_words)
        chunk_pairs = word_page_pairs[start:end]

        if not chunk_pairs:
            break

        chunk_text = " ".join(w for w, _ in chunk_pairs)
        # Use the page number of the first word in the chunk
        page_no = chunk_pairs[0][1]

        if len(chunk_text.strip()) < 50:
            # Skip very short chunks (usually just page headers)
            continue

        chunks.append({
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
            "page_no": page_no
        })
        chunk_index += 1

        if end == total_words:
            break

    return chunks


def compute_sha256(file_bytes: bytes) -> str:
    """Compute SHA-256 hash of file bytes for integrity check."""
    return hashlib.sha256(file_bytes).hexdigest()