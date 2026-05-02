"""
Minimal FastMCP test server — step 2: full imports, one tool.

Used for incremental diagnosis: start bare, add features one by one
until Claude Desktop / Claude Code can no longer attach.

Entry point: first-mcp-test
"""

import os
import sys
from typing import List, Dict, Any

from fastmcp import FastMCP

from .weather import WeatherAPI, GeocodingAPI
from .fileio import WorkspaceManager
from .calculate import Calculator, TimedeltaCalculator
from .embeddings import (
    compute_text_similarity as _compute_text_similarity,
    rank_texts_by_similarity as _rank_texts_by_similarity,
)
from .memory import (
    tinydb_memorize as _tinydb_memorize,
    tinydb_recall_memory as _tinydb_recall_memory,
    tinydb_search_memories as _tinydb_search_memories,
    tinydb_list_memories as _tinydb_list_memories,
    get_next_page,
    cleanup_paginated_files,
)

mcp = FastMCP(name="First MCP Test Server")

workspace_manager = WorkspaceManager()
calculator = Calculator()
timedelta_calculator = TimedeltaCalculator()


@mcp.tool()
def ping() -> Dict[str, Any]:
    """Minimal tool: returns OK."""
    return {"ok": True}


def main():
    print("Starting First MCP Test Server...", file=sys.stderr, flush=True)
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
