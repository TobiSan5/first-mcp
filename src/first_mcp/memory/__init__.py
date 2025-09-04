"""
Memory system core package for First MCP Server.

Provides TinyDB-based memory storage, retrieval, and semantic search capabilities.

ROADMAP - Smart Tag Management v1.1:
- [DONE] Vector embeddings system (100% coverage - 659/659 tags)
- [DONE] Semantic search expansion in tinydb_search_memories
- [DONE] Smart tag mapping integrated into tinydb_memorize
- [DONE] Integration testing with real MCP client
- [TODO] Background tag consolidation system
- [FUTURE] Hierarchical tagging system

CRITICAL ARCHITECTURE ISSUE - SMART TAG MAPPING NOT IN PRODUCTION:
- PROBLEM: Two separate implementations of tinydb_memorize exist:
  1. server_impl.py:717 - MCP tool wrapper (OLD, no smart mapping)
  2. memory/memory_tools.py:48 - Memory module (NEW, with smart mapping)
- IMPACT: Smart tag mapping integration is BYPASSED in production MCP calls
- ROOT CAUSE: server_impl.py has full implementation instead of delegating
- DISCOVERED: 2024-09-04 during architecture analysis

TODO - URGENT FIXES REQUIRED:
1. Fix server_impl.py tinydb_memorize to delegate to memory module:
   ```python
   @mcp.tool()
   def tinydb_memorize(...):
       result = tinydb_memorize_impl(content, tags, category, importance, expires_at)  
       return add_server_timestamp(result)
   ```
2. Clean up old experimental imports in server_impl.py (lines 32-43)
3. Test that MCP calls now use smart tag mapping
4. Remove redundant implementation from server_impl.py

CONFIGURATION NOTES:
- Max tag count for smart mapping is currently hardcoded to 3 in tag_mapper.py
- TODO: Make max_tags configurable via server initialization parameter
- Suggested approach: Pass max_tags_limit to server_impl.py during startup,
  then propagate to tinydb_memorize calls for flexible tag limit control
- This would allow different deployments to have different tag strategies

INTEGRATION PLAN:
- Phase 1: Test temp_tag_mapper thoroughly with existing data ✓
- Phase 2: Integrate smart mapping into tinydb_memorize with transparency logging ✓
- Phase 3: Add background consolidation during normal operations
- Phase 4: Advanced features (hierarchical tagging, approval workflows)

INTERFACES:
- MCP Tools: No changes to external API - improvements are transparent
- Internal: Enhanced tag processing with smart mapping and consolidation
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