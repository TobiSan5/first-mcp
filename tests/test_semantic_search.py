#!/usr/bin/env python3
"""
Test demonstrating current search limitations and proposed semantic improvements.
"""

import asyncio
from fastmcp import Client

async def demonstrate_search_limitations():
    """Demonstrate current search limitations that semantic search would solve."""
    print("=== Demonstrating Current Search Limitations ===")
    
    try:
        # Import server to get the FastMCP instance
        import sys
        import os
        # Add src to path to import first_mcp package
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from first_mcp import server_impl as server
        
        # Create client connected directly to the server instance
        client = Client(server.mcp)
        
        async with client:
            print("✓ Connected to MCP server")
            
            # Test 1: Search with approximate/suggestive tags
            print("\nTest 1: Searching with approximate tags...")
            test_cases = [
                {"tags": "python", "expected": "Should find programming-related memories"},
                {"tags": "web", "expected": "Should find web development memories"},
                {"tags": "api", "expected": "Should find API-related memories"},
                {"tags": "js", "expected": "Should find JavaScript memories (if 'javascript' tag exists)"},
                {"tags": "ml", "expected": "Should find machine learning memories (if related tags exist)"}
            ]
            
            for case in test_cases:
                print(f"\nSearching for tags: '{case['tags']}'")
                print(f"Expected: {case['expected']}")
                
                # Current search - exact tag matching only
                result = await client.call_tool("tinydb_search_memories", {
                    "tags": case["tags"],
                    "limit": 5
                })
                
                if result.data.get("success"):
                    memories = result.data.get("memories", [])
                    print(f"Current search found: {len(memories)} memories")
                    if memories:
                        for i, memory in enumerate(memories[:2], 1):
                            tags = memory.get("tags", [])
                            print(f"  {i}. Tags: {tags[:5]}...")  # Show first 5 tags
                    else:
                        print("  No memories found with exact tag match")
                        
                        # Show what similar tags exist
                        similar_result = await client.call_tool("tinydb_find_similar_tags", {
                            "query": case["tags"],
                            "limit": 3,
                            "min_similarity": 0.3
                        })
                        
                        if similar_result.data.get("success"):
                            similar_tags = similar_result.data.get("similar_tags", [])
                            if similar_tags:
                                print(f"  But similar tags exist: {[tag['tag'] for tag in similar_tags]}")
                                print("  → Semantic search would find these!")
                            else:
                                print("  No similar tags found either")
                else:
                    print(f"Search failed: {result.data.get('error')}")
            
            # Test 2: Category similarity demonstration
            print("\n\nTest 2: Category similarity potential...")
            categories = ["learnings", "projects", "facts", "best_practices"]
            
            for category in categories:
                result = await client.call_tool("tinydb_search_memories", {
                    "category": category,
                    "limit": 3
                })
                
                if result.data.get("success"):
                    count = result.data.get("total_found", 0)
                    print(f"Category '{category}': {count} memories")
                    
                    # Show related categories that could be searched
                    related = {
                        "learnings": ["projects", "best_practices", "corrections"],
                        "projects": ["learnings", "facts"],
                        "facts": ["user_context", "projects"],
                        "best_practices": ["learnings", "corrections", "reminders"]
                    }.get(category, [])
                    
                    if related:
                        print(f"  Related categories: {related}")
                        print(f"  → Semantic search could also search these!")
            
            # Test 3: Show tag landscape
            print("\n\nTest 3: Current tag landscape...")
            tags_result = await client.call_tool("tinydb_get_all_tags")
            if tags_result.data.get("success"):
                all_tags = tags_result.data.get("tags", [])
                print(f"Total tags in system: {len(all_tags)}")
                
                # Show most used tags
                top_tags = [tag["tag"] for tag in all_tags[:10]]
                print(f"Top 10 most used tags: {top_tags}")
                
                # Show potential for similarity matching
                programming_related = [tag["tag"] for tag in all_tags if any(
                    word in tag["tag"].lower() for word in ["python", "code", "dev", "program", "script", "js", "web"]
                )][:10]
                
                if programming_related:
                    print(f"Programming-related tags found: {programming_related}")
                    print("→ These could be found with semantic search for 'programming', 'code', etc.")
            
            print("\n=== SUMMARY ===")
            print("Current limitations:")
            print("1. Exact tag matching misses semantically related content")
            print("2. Users must know exact tag names")
            print("3. No cross-category discovery")
            print("4. Manual tag discovery workflow required")
            print("\nSemantic search would solve:")
            print("1. Automatic tag expansion (js → javascript)")
            print("2. Similar tag discovery (python → programming, development)")
            print("3. Related category search (learnings → projects, best_practices)")
            print("4. One-step search instead of multi-step workflow")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main test function."""
    await demonstrate_search_limitations()

if __name__ == "__main__":
    asyncio.run(main())