"""
First MCP Server - A minimal example with basic tools
"""

from fastmcp import FastMCP
# import json
import asyncio
import contextlib
import os
import sys
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional, Union
from .weather import WeatherAPI, GeocodingAPI
from .fileio import WorkspaceManager
from .calculate import Calculator, TimedeltaCalculator
from .embeddings import compute_text_similarity as _compute_text_similarity, rank_texts_by_similarity as _rank_texts_by_similarity
from .bible import bible_lookup as _bible_lookup

# Always import TinyDB components for fallback functions
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

# Import memory system components
try:
    # Try to import from the memory package if available
    from .memory import (
        get_memory_tinydb, get_tags_tinydb, get_categories_tinydb, get_custom_tinydb,
        tinydb_memorize as tinydb_memorize_impl, tinydb_recall_memory, tinydb_search_memories,
        tinydb_list_memories,
        tinydb_update_memory as _tinydb_update_memory_impl,
        tinydb_delete_memory as _tinydb_delete_memory_impl,
        tinydb_get_memory_categories, memory_workflow_guide,
        tinydb_find_similar_tags, tinydb_get_all_tags,
        find_similar_tags_internal, check_category_exists,
        tinydb_create_database, tinydb_store_data, tinydb_query_data,
        tinydb_update_data, tinydb_delete_data, tinydb_list_databases,
        tinydb_get_database_info,
        save_paginated_results, get_next_page, cleanup_paginated_files,
        build_tag_registry, score_memories_by_tags,
    )
    MEMORY_PACKAGE_AVAILABLE = True
except ImportError:
    # Fallback: use legacy inline implementation
    MEMORY_PACKAGE_AVAILABLE = False

try:
    from .memory.tag_enrichment import tag_enrichment_loop as _tag_enrichment_loop
    TAG_ENRICHMENT_AVAILABLE = True
except ImportError:
    TAG_ENRICHMENT_AVAILABLE = False

# Capture raw callable references before @mcp.tool() decorators overwrite the names
# with FunctionTool objects.  These are used for internal (non-MCP) calls.
if MEMORY_PACKAGE_AVAILABLE:
    _search_memories_fn = tinydb_search_memories   # from .memory import above
else:
    _search_memories_fn = None

