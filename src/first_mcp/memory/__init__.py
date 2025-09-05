"""
Memory system core package for First MCP Server.

Provides TinyDB-based memory storage, retrieval, and semantic search capabilities
with proper architecture delegation between MCP layer and data processing.

CURRENT STATUS (v1.1.0):
✅ Architecture delegation pattern implemented
✅ MCP tools properly delegate to memory module functions
✅ Server timestamps and error handling in MCP layer
✅ Data processing logic isolated in memory module
✅ 10 core memory tools streamlined for production use

MEMORY TOOLS (Production-Ready):
- tinydb_memorize: Primary storage with integrated smart tag mapping
- tinydb_search_memories: Semantic search with tag expansion
- tinydb_recall_memory: Direct memory access by ID
- tinydb_list_memories: Memory browsing and discovery
- tinydb_update_memory: Memory modification
- tinydb_delete_memory: Memory removal
- tinydb_get_memory_categories: Category management
- tinydb_get_all_tags: Tag inventory
- memory_workflow_guide: User guidance and best practices
- tinydb_find_similar_tags: Smart tag suggestions

ARCHITECTURE DESIGN:
┌─ MCP Layer (server_impl.py) ─┐
│ • Tool registration           │
│ • Server timestamps          │ 
│ • Error handling             │
│ • Parameter validation       │
└──────────┬───────────────────┘
           │ delegates to
┌─ Memory Module (memory/) ────┐
│ • Data processing logic      │
│ • TinyDB operations          │
│ • Semantic search            │
│ • Smart tag mapping          │
└──────────────────────────────┘

FUTURE ROADMAP:
v2.0.0: Ultra-simplified interface (2-4 tools total)
v2.1.0: Advanced features return as optional extensions
  - Hierarchical tagging system
  - Tag governance workflows  
  - Background consolidation system
  - Advanced semantic grouping
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
from .tag_mapper import smart_tag_mapping

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
    'tinydb_get_database_info',
    
    # Smart tag mapping (production-ready)
    'smart_tag_mapping'
]