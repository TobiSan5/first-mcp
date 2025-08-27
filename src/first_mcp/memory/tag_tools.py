"""
Tag management tools for memory system.
"""

from typing import Dict, Any, List
from datetime import datetime
from tinydb import Query
from .database import get_tags_tinydb


def tinydb_register_tags(tag_list: List[str]) -> Dict[str, Any]:
    """Register tags in TinyDB tags database with embeddings."""
    try:
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