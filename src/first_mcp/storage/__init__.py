"""
Storage strategy layer for first-mcp.

Provides protocol interfaces and concrete implementations for storage and
embedding backends, enabling the strategy pattern for switching between
TinyDB, SQLite/sqlite-vec, local embedding models, and cloud AI APIs.
"""
from .protocols import EmbeddingStrategy, StorageStrategy, MemoryRecord, TagRecord
from .sqlite_storage import SQLiteStorageStrategy
from .fast_embed_strategy import FastEmbedStrategy

__all__ = [
    "EmbeddingStrategy",
    "StorageStrategy",
    "MemoryRecord",
    "TagRecord",
    "SQLiteStorageStrategy",
    "FastEmbedStrategy",
]
