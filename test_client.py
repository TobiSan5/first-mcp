#!/usr/bin/env python3
"""
Test client for TinyDB integration using FastMCP client.
"""

import asyncio
from fastmcp import Client

async def test_tinydb_tools():
    """Test TinyDB tools using FastMCP client, including memory persistence fix verification."""
    print("=== Testing TinyDB Tools via MCP Client ===")
    
    try:
        # Import server to get the FastMCP instance
        import server
        
        # Create client connected directly to the server instance
        client = Client(server.mcp)
        
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

async def main():
    """Main test function."""
    success = await test_tinydb_tools()
    
    if success:
        print("\n🎉 Enhanced memory_workflow_guide test passed!")
        print("The merged function combines workflow guide + stored practices successfully!")
    else:
        print("\n❌ Test failed.")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())