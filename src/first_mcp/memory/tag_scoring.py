"""
Soft tag-to-tag similarity scoring for memory retrieval.

Scoring model:

  For each query tag qi and a candidate memory:
    sim(qi, memory) = max cosine_similarity(embed(qi), embed(mj))
                      over all memory tags mj with stored embeddings

  Adaptive threshold per query tag (computed across all candidate memories):
    threshold(qi) = mean(sim) + 0.5 * std(sim)
    When std ≈ 0 (single candidate or uniform scores), threshold is fixed at 0.5.

  Tag relevance score (sum-of-squares):
    tag_score = Σ sim(qi, memory)²  for all qi where sim > threshold

  Final rank score blends tag relevance with memory importance:
    rank_score = tag_score + IMPORTANCE_WEIGHT × importance

  IMPORTANCE_WEIGHT = 0.333 so that the default importance level (3) contributes
  ≈ 1.0 — the same order as a perfect single-tag match — making importance a
  meaningful tiebreaker without overriding tag relevance.

This makes retrieval robust to vocabulary mismatch ("scheduling" finds
"timetabling") while naturally surfacing higher-importance memories among
equally-relevant candidates.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from ..embeddings import generate_embedding as _generate_embedding, cosine_similarity as _cosine_similarity
from .database import get_tags_tinydb

IMPORTANCE_WEIGHT = 0.333


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

    # Second pass: rank score = sum-of-squares of above-threshold sims + importance weight
    scored: List[Tuple[float, Dict[str, Any], List[str]]] = []
    for i, memory in enumerate(all_memories):
        tag_score = 0.0
        matched: List[str] = []
        for qt in qt_list:
            s = raw_scores[qt][i]
            if s > thresholds[qt]:
                tag_score += s * s
                matched.append(qt)
        if tag_score > 0:
            importance = memory.get('importance', 3)
            rank_score = tag_score + IMPORTANCE_WEIGHT * importance
            scored.append((rank_score, memory, matched))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored
