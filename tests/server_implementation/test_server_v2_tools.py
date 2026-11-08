#!/usr/bin/env python3
"""
MCP Server Implementation Tests — v2 memory server (first-mcp-memory)

Runs the full v2 tool surface through fastmcp.Client with:
  - a temp FIRST_MCP_DATA_PATH (no production data touched)
  - GOOGLE_API_KEY removed and no FIRST_MCP_TAG_SUGGESTER — proves the server
    works with no LLM at all (local fastembed embeddings only)

Coverage:
  - Tool registration
  - memorize with client tags: success, tags, tag_resolution, server_timestamp
  - semantically close client tag reuses existing tag (house_alarm → home_alarm)
  - search finds tagged memories; unrelated memory not returned first
  - memorize without tags → success with warning
  - update content only keeps tags; update tags only replaces them
  - error paths: update/recall unknown id, update with no fields
"""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

_TMPDIR = tempfile.mkdtemp()
os.environ['FIRST_MCP_DATA_PATH'] = _TMPDIR
os.environ.pop('GOOGLE_API_KEY', None)
os.environ.pop('FIRST_MCP_TAG_SUGGESTER', None)

from fastmcp import Client  # noqa: E402
import first_mcp.server_v2 as server_v2  # noqa: E402

EXPECTED_TOOLS = {
    "first_mcp_memorize", "first_mcp_search", "first_mcp_list",
    "first_mcp_recall", "first_mcp_update", "first_mcp_forget",
}


def check(cond: bool, msg: str) -> bool:
    print(("  ✅ " if cond else "  ❌ ") + msg)
    return cond


async def test_registration(c) -> bool:
    print("\n🧪 Tool registration")
    names = {t.name for t in await c.list_tools()}
    return check(EXPECTED_TOOLS <= names, f"all v2 tools registered ({sorted(EXPECTED_TOOLS - names) or 'ok'})")


async def test_memorize_and_reuse(c, ids: dict) -> bool:
    print("\n🧪 memorize with client tags, no LLM")
    d = (await c.call_tool("first_mcp_memorize", {
        "content": "The burglar alarm at home is serviced by the security company every spring.",
        "tags": ["home_alarm", "Security Company"],
    })).data
    ok = check(d.get("success") is True, "success")
    ok &= check("server_timestamp" in d, "server_timestamp present")
    ok &= check(d.get("tags") == ["home_alarm", "security_company"], f"tags normalised: {d.get('tags')}")
    ok &= check(len(d.get("tag_resolution", [])) == 2, "tag_resolution has an entry per client tag")
    ok &= check("warnings" not in d, "no warnings")
    ids["alarm"] = d.get("memory_id")

    print("\n🧪 close client tag reuses existing tag")
    d = (await c.call_tool("first_mcp_memorize", {
        "content": "Remember to replace the batteries in the house alarm sensors.",
        "tags": "house_alarm",
    })).data
    ok &= check(d.get("tags") == ["home_alarm"], f"house_alarm → home_alarm: {d.get('tags')}")
    res = (d.get("tag_resolution") or [{}])[0]
    ok &= check(res.get("matched_existing") is True and res.get("suggested") == "house_alarm",
                "resolution reports the match")
    ids["battery"] = d.get("memory_id")

    d = (await c.call_tool("first_mcp_memorize", {
        "content": "Tomatoes need staking in June.",
        "tags": ["gardening"],
    })).data
    ok &= check(d.get("tags") == ["gardening"], "unrelated tag kept separate")
    ids["garden"] = d.get("memory_id")
    return ok


async def test_search(c, ids: dict) -> bool:
    print("\n🧪 search without LLM")
    d = (await c.call_tool("first_mcp_search", {"query": "home security alarm"})).data
    found = [m["id"] for m in d.get("memories", [])]
    ok = check(d.get("success") is True and "server_timestamp" in d, "success + timestamp")
    ok &= check({ids["alarm"], ids["battery"]} <= set(found), "both alarm memories found")
    ok &= check(bool(found) and found[0] != ids["garden"], "gardening memory not ranked first")
    return ok


async def test_memorize_without_tags(c, ids: dict) -> bool:
    print("\n🧪 memorize without tags → warning, still stored")
    d = (await c.call_tool("first_mcp_memorize", {"content": "Untagged note xyz."})).data
    ok = check(d.get("success") is True, "success")
    ok &= check(isinstance(d.get("warnings"), list) and len(d["warnings"]) >= 1, "warning returned")
    r = (await c.call_tool("first_mcp_recall", {"memory_id": d.get("memory_id")})).data
    ok &= check(r.get("success") is True, "memory retrievable by id")
    return ok


async def test_update(c, ids: dict) -> bool:
    print("\n🧪 update content only keeps tags")
    d = (await c.call_tool("first_mcp_update", {
        "memory_id": ids["garden"], "content": "Tomatoes need staking in late May.",
    })).data
    ok = check(d.get("success") is True, "success")
    ok &= check("tags" not in d.get("updated_fields", []), "tags not in updated_fields")
    r = (await c.call_tool("first_mcp_recall", {"memory_id": ids["garden"]})).data
    ok &= check(r["memory"]["tags"] == ["gardening"], f"tags kept: {r['memory']['tags']}")

    print("\n🧪 update tags only replaces tags")
    d = (await c.call_tool("first_mcp_update", {
        "memory_id": ids["garden"], "tags": ["vegetable_garden"],
    })).data
    ok &= check(d.get("success") is True and "tags" in d.get("updated_fields", []), "success, tags updated")
    r = (await c.call_tool("first_mcp_recall", {"memory_id": ids["garden"]})).data
    ok &= check("vegetable_garden" in r["memory"]["tags"], f"new tags: {r['memory']['tags']}")
    return ok


async def test_error_paths(c) -> bool:
    print("\n🧪 error paths")
    d = (await c.call_tool("first_mcp_update", {"memory_id": "nope", "content": "x"})).data
    ok = check(d.get("success") is False and "error" in d, "update unknown id → error")
    d = (await c.call_tool("first_mcp_recall", {"memory_id": "nope"})).data
    ok &= check(d.get("success") is False and "error" in d, "recall unknown id → error")
    d = (await c.call_tool("first_mcp_update", {"memory_id": "nope"})).data
    ok &= check(d.get("success") is False and "error" in d, "update with no fields → error")
    return ok


async def main() -> bool:
    print("🚀 v2 memory server MCP tests (no LLM)")
    ids: dict = {}
    async with Client(server_v2.mcp) as c:
        results = [
            await test_registration(c),
            await test_memorize_and_reuse(c, ids),
            await test_search(c, ids),
            await test_memorize_without_tags(c, ids),
            await test_update(c, ids),
            await test_error_paths(c),
        ]
    if all(results):
        print("\n🎉 All v2 server tests passed!")
        return True
    print("\n❌ v2 server tests failed!")
    return False


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(main()) else 1)
