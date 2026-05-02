"""
First MCP Server — MCP layer only.

Every @mcp.tool() here is a thin wrapper:
  1. Call one business-layer function (imported with _ prefix)
  2. Return add_server_timestamp(result)

No TinyDB access, no business logic, no if/else branching beyond what
FastMCP requires for parameter defaults.
"""

import asyncio
import os
import sys
from typing import List, Dict, Any

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan as _lifespan_decorator

from .weather import WeatherAPI, GeocodingAPI
from .fileio import WorkspaceManager
from .calculate import Calculator, TimedeltaCalculator
from .embeddings import (
    compute_text_similarity as _compute_text_similarity,
    rank_texts_by_similarity as _rank_texts_by_similarity,
)
from .bible import bible_lookup as _bible_lookup
from .calendar_tools import get_calendar as _get_calendar, get_day_of_week as _get_day_of_week

from .memory import (
    tinydb_memorize as _tinydb_memorize,
    tinydb_recall_memory as _tinydb_recall_memory,
    tinydb_search_memories as _tinydb_search_memories,
    tinydb_list_memories as _tinydb_list_memories,
    tinydb_update_memory as _tinydb_update_memory,
    tinydb_delete_memory as _tinydb_delete_memory,
    tinydb_get_memory_categories as _tinydb_get_memory_categories,
    memory_workflow_guide as _memory_workflow_guide,
    tinydb_find_similar_tags as _tinydb_find_similar_tags,
    tinydb_get_all_tags as _tinydb_get_all_tags,
    tinydb_create_database as _tinydb_create_database,
    tinydb_store_data as _tinydb_store_data,
    tinydb_query_data as _tinydb_query_data,
    tinydb_update_data as _tinydb_update_data,
    tinydb_delete_data as _tinydb_delete_data,
    tinydb_list_databases as _tinydb_list_databases,
    tinydb_get_database_info as _tinydb_get_database_info,
    get_next_page,
    save_paginated_results,
    cleanup_paginated_files,
)

from .assistant import get_second_opinion as _get_second_opinion


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def add_server_timestamp(response: Dict[str, Any]) -> Dict[str, Any]:
    """Add server_timestamp and server_timezone to any tool response dict."""
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
# Server lifecycle
# ---------------------------------------------------------------------------

@_lifespan_decorator
async def _lifespan(server: FastMCP):
    """
    Non-blocking startup warm-up: migrate tag embeddings and pre-load the tag
    registry cache into memory.  Runs as a background asyncio task so the MCP
    transport can complete its initialize handshake immediately, without waiting
    for the ~5 s TinyDB read + numpy conversion to finish.
    """
    async def _warm_up() -> None:
        from .memory.tag_tools import check_and_migrate_tag_embeddings
        from .memory.tag_scoring import warm_tag_registry_cache
        try:
            migration = await asyncio.to_thread(check_and_migrate_tag_embeddings)
            if migration.get("action") == "migrated":
                print(
                    f"✓ Tag embeddings migrated: {migration.get('updated', 0)} updated "
                    f"({migration.get('previous_model')} -> {migration.get('embedding_model')})",
                    file=sys.stderr,
                )
            count = await asyncio.to_thread(warm_tag_registry_cache)
            print(f"✓ Tag registry warmed: {count} tags cached", file=sys.stderr)
        except Exception as e:
            print(f"✗ Startup warm-up failed: {e}", file=sys.stderr)

    task = asyncio.create_task(_warm_up())
    yield {}
    if not task.done():
        await task


mcp = FastMCP(name="First MCP Server", lifespan=_lifespan)

# Module-level singletons
workspace_manager = WorkspaceManager()
calculator = Calculator()
timedelta_calculator = TimedeltaCalculator()


# ---------------------------------------------------------------------------
# Utility tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_system_info() -> Dict[str, Any]:
    """
    Get basic system information including memory storage configuration.

    Returns:
        Dictionary containing system information
    """
    import platform

    memory_data_path = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
    workspace_path = os.getenv('FIRST_MCP_WORKSPACE_PATH', os.getcwd())

    result = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "current_directory": os.getcwd(),
        "python_executable": sys.executable,
        "memory_storage_path": memory_data_path,
        "memory_storage_configured": os.getenv('FIRST_MCP_DATA_PATH') is not None,
        "workspace_path": workspace_path,
        "workspace_configured": os.getenv('FIRST_MCP_WORKSPACE_PATH') is not None,
    }
    return add_server_timestamp(result)


