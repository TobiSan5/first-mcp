"""
SQLite + sqlite-vec implementation of StorageStrategy.

Schema
------
  memories          — memory records (no embeddings; tags live in the junction table)
  tags              — tag records with old_embedding / new_embedding BLOBs
  tag_memory_links  — many-to-many junction between tags and memories
  tag_new_vecs      — vec0 virtual table for KNN search on new_embedding (384-dim)

Embeddings are stored as raw float32 bytes (numpy .tobytes() / frombuffer).
The vec0 rowid matches tags.id so a single JOIN resolves vector hits to names.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import numpy as np
import sqlite_vec

from .protocols import MemoryRecord, TagRecord


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id            TEXT PRIMARY KEY,
    content       TEXT NOT NULL,
    category      TEXT,
    importance    INTEGER DEFAULT 3,
    timestamp     TEXT,
    last_modified TEXT
);

CREATE TABLE IF NOT EXISTS tags (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT UNIQUE NOT NULL,
    usage_count   INTEGER DEFAULT 0,
    old_embedding BLOB,
    old_model     TEXT,
    new_embedding BLOB,
    new_model     TEXT
);

CREATE TABLE IF NOT EXISTS tag_memory_links (
    tag_name  TEXT NOT NULL REFERENCES tags(name),
    memory_id TEXT NOT NULL REFERENCES memories(id),
    PRIMARY KEY (tag_name, memory_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS tag_new_vecs USING vec0(
    embedding float[384]
);
"""

_NEW_EMBEDDING_DIMS = 384
_OLD_EMBEDDING_DIMS = 3072


# ---------------------------------------------------------------------------
# Blob helpers
# ---------------------------------------------------------------------------

def _to_blob(arr: np.ndarray | None) -> bytes | None:
    return arr.astype(np.float32).tobytes() if arr is not None else None


def _from_blob(blob: bytes | None) -> np.ndarray | None:
    return np.frombuffer(blob, dtype=np.float32).copy() if blob else None


# ---------------------------------------------------------------------------
# Row → record converters
# ---------------------------------------------------------------------------

def _row_to_memory(row: dict, tags: list[str] | None = None) -> MemoryRecord:
    return MemoryRecord(
        id=row["id"],
        content=row["content"],
        category=row.get("category"),
        importance=row.get("importance", 3),
        timestamp=row.get("timestamp") or "",
        last_modified=row.get("last_modified") or "",
        tags=tags or [],
    )


def _row_to_tag(row: dict) -> TagRecord:
    return TagRecord(
        name=row["name"],
        usage_count=row.get("usage_count", 0),
        old_embedding=_from_blob(row.get("old_embedding")),
        old_model=row.get("old_model"),
        new_embedding=_from_blob(row.get("new_embedding")),
        new_model=row.get("new_model"),
    )


# ---------------------------------------------------------------------------
# Strategy implementation
# ---------------------------------------------------------------------------

