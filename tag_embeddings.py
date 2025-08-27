"""
Tag management with vector embeddings for similarity search.

This module provides functionality to store tags with their vector embeddings
using Google's GenAI embedding model for semantic similarity search.
"""

import json
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from google import genai
import numpy as np
from datetime import datetime


@dataclass
class TagEmbedding:
    """Represents a tag with its vector embedding."""
    tag: str
    embedding: List[float]
    usage_count: int
    created_at: str
    last_used_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TagEmbedding':
        """Create TagEmbedding from dictionary."""
        return cls(**data)


class TagEmbeddingManager:
    """
    Manages tags with vector embeddings for semantic similarity search.
    
    Requires GOOGLE_API_KEY environment variable for Google GenAI access.
    """
    
    def __init__(self, tags_file: str = "memory_tags.json"):
        """
        Initialize tag embedding manager.
        
        Args:
            tags_file: Path to the JSON file for storing tag embeddings
        """
        self.tags_file = tags_file
        self.model_name = "text-embedding-004"  # Model name without 'models/' prefix
        self.embedding_dimensions = 768  # text-embedding-004 uses 768 dimensions
        
        # Initialize Google GenAI client
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("Google API key required. Set GOOGLE_API_KEY environment variable.")
        
        self.client = genai.Client(api_key=api_key)
        self._ensure_tags_file()
    
    def _ensure_tags_file(self) -> None:
        """Ensure the tags file exists."""
        if not os.path.exists(self.tags_file):
            with open(self.tags_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    def _load_tag_embeddings(self) -> List[TagEmbedding]:
        """Load all tag embeddings from file."""
        try:
            with open(self.tags_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [TagEmbedding.from_dict(item) for item in data]
        except (json.JSONDecodeError, KeyError, TypeError):
            return []
    
    def _save_tag_embeddings(self, tags: List[TagEmbedding]) -> None:
        """Save tag embeddings to file."""
        try:
            with open(self.tags_file, 'w', encoding='utf-8') as f:
                json.dump([tag.to_dict() for tag in tags], f, 
                         ensure_ascii=False, indent=2)
        except Exception as e:
            raise Exception(f"Failed to save tag embeddings: {e}")
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        Get vector embedding for text using Google GenAI.
        
        Args:
            text: Text to embed
            
        Returns:
            Vector embedding as list of floats
        """
        try:
            response = self.client.models.embed_content(
                model=self.model_name,
                contents=text
            )
            return response.embeddings[0].values
        except Exception as e:
            raise Exception(f"Failed to generate embedding: {e}")
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            a: First vector
            b: Second vector
            
        Returns:
            Cosine similarity score (0-1)
        """
        try:
            a_np = np.array(a)
            b_np = np.array(b)
            
            dot_product = np.dot(a_np, b_np)
            norm_a = np.linalg.norm(a_np)
            norm_b = np.linalg.norm(b_np)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            return float(dot_product / (norm_a * norm_b))
        except Exception:
            return 0.0
    
    def add_or_update_tag(self, tag: str) -> bool:
        """
        Add a new tag or update usage count of existing tag.
        
        Args:
            tag: Tag to add or update
            
        Returns:
            True if new tag was added, False if existing tag was updated
        """
        tags = self._load_tag_embeddings()
        current_time = datetime.now().isoformat()
        
        # Check if tag already exists
        for existing_tag in tags:
            if existing_tag.tag.lower() == tag.lower():
                existing_tag.usage_count += 1
                existing_tag.last_used_at = current_time
                self._save_tag_embeddings(tags)
                return False
        
        # Add new tag
        try:
            embedding = self._get_embedding(tag)
            new_tag = TagEmbedding(
                tag=tag,
                embedding=embedding,
                usage_count=1,
                created_at=current_time,
                last_used_at=current_time
            )
            
            tags.append(new_tag)
            self._save_tag_embeddings(tags)
            return True
            
        except Exception as e:
            raise Exception(f"Failed to add tag '{tag}': {e}")
    
    def find_similar_tags(self, query: str, limit: int = 5, 
                         min_similarity: float = 0.3) -> List[Dict[str, Any]]:
        """
        Find tags similar to the query using semantic similarity.
        
        Args:
            query: Query text to find similar tags for
            limit: Maximum number of similar tags to return
            min_similarity: Minimum similarity threshold (0-1)
            
        Returns:
            List of similar tags with similarity scores
        """
        try:
            query_embedding = self._get_embedding(query)
            tags = self._load_tag_embeddings()
            
            if not tags:
                return []
            
            similarities = []
            for tag in tags:
                similarity = self._cosine_similarity(query_embedding, tag.embedding)
                if similarity >= min_similarity:
                    similarities.append({
                        "tag": tag.tag,
                        "similarity": similarity,
                        "usage_count": tag.usage_count,
                        "last_used_at": tag.last_used_at
                    })
            
            # Sort by similarity score (descending)
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            
            return similarities[:limit]
            
        except Exception as e:
            raise Exception(f"Failed to find similar tags: {e}")
    
    def get_all_tags(self, sort_by: str = "usage") -> List[Dict[str, Any]]:
        """
        Get all tags with their information.
        
        Args:
            sort_by: Sort method ("usage", "alphabetical", "recent")
            
        Returns:
            List of all tags with metadata
        """
        tags = self._load_tag_embeddings()
        
        tag_info = []
        for tag in tags:
            tag_info.append({
                "tag": tag.tag,
                "usage_count": tag.usage_count,
                "created_at": tag.created_at,
                "last_used_at": tag.last_used_at
            })
        
        if sort_by == "usage":
            tag_info.sort(key=lambda x: x["usage_count"], reverse=True)
        elif sort_by == "alphabetical":
            tag_info.sort(key=lambda x: x["tag"].lower())
        elif sort_by == "recent":
            tag_info.sort(key=lambda x: x["last_used_at"], reverse=True)
        
        return tag_info
    
    def get_tag_stats(self) -> Dict[str, Any]:
        """
        Get statistics about stored tags.
        
        Returns:
            Dictionary with tag statistics
        """
        tags = self._load_tag_embeddings()
        
        if not tags:
            return {
                "total_tags": 0,
                "total_usage": 0,
                "most_used_tag": None,
                "average_usage": 0
            }
        
        total_usage = sum(tag.usage_count for tag in tags)
        most_used = max(tags, key=lambda x: x.usage_count)
        
        return {
            "total_tags": len(tags),
            "total_usage": total_usage,
            "most_used_tag": {
                "tag": most_used.tag,
                "usage_count": most_used.usage_count
            },
            "average_usage": total_usage / len(tags)
        }


def test_tag_embeddings():
    """Test the tag embedding functionality."""
    print("Testing Tag Embeddings...")
    
    # Use a test file
    test_file = "test_tags.json"
    
    try:
        tag_manager = TagEmbeddingManager(test_file)
        
        # Add some test tags
        print("Adding test tags...")
        test_tags = ["python", "programming", "development", "weather", "api", "database"]
        
        for tag in test_tags:
            is_new = tag_manager.add_or_update_tag(tag)
            print(f"Tag '{tag}': {'Added' if is_new else 'Updated'}")
        
        # Test similarity search
        print("\nFinding tags similar to 'coding':")
        similar = tag_manager.find_similar_tags("coding", limit=3)
        for item in similar:
            print(f"- {item['tag']} (similarity: {item['similarity']:.3f})")
        
        print("\nFinding tags similar to 'web service':")
        similar = tag_manager.find_similar_tags("web service", limit=3)
        for item in similar:
            print(f"- {item['tag']} (similarity: {item['similarity']:.3f})")
        
        print("\nAll tags:")
        all_tags = tag_manager.get_all_tags()
        for tag_info in all_tags:
            print(f"- {tag_info['tag']} (used {tag_info['usage_count']} times)")
        
        print("\nTag statistics:")
        stats = tag_manager.get_tag_stats()
        print(json.dumps(stats, indent=2))
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure GOOGLE_API_KEY environment variable is set!")
    finally:
        # Clean up test file
        if os.path.exists(test_file):
            os.remove(test_file)


if __name__ == "__main__":
    test_tag_embeddings()