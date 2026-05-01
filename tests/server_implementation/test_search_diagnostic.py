#!/usr/bin/env python3
"""
Diagnostic test for tinydb_search_memories disconnect issue.

Exercises every code path in tinydb_search_memories through the MCP protocol
layer (FastMCP Client) to reproduce the Claude Desktop disconnect and pinpoint
the failing path.

Paths covered:
  A. No tags, no content → importance sort (no tag_registry involved)
  B. Tags, semantic_search=False → exact match only
  C. Tags, semantic_search=True, empty tag registry → string expansion fallback
  D. Tags, semantic_search=True, populated registry → tag_scoring path
     (only when GOOGLE_API_KEY is set and tags have embeddings)
  E. Empty result set → has_more=False, no pagination token created
  F. Large result set → has_more=True, save_paginated_results called
"""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

_TMPDIR = tempfile.mkdtemp()
os.environ['FIRST_MCP_DATA_PATH'] = _TMPDIR
os.environ['FIRST_MCP_ENRICHMENT_DISABLED'] = '1'

_HAS_API_KEY = bool(os.getenv('GOOGLE_API_KEY'))

PASS = "✅"
FAIL = "❌"
SKIP = "⏭ "


def _report(label: str, data: dict) -> bool:
    ok = data.get("success") is not False and "error" not in data
    icon = PASS if ok else FAIL
    print(f"{icon} {label}")
    if not ok:
        print(f"   → {data}")
    return ok


async def _memorize(client, content: str, tags: str, importance: int = 3) -> str:
    res = await client.call_tool("tinydb_memorize", {
        "content": content,
        "tags": tags,
        "importance": importance,
    })
    return res.data.get("memory_id", "")


async def run_diagnostics():
    from fastmcp import Client
    from first_mcp import server_impl

    client = Client(server_impl.mcp)
    all_ok = True

    async with client:
        print("=== MCP client connected ===\n")

        # Seed some memories for searching
        print("--- Seeding memories ---")
        await _memorize(client, "Python asyncio event loop and coroutines.", "python,asyncio,concurrency")
        await _memorize(client, "FastAPI REST endpoint design patterns.", "python,web,api")
        await _memorize(client, "Docker container networking basics.", "docker,devops,networking")
        for i in range(6):
            await _memorize(client, f"Pagination test memory {i}.", "pagination-test")
        print(f"{PASS} 9 memories stored\n")

        # ----------------------------------------------------------------
        # Path A: no tags, no keywords → importance sort, no tag_registry
        # ----------------------------------------------------------------
        print("--- Path A: no tags (importance sort) ---")
        res = await client.call_tool("tinydb_search_memories", {
            "tags": "",
            "semantic_search": False,
        })
        all_ok &= _report("no-tag search returns success", res.data)
        all_ok &= _report("has server_timestamp", {"success": "server_timestamp" in res.data})

        # ----------------------------------------------------------------
        # Path B: tags, semantic_search=False → exact match, no API
        # ----------------------------------------------------------------
        print("\n--- Path B: exact tag match (semantic_search=False) ---")
        res = await client.call_tool("tinydb_search_memories", {
            "tags": "python",
            "semantic_search": False,
        })
        all_ok &= _report("exact match returns success", res.data)
        found = res.data.get("total_found", 0)
        all_ok &= _report(f"found ≥ 1 memory (got {found})", {"success": found >= 1})
        all_ok &= _report("scoring_method=exact", {"success": res.data.get("scoring_method") == "exact"})

        # ----------------------------------------------------------------
        # Path C: tags, semantic_search=True, empty registry → fallback
        # ----------------------------------------------------------------
        print("\n--- Path C: semantic=True, empty tag registry (string expansion fallback) ---")
        res = await client.call_tool("tinydb_search_memories", {
            "tags": "python",
            "semantic_search": True,
        })
        all_ok &= _report("semantic search (empty registry) returns success", res.data)
        method = res.data.get("scoring_method", "")
        expected = {"tag_scoring", "string_expansion", "exact", "importance", "none"}
        all_ok &= _report(f"scoring_method present (got '{method}')", {"success": method in expected})

        # ----------------------------------------------------------------
        # Path D: tag_scoring — verify Path C result or run again explicitly
        # ----------------------------------------------------------------
        print("\n--- Path D: tag_scoring with populated registry ---")
        # The memorize calls above register tags with embeddings when
        # GOOGLE_API_KEY is set, so the registry may already be populated.
        path_c_method = res.data.get("scoring_method", "")  # from Path C result
        if path_c_method == "tag_scoring":
            print(f"{PASS} tag_scoring already exercised in Path C")
        else:
            if not _HAS_API_KEY:
                print(f"{SKIP} GOOGLE_API_KEY not set — tag_scoring path skipped")
            else:
                # Re-run with semantic_search=True; registry should be populated by now
                res_d = await client.call_tool("tinydb_search_memories", {
                    "tags": "python",
                    "semantic_search": True,
                })
                all_ok &= _report("tag_scoring path returns success", res_d.data)
                method = res_d.data.get("scoring_method", "")
                all_ok &= _report(f"scoring_method=tag_scoring (got '{method}')",
                                   {"success": method == "tag_scoring"})

        # ----------------------------------------------------------------
        # Path E: content_keywords filter
        # ----------------------------------------------------------------
        print("\n--- Path E: content_keywords filter ---")
        res = await client.call_tool("tinydb_search_memories", {
            "content_keywords": "asyncio",
            "semantic_search": False,
        })
        all_ok &= _report("content_keywords filter returns success", res.data)
        found = res.data.get("total_found", 0)
        all_ok &= _report(f"keyword filter finds asyncio memory (got {found})", {"success": found >= 1})

        # ----------------------------------------------------------------
        # Path F: pagination — 6 pagination-test memories, page_size=3
        # ----------------------------------------------------------------
        print("\n--- Path F: pagination (save_paginated_results called) ---")
        res = await client.call_tool("tinydb_search_memories", {
            "tags": "pagination-test",
            "semantic_search": False,
            "page_size": 3,
        })
        all_ok &= _report("paginated search returns success", res.data)
        all_ok &= _report("has_more=True", {"success": res.data.get("has_more") is True})
        all_ok &= _report("next_page_token present", {"success": bool(res.data.get("next_page_token"))})

        token = res.data.get("next_page_token")
        if token:
            page2 = await client.call_tool("memory_next_page", {"next_page_token": token})
            all_ok &= _report("memory_next_page returns success", page2.data)
            all_ok &= _report("page 2 has memories", {"success": len(page2.data.get("memories", [])) > 0})

        # ----------------------------------------------------------------
        # Path G: invalid category → error response, not crash
        # ----------------------------------------------------------------
        print("\n--- Path G: invalid category (error path) ---")
        res = await client.call_tool("tinydb_search_memories", {
            "category": "nonexistent-category-xyz",
            "semantic_search": False,
        })
        all_ok &= _report("invalid category returns error dict (not exception)", {
            "success": res.data.get("success") is False and "error" in res.data
        })

    print(f"\n{'=' * 40}")
    if all_ok:
        print(f"{PASS} All diagnostic paths passed.")
    else:
        print(f"{FAIL} One or more paths failed — see above.")
    return all_ok


if __name__ == "__main__":
    ok = asyncio.run(run_diagnostics())
    sys.exit(0 if ok else 1)