# Server timestamp helper function
def add_server_timestamp(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add server timestamp to any tool response for time/date awareness.
    
    Args:
        response: Tool response dictionary
        
    Returns:
        Response dictionary with added server_timestamp and server_timezone
    """
    from datetime import datetime
    import time
    
    if not isinstance(response, dict):
        # If response is not a dict, wrap it
        response = {"data": response}
    
    # Add timestamp in ISO format with timezone info
    response["server_timestamp"] = datetime.now().isoformat()
    
    # Add timezone name if available
    try:
        response["server_timezone"] = time.tzname[time.daylight]
    except (AttributeError, IndexError):
        response["server_timezone"] = "local"
    
    return response

# Create the MCP server
@asynccontextmanager
async def _lifespan(server: FastMCP):
    task = asyncio.create_task(_tag_enrichment_loop()) if TAG_ENRICHMENT_AVAILABLE else None
    try:
        yield {}
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


mcp = FastMCP(name="First MCP Server", lifespan=_lifespan)

# Initialize workspace manager and calculators
workspace_manager = WorkspaceManager()
calculator = Calculator()
timedelta_calculator = TimedeltaCalculator()

# Conditionally define legacy memory functions if package not available
if not MEMORY_PACKAGE_AVAILABLE:
    # Dedicated TinyDB helper functions for memories, tags, and categories
    def get_memory_tinydb():
        """Get TinyDB instance for memories."""
        base_path = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
        db_path = os.path.join(base_path, 'tinydb_memories.json')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return TinyDB(db_path, storage=CachingMiddleware(JSONStorage))

    def get_tags_tinydb():
        """Get TinyDB instance for tags."""
        base_path = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
        db_path = os.path.join(base_path, 'tinydb_tags.json')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return TinyDB(db_path, storage=CachingMiddleware(JSONStorage))

    def get_categories_tinydb():
        """Get TinyDB instance for categories."""
        base_path = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
        db_path = os.path.join(base_path, 'tinydb_categories.json')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return TinyDB(db_path, storage=CachingMiddleware(JSONStorage))

    def get_custom_tinydb(db_name: str):
        """Get TinyDB instance for user-specified database."""
        base_path = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
        # Add .json extension if not present
        if not db_name.endswith('.json'):
            db_name = f'{db_name}.json'
        db_path = os.path.join(base_path, db_name)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return TinyDB(db_path, storage=CachingMiddleware(JSONStorage))

    # Internal semantic search helper functions
    def _find_similar_tags_internal(query: str, limit: int = 5, min_similarity: float = 0.3):
        """
        Internal helper to find similar tags. Used by tinydb_search_memories for semantic expansion.
        Returns list of similar tag names, not the full MCP tool response format.
        """
        try:
            tags_db = get_tags_tinydb()
            tags_table = tags_db.table('tags')
            
            all_tags = tags_table.all()
            if not all_tags:
                tags_db.close()
                return []
            
            query_lower = query.lower().strip()
            similar_tags = []
            
            for tag_entry in all_tags:
                tag = tag_entry.get('tag', '')
                similarity = 0.0
                
                if query_lower in tag.lower():
                    similarity = 0.8
                elif any(word in tag.lower() for word in query_lower.split()):
                    similarity = 0.6
                elif any(word in query_lower for word in tag.lower().split()):
                    similarity = 0.4
                    
                if similarity >= min_similarity:
                    similar_tags.append({
                        "tag": tag,
                        "similarity": similarity,
                        "usage_count": tag_entry.get('usage_count', 0)
                    })
            
            # Sort by similarity first, then usage count
            similar_tags.sort(key=lambda x: (x['similarity'], x['usage_count']), reverse=True)
            tags_db.close()
            
            # Return just the tag names for internal use
            return [tag_info["tag"] for tag_info in similar_tags[:limit]]
            
        except Exception as e:
            return []

    def _check_category_exists(category: str):
        """
        Check if a category exists and return error info if not.
        Returns (exists: bool, error_message: str, existing_categories: list)
        """
        try:
            categories_db = get_categories_tinydb()
            categories_table = categories_db.table('categories')
            
            all_categories = categories_table.all()
            categories_db.close()
            
            if not all_categories:
                return False, "No categories exist in database", []
            
            existing_cats = [cat.get('category', '') for cat in all_categories if cat.get('category')]
            
            # Check for exact match (case insensitive)
            if category.lower() in [cat.lower() for cat in existing_cats if cat]:
                return True, "", existing_cats
            
            # Category doesn't exist
            error_msg = f"Category '{category}' not found. Available categories: {', '.join(existing_cats)}"
            return False, error_msg, existing_cats
            
        except Exception as e:
            return False, f"Error checking categories: {str(e)}", []

@mcp.tool()
def get_system_info() -> Dict[str, Any]:
    """
    Get basic system information including memory storage configuration.
    
    Returns:
        Dictionary containing system information
    """
    import platform
    
    # Get memory storage path from environment or current directory
    memory_data_path = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
    
    # Get workspace path from environment or current directory
    workspace_path = os.getenv('FIRST_MCP_WORKSPACE_PATH', os.getcwd())
    
    result = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "current_directory": os.getcwd(),
        "python_executable": sys.executable,
        "memory_storage_path": memory_data_path,
        "memory_storage_configured": os.getenv('FIRST_MCP_DATA_PATH') is not None,
        "workspace_path": workspace_path,
        "workspace_configured": os.getenv('FIRST_MCP_WORKSPACE_PATH') is not None
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
        result = {"words": 0, "characters": 0, "lines": 0}
        return add_server_timestamp(result)
    
    words = len(text.split())
    characters = len(text)
    lines = len(text.splitlines())
    
    result = {
        "words": words,
        "characters": characters,
        "lines": lines
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
    and basic arithmetic operators (+, -, *, /, ^). All input is validated
    to prevent code injection and ensure only safe mathematical operations.
    
    Args:
        expression: Mathematical expression string (e.g., "2 + 3 * (4 - 1)", "2^3 + 5")
    
    Returns:
        Dictionary with calculation result or error information
        
    Examples:
        calculate("2 + 3")           -> {"success": True, "result": 5}
        calculate("2^3")             -> {"success": True, "result": 8}  
        calculate("(10 + 5) / 3")    -> {"success": True, "result": 5.0}
        calculate("-5 + 3")          -> {"success": True, "result": -2}
    """
    try:
        result = calculator.calculate(expression)
        return add_server_timestamp(result)
    except Exception as e:
        result = {
            "success": False,
            "error": f"Calculator error: {str(e)}",
            "expression": expression
        }
        return add_server_timestamp(result)

@mcp.tool()
def calculate_time_difference(datetime1: str, datetime2: str) -> Dict[str, Any]:
    """
    Calculate the time difference between two datetime strings.
    
    Returns the difference in a human-readable format showing days, hours, 
    minutes, and seconds. Supports various datetime formats including:
    - ISO format: "2025-08-12T14:30:00" or "2025-08-12 14:30:00"
    - Date only: "2025-08-12"
    - Various regional formats: "12/08/2025 14:30", "08/12/2025", "12-08-2025"
    
    Args:
        datetime1: First datetime string (start time)
        datetime2: Second datetime string (end time)
    
    Returns:
        Dictionary with time difference result or error information
        
    Note:
        Result is datetime2 - datetime1, so:
        - Positive result means datetime2 is after datetime1
        - Negative result means datetime2 is before datetime1
        
    Examples:
        calculate_time_difference("2025-08-12 10:00:00", "2025-08-12 15:30:45")
        -> "5 hours, 30 minutes, and 45 seconds"
        
        calculate_time_difference("2025-08-12", "2025-08-15")
        -> "3 days"
    """
    try:
        result = timedelta_calculator.calculate_timedelta(datetime1, datetime2)
        return add_server_timestamp(result)
    except Exception as e:
        result = {
            "success": False,
            "error": f"Timedelta calculator error: {str(e)}",
            "datetime1": datetime1,
            "datetime2": datetime2
        }
        return add_server_timestamp(result)

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
            result = {"error": f"No results found for location: {location}"}
            return add_server_timestamp(result)
        
        formatted_results = []
        for result in results:
            formatted_results.append({
                "name": result.get('name'),
                "country": result.get('country'),
                "state": result.get('state'),
                "latitude": result.get('lat'),
                "longitude": result.get('lon'),
                "local_names": result.get('local_names', {})
            })
        
        result = {
            "query": location,
            "results": formatted_results,
            "count": len(formatted_results)
        }
        return add_server_timestamp(result)
        
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

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
        result = {"error": str(e)}
        return add_server_timestamp(result)



@mcp.tool()
def tool_info(tool_name: str) -> Dict[str, Any]:
    """
    Return detailed documentation for a named tool.

    Call with tool_name="list" to see which tools have extended documentation.

    Args:
        tool_name: Name of the tool (e.g. "tinydb_search_memories"), or "list".
    """
    import os
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
        result = {
            "success": False,
            "error": f"No documentation file found for '{tool_name}'.",
            "available": available,
        }
        return add_server_timestamp(result)

    with open(path, encoding="utf-8") as fh:
        content = fh.read()
    return add_server_timestamp({"success": True, "tool_name": tool_name, "documentation": content})


@mcp.tool()
def memory_workflow_guide() -> Dict[str, Any]:
    """
    Return stored best practices for memory use.

    For full workflow documentation call tool_info("memory_workflow_guide").
    """
    # Get stored best practices from TinyDB memory system
    stored_guidelines = []
    try:
        stored_practices_result = _search_memories_fn(
            category="best_practices",
            limit=20,
        )
        
        if stored_practices_result.get("success") and stored_practices_result.get("memories"):
            for memory in stored_practices_result["memories"]:
                stored_guidelines.append({
                    "guideline": memory.get("content", ""),
                    "importance": memory.get("importance", 3),
                    "tags": memory.get("tags", []),
                    "stored_at": memory.get("created_at", ""),
                    "memory_id": memory.get("id", "")
                })
    except Exception as e:
        stored_guidelines.append({
            "guideline": f"Error retrieving stored practices: {str(e)}",
            "importance": 3,
            "tags": ["error"],
            "stored_at": "",
            "memory_id": ""
        })
    
    result = {
        "success": True,
        "best_practices": stored_guidelines,
    }
    return add_server_timestamp(result)



# =============================================================================
# TINYDB MEMORY TOOLS - High-performance memory management with TinyDB backend
# =============================================================================

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
    try:
        import uuid
        from datetime import datetime
        
        memory_db = get_memory_tinydb()
        try:
            memories_table = memory_db.table('memories')
            
            # Create memory record
            memory_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            
            # Parse tags
            tag_list = [tag.strip().lower() for tag in tags.split(',') if tag.strip()] if tags else []
            
            # Validate category
            category_val = category.strip() if category else None
            
            # Validate expiration
            expires_val = expires_at.strip() if expires_at else None
            if expires_val:
                try:
                    datetime.fromisoformat(expires_val.replace('Z', '+00:00'))
                except ValueError:
                    result = {"error": f"Invalid expiration date format: {expires_val}. Use ISO format."}
                    return add_server_timestamp(result)
            
            # Create memory object with proper timestamps
            memory_data = {
                "id": memory_id,
                "content": content,
                "created_at": now,
                "last_modified": now,
                "tags": tag_list,
                "category": category_val,
                "importance": importance,
                "expires_at": expires_val,
                "metadata": {}
            }
            
            # Store in TinyDB
            memories_table.insert(memory_data)
            
            # Force flush to disk
            memory_db.close()
            
            # Register tags if any
            tag_info = {}
            if tag_list:
                tag_info = tinydb_register_tags(tag_list)
                
            # Update category usage if provided
            if category_val:
                tinydb_update_category_usage(category_val)
            
            result = {
                "success": True,
                "memory_id": memory_id,
                "content": content,
                "created_at": now,
                "last_modified": now,
                "tags": tag_list,
                "category": category_val,
                "importance": importance,
                "expires_at": expires_val,
                "tag_registration": tag_info,
                "message": "Information memorized successfully with TinyDB"
            }
            return add_server_timestamp(result)
        except Exception as e:
            memory_db.close()
            raise e
        
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

@mcp.tool()
def tinydb_recall_memory(memory_id: str) -> Dict[str, Any]:
    """
    Fetch a single memory by its exact ID.

    Use this when you already have a memory_id from a previous search result and
    want its full content without running another search.  For finding memories
    by topic, use tinydb_search_memories instead.

    Args:
        memory_id: The UUID from a previous tinydb_memorize or search result.
    """
    try:
        memory_db = get_memory_tinydb()
        try:
            memories_table = memory_db.table('memories')
            Record = Query()
            
            # Find memory by ID
            results = memories_table.search(Record.id == memory_id)
            
            if results:
                memory = results[0]
                # Check if expired
                if memory.get('expires_at'):
                    from datetime import datetime
                    expiry = datetime.fromisoformat(memory['expires_at'].replace('Z', '+00:00'))
                    if datetime.now() > expiry:
                        memory_db.close()
                        result = {"error": f"Memory {memory_id} has expired"}
                        return add_server_timestamp(result)
                        
                memory_db.close()
                result = {
                    "success": True,
                    "memory": memory
                }
                return add_server_timestamp(result)
            else:
                memory_db.close()
                result = {"error": f"Memory with ID {memory_id} not found"}
                return add_server_timestamp(result)
        except Exception as e:
            memory_db.close()
            raise e
            
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

@mcp.tool()
def tinydb_search_memories(tags: str = "", content_keywords: str = "", category: str = "",
                          limit: int = 50, semantic_search: bool = True,
                          page_size: int = 5,
                          sort_by: str = "relevance") -> Dict[str, Any]:
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
    try:
        from datetime import datetime

        memory_db = get_memory_tinydb()
        try:
            memories_table = memory_db.table('memories')

            # Validate category if provided
            if category:
                category_exists, category_error, existing_categories = check_category_exists(category)
                if not category_exists:
                    memory_db.close()
                    result = {
                        "success": False,
                        "error": category_error,
                        "available_categories": existing_categories,
                    }
                    return add_server_timestamp(result)

            # Load and filter expired memories
            current_time = datetime.now()
            all_memories = []
            for memory in memories_table.all():
                if memory.get('expires_at'):
                    try:
                        expiry = datetime.fromisoformat(memory['expires_at'].replace('Z', '+00:00'))
                        if current_time > expiry:
                            continue
                    except Exception:
                        pass
                all_memories.append(memory)

            memory_db.close()

            # Content keyword filter
            if content_keywords:
                query_words = [w.lower().strip() for w in content_keywords.split() if w.strip()]
                all_memories = [
                    m for m in all_memories
                    if all(w in m['content'].lower() for w in query_words)
                ]

            # Category filter
            if category:
                all_memories = [
                    m for m in all_memories
                    if (m.get('category') or '').lower() == category.strip().lower()
                ]

            # Tag-based scoring (primary) or legacy expansion (fallback)
            scored_method = "none"
            if tags:
                input_tags = [t.strip().lower() for t in tags.split(',') if t.strip()]

                if semantic_search and MEMORY_PACKAGE_AVAILABLE:
                    tag_registry = build_tag_registry()
                    if tag_registry:
                        scored = score_memories_by_tags(input_tags, all_memories, tag_registry)
                        # scored = list of (rank_score, memory, matched_tags)
                        filtered_results = [mem for (_, mem, _) in scored][:limit]
                        scored_method = "tag_scoring"
                    else:
                        # Registry empty — fall back to string expansion
                        expanded = set(input_tags)
                        for t in input_tags:
                            expanded.update(find_similar_tags_internal(t, limit=3, min_similarity=0.4))
                        filter_tags = [t.lower() for t in expanded]
                        filtered_results = [
                            m for m in all_memories
                            if any(ft in m.get('tags', []) for ft in filter_tags)
                        ][:limit]
                        scored_method = "string_expansion"
                else:
                    # Exact tag match
                    filter_tags = input_tags
                    filtered_results = [
                        m for m in all_memories
                        if any(ft in m.get('tags', []) for ft in filter_tags)
                    ][:limit]
                    scored_method = "exact"
            else:
                # No tags — sort by importance then recency
                all_memories.sort(
                    key=lambda x: (x.get('importance', 3), x.get('last_modified') or x.get('timestamp') or ''),
                    reverse=True,
                )
                filtered_results = all_memories[:limit]
                scored_method = "importance"

            # Date sort override — re-order survivors by last_modified / timestamp
            if sort_by in ("date_desc", "date_asc"):
                filtered_results.sort(
                    key=lambda m: m.get('last_modified') or m.get('timestamp') or '',
                    reverse=(sort_by == "date_desc"),
                )
                scored_method = "tag_filter_date_sorted" if tags else "date_sorted"

            total_found = len(filtered_results)
            first_page = filtered_results[:page_size]
            has_more = total_found > page_size

            next_page_token = None
            if has_more and MEMORY_PACKAGE_AVAILABLE:
                next_page_token = save_paginated_results(
                    all_results=filtered_results,
                    page_size=page_size,
                    query_info={
                        "content_keywords": content_keywords, "tags": tags, "category": category,
                        "limit": limit, "semantic_search": semantic_search,
                        "page_size": page_size, "sort_by": sort_by,
                    },
                )

            result = {
                "success": True,
                "memories": first_page,
                "total_found": total_found,
                "returned_count": len(first_page),
                "has_more": has_more,
                "next_page_token": next_page_token,
                "scoring_method": scored_method,
                "search_criteria": {
                    "content_keywords": content_keywords,
                    "tags": tags,
                    "category": category,
                    "limit": limit,
                    "page_size": page_size,
                    "semantic_search": semantic_search,
                    "sort_by": sort_by,
                },
            }
            return add_server_timestamp(result)

        except Exception as e:
            memory_db.close()
            raise e

    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

@mcp.tool()
def tinydb_list_memories(limit: int = 100, page_size: int = 10,
                        category: str = "",
                        sort_by: str = "relevance") -> Dict[str, Any]:
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
    try:
        from datetime import datetime

        memory_db = get_memory_tinydb()
        try:
            memories_table = memory_db.table('memories')
            all_memories = memories_table.all()

            current_time = datetime.now()
            active_memories = []
            for memory in all_memories:
                if memory.get('expires_at'):
                    try:
                        expiry = datetime.fromisoformat(memory['expires_at'].replace('Z', '+00:00'))
                        if current_time > expiry:
                            continue
                    except Exception:
                        pass
                active_memories.append(memory)

            memory_db.close()

            # Category filter
            if category:
                active_memories = [
                    m for m in active_memories
                    if (m.get('category') or '').lower() == category.strip().lower()
                ]

            if sort_by in ("date_desc", "date_asc"):
                active_memories.sort(
                    key=lambda m: m.get('last_modified') or m.get('timestamp') or '',
                    reverse=(sort_by == "date_desc"),
                )
            else:
                active_memories.sort(
                    key=lambda x: (x.get('importance', 3), x.get('last_modified') or x.get('timestamp') or ''),
                    reverse=True,
                )

            capped = active_memories[:limit]
            total_active = len(capped)
            first_page = capped[:page_size]
            has_more = total_active > page_size

            next_page_token = None
            if has_more and MEMORY_PACKAGE_AVAILABLE:
                next_page_token = save_paginated_results(
                    all_results=capped,
                    page_size=page_size,
                    query_info={"limit": limit, "page_size": page_size,
                                "category": category, "sort_by": sort_by},
                )

            result = {
                "success": True,
                "memories": first_page,
                "total_active": total_active,
                "returned_count": len(first_page),
                "has_more": has_more,
                "next_page_token": next_page_token,
                "search_criteria": {
                    "category": category,
                    "sort_by": sort_by,
                    "limit": limit,
                    "page_size": page_size,
                },
            }
            return add_server_timestamp(result)

        except Exception as e:
            memory_db.close()
            raise e

    except Exception as e:
        result = {"error": str(e)}
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
    if not MEMORY_PACKAGE_AVAILABLE:
        result = {"error": "Memory package not available — pagination requires the memory module."}
        return add_server_timestamp(result)
    try:
        result = get_next_page(next_page_token)
        return add_server_timestamp(result)
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)