@mcp.tool()
def count_words(text: str) -> Dict[str, Any]:
    """
    Count words and characters in a text.

    Args:
        text: The text to analyze

    Returns:
        Dictionary with word count, character count, and line count
    """
    if not text:
        return add_server_timestamp({"words": 0, "characters": 0, "lines": 0})

    result = {
        "words": len(text.split()),
        "characters": len(text),
        "lines": len(text.splitlines()),
    }
    return add_server_timestamp(result)


@mcp.tool()
def list_files(directory: str = ".") -> List[str]:
    """
    List files in a directory.

    Args:
        directory: Directory path to list (default: current directory)

    Returns:
        List of filenames in the directory
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


@mcp.tool()
def calculate(expression: str) -> Dict[str, Any]:
    """
    Perform secure mathematical calculations on expressions.

    Evaluates mathematical expressions containing only numbers, parentheses,
    and basic arithmetic operators (+, -, *, /, ^).

    Args:
        expression: Mathematical expression string (e.g., "2 + 3 * (4 - 1)", "2^3 + 5")

    Returns:
        Dictionary with calculation result or error information
    """
    try:
        result = calculator.calculate(expression)
        return add_server_timestamp(result)
    except Exception as e:
        return add_server_timestamp({
            "success": False,
            "error": f"Calculator error: {str(e)}",
            "expression": expression,
        })


@mcp.tool()
def calculate_time_difference(datetime1: str, datetime2: str) -> Dict[str, Any]:
    """
    Calculate the time difference between two datetime strings.

    Args:
        datetime1: First datetime string (start time)
        datetime2: Second datetime string (end time)

    Returns:
        Dictionary with time difference result or error information
    """
    try:
        result = timedelta_calculator.calculate_timedelta(datetime1, datetime2)
        return add_server_timestamp(result)
    except Exception as e:
        return add_server_timestamp({
            "success": False,
            "error": f"Timedelta calculator error: {str(e)}",
            "datetime1": datetime1,
            "datetime2": datetime2,
        })


@mcp.tool()
def get_geocode(location: str, limit: int = 3) -> Dict[str, Any]:
    """
    Get coordinates for a location name using OpenWeatherMap geocoding API.

    Args:
        location: Location name (e.g., "Oslo,,NO", "London,GB", "New York,US")
        limit: Maximum number of results (1-5, default: 3)

    Returns:
        Dictionary with geocoding results or error message
    """
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

    Returns:
        Dictionary with current weather conditions and attribution
    """
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
def compute_text_similarity(
    query: str,
    text: str,
    context: str = "",
    text_weight: float = 0.7,
    context_weight: float = 0.3,
) -> Dict[str, Any]:
    """
    Compute semantic similarity between a query and a text, with optional context weighting.

    Requires GOOGLE_API_KEY environment variable.

    Args:
        query: Reference text or semantic label to compare against
        text: Primary text to evaluate
        context: Optional surrounding context. Ignored if empty.
        text_weight: Weight for the text embedding when context is used. Default: 0.7
        context_weight: Weight for the context embedding. Default: 0.3

    Returns:
        Dictionary with similarity score and request metadata
    """
    result = _compute_text_similarity(query, text, context, text_weight, context_weight)
    return add_server_timestamp(result)


@mcp.tool()
def rank_texts_by_similarity(query: str, candidates: List[str]) -> Dict[str, Any]:
    """
    Rank a list of texts by semantic similarity to a query text.

    Requires GOOGLE_API_KEY environment variable.

    Args:
        query: Reference text to compare against
        candidates: List of texts to rank

    Returns:
        Dictionary with candidates ranked by descending similarity score
    """
    result = _rank_texts_by_similarity(query, candidates)
    return add_server_timestamp(result)


