"""
Standalone tag enrichment runner.

Processes all unenriched memories in one batch and exits.
Designed to be called on a schedule (cron, Windows Task Scheduler) rather
than run as a background thread inside the MCP server.

Usage:
    first-mcp-enrich                  # uses FIRST_MCP_DATA_PATH from env
    first-mcp-enrich --limit 20       # cap memories per run
    first-mcp-enrich --dry-run        # report what would be enriched, no API calls
"""

import argparse
import os
import sys
from datetime import datetime


def _log(msg: str) -> None:
    print(f"{datetime.now().isoformat()} {msg}", flush=True)


def run(limit: int = 50, dry_run: bool = False) -> int:
    """
    Enrich up to `limit` unenriched memories.

    Returns the number of memories successfully enriched.
    """
    data_path = os.getenv('FIRST_MCP_DATA_PATH', '')
    if not data_path:
        _log("ERROR: FIRST_MCP_DATA_PATH is not set.")
        return 0

    from first_mcp.memory.tag_enrichment import (
        get_unenriched_memory_ids,
        enrich_single,
    )

    candidates = get_unenriched_memory_ids(limit=limit)

    if not candidates:
        _log("Nothing to enrich — all memories are up to date.")
        return 0

    _log(f"{len(candidates)} memories to enrich.")

    if dry_run:
        for mid in candidates:
            _log(f"  [dry-run] {mid}")
        return 0

    succeeded = 0
    for memory_id in candidates:
        result = enrich_single(memory_id)
        status = "ok" if result.get('success') else f"FAILED: {result.get('error')}"
        _log(f"  {memory_id[:8]}  {status}  {result}")
        if result.get('success'):
            succeeded += 1

    _log(f"Done. {succeeded}/{len(candidates)} enriched successfully.")
    return succeeded


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich memory tags using the Gemini API.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of memories to process per run (default: 50).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List memories that would be enriched without calling the API.",
    )
    args = parser.parse_args()

    succeeded = run(limit=args.limit, dry_run=args.dry_run)
    sys.exit(0 if succeeded >= 0 else 1)


if __name__ == "__main__":
    main()
