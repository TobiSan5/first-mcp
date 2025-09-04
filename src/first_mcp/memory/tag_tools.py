"""
Tag management tools for memory system.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import os
from tinydb import Query
from .database import get_tags_tinydb

# Try to import Google AI for embeddings
try:
    import google.genai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def _generate_embedding(text: str) -> Optional[List[float]]:
    """
    Generate embedding for text using Google AI API.
    
    Args:
        text: Text to embed
        
    Returns:
        768-dimensional embedding vector or None if API unavailable
    """
    if not GENAI_AVAILABLE:
        return None
        
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        return None
    
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.embed_content(
            model="text-embedding-004",
            contents=text
        )
        return response.embeddings[0].values
    except Exception:
        # Silently fail - don't break tag creation if embedding fails
        return None


def _cosine_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Calculate cosine similarity between two embeddings.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        
    Returns:
        Cosine similarity score (0.0 to 1.0)
    """
    if not embedding1 or not embedding2:
        return 0.0
        
    try:
        import numpy as np
        
        # Convert to numpy arrays
        vec1 = np.array(embedding1, dtype=np.float32)
        vec2 = np.array(embedding2, dtype=np.float32)
        
        # Calculate norms
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        # Calculate cosine similarity
        similarity = np.dot(vec1, vec2) / (norm1 * norm2)
        
        # Ensure result is between 0 and 1
        return max(0.0, min(1.0, float(similarity)))
        
    except Exception:
        return 0.0


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
                    # Generate embedding for new tag
                    embedding = _generate_embedding(tag)
                    
                    # Create new tag entry
                    tag_data = {
                        'tag': tag,
                        'usage_count': 1,
                        'created_at': datetime.now().isoformat(),
                        'last_used_at': datetime.now().isoformat(),
                        'embedding': embedding if embedding else []
                    }
                    
                    # Add embedding metadata if successful
                    if embedding:
                        tag_data['embedding_generated_at'] = datetime.now().isoformat()
                        tag_data['embedding_model'] = 'text-embedding-004'
                    
                    tags_table.insert(tag_data)
                    status = f"Created: {tag}"
                    if embedding:
                        status += " (with embedding)"
                    else:
                        status += " (no embedding - API unavailable)"
                    registered.append(status)
                    
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
        
        # Generate embedding for query
        query_embedding = _generate_embedding(query)
        
        all_tags = tags_table.all()
        
        if not all_tags:
            return {
                "success": True,
                "similar_tags": [],
                "message": "No tags found in database"
            }
        
        similar_tags = []
        
        # Use embeddings if available for both query and tags
        if query_embedding:
            for tag_entry in all_tags:
                tag_embedding = tag_entry.get('embedding', [])
                if tag_embedding and len(tag_embedding) > 0:
                    # Calculate cosine similarity
                    similarity = _cosine_similarity(query_embedding, tag_embedding)
                    
                    if similarity >= min_similarity:
                        similar_tags.append({
                            "tag": tag_entry.get('tag', ''),
                            "similarity": round(similarity, 4),
                            "usage_count": tag_entry.get('usage_count', 0),
                            "last_used": tag_entry.get('last_used_at', ''),
                            "method": "embedding"
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
                        "usage_count": tag_entry.get('usage_count', 0),
                        "last_used": tag_entry.get('last_used_at', ''),
                        "method": "string"
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


def tinydb_generate_missing_embeddings() -> Dict[str, Any]:
    """
    Generate embeddings for tags that don't have them.
    
    Returns:
        Dictionary with results of embedding generation
    """
    try:
        tags_db = get_tags_tinydb()
        tags_table = tags_db.table('tags')
        Record = Query()
        
        # Find tags without embeddings
        tags_without_embeddings = tags_table.search(
            (Record.embedding == []) | (~Record.embedding.exists())
        )
        
        if not tags_without_embeddings:
            return {
                "success": True,
                "message": "All tags already have embeddings",
                "processed": 0,
                "generated": 0,
                "failed": 0
            }
        
        generated = 0
        failed = 0
        failed_tags = []
        
        for tag_record in tags_without_embeddings:
            tag_name = tag_record.get('tag', '')
            
            # Generate embedding
            embedding = _generate_embedding(tag_name)
            
            if embedding:
                # Update the tag with embedding
                tags_table.update(
                    {
                        'embedding': embedding,
                        'embedding_generated_at': datetime.now().isoformat(),
                        'embedding_model': 'text-embedding-004'
                    },
                    Record.tag == tag_name
                )
                generated += 1
            else:
                failed += 1
                failed_tags.append(tag_name)
        
        tags_db.close()
        
        result = {
            "success": True,
            "processed": len(tags_without_embeddings),
            "generated": generated,
            "failed": failed,
            "api_available": GENAI_AVAILABLE and bool(os.getenv('GOOGLE_API_KEY'))
        }
        
        if failed_tags:
            result["failed_tags"] = failed_tags[:10]  # Show first 10 failed tags
        
        return result
        
    except Exception as e:
        return {"error": f"Failed to generate missing embeddings: {str(e)}"}


def tinydb_embedding_stats() -> Dict[str, Any]:
    """
    Get statistics about tag embeddings.
    
    Returns:
        Dictionary with embedding coverage statistics
    """
    try:
        tags_db = get_tags_tinydb()
        tags_table = tags_db.table('tags')
        Record = Query()
        
        total_tags = len(tags_table.all())
        tags_with_embeddings = len(tags_table.search(
            Record.embedding.exists() & (Record.embedding != [])
        ))
        
        coverage_percent = (tags_with_embeddings / max(total_tags, 1)) * 100
        
        return {
            "success": True,
            "total_tags": total_tags,
            "tags_with_embeddings": tags_with_embeddings,
            "tags_without_embeddings": total_tags - tags_with_embeddings,
            "coverage_percent": round(coverage_percent, 1),
            "api_available": GENAI_AVAILABLE and bool(os.getenv('GOOGLE_API_KEY')),
            "embedding_model": "text-embedding-004",
            "embedding_dimensions": 768
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