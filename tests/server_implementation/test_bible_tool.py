#!/usr/bin/env python3
"""
Server Implementation Tests — bible_lookup tool

Tests the bible_lookup MCP tool via fastmcp.Client.
All tests here avoid network calls: they cover tool registration,
error propagation (bad reference, unsupported version), and response format.

Live verse lookup (which triggers a one-time ESV download) is covered in
tests/server_intelligence/ where network access is permitted.
"""

import asyncio
import os
import sys
from fastmcp import Client

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


async def test_tool_registration():
    """bible_lookup must be registered as an MCP tool."""
    print("=== Testing tool registration ===")
    try:
        from first_mcp import server_impl
        client = Client(server_impl.mcp)
        async with client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]
            if "bible_lookup" not in tool_names:
                print("FAIL: bible_lookup not in tool list")
                return False
            print("OK: bible_lookup is registered")
            return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False


async def test_unsupported_version_returns_error():
    """An unsupported version must return an error dict, not raise an exception."""
    print("\n=== Testing unsupported version handling ===")
    try:
        from first_mcp import server_impl
        client = Client(server_impl.mcp)
        async with client:
            result = await client.call_tool("bible_lookup", {
                "reference": "John 3:16",
                "bible_version": "NIV",
            })
            data = result.data
            if "error" not in data:
                print(f"FAIL: expected error key for unsupported version, got {data}")
                return False
            if "NIV" not in data["error"]:
                print(f"FAIL: error message should mention 'NIV', got: {data['error']}")
                return False
            print("OK: unsupported version returns error dict mentioning the version")
            return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False


async def test_invalid_reference_returns_error():
    """A malformed reference string must return an error dict."""
    print("\n=== Testing invalid reference handling ===")
    try:
        from first_mcp import server_impl
        client = Client(server_impl.mcp)
        async with client:
            result = await client.call_tool("bible_lookup", {
                "reference": "this is not a bible reference",
            })
            data = result.data
            if "error" not in data:
                print(f"FAIL: expected error key for invalid reference, got {data}")
                return False
            print("OK: invalid reference returns error dict")
            return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False


async def test_error_response_includes_timestamp():
    """Even error responses must carry server_timestamp and server_timezone."""
    print("\n=== Testing error response format (timestamps) ===")
    try:
        from first_mcp import server_impl
        client = Client(server_impl.mcp)
        async with client:
            result = await client.call_tool("bible_lookup", {
                "reference": "John 3:16",
                "bible_version": "KJV",   # unsupported — guaranteed error
            })
            data = result.data
            if "error" not in data:
                print(f"FAIL: expected error, got {data}")
                return False
            if "server_timestamp" not in data or "server_timezone" not in data:
                print(f"FAIL: error response missing timestamps: {data}")
                return False
            from datetime import datetime
            datetime.fromisoformat(data["server_timestamp"])
            print("OK: error response includes valid server_timestamp and server_timezone")
            return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False


async def test_success_response_format():
    """
    When the ESV data is already cached, a valid lookup must return the
    expected response structure. Skipped if no cached data is present
    (live download belongs in server_intelligence tier).
    """
    print("\n=== Testing success response format (cached data only) ===")
    import os
    from pathlib import Path
    data_path = os.environ.get('FIRST_MCP_DATA_PATH', '.')
    esv_dir = Path(data_path) / "bible_data" / "ESV" / "mdbible-main"
    if not esv_dir.exists():
        print("SKIP: ESV data not cached locally — run a live lookup first")
        return True  # not a failure

    try:
        from first_mcp import server_impl
        client = Client(server_impl.mcp)
        async with client:
            result = await client.call_tool("bible_lookup", {
                "reference": "John 3:16",
            })
            data = result.data

            required_keys = ["success", "reference", "version", "verse_count",
                             "verses", "server_timestamp", "server_timezone"]
            for key in required_keys:
                if key not in data:
                    print(f"FAIL: missing key '{key}' in success response")
                    return False

            if data["verse_count"] != 1:
                print(f"FAIL: expected 1 verse for John 3:16, got {data['verse_count']}")
                return False

            verse = data["verses"][0]
            if "reference" not in verse or "text" not in verse:
                print(f"FAIL: verse item missing 'reference' or 'text': {verse}")
                return False

            if data["version"] != "ESV":
                print(f"FAIL: version field should be 'ESV', got {data['version']}")
                return False

            from datetime import datetime
            datetime.fromisoformat(data["server_timestamp"])

            print(f"OK: success response structure valid (verse: {verse['text'][:40]}...)")
            return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False


async def main():
    print("Server Implementation Tests — bible_lookup\n")
    tests = [
        test_tool_registration,
        test_unsupported_version_returns_error,
        test_invalid_reference_returns_error,
        test_error_response_includes_timestamp,
        test_success_response_format,
    ]
    results = []
    for test in tests:
        ok = await test()
        results.append(ok)

    if all(results):
        print("\nAll bible_lookup MCP tests passed.")
        return True
    else:
        print("\nbible_lookup MCP tests FAILED.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
