# backend/app/services/embedding_service.py

import os
import time
from typing import List

from google.genai import Client
from dotenv import load_dotenv

load_dotenv()

# Initialize client once
client = Client(api_key=os.getenv("GEMINI_API_KEY"))

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", 3072))


def get_embedding(text: str, task_type: str = "retrieval_document") -> List[float]:
    """
    Generate embedding using Google's latest Gemini embedding model.
    
    task_type options:
      - retrieval_document  → when storing chunks/documents
      - retrieval_query     → when searching/querying
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty for embedding")

    try:
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config={"task_type": task_type}
        )
        # New SDK returns: result.embeddings[0].values
        return result.embeddings[0].values

    except Exception as e:
        raise ValueError(f"Embedding generation failed: {e}")


def get_embeddings_batch(
    texts: List[str],
    task_type: str = "retrieval_document",
    delay: float = 0.2
) -> List[List[float]]:
    """
    Generate embeddings for multiple texts with rate limit safety.
    """
    embeddings = []
    total = len(texts)

    for idx, text in enumerate(texts):
        print(f"  Embedding chunk {idx + 1}/{total}...")
        embedding = get_embedding(text, task_type)
        embeddings.append(embedding)

        if idx < total - 1:
            time.sleep(delay)

    return embeddings


def get_query_embedding(query: str) -> List[float]:
    """Generate embedding for search queries."""
    return get_embedding(query, task_type="retrieval_query")


# Optional: Quick test when running file directly
if __name__ == "__main__":
    emb = get_embedding("This is a test sentence for GRC compliance")
    print("First 5 values:", emb[:5])
    print("Embedding length:", len(emb))
    print("✅ Embedding service is working!")