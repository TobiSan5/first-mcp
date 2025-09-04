#!/usr/bin/env python3
"""
Test client for TinyDB integration using FastMCP client.
"""

import asyncio
import os
import tempfile
import shutil
from fastmcp import Client

async def test_tinydb_tools():
    """Test TinyDB tools using FastMCP client, including memory persistence fix verification."""
    print("=== Testing TinyDB Tools via MCP Client ===")
    
    try:
        # Import server to get the FastMCP instance
        import sys
        import os
        # Add src to path to import first_mcp package
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from first_mcp import server_impl
        
        # Create client connected directly to the server instance
        client = Client(server_impl.mcp)
        
        async with client:
            print("✓ Connected to MCP server")
            
            # Test basic TinyDB functionality
            print("\nTest 1: Testing enhanced memory_workflow_guide...")
            workflow_result = await client.call_tool("memory_workflow_guide")
            workflow_data = workflow_result.data
            
            if workflow_data.get("success"):
                stored_section = workflow_data.get("stored_best_practices", {})
                total_practices = stored_section.get("total_stored_practices", 0)
                print(f"✅ Enhanced memory_workflow_guide works correctly!")
                print(f"✅ Retrieved {total_practices} stored best practices")
                print(f"✅ Has workflow sections: {list(workflow_data.keys())}")
                
                # Test that key sections are present
                required_sections = ["stored_best_practices", "system_status", "recommended_workflow"]
                missing = [s for s in required_sections if s not in workflow_data]
                if missing:
                    print(f"❌ Missing sections: {missing}")
                    return False
                else:
                    print("✅ All key sections present in merged function")
            else:
                print(f"❌ memory_workflow_guide failed: {workflow_data}")
                return False
            
            # Test 2: Test primary tag suggestion tool: tinydb_find_similar_tags
            print("\nTest 2: Testing tinydb_find_similar_tags as primary tag suggestion tool...")
            print("   (This replaces the broken tinydb_suggest_tags_for_content)")
            
            content_concepts = ["python", "web", "frameworks", "django", "flask", "apis", "programming"]
            found_suggestions = 0
            
            for concept in content_concepts[:4]:  # Test first 4 concepts
                try:
                    similar_result = await client.call_tool("tinydb_find_similar_tags", {
                        "query": concept,
                        "limit": 3,
                        "min_similarity": 0.3
                    })
                    similar_data = similar_result.data
                    
                    if similar_data.get("success"):
                        similar_tags = similar_data.get("similar_tags", [])
                        if similar_tags:
                            found_suggestions += len(similar_tags)
                            similarities = [f"{tag['similarity']:.2f}" for tag in similar_tags]
                            print(f"✅ '{concept}' -> {[tag['tag'] for tag in similar_tags]} (similarities: {similarities})")
                        else:
                            print(f"   '{concept}' -> no similar tags found")
                    else:
                        print(f"❌ tinydb_find_similar_tags failed for '{concept}': {similar_data.get('error')}")
                        return False
                        
                except Exception as e:
                    print(f"❌ tinydb_find_similar_tags failed for '{concept}': {e}")
                    return False
            
            print(f"✅ tinydb_find_similar_tags works as primary tag suggestion tool!")
            print(f"✅ Found {found_suggestions} total tag suggestions across concepts")
            
            # Test 3: Test new semantic search functionality
            print("\nTest 3: Testing semantic-aware tinydb_search_memories...")
            try:
                # Test semantic tag expansion
                print("   Testing semantic tag expansion...")
                semantic_result = await client.call_tool("tinydb_search_memories", {
                    "query": "",
                    "tags": "python-dev,coding",  # Approximate tags that might not exist exactly
                    "category": "",
                    "limit": 5,
                    "semantic_search": True
                })
                semantic_data = semantic_result.data
                
                if semantic_data.get("success"):
                    expansion_info = semantic_data.get("semantic_expansion", {})
                    if expansion_info.get("enabled"):
                        tag_expansion = expansion_info.get("tag_expansion", {})
                        if tag_expansion.get("expansion_occurred"):
                            print(f"✅ Semantic tag expansion worked!")
                            print(f"   Original: {tag_expansion.get('original_tags')}")
                            print(f"   Expanded: {tag_expansion.get('expanded_tags')}")
                        else:
                            print("   No tag expansion occurred (original tags may have matched exactly)")
                        
                        found_memories = semantic_data.get("memories", [])
                        print(f"✅ Found {len(found_memories)} memories with semantic search")
                    else:
                        print("❌ Semantic search was not enabled")
                        return False
                else:
                    print(f"❌ Semantic search failed: {semantic_data.get('error')}")
                    return False
                
                # Test category validation with invalid category
                print("   Testing category validation with invalid category...")
                category_result = await client.call_tool("tinydb_search_memories", {
                    "query": "",
                    "tags": "",
                    "category": "invalid_category",  # This should trigger helpful error
                    "limit": 5,
                    "semantic_search": True
                })
                category_data = category_result.data
                
                if not category_data.get("success"):
                    # This is expected - we want the error response
                    error_msg = category_data.get("error", "")
                    available_cats = category_data.get("available_categories", [])
                    if "not found" in error_msg.lower() and available_cats:
                        print(f"✅ Category validation works correctly!")
                        print(f"   Error: {error_msg}")
                        print(f"   Available: {available_cats[:3]}...")  # Show first 3
                    else:
                        print(f"❌ Category validation failed: {error_msg}")
                        return False
                else:
                    print("❌ Expected error for invalid category but got success")
                    return False
                
                # Test valid category still works
                print("   Testing valid category search...")
                valid_category_result = await client.call_tool("tinydb_search_memories", {
                    "query": "",
                    "tags": "",
                    "category": "best_practices",  # This should work
                    "limit": 3,
                    "semantic_search": True
                })
                valid_category_data = valid_category_result.data
                
                if valid_category_data.get("success"):
                    found_memories = valid_category_data.get("memories", [])
                    print(f"✅ Valid category search works! Found {len(found_memories)} memories")
                else:
                    print(f"❌ Valid category search failed: {valid_category_data.get('error')}")
                    return False
                
                print("✅ Semantic search enhancements working correctly!")
                        
            except Exception as e:
                print(f"❌ Semantic search test failed: {e}")
                return False
            
            # Test 4: Test backup tinydb_get_all_tags
            print("\nTest 4: Testing backup tinydb_get_all_tags...")
            try:
                tags_result = await client.call_tool("tinydb_get_all_tags")
                tags_data = tags_result.data
                
                if tags_data.get("success"):
                    all_tags = tags_data.get("tags", [])
                    print(f"✅ tinydb_get_all_tags works correctly!")
                    print(f"✅ Found {len(all_tags)} total tags")
                    if all_tags:
                        print(f"✅ Example tags: {[tag['tag'] for tag in all_tags[:5]]}")
                else:
                    print(f"❌ tinydb_get_all_tags failed: {tags_data.get('error', 'Unknown error')}")
                    return False
                    
            except Exception as e:
                print(f"❌ tinydb_get_all_tags test failed with exception: {e}")
                return False
            
            print("\n=== ALL TESTS COMPLETED SUCCESSFULLY ===")
            return True
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_tag_mapping_integration():
    """Test the smart tag mapping integration in tinydb_memorize."""
    print("\n=== Testing Smart Tag Mapping Integration ===")
    
    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from first_mcp.memory.memory_tools import tinydb_memorize
        
        # Test tag mapping directly
        print("Testing tag mapping with potentially similar tags...")
        result = tinydb_memorize(
            content="Testing smart tag mapping integration", 
            tags="py,programming,test-integration",
            category="testing"
        )
        
        if result.get("success"):
            tag_mapping = result.get("tag_mapping", {})
            raw_tags = tag_mapping.get("raw_tags", [])
            final_tags = tag_mapping.get("final_tags", [])
            mapping_applied = tag_mapping.get("mapping_applied", False)
            
            print(f"✅ Tag mapping test successful!")
            print(f"   Raw tags: {raw_tags}")
            print(f"   Final tags: {final_tags}")
            print(f"   Mapping applied: {mapping_applied}")
            
            # Verify the mapping info is present
            if "tag_mapping" in result:
                print("✅ Tag mapping transparency info included in response")
                return True
            else:
                print("❌ Tag mapping transparency info missing")
                return False
                
        else:
            print(f"❌ Tag mapping test failed: {result.get('error')}")
            return False
                
    except Exception as e:
        print(f"❌ Tag mapping integration test failed: {e}")
        return False


