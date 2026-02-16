"""
Text embedding and similarity tools.

Provides access to the server's embedding model (Google AI gemini-embedding-001)
for semantic similarity scoring. These are general-purpose utilities not tied
to the memory/tag system.
"""

from typing import Optional, List, Dict, Any
import os

# Try to import Google AI for embeddings
try:
    import google.genai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 3072


def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Generate an embedding vector for text using Google AI API.

    Args:
        text: Text to embed

    Returns:
        768-dimensional embedding vector, or None if API unavailable
    """
    if not GENAI_AVAILABLE:
        return None

    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        return None

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text
        )
        return response.embeddings[0].values
    except Exception:
        return None


def cosine_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Calculate cosine similarity between two embedding vectors.

    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector

    Returns:
        Cosine similarity score in range [0.0, 1.0]
    """
    if not embedding1 or not embedding2:
        return 0.0

    try:
        import numpy as np

        vec1 = np.array(embedding1, dtype=np.float32)
        vec2 = np.array(embedding2, dtype=np.float32)

        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = np.dot(vec1, vec2) / (norm1 * norm2)
        return max(0.0, min(1.0, float(similarity)))

    except Exception:
        return 0.0


def weighted_combine_embeddings(
    emb_primary: List[float],
    emb_context: List[float],
    primary_weight: float,
    context_weight: float
) -> Optional[List[float]]:
    """
    Combine two embedding vectors as a weighted sum, then re-normalize.

    Weights do not need to sum to 1 — the result is L2-normalized, so only
    their ratio matters. The re-normalization preserves directional meaning
    while making the result suitable for cosine similarity.

    Args:
        emb_primary: Embedding of the primary (foreground) text
        emb_context: Embedding of the context (background) text
        primary_weight: Relative weight for the primary embedding
        context_weight: Relative weight for the context embedding

    Returns:
        Normalized combined embedding vector, or None on failure
    """
    try:
        import numpy as np

        vec_p = np.array(emb_primary, dtype=np.float32) * primary_weight
        vec_c = np.array(emb_context, dtype=np.float32) * context_weight
        combined = vec_p + vec_c

        norm = np.linalg.norm(combined)
        if norm == 0:
            return None

        return (combined / norm).tolist()

    except Exception:
        return None


def compute_text_similarity(
    query: str,
    text: str,
    context: str = "",
    text_weight: float = 0.7,
    context_weight: float = 0.3
) -> Dict[str, Any]:
    """
    Compute semantic similarity between a query and a text, with optional context.

    When `context` is provided, the text and context embeddings are combined as a
    weighted sum (then re-normalized) before comparison against the query. This
    allows the text to be evaluated in light of its surrounding context while
    still being weighted more heavily than it.

    When `context` is empty, the similarity is computed directly between query
    and text — weights are ignored.

    Args:
        query: The reference text or semantic label (e.g. "grace_follows_faith")
        text: The primary text to evaluate (e.g. a verse)
        context: Optional surrounding context (e.g. a pericope). Default: no context.
        text_weight: Weight for the text embedding when combining with context. Default: 0.7
        context_weight: Weight for the context embedding. Default: 0.3

    Returns:
        Dictionary with similarity score and metadata
    """
    api_available = GENAI_AVAILABLE and bool(os.getenv('GOOGLE_API_KEY'))

    if not api_available:
        return {
            "success": False,
            "error": "Embedding API unavailable. Ensure google-genai is installed and GOOGLE_API_KEY is set.",
            "api_available": False
        }

    query_emb = generate_embedding(query)
    text_emb = generate_embedding(text)

    if query_emb is None or text_emb is None:
        return {
            "success": False,
            "error": "Failed to generate embeddings. Check API key and connectivity.",
            "api_available": api_available
        }

    context_used = bool(context and context.strip())

    if context_used:
        context_emb = generate_embedding(context)
        if context_emb is None:
            return {
                "success": False,
                "error": "Failed to generate embedding for context.",
                "api_available": api_available
            }
        target_emb = weighted_combine_embeddings(text_emb, context_emb, text_weight, context_weight)
        if target_emb is None:
            return {
                "success": False,
                "error": "Failed to combine text and context embeddings.",
                "api_available": api_available
            }
    else:
        target_emb = text_emb

    score = cosine_similarity(query_emb, target_emb)

    result: Dict[str, Any] = {
        "success": True,
        "similarity": round(score, 4),
        "query": query,
        "text": text,
        "model": EMBEDDING_MODEL,
        "api_available": True,
        "context_used": context_used
    }

    if context_used:
        result["context"] = context
        result["text_weight"] = text_weight
        result["context_weight"] = context_weight

    return result


def rank_texts_by_similarity(query: str, candidates: List[str]) -> Dict[str, Any]:
    """
    Rank a list of candidate texts by semantic similarity to a query.

    Args:
        query: Reference text to compare against
        candidates: List of texts to rank

    Returns:
        Dictionary with candidates ranked by descending similarity score
    """
    api_available = GENAI_AVAILABLE and bool(os.getenv('GOOGLE_API_KEY'))

    if not api_available:
        return {
            "success": False,
            "error": "Embedding API unavailable. Ensure google-genai is installed and GOOGLE_API_KEY is set.",
            "api_available": False
        }

    if not candidates:
        return {
            "success": False,
            "error": "No candidate texts provided.",
            "api_available": api_available
        }

    query_embedding = generate_embedding(query)
    if query_embedding is None:
        return {
            "success": False,
            "error": "Failed to generate embedding for query.",
            "api_available": api_available
        }

    ranked = []
    failed = []

    for i, candidate in enumerate(candidates):
        emb = generate_embedding(candidate)
        if emb is None:
            failed.append({"index": i, "text": candidate})
            continue
        score = cosine_similarity(query_embedding, emb)
        ranked.append({
            "index": i,
            "text": candidate,
            "similarity": round(score, 4)
        })

    ranked.sort(key=lambda x: x["similarity"], reverse=True)

    result = {
        "success": True,
        "query": query,
        "ranked": ranked,
        "total_candidates": len(candidates),
        "model": EMBEDDING_MODEL,
        "api_available": True
    }

    if failed:
        result["failed"] = failed

    return result
