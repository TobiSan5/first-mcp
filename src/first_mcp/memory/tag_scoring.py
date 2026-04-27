"""
Soft tag-to-tag similarity scoring for memory retrieval.

Implements the scoring model from the MCP Memory Retrieval Architecture design
(markdown/mcp-memory-retrieval-architecture.md):

  For each query tag qi:
    score(qi, memory) = max cosine_similarity(embed(qi), embed(mj))
                        over all memory tags mj

  Adaptive threshold per query tag (computed across all candidate memories):
    threshold(qi) = mean(scores) + 0.5 * std(scores)

  Rank score for a memory = Σ score(qi) for all qi where score > threshold

This makes retrieval robust to vocabulary mismatch: "scheduling software"
will still surface a memory tagged "timetabling" if their embeddings are close.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from ..embeddings import generate_embedding as _generate_embedding, cosine_similarity as _cosine_similarity
from .database import get_tags_tinydb


def build_tag_registry() -> Dict[str, List[float]]:
    """
    Load all tags that have stored embeddings into a dict.

    Returns:
        {tag_name: embedding_vector} — only entries with non-empty embeddings.
    """
    try:
        tags_db = get_tags_tinydb()
        tags_table = tags_db.table('tags')
        all_tags = tags_table.all()
        tags_db.close()

        registry: Dict[str, List[float]] = {}
        for entry in all_tags:
            tag = entry.get('tag', '')
            emb = entry.get('embedding', [])
            if tag and emb and len(emb) > 0:
                registry[tag] = emb
        return registry
    except Exception:
        return {}


def score_memories_by_tags(
    query_tags: List[str],
    all_memories: List[Dict[str, Any]],
    tag_registry: Dict[str, List[float]],
) -> List[Tuple[float, Dict[str, Any], List[str]]]:
    """
    Score and rank memories using soft tag-to-tag similarity.

    Args:
        query_tags: Tags extracted from the search request.
        all_memories: Candidate memories (already filtered by content/category).
        tag_registry: {tag_name: embedding_vector} built by build_tag_registry().

    Returns:
        List of (rank_score, memory, matched_query_tags) sorted descending by
        rank_score.  Memories with no tag match above threshold are omitted.
        Returns [] when no query-tag embeddings are resolvable.
    """
    # Resolve embeddings for query tags (registry first, on-the-fly fallback)
    qt_embeddings: Dict[str, List[float]] = {}
    for qt in query_tags:
        emb = tag_registry.get(qt)
        if emb is None:
            emb = _generate_embedding(qt)
        if emb:
            qt_embeddings[qt] = emb

    if not qt_embeddings:
        return []

    qt_list = list(qt_embeddings.keys())

    # First pass: raw_scores[qt][i] = best cosine sim between qt and memory[i]'s tags
    raw_scores: Dict[str, List[float]] = {qt: [] for qt in qt_list}

    for memory in all_memories:
        mem_embs = [
            tag_registry[mt]
            for mt in memory.get('tags', [])
            if mt in tag_registry
        ]
        for qt in qt_list:
            qt_emb = qt_embeddings[qt]
            if mem_embs:
                best = max(_cosine_similarity(qt_emb, mt_emb) for mt_emb in mem_embs)
            else:
                best = 0.0
            raw_scores[qt].append(best)

    # Adaptive threshold per query tag: mean + 0.5 * std across all memories.
    # When std ≈ 0 (single candidate or all scores identical) the formula collapses
    # to the mean itself and the strict > check would exclude everything.  Use a
    # fixed midpoint instead so a well-matched memory still registers as a hit.
    thresholds: Dict[str, float] = {}
    for qt in qt_list:
        scores = raw_scores[qt]
        if not scores:
            thresholds[qt] = 0.75
            continue
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std = math.sqrt(variance)
        if std < 1e-9:
            thresholds[qt] = 0.5
        else:
            thresholds[qt] = mean + 0.5 * std

    # Second pass: rank score = sum of above-threshold scores per memory
    scored: List[Tuple[float, Dict[str, Any], List[str]]] = []
    for i, memory in enumerate(all_memories):
        rank_score = 0.0
        matched: List[str] = []
        for qt in qt_list:
            s = raw_scores[qt][i]
            if s > thresholds[qt]:
                rank_score += s
                matched.append(qt)
        if rank_score > 0:
            scored.append((rank_score, memory, matched))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored
