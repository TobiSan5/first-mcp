#!/usr/bin/env python3
"""
MCP Server Implementation Tests — Embedding Tools

Tests the compute_text_similarity and rank_texts_by_similarity MCP tools
via a FastMCP client. Tests cover:
- Tool registration (tools appear in discovery)
- Response structure (server_timestamp present)
- Graceful failure when API unavailable (success:False, not a crash)
- Context-aware similarity parameter acceptance
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


async def test_embedding_tools_registered():
    """Verify both embedding tools appear in MCP tool discovery."""
    print("=== Testing Embedding Tool Registration ===")
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]

            expected = ["compute_text_similarity", "rank_texts_by_similarity"]
            missing = [t for t in expected if t not in tool_names]

            if missing:
                print(f"❌ Missing embedding tools: {missing}")
                return False

            print(f"✅ Both embedding tools registered: {expected}")
            return True

    except Exception as e:
        print(f"❌ Tool registration test failed: {e}")
        return False


async def test_compute_text_similarity_structure():
    """
    Call compute_text_similarity and verify response structure.
    The call may succeed or fail depending on API availability — either way
    the response must be a dict with server_timestamp and a 'success' key.
    """
    print("\n=== Testing compute_text_similarity Response Structure ===")
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            result = await client.call_tool("compute_text_similarity", {
                "query": "faith and grace",
                "text": "For by grace you have been saved through faith."
            })
            data = result.data

            # Must be a dict
            if not isinstance(data, dict):
                print(f"❌ Expected dict, got {type(data)}: {data}")
                return False

            # Must have server_timestamp (added by MCP layer)
            if "server_timestamp" not in data:
                print(f"❌ Missing server_timestamp in response: {data}")
                return False

            # Must have success key
            if "success" not in data:
                print(f"❌ Missing 'success' key in response: {data}")
                return False

            # If successful, must have similarity score in [0, 1]
            if data["success"]:
                sim = data.get("similarity")
                if sim is None or not (0.0 <= sim <= 1.0):
                    print(f"❌ Invalid similarity score: {sim}")
                    return False
                print(f"✅ compute_text_similarity succeeded, similarity={sim}")
            else:
                # Graceful failure — must have error message
                if "error" not in data:
                    print(f"❌ Failed response missing 'error' key: {data}")
                    return False
                print(f"✅ compute_text_similarity failed gracefully: {data['error'][:60]}")

            print("✅ Response structure correct")
            return True

    except Exception as e:
        print(f"❌ compute_text_similarity structure test failed: {e}")
        return False


async def test_compute_text_similarity_with_context():
    """
    Call compute_text_similarity with context and weight parameters.
    Verifies the MCP layer accepts all parameters and returns a valid structure.
    """
    print("\n=== Testing compute_text_similarity with Context Parameters ===")
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            result = await client.call_tool("compute_text_similarity", {
                "query": "grace_follows_faith",
                "text": "For by grace you have been saved through faith.",
                "context": "Paul writes to the Ephesians about salvation not of works.",
                "text_weight": 0.7,
                "context_weight": 0.3
            })
            data = result.data

            if not isinstance(data, dict):
                print(f"❌ Expected dict, got {type(data)}: {data}")
                return False

            if "server_timestamp" not in data or "success" not in data:
                print(f"❌ Missing required keys in response: {data}")
                return False

            if data["success"]:
                # context_used should be True and reported in response
                if not data.get("context_used"):
                    print(f"❌ context_used should be True when context provided: {data}")
                    return False
                print(f"✅ Context-aware similarity succeeded, similarity={data.get('similarity')}")
            else:
                print(f"✅ Context-aware call failed gracefully: {data.get('error', '')[:60]}")

            print("✅ Context parameter handling correct")
            return True

    except Exception as e:
        print(f"❌ Context similarity test failed: {e}")
        return False


async def test_rank_texts_by_similarity_structure():
    """
    Call rank_texts_by_similarity and verify response structure.
    Accepts both API success and graceful failure.
    """
    print("\n=== Testing rank_texts_by_similarity Response Structure ===")
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            candidates = [
                "Salvation comes through faith in Christ.",
                "The temple was destroyed in 70 AD.",
                "Grace is a gift not earned by works."
            ]
            result = await client.call_tool("rank_texts_by_similarity", {
                "query": "grace_follows_faith",
                "candidates": candidates
            })
            data = result.data

            if not isinstance(data, dict):
                print(f"❌ Expected dict, got {type(data)}: {data}")
                return False

            if "server_timestamp" not in data or "success" not in data:
                print(f"❌ Missing required keys in response: {data}")
                return False

            if data["success"]:
                ranked = data.get("ranked", [])
                if not isinstance(ranked, list):
                    print(f"❌ 'ranked' should be a list: {ranked}")
                    return False

                # Verify descending order
                scores = [r["similarity"] for r in ranked]
                if scores != sorted(scores, reverse=True):
                    print(f"❌ Results not sorted by descending similarity: {scores}")
                    return False

                print(f"✅ rank_texts_by_similarity succeeded, ranked {len(ranked)} candidates")
            else:
                if "error" not in data:
                    print(f"❌ Failed response missing 'error' key: {data}")
                    return False
                print(f"✅ rank_texts_by_similarity failed gracefully: {data['error'][:60]}")

            print("✅ Response structure correct")
            return True

    except Exception as e:
        print(f"❌ rank_texts_by_similarity structure test failed: {e}")
        return False


async def test_rank_texts_empty_candidates():
    """Empty candidates list should return success:False with an error, not crash."""
    print("\n=== Testing rank_texts_by_similarity with Empty Candidates ===")
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            result = await client.call_tool("rank_texts_by_similarity", {
                "query": "test query",
                "candidates": []
            })
            data = result.data

            if data.get("success"):
                print(f"❌ Should not succeed with empty candidates: {data}")
                return False

            if "error" not in data:
                print(f"❌ Missing error message for empty candidates: {data}")
                return False

            print("✅ Empty candidates handled gracefully")
            return True

    except Exception as e:
        print(f"❌ Empty candidates test failed: {e}")
        return False


async def main():
    """Run all embedding tool MCP tests."""
    print("🚀 Starting MCP Server Implementation Tests — Embedding Tools\n")

    tests = [
        test_embedding_tools_registered,
        test_compute_text_similarity_structure,
        test_compute_text_similarity_with_context,
        test_rank_texts_by_similarity_structure,
        test_rank_texts_empty_candidates,
    ]

    results = []
    for test in tests:
        success = await test()
        results.append(success)
        if not success:
            print(f"\n❌ Test {test.__name__} failed — stopping.")
            break

    if all(results):
        print("\n🎉 All Embedding Tool Tests Passed!")
        return True
    else:
        print("\n❌ Embedding Tool Tests Failed!")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