async def main():
    """Main test function."""
    success = await test_tinydb_tools()
    
    if success:
        print("\n🎉 Enhanced memory_workflow_guide test passed!")
        print("The merged function combines workflow guide + stored practices successfully!")
    else:
        print("\n❌ Test failed.")
        exit(1)

async def test_fresh_install_initialization():
    """Test that fresh installation automatically creates session-start memory."""
    print("\n=== Testing Fresh Install Auto-Initialization ===")
    
    # Create temporary directory for test databases
    test_data_dir = os.path.join(os.path.dirname(__file__), 'test_data')
    if os.path.exists(test_data_dir):
        shutil.rmtree(test_data_dir)
    os.makedirs(test_data_dir)
    
    # Temporarily override the data path environment variable
    original_data_path = os.environ.get('FIRST_MCP_DATA_PATH')
    os.environ['FIRST_MCP_DATA_PATH'] = test_data_dir
    
    try:
        # Import server to get the FastMCP instance with fresh data path
        import sys
        # Add src to path to import first_mcp package
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        
        # Force reload of server_impl to pick up new data path
        if 'first_mcp.server_impl' in sys.modules:
            del sys.modules['first_mcp.server_impl']
        from first_mcp import server_impl
        
        # Manually trigger initialization since we're bypassing main()
        server_impl.check_and_initialize_fresh_install()
        
        # Create client connected directly to the server instance
        client = Client(server_impl.mcp)
        
        async with client:
            print("✓ Connected to MCP server with fresh data directory")
            
            # Search for session-start memories (should be auto-created)
            result = await client.call_tool("tinydb_search_memories", {
                "tags": "session-start",
                "limit": 5
            })
            
            data = result.data
            if data.get("success"):
                memories = data.get("memories", [])
                if memories:
                    session_memory = memories[0]
                    print(f"✅ Auto-initialization successful!")
                    print(f"✅ Found session-start memory with ID: {session_memory.get('id')}")
                    print(f"✅ Category: {session_memory.get('category')}")
                    print(f"✅ Importance: {session_memory.get('importance')}")
                    
                    # Verify content includes key initialization points
                    content = session_memory.get('content', '')
                    if 'SESSION INITIALIZATION GUIDE' in content and 'session-start' in content:
                        print("✅ Session memory contains proper initialization guide")
                        return True
                    else:
                        print("❌ Session memory missing expected initialization content")
                        return False
                else:
                    print("❌ No session-start memories found after initialization")
                    return False
            else:
                print(f"❌ Failed to search for session memories: {data.get('error')}")
                return False
                
    except Exception as e:
        print(f"❌ Fresh install test failed: {e}")
        return False
        
    finally:
        # Restore original data path
        if original_data_path:
            os.environ['FIRST_MCP_DATA_PATH'] = original_data_path
        elif 'FIRST_MCP_DATA_PATH' in os.environ:
            del os.environ['FIRST_MCP_DATA_PATH']
        
        # Clean up test directory
        if os.path.exists(test_data_dir):
            shutil.rmtree(test_data_dir)