class SQLiteStorageStrategy:
    """
    StorageStrategy backed by SQLite + sqlite-vec.

    One connection is held for the lifetime of the instance.
    All public methods are thread-safe via an internal lock.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._conn = self._open_connection()
        self._apply_schema()

    # --- Connection setup ---

    def _open_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _apply_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # --- Internal helpers ---

    def _tags_for_memory(self, memory_id: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT tag_name FROM tag_memory_links WHERE memory_id = ? ORDER BY tag_name",
            (memory_id,),
        ).fetchall()
        return [r["tag_name"] for r in rows]

    # --- Memory CRUD ---

    def store_memory(self, memory: MemoryRecord) -> str:
        with self._lock:
            self._conn.execute(
                """INSERT INTO memories(id, content, category, importance, timestamp, last_modified)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    memory.id, memory.content, memory.category,
                    memory.importance, memory.timestamp, memory.last_modified,
                ),
            )
            self._conn.commit()
        if memory.tags:
            self.link_tags_to_memory(memory.tags, memory.id)
        return memory.id

    def get_memory(self, memory_id: str) -> MemoryRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()
            if row is None:
                return None
            tags = self._tags_for_memory(memory_id)
        return _row_to_memory(dict(row), tags)

    def update_memory(self, memory_id: str, updates: dict) -> bool:
        allowed = {"content", "category", "importance", "timestamp", "last_modified"}
        fields = {k: v for k, v in updates.items() if k in allowed}
        if not fields:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE memories SET {set_clause} WHERE id = ?",
                (*fields.values(), memory_id),
            )
            self._conn.commit()
        return cur.rowcount > 0

    def delete_memory(self, memory_id: str) -> bool:
        with self._lock:
            self._conn.execute(
                "DELETE FROM tag_memory_links WHERE memory_id = ?", (memory_id,)
            )
            cur = self._conn.execute(
                "DELETE FROM memories WHERE id = ?", (memory_id,)
            )
            self._conn.commit()
        return cur.rowcount > 0

    def list_memories(
        self,
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        with self._lock:
            if category:
                rows = self._conn.execute(
                    """SELECT * FROM memories WHERE category = ?
                       ORDER BY last_modified DESC LIMIT ? OFFSET ?""",
                    (category, limit, offset),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM memories ORDER BY last_modified DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        return [
            _row_to_memory(dict(r), self._tags_for_memory(r["id"])) for r in rows
        ]

    # --- Tag CRUD ---

    def upsert_tag(self, tag: TagRecord) -> None:
        """
        Insert or update a tag. Uses ON CONFLICT DO UPDATE to preserve the
        integer id (and thus the vec0 rowid alignment) across updates.
        """
        old_blob = _to_blob(tag.old_embedding)
        new_blob = _to_blob(tag.new_embedding)
        with self._lock:
            self._conn.execute(
                """INSERT INTO tags(name, usage_count, old_embedding, old_model, new_embedding, new_model)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                       usage_count   = excluded.usage_count,
                       old_embedding = excluded.old_embedding,
                       old_model     = excluded.old_model,
                       new_embedding = excluded.new_embedding,
                       new_model     = excluded.new_model""",
                (tag.name, tag.usage_count, old_blob, tag.old_model, new_blob, tag.new_model),
            )
            if new_blob is not None:
                tag_id = self._conn.execute(
                    "SELECT id FROM tags WHERE name = ?", (tag.name,)
                ).fetchone()["id"]
                # Replace the vec0 entry (DELETE + INSERT to stay safe with v0.1.x)
                self._conn.execute(
                    "DELETE FROM tag_new_vecs WHERE rowid = ?", (tag_id,)
                )
                self._conn.execute(
                    "INSERT INTO tag_new_vecs(rowid, embedding) VALUES (?, ?)",
                    (tag_id, new_blob),
                )
            self._conn.commit()

    def get_tag(self, name: str) -> TagRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM tags WHERE name = ?", (name,)
            ).fetchone()
        return _row_to_tag(dict(row)) if row else None

    def all_tags(self) -> list[TagRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM tags ORDER BY usage_count DESC"
            ).fetchall()
        return [_row_to_tag(dict(r)) for r in rows]

    # --- Junction table ---

    def link_tags_to_memory(self, tag_names: list[str], memory_id: str) -> None:
        with self._lock:
            for name in tag_names:
                self._conn.execute(
                    "INSERT OR IGNORE INTO tags(name) VALUES (?)", (name,)
                )
                self._conn.execute(
                    "INSERT OR IGNORE INTO tag_memory_links(tag_name, memory_id) VALUES (?, ?)",
                    (name, memory_id),
                )
            self._conn.commit()

    def get_tags_for_memory(self, memory_id: str) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT tag_name FROM tag_memory_links WHERE memory_id = ? ORDER BY tag_name",
                (memory_id,),
            ).fetchall()
        return [r["tag_name"] for r in rows]

    def get_memories_for_tag(self, tag_name: str) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT memory_id FROM tag_memory_links WHERE tag_name = ?",
                (tag_name,),
            ).fetchall()
        return [r["memory_id"] for r in rows]

    # --- Search ---

    def search_by_vector(
        self, query_vec: np.ndarray, top_k: int = 10
    ) -> list[tuple[str, float]]:
        """
        KNN tag search. Two-phase fallback:
        1. vec0 KNN on new_embedding (384-dim) — fast, index-backed.
        2. numpy cosine on old_embedding (3072-dim) — only when query_vec
           has matching dimensions and the new index is empty.
        """
        qdim = query_vec.shape[0]
        query_blob = query_vec.astype(np.float32).tobytes()

        # Phase 1: vec0 KNN (new_embedding, 384-dim)
        if qdim == _NEW_EMBEDDING_DIMS:
            with self._lock:
                rows = self._conn.execute(
                    """SELECT v.rowid, v.distance, t.name
                       FROM tag_new_vecs v
                       JOIN tags t ON t.id = v.rowid
                       WHERE v.embedding MATCH ? AND k = ?
                       ORDER BY v.distance""",
                    (query_blob, top_k),
                ).fetchall()
            if rows:
                return [(r["name"], r["distance"]) for r in rows]

        # Phase 2: numpy cosine on old_embedding (transition period fallback)
        if qdim != _OLD_EMBEDDING_DIMS:
            return []  # dimension mismatch — no compatible index available

        with self._lock:
            tag_rows = self._conn.execute(
                "SELECT name, old_embedding FROM tags WHERE old_embedding IS NOT NULL"
            ).fetchall()

        if not tag_rows:
            return []

        qv = query_vec.astype(np.float32)
        qnorm = np.linalg.norm(qv)
        if qnorm == 0:
            return []

        scored: list[tuple[str, float]] = []
        for row in tag_rows:
            tv = _from_blob(row["old_embedding"])
            if tv is None:
                continue
            tnorm = np.linalg.norm(tv)
            if tnorm == 0:
                continue
            sim = float(np.dot(qv, tv) / (qnorm * tnorm))
            scored.append((row["name"], 1.0 - sim))  # distance = 1 − similarity

        scored.sort(key=lambda x: x[1])
        return scored[:top_k]

    # --- Lifecycle ---

    def close(self) -> None:
        with self._lock:
            self._conn.close()
