"""
Re-embedding pass: populate new_embedding on all tag records in the SQLite DB.

Entry point: first-mcp-reembed

Reads FIRST_MCP_DATA_PATH from the environment to locate first_mcp_memory.db,
loads every tag, embeds tag names in batches using FastEmbedStrategy, and
writes new_embedding + new_model back via SQLiteStorageStrategy.upsert_tag.

Tags that already have new_embedding set are skipped unless --force is passed.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .fast_embed_strategy import FastEmbedStrategy, _MODEL_NAME
from .sqlite_storage import SQLiteStorageStrategy


_BATCH_SIZE = 256


def reembed(db_path: Path, force: bool = False) -> None:
    storage = SQLiteStorageStrategy(db_path)
    embedder = FastEmbedStrategy()

    all_tags = storage.all_tags()
    candidates = [t for t in all_tags if force or t.new_embedding is None]

    total = len(all_tags)
    todo = len(candidates)
    print(f"Tags total: {total}  |  to embed: {todo}  |  already done: {total - todo}")

    if not candidates:
        print("Nothing to do.")
        storage.close()
        return

    # Trigger model download before the progress loop
    print(f"Loading model {_MODEL_NAME} …")
    embedder._get_model()
    print("Model ready.\n")

    done = 0
    for batch_start in range(0, todo, _BATCH_SIZE):
        batch = candidates[batch_start : batch_start + _BATCH_SIZE]
        names = [t.name for t in batch]
        vecs = embedder.embed(names)

        for tag, vec in zip(batch, vecs):
            tag.new_embedding = vec
            tag.new_model = _MODEL_NAME if vec is not None else None
            storage.upsert_tag(tag)

        done += len(batch)
        pct = done / todo * 100
        print(f"  {done}/{todo}  ({pct:.1f}%)", end="\r", flush=True)

    print(f"\nDone. {done} tags embedded with {_MODEL_NAME}.")
    storage.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate new_embedding on all tags in the SQLite memory database."
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to first_mcp_memory.db. Defaults to $FIRST_MCP_DATA_PATH/first_mcp_memory.db.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed tags that already have new_embedding set.",
    )
    args = parser.parse_args()

    if args.db:
        db_path = Path(args.db)
    else:
        data_path = os.environ.get("FIRST_MCP_DATA_PATH")
        if not data_path:
            print("Error: FIRST_MCP_DATA_PATH is not set. Pass --db or set the env var.")
            sys.exit(1)
        db_path = Path(data_path) / "first_mcp_memory.db"

    if not db_path.exists():
        print(f"Error: database not found at {db_path}")
        sys.exit(1)

    print(f"Database: {db_path}")
    reembed(db_path, force=args.force)


if __name__ == "__main__":
    main()
