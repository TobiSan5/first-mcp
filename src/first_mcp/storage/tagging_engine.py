"""
Tagging engine for the v2 memory system.

The TaggingEngine is the single authority over the tag table and the
tag_memory_links junction table. No other module should write to those
tables directly.

Responsibilities:
  tag table       — creating new tags with embeddings, deduplicating candidates
                    against existing tags, managing usage counts
  junction table  — linking/unlinking tags to memories, keeping usage counts
                    consistent with actual link counts

No LLM is required. Embeddings are local (fastembed).

Write-time flow (tag_memory):
  1. Candidates are gathered from up to three sources, in priority order:
       a. client  — tags suggested by the MCP client (normalised to snake_case)
       b. suggester — an optional server-side TagSuggester (any LLM vendor or
          local model; disabled by default)
       c. content_match — existing tags whose embedding is close to the
          content itself (ADD EXISTING behaviour)
  2. Every candidate is resolved against the vec0 index: if the nearest
     existing tag is within _DEDUP_DISTANCE_THRESHOLD (default cosine ~0.85),
     the existing tag is used instead. Existing tags are always preferred over
     new ones. Only candidates with no close match are registered as new tags.
  3. The junction table is updated: old links for the memory are removed (and
     their usage counts decremented), new links are inserted (and incremented).

Query-time flow (search_memories):
  The natural language query is embedded directly by fastembed — no LLM step.
  KNN on the vec0 index finds the nearest tags; the junction table is traversed
  to collect memory IDs, which are scored by Σsim².
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .protocols import TagRecord, TagSuggester
from .sqlite_storage import SQLiteStorageStrategy
from .fast_embed_strategy import FastEmbedStrategy

# This is an L2 distance (vec0's default metric), NOT a cosine similarity.
# fastembed vectors are unit-length, so cosine = 1 − L2²/2 exactly:
# 0.55 L2 ≈ cosine 0.85. Existing tags are preferred over new ones whenever
# they're "close enough". Tunable via FIRST_MCP_TAGGING_DEDUP_THRESHOLD.
_DEDUP_DISTANCE_THRESHOLD = float(
    os.getenv("FIRST_MCP_TAGGING_DEDUP_THRESHOLD", "0.55")
)

# How many existing tags to surface from a content-level vec0 search
# (ADD EXISTING behaviour).
_CONTENT_SEARCH_TOP_K = int(os.getenv("FIRST_MCP_TAGGING_CONTENT_TOP_K", "15"))

NO_TAGS_WARNING = (
    "No tags were applied, so this memory will not be found by search. "
    "Supply tags (2-6 short snake_case topics) via first_mcp_update."
)


def _to_snake_case(tag: str) -> str:
    """Normalise any string to snake_case."""
    tag = tag.lower().strip()
    tag = re.sub(r"[\s\-]+", "_", tag)
    tag = re.sub(r"[^a-z0-9_]", "", tag)
    tag = re.sub(r"_+", "_", tag).strip("_")
    return tag


_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")


def _is_valid_tag(tag: str) -> bool:
    """Return True only for well-formed snake_case tags."""
    return bool(tag and _SNAKE_CASE_RE.match(tag))


def normalize_tags(raw: list[str] | str | None) -> tuple[list[str], list[str]]:
    """
    Normalise client- or LLM-supplied tags.

    Accepts a list of strings or a comma-separated string. Returns
    (valid_snake_case_tags_deduplicated, rejected_raw_values).
    """
    if raw is None:
        return [], []
    items = raw.split(",") if isinstance(raw, str) else list(raw)

    valid: list[str] = []
    rejected: list[str] = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            continue
        tag = _to_snake_case(item)
        if not _is_valid_tag(tag):
            rejected.append(item)
        elif tag not in valid:
            valid.append(tag)
    return valid, rejected


@dataclass
class TaggingResult:
    """Outcome of a tagging pass."""
    tags: list[str] = field(default_factory=list)
    # One entry per client/suggester candidate:
    # {"suggested", "applied", "matched_existing", "source"}
    resolution: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class TaggingEngine:
    """
    Owns the tag table and tag_memory_links junction table.

    Storage, embedder and the optional suggester are injected so the engine is
    testable in isolation.
    """

    def __init__(
        self,
        storage: SQLiteStorageStrategy,
        embedder: FastEmbedStrategy,
        suggester: TagSuggester | None = None,
    ) -> None:
        self._storage = storage
        self._embedder = embedder
        self._suggester = suggester

    @property
    def suggester_name(self) -> str | None:
        return self._suggester.name if self._suggester else None

    # ------------------------------------------------------------------
    # Public write-time API
    # ------------------------------------------------------------------

    def tag_memory(
        self,
        memory_id: str,
        content: str,
        suggested_tags: list[str] | str | None = None,
    ) -> TaggingResult:
        """
        Resolve tags for content and make the junction table reflect them.

        Handles both new memories (no existing links) and re-tagging (replaces
        all links).
        """
        old_tags = self._storage.unlink_all_tags_from_memory(memory_id)
        if old_tags:
            self._storage.decrement_tag_usage(old_tags)

        result = self._generate_and_register(content, suggested_tags)

        if result.tags:
            self._storage.link_tags_to_memory(result.tags, memory_id)
            self._storage.increment_tag_usage(result.tags)
        else:
            result.warnings.append(NO_TAGS_WARNING)

        return result

    def retag_on_update(
        self,
        memory_id: str,
        new_content: str | None,
        suggested_tags: list[str] | str | None,
    ) -> TaggingResult | None:
        """
        Decide whether an update changes a memory's tags.

        - Tags supplied → retag with them (against the new or stored content).
        - Content changed, no tags, suggester configured → regenerate.
        - Otherwise → existing tags are kept; returns None.
        """
        valid, rejected = normalize_tags(suggested_tags)
        if valid or rejected:
            content = new_content
            if not content:
                mem = self._storage.get_memory(memory_id)
                content = mem.content if mem else ""
            return self.tag_memory(memory_id, content, suggested_tags)
        if new_content and self._suggester is not None:
            return self.tag_memory(memory_id, new_content)
        return None

    def untag_memory(self, memory_id: str) -> None:
        """
        Remove all tag links for a memory and decrement usage counts.
        Call this before deleting a memory so counts stay accurate.
        """
        old_tags = self._storage.unlink_all_tags_from_memory(memory_id)
        if old_tags:
            self._storage.decrement_tag_usage(old_tags)

    # ------------------------------------------------------------------
    # Public query-time API
    # ------------------------------------------------------------------

    def search_memories(
        self,
        query: str,
        top_k_tags: int = 30,
    ) -> list[tuple[str, float, list[str]]]:
        """
        Find memories relevant to a natural language query.

        Embeds the query with fastembed, runs KNN against the vec0 tag index,
        traverses the junction table to aggregate memory IDs, and scores each
        memory by Σsim² across all matched tags.

        Returns list of (memory_id, score, matched_tags) sorted by score desc.
        """
        qvec = self._embedder.embed([query])[0]
        if qvec is None:
            return []

        tag_hits = self._storage.search_by_vector(qvec, top_k=top_k_tags)

        memory_scores: dict[str, dict] = {}
        for tag_name, distance in tag_hits:
            sim = max(0.0, 1.0 - distance)
            for memory_id in self._storage.get_memories_for_tag(tag_name):
                if memory_id not in memory_scores:
                    memory_scores[memory_id] = {"score": 0.0, "tags": []}
                memory_scores[memory_id]["score"] += sim ** 2
                memory_scores[memory_id]["tags"].append(tag_name)

        ranked = [
            (mid, data["score"], data["tags"])
            for mid, data in memory_scores.items()
        ]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    # ------------------------------------------------------------------
    # Internal: candidate gathering and registration
    # ------------------------------------------------------------------

    def _generate_and_register(
        self,
        content: str,
        suggested_tags: list[str] | str | None,
    ) -> TaggingResult:
        result = TaggingResult()
        candidates: list[tuple[str, str]] = []  # (candidate, source)

        # a. Client-suggested tags
        client_tags, rejected = normalize_tags(suggested_tags)
        if rejected:
            result.warnings.append(
                f"Ignored tags that are not valid snake_case after normalisation: {rejected}"
            )
        candidates += [(t, "client") for t in client_tags]

        # b. Optional server-side suggester — failures never block the write
        if self._suggester is not None:
            try:
                llm_tags, _ = normalize_tags(self._suggester.suggest(content))
                candidates += [(t, "suggester") for t in llm_tags
                               if t not in client_tags]
            except Exception as e:  # noqa: BLE001 — any vendor/network error
                result.warnings.append(
                    f"Tag suggester {self._suggester.name} failed ({type(e).__name__}); "
                    "used client tags only."
                )

        # c. Existing tags close to the content itself
        content_vec = self._embedder.embed([content])[0] if content.strip() else None
        if content_vec is not None:
            seen = {c for c, _ in candidates}
            hits = self._storage.search_by_vector(content_vec, top_k=_CONTENT_SEARCH_TOP_K)
            candidates += [
                (name, "content_match") for name, dist in hits
                if dist < _DEDUP_DISTANCE_THRESHOLD and _is_valid_tag(name)
                and name not in seen
            ]

        self._resolve_candidates(candidates, result)
        return result

    def _resolve_candidates(
        self,
        candidates: list[tuple[str, str]],
        result: TaggingResult,
    ) -> None:
        """
        Resolve each candidate to an existing tag or register it as new.

        Existing tags are preferred: if the nearest vec0 neighbour of a candidate
        is within _DEDUP_DISTANCE_THRESHOLD, the existing tag name is used instead.
        New tags are embedded and upserted with usage_count=0 (the caller
        increments after linking to a memory).
        """
        if not candidates:
            return

        vecs = self._embedder.embed([c for c, _ in candidates])
        for (candidate, source), vec in zip(candidates, vecs):
            if vec is None:
                continue
            nearest = self._storage.search_by_vector(vec, top_k=1)
            if nearest and nearest[0][1] < _DEDUP_DISTANCE_THRESHOLD:
                applied, matched = nearest[0][0], True
            else:
                self._storage.upsert_tag(
                    TagRecord(
                        name=candidate,
                        usage_count=0,
                        new_embedding=vec,
                        new_model=self._embedder.model_name,
                    )
                )
                applied, matched = candidate, False

            if applied not in result.tags:
                result.tags.append(applied)
            if source != "content_match":
                result.resolution.append({
                    "suggested": candidate,
                    "applied": applied,
                    "matched_existing": matched,
                    "source": source,
                })
