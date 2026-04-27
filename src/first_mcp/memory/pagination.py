"""
Pagination persistence for memory query results.

Stores full result sets in temporary JSON files so callers can fetch
subsequent pages without re-running the original query.

Token → file: {FIRST_MCP_DATA_PATH}/_paginated/{token}.json

Cleanup: call cleanup_paginated_files() at server startup.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


def _paginated_dir() -> str:
    base = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
    return os.path.join(base, '_paginated')


def save_paginated_results(
    all_results: List[Dict[str, Any]],
    page_size: int,
    query_info: Dict[str, Any],
) -> str:
    """
    Persist all_results to a temp file and return a next-page token.

    Assumes the first page (all_results[:page_size]) has already been
    returned to the caller; the stored offset starts at page_size.

    Args:
        all_results: Full sorted result list from the query.
        page_size: Number of results per page.
        query_info: Original query parameters for informational purposes.

    Returns:
        Token string (UUID) that identifies the paginated file.
    """
    token = str(uuid.uuid4())
    directory = _paginated_dir()
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{token}.json")

    payload = {
        "all_results": all_results,
        "page_size": page_size,
        "offset": page_size,
        "total": len(all_results),
        "query_info": query_info,
        "created_at": datetime.now().isoformat(),
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    return token


def get_next_page(token: str) -> Dict[str, Any]:
    """
    Return the next page for the given token.

    Advances the stored offset. Deletes the file once all results are
    returned so no stale state accumulates mid-session.

    Args:
        token: Token returned by a previous search or memory_next_page call.

    Returns:
        Dict with keys: success, memories, returned_count, page_offset,
        total_found, has_more, next_page_token, query_info.
    """
    path = os.path.join(_paginated_dir(), f"{token}.json")
    if not os.path.exists(path):
        return {
            "success": False,
            "error": "Token not found — it may have been exhausted or was cleaned up at startup.",
        }

    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    all_results: List[Dict[str, Any]] = data["all_results"]
    page_size: int = data["page_size"]
    offset: int = data["offset"]
    total: int = data["total"]

    page = all_results[offset : offset + page_size]
    new_offset = offset + len(page)
    has_more = new_offset < total
    next_token: Optional[str] = None

    if has_more:
        data["offset"] = new_offset
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        next_token = token
    else:
        try:
            os.remove(path)
        except OSError:
            pass

    return {
        "success": True,
        "memories": page,
        "returned_count": len(page),
        "page_offset": offset,
        "total_found": total,
        "has_more": has_more,
        "next_page_token": next_token,
        "query_info": data.get("query_info", {}),
    }


def cleanup_paginated_files() -> int:
    """
    Delete all paginated temp files from a previous server session.

    Called at server startup so stale tokens from the previous session
    cannot be accidentally consumed.

    Returns:
        Number of files deleted.
    """
    directory = _paginated_dir()
    if not os.path.isdir(directory):
        return 0

    count = 0
    for fname in os.listdir(directory):
        if fname.endswith(".json"):
            try:
                os.remove(os.path.join(directory, fname))
                count += 1
            except OSError:
                pass
    return count
