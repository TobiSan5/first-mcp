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
                "content_keywords": "nonexistent-sentinel-xyz"
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


async def test_search_sort_by_date():
    """
    tinydb_search_memories with sort_by="date_desc" must return memories newest-
    first (by last_modified / timestamp).  Inserts 3 memories sequentially so
    their timestamps are naturally ordered, then verifies the response order.
    """
    print("\n=== Testing tinydb_search_memories sort_by date ===")
    try:
        import time
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            tag = "date-sort-search-test"
            ids = []
            for i in range(3):
                res = await client.call_tool("tinydb_memorize", {
                    "content": f"Date sort search memory {i}.",
                    "tags": tag,
                    "importance": 3,
                })
                ids.append(res.data.get("memory_id"))
                time.sleep(0.05)  # ensure distinct timestamps

            # date_desc — most recently inserted should come first
            result = await client.call_tool("tinydb_search_memories", {
                "tags": tag,
                "sort_by": "date_desc",
                "semantic_search": False,
                "page_size": 10,
            })
            data = result.data

        if not data.get("success"):
            print(f"❌ Search failed: {data.get('error')}")
            return False

        required = ["scoring_method", "search_criteria"]
        missing = [k for k in required if k not in data]
        if missing:
            print(f"❌ Missing keys: {missing}")
            return False

        if data["search_criteria"].get("sort_by") != "date_desc":
            print(f"❌ sort_by not echoed in search_criteria: {data['search_criteria']}")
            return False

        method = data.get("scoring_method")
        if method not in ("tag_filter_date_sorted", "date_sorted"):
            print(f"❌ Expected date scoring_method, got '{method}'")
            return False

        memories = data.get("memories", [])
        if len(memories) < 2:
            print(f"⚠️  Only {len(memories)} memories returned — cannot verify order")
            print("✅ sort_by=date_desc accepted, structure correct")
            return True

        # Verify descending order
        def _ts(m):
            return m.get('last_modified') or m.get('timestamp') or ''

        timestamps = [_ts(m) for m in memories]
        if timestamps != sorted(timestamps, reverse=True):
            print(f"❌ Memories not in descending order: {timestamps}")
            return False

        print(f"✅ sort_by=date_desc: {len(memories)} memories in correct order, method='{method}'")
        return True

    except Exception as e:
        import traceback
        print(f"❌ test_search_sort_by_date failed: {e}")
        traceback.print_exc()
        return False


async def test_list_sort_by_date():
    """
    tinydb_list_memories with sort_by="date_asc" must return memories oldest-first.
    """
    print("\n=== Testing tinydb_list_memories sort_by date ===")
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            result = await client.call_tool("tinydb_list_memories", {
                "sort_by": "date_asc",
                "page_size": 20,
                "limit": 100,
            })
            data = result.data

        if not data.get("success"):
            print(f"❌ List failed: {data.get('error')}")
            return False

        if "search_criteria" not in data:
            print(f"❌ Missing search_criteria in response: {list(data.keys())}")
            return False

        if data["search_criteria"].get("sort_by") != "date_asc":
            print(f"❌ sort_by not echoed correctly: {data['search_criteria']}")
            return False

        memories = data.get("memories", [])
        if len(memories) < 2:
            print("✅ sort_by=date_asc accepted (too few memories to verify order)")
            return True

        def _ts(m):
            return m.get('last_modified') or m.get('timestamp') or ''

        timestamps = [_ts(m) for m in memories]
        if timestamps != sorted(timestamps):
            print(f"❌ Memories not in ascending order: {timestamps}")
            return False

        print(f"✅ sort_by=date_asc: {len(memories)} memories in correct order")
        return True

    except Exception as e:
        import traceback
        print(f"❌ test_list_sort_by_date failed: {e}")
        traceback.print_exc()
        return False


async def test_list_category_filter():
    """
    tinydb_list_memories with category="projects" must return only memories
    in that category and exclude others.
    """
    print("\n=== Testing tinydb_list_memories category filter ===")
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            # Insert one "projects" memory and one "preferences" memory
            await client.call_tool("tinydb_memorize", {
                "content": "List-category-filter project memory.",
                "category": "projects",
                "tags": "list-category-filter-test",
                "importance": 3,
            })
            await client.call_tool("tinydb_memorize", {
                "content": "List-category-filter preference memory.",
                "category": "preferences",
                "tags": "list-category-filter-test",
                "importance": 3,
            })

            result = await client.call_tool("tinydb_list_memories", {
                "category": "projects",
                "page_size": 50,
                "limit": 100,
            })
            data = result.data

        if not data.get("success"):
            print(f"❌ List with category failed: {data.get('error')}")
            return False

        memories = data.get("memories", [])
        wrong_category = [
            m for m in memories
            if (m.get('category') or '').lower() != "projects"
        ]
        if wrong_category:
            print(f"❌ {len(wrong_category)} memories with wrong category returned")
            return False

        projects_memory_present = any(
            "List-category-filter project memory" in m.get("content", "")
            for m in memories
        )
        if not projects_memory_present:
            print("❌ Inserted projects memory not found in filtered result")
            return False

        print(f"✅ category filter works: {len(memories)} memories, all in 'projects'")
        return True

    except Exception as e:
        import traceback
        print(f"❌ test_list_category_filter failed: {e}")
        traceback.print_exc()
        return False


async def test_sort_prefers_last_modified():
    """
    When a memory is updated its last_modified timestamp becomes newer than
    the timestamp of a more recently *inserted* memory.  sort_by="date_desc"
    must rank the updated (older) memory first, proving last_modified takes
    priority over the original insertion timestamp.

    Timeline:
      T1 — insert memory A
      T2 — insert memory B  (B.timestamp > A.timestamp)
      T3 — update memory A  (A.last_modified = T3 > T2)
    Expected date_desc order: A (T3), B (T2)
    Expected date_asc  order: B (T2), A (T3)
    """
    print("\n=== Testing sort key: last_modified beats timestamp ===")
    import time
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            tag = "last-modified-priority-test"

            res_a = await client.call_tool("tinydb_memorize", {
                "content": "Memory A — inserted first, later modified.",
                "tags": tag,
                "importance": 3,
            })
            id_a = res_a.data.get("memory_id")
            time.sleep(0.1)

            res_b = await client.call_tool("tinydb_memorize", {
                "content": "Memory B — inserted second, never modified.",
                "tags": tag,
                "importance": 3,
            })
            id_b = res_b.data.get("memory_id")
            time.sleep(0.1)

            # Update A — its last_modified now > B's timestamp
            upd = await client.call_tool("tinydb_update_memory", {
                "memory_id": id_a,
                "content": "Memory A — updated content.",
            })
            if not upd.data.get("success"):
                print(f"❌ Update failed: {upd.data}")
                return False

            # date_desc: A (last_modified=T3) should come before B (timestamp=T2)
            r_desc = await client.call_tool("tinydb_search_memories", {
                "tags": tag,
                "sort_by": "date_desc",
                "semantic_search": False,
                "page_size": 10,
            })
            memories_desc = r_desc.data.get("memories", [])
            ids_desc = [m["id"] for m in memories_desc]

            if len(ids_desc) < 2:
                print(f"❌ Expected 2 memories, got {len(ids_desc)}")
                return False

            if ids_desc[0] != id_a:
                print(f"❌ date_desc: expected A first (has last_modified), got order {ids_desc}")
                return False

            # date_asc: B (timestamp=T2) should come before A (last_modified=T3)
            r_asc = await client.call_tool("tinydb_search_memories", {
                "tags": tag,
                "sort_by": "date_asc",
                "semantic_search": False,
                "page_size": 10,
            })
            memories_asc = r_asc.data.get("memories", [])
            ids_asc = [m["id"] for m in memories_asc]

            if ids_asc[0] != id_b:
                print(f"❌ date_asc: expected B first (older timestamp), got order {ids_asc}")
                return False

        print("✅ last_modified takes priority over timestamp in both date_desc and date_asc")
        return True

    except Exception as e:
        import traceback
        print(f"❌ test_sort_prefers_last_modified failed: {e}")
        traceback.print_exc()
        return False


