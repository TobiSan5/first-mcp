"""
First MCP Server - A minimal example with basic tools
"""

from fastmcp import FastMCP
# import json
import os
import sys
from typing import List, Dict, Any, Optional, Union
from weather import WeatherAPI, GeocodingAPI
from fileio import WorkspaceManager
from calculate import Calculator, TimedeltaCalculator

# Always import TinyDB components for fallback functions
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

# Import memory system components
try:
    # Try to import from the memory package if available
    from src.first_mcp.memory import (
        get_memory_tinydb, get_tags_tinydb, get_categories_tinydb, get_custom_tinydb,
        tinydb_memorize, tinydb_recall_memory, tinydb_search_memories, 
        tinydb_list_memories, tinydb_update_memory, tinydb_delete_memory,
        tinydb_memory_stats, tinydb_get_memory_categories, memory_workflow_guide,
        tinydb_find_similar_tags, tinydb_get_all_tags,
        find_similar_tags_internal, check_category_exists,
        tinydb_create_database, tinydb_store_data, tinydb_query_data,
        tinydb_update_data, tinydb_delete_data, tinydb_list_databases,
        tinydb_get_database_info
    )
    MEMORY_PACKAGE_AVAILABLE = True
except ImportError:
    # Fallback: use legacy inline implementation
    MEMORY_PACKAGE_AVAILABLE = False

# Create the MCP server
mcp = FastMCP(name="First MCP Server")

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
def hello_world(name: str = "World") -> str:
    """
    A simple greeting tool.
    
    Args:
        name: The name to greet (default: "World")
    
    Returns:
        A friendly greeting message
    """
    return f"Hello, {name}! This is your first MCP server."

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
    
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "current_directory": os.getcwd(),
        "python_executable": sys.executable,
        "memory_storage_path": memory_data_path,
        "memory_storage_configured": os.getenv('FIRST_MCP_DATA_PATH') is not None,
        "workspace_path": workspace_path,
        "workspace_configured": os.getenv('FIRST_MCP_WORKSPACE_PATH') is not None
    }

@mcp.tool()
def count_words(text: str) -> Dict[str, int]:
    """
    Count words and characters in a text.
    
    Args:
        text: The text to analyze
    
    Returns:
        Dictionary with word count, character count, and line count
    """
    if not text:
        return {"words": 0, "characters": 0, "lines": 0}
    
    words = len(text.split())
    characters = len(text)
    lines = len(text.splitlines())
    
    return {
        "words": words,
        "characters": characters,
        "lines": lines
    }

@mcp.tool()
def now() -> str:
    """
    Get the current date and time in ISO format with timezone info.
    
    Returns:
        Current datetime as ISO-formatted string with timezone
    """
    from datetime import datetime
    return datetime.now().astimezone().isoformat()

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
        return calculator.calculate(expression)
    except Exception as e:
        return {
            "success": False,
            "error": f"Calculator error: {str(e)}",
            "expression": expression
        }

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
        return timedelta_calculator.calculate_timedelta(datetime1, datetime2)
    except Exception as e:
        return {
            "success": False,
            "error": f"Timedelta calculator error: {str(e)}",
            "datetime1": datetime1,
            "datetime2": datetime2
        }

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
            return {"error": f"No results found for location: {location}"}
        
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
        
        return {
            "query": location,
            "results": formatted_results,
            "count": len(formatted_results)
        }
        
    except Exception as e:
        return {"error": str(e)}

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
        return weather.get_current_weather(latitude, longitude)
        
    except Exception as e:
        return {"error": str(e)}



@mcp.tool()
def memory_workflow_guide() -> Dict[str, Any]:
    """
    Get comprehensive memory management guidance including stored best practices and workflow steps.
    
    This is the primary memory guidance tool that combines:
    - Stored best practices from your TinyDB memory system
    - Complete step-by-step workflow for optimal memory management
    - System recommendations and troubleshooting guides
    
    CRITICAL: Use this tool first when working with memory to get both stored and system guidance.
    
    Returns:
        Dictionary with stored practices, workflow steps, and comprehensive best practices
    """
    # Get stored best practices from TinyDB memory system
    stored_guidelines = []
    try:
        stored_practices_result = tinydb_search_memories(
            category="best_practices",
            limit=20
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
    
    return {
        "success": True,
        "stored_best_practices": {
            "total_stored_practices": len(stored_guidelines),
            "guidelines": stored_guidelines,
            "note": "These are your personal best practices stored in TinyDB category='best_practices'"
        },
        "system_status": {
            "current_backend": "TinyDB (high-performance)",
            "memory_file": "tinydb_memories.json",
            "tags_file": "tinydb_tags.json", 
            "categories_file": "tinydb_categories.json",
            "migration_status": "Legacy tools removed - use tinydb_ prefixed tools"
        },
        "recommended_workflow": {
            "0_check_best_practices": {
                "step": "ALWAYS check stored best practices first",
                "tool": "tinydb_search_memories",
                "command": "tinydb_search_memories(category='best_practices')",
                "rationale": "Learn from previous experience and improve memory usage patterns",
                "example": "Review guidelines about tag naming, content formatting, category usage",
                "priority": "CRITICAL - Do this before every memory storage operation"
            },
            "1_analyze_content": {
                "step": "Extract key concepts and find similar existing tags",
                "tool": "tinydb_find_similar_tags",
                "command": "tinydb_find_similar_tags(query='concept_from_content', limit=3, min_similarity=0.3)",
                "rationale": "Find existing similar tags for each concept to avoid creating duplicates",
                "example": "For 'python web frameworks' → extract concepts ['python', 'web', 'frameworks'] → find similar tags for each",
                "workflow": "1) Extract key concepts 2) Call tinydb_find_similar_tags for each concept 3) Use suggested existing tags"
            },
            "1b_fallback_tag_discovery": {
                "step": "Fallback: Browse all existing tags if concept search yields nothing",
                "tool": "tinydb_get_all_tags",
                "example": "tinydb_get_all_tags() shows all 388 existing tags with usage counts",
                "note": "Use this if tinydb_find_similar_tags returns no matches for your concepts"
            },
            "2_select_category": {
                "step": "Choose appropriate category for organization",
                "tool": "tinydb_get_memory_categories",
                "command": "tinydb_get_memory_categories()",
                "categories": ["user_context", "preferences", "projects", "learnings", "corrections", "facts", "reminders", "best_practices"],
                "example": "Use 'projects' for work-related info, 'best_practices' for guidelines"
            },
            "3_determine_importance": {
                "step": "Set appropriate importance level (1-5)",
                "scale": {
                    "5": "Critical - Essential information that must never be forgotten",
                    "4": "High - Very important information frequently referenced", 
                    "3": "Normal - Standard importance (default)",
                    "2": "Low - Useful but not critical information",
                    "1": "Reference - Nice to have, rarely accessed"
                },
                "tip": "Higher importance memories appear first in search results"
            },
            "4_store_memory": {
                "step": "Store memory with optimized parameters",
                "tool": "tinydb_memorize",
                "full_example": "tinydb_memorize(content='React hooks allow state in functional components', tags='react,javascript,frontend,hooks', category='learnings', importance=4)",
                "parameters": {
                    "content": "The actual information to store (required)",
                    "tags": "Comma-separated tags from step 1 suggestions",
                    "category": "Category from step 2",
                    "importance": "1-5 scale from step 3 (default: 3)",
                    "expires_at": "Optional: ISO format date for temporary info"
                }
            },
            "5_verify_storage": {
                "step": "Verify memory was stored correctly and is findable with enhanced search",
                "tools": ["tinydb_search_memories", "tinydb_recall_memory"],
                "verification_steps": [
                    "Search by content: tinydb_search_memories(query='key terms')",
                    "Search by tags: tinydb_search_memories(tags='your_tags') - uses semantic expansion", 
                    "Search by category: tinydb_search_memories(category='your_category') - validates category exists",
                    "Direct recall: tinydb_recall_memory(memory_id='returned_id')"
                ],
                "success_indicators": ["Memory appears in search results", "Tags are registered", "Category is validated"],
                "enhanced_features": "Semantic tag expansion means approximate tags still find your memory"
            }
        },
        "available_tinydb_tools": {
            "memory_management": [
                "tinydb_memorize(content, tags, category, importance, expires_at)",
                "tinydb_search_memories(query, tags, category, limit, importance_min)",
                "tinydb_list_memories(category, tags, limit)",
                "tinydb_delete_memory(memory_id)",
                "tinydb_update_memory(memory_id, content, tags, category, importance)",
                "tinydb_recall_memory(memory_id)"
            ],
            "tag_optimization": [
                "tinydb_find_similar_tags(query, limit, min_similarity) - PRIMARY TAG SUGGESTION TOOL",
                "tinydb_get_all_tags()",
            ],
            "analytics": [
                "tinydb_memory_stats()",
                "tinydb_get_memory_categories()"
            ],
            "generic_database": [
                "tinydb_query(db_name, table_name, query_dict)",
                "tinydb_insert(db_name, table_name, data)",
                "tinydb_delete(db_name, table_name, query_dict)",
                "tinydb_list_databases()",
                "tinydb_list_tables(db_name)",
                "tinydb_get_database_info(db_name)"
            ]
        },
        "advanced_workflows": {
            "bulk_memory_storage": {
                "scenario": "Storing multiple related memories efficiently",
                "steps": [
                    "1. Extract common concepts from representative content",
                    "2. Use tinydb_find_similar_tags() to find existing tags for each concept",
                    "3. Identify common tags and category for the batch",
                    "4. Store each memory with consistent tagging",
                    "5. Use tinydb_memory_stats() to verify batch storage"
                ],
                "efficiency_tip": "Reuse discovered existing tags across similar content to maintain consistency"
            },
            "memory_maintenance": {
                "scenario": "Cleaning up and organizing existing memories",
                "steps": [
                    "1. Use tinydb_memory_stats() to analyze current state",
                    "2. Use tinydb_get_all_tags() to identify tag inconsistencies", 
                    "3. Use tinydb_search_memories() to find memories needing updates",
                    "4. Use tinydb_update_memory() to standardize tags/categories",
                    "5. Use tinydb_delete_memory() to remove outdated information"
                ],
                "tools_needed": ["tinydb_memory_stats", "tinydb_get_all_tags", "tinydb_update_memory"]
            },
            "information_retrieval": {
                "scenario": "Finding specific information quickly",
                "search_strategies": [
                    "Content search: tinydb_search_memories(query='specific terms')",
                    "Tag filtering: tinydb_search_memories(tags='specific_tag')",
                    "Category filtering: tinydb_search_memories(category='category_name')", 
                    "Importance filtering: tinydb_search_memories(importance_min=4)",
                    "Combined filters: tinydb_search_memories(query='term', tags='tag', category='cat')"
                ],
                "tip": "Use importance_min parameter to focus on critical information first"
            }
        },
        "performance_optimization": {
            "efficient_tagging": {
                "primary_strategy": "ALWAYS use tinydb_find_similar_tags() for each content concept",
                "rationale": "Finds existing similar tags, preventing duplicates and tag proliferation",
                "workflow": "Extract concepts → call tinydb_find_similar_tags() for each → use existing matches",
                "avoid": "Creating new tags without checking for similar existing ones"
            },
            "search_optimization": {
                "semantic_advantage": "tinydb_search_memories() now automatically expands approximate tags",
                "category_clarity": "Invalid categories get helpful error showing all available options", 
                "tag_flexibility": "Use approximate tags like 'python-dev' - system finds 'python', 'development' matches",
                "specific_searches": "Use specific terms rather than broad queries",
                "tag_combinations": "Combine multiple tags for precise filtering",
                "importance_filtering": "Use importance_min to prioritize results",
                "limit_results": "Use limit parameter for large datasets"
            },
            "database_maintenance": {
                "regular_stats": "Use tinydb_memory_stats() to monitor growth",
                "tag_cleanup": "Use tinydb_get_all_tags() to identify unused tags",
                "category_review": "Use tinydb_get_memory_categories() to ensure proper organization"
            }
        },
        "troubleshooting": {
            "memory_not_found": {
                "issue": "Stored memory cannot be found in searches",
                "solutions": [
                    "Check if memory was actually stored: use tinydb_recall_memory(memory_id)",
                    "Verify tags: use tinydb_search_memories(tags='expected_tag')",
                    "Check category: use tinydb_search_memories(category='expected_category')",
                    "Use broader search terms: tinydb_search_memories(query='partial_content')"
                ]
            },
            "tag_proliferation": {
                "issue": "Too many similar tags created",
                "prevention": "ALWAYS use tinydb_find_similar_tags() for each concept before creating new tags",
                "solution": "Use tinydb_get_all_tags() to identify duplicates, then tinydb_update_memory() to consolidate"
            },
            "performance_issues": {
                "issue": "Slow search or storage operations",
                "solutions": [
                    "Use specific search terms instead of broad queries",
                    "Limit results with limit parameter",
                    "Use importance_min to filter to essential memories only",
                    "Check database size with tinydb_memory_stats()"
                ]
            },
            "category_confusion": {
                "issue": "Uncertain which category to use, or getting category not found errors",
                "solution": "Use tinydb_get_memory_categories() to see available options, or let tinydb_search_memories show you available categories",
                "tip": "Invalid categories in tinydb_search_memories() return helpful error listing all available categories",
                "example": "Search with wrong category gets: 'Available categories: learnings, facts, projects, best_practices...'"
            }
        },
        "tag_best_practices": {
            "primary_rule": "ALWAYS use tinydb_find_similar_tags() for each content concept - prevents tag proliferation",
            "workflow_order": "1) Extract concepts 2) Find similar tags for each 3) Use existing matches 4) Only create truly new tags",
            "use_existing_first": "Always prefer existing similar tags over creating new ones",
            "consistent_naming": "Prefer existing tag conventions discovered through tinydb_find_similar_tags()",
            "avoid_duplicates": "Don't create 'js' if tinydb_find_similar_tags('javascript') shows 'javascript' exists",
            "compound_concepts": "For complex topics, find existing tags for each concept rather than creating one big tag"
        },
        "migration_info": {
            "legacy_location": "Legacy memory files moved to legacy/ folder",
            "migration_script": "migrate_to_tinydb.py - run with --migrate flag",
            "data_preserved": "All 88 memories, 242 tags, 8 categories successfully migrated",
            "performance_improvement": "TinyDB provides faster, more reliable data persistence"
        },
        "comprehensive_workflow_example": {
            "scenario": "Storing information about React hooks efficiently",
            "content_to_store": "React hooks allow functional components to use state and lifecycle methods without converting to class components",
            "step_0": {
                "action": "tinydb_search_memories(category='best_practices')",
                "purpose": "Review stored best practices first",
                "result": "Found guidelines about consistent tagging"
            },
            "step_1": {
                "action": "Extract concepts: ['react', 'hooks', 'functional', 'components', 'state'] → call tinydb_find_similar_tags() for each",
                "purpose": "Find existing similar tags for each concept",
                "result": "'react' → ['react'], 'hooks' → ['javascript'], 'functional' → ['programming'], 'components' → ['frontend']"
            },
            "step_2": {
                "action": "tinydb_get_memory_categories()",
                "purpose": "Choose appropriate category",
                "result": "Selected 'learnings' for educational content"
            },
            "step_3": {
                "action": "tinydb_memorize(content='...', tags='react,javascript,frontend,hooks', category='learnings', importance=4)",
                "purpose": "Store with optimized parameters",
                "result": "Memory stored with ID: mem_12345"
            },
            "step_4": {
                "action": "tinydb_search_memories(tags='react')",
                "purpose": "Verify storage and findability",
                "result": "Memory appears in results, successfully tagged"
            },
            "efficiency_gained": "Systematic tinydb_find_similar_tags() calls find existing tags instead of creating duplicates",
            "time_saved": "Prevents tag proliferation and improves search accuracy"
        },
        "quick_reference": {
            "most_important_tools": [
                "tinydb_find_similar_tags() - PRIMARY TOOL: Find existing tags for concepts",
                "tinydb_memorize() - Store with discovered existing tags",
                "tinydb_search_memories() - ENHANCED: Semantic tag expansion + category validation",
                "tinydb_memory_stats() - Monitor system health"
            ],
            "efficiency_shortcuts": {
                "new_memory": "extract concepts → find similar tags → memorize → verify",
                "find_memory": "search by content, tags, or category",
                "maintenance": "stats → get_all_tags → update as needed"
            }
        }
    }



# =============================================================================
# TINYDB MEMORY TOOLS - High-performance memory management with TinyDB backend
# =============================================================================

@mcp.tool()
def tinydb_memorize(content: str, tags: str = "", category: str = "", 
                   importance: int = 3, expires_at: str = "") -> Dict[str, Any]:
    """
    Store information using TinyDB (tinydb_memories.json) - HIGH PERFORMANCE VERSION.
    
    This is a TinyDB-based version of memorize() with better performance and reliability.
    Identical API to memorize() but uses dedicated tinydb_memories.json file.
    
    Args:
        content: The information to memorize
        tags: Comma-separated tags for categorization
        category: Memory category (user_context, preferences, projects, etc.)
        importance: Importance level 1-5 (5 being most critical)
        expires_at: Optional expiration date in ISO format
        
    Returns:
        Dictionary with memory ID and storage confirmation
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
                    return {"error": f"Invalid expiration date format: {expires_val}. Use ISO format."}
            
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
            
            return {
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
        except Exception as e:
            memory_db.close()
            raise e
        
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def tinydb_recall_memory(memory_id: str) -> Dict[str, Any]:
    """
    Retrieve a specific memorized item by ID using TinyDB.
    
    Args:
        memory_id: The ID of the memory to retrieve
        
    Returns:
        Dictionary with memory details or error
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
                        return {"error": f"Memory {memory_id} has expired"}
                        
                memory_db.close()
                return {
                    "success": True,
                    "memory": memory
                }
            else:
                memory_db.close()
                return {"error": f"Memory with ID {memory_id} not found"}
        except Exception as e:
            memory_db.close()
            raise e
            
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def tinydb_search_memories(query: str = "", tags: str = "", category: str = "", 
                          limit: int = 10, semantic_search: bool = True) -> Dict[str, Any]:
    """
    Search memorized information using TinyDB with advanced filtering and semantic tag awareness.
    
    SEMANTIC ENHANCEMENT: When semantic_search=True (default), this tool automatically:
    - Finds similar existing tags if provided tags don't match exactly
    - Returns helpful error with available categories if invalid category provided
    - This makes tag-based search much more effective with approximate terms
    
    Args:
        query: Text to search for in memory content
        tags: Comma-separated tags to filter by (semantic expansion when enabled)
        category: Category to filter by (exact match required - error shows available categories)
        limit: Maximum number of results (default: 10)
        semantic_search: Enable semantic tag expansion (default: True)
        
    Returns:
        Dictionary with search results sorted by importance, or error with available categories if invalid category
    """
    try:
        from datetime import datetime
        
        memory_db = get_memory_tinydb()
        try:
            memories_table = memory_db.table('memories')
            Record = Query()
            
            # Semantic search expansion (tags only) and category validation
            original_tags = tags
            original_category = category
            expanded_tags = []
            
            # Validate category exists if provided
            if category:
                category_exists, category_error, existing_categories = check_category_exists(category)
                if not category_exists:
                    memory_db.close()
                    return {
                        "success": False,
                        "error": category_error,
                        "available_categories": existing_categories
                    }
            
            # Semantic tag expansion (if enabled)
            if semantic_search and tags:
                input_tags = [tag.strip() for tag in tags.split(',') if tag.strip()]
                all_expanded = set(input_tags)  # Start with original tags
                
                for tag in input_tags:
                    similar_tags = find_similar_tags_internal(tag, limit=3, min_similarity=0.4)
                    all_expanded.update(similar_tags)
                
                expanded_tags = list(all_expanded)
            
            # Start with all memories
            results = memories_table.all()
            
            # Filter out expired memories
            current_time = datetime.now()
            active_results = []
            for memory in results:
                if memory.get('expires_at'):
                    try:
                        expiry = datetime.fromisoformat(memory['expires_at'].replace('Z', '+00:00'))
                        if current_time <= expiry:
                            active_results.append(memory)
                    except:
                        active_results.append(memory)  # Keep if date parsing fails
                else:
                    active_results.append(memory)
            
            # Apply filters
            filtered_results = active_results
            
            # Content query filter
            if query:
                query_words = [word.lower().strip() for word in query.split() if word.strip()]
                filtered_results = [
                    memory for memory in filtered_results
                    if all(word in memory['content'].lower() for word in query_words)
                ]
            
            # Tags filter (with semantic expansion)
            if tags:
                if semantic_search and expanded_tags:
                    # Use expanded tags for better matching
                    filter_tags = [tag.lower() for tag in expanded_tags]
                else:
                    # Use original tags
                    filter_tags = [tag.strip().lower() for tag in tags.split(',') if tag.strip()]
                    
                filtered_results = [
                    memory for memory in filtered_results
                    if any(filter_tag in memory.get('tags', []) for filter_tag in filter_tags)
                ]
            
            # Category filter (exact matching only - category validated above)
            if category:
                filtered_results = [
                    memory for memory in filtered_results
                    if memory.get('category', '').lower() == category.strip().lower()
                ]
            
            # Sort by importance (descending), then by creation time (most recent first)
            filtered_results.sort(
                key=lambda x: (x.get('importance', 3), x.get('created_at', x.get('timestamp', ''))), 
                reverse=True
            )
            
            # Apply limit
            final_results = filtered_results[:limit]
            
            # Close database before returning
            memory_db.close()
            
            # Prepare semantic expansion info (tags only)
            semantic_info = {}
            if semantic_search:
                semantic_info = {
                    "enabled": True,
                    "tag_expansion": {
                        "original_tags": original_tags,
                        "expanded_tags": expanded_tags if expanded_tags else None,
                        "expansion_occurred": bool(expanded_tags and set(expanded_tags) != set(original_tags.split(',') if original_tags else []))
                    },
                    "category_validation": "Categories use exact matching - invalid categories return helpful error with available options"
                }
            else:
                semantic_info = {"enabled": False}
            
            return {
                "success": True,
                "memories": final_results,
                "total_found": len(filtered_results),
                "returned_count": len(final_results),
                "search_criteria": {
                    "query": query,
                    "tags": tags,
                    "category": category,
                    "limit": limit,
                    "semantic_search": semantic_search
                },
                "semantic_expansion": semantic_info
            }
        except Exception as e:
            memory_db.close()
            raise e
        
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def tinydb_list_memories(limit: int = 20) -> Dict[str, Any]:
    """
    List all memorized information using TinyDB (most important first).
    
    Args:
        limit: Maximum number of memories to return (default: 20)
        
    Returns:
        Dictionary with list of all memories
    """
    try:
        from datetime import datetime
        
        memory_db = get_memory_tinydb()
        try:
            memories_table = memory_db.table('memories')
            
            # Get all memories
            all_memories = memories_table.all()
            
            # Filter out expired memories
            current_time = datetime.now()
            active_memories = []
            for memory in all_memories:
                if memory.get('expires_at'):
                    try:
                        expiry = datetime.fromisoformat(memory['expires_at'].replace('Z', '+00:00'))
                        if current_time <= expiry:
                            active_memories.append(memory)
                    except:
                        active_memories.append(memory)  # Keep if date parsing fails
                else:
                    active_memories.append(memory)
            
            # Sort by importance (descending), then by creation time (most recent first)
            active_memories.sort(
                key=lambda x: (x.get('importance', 3), x.get('created_at', x.get('timestamp', ''))), 
                reverse=True
            )
            
            # Apply limit
            limited_memories = active_memories[:limit]
            
            # Close database
            memory_db.close()
            
            return {
                "success": True,
                "memories": limited_memories,
                "total_active": len(active_memories),
                "returned_count": len(limited_memories),
                "limit": limit
            }
        except Exception as e:
            memory_db.close()
            raise e
        
    except Exception as e:
        return {"error": str(e)}

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
    Update an existing memorized item using TinyDB.
    
    Args:
        memory_id: ID of the memory to update
        content: New content (empty = no change)
        tags: New tags (empty = no change)
        category: New category (empty = no change) 
        importance: New importance level (0 = no change)
        expires_at: New expiration date (empty = no change)
        
    Returns:
        Dictionary with update confirmation
    """
    try:
        from datetime import datetime
        
        memory_db = get_memory_tinydb()
        try:
            memories_table = memory_db.table('memories')
            Record = Query()
            
            # Find existing memory
            existing = memories_table.search(Record.id == memory_id)
            if not existing:
                memory_db.close()
                return {"error": f"Memory with ID {memory_id} not found"}
                
            # Prepare updates
            updates = {}
            
            if content.strip():
                updates['content'] = content.strip()
                
            if tags.strip():
                tag_list = [tag.strip().lower() for tag in tags.split(',') if tag.strip()]
                updates['tags'] = tag_list
                # Register new tags
                if tag_list:
                    tinydb_register_tags(tag_list)
                    
            if category.strip():
                updates['category'] = category.strip()
                tinydb_update_category_usage(category.strip())
                
            if importance > 0:
                updates['importance'] = importance
                
            if expires_at.strip():
                try:
                    datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    updates['expires_at'] = expires_at.strip()
                except ValueError:
                    memory_db.close()
                    return {"error": f"Invalid expiration date format: {expires_at}"}
            
            if not updates:
                memory_db.close()
                return {"error": "No valid updates provided"}
            
            # Always update the last_modified timestamp
            updates['last_modified'] = datetime.now().isoformat()
                
            # Perform update
            updated_count = memories_table.update(updates, Record.id == memory_id)
            
            if updated_count:
                # Get updated record
                updated_record = memories_table.search(Record.id == memory_id)[0]
                memory_db.close()
                return {
                    "success": True,
                    "memory_id": memory_id,
                    "updated_fields": list(updates.keys()),
                    "memory": updated_record
                }
            else:
                memory_db.close()
                return {"error": "Update failed"}
                
        except Exception as e:
            memory_db.close()
            raise e
            
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def tinydb_delete_memory(memory_id: str) -> Dict[str, Any]:
    """
    Delete a memorized item by ID using TinyDB.
    
    Args:
        memory_id: The ID of the memory to delete
        
    Returns:
        Dictionary with deletion confirmation
    """
    try:
        memory_db = get_memory_tinydb()
        try:
            memories_table = memory_db.table('memories')
            Record = Query()
            
            # Check if memory exists
            existing = memories_table.search(Record.id == memory_id)
            if not existing:
                memory_db.close()
                return {"error": f"Memory with ID {memory_id} not found"}
                
            # Delete the memory
            deleted_count = memories_table.remove(Record.id == memory_id)
            
            if deleted_count:
                memory_db.close()
                return {
                    "success": True,
                    "memory_id": memory_id,
                    "deleted_memory": existing[0],
                    "message": "Memory deleted successfully"
                }
            else:
                memory_db.close()
                return {"error": "Deletion failed"}
                
        except Exception as e:
            memory_db.close()
            raise e
            
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def tinydb_memory_stats() -> Dict[str, Any]:
    """
    Get statistics about memorized information using TinyDB.
    
    Returns:
        Dictionary with comprehensive memory statistics
    """
    try:
        from datetime import datetime
        
        memory_db = get_memory_tinydb()
        memories_table = memory_db.table('memories')
        tags_db = get_tags_tinydb()
        tags_table = tags_db.table('tags')
        categories_db = get_categories_tinydb()
        categories_table = categories_db.table('categories')
        
        # Get all memories
        all_memories = memories_table.all()
        
        # Count active vs expired
        current_time = datetime.now()
        active_count = 0
        expired_count = 0
        
        importance_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        category_dist = {}
        
        for memory in all_memories:
            # Check expiration
            if memory.get('expires_at'):
                try:
                    expiry = datetime.fromisoformat(memory['expires_at'].replace('Z', '+00:00'))
                    if current_time <= expiry:
                        active_count += 1
                    else:
                        expired_count += 1
                except:
                    active_count += 1  # Keep if date parsing fails
            else:
                active_count += 1
                
            # Count importance distribution
            importance = memory.get('importance', 3)
            if importance in importance_dist:
                importance_dist[importance] += 1
                
            # Count category distribution
            category = memory.get('category')
            if category:
                category_dist[category] = category_dist.get(category, 0) + 1
        
        # Get tag statistics
        all_tags = tags_table.all()
        tag_count = len(all_tags)
        
        # Get category statistics
        all_categories = categories_table.all()
        category_count = len(all_categories)
        
        return {
            "success": True,
            "total_memories": len(all_memories),
            "active_memories": active_count,
            "expired_memories": expired_count,
            "importance_distribution": importance_dist,
            "category_distribution": category_dist,
            "total_tags": tag_count,
            "total_categories": category_count,
            "database_files": {
                "memories": "tinydb_memories.json",
                "tags": "tinydb_tags.json", 
                "categories": "tinydb_categories.json"
            }
        }
        
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def tinydb_get_memory_categories() -> Dict[str, Any]:
    """
    Get available categories for organizing memories using TinyDB.
    
    Returns:
        Dictionary with category information and usage statistics
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
        
        return {
            "success": True,
            "existing_categories": sorted_categories,
            "suggested_categories": suggested,
            "total_categories": len(all_categories)
        }
        
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def tinydb_find_similar_tags(query: str, limit: int = 5, min_similarity: float = 0.3) -> Dict[str, Any]:
    """
    Find similar existing tags for any concept or content topic using TinyDB similarity matching.
    
    RECOMMENDED USE: This is the primary tool for tag suggestions when storing memories.
    Instead of creating new tags, use this to find existing similar tags first.
    
    CONTENT-BASED WORKFLOW:
    1. Extract key concepts from your content (e.g., "python", "web", "api")
    2. Call this tool for each concept to find similar existing tags
    3. Use the suggested tags when calling tinydb_memorize()
    
    Args:
        query: Tag, concept, or topic to find similar tags for (e.g., "programming", "web development", "machine learning")
        limit: Maximum number of similar tags to return (default: 5)
        min_similarity: Minimum similarity score 0.0-1.0 (default: 0.3)
        
    Returns:
        Dictionary with similar tags, similarity scores, and usage statistics
        
    Examples:
        - query="python" might return ["programming", "development", "coding"]
        - query="web development" might return ["frontend", "javascript", "html"]
        - query="machine learning" might return ["ai", "data-science", "algorithms"]
    """
    try:
        tags_db = get_tags_tinydb()
        tags_table = tags_db.table('tags')
        
        # For now, return a simple text-based similarity search
        # This can be enhanced with actual vector embeddings later
        all_tags = tags_table.all()
        
        if not all_tags:
            return {
                "success": True,
                "similar_tags": [],
                "message": "No tags found in database"
            }
        
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
        
        return {
            "success": True,
            "query": query,
            "similar_tags": similar_tags[:limit],
            "total_found": len(similar_tags)
        }
        
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def tinydb_get_all_tags() -> Dict[str, Any]:
    """
    Get all existing tags with usage statistics using TinyDB.
    
    Returns:
        Dictionary with all tags sorted by usage frequency
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
        
        return {
            "success": True,
            "tags": formatted_tags,
            "total_tags": len(formatted_tags)
        }
        
    except Exception as e:
        return {"error": str(e)}

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
        
        return {
            "success": True,
            "database_name": db_name,
            "database_file": f"{db_name}.json" if not db_name.endswith('.json') else db_name,
            "description": description,
            "message": "Database created successfully"
        }
        
    except Exception as e:
        return {"error": str(e)}

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
        
        return result
        
    except Exception as e:
        return {"error": str(e)}

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
        return workspace_manager.read_text_file(filename)
    except Exception as e:
        return {"error": str(e)}

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
        
        return workspace_manager.list_workspace_files(filter_tags=tag_filter)
        
    except Exception as e:
        return {"error": str(e)}

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
        return workspace_manager.delete_workspace_file(filename)
    except Exception as e:
        return {"error": str(e)}

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
        
        return workspace_manager.update_file_metadata(
            filename=filename,
            description=description_val,
            tags=tag_list,
            language=language_val
        )
        
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_workspace_info() -> Dict[str, Any]:
    """
    Get information about the workspace directory and its contents.
    
    Returns:
        Dictionary with workspace statistics and configuration
    """
    try:
        return workspace_manager.get_workspace_info()
    except Exception as e:
        return {"error": str(e)}

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
            return {"error": "Month must be between 1 and 12"}
        
        if year < 1:
            return {"error": "Year must be positive"}
        
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
        
        return {
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
        
    except Exception as e:
        return {"error": str(e)}

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
            return {"error": f"Invalid date format. Use YYYY-MM-DD format (e.g., '2025-08-09')"}
        
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
        
        return {
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
        
    except Exception as e:
        return {"error": str(e)}

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
            
            return {
                "success": True,
                "database": db_name,
                "table": table,
                "record_id": record_id,
                "action": action,
                "data": data
            }
            
        except Exception as e:
            custom_db.close()
            raise e
        
    except Exception as e:
        return {"error": str(e)}

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
            
            return {
                "success": True,
                "database": db_name,
                "table": table,
                "query_conditions": query_conditions,
                "results": limited_results,
                "total_found": len(results),
                "returned_count": len(limited_results)
            }
            
        except Exception as e:
            custom_db.close()
            raise e
        
    except Exception as e:
        return {"error": str(e)}

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
                return {
                    "success": True,
                    "database": db_name,
                    "table": table,
                    "record_id": record_id,
                    "updated_fields": list(updates.keys()),
                    "updated_record": updated_record
                }
            else:
                custom_db.close()
                return {"error": f"No record found with ID {record_id} in table {table}"}
                
        except Exception as e:
            custom_db.close()
            raise e
            
    except Exception as e:
        return {"error": str(e)}

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
                return {"error": "Must provide either record_id or query_conditions"}
            
            custom_db.close()
            
            return {
                "success": True,
                "database": db_name,
                "table": table,
                "operation_type": operation_type,
                "deleted_count": deleted_count
            }
            
        except Exception as e:
            custom_db.close()
            raise e
        
    except Exception as e:
        return {"error": str(e)}

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
        
        return {
            "success": True,
            "databases": databases,
            "total_databases": len(databases),
            "data_path": base_path
        }
        
    except Exception as e:
        return {"error": str(e)}

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
        
        return {
            "success": True,
            **info
        }
        
    except Exception as e:
        return {"error": str(e)}

def main():
    """Main entry point for the MCP server."""
    print("Starting First MCP Server...", file=sys.stderr)
    print(f"Python executable: {sys.executable}", file=sys.stderr)
    print(f"Current directory: {os.getcwd()}", file=sys.stderr)
    
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
            
            from weather import WeatherAPI, GeocodingAPI
            print("✓ Weather imports OK", file=sys.stderr)
            
            from fileio import WorkspaceManager
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