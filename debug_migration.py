#!/usr/bin/env python3
"""
Debug script to test migration step by step.
"""

import os
import sys
import json

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from migrate_to_tinydb import get_data_path, load_legacy_data, migrate_to_tinydb

def debug_legacy_files():
    """Debug what's in the legacy files."""
    print("=== Debugging Legacy Files ===")
    
    data_path = get_data_path()
    legacy_path = os.path.join(data_path, 'legacy')
    
    print(f"Data path: {data_path}")
    print(f"Legacy path: {legacy_path}")
    print(f"Legacy path exists: {os.path.exists(legacy_path)}")
    
    if os.path.exists(legacy_path):
        legacy_files = os.listdir(legacy_path)
        print(f"Files in legacy folder: {legacy_files}")
        
        # Check each expected file
        for filename in ['memory_store.json', 'memory_tags.json', 'memory_categories.json']:
            file_path = os.path.join(legacy_path, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    print(f"\n📄 {filename}:")
                    print(f"  Type: {type(data)}")
                    print(f"  Length: {len(data) if isinstance(data, (list, dict)) else 'N/A'}")
                    
                    if isinstance(data, list) and len(data) > 0:
                        print(f"  First item: {data[0]}")
                        print(f"  First item type: {type(data[0])}")
                        if isinstance(data[0], dict):
                            print(f"  First item keys: {list(data[0].keys())}")
                    elif isinstance(data, dict) and len(data) > 0:
                        first_key = list(data.keys())[0]
                        print(f"  First key: {first_key}")
                        print(f"  First value: {data[first_key]}")
                        print(f"  First value type: {type(data[first_key])}")
                        
                except Exception as e:
                    print(f"❌ Error reading {filename}: {e}")
            else:
                print(f"⚠️  {filename} not found")
    else:
        print("❌ Legacy folder doesn't exist")

def debug_legacy_data_loading():
    """Debug the load_legacy_data function."""
    print("\n=== Debugging Legacy Data Loading ===")
    
    data_path = get_data_path()
    legacy_data = load_legacy_data(data_path)
    
    print(f"Loaded legacy data:")
    print(f"  Memories: {len(legacy_data['memories'])}")
    print(f"  Tags: {len(legacy_data['tags'])}")  
    print(f"  Categories: {len(legacy_data['categories'])}")
    
    if legacy_data['memories']:
        print(f"\nFirst memory:")
        first_memory = legacy_data['memories'][0]
        print(f"  Type: {type(first_memory)}")
        print(f"  Content: {first_memory}")
        if isinstance(first_memory, dict):
            print(f"  Keys: {list(first_memory.keys())}")
    
    if legacy_data['tags']:
        print(f"\nFirst tag:")
        first_tag = legacy_data['tags'][0]
        print(f"  Type: {type(first_tag)}")
        print(f"  Content: {first_tag}")
    
    if legacy_data['categories']:
        print(f"\nFirst category:")
        first_category = legacy_data['categories'][0]
        print(f"  Type: {type(first_category)}")
        print(f"  Content: {first_category}")
    
    return legacy_data

def debug_migration_process(legacy_data):
    """Debug the actual migration process."""
    print("\n=== Debugging Migration Process ===")
    
    if not legacy_data['memories']:
        print("❌ No memories to migrate")
        return
    
    try:
        from tinydb import TinyDB, Query
        from tinydb.storages import JSONStorage
        from tinydb.middlewares import CachingMiddleware
        from datetime import datetime
        
        data_path = get_data_path()
        
        # Test memory migration manually
        print("Testing memory migration manually...")
        memories_db_path = os.path.join(data_path, 'debug_memories.json')
        
        # Remove existing test file
        if os.path.exists(memories_db_path):
            os.remove(memories_db_path)
        
        memories_db = TinyDB(memories_db_path, storage=CachingMiddleware(JSONStorage))
        memories_table = memories_db.table('memories')
        
        print(f"Processing {len(legacy_data['memories'])} memories...")
        
        migrated_count = 0
        for i, memory_item in enumerate(legacy_data['memories']):
            print(f"\nProcessing memory {i+1}:")
            print(f"  Raw item: {memory_item}")
            print(f"  Type: {type(memory_item)}")
            
            if isinstance(memory_item, dict):
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
                
                print(f"  Converted data: {memory_data}")
                
                # Insert and immediately check
                result = memories_table.insert(memory_data)
                print(f"  Insert result: {result}")
                
                # Verify it's there
                all_records = memories_table.all()
                print(f"  Total records after insert: {len(all_records)}")
                
                migrated_count += 1
            else:
                print(f"  ❌ Skipping - not a dict: {type(memory_item)}")
        
        # Final verification before closing
        final_count_before_close = len(memories_table.all())
        print(f"\nFinal count before close: {final_count_before_close}")
        
        # Close database
        memories_db.close()
        print("Database closed")
        
        # Reopen and verify persistence
        memories_db = TinyDB(memories_db_path, storage=CachingMiddleware(JSONStorage))
        memories_table = memories_db.table('memories')
        final_count_after_reopen = len(memories_table.all())
        print(f"Final count after reopen: {final_count_after_reopen}")
        
        memories_db.close()
        
        # Check file size
        if os.path.exists(memories_db_path):
            file_size = os.path.getsize(memories_db_path)
            print(f"Database file size: {file_size} bytes")
        
        print(f"Migration test completed: {migrated_count} memories processed")
        
    except Exception as e:
        print(f"❌ Migration test failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run all debug steps."""
    print("Migration Debug Script")
    print("=" * 50)
    
    # Step 1: Check legacy files
    debug_legacy_files()
    
    # Step 2: Test legacy data loading
    legacy_data = debug_legacy_data_loading()
    
    # Step 3: Test migration process
    debug_migration_process(legacy_data)
    
    print("\n" + "=" * 50)
    print("Debug completed")

if __name__ == '__main__':
    main()