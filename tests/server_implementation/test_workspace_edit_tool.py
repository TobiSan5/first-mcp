#!/usr/bin/env python3
"""
Server Implementation Tests — workspace_edit_textfile tool

Tests the workspace_edit_textfile MCP tool via fastmcp.Client.
Validates tool registration, parameter passing, response format,
timestamps, and error propagation through the MCP layer.
"""

import asyncio
import os
import sys
import tempfile
import shutil
from fastmcp import Client

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


def _setup_env():
    test_dir = tempfile.mkdtemp()
    original = os.environ.get('FIRST_MCP_WORKSPACE_PATH')
    os.environ['FIRST_MCP_WORKSPACE_PATH'] = test_dir
    return test_dir, original


def _teardown_env(test_dir, original):
    if original is not None:
        os.environ['FIRST_MCP_WORKSPACE_PATH'] = original
    else:
        os.environ.pop('FIRST_MCP_WORKSPACE_PATH', None)
    shutil.rmtree(test_dir, ignore_errors=True)


async def test_tool_registration():
    """workspace_edit_textfile must be registered as an MCP tool."""
    print("=== Testing tool registration ===")
    try:
        from first_mcp import server_impl
        client = Client(server_impl.mcp)
        async with client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]
            if "workspace_edit_textfile" not in tool_names:
                print("FAIL: workspace_edit_textfile not in tool list")
                return False
            print("OK: workspace_edit_textfile is registered")
            return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False


async def test_all_modes_via_mcp():
    """All six edit modes must succeed through the MCP layer."""
    print("\n=== Testing all modes via MCP ===")
    test_dir, original = _setup_env()
    try:
        from first_mcp import server_impl
        # Re-init workspace manager so it picks up the new env var
        server_impl.workspace_manager.__init__()

        client = Client(server_impl.mcp)
        async with client:
            # Seed a file via the store tool
            await client.call_tool("store_workspace_file", {
                "filename": "edit_test.txt",
                "content": "line one\nline two\nline three\n",
                "overwrite": True,
            })

            cases = [
                ("append",        {"content": "line four\n"}),
                ("prepend",       {"content": "line zero\n"}),
                ("insert_after",  {"content": " (A)", "anchor": "line one"}),
                ("insert_before", {"content": "(B) ", "anchor": "line two"}),
                ("replace",       {"content": "LINE TWO", "anchor": "line two"}),
            ]

            for mode, extra_params in cases:
                params = {"filename": "edit_test.txt", "mode": mode, **extra_params}
                result = await client.call_tool("workspace_edit_textfile", params)
                data = result.data
                if not data.get("success"):
                    print(f"FAIL [{mode}]: {data}")
                    return False
                print(f"OK   [{mode}]")

            # replace_all separately (verify replacement count propagates)
            await client.call_tool("store_workspace_file", {
                "filename": "dup.txt",
                "content": "x x x",
                "overwrite": True,
            })
            result = await client.call_tool("workspace_edit_textfile", {
                "filename": "dup.txt",
                "mode": "replace_all",
                "content": "y",
                "anchor": "x",
            })
            data = result.data
            if not data.get("success") or data.get("replacements") != 3:
                print(f"FAIL [replace_all]: {data}")
                return False
            print("OK   [replace_all] (replacements=3)")

        return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False
    finally:
        _teardown_env(test_dir, original)


async def test_error_responses():
    """Errors must return {'error': ...} dicts, not exceptions, through the MCP layer."""
    print("\n=== Testing error responses via MCP ===")
    test_dir, original = _setup_env()
    try:
        from first_mcp import server_impl
        server_impl.workspace_manager.__init__()

        client = Client(server_impl.mcp)
        async with client:
            # File not found
            result = await client.call_tool("workspace_edit_textfile", {
                "filename": "ghost.txt",
                "mode": "append",
                "content": "x",
            })
            data = result.data
            if "error" not in data:
                print(f"FAIL [file not found]: expected error key, got {data}")
                return False
            print("OK   [file not found returns error dict]")

            # Seed a file for anchor-missing tests
            await client.call_tool("store_workspace_file", {
                "filename": "err_test.txt",
                "content": "hello world",
                "overwrite": True,
            })

            # Anchor not found
            result = await client.call_tool("workspace_edit_textfile", {
                "filename": "err_test.txt",
                "mode": "replace",
                "content": "x",
                "anchor": "ZZZMISSING",
            })
            data = result.data
            if "error" not in data:
                print(f"FAIL [anchor not found]: expected error key, got {data}")
                return False
            print("OK   [anchor not found returns error dict]")

            # Missing anchor param
            result = await client.call_tool("workspace_edit_textfile", {
                "filename": "err_test.txt",
                "mode": "insert_after",
                "content": "x",
            })
            data = result.data
            if "error" not in data:
                print(f"FAIL [missing anchor param]: expected error key, got {data}")
                return False
            print("OK   [missing anchor param returns error dict]")

            # Invalid mode
            result = await client.call_tool("workspace_edit_textfile", {
                "filename": "err_test.txt",
                "mode": "nuke",
                "content": "x",
            })
            data = result.data
            if "error" not in data:
                print(f"FAIL [invalid mode]: expected error key, got {data}")
                return False
            print("OK   [invalid mode returns error dict]")

        return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False
    finally:
        _teardown_env(test_dir, original)


async def test_response_format():
    """Successful responses must include server_timestamp and core result fields."""
    print("\n=== Testing response format ===")
    test_dir, original = _setup_env()
    try:
        from first_mcp import server_impl
        server_impl.workspace_manager.__init__()

        client = Client(server_impl.mcp)
        async with client:
            await client.call_tool("store_workspace_file", {
                "filename": "fmt_test.txt",
                "content": "some content",
                "overwrite": True,
            })
            result = await client.call_tool("workspace_edit_textfile", {
                "filename": "fmt_test.txt",
                "mode": "append",
                "content": " more",
            })
            data = result.data

            required = ["success", "filename", "mode", "size_bytes",
                        "server_timestamp", "server_timezone"]
            for key in required:
                if key not in data:
                    print(f"FAIL: missing key '{key}' in response")
                    return False

            from datetime import datetime
            datetime.fromisoformat(data["server_timestamp"])
            print("OK   [response contains all required fields and valid timestamp]")
        return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False
    finally:
        _teardown_env(test_dir, original)


async def main():
    print("Server Implementation Tests — workspace_edit_textfile\n")
    tests = [
        test_tool_registration,
        test_all_modes_via_mcp,
        test_error_responses,
        test_response_format,
    ]
    results = []
    for test in tests:
        ok = await test()
        results.append(ok)
        if not ok:
            break

    if all(results):
        print("\nAll workspace_edit_textfile MCP tests passed.")
        return True
    else:
        print("\nworkspace_edit_textfile MCP tests FAILED.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
