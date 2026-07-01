"""
First MCP Memory Server — v2

Exposes only memory tools, wired to the SQLite/sqlite-vec/fastembed backend.
All tool names are prefixed with first_mcp_ to reduce Claude Desktop confusion
when multiple MCP servers are active.

Entry point: first-mcp-memory
Run alongside the main server for parallel testing during migration.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastmcp import FastMCP

from .storage.protocols import MemoryRecord
from .storage.sqlite_storage import SQLiteStorageStrategy
from .storage.fast_embed_strategy import FastEmbedStrategy
from .storage.tagging_engine import TaggingEngine


# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

_storage_instance: SQLiteStorageStrategy | None = None
_embedder_instance: FastEmbedStrategy | None = None
_engine_instance: TaggingEngine | None = None


def _get_storage() -> SQLiteStorageStrategy:
    global _storage_instance
    if _storage_instance is None:
        data_path = os.environ.get("FIRST_MCP_DATA_PATH", ".")
        _storage_instance = SQLiteStorageStrategy(Path(data_path) / "first_mcp_memory.db")
    return _storage_instance


def _get_embedder() -> FastEmbedStrategy:
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = FastEmbedStrategy()
    return _embedder_instance


def _get_engine() -> TaggingEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = TaggingEngine(_get_storage(), _get_embedder())
    return _engine_instance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat()


def _ts(response: Dict[str, Any]) -> Dict[str, Any]:
    """Add server_timestamp to any response dict."""
    import time
    response["server_timestamp"] = _now()
    try:
        response["server_timezone"] = time.tzname[time.daylight]
    except (AttributeError, IndexError):
        response["server_timezone"] = "local"
    return response


def _memory_dict(mem: MemoryRecord) -> Dict[str, Any]:
    return {
        "id": mem.id,
        "content": mem.content,
        "category": mem.category,
        "importance": mem.importance,
        "tags": mem.tags,
        "timestamp": mem.timestamp,
        "last_modified": mem.last_modified,
    }


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(name="First MCP Memory Server")


@mcp.tool()
def first_mcp_memorize(
    content: str,
    category: str = "",
    importance: int = 3,
) -> Dict[str, Any]:
    """
    Store a memory with automatic tag generation.

    Args:
        content: The memory content to store.
        category: Optional category label (e.g. 'project', 'personal').
        importance: Priority 1–5, default 3.
    """
    tags = _get_engine().generate_tags(content)
    memory_id = str(uuid.uuid4())
    now = _now()
    memory = MemoryRecord(
        id=memory_id,
        content=content,
        category=category or None,
        importance=importance,
        timestamp=now,
        last_modified=now,
        tags=tags,
    )
    _get_storage().store_memory(memory)
    return _ts({"success": True, "memory_id": memory_id, "tags": tags})


@mcp.tool()
def first_mcp_search(query: str, limit: int = 10) -> Dict[str, Any]:
    """
    Search memories by natural language query using semantic tag matching.

    Args:
        query: Natural language description of what you're looking for.
        limit: Maximum number of results to return (default 10).
    """
    ranked = _get_engine().search_memories(query, top_k_tags=40)[:limit]

    memories = []
    for memory_id, score, matched_tags in ranked:
        mem = _get_storage().get_memory(memory_id)
        if mem:
            d = _memory_dict(mem)
            d["score"] = round(score, 4)
            d["matched_tags"] = matched_tags
            memories.append(d)

    return _ts({"success": True, "query": query, "count": len(memories), "memories": memories})


@mcp.tool()
def first_mcp_list(
    category: str = "",
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    List memories, newest first, with optional category filter.

    Args:
        category: Filter to a specific category (omit for all).
        limit: Page size (default 20).
        offset: Pagination offset (default 0).
    """
    memories = _get_storage().list_memories(
        category=category or None,
        limit=limit,
        offset=offset,
    )
    items = []
    for m in memories:
        d = _memory_dict(m)
        d["content"] = m.content[:200]  # truncated for list view
        items.append(d)

    return _ts({"success": True, "count": len(items), "offset": offset, "memories": items})


@mcp.tool()
def first_mcp_recall(memory_id: str) -> Dict[str, Any]:
    """
    Retrieve a single memory by its ID.

    Args:
        memory_id: The UUID of the memory to retrieve.
    """
    mem = _get_storage().get_memory(memory_id)
    if mem is None:
        return _ts({"success": False, "error": f"Memory '{memory_id}' not found"})
    return _ts({"success": True, "memory": _memory_dict(mem)})


@mcp.tool()
def first_mcp_update(
    memory_id: str,
    content: str = "",
    category: str = "",
    importance: int = 0,
) -> Dict[str, Any]:
    """
    Update one or more fields of an existing memory.

    Args:
        memory_id: The UUID of the memory to update.
        content: New content (omit to leave unchanged).
        category: New category (omit to leave unchanged).
        importance: New importance 1–5 (omit or 0 to leave unchanged).
    """
    updates: Dict[str, Any] = {"last_modified": _now()}
    if content:
        updates["content"] = content
    if category:
        updates["category"] = category
    if importance:
        updates["importance"] = importance

    if len(updates) == 1:
        return _ts({"success": False, "error": "No fields provided to update"})

    ok = _get_storage().update_memory(memory_id, updates)
    if not ok:
        return _ts({"success": False, "error": f"Memory '{memory_id}' not found"})

    return _ts({"success": True, "memory_id": memory_id, "updated_fields": list(updates.keys())})


@mcp.tool()
def first_mcp_forget(memory_id: str) -> Dict[str, Any]:
    """
    Permanently delete a memory.

    Args:
        memory_id: The UUID of the memory to delete.
    """
    ok = _get_storage().delete_memory(memory_id)
    if not ok:
        return _ts({"success": False, "error": f"Memory '{memory_id}' not found"})
    return _ts({"success": True, "memory_id": memory_id})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