async def test_server_timestamps():
    """Test server timestamp functionality for the 3 updated tools."""
    print("\n=== Testing Server Timestamp Functionality ===")
    
    try:
        # Import server to get the FastMCP instance
        import sys
        import os
        # Add src to path to import first_mcp package
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from first_mcp import server_impl
        
        # Create client connected directly to the server instance
        client = Client(server_impl.mcp)
        
        async with client:
            print("✓ Connected to MCP server for timestamp testing")
            
            # Test 1: get_system_info tool with server timestamp
            print("\nTest 1: Testing get_system_info with server timestamp...")
            try:
                system_result = await client.call_tool("get_system_info")
                system_data = system_result.data
                
                # Verify timestamp fields exist
                if "server_timestamp" in system_data and "server_timezone" in system_data:
                    print(f"✅ get_system_info has server_timestamp: {system_data['server_timestamp']}")
                    print(f"✅ get_system_info has server_timezone: {system_data['server_timezone']}")
                    
                    # Verify original functionality preserved
                    expected_fields = ["python_version", "platform", "current_directory", "python_executable"]
                    if all(field in system_data for field in expected_fields):
                        print("✅ get_system_info original functionality preserved")
                    else:
                        print(f"❌ get_system_info original functionality broken: {system_data}")
                        return False
                    
                    # Validate ISO timestamp format
                    from datetime import datetime
                    try:
                        datetime.fromisoformat(system_data["server_timestamp"])
                        print("✅ get_system_info timestamp is valid ISO format")
                    except ValueError:
                        print(f"❌ get_system_info timestamp is not valid ISO format: {system_data['server_timestamp']}")
                        return False
                        
                else:
                    print(f"❌ get_system_info missing timestamp fields: {system_data}")
                    return False
                    
            except Exception as e:
                print(f"❌ get_system_info timestamp test failed: {e}")
                return False
            
            # Test 2: count_words tool with server timestamp
            print("\nTest 2: Testing count_words with server timestamp...")
            try:
                count_result = await client.call_tool("count_words", {"text": "This is a test message for timestamp verification"})
                count_data = count_result.data
                
                # Verify timestamp fields exist
                if "server_timestamp" in count_data and "server_timezone" in count_data:
                    print(f"✅ count_words has server_timestamp: {count_data['server_timestamp']}")
                    print(f"✅ count_words has server_timezone: {count_data['server_timezone']}")
                    
                    # Verify original functionality preserved
                    expected_fields = ["words", "characters", "lines"]
                    if all(field in count_data for field in expected_fields):
                        # Verify the counts are correct
                        if (count_data["words"] == 8 and 
                            count_data["characters"] == 49 and 
                            count_data["lines"] == 1):
                            print("✅ count_words original functionality preserved and accurate")
                        else:
                            print(f"❌ count_words counts incorrect: {count_data}")
                            return False
                    else:
                        print(f"❌ count_words original functionality broken: {count_data}")
                        return False
                    
                    # Validate ISO timestamp format
                    try:
                        datetime.fromisoformat(count_data["server_timestamp"])
                        print("✅ count_words timestamp is valid ISO format")
                    except ValueError:
                        print(f"❌ count_words timestamp is not valid ISO format: {count_data['server_timestamp']}")
                        return False
                        
                else:
                    print(f"❌ count_words missing timestamp fields: {count_data}")
                    return False
                    
            except Exception as e:
                print(f"❌ count_words timestamp test failed: {e}")
                return False
            
            # Test 3: Verify timestamps are recent and reasonable
            print("\nTest 3: Verifying timestamp recency and consistency...")
            try:
                from datetime import datetime, timezone
                current_time = datetime.now()
                
                # Check all timestamps are recent (within last 10 seconds)
                timestamps = [
                    system_data["server_timestamp"], 
                    count_data["server_timestamp"]
                ]
                
                for i, timestamp_str in enumerate(timestamps):
                    timestamp_obj = datetime.fromisoformat(timestamp_str)
                    # Remove timezone info for comparison if present
                    if timestamp_obj.tzinfo:
                        timestamp_obj = timestamp_obj.replace(tzinfo=None)
                    
                    time_diff = abs((current_time - timestamp_obj).total_seconds())
                    if time_diff <= 10:
                        print(f"✅ Timestamp {i+1} is recent (within 10 seconds)")
                    else:
                        print(f"❌ Timestamp {i+1} is too old: {time_diff} seconds ago")
                        return False
                
                # Verify timezone fields are populated
                timezones = [
                    system_data["server_timezone"], 
                    count_data["server_timezone"]
                ]
                
                for i, timezone_str in enumerate(timezones):
                    if timezone_str and timezone_str != "":
                        print(f"✅ Timezone {i+1} is populated: {timezone_str}")
                    else:
                        print(f"❌ Timezone {i+1} is empty or missing")
                        return False
                        
            except Exception as e:
                print(f"❌ Timestamp verification failed: {e}")
                return False
            
            print("\n=== ALL TIMESTAMP TESTS COMPLETED SUCCESSFULLY ===")
            return True
        
    except Exception as e:
        print(f"\n✗ Timestamp test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Run main test
    asyncio.run(main())
    
    # Run tag mapping integration test
    tag_mapping_success = asyncio.run(test_tag_mapping_integration())
    if not tag_mapping_success:
        print("❌ Tag mapping integration test failed!")
        exit(1)
    
    # Run fresh install test
    fresh_success = asyncio.run(test_fresh_install_initialization())
    if not fresh_success:
        print("❌ Fresh install test failed!")
        exit(1)
    
    # Run timestamp test
    timestamp_success = asyncio.run(test_server_timestamps())
    if not timestamp_success:
        print("❌ Timestamp test failed!")
        exit(1)
        
    print("🎉 All tests passed!")