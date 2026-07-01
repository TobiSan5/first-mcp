"""
Strategy protocols for storage and embedding backends.

EmbeddingStrategy — generates float32 vectors from text.
StorageStrategy   — persists and retrieves memories and tags.

Concrete implementations satisfy these protocols without inheriting from them;
use isinstance(obj, EmbeddingStrategy) at runtime to verify (runtime_checkable).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np


# ---------------------------------------------------------------------------
# Data records
# ---------------------------------------------------------------------------

@dataclass
class MemoryRecord:
    """A single stored memory."""
    id: str
    content: str
    category: str | None = None
    importance: int = 3
    timestamp: str = ""
    last_modified: str = ""
    # Populated on read via the junction table; not stored in the memories table.
    tags: list[str] = field(default_factory=list)


@dataclass
class TagRecord:
    """A tag with optional embedding vectors from two generations of models."""
    name: str
    usage_count: int = 0
    # Migrated from TinyDB (Google AI gemini-embedding-001, 3072-dim float32).
    old_embedding: np.ndarray | None = None
    old_model: str | None = None
    # Populated post-migration by the local fastembed model (384-dim float32).
    new_embedding: np.ndarray | None = None
    new_model: str | None = None


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------

@runtime_checkable
class EmbeddingStrategy(Protocol):
    """Generates embedding vectors from text strings."""

    @property
    def model_name(self) -> str:
        """Identifier for the underlying model, e.g. 'BAAI/bge-small-en-v1.5'."""
        ...

    @property
    def dimensions(self) -> int:
        """Output vector dimensionality."""
        ...

    def embed(self, texts: list[str]) -> list[np.ndarray | None]:
        """
        Embed a batch of texts. Returns one float32 array per text, or None
        for any text whose embedding could not be generated.
        """
        ...


@runtime_checkable
class StorageStrategy(Protocol):
    """Persists and retrieves memories and tags."""

    # --- Memory CRUD ---

    def store_memory(self, memory: MemoryRecord) -> str:
        """Insert a new memory. Returns the memory's id."""
        ...

    def get_memory(self, memory_id: str) -> MemoryRecord | None:
        """Fetch a single memory by id, with tags populated from the junction table."""
        ...

    def update_memory(self, memory_id: str, updates: dict) -> bool:
        """Apply field updates to an existing memory. Returns True if the record existed."""
        ...

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory and its junction-table rows. Returns True if the record existed."""
        ...

    def list_memories(
        self,
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        """List memories ordered by last_modified descending, with optional category filter."""
        ...

    # --- Tag CRUD ---

    def upsert_tag(self, tag: TagRecord) -> None:
        """Insert or update a tag record, keeping the integer id stable for vec0 alignment."""
        ...

    def get_tag(self, name: str) -> TagRecord | None:
        """Fetch a single tag by name."""
        ...

    def all_tags(self) -> list[TagRecord]:
        """Return all tag records ordered by usage_count descending."""
        ...

    # --- Junction table ---

    def link_tags_to_memory(self, tag_names: list[str], memory_id: str) -> None:
        """
        Create tag ↔ memory links. Tags absent from the tags table are inserted
        as minimal stubs so referential integrity is preserved.
        """
        ...

    def get_tags_for_memory(self, memory_id: str) -> list[str]:
        """Return the tag names linked to a memory."""
        ...

    def get_memories_for_tag(self, tag_name: str) -> list[str]:
        """Return the memory ids linked to a tag."""
        ...

    # --- Search ---

    def search_by_vector(
        self, query_vec: np.ndarray, top_k: int = 10
    ) -> list[tuple[str, float]]:
        """
        Find the top_k nearest tags to query_vec by cosine distance.
        Returns (tag_name, distance) pairs, distance=0 is identical.

        Uses the new_embedding vec0 index (384-dim) when populated.
        Falls back to numpy cosine on old_embedding (3072-dim) when the new
        index is empty and the query vector has matching dimensions.
        Returns [] when no compatible index is available.
        """
        ...

    # --- Lifecycle ---

    def close(self) -> None:
        """Release any held resources (connections, file handles)."""
        ...