# Helper functions for TinyDB memory system
def tinydb_register_tags(tag_list: List[str]) -> Dict[str, Any]:
    """Register tags in TinyDB tags database with embeddings."""
    try:
        from datetime import datetime
        tags_db = get_tags_tinydb()
        try:
            tags_table = tags_db.table('tags')
            Record = Query()
            
            registered = []
            for tag in tag_list:
                # Check if tag already exists
                existing = tags_table.search(Record.tag == tag)
                if existing:
                    # Update usage count
                    tags_table.update(
                        {'usage_count': existing[0]['usage_count'] + 1,
                         'last_used_at': datetime.now().isoformat()},
                        Record.tag == tag
                    )
                    registered.append(f"Updated: {tag}")
                else:
                    # Create new tag entry
                    tag_data = {
                        'tag': tag,
                        'usage_count': 1,
                        'created_at': datetime.now().isoformat(),
                        'last_used_at': datetime.now().isoformat(),
                        'embedding': []  # Will be populated by embedding system
                    }
                    tags_table.insert(tag_data)
                    registered.append(f"Created: {tag}")
                    
            # Force flush to disk
            tags_db.close()
            return {"registered_tags": registered}
        except Exception as e:
            tags_db.close()
            raise e
        
    except Exception as e:
        return {"error": f"Tag registration failed: {str(e)}"}

