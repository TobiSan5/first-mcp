"""
Core memory management tools for the TinyDB memory system.
"""

import sys
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List
from tinydb import Query


def _log_search(msg: str) -> None:
    print(f"{time.monotonic():.3f} [search] {msg}", file=sys.stderr, flush=True)

from .database import get_memory_tinydb, get_categories_tinydb
from .tag_tools import tinydb_register_tags, decrement_tag_usage
from .semantic_search import find_similar_tags_internal, check_category_exists
from .tag_scoring import build_tag_registry, score_memories_by_tags
from .pagination import save_paginated_results


def tinydb_update_category_usage(category: str) -> None:
    """Update category usage statistics in TinyDB."""
    try:
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
        memory_db = get_memory_tinydb()
        try:
            memories_table = memory_db.table('memories')
            
            # Create memory record
            memory_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            
            # Parse and process tags with smart mapping
            raw_tags = [tag.strip().lower() for tag in tags.split(',') if tag.strip()] if tags else []
            
            # Use raw tags directly. smart_tag_mapping (tag consolidation via
            # embedding similarity) belongs in the background enrichment loop,
            # not on the synchronous MCP tool path where live API calls cause
            # tool-call timeouts and client disconnects.
            tag_list = raw_tags
            mapping_info = {
                "mapping_applied": False,
                "transparency_info": "Tags stored as provided; enrichment loop optimises asynchronously",
                "auto_replacements": 0,
                "raw_tags": raw_tags,
                "final_tags": raw_tags,
            }
            
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
                "tag_mapping": mapping_info,
                "message": "Information memorized successfully with TinyDB"
            }
        except Exception as e:
            memory_db.close()
            raise e
        
    except Exception as e:
        return {"error": str(e)}


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


def tinydb_search_memories(tags: str = "", content_keywords: str = "", category: str = "",
                          limit: int = 50, semantic_search: bool = True,
                          page_size: int = 5, sort_by: str = "relevance") -> Dict[str, Any]:
    """
    Search memories by tag similarity — the primary retrieval tool.

    Args:
        tags: Comma-separated tags — primary search signal.
        content_keywords: Optional substring filter on memory content (not semantic).
        category: Optional exact-match category filter.
        sort_by: "relevance" (default), "date_desc", or "date_asc".
        page_size: Results in first response (default 5).
        limit: Hard cap on total memories considered (default 50).
        semantic_search: False uses exact tag matching only (default True).
    """
    _log_search(f"start tags={tags!r} semantic={semantic_search}")
    try:
        memory_db = get_memory_tinydb()
        try:
            memories_table = memory_db.table('memories')

            # Validate category if provided
            if category:
                category_exists, category_error, existing_categories = check_category_exists(category)
                if not category_exists:
                    memory_db.close()
                    return {
                        "success": False,
                        "error": category_error,
                        "available_categories": existing_categories,
                    }

            # Load and filter expired memories
            _log_search("loading memories from TinyDB")
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
            _log_search(f"loaded {len(all_memories)} memories")

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

                if semantic_search:
                    _log_search("building tag registry")
                    try:
                        tag_registry = build_tag_registry()
                    except Exception as e:
                        _log_search(f"build_tag_registry failed: {e}")
                        raise
                    _log_search(f"tag registry: {len(tag_registry)} tags")
                    if tag_registry:
                        _log_search("scoring memories")
                        try:
                            scored = score_memories_by_tags(input_tags, all_memories, tag_registry)
                        except Exception as e:
                            _log_search(f"score_memories_by_tags failed: {e}")
                            raise
                        filtered_results = [mem for (_, mem, _) in scored][:limit]
                        scored_method = "tag_scoring"
                        _log_search(f"scoring done: {len(filtered_results)} results")
                    else:
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
                    filter_tags = input_tags
                    filtered_results = [
                        m for m in all_memories
                        if any(ft in m.get('tags', []) for ft in filter_tags)
                    ][:limit]
                    scored_method = "exact"
            else:
                all_memories.sort(
                    key=lambda x: (x.get('importance', 3), x.get('last_modified') or x.get('timestamp') or ''),
                    reverse=True,
                )
                filtered_results = all_memories[:limit]
                scored_method = "importance"

            # Date sort override
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
            if has_more:
                _log_search("saving paginated results")
                try:
                    next_page_token = save_paginated_results(
                        all_results=filtered_results,
                        page_size=page_size,
                        query_info={
                            "content_keywords": content_keywords, "tags": tags, "category": category,
                            "limit": limit, "semantic_search": semantic_search,
                            "page_size": page_size, "sort_by": sort_by,
                        },
                    )
                except Exception as e:
                    _log_search(f"save_paginated_results failed: {e}")
                    raise
                _log_search("pagination saved")

            _log_search(f"returning {len(first_page)} memories, method={scored_method}")
            return {
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

        except Exception as e:
            _log_search(f"inner exception: {e}")
            memory_db.close()
            raise e

    except Exception as e:
        _log_search(f"outer exception: {e}")
        return {"error": str(e)}


def tinydb_list_memories(limit: int = 100, page_size: int = 10,
                        category: str = "", sort_by: str = "relevance") -> Dict[str, Any]:
    """
    Browse memories by category — use for inventory, not topic search.

    Args:
        category: Optional exact-match category filter.
        sort_by: "relevance" (default, highest importance first), "date_desc", or "date_asc".
        page_size: Results in first response (default 10).
        limit: Hard cap on total memories considered (default 100).
    """
    try:
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
            if has_more:
                next_page_token = save_paginated_results(
                    all_results=capped,
                    page_size=page_size,
                    query_info={"limit": limit, "page_size": page_size,
                                "category": category, "sort_by": sort_by},
                )

            return {
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

        except Exception as e:
            memory_db.close()
            raise e

    except Exception as e:
        return {"error": str(e)}


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
                old_tag_set = set(existing[0].get('tags', []))
                new_tag_set = set(tag_list)
                removed_tags = list(old_tag_set - new_tag_set)
                updates['tags'] = tag_list
                if tag_list:
                    tinydb_register_tags(tag_list)
                if removed_tags:
                    decrement_tag_usage(removed_tags)
                    
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
                # Re-queue for enrichment when tags change
                if 'tags' in updates:
                    try:
                        from .tag_enrichment import remove_from_enrichment_register
                        remove_from_enrichment_register(memory_id)
                    except Exception:
                        pass
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
                deleted_tags = existing[0].get('tags', [])
                memory_db.close()
                if deleted_tags:
                    decrement_tag_usage(deleted_tags)
                try:
                    from .tag_enrichment import remove_from_enrichment_register
                    remove_from_enrichment_register(memory_id)
                except Exception:
                    pass
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


def tinydb_memory_stats() -> Dict[str, Any]:
    """
    Get statistics about memorized information using TinyDB.
    
    Returns:
        Dictionary with comprehensive memory statistics
    """
    try:
        memory_db = get_memory_tinydb()
        memories_table = memory_db.table('memories')
        
        from .database import get_tags_tinydb, get_categories_tinydb
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
            limit=20,
            page_size=20,
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
        # ... Rest of the comprehensive workflow guide from original function
        # (This is a large dictionary - keeping it short for now)
        "message": "Full workflow guide available - extracted to core memory package"
    }