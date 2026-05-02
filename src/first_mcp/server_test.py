"""
Incremental test server — lazy-import build-up.

Each batch adds tools with imports inside the function body so
mcp.run() starts immediately and the initialize handshake completes
before any heavy module is loaded.

Entry point: first-mcp-test

Batch 1: utility + math/time tools — stdlib only, no heavy deps.
Batch 2: weather, tool_info, bible tools — lazy imports.
         (embedding tools deferred: google.genai import + HTTP calls need
          separate investigation to avoid GIL/timeout disconnect)
Batch 3: memory tools + generic TinyDB tools — all lazy imports from .memory.
         Import cost paid once on first call; subsequent calls use sys.modules cache.
"""

import os
import sys
from typing import List, Dict, Any

from fastmcp import FastMCP
from .calculate import Calculator, TimedeltaCalculator

mcp = FastMCP(name="First MCP Test Server")

calculator = Calculator()
timedelta_calculator = TimedeltaCalculator()


def add_server_timestamp(response: Dict[str, Any]) -> Dict[str, Any]:
    import time
    from datetime import datetime
    if not isinstance(response, dict):
        response = {"data": response}
    response["server_timestamp"] = datetime.now().isoformat()
    try:
        response["server_timezone"] = time.tzname[time.daylight]
    except (AttributeError, IndexError):
        response["server_timezone"] = "local"
    return response


# ---------------------------------------------------------------------------
# Utility tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_system_info() -> Dict[str, Any]:
    """Get basic system information including memory storage configuration."""
    import platform
    return add_server_timestamp({
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "current_directory": os.getcwd(),
        "python_executable": sys.executable,
        "memory_storage_path": os.getenv('FIRST_MCP_DATA_PATH', os.getcwd()),
        "memory_storage_configured": os.getenv('FIRST_MCP_DATA_PATH') is not None,
        "workspace_path": os.getenv('FIRST_MCP_WORKSPACE_PATH', os.getcwd()),
        "workspace_configured": os.getenv('FIRST_MCP_WORKSPACE_PATH') is not None,
    })


@mcp.tool()
def count_words(text: str) -> Dict[str, Any]:
    """
    Count words and characters in a text.

    Args:
        text: The text to analyze
    """
    if not text:
        return add_server_timestamp({"words": 0, "characters": 0, "lines": 0})
    return add_server_timestamp({
        "words": len(text.split()),
        "characters": len(text),
        "lines": len(text.splitlines()),
    })


@mcp.tool()
def list_files(directory: str = ".") -> List[str]:
    """
    List files in a directory.

    Args:
        directory: Directory path to list (default: current directory)
    """
    try:
        if not os.path.exists(directory):
            return [f"Error: Directory '{directory}' does not exist"]
        files = []
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isfile(item_path):
                files.append(f"📄 {item}")
            elif os.path.isdir(item_path):
                files.append(f"📁 {item}/")
        return sorted(files)
    except Exception as e:
        return [f"Error: {str(e)}"]


# ---------------------------------------------------------------------------
# Math / time tools
# ---------------------------------------------------------------------------

@mcp.tool()
def calculate(expression: str) -> Dict[str, Any]:
    """
    Perform secure mathematical calculations.

    Args:
        expression: Mathematical expression (e.g. "2 + 3 * (4 - 1)")
    """
    try:
        return add_server_timestamp(calculator.calculate(expression))
    except Exception as e:
        return add_server_timestamp({"success": False, "error": str(e), "expression": expression})


@mcp.tool()
def calculate_time_difference(datetime1: str, datetime2: str) -> Dict[str, Any]:
    """
    Calculate the time difference between two datetime strings.

    Args:
        datetime1: First datetime string (start time)
        datetime2: Second datetime string (end time)
    """
    try:
        return add_server_timestamp(timedelta_calculator.calculate_timedelta(datetime1, datetime2))
    except Exception as e:
        return add_server_timestamp({"success": False, "error": str(e)})


@mcp.tool()
def get_day_of_week(date_string: str) -> Dict[str, Any]:
    """
    Get the day of the week for a given date.

    Args:
        date_string: Date in YYYY-MM-DD format
    """
    from .calendar_tools import get_day_of_week as _get_day_of_week
    return add_server_timestamp(_get_day_of_week(date_string))