def tinydb_update_category_usage(category: str) -> None:
    """Update category usage statistics in TinyDB."""
    try:
        from datetime import datetime
        categories_db = get_categories_tinydb()
        try:
            categories_table = categories_db.table('categories')
            Record = Query()
            
            existing = categories_table.search(Record.category == category)
            if existing:
                categories_table.update(
                    {'usage_count': existing[0]['usage_count'] + 1,
                     'last_used_at': datetime.now().isoformat()},
                    Record.category == category
                )
            else:
                category_data = {
                    'category': category,
                    'usage_count': 1,
                    'created_at': datetime.now().isoformat(),
                    'last_used_at': datetime.now().isoformat()
                }
                categories_table.insert(category_data)
                
            # Force flush to disk
            categories_db.close()
        except Exception:
            categories_db.close()
            
    except Exception:
        pass  # Non-critical operation

@mcp.tool()
def tinydb_update_memory(memory_id: str, content: str = "", tags: str = "",
                        category: str = "", importance: int = 0, expires_at: str = "") -> Dict[str, Any]:
    """
    Modify an existing memory in place.

    Only the fields you supply are changed; omit a parameter to leave it unchanged.
    Updating tags is particularly important: if a memory is hard to find, the most
    effective fix is to add better tags rather than rewriting the content.

    Args:
        memory_id: ID from a previous search or memorize result.
        content: Replacement text (leave empty to keep current content).
        tags: Replacement tag list, comma-separated (leave empty to keep current tags).
        category: New category (leave empty to keep current).
        importance: New importance 1-5 (pass 0 to keep current).
        expires_at: New expiry in ISO format (leave empty to keep current).
    """
    result = _tinydb_update_memory_impl(
        memory_id=memory_id, content=content, tags=tags,
        category=category, importance=importance, expires_at=expires_at,
    )
    return add_server_timestamp(result)

@mcp.tool()
def tinydb_delete_memory(memory_id: str) -> Dict[str, Any]:
    """
    Permanently delete a memory by ID.

    Prefer updating over deleting when the information is partly correct —
    adjust the content or tags rather than removing the record.  Use deletion for
    information that is entirely outdated or was stored in error.

    Args:
        memory_id: ID from a previous search or memorize result.
    """
    result = _tinydb_delete_memory_impl(memory_id=memory_id)
    return add_server_timestamp(result)


@mcp.tool()
def tinydb_get_memory_categories() -> Dict[str, Any]:
    """
    List all categories that have been used, plus suggested standard categories.

    Categories are a broad secondary axis for organising memories ("projects",
    "preferences", "user_context", "facts", …).  Tags are the primary retrieval
    mechanism; categories are most useful as a coarse filter on top of tag search.

    Call this before passing a category argument to tinydb_search_memories to
    confirm the exact spelling of available categories.
    """
    try:
        categories_db = get_categories_tinydb()
        categories_table = categories_db.table('categories')
        
        all_categories = categories_table.all()
        
        # Sort by usage count (most used first)
        sorted_categories = sorted(all_categories, key=lambda x: x.get('usage_count', 0), reverse=True)
        
        # Prepare suggested categories (same as legacy system)
        suggested = [
            {
                "name": "user_context",
                "description": "Information about the user's location, profession, interests, and personal details"
            },
            {
                "name": "preferences", 
                "description": "How information should be presented, preferred tools and methods"
            },
            {
                "name": "projects",
                "description": "Ongoing work, previous discussions, and project-specific details"
            },
            {
                "name": "learnings",
                "description": "Things learned about the user's specific situation and needs"
            },
            {
                "name": "corrections",
                "description": "When initial assumptions or responses were incorrect"
            },
            {
                "name": "facts",
                "description": "Important factual information that should be remembered"
            },
            {
                "name": "reminders", 
                "description": "Things to remember for future interactions"
            },
            {
                "name": "best_practices",
                "description": "Guidelines, procedures, and effective methods to follow"
            }
        ]
        
        result = {
            "success": True,
            "existing_categories": sorted_categories,
            "suggested_categories": suggested,
            "total_categories": len(all_categories)
        }
        return add_server_timestamp(result)
        
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

