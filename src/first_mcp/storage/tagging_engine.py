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

Write-time flow (tag_memory):
  1. Gemini generates snake_case compound tag candidates from memory content.
  2. The content itself is embedded and a vec0 search surfaces existing tags
     that are semantically close — these are added as candidates alongside
     Gemini's output (ADD EXISTING behaviour).
  3. Every candidate is resolved against the vec0 index: if the nearest
     existing tag is within _DEDUP_DISTANCE_THRESHOLD (default cosine ~0.85),
     the existing tag is used instead. Existing tags are always preferred over
     new ones. Only candidates with no close match are registered as new tags.
  4. The junction table is updated: old links for the memory are removed (and
     their usage counts decremented), new links are inserted (and incremented).

Query-time flow (search_memories):
  The natural language query is embedded directly by fastembed — no LLM step.
  KNN on the vec0 index finds the nearest tags; the junction table is traversed
  to collect memory IDs, which are scored by Σsim².
"""
from __future__ import annotations

import os
import pathlib
import re

from .protocols import TagRecord
from .sqlite_storage import SQLiteStorageStrategy
from .fast_embed_strategy import FastEmbedStrategy

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"
_TAGGING_MODEL = os.getenv("FIRST_MCP_TAGGING_MODEL", "gemini-2.5-flash")

# L2 distance on normalised vectors ≈ sqrt(2*(1−cosine_sim)).
# 0.55 ≈ cosine similarity ~0.85 — existing tags are preferred over new ones
# whenever they're "close enough". Matches the enrichment agent's replacement
# threshold. Tunable via FIRST_MCP_TAGGING_DEDUP_THRESHOLD.
_DEDUP_DISTANCE_THRESHOLD = float(
    os.getenv("FIRST_MCP_TAGGING_DEDUP_THRESHOLD", "0.55")
)

# How many existing tags to surface from a content-level vec0 search and pass
# to _resolve_candidates alongside Gemini's output (ADD EXISTING behaviour).
_CONTENT_SEARCH_TOP_K = int(os.getenv("FIRST_MCP_TAGGING_CONTENT_TOP_K", "15"))


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


class TaggingEngine:
    """
    Owns the tag table and tag_memory_links junction table.

    Both storage and embedder are injected so the engine is testable in
    isolation. The Gemini client is created lazily on first use.
    """

    def __init__(
        self,
        storage: SQLiteStorageStrategy,
        embedder: FastEmbedStrategy,
    ) -> None:
        self._storage = storage
        self._embedder = embedder
        self._client = None  # google.genai.Client, lazy

    # ------------------------------------------------------------------
    # Public write-time API
    # ------------------------------------------------------------------

    def tag_memory(self, memory_id: str, content: str) -> list[str]:
        """
        Generate tags for content and make the junction table reflect them.

        Handles both new memories (no existing links) and re-tagging after
        a content update (replaces all links). Returns the applied tag names.
        """
        # Remove any existing links and adjust usage counts
        old_tags = self._storage.unlink_all_tags_from_memory(memory_id)
        if old_tags:
            self._storage.decrement_tag_usage(old_tags)

        # Generate, deduplicate, and register new tags
        new_tags = self._generate_and_register(content)

        # Link to memory and increment usage
        if new_tags:
            self._storage.link_tags_to_memory(new_tags, memory_id)
            self._storage.increment_tag_usage(new_tags)

        return new_tags

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
    # Internal: tag generation and registration
    # ------------------------------------------------------------------

    def _generate_and_register(self, content: str) -> list[str]:
        """
        Produce the final tag list for a piece of content.

        Two sources feed into _resolve_candidates:
          1. Gemini's suggested tags (LLM generation)
          2. Top existing tags from a content-level vec0 search (ADD EXISTING)

        _resolve_candidates maps every candidate to an existing tag when one
        is within _DEDUP_DISTANCE_THRESHOLD; otherwise it registers the
        candidate as a new tag. Existing tags are always preferred over new ones.
        """
        llm_candidates = self._llm_generate(content)

        # Content-level vec0 search: find existing tags already close to this
        # content so they can be included even if Gemini didn't suggest them.
        content_vec = self._embedder.embed([content])[0]
        existing_hits: list[str] = []
        if content_vec is not None:
            hits = self._storage.search_by_vector(content_vec, top_k=_CONTENT_SEARCH_TOP_K)
            existing_hits = [
                name for name, dist in hits
                if dist < _DEDUP_DISTANCE_THRESHOLD and _is_valid_tag(name)
            ]

        # Merge: LLM candidates first (they carry semantic intent), then any
        # existing tags surfaced by the content search not already covered.
        all_candidates = llm_candidates + [t for t in existing_hits if t not in llm_candidates]

        return self._resolve_candidates(all_candidates)

    def _resolve_candidates(self, candidates: list[str]) -> list[str]:
        """
        For each candidate string, resolve to an existing tag or register a new one.

        Existing tags are preferred: if the nearest vec0 neighbour of a candidate
        is within _DEDUP_DISTANCE_THRESHOLD, the existing tag name is used instead.
        Truly new tags are embedded and upserted with usage_count=0 (the caller
        increments after linking to a memory).
        """
        if not candidates:
            return []

        vecs = self._embedder.embed(candidates)
        final_tags: list[str] = []

        for candidate, vec in zip(candidates, vecs):
            if vec is None:
                continue
            nearest = self._storage.search_by_vector(vec, top_k=1)
            if nearest and nearest[0][1] < _DEDUP_DISTANCE_THRESHOLD:
                final_tags.append(nearest[0][0])  # prefer existing tag
            else:
                self._storage.upsert_tag(
                    TagRecord(
                        name=candidate,
                        usage_count=0,
                        new_embedding=vec,
                        new_model=self._embedder.model_name,
                    )
                )
                final_tags.append(candidate)

        # Deduplicate while preserving order
        seen: set[str] = set()
        return [t for t in final_tags if not (t in seen or seen.add(t))]  # type: ignore[func-returns-value]

    def _llm_generate(self, content: str) -> list[str]:
        """Call Gemini with structured output to get snake_case tag candidates."""
        from pydantic import BaseModel
        import importlib

        genai = importlib.import_module("google.genai")
        genai_types = importlib.import_module("google.genai.types")

        class _TagList(BaseModel):
            tags: list[str]

        prompt_template = (_PROMPTS_DIR / "tag_generation.md").read_text(encoding="utf-8")
        prompt = prompt_template.format(content=content[:600])

        client = self._get_client()
        response = client.models.generate_content(
            model=_TAGGING_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_TagList,
            ),
        )
        result = _TagList.model_validate_json(response.text)
        return [_to_snake_case(t) for t in result.tags if t.strip()]

    def _get_client(self):
        if self._client is None:
            genai = __import__("google.genai", fromlist=["Client"])
            self._client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        return self._client