@mcp.tool()
def get_calendar(year: int, month: int) -> Dict[str, Any]:
    """
    Get a calendar for a specific month.

    Args:
        year: Year (e.g. 2025)
        month: Month number (1-12)
    """
    from .calendar_tools import get_calendar as _get_calendar
    return add_server_timestamp(_get_calendar(year, month))


# ---------------------------------------------------------------------------
# Batch 2: weather, tool_info, embedding, bible tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_geocode(location: str, limit: int = 3) -> Dict[str, Any]:
    """
    Get coordinates for a location name using OpenWeatherMap geocoding API.

    Args:
        location: Location name (e.g., "Oslo,,NO", "London,GB", "New York,US")
        limit: Maximum number of results (1-5, default: 3)
    """
    from .weather import GeocodingAPI
    try:
        geocoding = GeocodingAPI()
        results = geocoding.geocode(location, limit)
        if not results:
            return add_server_timestamp({"error": f"No results found for location: {location}"})
        formatted_results = [
            {
                "name": r.get('name'),
                "country": r.get('country'),
                "state": r.get('state'),
                "latitude": r.get('lat'),
                "longitude": r.get('lon'),
                "local_names": r.get('local_names', {}),
            }
            for r in results
        ]
        return add_server_timestamp({
            "query": location,
            "results": formatted_results,
            "count": len(formatted_results),
        })
    except Exception as e:
        return add_server_timestamp({"error": str(e)})