@mcp.tool()
def tinydb_find_similar_tags(query: str, limit: int = 5, min_similarity: float = 0.3) -> Dict[str, Any]:
    """
    Find existing tags whose meaning is close to a concept you describe.

    Call this before searching or storing when you are unsure which tags are
    already in the memory store.  It bridges vocabulary gaps: if memories were
    stored with "timetabling" and you would naturally search for "scheduling",
    this tool reveals the mismatch so you can use the right tag.

    Two uses:
      BEFORE SEARCHING  — discover which tags to pass to tinydb_search_memories.
      BEFORE STORING    — reuse existing tags rather than creating near-duplicates,
                          which keeps the tag space clean and retrieval accurate.

    Args:
        query: A word, phrase, or concept to match against existing tags.
        limit: Maximum results to return (default 5).
        min_similarity: Minimum similarity threshold 0.0–1.0 (default 0.3).
    """
    try:
        tags_db = get_tags_tinydb()
        tags_table = tags_db.table('tags')
        
        # For now, return a simple text-based similarity search
        # This can be enhanced with actual vector embeddings later
        all_tags = tags_table.all()
        
        if not all_tags:
            result = {
                "success": True,
                "similar_tags": [],
                "message": "No tags found in database"
            }
            return add_server_timestamp(result)
        
        query_lower = query.lower().strip()
        similar_tags = []
        
        for tag_entry in all_tags:
            tag = tag_entry.get('tag', '')
            # Simple similarity based on substring matching and usage
            similarity = 0.0
            
            if query_lower in tag.lower():
                similarity = 0.8
            elif any(word in tag.lower() for word in query_lower.split()):
                similarity = 0.6
            elif any(word in query_lower for word in tag.lower().split()):
                similarity = 0.4
                
            if similarity >= min_similarity:
                similar_tags.append({
                    "tag": tag,
                    "similarity": similarity,
                    "usage_count": tag_entry.get('usage_count', 0),
                    "last_used": tag_entry.get('last_used_at', '')
                })
        
        # Sort by similarity first, then usage count
        similar_tags.sort(key=lambda x: (x['similarity'], x['usage_count']), reverse=True)
        
        result = {
            "success": True,
            "query": query,
            "similar_tags": similar_tags[:limit],
            "total_found": len(similar_tags)
        }
        return add_server_timestamp(result)
        
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

@mcp.tool()
def tinydb_get_all_tags(cap: int=100) -> Dict[str, Any]:
    """
    Return every tag in the memory store, sorted by how often it has been used.

    Use carefully - there might be a lot of tags in the system - and for this
    reason it's capped at 100 by default. High-usage tags are the most reliable search
    keys. Prefer tinydb_find_similar_tags to narrow down to a specific concept instead.

    Args:
        cap: any integer value, where 0 means uncapped (return all)
    """
    try:
        tags_db = get_tags_tinydb()
        tags_table = tags_db.table('tags')
        
        all_tags = tags_table.all()
        
        # Sort by usage count (most used first)
        sorted_tags = sorted(all_tags, key=lambda x: x.get('usage_count', 0), reverse=True)
        
        # Format for display
        formatted_tags = []
        for tag_entry in sorted_tags:
            formatted_tags.append({
                "tag": tag_entry.get('tag', ''),
                "usage_count": tag_entry.get('usage_count', 0),
                "created_at": tag_entry.get('created_at', ''),
                "last_used_at": tag_entry.get('last_used_at', '')
            })

        if cap and formatted_tags:
            formatted_tags = formatted_tags[:cap]
        
        result = {
            "success": True,
            "tags": formatted_tags,
            "total_tags": len(formatted_tags)
        }
        return add_server_timestamp(result)
        
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

# =============================================================================
# GENERIC TINYDB TOOLS - Work with any TinyDB database in data folder
# =============================================================================

@mcp.tool()
def tinydb_create_database(db_name: str, description: str = "") -> Dict[str, Any]:
    """
    Create a new TinyDB database file in the data folder.
    
    Perfect for expense tracking, research notes, project data, etc.
    Much faster than LLM-based JSON file updates.
    
    Args:
        db_name: Name of the database (will add .json if needed)
        description: Optional description of the database purpose
        
    Returns:
        Dictionary with database creation confirmation
    """
    try:
        from datetime import datetime
        
        # Create the database (this initializes the file)
        custom_db = get_custom_tinydb(db_name)
        
        # Store metadata about the database
        metadata_table = custom_db.table('_metadata')
        metadata_table.insert({
            "database_name": db_name,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "created_by": "tinydb_create_database"
        })
        
        result = {
            "success": True,
            "database_name": db_name,
            "database_file": f"{db_name}.json" if not db_name.endswith('.json') else db_name,
            "description": description,
            "message": "Database created successfully"
        }
        return add_server_timestamp(result)
        
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

@mcp.tool() 
def store_workspace_file(filename: str, content: str, description: str = "",
                        tags: str = "", language: str = "", overwrite: bool = False) -> Dict[str, Any]:
    """
    Store a text file in the configured workspace directory.
    
    The workspace location is set via FIRST_MCP_WORKSPACE_PATH environment variable.
    This allows Claude to persist text content across sessions in a user-controlled location.
    
    Args:
        filename: Name of the file to store (e.g., "notes.txt", "script.py")
        content: Text content to store in the file
        description: Optional description of the file's purpose
        tags: Comma-separated tags for categorization (e.g., "notes,important,draft")
        language: Programming language or content type. For multiple languages/types, separate with "/" 
                 (e.g., "python", "javascript", "markdown/norwegian", "html/css", "text/english")
        overwrite: Whether to overwrite existing files (default: False)
    
    Returns:
        Dictionary with storage result and file information
    """
    try:
        # Parse tags from comma-separated string
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
        
        result = workspace_manager.store_text_file(
            filename=filename,
            content=content,
            description=description.strip() if description else "",
            tags=tag_list,
            language=language.strip() if language else "",
            overwrite=overwrite
        )
        
        return add_server_timestamp(result)
        
    except Exception as e:
        result = {"error": str(e)}
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
        result = {"error": str(e)}
        return add_server_timestamp(result)

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
            filename=filename,
            mode=mode,
            content=content,
            anchor=anchor
        )
        return add_server_timestamp(result)
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

@mcp.tool()
def list_workspace_files(filter_tags: str = "") -> Dict[str, Any]:
    """
    List all files in the workspace directory with their metadata.
    
    Args:
        filter_tags: Optional comma-separated tags to filter by (e.g., "notes,draft")
    
    Returns:
        Dictionary with list of files and their information
    """
    try:
        # Parse filter tags
        tag_filter = [tag.strip() for tag in filter_tags.split(",") if tag.strip()] if filter_tags else None
        
        result = workspace_manager.list_workspace_files(filter_tags=tag_filter)
        return add_server_timestamp(result)
        
    except Exception as e:
        result = {"error": str(e)}
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
        result = {"error": str(e)}
        return add_server_timestamp(result)

@mcp.tool()
def update_workspace_file_metadata(filename: str, description: str = "",
                                  tags: str = "", language: str = "") -> Dict[str, Any]:
    """
    Update metadata (description, tags, and language) for an existing workspace file.
    
    Args:
        filename: Name of the file to update
        description: New description (leave empty to keep existing)
        tags: New comma-separated tags (leave empty to keep existing)
        language: New language/content type. For multiple languages/types, separate with "/" 
                 (e.g., "python", "javascript", "markdown/norwegian", "html/css", "text/english")
                 Leave empty to keep existing language setting.
    
    Returns:
        Dictionary with update result
    """
    try:
        # Parse tags from comma-separated string
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else None
        description_val = description.strip() if description.strip() else None
        language_val = language.strip() if language.strip() else None
        
        result = workspace_manager.update_file_metadata(
            filename=filename,
            description=description_val,
            tags=tag_list,
            language=language_val
        )
        return add_server_timestamp(result)
        
    except Exception as e:
        result = {"error": str(e)}
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
        result = {"error": str(e)}
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

