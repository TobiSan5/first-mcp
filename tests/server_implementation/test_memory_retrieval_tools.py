#!/usr/bin/env python3
"""
MCP Server Implementation Tests — Memory Retrieval Tools

Tests the MCP layer for the three retrieval tools via FastMCP client:
  - tinydb_search_memories  (tag scoring + pagination)
  - tinydb_list_memories    (pagination)
  - memory_next_page        (new tool)
  - memory_workflow_guide   (internal call must not be silently truncated)

Tests use a temp FIRST_MCP_DATA_PATH so no production data is touched.
GOOGLE_API_KEY is not required; the tag-scoring path test is skipped when
no key is present and executed (with graceful API-failure acceptance) when
a key is set.

Coverage:
  - Tool registration
  - Response structure (server_timestamp, pagination fields)
  - Graceful error on bad next_page_token
  - scoring_method field correctness
  - End-to-end pagination round-trip (insert memories → search → next_page)
  - memory_workflow_guide returns all best_practices (regression: page_size fix)
  - Tag-scoring path exercised through the MCP layer (API-conditional)
"""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Point all TinyDB writes to a temporary directory for the entire test session
_TMPDIR = tempfile.mkdtemp()
os.environ['FIRST_MCP_DATA_PATH'] = _TMPDIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _insert_memories(client, n: int, tag: str = "test-pagination") -> list:
    """Insert n memories via tinydb_memorize and return their IDs."""
    ids = []
    for i in range(n):
        res = await client.call_tool("tinydb_memorize", {
            "content": f"Test memory number {i} for pagination verification.",
            "tags": tag,
            "importance": 3,
        })
        data = res.data
        if data.get("success"):
            ids.append(data.get("memory_id"))
    return ids


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