@mcp.tool()
def bible_lookup(reference: str, bible_version: str = "ESV") -> Dict[str, Any]:
    """
    Look up biblical text by reference.

    Bible text is downloaded automatically from github.com/lguenth/mdbible on first
    use and cached locally. Subsequent calls are served from the local cache.

    Args:
        reference: Biblical reference string. Supports:
            - "Gen 1:1"                   Single verse
            - "Gen 1:1-10"               Verse range
            - "Gen 1"                     Entire chapter
            - "Gen 1-4"                   Chapter range
            - "John 3:16; Rom 6:23"       Multiple references (semicolon separated)
            Common abbreviations are accepted for all 66 books.
        bible_version: Translation to use. Default "ESV". Currently only "ESV"
                       is supported.

    Returns:
        Dictionary with reference, version, and list of verse objects
    """
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
# Calendar tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_calendar(year: int, month: int) -> Dict[str, Any]:
    """
    Get a calendar for a specified year and month in both HTML and text formats.

    Args:
        year: The year (e.g., 2025)
        month: The month (1-12, where 1=January, 12=December)

    Returns:
        Dictionary with calendar in HTML format, plain text, and metadata
    """
    return add_server_timestamp(_get_calendar(year=year, month=month))


@mcp.tool()
def get_day_of_week(date_string: str) -> Dict[str, Any]:
    """
    Get the day of the week for a given date in ISO format (YYYY-MM-DD).

    Args:
        date_string: Date in ISO format (e.g., "2025-08-09", "2024-12-25")

    Returns:
        Dictionary with weekday information and metadata
    """
    return add_server_timestamp(_get_day_of_week(date_string=date_string))


# ---------------------------------------------------------------------------
# Memory tools
# ---------------------------------------------------------------------------

@mcp.tool()
def memory_workflow_guide() -> Dict[str, Any]:
    """
    Return stored best practices for memory use.

    For full workflow documentation call tool_info("memory_workflow_guide").
    """
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
    want its full content without running another search. For finding memories
    by topic, use tinydb_search_memories instead.

    Args:
        memory_id: The UUID from a previous tinydb_memorize or search result.
    """
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
        category: Optional exact-match category filter. Call tinydb_get_memory_categories
                  to see available values.
        sort_by: "relevance" (default), "date_desc", or "date_asc".
        page_size: Results in first response (default 5). Use memory_next_page to expand.
        limit: Hard cap on total memories considered (default 50).
        semantic_search: False uses exact tag matching only (default True).
    """
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

    Prefer tinydb_search_memories when you have a topic in mind. Call
    tool_info("tinydb_list_memories") for a list-vs-search decision table.

    Args:
        category: Optional exact-match category filter. Call tinydb_get_memory_categories
                  to see available values.
        sort_by: "relevance" (default, highest importance first), "date_desc", or "date_asc".
        page_size: Results in first response (default 10). Use memory_next_page to expand.
        limit: Hard cap on total memories considered (default 100).
    """
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
    Use deletion for information that is entirely outdated or was stored in error.

    Args:
        memory_id: ID from a previous search or memorize result.
    """
    return add_server_timestamp(_tinydb_delete_memory(memory_id=memory_id))


@mcp.tool()
def tinydb_get_memory_categories() -> Dict[str, Any]:
    """
    List all categories that have been used, plus suggested standard categories.

    Categories are a broad secondary axis for organising memories ("projects",
    "preferences", "user_context", "facts", …). Tags are the primary retrieval
    mechanism; categories are most useful as a coarse filter on top of tag search.

    Call this before passing a category argument to tinydb_search_memories to
    confirm the exact spelling of available categories.
    """
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
    result = _tinydb_find_similar_tags(query=query, limit=limit, min_similarity=min_similarity)
    return add_server_timestamp(result)


@mcp.tool()
def tinydb_get_all_tags(cap: int = 100) -> Dict[str, Any]:
    """
    Return every tag in the memory store, sorted by how often it has been used.

    High-usage tags are the most reliable search keys. Prefer tinydb_find_similar_tags
    to narrow down to a specific concept instead.

    Args:
        cap: Maximum tags to return. 0 means uncapped (return all). Default 100.
    """
    result = _tinydb_get_all_tags()
    # Apply cap here since the impl always returns all
    if cap and isinstance(result.get("tags"), list):
        result["tags"] = result["tags"][:cap]
        result["total_tags"] = len(result["tags"])
    return add_server_timestamp(result)


# ---------------------------------------------------------------------------
# Generic TinyDB tools
# ---------------------------------------------------------------------------