@mcp.tool()
def get_weather(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Get weather forecast for given coordinates using Yr.no (MET Norway) API.

    Args:
        latitude: Latitude coordinate (-90 to 90)
        longitude: Longitude coordinate (-180 to 180)
    """
    from .weather import WeatherAPI
    try:
        weather = WeatherAPI()
        result = weather.get_current_weather(latitude, longitude)
        return add_server_timestamp(result)
    except Exception as e:
        return add_server_timestamp({"error": str(e)})


@mcp.tool()
def tool_info(tool_name: str) -> Dict[str, Any]:
    """
    Return detailed documentation for a named tool.

    Call with tool_name="list" to see which tools have extended documentation.

    Args:
        tool_name: Name of the tool (e.g. "tinydb_search_memories"), or "list".
    """
    docs_dir = os.path.join(os.path.dirname(__file__), 'tool_docs')
    if tool_name == "list":
        try:
            available = sorted(f[:-3] for f in os.listdir(docs_dir) if f.endswith('.md'))
        except Exception:
            available = []
        return add_server_timestamp({"success": True, "available": available})
    path = os.path.join(docs_dir, f"{tool_name}.md")
    if not os.path.exists(path):
        try:
            available = sorted(f[:-3] for f in os.listdir(docs_dir) if f.endswith('.md'))
        except Exception:
            available = []
        return add_server_timestamp({
            "success": False,
            "error": f"No documentation file found for '{tool_name}'.",
            "available": available,
        })
    with open(path, encoding="utf-8") as fh:
        content = fh.read()
    return add_server_timestamp({"success": True, "tool_name": tool_name, "documentation": content})


@mcp.tool()
def bible_lookup(reference: str, bible_version: str = "ESV") -> Dict[str, Any]:
    """
    Look up biblical text by reference.

    Bible text is downloaded automatically from github.com/lguenth/mdbible on first
    use and cached locally. Subsequent calls are served from the local cache.

    Args:
        reference: Biblical reference string. Supports single verse ("Gen 1:1"),
            verse range ("Gen 1:1-10"), chapter ("Gen 1"), chapter range ("Gen 1-4"),
            or multiple references semicolon-separated ("John 3:16; Rom 6:23").
        bible_version: Translation to use. Default "ESV". Currently only "ESV" is supported.
    """
    from .bible import bible_lookup as _bible_lookup
    try:
        verses = _bible_lookup(reference, version=bible_version)
        return add_server_timestamp({
            "success": True,
            "reference": reference,
            "version": bible_version,
            "verse_count": len(verses),
            "verses": [{"reference": ref, "text": text} for ref, text in verses],
        })
    except Exception as e:
        return add_server_timestamp({"error": str(e)})


# ---------------------------------------------------------------------------
# Batch 3: memory tools + generic TinyDB tools
# ---------------------------------------------------------------------------

@mcp.tool()
def memory_workflow_guide() -> Dict[str, Any]:
    """
    Return stored best practices for memory use.

    For full workflow documentation call tool_info("memory_workflow_guide").
    """
    from .memory import memory_workflow_guide as _memory_workflow_guide
    return add_server_timestamp(_memory_workflow_guide())


@mcp.tool()
def tinydb_memorize(content: str, tags: str = "", category: str = "",
                   importance: int = 3, expires_at: str = "") -> Dict[str, Any]:
    """
    Store information in long-term memory.

    Tags are the primary retrieval key — call tool_info("tinydb_memorize") for tag
    selection guidance and bridging-tag recommendations.

    Args:
        content: The information to store.
        tags: Comma-separated tags (e.g. "ergatax,higher-education,norway").
        category: One of: user_context, preferences, projects, learnings, corrections,
                  facts, reminders, best_practices.
        importance: 1–5. Higher values surface first in results. Default is 3.
        expires_at: ISO datetime after which the memory is down-prioritised (optional).
    """
    from .memory import tinydb_memorize as _tinydb_memorize
    result = _tinydb_memorize(
        content=content, tags=tags, category=category,
        importance=importance, expires_at=expires_at,
    )
    return add_server_timestamp(result)


@mcp.tool()
def tinydb_recall_memory(memory_id: str) -> Dict[str, Any]:
    """
    Fetch a single memory by its exact ID.

    Use this when you already have a memory_id from a previous search result and
    want its full content without running another search.

    Args:
        memory_id: The UUID from a previous tinydb_memorize or search result.
    """
    from .memory import tinydb_recall_memory as _tinydb_recall_memory
    return add_server_timestamp(_tinydb_recall_memory(memory_id=memory_id))


@mcp.tool()
def tinydb_search_memories(tags: str = "", content_keywords: str = "", category: str = "",
                           limit: int = 50, semantic_search: bool = True,
                           page_size: int = 5, sort_by: str = "relevance") -> Dict[str, Any]:
    """
    Search memories by tag similarity — the primary retrieval tool.

    Scores memories by tag-embedding similarity so approximate tags work ("scheduling"
    finds "timetabling"). Call tool_info("tinydb_search_memories") for full guidance.

    Args:
        tags: Comma-separated tags — primary search signal.
        content_keywords: Optional substring filter on memory content (not semantic).
        category: Optional exact-match category filter.
        sort_by: "relevance" (default), "date_desc", or "date_asc".
        page_size: Results in first response (default 5). Use memory_next_page to expand.
        limit: Hard cap on total memories considered (default 50).
        semantic_search: False uses exact tag matching only (default True).
    """
    from .memory import tinydb_search_memories as _tinydb_search_memories
    return add_server_timestamp(_tinydb_search_memories(
        tags=tags, content_keywords=content_keywords, category=category,
        limit=limit, semantic_search=semantic_search,
        page_size=page_size, sort_by=sort_by,
    ))


@mcp.tool()
def tinydb_list_memories(limit: int = 100, page_size: int = 10,
                        category: str = "", sort_by: str = "relevance") -> Dict[str, Any]:
    """
    Browse memories by category — use for inventory, not topic search.

    Prefer tinydb_search_memories when you have a topic in mind.

    Args:
        category: Optional exact-match category filter.
        sort_by: "relevance" (default, highest importance first), "date_desc", or "date_asc".
        page_size: Results in first response (default 10). Use memory_next_page to expand.
        limit: Hard cap on total memories considered (default 100).
    """
    from .memory import tinydb_list_memories as _tinydb_list_memories
    result = _tinydb_list_memories(
        limit=limit, page_size=page_size, category=category, sort_by=sort_by,
    )
    return add_server_timestamp(result)


@mcp.tool()
def memory_next_page(next_page_token: str) -> Dict[str, Any]:
    """
    Load the next page of results from a previous search or list call.

    Call this when has_more is True in a tinydb_search_memories or tinydb_list_memories
    response. Tokens are session-scoped and cleaned up at server startup.

    Args:
        next_page_token: Token from a search, list, or previous memory_next_page response.
    """
    from .memory import get_next_page
    try:
        result = get_next_page(next_page_token)
        return add_server_timestamp(result)
    except Exception as e:
        return add_server_timestamp({"error": str(e)})


@mcp.tool()
def tinydb_update_memory(memory_id: str, content: str = "", tags: str = "",
                        category: str = "", importance: int = 0, expires_at: str = "") -> Dict[str, Any]:
    """
    Modify an existing memory in place.

    Only the fields you supply are changed; omit a parameter to leave it unchanged.

    Args:
        memory_id: ID from a previous search or memorize result.
        content: Replacement text (leave empty to keep current content).
        tags: Replacement tag list, comma-separated (leave empty to keep current tags).
        category: New category (leave empty to keep current).
        importance: New importance 1-5 (pass 0 to keep current).
        expires_at: New expiry in ISO format (leave empty to keep current).
    """
    from .memory import tinydb_update_memory as _tinydb_update_memory
    result = _tinydb_update_memory(
        memory_id=memory_id, content=content, tags=tags,
        category=category, importance=importance, expires_at=expires_at,
    )
    return add_server_timestamp(result)


@mcp.tool()
def tinydb_delete_memory(memory_id: str) -> Dict[str, Any]:
    """
    Permanently delete a memory by ID.

    Prefer updating over deleting when the information is partly correct.

    Args:
        memory_id: ID from a previous search or memorize result.
    """
    from .memory import tinydb_delete_memory as _tinydb_delete_memory
    return add_server_timestamp(_tinydb_delete_memory(memory_id=memory_id))


@mcp.tool()
def tinydb_get_memory_categories() -> Dict[str, Any]:
    """
    List all categories that have been used, plus suggested standard categories.

    Call this before passing a category argument to tinydb_search_memories to
    confirm the exact spelling of available categories.
    """
    from .memory import tinydb_get_memory_categories as _tinydb_get_memory_categories
    return add_server_timestamp(_tinydb_get_memory_categories())


@mcp.tool()
def tinydb_find_similar_tags(query: str, limit: int = 5, min_similarity: float = 0.3) -> Dict[str, Any]:
    """
    Find existing tags whose meaning is close to a concept you describe.

    Call this before searching or storing when you are unsure which tags are
    already in the memory store.

    Args:
        query: A word, phrase, or concept to match against existing tags.
        limit: Maximum results to return (default 5).
        min_similarity: Minimum similarity threshold 0.0–1.0 (default 0.3).
    """
    from .memory import tinydb_find_similar_tags as _tinydb_find_similar_tags
    result = _tinydb_find_similar_tags(query=query, limit=limit, min_similarity=min_similarity)
    return add_server_timestamp(result)


@mcp.tool()
def tinydb_get_all_tags(cap: int = 100) -> Dict[str, Any]:
    """
    Return every tag in the memory store, sorted by how often it has been used.

    High-usage tags are the most reliable search keys.

    Args:
        cap: Maximum tags to return. 0 means uncapped (return all). Default 100.
    """
    from .memory import tinydb_get_all_tags as _tinydb_get_all_tags
    result = _tinydb_get_all_tags()
    if cap and isinstance(result.get("tags"), list):
        result["tags"] = result["tags"][:cap]
        result["total_tags"] = len(result["tags"])
    return add_server_timestamp(result)


# ---------------------------------------------------------------------------
# Batch 3 (cont.): generic TinyDB tools — same .memory import, no extra cost
# ---------------------------------------------------------------------------

@mcp.tool()
def tinydb_create_database(db_name: str, description: str = "") -> Dict[str, Any]:
    """
    Create a new TinyDB database file in the data folder.

    Args:
        db_name: Name of the database (will add .json if needed)
        description: Optional description of the database purpose
    """
    from .memory import tinydb_create_database as _tinydb_create_database
    return add_server_timestamp(_tinydb_create_database(db_name=db_name, description=description))


@mcp.tool()
def tinydb_store_data(db_name: str, table: str, data: Dict[str, Any], record_id: str = "") -> Dict[str, Any]:
    """
    Store data in any TinyDB database in the data folder.

    Args:
        db_name: Name of the database file
        table: Table name within the database
        data: Data to store (dictionary)
        record_id: Optional specific ID for the record
    """
    from .memory import tinydb_store_data as _tinydb_store_data
    return add_server_timestamp(_tinydb_store_data(db_name=db_name, table=table, data=data, record_id=record_id))


@mcp.tool()
def tinydb_query_data(db_name: str, table: str, query_conditions: Dict[str, Any] = {},
                     limit: int = 100, sort_by: str = "", reverse_sort: bool = True) -> Dict[str, Any]:
    """
    Query data from any TinyDB database in the data folder.

    Args:
        db_name: Name of the database file
        table: Table name to query
        query_conditions: Dictionary of field:value conditions
        limit: Maximum number of results
        sort_by: Field to sort by
        reverse_sort: Sort in descending order (default: True)
    """
    from .memory import tinydb_query_data as _tinydb_query_data
    return add_server_timestamp(
        _tinydb_query_data(
            db_name=db_name, table=table, query_conditions=query_conditions,
            limit=limit, sort_by=sort_by, reverse_sort=reverse_sort,
        )
    )


@mcp.tool()
def tinydb_update_data(db_name: str, table: str, record_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update specific fields in an existing record in any TinyDB database.

    Args:
        db_name: Name of the database file
        table: Table name
        record_id: ID of the record to update
        updates: Dictionary of field:value updates
    """
    from .memory import tinydb_update_data as _tinydb_update_data
    return add_server_timestamp(
        _tinydb_update_data(db_name=db_name, table=table, record_id=record_id, updates=updates)
    )


@mcp.tool()
def tinydb_delete_data(db_name: str, table: str, record_id: str = "",
                      query_conditions: Dict[str, Any] = {}) -> Dict[str, Any]:
    """
    Delete records from any TinyDB database in the data folder.

    Args:
        db_name: Name of the database file
        table: Table name
        record_id: ID of specific record to delete (optional)
        query_conditions: Conditions for bulk deletion (optional)
    """
    from .memory import tinydb_delete_data as _tinydb_delete_data
    return add_server_timestamp(
        _tinydb_delete_data(db_name=db_name, table=table, record_id=record_id, query_conditions=query_conditions)
    )


@mcp.tool()
def tinydb_list_databases() -> Dict[str, Any]:
    """
    List all TinyDB databases in the data folder.

    Shows dedicated databases (memories, tags, categories) and user-created databases.
    """
    from .memory import tinydb_list_databases as _tinydb_list_databases
    return add_server_timestamp(_tinydb_list_databases())


@mcp.tool()
def tinydb_get_database_info(db_name: str) -> Dict[str, Any]:
    """
    Get comprehensive information about a specific TinyDB database.

    Args:
        db_name: Name of the database to inspect
    """
    from .memory import tinydb_get_database_info as _tinydb_get_database_info
    return add_server_timestamp(_tinydb_get_database_info(db_name=db_name))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import time as _time
    print("Starting First MCP Test Server...", file=sys.stderr, flush=True)

    t0 = _time.monotonic()

    # Fast synchronous pre-warms (proven within startup budget).
    try:
        from . import memory as _memory_warmup  # noqa: F401
        print(f"memory pkg pre-loaded ({_time.monotonic()-t0:.2f}s).", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"memory pre-warm failed: {e}", file=sys.stderr, flush=True)

    t1 = _time.monotonic()
    try:
        import google.genai  # noqa: F401
        print(f"google.genai pre-loaded ({_time.monotonic()-t1:.2f}s).", file=sys.stderr, flush=True)
    except ImportError:
        print("google.genai not available — embedding features disabled.", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"google.genai pre-warm failed: {e}", file=sys.stderr, flush=True)

    # Numpy is too slow to import synchronously on Windows without exceeding the
    # MCP initialize timeout, but importing it lazily mid-request holds the GIL
    # and causes Claude Desktop to close the transport. Background-thread import
    # is the solution: if a tool call reaches `import numpy` while this thread is
    # still running, the tool thread waits on Python's per-module import lock,
    # which releases the GIL — so the event loop stays responsive during the wait.
    def _warmup_numpy() -> None:
        t = _time.monotonic()
        try:
            import numpy  # noqa: F401
            print(f"numpy pre-loaded ({_time.monotonic()-t:.2f}s).", file=sys.stderr, flush=True)
        except ImportError:
            print("numpy not available — semantic search disabled.", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"numpy pre-warm failed: {e}", file=sys.stderr, flush=True)

    import threading as _threading
    _threading.Thread(target=_warmup_numpy, daemon=True, name="numpy-warmup").start()

    print(f"Sync pre-warm done ({_time.monotonic()-t0:.2f}s). Starting MCP transport.", file=sys.stderr, flush=True)
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