@mcp.tool()
def get_calendar(year: int, month: int) -> Dict[str, Any]:
    """
    Get a calendar for a specified year and month in both HTML and text formats.
    
    The HTML format provides structured data that's easier for LLMs to parse and understand,
    while the text format provides a human-readable fallback.
    
    Args:
        year: The year (e.g., 2025)
        month: The month (1-12, where 1=January, 12=December)
    
    Returns:
        Dictionary with calendar in HTML format, plain text, and metadata
    """
    import calendar
    from datetime import datetime
    
    try:
        # Validate inputs
        if not (1 <= month <= 12):
            result = {"error": "Month must be between 1 and 12"}
            return add_server_timestamp(result)
        
        if year < 1:
            result = {"error": "Year must be positive"}
            return add_server_timestamp(result)
        
        # Create HTML calendar
        html_cal = calendar.HTMLCalendar(firstweekday=0)  # 0=Monday
        calendar_html = html_cal.formatmonth(year, month)
        
        # Also generate plain text for fallback
        cal_text = calendar.month(year, month)
        
        # Get month name
        month_name = calendar.month_name[month]
        
        # Get additional info
        month_abbr = calendar.month_abbr[month]
        days_in_month = calendar.monthrange(year, month)[1]
        first_weekday = calendar.monthrange(year, month)[0]  # 0=Monday, 6=Sunday
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        first_weekday_name = weekday_names[first_weekday]
        
        # Check if it's a leap year
        is_leap_year = calendar.isleap(year)
        
        # Get current date info for context
        today = datetime.now()
        is_current_month = (today.year == year and today.month == month)
        current_day = today.day if is_current_month else None
        
        result = {
            "success": True,
            "year": year,
            "month": month,
            "month_name": month_name,
            "month_abbreviation": month_abbr,
            "calendar_html": calendar_html,
            "calendar_text": cal_text,
            "days_in_month": days_in_month,
            "first_day_of_month": first_weekday_name,
            "is_leap_year": is_leap_year,
            "is_current_month": is_current_month,
            "current_day": current_day,
            "format_note": "calendar_html provides structured data for easy parsing; calendar_text is human-readable fallback"
        }
        return add_server_timestamp(result)
        
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

@mcp.tool()
def get_day_of_week(date_string: str) -> Dict[str, Any]:
    """
    Get the day of the week for a given date in ISO format (YYYY-MM-DD).
    
    Args:
        date_string: Date in ISO format (e.g., "2025-08-09", "2024-12-25")
    
    Returns:
        Dictionary with weekday information and metadata
    """
    from datetime import datetime
    
    try:
        # Parse the date string
        try:
            date_obj = datetime.strptime(date_string, "%Y-%m-%d")
        except ValueError:
            result = {"error": f"Invalid date format. Use YYYY-MM-DD format (e.g., '2025-08-09')"}
            return add_server_timestamp(result)
        
        # Get weekday information
        weekday_number = date_obj.weekday()  # 0=Monday, 6=Sunday
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        weekday_name = weekday_names[weekday_number]
        
        # Additional information
        weekday_abbr = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][weekday_number]
        is_weekend = weekday_number >= 5  # Saturday=5, Sunday=6
        is_weekday = not is_weekend
        
        # Context information
        today = datetime.now().date()
        is_today = date_obj.date() == today
        is_past = date_obj.date() < today
        is_future = date_obj.date() > today
        
        result = {
            "success": True,
            "date": date_string,
            "weekday_name": weekday_name,
            "weekday_abbreviation": weekday_abbr,
            "weekday_number": weekday_number,
            "is_weekend": is_weekend,
            "is_weekday": is_weekday,
            "is_today": is_today,
            "is_past": is_past,
            "is_future": is_future,
            "year": date_obj.year,
            "month": date_obj.month,
            "day": date_obj.day
        }
        return add_server_timestamp(result)
        
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

@mcp.tool()
def tinydb_store_data(db_name: str, table: str, data: Dict[str, Any], record_id: str = "") -> Dict[str, Any]:
    """
    Store data in any TinyDB database in the data folder.
    
    Perfect for expense tracking, research notes, project data, etc.
    Much faster than LLM-based JSON file updates.
    
    Args:
        db_name: Name of the database file
        table: Table name within the database
        data: Data to store (dictionary)
        record_id: Optional specific ID for the record
        
    Returns:
        Dictionary with storage confirmation and record ID
    """
    try:
        import uuid
        from datetime import datetime
        
        custom_db = get_custom_tinydb(db_name)
        try:
            table_db = custom_db.table(table)
            Record = Query()
            
            if record_id:
                # Update existing record or create with specific ID
                existing = table_db.search(Record.id == record_id)
                if existing:
                    table_db.update(data, Record.id == record_id)
                    action = "updated"
                else:
                    data['id'] = record_id
                    table_db.insert(data)
                    action = "created"
            else:
                # Create new record with generated ID
                record_id = str(uuid.uuid4())
                data['id'] = record_id
                table_db.insert(data)
                action = "created"
            
            custom_db.close()
            
            result = {
                "success": True,
                "database": db_name,
                "table": table,
                "record_id": record_id,
                "action": action,
                "data": data
            }
            return add_server_timestamp(result)
            
        except Exception as e:
            custom_db.close()
            raise e
        
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

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
    try:
        custom_db = get_custom_tinydb(db_name)
        try:
            table_db = custom_db.table(table)
            Record = Query()
            
            # Build query
            if query_conditions:
                query = None
                for field, value in query_conditions.items():
                    condition = Record[field] == value
                    if query is None:
                        query = condition
                    else:
                        query = query & condition
                        
                results = table_db.search(query)
            else:
                results = table_db.all()
            
            # Sort results if specified
            if sort_by and results:
                results.sort(key=lambda x: x.get(sort_by, ''), reverse=reverse_sort)
            
            # Apply limit
            limited_results = results[:limit]
            
            custom_db.close()
            
            result = {
                "success": True,
                "database": db_name,
                "table": table,
                "query_conditions": query_conditions,
                "results": limited_results,
                "total_found": len(results),
                "returned_count": len(limited_results)
            }
            return add_server_timestamp(result)
            
        except Exception as e:
            custom_db.close()
            raise e
        
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

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
    try:
        custom_db = get_custom_tinydb(db_name)
        try:
            table_db = custom_db.table(table)
            Record = Query()
            
            # Perform update
            updated = table_db.update(updates, Record.id == record_id)
            
            if updated:
                # Get updated record
                updated_record = table_db.search(Record.id == record_id)[0]
                custom_db.close()
                result = {
                    "success": True,
                    "database": db_name,
                    "table": table,
                    "record_id": record_id,
                    "updated_fields": list(updates.keys()),
                    "updated_record": updated_record
                }
                return add_server_timestamp(result)
            else:
                custom_db.close()
                result = {"error": f"No record found with ID {record_id} in table {table}"}
                return add_server_timestamp(result)
                
        except Exception as e:
            custom_db.close()
            raise e
            
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

