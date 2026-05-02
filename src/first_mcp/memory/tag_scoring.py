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
import time as _time
from typing import Any, Dict, List, Optional, Tuple

from ..embeddings import generate_embedding as _generate_embedding, cosine_similarity as _cosine_similarity
from .database import get_tags_tinydb

IMPORTANCE_WEIGHT = 0.333
_REGISTRY_CACHE_TTL = 300  # seconds

_registry_cache: Optional[Dict[str, List[float]]] = None
_registry_cache_loaded_at: float = 0.0


def build_tag_registry() -> Dict[str, List[float]]:
    """
    Load all tags that have stored embeddings into a dict.

    Caches the result in memory for _REGISTRY_CACHE_TTL seconds.  The first
    call (or any call after cache expiry) reads TinyDB; all others return the
    cached dict instantly.  Call warm_tag_registry_cache() at server startup to
    pay the I/O cost before the MCP transport starts so tool calls are never
    blocked by the initial JSON parse.

    Returns:
        {tag_name: embedding_vector} — only entries with non-empty embeddings.
    """
    import sys
    global _registry_cache, _registry_cache_loaded_at

    now = _time.monotonic()
    if _registry_cache is not None and now - _registry_cache_loaded_at < _REGISTRY_CACHE_TTL:
        print(f"{now:.3f} [tag_registry] cache hit ({len(_registry_cache)} tags)", file=sys.stderr, flush=True)
        return _registry_cache
    print(f"{now:.3f} [tag_registry] cold load (cache={'None' if _registry_cache is None else 'expired'})", file=sys.stderr, flush=True)

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

        _registry_cache = registry
        _registry_cache_loaded_at = _time.monotonic()
        return registry
    except Exception:
        return {}


def warm_tag_registry_cache() -> int:
    """
    Pre-load the tag registry into memory.  Call once at server startup, before
    mcp.run(), so the slow JSON parse happens before the MCP transport starts
    and never blocks a live tool call.

    Returns the number of tags loaded.
    """
    registry = build_tag_registry()
    return len(registry)


def invalidate_tag_registry_cache() -> None:
    """Force the next build_tag_registry() call to reload from TinyDB."""
    global _registry_cache
    _registry_cache = None


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
    import sys
    t0 = _time.monotonic()

    # Resolve embeddings for query tags (registry first, on-the-fly fallback)
    qt_embeddings: Dict[str, List[float]] = {}
    for qt in query_tags:
        emb = tag_registry.get(qt)
        in_registry = emb is not None
        if emb is None:
            print(f"{_time.monotonic():.3f} [scoring] qt={qt!r} not in registry, calling API", file=sys.stderr, flush=True)
            emb = _generate_embedding(qt)
        else:
            print(f"{_time.monotonic():.3f} [scoring] qt={qt!r} found in registry", file=sys.stderr, flush=True)
        if emb:
            qt_embeddings[qt] = emb

    if not qt_embeddings:
        print(f"{_time.monotonic():.3f} [scoring] no qt embeddings resolved, returning []", file=sys.stderr, flush=True)
        return []

    qt_list = list(qt_embeddings.keys())
    print(f"{_time.monotonic():.3f} [scoring] first pass: {len(all_memories)} memories × {len(qt_list)} query tags", file=sys.stderr, flush=True)

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

    print(f"{_time.monotonic():.3f} [scoring] first pass done ({_time.monotonic()-t0:.3f}s total so far)", file=sys.stderr, flush=True)

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

    print(f"{_time.monotonic():.3f} [scoring] second pass", file=sys.stderr, flush=True)

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

    print(f"{_time.monotonic():.3f} [scoring] done: {len(scored)} hits ({_time.monotonic()-t0:.3f}s total)", file=sys.stderr, flush=True)

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored
