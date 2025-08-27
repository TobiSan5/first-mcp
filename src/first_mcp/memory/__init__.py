"""
Memory system core package for First MCP Server.

Provides TinyDB-based memory storage, retrieval, and semantic search capabilities.
"""

from .database import get_memory_tinydb, get_tags_tinydb, get_categories_tinydb, get_custom_tinydb
from .memory_tools import (
    tinydb_memorize,
    tinydb_recall_memory, 
    tinydb_search_memories,
    tinydb_list_memories,
    tinydb_update_memory,
    tinydb_delete_memory,
    tinydb_memory_stats,
    tinydb_get_memory_categories,
    memory_workflow_guide
)
from .tag_tools import (
    tinydb_find_similar_tags,
    tinydb_get_all_tags,
    tinydb_register_tags
)
from .semantic_search import find_similar_tags_internal, check_category_exists
from .generic_tools import (
    tinydb_create_database,
    tinydb_store_data,
    tinydb_query_data,
    tinydb_update_data,
    tinydb_delete_data,
    tinydb_list_databases,
    tinydb_get_database_info
)

__all__ = [
    # Database connections
    'get_memory_tinydb', 'get_tags_tinydb', 'get_categories_tinydb', 'get_custom_tinydb',
    
    # Core memory tools
    'tinydb_memorize', 'tinydb_recall_memory', 'tinydb_search_memories', 
    'tinydb_list_memories', 'tinydb_update_memory', 'tinydb_delete_memory',
    'tinydb_memory_stats', 'tinydb_get_memory_categories', 'memory_workflow_guide',
    
    # Tag management
    'tinydb_find_similar_tags', 'tinydb_get_all_tags', 'tinydb_register_tags',
    
    # Semantic search
    'find_similar_tags_internal', 'check_category_exists',
    
    # Generic database tools
    'tinydb_create_database', 'tinydb_store_data', 'tinydb_query_data',
    'tinydb_update_data', 'tinydb_delete_data', 'tinydb_list_databases',
    'tinydb_get_database_info'
]