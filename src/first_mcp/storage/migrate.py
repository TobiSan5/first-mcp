"""
TinyDB → SQLite migration for first-mcp memory data.

Reads tinydb_memories.json and tinydb_tags.json from a data directory and
writes first_mcp_memory.db in the same directory using SQLiteStorageStrategy.

Source files are never modified. The destination file is created fresh; an
existing first_mcp_memory.db will be backed up before being overwritten.

Usage
-----
    first-mcp-migrate                    # uses FIRST_MCP_DATA_PATH env var
    first-mcp-migrate /path/to/data/dir  # explicit path argument
    python -m first_mcp.storage.migrate  # same, module form
"""
from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from tinydb import TinyDB
from tinydb.middlewares import CachingMiddleware
from tinydb.storages import JSONStorage

from .protocols import MemoryRecord, TagRecord
from .sqlite_storage import SQLiteStorageStrategy

DB_FILENAME = "first_mcp_memory.db"


# ---------------------------------------------------------------------------
# TinyDB readers
# ---------------------------------------------------------------------------

def _read_table(json_path: Path, table_name: str) -> list[dict]:
    """Return all records from a named TinyDB table, or [] if the file is absent."""
    if not json_path.exists():
        return []
    db = TinyDB(str(json_path), storage=CachingMiddleware(JSONStorage))
    try:
        return [dict(r) for r in db.table(table_name).all()]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def migrate(data_dir: Path, db_path: Path) -> None:
    print(f"Source:      {data_dir}")
    print(f"Destination: {db_path}")

    # Back up an existing destination file rather than silently overwriting it.
    if db_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db_path.with_name(f"{db_path.stem}_backup_{ts}.db")
        shutil.move(str(db_path), str(backup))
        print(f"Existing DB backed up → {backup.name}")

    print()

    # --- Load TinyDB records ---
    print("Reading TinyDB tags...", end="  ", flush=True)
    raw_tags = _read_table(data_dir / "tinydb_tags.json", "tags")
    print(f"{len(raw_tags)} records")

    print("Reading TinyDB memories...", end="  ", flush=True)
    raw_memories = _read_table(data_dir / "tinydb_memories.json", "memories")
    print(f"{len(raw_memories)} records")
    print()

    storage = SQLiteStorageStrategy(db_path)

    # --- Migrate tags ---
    print("Migrating tags...")
    tags_ok = 0
    tags_with_embedding = 0
    tags_skipped = 0
    known_tag_names: set[str] = set()

    for raw in raw_tags:
        name = (raw.get("tag") or "").strip()
        if not name:
            tags_skipped += 1
            continue

        embedding_list = raw.get("embedding") or []
        if embedding_list:
            old_embedding: np.ndarray | None = np.array(embedding_list, dtype=np.float32)
            old_model: str | None = raw.get("embedding_model", "gemini-embedding-001")
            tags_with_embedding += 1
        else:
            old_embedding = None
            old_model = None

        storage.upsert_tag(TagRecord(
            name=name,
            usage_count=raw.get("usage_count", 1),
            old_embedding=old_embedding,
            old_model=old_model,
        ))
        known_tag_names.add(name)
        tags_ok += 1

    print(f"  Tags migrated:            {tags_ok}")
    print(f"  With old_embedding:       {tags_with_embedding}")
    print(f"  Without embedding (NULL): {tags_ok - tags_with_embedding}")
    if tags_skipped:
        print(f"  Skipped (empty name):     {tags_skipped}")

    # --- Migrate memories ---
    print("\nMigrating memories...")
    memories_ok = 0
    memories_skipped = 0
    links_total = 0
    orphan_tag_names: set[str] = set()

    for raw in raw_memories:
        memory_id = (raw.get("id") or "").strip()
        content = (raw.get("content") or "").strip()
        if not memory_id or not content:
            memories_skipped += 1
            continue

        tags: list[str] = [t.strip() for t in (raw.get("tags") or []) if t.strip()]
        category = raw.get("category") or None

        storage.store_memory(MemoryRecord(
            id=memory_id,
            content=content,
            category=category,
            importance=raw.get("importance", 3),
            timestamp=raw.get("timestamp") or "",
            last_modified=raw.get("last_modified") or raw.get("timestamp") or "",
        ))

        if tags:
            storage.link_tags_to_memory(tags, memory_id)
            links_total += len(tags)
            for t in tags:
                if t not in known_tag_names:
                    orphan_tag_names.add(t)

        memories_ok += 1

    print(f"  Memories migrated:        {memories_ok}")
    print(f"  Tag-memory links:         {links_total}")
    if orphan_tag_names:
        print(f"  Orphan tag stubs:         {len(orphan_tag_names)}"
              " (referenced in memories but absent from tags DB)")
    if memories_skipped:
        print(f"  Skipped (missing id/content): {memories_skipped}")

    storage.close()

    # --- Summary ---
    size_kb = db_path.stat().st_size // 1024
    print(f"\nDone.  {db_path.name}  ({size_kb} KB)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) > 1:
        data_dir = Path(sys.argv[1])
    else:
        env = os.getenv("FIRST_MCP_DATA_PATH", "")
        if not env:
            print(
                "Error: provide a data directory path as an argument "
                "or set FIRST_MCP_DATA_PATH.",
                file=sys.stderr,
            )
            sys.exit(1)
        data_dir = Path(env)

    if not data_dir.is_dir():
        print(f"Error: '{data_dir}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    migrate(data_dir, data_dir / DB_FILENAME)


if __name__ == "__main__":
    main()
