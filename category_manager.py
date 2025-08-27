"""
Category management system for memory organization.

This module provides functionality to manage memory categories in a separate
JSON file, allowing for dynamic category management and usage tracking.
"""

import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class Category:
    """Represents a memory category with metadata."""
    name: str
    description: str
    usage_count: int
    created_at: str
    last_used_at: str
    is_system: bool = True  # System categories vs user-defined

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Category':
        """Create Category from dictionary."""
        return cls(**data)


class CategoryManager:
    """
    Manages memory categories with usage tracking and descriptions.
    """
    
    def __init__(self, categories_file: str = "memory_categories.json"):
        """
        Initialize category manager.
        
        Args:
            categories_file: Path to the JSON file for storing categories
        """
        self.categories_file = categories_file
        self._ensure_categories_file()
        self._initialize_system_categories()
    
    def _ensure_categories_file(self) -> None:
        """Ensure the categories file exists."""
        if not os.path.exists(self.categories_file):
            with open(self.categories_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    def _load_categories(self) -> List[Category]:
        """Load all categories from file."""
        try:
            with open(self.categories_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [Category.from_dict(item) for item in data]
        except (json.JSONDecodeError, KeyError, TypeError):
            return []
    
    def _save_categories(self, categories: List[Category]) -> None:
        """Save categories to file."""
        try:
            with open(self.categories_file, 'w', encoding='utf-8') as f:
                json.dump([cat.to_dict() for cat in categories], f, 
                         ensure_ascii=False, indent=2)
        except Exception as e:
            raise Exception(f"Failed to save categories: {e}")
    
    def _initialize_system_categories(self) -> None:
        """Initialize system categories if they don't exist."""
        categories = self._load_categories()
        existing_names = {cat.name for cat in categories}
        
        system_categories = [
            ("user_context", "Location, profession, interests, personal details"),
            ("preferences", "How information should be presented, preferred tools"),
            ("projects", "Ongoing work, previous discussions, project details"),
            ("learnings", "Things learned about user's specific situation"),
            ("corrections", "When initial assumptions were wrong"),
            ("facts", "Important factual information to remember"),
            ("reminders", "Things to remember for future interactions"),
            ("best_practices", "Guidelines and procedures to follow")
        ]
        
        current_time = datetime.now().isoformat()
        new_categories_added = False
        
        for name, description in system_categories:
            if name not in existing_names:
                categories.append(Category(
                    name=name,
                    description=description,
                    usage_count=0,
                    created_at=current_time,
                    last_used_at=current_time,
                    is_system=True
                ))
                new_categories_added = True
        
        if new_categories_added:
            self._save_categories(categories)
    
    def add_category(self, name: str, description: str, is_system: bool = False) -> bool:
        """
        Add a new category.
        
        Args:
            name: Category name
            description: Category description
            is_system: Whether this is a system category
            
        Returns:
            True if added successfully, False if already exists
        """
        categories = self._load_categories()
        
        # Check if category already exists (case-insensitive)
        for existing_cat in categories:
            if existing_cat.name.lower() == name.lower():
                return False
        
        current_time = datetime.now().isoformat()
        new_category = Category(
            name=name,
            description=description,
            usage_count=0,
            created_at=current_time,
            last_used_at=current_time,
            is_system=is_system
        )
        
        categories.append(new_category)
        self._save_categories(categories)
        return True
    
    def update_category_usage(self, name: str) -> bool:
        """
        Update usage count and last used time for a category.
        
        Args:
            name: Category name
            
        Returns:
            True if updated, False if category not found
        """
        categories = self._load_categories()
        
        for category in categories:
            if category.name.lower() == name.lower():
                category.usage_count += 1
                category.last_used_at = datetime.now().isoformat()
                self._save_categories(categories)
                return True
        
        return False
    
    def get_category(self, name: str) -> Optional[Category]:
        """
        Get a specific category by name.
        
        Args:
            name: Category name
            
        Returns:
            Category object or None if not found
        """
        categories = self._load_categories()
        
        for category in categories:
            if category.name.lower() == name.lower():
                return category
        
        return None
    
    def get_all_categories(self, sort_by: str = "usage") -> List[Dict[str, Any]]:
        """
        Get all categories with their information.
        
        Args:
            sort_by: Sort method ("usage", "alphabetical", "recent", "system_first")
            
        Returns:
            List of all categories with metadata
        """
        categories = self._load_categories()
        
        category_info = []
        for cat in categories:
            category_info.append({
                "name": cat.name,
                "description": cat.description,
                "usage_count": cat.usage_count,
                "created_at": cat.created_at,
                "last_used_at": cat.last_used_at,
                "is_system": cat.is_system
            })
        
        if sort_by == "usage":
            category_info.sort(key=lambda x: x["usage_count"], reverse=True)
        elif sort_by == "alphabetical":
            category_info.sort(key=lambda x: x["name"].lower())
        elif sort_by == "recent":
            category_info.sort(key=lambda x: x["last_used_at"], reverse=True)
        elif sort_by == "system_first":
            category_info.sort(key=lambda x: (not x["is_system"], x["name"].lower()))
        
        return category_info
    
    def update_category(self, name: str, description: Optional[str] = None) -> bool:
        """
        Update a category's description.
        
        Args:
            name: Category name
            description: New description
            
        Returns:
            True if updated, False if category not found
        """
        categories = self._load_categories()
        
        for category in categories:
            if category.name.lower() == name.lower():
                if description is not None:
                    category.description = description
                self._save_categories(categories)
                return True
        
        return False
    
    def delete_category(self, name: str) -> bool:
        """
        Delete a category (only non-system categories).
        
        Args:
            name: Category name
            
        Returns:
            True if deleted, False if not found or is system category
        """
        categories = self._load_categories()
        original_count = len(categories)
        
        # Only allow deletion of non-system categories
        categories = [cat for cat in categories 
                     if not (cat.name.lower() == name.lower() and not cat.is_system)]
        
        if len(categories) < original_count:
            self._save_categories(categories)
            return True
        
        return False
    
    def get_category_stats(self) -> Dict[str, Any]:
        """
        Get statistics about categories.
        
        Returns:
            Dictionary with category statistics
        """
        categories = self._load_categories()
        
        if not categories:
            return {
                "total_categories": 0,
                "system_categories": 0,
                "user_categories": 0,
                "total_usage": 0,
                "most_used_category": None
            }
        
        system_count = sum(1 for cat in categories if cat.is_system)
        user_count = len(categories) - system_count
        total_usage = sum(cat.usage_count for cat in categories)
        most_used = max(categories, key=lambda x: x.usage_count) if categories else None
        
        return {
            "total_categories": len(categories),
            "system_categories": system_count,
            "user_categories": user_count,
            "total_usage": total_usage,
            "most_used_category": {
                "name": most_used.name,
                "usage_count": most_used.usage_count,
                "is_system": most_used.is_system
            } if most_used else None
        }
    
    def search_categories(self, query: str) -> List[Dict[str, Any]]:
        """
        Search categories by name or description.
        
        Args:
            query: Search query
            
        Returns:
            List of matching categories
        """
        categories = self._load_categories()
        query_lower = query.lower()
        
        matching_categories = []
        for cat in categories:
            if (query_lower in cat.name.lower() or 
                query_lower in cat.description.lower()):
                matching_categories.append({
                    "name": cat.name,
                    "description": cat.description,
                    "usage_count": cat.usage_count,
                    "is_system": cat.is_system
                })
        
        return matching_categories


def test_category_manager():
    """Test the category manager functionality."""
    print("Testing Category Manager...")
    
    # Use a test file
    test_file = "test_categories.json"
    
    try:
        cat_manager = CategoryManager(test_file)
        
        # Add a custom category
        print("Adding custom category...")
        success = cat_manager.add_category("testing", "Test-related memories")
        print(f"Added 'testing' category: {success}")
        
        # Update usage
        print("Updating category usage...")
        cat_manager.update_category_usage("user_context")
        cat_manager.update_category_usage("testing")
        cat_manager.update_category_usage("testing")
        
        print("All categories:")
        all_cats = cat_manager.get_all_categories(sort_by="system_first")
        for cat_info in all_cats:
            system_label = " [SYSTEM]" if cat_info["is_system"] else " [USER]"
            print(f"- {cat_info['name']}{system_label}: {cat_info['description']} "
                  f"(used {cat_info['usage_count']} times)")
        
        print("\nSearching for 'user':")
        search_results = cat_manager.search_categories("user")
        for result in search_results:
            print(f"- {result['name']}: {result['description']}")
        
        print("\nCategory statistics:")
        stats = cat_manager.get_category_stats()
        print(json.dumps(stats, indent=2))
        
    finally:
        # Clean up test file
        if os.path.exists(test_file):
            os.remove(test_file)


if __name__ == "__main__":
    test_category_manager()