@mcp.tool()
def tinydb_delete_data(db_name: str, table: str, record_id: str = "", query_conditions: Dict[str, Any] = {}) -> Dict[str, Any]:
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
    try:
        custom_db = get_custom_tinydb(db_name)
        try:
            table_db = custom_db.table(table)
            Record = Query()
            
            if record_id:
                # Delete specific record by ID
                deleted_count = len(table_db.remove(Record.id == record_id))
                operation_type = "single_record"
            elif query_conditions:
                # Delete records matching conditions
                query = None
                for field, value in query_conditions.items():
                    condition = Record[field] == value
                    if query is None:
                        query = condition
                    else:
                        query = query & condition
                
                deleted_count = len(table_db.remove(query))
                operation_type = "bulk_deletion"
            else:
                custom_db.close()
                result = {"error": "Must provide either record_id or query_conditions"}
                return add_server_timestamp(result)
            
            custom_db.close()
            
            result = {
                "success": True,
                "database": db_name,
                "table": table,
                "operation_type": operation_type,
                "deleted_count": deleted_count
            }
            return add_server_timestamp(result)
            
        except Exception as e:
            custom_db.close()
            raise e
        
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

@mcp.tool()
def tinydb_list_databases() -> Dict[str, Any]:
    """
    List all TinyDB databases in the data folder.
    
    Shows dedicated databases (memories, tags, categories) and user-created databases.
    
    Returns:
        Dictionary with all available databases and their information
    """
    try:
        import os
        import glob
        
        base_path = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
        
        # Find all JSON files in data path
        json_pattern = os.path.join(base_path, '*.json')
        json_files = glob.glob(json_pattern)
        
        databases = []
        for json_file in json_files:
            filename = os.path.basename(json_file)
            
            # Skip legacy files and workspace metadata
            if filename.startswith('memory_') or filename == '.workspace_metadata.json':
                continue
                
            db_info = {
                "database_name": filename.replace('.json', ''),
                "database_file": filename,
                "file_size": os.path.getsize(json_file),
                "modified_time": os.path.getmtime(json_file)
            }
            
            # Add type classification
            if filename in ['tinydb_memories.json', 'tinydb_tags.json', 'tinydb_categories.json']:
                db_info["type"] = "dedicated_memory_system"
            elif filename == 'mcp_database.json':
                db_info["type"] = "legacy_generic_database"
            else:
                db_info["type"] = "user_created_database"
                
            # Try to get table count
            try:
                temp_db = get_custom_tinydb(filename.replace('.json', ''))
                db_info["table_count"] = len(temp_db.tables())
                temp_db.close()
            except:
                db_info["table_count"] = 0
                
            databases.append(db_info)
        
        # Sort by type and name
        databases.sort(key=lambda x: (x["type"], x["database_name"]))
        
        result = {
            "success": True,
            "databases": databases,
            "total_databases": len(databases),
            "data_path": base_path
        }
        return add_server_timestamp(result)
        
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)

@mcp.tool()
def tinydb_get_database_info(db_name: str) -> Dict[str, Any]:
    """
    Get comprehensive information about a specific TinyDB database.
    
    Args:
        db_name: Name of the database to inspect
        
    Returns:
        Dictionary with detailed database information
    """
    try:
        import os
        from datetime import datetime
        
        custom_db = get_custom_tinydb(db_name)
        
        # Get basic database info
        base_path = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
        db_file = f"{db_name}.json" if not db_name.endswith('.json') else db_name
        db_path = os.path.join(base_path, db_file)
        
        info = {
            "database_name": db_name,
            "database_file": db_file,
            "database_path": db_path,
            "file_exists": os.path.exists(db_path)
        }
        
        if info["file_exists"]:
            info["file_size"] = os.path.getsize(db_path)
            info["file_size_mb"] = round(info["file_size"] / (1024 * 1024), 2)
            info["modified_time"] = datetime.fromtimestamp(os.path.getmtime(db_path)).isoformat()
        
        # Get table information
        tables = []
        total_records = 0
        
        for table_name in custom_db.tables():
            table_db = custom_db.table(table_name)
            record_count = len(table_db.all())
            total_records += record_count
            
            table_info = {
                "table_name": table_name,
                "record_count": record_count
            }
            
            # Get sample record if available
            if record_count > 0:
                sample_record = table_db.all()[0]
                # Remove large values for preview
                sample_preview = {}
                for key, value in sample_record.items():
                    if isinstance(value, str) and len(value) > 100:
                        sample_preview[key] = value[:97] + "..."
                    else:
                        sample_preview[key] = value
                table_info["sample_record"] = sample_preview
                
            tables.append(table_info)
        
        custom_db.close()
        
        info.update({
            "tables": tables,
            "table_count": len(tables),
            "total_records": total_records
        })
        
        result = {
            "success": True,
            **info
        }
        return add_server_timestamp(result)
        
    except Exception as e:
        result = {"error": str(e)}
        return add_server_timestamp(result)







def check_and_initialize_fresh_install():
    """Check if this is a fresh install and initialize with session-start preferences."""
    try:
        import uuid
        from datetime import datetime
        memory_db = get_memory_tinydb()
        memories_table = memory_db.table('memories')
        
        # Check if database is empty (fresh install)
        if len(memories_table.all()) == 0:
            print("✓ Fresh installation detected - initializing with session preferences", file=sys.stderr)
            
            session_guide = """SESSION INITIALIZATION GUIDE - Essential for optimal MCP server usage:

1. SEARCH SESSION PREFERENCES: Use tinydb_search_memories with tags='session-start' to load your behavioral preferences
2. LOAD WORKSPACE CONTEXT: Read key workspace files (like general-instructions.md) to understand current context  
3. SEMANTIC SEARCH: When searching memories, use English search terms for best results regardless of conversation language
4. TOOL-FIRST APPROACH: Proactively use available MCP tools rather than providing general responses
5. WORKFLOW ADHERENCE: Follow established patterns from memory rather than improvising

CRITICAL SEARCH TIP: Memory database content is stored in English. Always use English search terms for optimal results, even when conversing in Norwegian or other languages.

This memory serves as your initialization checklist. Search for 'session-start' tagged memories at the beginning of each session for personalized assistant behavior."""
            
            # Store the initialization guide using raw function call
            memory_id = str(uuid.uuid4())
            memory_entry = {
                "id": memory_id,
                "content": session_guide,
                "tags": "session-start,initialization,workflow",
                "category": "preferences",
                "importance": 5,
                "created_at": datetime.now().isoformat(),
                "expires_at": "",
                "is_active": True
            }
            
            # Insert directly into database
            doc_id = memories_table.insert(memory_entry)
            
            # Also update tag database
            tag_list = ["session-start", "initialization", "workflow"]
            tags_db = get_tags_tinydb()
            tags_table = tags_db.table('tags')
            
            Tag = Query()
            for tag in tag_list:
                if not tags_table.search(Tag.tag == tag):
                    tags_table.insert({
                        "tag": tag,
                        "count": 1,
                        "last_used": datetime.now().isoformat()
                    })
                else:
                    existing_count = tags_table.search(Tag.tag == tag)[0]["count"]
                    tags_table.update(
                        {"count": existing_count + 1,
                         "last_used": datetime.now().isoformat()},
                        Tag.tag == tag
                    )
            
            tags_db.close()
            result = {"success": True, "memory_id": memory_id}
            
            if result.get("success"):
                print("✓ Session initialization guide stored successfully", file=sys.stderr)
            else:
                print("✗ Failed to store session guide:", result.get("error"), file=sys.stderr)
        
        memory_db.close()
        
    except Exception as e:
        print(f"✗ Fresh install initialization failed: {e}", file=sys.stderr)