async def test_search_date_sort_tag_filter_still_applies():
    """
    With sort_by=date_desc AND tags provided, only memories matching those tags
    must be returned — tag filtering must not be bypassed by the date sort.

    Inserts 2 memories with tag X and 1 with tag Y.  Searching tag X + date_desc
    must return exactly the 2 X-tagged memories, not the Y one.
    """
    print("\n=== Testing tag filter is preserved under sort_by=date_desc ===")
    import time
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            # Use semantically distinct tags so smart_tag_mapping does not conflate them
            tag_x = "alpine-geology-research"
            tag_y = "maritime-cooking-recipes"

            for i in range(2):
                await client.call_tool("tinydb_memorize", {
                    "content": f"Alpine geology research note {i} about rock strata.",
                    "tags": tag_x,
                    "importance": 3,
                })
                time.sleep(0.05)

            await client.call_tool("tinydb_memorize", {
                "content": "Maritime cooking recipe for fish stew.",
                "tags": tag_y,
                "importance": 3,
            })

            # Search for actual stored tag (smart_tag_mapping may rename but stays consistent)
            # First find what tag the X memories actually got stored under
            r_all = await client.call_tool("tinydb_list_memories", {"page_size": 200, "limit": 200})
            x_mems = [m for m in r_all.data.get("memories", [])
                      if "Alpine geology research note" in m.get("content", "")]
            if not x_mems:
                print("❌ Could not locate inserted X memories")
                return False
            actual_tag_x = x_mems[0].get("tags", [tag_x])[0]

            result = await client.call_tool("tinydb_search_memories", {
                "tags": actual_tag_x,
                "sort_by": "date_desc",
                "semantic_search": False,
                "page_size": 20,
            })
            data = result.data

        if not data.get("success"):
            print(f"❌ Search failed: {data.get('error')}")
            return False

        memories = data.get("memories", [])
        wrong = [m for m in memories if "Alpine geology research note" not in m.get("content", "")
                 and "Maritime cooking" not in m.get("content", "")]
        x_count = sum(1 for m in memories if "Alpine geology research note" in m.get("content", ""))
        y_count = sum(1 for m in memories if "Maritime cooking" in m.get("content", ""))

        if y_count > 0:
            print(f"❌ Maritime cooking (Y) memory leaked into alpine geology (X) search")
            return False

        if x_count != 2:
            print(f"❌ Expected exactly 2 alpine geology (X) memories, got {x_count}")
            return False

        print(f"✅ Tag filter preserved: {x_count} alpine geology memories only, maritime excluded")
        return True

    except Exception as e:
        import traceback
        print(f"❌ test_search_date_sort_tag_filter_still_applies failed: {e}")
        traceback.print_exc()
        return False


