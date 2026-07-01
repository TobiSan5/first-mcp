"""
Tagging engine for the v2 memory system.

Write-time: calls Gemini to generate snake_case tag candidates, then deduplicates
each candidate against the existing vec0 index. Truly new tags are embedded with
fastembed and registered immediately. Existing close-enough tags are reused by name.

Query-time: embeds the natural language query with fastembed, runs KNN against the
vec0 index, traverses the junction table to collect memory IDs, and scores memories
by sum-of-squares tag similarity.
"""
from __future__ import annotations

import os
import pathlib
import re
from typing import TYPE_CHECKING

import numpy as np

from .protocols import TagRecord
from .sqlite_storage import SQLiteStorageStrategy
from .fast_embed_strategy import FastEmbedStrategy

if TYPE_CHECKING:
    pass

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"
_TAGGING_MODEL = os.getenv("FIRST_MCP_TAGGING_MODEL", "gemini-2.5-flash")

# Distance below which a generated tag is considered a duplicate of an existing one.
# vec0 returns L2 distance on normalised vectors ≈ sqrt(2*(1-cosine_sim)).
# 0.25 ≈ cosine similarity of ~0.97 — very close synonyms/variants only.
_DEDUP_DISTANCE_THRESHOLD = 0.25


def _to_snake_case(tag: str) -> str:
    """Normalise any string to snake_case."""
    tag = tag.lower().strip()
    tag = re.sub(r"[\s\-]+", "_", tag)
    tag = re.sub(r"[^a-z0-9_]", "", tag)
    tag = re.sub(r"_+", "_", tag).strip("_")
    return tag


class TaggingEngine:
    """
    Coordinates Gemini (tag generation) and fastembed (embedding + dedup + search).

    Both storage and embedder are injected so the engine is testable in isolation.
    The Gemini client is created lazily on first use.
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
    # Write-time: tag generation
    # ------------------------------------------------------------------

    def generate_tags(self, content: str) -> list[str]:
        """
        Generate and register tags for new memory content.

        1. Gemini produces snake_case candidates from the content.
        2. Each candidate is embedded; if a near-identical tag already exists
           in the vec0 index (distance < threshold) the existing name is used.
        3. Truly new tags are upserted with their embeddings.
        4. Usage counts are incremented for all final tags.
        """
        candidates = self._llm_generate(content)
        if not candidates:
            return []

        vecs = self._embedder.embed(candidates)

        final_tags: list[str] = []
        new_tag_records: list[TagRecord] = []

        for candidate, vec in zip(candidates, vecs):
            if vec is None:
                continue
            nearest = self._storage.search_by_vector(vec, top_k=1)
            if nearest and nearest[0][1] < _DEDUP_DISTANCE_THRESHOLD:
                final_tags.append(nearest[0][0])  # reuse existing tag name
            else:
                new_tag_records.append(
                    TagRecord(
                        name=candidate,
                        usage_count=0,
                        new_embedding=vec,
                        new_model=self._embedder.model_name,
                    )
                )
                final_tags.append(candidate)

        # Register new tags before incrementing so the rows exist
        for record in new_tag_records:
            self._storage.upsert_tag(record)

        # Deduplicate while preserving order
        seen: set[str] = set()
        deduped = [t for t in final_tags if not (t in seen or seen.add(t))]  # type: ignore[func-returns-value]

        self._storage.increment_tag_usage(deduped)
        return deduped

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
            api_key = os.environ["GOOGLE_API_KEY"]
            self._client = genai.Client(api_key=api_key)
        return self._client

    # ------------------------------------------------------------------
    # Query-time: semantic memory search
    # ------------------------------------------------------------------

    def search_memories(
        self,
        query: str,
        top_k_tags: int = 30,
    ) -> list[tuple[str, float, list[str]]]:
        """
        Find memories relevant to a natural language query.

        Embeds the query, runs KNN against the vec0 tag index, then traverses
        the junction table to aggregate memory IDs scored by Σsim².

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
