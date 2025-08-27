#!/usr/bin/env python3
"""
Test TinyDB persistence functionality.

This test verifies that TinyDB databases are properly writing data to disk
and that we can read back what we write.
"""

import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add current directory to path so we can import server modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import TinyDB directly to test low-level persistence
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

def get_test_data_path():
    """Get test data directory."""
    test_path = os.path.join(os.getcwd(), 'test_data')
    os.makedirs(test_path, exist_ok=True)
    return test_path

def test_basic_tinydb_persistence():
    """Test basic TinyDB write and read operations."""
    print("=== Testing Basic TinyDB Persistence ===")
    
    test_path = get_test_data_path()
    db_file = os.path.join(test_path, 'test_persistence.json')
    
    # Remove existing test file
    if os.path.exists(db_file):
        os.remove(db_file)
    
    try:
        # Test 1: Create database and insert data
        print("Test 1: Creating database and inserting data...")
        db = TinyDB(db_file, storage=CachingMiddleware(JSONStorage))
        
        test_table = db.table('test_records')
        test_id = str(uuid.uuid4())
        test_data = {
            "id": test_id,
            "content": "Test record for persistence check",
            "timestamp": datetime.now().isoformat(),
            "test": True
        }
        
        # Insert data
        result = test_table.insert(test_data)
        print(f"✓ Data inserted with doc ID: {result}")
        
        # Verify data exists in current session
        Record = Query()
        found = test_table.search(Record.id == test_id)
        print(f"✓ Found {len(found)} records in current session")
        
        # Check file size before close
        file_size_before = os.path.getsize(db_file) if os.path.exists(db_file) else 0
        print(f"File size before close: {file_size_before} bytes")
        
        # Close database to force write
        db.close()
        
        # Check file size after close
        file_size_after = os.path.getsize(db_file) if os.path.exists(db_file) else 0
        print(f"File size after close: {file_size_after} bytes")
        
        if file_size_after == 0:
            print("❌ CRITICAL: Database file is empty after close!")
            return False
        
        # Test 2: Reopen database and verify data persistence
        print("\nTest 2: Reopening database to verify persistence...")
        db = TinyDB(db_file, storage=CachingMiddleware(JSONStorage))
        
        test_table = db.table('test_records')
        all_records = test_table.all()
        found_records = test_table.search(Record.id == test_id)
        
        print(f"✓ Total records found after reopening: {len(all_records)}")
        print(f"✓ Test record found: {len(found_records) > 0}")
        
        if found_records:
            print(f"✓ Test record content: {found_records[0]['content']}")
            persistence_success = found_records[0]['content'] == test_data['content']
        else:
            persistence_success = False
        
        db.close()
        
        print(f"✓ Persistence test result: {'PASS' if persistence_success else 'FAIL'}")
        return persistence_success
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False
    finally:
        # Cleanup
        if os.path.exists(db_file):
            os.remove(db_file)
        try:
            os.rmdir(test_path)
        except:
            pass

def test_server_tinydb_functions():
    """Test the actual server TinyDB functions."""
    print("\n=== Testing Server TinyDB Functions ===")
    
    try:
        # Import server functions
        import server
        
        # Test tinydb_memorize
        print("Test 1: Testing tinydb_memorize function...")
        result = server.tinydb_memorize(
            content="Test memory for persistence check",
            tags="test,persistence",
            category="test",
            importance=4
        )
        
        print(f"Memorize result: {result}")
        
        if not result.get('success'):
            print("❌ tinydb_memorize failed")
            return False
        
        memory_id = result.get('memory_id')
        print(f"✓ Memory stored with ID: {memory_id}")
        
        # Test tinydb_recall_memory
        print("\nTest 2: Testing tinydb_recall_memory function...")
        recall_result = server.tinydb_recall_memory(memory_id)
        print(f"Recall result: {recall_result}")
        
        if not recall_result.get('success'):
            print("❌ tinydb_recall_memory failed")
            return False
        
        print("✓ Memory recalled successfully")
        
        # Test tinydb_list_memories
        print("\nTest 3: Testing tinydb_list_memories function...")
        list_result = server.tinydb_list_memories()
        print(f"List result - Total memories: {list_result.get('total_active', 0)}")
        
        if list_result.get('total_active', 0) == 0:
            print("❌ tinydb_list_memories shows 0 memories")
            return False
        
        print("✓ Memory list shows stored memories")
        
        # Test tinydb_memory_stats
        print("\nTest 4: Testing tinydb_memory_stats function...")
        stats_result = server.tinydb_memory_stats()
        print(f"Stats result - Total memories: {stats_result.get('total_memories', 0)}")
        
        if stats_result.get('total_memories', 0) == 0:
            print("❌ tinydb_memory_stats shows 0 memories")
            return False
        
        print("✓ Memory stats show stored memories")
        
        return True
        
    except Exception as e:
        print(f"❌ Server function test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_file_inspection():
    """Inspect actual TinyDB database files."""
    print("\n=== Inspecting Database Files ===")
    
    data_path = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
    
    db_files = [
        'tinydb_memories.json',
        'tinydb_tags.json', 
        'tinydb_categories.json'
    ]
    
    for db_file in db_files:
        file_path = os.path.join(data_path, db_file)
        
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            print(f"📁 {db_file}: {file_size} bytes")
            
            if file_size > 0:
                try:
                    # Try to open and read the file
                    db = TinyDB(file_path)
                    table_names = db.tables()
                    print(f"   Tables: {table_names}")
                    
                    for table_name in table_names:
                        table = db.table(table_name)
                        record_count = len(table.all())
                        print(f"   - {table_name}: {record_count} records")
                    
                    db.close()
                except Exception as e:
                    print(f"   ❌ Error reading file: {e}")
            else:
                print(f"   ⚠️  File exists but is empty")
        else:
            print(f"📁 {db_file}: File does not exist")

def main():
    """Run all tests."""
    print("TinyDB Persistence Test Suite")
    print("=" * 40)
    
    # Test 1: Basic TinyDB functionality
    basic_test_passed = test_basic_tinydb_persistence()
    
    # Test 2: Server function integration
    server_test_passed = test_server_tinydb_functions()
    
    # Test 3: Database file inspection
    test_database_file_inspection()
    
    # Summary
    print("\n" + "=" * 40)
    print("Test Summary:")
    print(f"Basic TinyDB Persistence: {'PASS' if basic_test_passed else 'FAIL'}")
    print(f"Server Function Integration: {'PASS' if server_test_passed else 'FAIL'}")
    
    overall_success = basic_test_passed and server_test_passed
    print(f"Overall Result: {'ALL TESTS PASS' if overall_success else 'SOME TESTS FAILED'}")
    
    if not overall_success:
        print("\n🔧 Suggested fixes:")
        print("1. Ensure all TinyDB instances are properly closed with db.close()")
        print("2. Check CachingMiddleware is flushing data to disk")
        print("3. Verify file permissions in data directory")
        print("4. Test with a simple TinyDB example to isolate the issue")
    
    return 0 if overall_success else 1

if __name__ == '__main__':
    exit(main())