@mcp.tool()
def compute_text_similarity(
    query: str,
    text: str,
    context: str = "",
    text_weight: float = 0.7,
    context_weight: float = 0.3
) -> Dict[str, Any]:
    """
    Compute semantic similarity between a query and a text, with optional context weighting.

    Returns a cosine similarity score in [0.0, 1.0]. When context is provided,
    the text and context embeddings are blended (weighted sum, then re-normalized)
    before comparison — so the text is evaluated in light of its surrounding context
    while still being the primary focus.

    Useful for:
    - Simple query vs. text comparison (no context)
    - Matching a semantic label against a passage situated within a larger text
      (e.g. comparing a tag like "grace_follows_faith" against a verse within its pericope)

    Requires GOOGLE_API_KEY environment variable.

    Args:
        query: Reference text or semantic label to compare against
        text: Primary text to evaluate (e.g. a verse or sentence)
        context: Optional surrounding context (e.g. a pericope). Ignored if empty.
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

    Embeds the query and each candidate, then returns them sorted by
    descending cosine similarity. Useful for finding the most relevant
    option from a set of alternatives.

    Requires GOOGLE_API_KEY environment variable.

    Args:
        query: Reference text to compare against
        candidates: List of texts to rank (order does not matter)

    Returns:
        Dictionary with candidates ranked by descending similarity score
    """
    result = _rank_texts_by_similarity(query, candidates)
    return add_server_timestamp(result)


def main():
    """Main entry point for the MCP server."""
    print("Starting First MCP Server...", file=sys.stderr)
    print(f"Python executable: {sys.executable}", file=sys.stderr)
    print(f"Current directory: {os.getcwd()}", file=sys.stderr)
    
    # Check for fresh install and initialize if needed
    check_and_initialize_fresh_install()

    # Clean up paginated temp files from any previous session
    if MEMORY_PACKAGE_AVAILABLE:
        from .memory.pagination import cleanup_paginated_files as _cleanup_paginated
        cleaned = _cleanup_paginated()
        if cleaned:
            print(f"✓ Cleaned {cleaned} stale paginated temp file(s)", file=sys.stderr)

    # Migrate tag embeddings if the embedding model has changed
    if MEMORY_PACKAGE_AVAILABLE:
        from .memory.tag_tools import check_and_migrate_tag_embeddings
        migration = check_and_migrate_tag_embeddings()
        if migration.get("action") == "migrated":
            print(
                f"✓ Tag embeddings migrated: {migration.get('updated', 0)} updated "
                f"({migration.get('previous_model')} -> {migration.get('embedding_model')})",
                file=sys.stderr
            )
        elif migration.get("action") == "none":
            print(f"✓ Tag embeddings current ({migration.get('reason', '')})", file=sys.stderr)

    # Run the MCP server
    mcp.run(transport="stdio")

if __name__ == "__main__":
    import sys
    
    # Check for debug flag
    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        print("=== DEBUG MODE ===", file=sys.stderr)
        
        try:
            print("Testing imports...", file=sys.stderr)
            from fastmcp import FastMCP
            print("✓ FastMCP import OK", file=sys.stderr)
            
            from .weather import WeatherAPI, GeocodingAPI
            print("✓ Weather imports OK", file=sys.stderr)
            
            from .fileio import WorkspaceManager
            print("✓ WorkspaceManager import OK", file=sys.stderr)
            
            print("Testing manager initialization...", file=sys.stderr)
            workspace_test = WorkspaceManager()
            print("✓ WorkspaceManager init OK", file=sys.stderr)
            
            print("Testing MCP server creation...", file=sys.stderr)
            mcp_test = FastMCP("Debug Test Server")
            print("✓ MCP server creation OK", file=sys.stderr)
            
            print("Testing calendar functionality...", file=sys.stderr)
            import calendar
            from datetime import datetime
            
            # Test calendar functionality directly (not through MCP wrapper)
            today = datetime.now()
            try:
                # Test calendar module imports and basic functionality
                html_cal = calendar.HTMLCalendar(firstweekday=0)
                calendar_html = html_cal.formatmonth(today.year, today.month)
                cal_text = calendar.month(today.year, today.month)
                month_name = calendar.month_name[today.month]
                days_in_month = calendar.monthrange(today.year, today.month)[1]
                
                print(f"✓ Calendar test OK - Generated {month_name} {today.year}", file=sys.stderr)
                print(f"  - HTML calendar: {len(calendar_html)} chars", file=sys.stderr)
                print(f"  - Text calendar: {len(cal_text)} chars", file=sys.stderr)
                print(f"  - Days in month: {days_in_month}", file=sys.stderr)
                print(f"  - Calendar module working correctly", file=sys.stderr)
                
            except Exception as cal_error:
                print(f"✗ Calendar test failed: {cal_error}", file=sys.stderr)
                raise Exception(f"Calendar test failed: {cal_error}")
            
            print("Testing weekday functionality...", file=sys.stderr)
            try:
                # Test weekday lookup with current date
                today_str = today.strftime("%Y-%m-%d")
                test_date = datetime.strptime(today_str, "%Y-%m-%d")
                weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                expected_weekday = weekday_names[test_date.weekday()]
                
                print(f"✓ Weekday test OK - {today_str} is {expected_weekday}", file=sys.stderr)
                print(f"  - Date parsing working correctly", file=sys.stderr)
                print(f"  - Weekday calculation working correctly", file=sys.stderr)
                
                # Test some known dates for validation
                test_cases = [
                    ("2025-01-01", "Wednesday"),  # New Year 2025
                    ("2024-12-25", "Wednesday"),  # Christmas 2024
                ]
                
                for test_date_str, expected_day in test_cases:
                    test_obj = datetime.strptime(test_date_str, "%Y-%m-%d")
                    actual_day = weekday_names[test_obj.weekday()]
                    if actual_day == expected_day:
                        print(f"  ✓ {test_date_str} = {actual_day} (correct)", file=sys.stderr)
                    else:
                        print(f"  ✗ {test_date_str} = {actual_day} (expected {expected_day})", file=sys.stderr)
                        raise Exception(f"Weekday calculation error for {test_date_str}")
                
            except Exception as day_error:
                print(f"✗ Weekday test failed: {day_error}", file=sys.stderr)
                raise Exception(f"Weekday test failed: {day_error}")
            
            print("=== ALL TESTS PASSED ===", file=sys.stderr)
            print("Run without --debug flag to start normally", file=sys.stderr)
            
        except Exception as e:
            print(f"✗ DEBUG ERROR: {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)
    else:
        try:
            main()
        except Exception as e:
            print(f"Error starting MCP server: {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.exit(1) 