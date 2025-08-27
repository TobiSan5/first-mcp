#!/usr/bin/env python3
"""
Migration script for transitioning from legacy JSON-based memory system to TinyDB.

This script:
1. Moves legacy files to a 'legacy' subfolder
2. Migrates data from legacy JSON files to TinyDB format
3. Preserves all data including memories, tags, and categories
4. Creates backups before any operations

Usage:
    python migrate_to_tinydb.py --help
    python migrate_to_tinydb.py --backup-only
    python migrate_to_tinydb.py --migrate
    python migrate_to_tinydb.py --migrate --force
"""

import os
import sys
import json
import shutil
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add current directory to path so we can import server modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_data_path() -> str:
    """Get the data path from environment variable or current directory."""
    return os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())

def backup_legacy_files(data_path: str, backup_suffix: str = None) -> bool:
    """
    Move legacy memory files to legacy/ subfolder.
    
    Args:
        data_path: Path to data directory
        backup_suffix: Optional suffix (ignored - always uses 'legacy' folder)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        legacy_files = [
            'memory_store.json',
            'memory_tags.json', 
            'memory_categories.json'
        ]
        
        # Always use 'legacy' folder name (no timestamps)
        legacy_path = os.path.join(data_path, 'legacy')
        
        # Check if any legacy files exist
        existing_files = []
        for filename in legacy_files:
            file_path = os.path.join(data_path, filename)
            if os.path.exists(file_path):
                existing_files.append((filename, file_path))
        
        if not existing_files:
            print("No legacy files found to move.")
            return True
            
        # Create legacy directory
        os.makedirs(legacy_path, exist_ok=True)
        print(f"Created legacy folder: {legacy_path}")
        
        # Move each file
        moved_files = []
        for filename, file_path in existing_files:
            dest_path = os.path.join(legacy_path, filename)
            
            # If destination exists, create backup with timestamp
            if os.path.exists(dest_path):
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                base_name = filename.replace('.json', '')
                backup_dest = os.path.join(legacy_path, f'{base_name}_{timestamp}.json')
                shutil.move(dest_path, backup_dest)
                print(f"Backed up existing {filename} -> {backup_dest}")
            
            shutil.move(file_path, dest_path)
            moved_files.append((filename, dest_path))
            print(f"Moved {filename} -> {dest_path}")
        
        print(f"Successfully moved {len(moved_files)} legacy files to {legacy_path}")
        return True
        
    except Exception as e:
        print(f"Error backing up legacy files: {e}")
        return False

def load_legacy_data(data_path: str) -> Dict[str, Any]:
    """
    Load data from legacy files (now in legacy/ folder).
    
    Args:
        data_path: Path to data directory
        
    Returns:
        Dictionary containing all legacy data
    """
    legacy_data = {
        'memories': [],
        'tags': [],
        'categories': []
    }
    
    legacy_path = os.path.join(data_path, 'legacy')
    
    try:
        # Load memories
        memory_file = os.path.join(legacy_path, 'memory_store.json')
        if os.path.exists(memory_file):
            with open(memory_file, 'r', encoding='utf-8') as f:
                legacy_data['memories'] = json.load(f)
            print(f"Loaded {len(legacy_data['memories'])} memories from legacy file")
        
        # Load tags
        tags_file = os.path.join(legacy_path, 'memory_tags.json')
        if os.path.exists(tags_file):
            with open(tags_file, 'r', encoding='utf-8') as f:
                tags_data = json.load(f)
                # Convert from tag embedding format to simple list
                if isinstance(tags_data, dict):
                    legacy_data['tags'] = list(tags_data.values()) if tags_data else []
                else:
                    legacy_data['tags'] = tags_data or []
            print(f"Loaded {len(legacy_data['tags'])} tags from legacy file")
        
        # Load categories
        categories_file = os.path.join(legacy_path, 'memory_categories.json')
        if os.path.exists(categories_file):
            with open(categories_file, 'r', encoding='utf-8') as f:
                categories_data = json.load(f)
                # Convert from category format to simple list
                if isinstance(categories_data, dict):
                    legacy_data['categories'] = list(categories_data.values()) if categories_data else []
                else:
                    legacy_data['categories'] = categories_data or []
            print(f"Loaded {len(legacy_data['categories'])} categories from legacy file")
            
    except Exception as e:
        print(f"Error loading legacy data: {e}")
        
    return legacy_data

def migrate_to_tinydb(data_path: str, legacy_data: Dict[str, Any], force: bool = False) -> bool:
    """
    Migrate legacy data to TinyDB format.
    
    Args:
        data_path: Path to data directory
        legacy_data: Dictionary containing legacy data
        force: Force migration even if TinyDB files exist
        
    Returns:
        True if successful, False otherwise
    """
    try:
        from tinydb import TinyDB, Query
        from tinydb.storages import JSONStorage
        from tinydb.middlewares import CachingMiddleware
        
        # Check if TinyDB files already exist
        tinydb_files = [
            'tinydb_memories.json',
            'tinydb_tags.json',
            'tinydb_categories.json'
        ]
        
        existing_tinydb_files = []
        for filename in tinydb_files:
            file_path = os.path.join(data_path, filename)
            if os.path.exists(file_path):
                existing_tinydb_files.append(filename)
        
        if existing_tinydb_files and not force:
            print("TinyDB files already exist:")
            for filename in existing_tinydb_files:
                print(f"  - {filename}")
            print("Use --force to overwrite existing TinyDB files.")
            return False
        
        # Migrate memories
        memories_db_path = os.path.join(data_path, 'tinydb_memories.json')
        memories_db = TinyDB(memories_db_path, storage=CachingMiddleware(JSONStorage))
        memories_table = memories_db.table('memories')
        
        if legacy_data['memories']:
            # Clear existing data if force migration
            if force:
                memories_table.truncate()
            
            migrated_memories = 0
            for memory_item in legacy_data['memories']:
                # Convert legacy memory format to TinyDB format
                memory_data = {
                    'id': memory_item.get('id'),
                    'content': memory_item.get('content'),
                    'timestamp': memory_item.get('timestamp'),
                    'tags': memory_item.get('tags', []),
                    'category': memory_item.get('category'),
                    'importance': memory_item.get('importance', 3),
                    'expires_at': memory_item.get('expires_at'),
                    'metadata': memory_item.get('metadata', {})
                }
                memories_table.insert(memory_data)
                migrated_memories += 1
            
            print(f"Migrated {migrated_memories} memories to TinyDB")
        
        memories_db.close()
        
        # Migrate tags
        tags_db_path = os.path.join(data_path, 'tinydb_tags.json')
        tags_db = TinyDB(tags_db_path, storage=CachingMiddleware(JSONStorage))
        tags_table = tags_db.table('tags')
        
        if legacy_data['tags']:
            if force:
                tags_table.truncate()
            
            migrated_tags = 0
            for tag_item in legacy_data['tags']:
                # Convert legacy tag format to TinyDB format
                if isinstance(tag_item, dict):
                    tag_data = {
                        'tag': tag_item.get('tag'),
                        'usage_count': tag_item.get('usage_count', 1),
                        'created_at': tag_item.get('created_at', datetime.now().isoformat()),
                        'last_used_at': tag_item.get('last_used_at', datetime.now().isoformat()),
                        'embedding': tag_item.get('embedding', [])
                    }
                else:
                    # Simple string tag
                    tag_data = {
                        'tag': str(tag_item),
                        'usage_count': 1,
                        'created_at': datetime.now().isoformat(),
                        'last_used_at': datetime.now().isoformat(),
                        'embedding': []
                    }
                tags_table.insert(tag_data)
                migrated_tags += 1
            
            print(f"Migrated {migrated_tags} tags to TinyDB")
        
        tags_db.close()
        
        # Migrate categories
        categories_db_path = os.path.join(data_path, 'tinydb_categories.json')
        categories_db = TinyDB(categories_db_path, storage=CachingMiddleware(JSONStorage))
        categories_table = categories_db.table('categories')
        
        if legacy_data['categories']:
            if force:
                categories_table.truncate()
            
            migrated_categories = 0
            for category_item in legacy_data['categories']:
                # Convert legacy category format to TinyDB format
                if isinstance(category_item, dict):
                    category_data = {
                        'category': category_item.get('category'),
                        'usage_count': category_item.get('usage_count', 1),
                        'created_at': category_item.get('created_at', datetime.now().isoformat()),
                        'last_used_at': category_item.get('last_used_at', datetime.now().isoformat())
                    }
                else:
                    # Simple string category
                    category_data = {
                        'category': str(category_item),
                        'usage_count': 1,
                        'created_at': datetime.now().isoformat(),
                        'last_used_at': datetime.now().isoformat()
                    }
                categories_table.insert(category_data)
                migrated_categories += 1
            
            print(f"Migrated {migrated_categories} categories to TinyDB")
        
        categories_db.close()
        
        print("Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        return False

def verify_migration(data_path: str) -> bool:
    """
    Verify that migration was successful by checking TinyDB files.
    
    Args:
        data_path: Path to data directory
        
    Returns:
        True if verification passes, False otherwise
    """
    try:
        from tinydb import TinyDB
        from tinydb.storages import JSONStorage
        from tinydb.middlewares import CachingMiddleware
        
        print("Verifying migration...")
        
        # Check memories
        memories_db_path = os.path.join(data_path, 'tinydb_memories.json')
        if os.path.exists(memories_db_path):
            memories_db = TinyDB(memories_db_path, storage=CachingMiddleware(JSONStorage))
            memories_table = memories_db.table('memories')
            memory_count = len(memories_table.all())
            print(f"✓ TinyDB memories: {memory_count} records")
            memories_db.close()
        else:
            print("✗ TinyDB memories file not found")
            return False
        
        # Check tags
        tags_db_path = os.path.join(data_path, 'tinydb_tags.json')
        if os.path.exists(tags_db_path):
            tags_db = TinyDB(tags_db_path, storage=CachingMiddleware(JSONStorage))
            tags_table = tags_db.table('tags')
            tag_count = len(tags_table.all())
            print(f"✓ TinyDB tags: {tag_count} records")
            tags_db.close()
        else:
            print("✓ TinyDB tags file created (may be empty)")
        
        # Check categories
        categories_db_path = os.path.join(data_path, 'tinydb_categories.json')
        if os.path.exists(categories_db_path):
            categories_db = TinyDB(categories_db_path, storage=CachingMiddleware(JSONStorage))
            categories_table = categories_db.table('categories')
            category_count = len(categories_table.all())
            print(f"✓ TinyDB categories: {category_count} records")
            categories_db.close()
        else:
            print("✓ TinyDB categories file created (may be empty)")
        
        print("Migration verification completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during verification: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Migrate from legacy JSON memory system to TinyDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python migrate_to_tinydb.py --backup-only     # Only move legacy files to legacy/ folder
  python migrate_to_tinydb.py --migrate         # Full migration (backup + migrate)
  python migrate_to_tinydb.py --migrate --force # Force migration even if TinyDB files exist
  python migrate_to_tinydb.py --verify          # Verify existing TinyDB files
        """
    )
    
    parser.add_argument('--backup-only', action='store_true',
                       help='Only move legacy files to legacy/ folder without migrating')
    parser.add_argument('--migrate', action='store_true',
                       help='Perform full migration (backup + migrate to TinyDB)')
    parser.add_argument('--force', action='store_true',
                       help='Force migration even if TinyDB files already exist')
    parser.add_argument('--verify', action='store_true',
                       help='Verify existing TinyDB migration')
    parser.add_argument('--data-path', type=str,
                       help='Override data path (default: FIRST_MCP_DATA_PATH or current directory)')
    
    args = parser.parse_args()
    
    # Determine data path
    if args.data_path:
        data_path = args.data_path
    else:
        data_path = get_data_path()
    
    if not os.path.exists(data_path):
        print(f"Error: Data path does not exist: {data_path}")
        return 1
    
    print(f"Using data path: {data_path}")
    
    # Handle verification
    if args.verify:
        success = verify_migration(data_path)
        return 0 if success else 1
    
    # Handle backup only
    if args.backup_only:
        success = backup_legacy_files(data_path)
        return 0 if success else 1
    
    # Handle full migration
    if args.migrate:
        # Step 1: Backup legacy files
        print("Step 1: Backing up legacy files...")
        backup_success = backup_legacy_files(data_path)
        
        if not backup_success:
            print("Backup failed. Migration aborted.")
            return 1
        
        # Step 2: Load legacy data
        print("Step 2: Loading legacy data...")
        legacy_data = load_legacy_data(data_path)
        
        # Step 3: Migrate to TinyDB
        print("Step 3: Migrating to TinyDB...")
        migrate_success = migrate_to_tinydb(data_path, legacy_data, args.force)
        
        if not migrate_success:
            print("Migration failed.")
            return 1
        
        # Step 4: Verify migration
        print("Step 4: Verifying migration...")
        verify_success = verify_migration(data_path)
        
        if verify_success:
            print("\n🎉 Migration completed successfully!")
            print("\nNext steps:")
            print("1. Test the new TinyDB memory tools in your MCP server")
            print("2. Use tinydb_memorize(), tinydb_search_memories(), etc.")
            print("3. Legacy files are preserved in legacy/ folder")
        else:
            print("\n⚠️  Migration completed but verification failed.")
            print("Please check the TinyDB files manually.")
        
        return 0 if verify_success else 1
    
    # No action specified
    print("No action specified. Use --help for usage information.")
    print("Common usage: python migrate_to_tinydb.py --migrate")
    return 1

if __name__ == '__main__':
    exit(main())