@mcp.tool()
def tinydb_create_database(db_name: str, description: str = "") -> Dict[str, Any]:
    """
    Create a new TinyDB database file in the data folder.

    Args:
        db_name: Name of the database (will add .json if needed)
        description: Optional description of the database purpose

    Returns:
        Dictionary with database creation confirmation
    """
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

    Returns:
        Dictionary with storage confirmation and record ID
    """
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

    Returns:
        Dictionary with query results
    """
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

    Returns:
        Dictionary with update confirmation
    """
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

    Returns:
        Dictionary with deletion confirmation
    """
    return add_server_timestamp(
        _tinydb_delete_data(db_name=db_name, table=table, record_id=record_id, query_conditions=query_conditions)
    )


@mcp.tool()
def tinydb_list_databases() -> Dict[str, Any]:
    """
    List all TinyDB databases in the data folder.

    Shows dedicated databases (memories, tags, categories) and user-created databases.

    Returns:
        Dictionary with all available databases and their information
    """
    return add_server_timestamp(_tinydb_list_databases())


@mcp.tool()
def tinydb_get_database_info(db_name: str) -> Dict[str, Any]:
    """
    Get comprehensive information about a specific TinyDB database.

    Args:
        db_name: Name of the database to inspect

    Returns:
        Dictionary with detailed database information
    """
    return add_server_timestamp(_tinydb_get_database_info(db_name=db_name))


# ---------------------------------------------------------------------------
# Workspace tools
# ---------------------------------------------------------------------------

@mcp.tool()
def store_workspace_file(filename: str, content: str, description: str = "",
                        tags: str = "", language: str = "", overwrite: bool = False) -> Dict[str, Any]:
    """
    Store a text file in the configured workspace directory.

    Args:
        filename: Name of the file to store (e.g., "notes.txt", "script.py")
        content: Text content to store in the file
        description: Optional description of the file's purpose
        tags: Comma-separated tags for categorization
        language: Programming language or content type. Use "/" for multiple
                 (e.g., "python", "markdown/norwegian", "html/css").
        overwrite: Whether to overwrite existing files (default: False)

    Returns:
        Dictionary with storage result and file information
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    result = workspace_manager.store_text_file(
        filename=filename,
        content=content,
        description=description.strip() if description else "",
        tags=tag_list,
        language=language.strip() if language else "",
        overwrite=overwrite,
    )
    return add_server_timestamp(result)


@mcp.tool()
def read_workspace_file(filename: str) -> Dict[str, Any]:
    """
    Read a text file from the workspace directory.

    Args:
        filename: Name of the file to read

    Returns:
        Dictionary with file content and metadata
    """
    try:
        result = workspace_manager.read_text_file(filename)
        return add_server_timestamp(result)
    except Exception as e:
        return add_server_timestamp({"error": str(e)})


@mcp.tool()
def workspace_edit_textfile(filename: str, mode: str, content: str, anchor: str = "") -> Dict[str, Any]:
    """
    Edit a workspace text file using anchor-based positioning.

    Call tool_info("workspace_edit_textfile") for mode descriptions and anchor tips.

    Args:
        filename: Name of the workspace file to edit.
        mode: One of: append, prepend, insert_after, insert_before, replace, replace_all.
        content: Text to insert or use as replacement.
        anchor: Exact substring used as reference point. Required for insert_after,
                insert_before, replace, replace_all. Ignored for append and prepend.
    """
    try:
        result = workspace_manager.edit_text_file(
            filename=filename, mode=mode, content=content, anchor=anchor
        )
        return add_server_timestamp(result)
    except Exception as e:
        return add_server_timestamp({"error": str(e)})


@mcp.tool()
def list_workspace_files(filter_tags: str = "") -> Dict[str, Any]:
    """
    List all files in the workspace directory with their metadata.

    Args:
        filter_tags: Optional comma-separated tags to filter by

    Returns:
        Dictionary with list of files and their information
    """
    tag_filter = [t.strip() for t in filter_tags.split(",") if t.strip()] if filter_tags else None
    result = workspace_manager.list_workspace_files(filter_tags=tag_filter)
    return add_server_timestamp(result)


@mcp.tool()
def delete_workspace_file(filename: str) -> Dict[str, Any]:
    """
    Delete a file from the workspace directory.

    Args:
        filename: Name of the file to delete

    Returns:
        Dictionary with deletion result
    """
    try:
        result = workspace_manager.delete_workspace_file(filename)
        return add_server_timestamp(result)
    except Exception as e:
        return add_server_timestamp({"error": str(e)})


@mcp.tool()
def update_workspace_file_metadata(filename: str, description: str = "",
                                  tags: str = "", language: str = "") -> Dict[str, Any]:
    """
    Update metadata (description, tags, and language) for an existing workspace file.

    Args:
        filename: Name of the file to update
        description: New description (leave empty to keep existing)
        tags: New comma-separated tags (leave empty to keep existing)
        language: New language/content type (leave empty to keep existing)

    Returns:
        Dictionary with update result
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    description_val = description.strip() if description.strip() else None
    language_val = language.strip() if language.strip() else None
    result = workspace_manager.update_file_metadata(
        filename=filename,
        description=description_val,
        tags=tag_list,
        language=language_val,
    )
    return add_server_timestamp(result)


@mcp.tool()
def get_workspace_info() -> Dict[str, Any]:
    """
    Get information about the workspace directory and its contents.

    Returns:
        Dictionary with workspace statistics and configuration
    """
    try:
        result = workspace_manager.get_workspace_info()
        return add_server_timestamp(result)
    except Exception as e:
        return add_server_timestamp({"error": str(e)})


# ---------------------------------------------------------------------------
# Assistant tools
# ---------------------------------------------------------------------------

@mcp.tool()
def second_opinion(question: str, context: str = "") -> Dict[str, Any]:
    """
    Ask Gemini for a second opinion on any question.

    Useful when a different model perspective is helpful — analysis, wording,
    trade-offs, or a sanity check. The answer is returned as plain text and
    should be treated as one input, not ground truth.

    Args:
        question: The question to ask Gemini.
        context:  Optional background context to include (e.g. a code snippet,
                  a summary of the situation, or relevant facts).
    """
    return add_server_timestamp(_get_second_opinion(question=question, context=context))


# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------

def _check_and_initialize_fresh_install():
    """Initialize memory DB with a session guide on first run (empty DB)."""
    try:
        from .memory import tinydb_memorize as _mem, get_memory_tinydb
        memory_db = get_memory_tinydb()
        memories_table = memory_db.table('memories')
        is_fresh = len(memories_table.all()) == 0
        memory_db.close()

        if not is_fresh:
            return

        print("✓ Fresh installation detected - initializing with session preferences", file=sys.stderr)

        session_guide = (
            "SESSION INITIALIZATION GUIDE - Essential for optimal MCP server usage:\n\n"
            "1. SEARCH SESSION PREFERENCES: Use tinydb_search_memories with tags='session-start' "
            "to load your behavioral preferences\n"
            "2. LOAD WORKSPACE CONTEXT: Read key workspace files (like general-instructions.md) "
            "to understand current context\n"
            "3. SEMANTIC SEARCH: When searching memories, use English search terms for best results "
            "regardless of conversation language\n"
            "4. TOOL-FIRST APPROACH: Proactively use available MCP tools rather than providing "
            "general responses\n"
            "5. WORKFLOW ADHERENCE: Follow established patterns from memory rather than improvising\n\n"
            "CRITICAL SEARCH TIP: Memory database content is stored in English. Always use English "
            "search terms for optimal results, even when conversing in Norwegian or other languages.\n\n"
            "This memory serves as your initialization checklist. Search for 'session-start' tagged "
            "memories at the beginning of each session for personalized assistant behavior."
        )

        result = _mem(
            content=session_guide,
            tags="session-start,initialization,workflow",
            category="preferences",
            importance=5,
        )
        if result.get("success"):
            print("✓ Session initialization guide stored successfully", file=sys.stderr)
        else:
            print("✗ Failed to store session guide:", result.get("error"), file=sys.stderr)

    except Exception as e:
        print(f"✗ Fresh install initialization failed: {e}", file=sys.stderr)


def main():
    """Main entry point for the MCP server."""
    print("Starting First MCP Server...", file=sys.stderr)
    print(f"Python executable: {sys.executable}", file=sys.stderr)
    print(f"Current directory: {os.getcwd()}", file=sys.stderr)

    _check_and_initialize_fresh_install()

    # Clean up paginated temp files from any previous session
    cleaned = cleanup_paginated_files()
    if cleaned:
        print(f"✓ Cleaned {cleaned} stale paginated temp file(s)", file=sys.stderr)

    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error starting MCP server: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