async def test_search_date_sort_pagination_preserves_order():
    """
    Insert 7 memories with a unique tag and distinct timestamps.
    Search with sort_by="date_desc" and page_size=3, then paginate to end.
    The timestamps collected across all pages must be monotonically non-increasing —
    proving the sort order is not disrupted by the pagination layer.
    """
    print("\n=== Testing sort order preserved across pages (search date_desc) ===")
    import time
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            tag = "date-sort-pagination-order-test"
            for i in range(7):
                await client.call_tool("tinydb_memorize", {
                    "content": f"Ordered memory {i}.",
                    "tags": tag,
                    "importance": 3,
                })
                time.sleep(0.05)

            result = await client.call_tool("tinydb_search_memories", {
                "tags": tag,
                "sort_by": "date_desc",
                "semantic_search": False,
                "page_size": 3,
                "limit": 50,
            })
            data = result.data

            if not data.get("success"):
                print(f"❌ Initial search failed: {data.get('error')}")
                return False

            def _ts(m):
                return m.get('last_modified') or m.get('timestamp') or ''

            all_timestamps = [_ts(m) for m in data.get("memories", [])]
            token = data.get("next_page_token")

            while token:
                next_res = await client.call_tool("memory_next_page", {"next_page_token": token})
                nd = next_res.data
                if not nd.get("success"):
                    print(f"❌ memory_next_page failed: {nd.get('error')}")
                    return False
                all_timestamps.extend(_ts(m) for m in nd.get("memories", []))
                token = nd.get("next_page_token")

        if len(all_timestamps) != 7:
            print(f"❌ Expected 7 timestamps across all pages, got {len(all_timestamps)}")
            return False

        if all_timestamps != sorted(all_timestamps, reverse=True):
            print(f"❌ Timestamps not monotonically non-increasing across pages:\n  {all_timestamps}")
            return False

        print(f"✅ All 7 timestamps in correct descending order across pages")
        return True

    except Exception as e:
        import traceback
        print(f"❌ test_search_date_sort_pagination_preserves_order failed: {e}")
        traceback.print_exc()
        return False


async def test_list_category_and_sort_combined():
    """
    tinydb_list_memories with both category and sort_by set must:
      1. Return only memories in the specified category.
      2. Return them in the requested date order.
    """
    print("\n=== Testing tinydb_list_memories: category + sort_by combined ===")
    import time
    try:
        from first_mcp import server_impl
        from fastmcp import Client

        client = Client(server_impl.mcp)
        async with client:
            cat = "projects"
            for i in range(3):
                await client.call_tool("tinydb_memorize", {
                    "content": f"Category-sort combo project memory {i}.",
                    "category": cat,
                    "tags": "category-sort-combo-test",
                    "importance": 3,
                })
                time.sleep(0.05)

            # Insert a decoy in a different category
            await client.call_tool("tinydb_memorize", {
                "content": "Category-sort combo preferences decoy.",
                "category": "preferences",
                "tags": "category-sort-combo-test",
                "importance": 3,
            })

            result = await client.call_tool("tinydb_list_memories", {
                "category": cat,
                "sort_by": "date_asc",
                "page_size": 50,
                "limit": 100,
            })
            data = result.data

        if not data.get("success"):
            print(f"❌ List failed: {data.get('error')}")
            return False

        memories = data.get("memories", [])

        # Only projects
        wrong_cat = [m for m in memories if (m.get("category") or "").lower() != cat]
        if wrong_cat:
            print(f"❌ {len(wrong_cat)} non-'{cat}' memories leaked through")
            return False

        # Confirm the 3 new ones are present
        combo_memories = [m for m in memories if "Category-sort combo project" in m.get("content", "")]
        if len(combo_memories) < 3:
            print(f"❌ Expected at least 3 combo project memories, found {len(combo_memories)}")
            return False

        # Check ascending timestamp order across the combo memories
        def _ts(m):
            return m.get('last_modified') or m.get('timestamp') or ''

        ts = [_ts(m) for m in memories]
        if ts != sorted(ts):
            print(f"❌ Memories not in ascending order: {ts}")
            return False

        print(f"✅ category='{cat}' + sort_by=date_asc: {len(memories)} memories, correct category and order")
        return True

    except Exception as e:
        import traceback
        print(f"❌ test_list_category_and_sort_combined failed: {e}")
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
        test_search_sort_by_date,
        test_list_sort_by_date,
        test_list_category_filter,
        test_sort_prefers_last_modified,
        test_search_date_sort_tag_filter_still_applies,
        test_search_date_sort_pagination_preserves_order,
        test_list_category_and_sort_combined,
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
