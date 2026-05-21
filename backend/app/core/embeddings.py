# backend/app/core/embeddings.py

from google.genai import Client
from typing import List

client = Client(api_key="AIzaSyChlbqWI1akJecFHnQ9eVbuTJ4718S8GDw")


def get_embedding(
    text: str, 
    task_type: str = "retrieval_document"
) -> List[float]:
    """
    Generate embedding using Google's Gemini embedding model.
    Returns a list of floats.
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")

    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config={"task_type": task_type}
    )
    
    # New SDK returns 'embeddings' (list) instead of 'embedding'
    return result.embeddings[0].values


def get_embeddings(
    texts: List[str], 
    task_type: str = "retrieval_document"
) -> List[List[float]]:
    """Generate embeddings for multiple texts."""
    return [get_embedding(text, task_type) for text in texts]


# ==================== Test when running directly ====================
if __name__ == "__main__":
    emb = get_embedding("This is a test sentence for GRC compliance")
    print("First 5 values :", emb[:5])
    print("Embedding length:", len(emb))
    print("Success!")