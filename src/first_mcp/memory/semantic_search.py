"""
Semantic search functionality for memory system.
"""

from typing import List, Tuple, Dict, Any
from .database import get_tags_tinydb, get_categories_tinydb
from .tag_tools import _generate_embedding, _cosine_similarity


def find_similar_tags_internal(query: str, limit: int = 5, min_similarity: float = 0.3) -> List[str]:
    """
    Internal helper to find similar tags using embeddings. Used by tinydb_search_memories for semantic expansion.
    Returns list of similar tag names, not the full MCP tool response format.
    """
    try:
        tags_db = get_tags_tinydb()
        tags_table = tags_db.table('tags')
        
        all_tags = tags_table.all()
        if not all_tags:
            tags_db.close()
            return []
        
        # Generate embedding for query
        query_embedding = _generate_embedding(query)
        similar_tags = []
        
        # Use embeddings if available
        if query_embedding:
            for tag_entry in all_tags:
                tag_embedding = tag_entry.get('embedding', [])
                if tag_embedding and len(tag_embedding) > 0:
                    # Calculate embedding similarity
                    similarity = _cosine_similarity(query_embedding, tag_embedding)
                    
                    if similarity >= min_similarity:
                        similar_tags.append({
                            "tag": tag_entry.get('tag', ''),
                            "similarity": similarity,
                            "usage_count": tag_entry.get('usage_count', 0)
                        })
        
        # Fallback to string similarity if no embeddings available
        if not similar_tags:
            query_lower = query.lower().strip()
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
        
    except Exception:
        return []


def check_category_exists(category: str) -> Tuple[bool, str, List[str]]:
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