async def test_memory_tools_registered():
    """All three retrieval tools (including new memory_next_page) are discoverable."""
    print("=== Testing Memory Retrieval Tool Registration ===")
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        expected = ["tinydb_search_memories", "tinydb_list_memories", "memory_next_page"]
        missing = [t for t in expected if t not in names]

        if missing:
            print(f"❌ Missing tools: {missing}")
            return False

        print(f"✅ All retrieval tools registered: {expected}")
        return True

    except Exception as e:
        print(f"❌ Registration check failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------

async def test_search_response_structure():
    """
    tinydb_search_memories response must include server_timestamp and the new
    pagination fields: has_more, next_page_token, scoring_method.
    """
    print("\n=== Testing tinydb_search_memories Response Structure ===")
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            result = await client.call_tool("tinydb_search_memories", {
                "query": "nonexistent-sentinel-xyz"
            })
            data = result.data

        if not isinstance(data, dict):
            print(f"❌ Expected dict, got {type(data)}")
            return False

        required = ["server_timestamp", "success", "has_more", "next_page_token", "scoring_method"]
        missing = [k for k in required if k not in data]
        if missing:
            print(f"❌ Missing response keys: {missing} — got: {list(data.keys())}")
            return False

        print(f"✅ Response has all required keys: {required}")
        return True

    except Exception as e:
        print(f"❌ Search response structure test failed: {e}")
        return False


async def test_list_response_structure():
    """
    tinydb_list_memories response must include server_timestamp and pagination
    fields: has_more, next_page_token.
    """
    print("\n=== Testing tinydb_list_memories Response Structure ===")
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            result = await client.call_tool("tinydb_list_memories", {})
            data = result.data

        if not isinstance(data, dict):
            print(f"❌ Expected dict, got {type(data)}")
            return False

        required = ["server_timestamp", "success", "has_more", "next_page_token"]
        missing = [k for k in required if k not in data]
        if missing:
            print(f"❌ Missing response keys: {missing}")
            return False

        print("✅ tinydb_list_memories response structure correct")
        return True

    except Exception as e:
        print(f"❌ List response structure test failed: {e}")
        return False


async def test_next_page_bad_token_returns_error():
    """
    memory_next_page with an unknown token returns a response dict (not a crash)
    containing success=False and an error message.
    """
    print("\n=== Testing memory_next_page with Bad Token ===")
    try:
        from first_mcp import server_impl
        from fastmcp import Client
        import uuid

        client = Client(server_impl.mcp)
        async with client:
            result = await client.call_tool("memory_next_page", {
                "next_page_token": str(uuid.uuid4())
            })
            data = result.data

        if not isinstance(data, dict):
            print(f"❌ Expected dict, got {type(data)}")
            return False

        if "server_timestamp" not in data:
            print(f"❌ Missing server_timestamp: {data}")
            return False

        if data.get("success") is not False:
            print(f"❌ Expected success=False for bad token, got: {data.get('success')}")
            return False

        if "error" not in data:
            print(f"❌ Missing error key in failure response: {data}")
            return False

        print(f"✅ Bad token returned clean error: {data['error'][:60]}")
        return True

    except Exception as e:
        print(f"❌ Bad token test failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Pagination round-trip
# ---------------------------------------------------------------------------

async def test_search_pagination_round_trip():
    """
    Insert 8 memories with a unique tag, search with page_size=3.
    Verify: first page has 3 results, total_found=8, has_more=True, token present.
    Then call memory_next_page until exhausted and verify all 8 IDs are collected
    exactly once.
    """
    print("\n=== Testing tinydb_search_memories Pagination Round-Trip ===")
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            # Insert 8 test memories with a distinctive tag
            tag = "pagination-round-trip-test"
            inserted_ids = await _insert_memories(client, 8, tag=tag)

            if len(inserted_ids) < 8:
                print(f"❌ Only inserted {len(inserted_ids)}/8 memories — cannot proceed")
                return False

            # Search with page_size=3 and limit large enough to include all 8
            result = await client.call_tool("tinydb_search_memories", {
                "tags": tag,
                "page_size": 3,
                "limit": 50,
                "semantic_search": False,   # avoid API dependency in tests
            })
            data = result.data

            if not data.get("success"):
                print(f"❌ Search failed: {data.get('error')}")
                return False

            total_found = data.get("total_found", 0)
            if total_found < 8:
                print(f"❌ Expected total_found >= 8, got {total_found}")
                return False

            first_page = data.get("memories", [])
            if len(first_page) != 3:
                print(f"❌ Expected 3 results on first page, got {len(first_page)}")
                return False

            if not data.get("has_more"):
                print(f"❌ has_more should be True when total={total_found} > page_size=3")
                return False

            token = data.get("next_page_token")
            if not token:
                print("❌ next_page_token is missing despite has_more=True")
                return False

            print(f"   Page 1: {len(first_page)} memories, total_found={total_found}, token present ✓")

            # Collect all IDs across pages
            collected_ids = [m["id"] for m in first_page]
            page_num = 1

            while token:
                next_result = await client.call_tool("memory_next_page", {
                    "next_page_token": token
                })
                nd = next_result.data

                if not nd.get("success"):
                    print(f"❌ memory_next_page failed on page {page_num + 1}: {nd.get('error')}")
                    return False

                page_memories = nd.get("memories", [])
                collected_ids.extend(m["id"] for m in page_memories)
                token = nd.get("next_page_token")
                page_num += 1
                print(f"   Page {page_num}: {len(page_memories)} memories ✓")

            # All 8 inserted IDs should appear exactly once
            collected_set = set(collected_ids)
            inserted_set = set(inserted_ids)
            missing_from_pages = inserted_set - collected_set
            if missing_from_pages:
                print(f"❌ {len(missing_from_pages)} inserted memories never appeared in pages")
                return False

            # No duplicates
            if len(collected_ids) != len(collected_set):
                print(f"❌ Duplicate IDs found across pages: {len(collected_ids)} ids, {len(collected_set)} unique")
                return False

            print(f"✅ Pagination round-trip complete: {page_num} pages, all {len(inserted_ids)} inserted IDs collected once")
            return True

    except Exception as e:
        import traceback
        print(f"❌ Pagination round-trip test failed: {e}")
        traceback.print_exc()
        return False


async def test_list_pagination_round_trip():
    """
    With memories already in the DB from prior tests, list with page_size=2
    and verify the token / has_more contract holds.
    """
    print("\n=== Testing tinydb_list_memories Pagination Round-Trip ===")
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            result = await client.call_tool("tinydb_list_memories", {
                "page_size": 2,
                "limit": 100,
            })
            data = result.data

        if not data.get("success"):
            print(f"❌ list failed: {data.get('error')}")
            return False

        total = data.get("total_active", 0)
        first_page = data.get("memories", [])
        expected_page_len = min(2, total)

        if len(first_page) != expected_page_len:
            print(f"❌ Expected {expected_page_len} memories on first page, got {len(first_page)}")
            return False

        if total > 2:
            if not data.get("has_more"):
                print(f"❌ has_more should be True when total={total} > page_size=2")
                return False
            if not data.get("next_page_token"):
                print("❌ next_page_token missing despite has_more=True")
                return False

        print(f"✅ tinydb_list_memories pagination fields correct (total={total})")
        return True

    except Exception as e:
        print(f"❌ List pagination round-trip test failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Scoring method field
# ---------------------------------------------------------------------------

async def test_scoring_method_reported():
    """
    scoring_method in the response should reflect which path was taken:
    'importance' when no tags given, something else when tags given.
    """
    print("\n=== Testing scoring_method Field ===")
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            # No tags — should use importance sorting
            r_no_tags = await client.call_tool("tinydb_search_memories", {
                "query": "",
                "semantic_search": False,
            })
            d_no_tags = r_no_tags.data

            if d_no_tags.get("scoring_method") != "importance":
                print(f"❌ Expected scoring_method='importance', got '{d_no_tags.get('scoring_method')}'")
                return False

            # Tags given — method should be 'exact', 'string_expansion', or 'tag_scoring'
            r_with_tags = await client.call_tool("tinydb_search_memories", {
                "tags": "some-tag",
                "semantic_search": False,
            })
            d_with_tags = r_with_tags.data

            method = d_with_tags.get("scoring_method")
            if method not in ("exact", "string_expansion", "tag_scoring"):
                print(f"❌ Unexpected scoring_method when tags given: '{method}'")
                return False

        print(f"✅ scoring_method reported correctly (no-tags: 'importance', tags: '{method}')")
        return True

    except Exception as e:
        print(f"❌ scoring_method test failed: {e}")
        return False


async def test_workflow_guide_returns_all_best_practices():
    """
    memory_workflow_guide internally calls tinydb_search_memories to fetch
    best_practices memories.  After introducing page_size=5 as a default,
    there was a regression where only the first page was returned even when
    limit=20 was requested.  This test stores 8 best_practices memories and
    verifies the guide returns all of them.
    """
    print("\n=== Testing memory_workflow_guide Does Not Truncate best_practices ===")
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            # Store 8 best_practices memories
            for i in range(8):
                await client.call_tool("tinydb_memorize", {
                    "content": f"Best practice guideline number {i}.",
                    "category": "best_practices",
                    "tags": "best-practices,workflow",
                    "importance": 4,
                })

            result = await client.call_tool("memory_workflow_guide", {})
            data = result.data

        if not isinstance(data, dict):
            print(f"❌ Expected dict, got {type(data)}")
            return False

        if "server_timestamp" not in data:
            print("❌ Missing server_timestamp")
            return False

        stored = data.get("stored_best_practices", {})
        count = stored.get("total_stored_practices", 0)

        if count < 8:
            print(
                f"❌ memory_workflow_guide only returned {count}/8 best_practices — "
                f"page_size truncation bug is present"
            )
            return False

        print(f"✅ memory_workflow_guide returned all {count} best_practices (no truncation)")
        return True

    except Exception as e:
        import traceback
        print(f"❌ workflow_guide regression test failed: {e}")
        traceback.print_exc()
        return False


async def test_tag_scoring_path_via_mcp():
    """
    Exercise the tag-scoring code path (scoring_method='tag_scoring') through
    the MCP protocol.  This requires the tag registry to contain embeddings,
    which in turn requires GOOGLE_API_KEY.

    - If no API key is set: confirms the tool falls back gracefully (no crash,
      valid response, scoring_method is 'string_expansion' or 'exact').
    - If an API key is set: inserts memories, searches with semantic_search=True,
      and verifies scoring_method='tag_scoring' is reported.

    Either outcome is a pass; the test fails only on a crash or missing fields.
    """
    print("\n=== Testing Tag-Scoring Path Through MCP Layer ===")
    import os
    has_api_key = bool(os.getenv("GOOGLE_API_KEY"))

    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            # Insert memories with known tags (registration triggers embedding generation)
            tag = "tag-scoring-mcp-test"
            for i in range(3):
                await client.call_tool("tinydb_memorize", {
                    "content": f"Tag scoring test memory {i} about semantic retrieval.",
                    "tags": tag,
                    "importance": 3,
                })

            # Search with semantic_search=True (the default)
            result = await client.call_tool("tinydb_search_memories", {
                "tags": tag,
                "semantic_search": True,
                "page_size": 10,
            })
            data = result.data

        if not isinstance(data, dict):
            print(f"❌ Expected dict, got {type(data)}")
            return False

        required = ["success", "server_timestamp", "scoring_method", "memories"]
        missing = [k for k in required if k not in data]
        if missing:
            print(f"❌ Missing response keys: {missing}")
            return False

        method = data.get("scoring_method")
        valid_methods = ("tag_scoring", "string_expansion", "exact")
        if method not in valid_methods:
            print(f"❌ Unexpected scoring_method: '{method}'")
            return False

        if has_api_key:
            if method == "tag_scoring":
                print(f"✅ Tag-scoring path active (API key present, method='{method}')")
            else:
                # API key set but embeddings may not have been generated for the new tags yet
                print(
                    f"⚠️  API key present but scoring_method='{method}' — "
                    f"tag embeddings may not yet be populated for new tags.  "
                    f"Response structure is valid."
                )
        else:
            print(
                f"✅ No API key — fell back gracefully to '{method}' "
                f"(tag_scoring requires GOOGLE_API_KEY)"
            )

        return True

    except Exception as e:
        import traceback
        print(f"❌ Tag-scoring MCP path test failed: {e}")
        traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def main():
    """Run all memory retrieval MCP implementation tests."""
    print("🚀 MCP Server Implementation Tests — Memory Retrieval Tools\n")
    print(f"   Using temp data path: {_TMPDIR}\n")

    tests = [
        test_memory_tools_registered,
        test_search_response_structure,
        test_list_response_structure,
        test_next_page_bad_token_returns_error,
        test_scoring_method_reported,
        test_search_pagination_round_trip,
        test_list_pagination_round_trip,
        test_workflow_guide_returns_all_best_practices,
        test_tag_scoring_path_via_mcp,
    ]

    results = []
    for test in tests:
        success = await test()
        results.append(success)
        if not success:
            print(f"\n❌ {test.__name__} failed — stopping.")
            break

    if all(results):
        print("\n🎉 All Memory Retrieval Tool Tests Passed!")
        return True
    else:
        print("\n❌ Memory Retrieval Tool Tests Failed!")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
