#!/usr/bin/env python3
"""
MCP Server Implementation Tests

Tests the MCP server layer using FastMCP client to validate:
- Tool registration and discovery
- Client-server communication via MCP protocol
- Parameter passing and validation
- Response formatting with server timestamps
- MCP-specific error handling
"""

import asyncio
import os
import sys
from fastmcp import Client

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


async def test_mcp_server_connectivity():
    """Test basic MCP server connectivity and tool discovery."""
    print("=== Testing MCP Server Connectivity ===")
    
    try:
        from first_mcp import server_impl
        client = Client(server_impl.mcp)
        
        async with client:
            print("✅ MCP client connected successfully")
            
            # Test tool discovery (this is MCP-specific)
            tools = await client.list_tools()
            tool_names = [tool.name for tool in tools]
            
            print(f"✅ Discovered {len(tool_names)} MCP tools")
            print(f"   Sample tools: {tool_names[:5]}...")
            
            # Verify essential tools are present
            essential_tools = [
                "tinydb_memorize", 
                "tinydb_search_memories",
                "memory_workflow_guide"
            ]
            
            missing_tools = [tool for tool in essential_tools if tool not in tool_names]
            if missing_tools:
                print(f"❌ Missing essential tools: {missing_tools}")
                return False
                
            print("✅ All essential tools discovered via MCP")
            return True
            
    except Exception as e:
        print(f"❌ MCP connectivity test failed: {e}")
        return False


async def test_mcp_tool_calls():
    """Test actual MCP tool calls with parameter validation."""
    print("\n=== Testing MCP Tool Calls ===")
    
    try:
        from first_mcp import server_impl
        client = Client(server_impl.mcp)
        
        async with client:
            # Test 1: Simple tool call with no parameters
            print("Test 1: Tool call without parameters...")
            result = await client.call_tool("get_system_info")
            data = result.data
            
            if isinstance(data, dict) and "python_version" in data:
                print("✅ Parameter-less tool call successful")
            else:
                print(f"❌ Parameter-less tool call failed: {data}")
                return False
            
            # Test 2: Tool call with parameters
            print("Test 2: Tool call with parameters...")
            result = await client.call_tool("count_words", {"text": "MCP test message"})
            data = result.data
            
            if isinstance(data, dict) and data.get("words") == 3:
                print("✅ Parameterized tool call successful")
            else:
                print(f"❌ Parameterized tool call failed: {data}")
                return False
            
            # Test 3: Complex tool call (memory operations)
            print("Test 3: Complex tool call (memory operations)...")
            result = await client.call_tool("memory_workflow_guide")
            data = result.data
            
            if isinstance(data, dict) and data.get("success"):
                print("✅ Complex tool call successful")
            else:
                print(f"❌ Complex tool call failed: {data}")
                return False
            
            print("✅ All MCP tool calls successful")
            return True
            
    except Exception as e:
        print(f"❌ MCP tool call test failed: {e}")
        return False


async def test_mcp_error_handling():
    """Test MCP-level error handling and validation."""
    print("\n=== Testing MCP Error Handling ===")
    
    try:
        from first_mcp import server_impl
        client = Client(server_impl.mcp)
        
        async with client:
            # Test 1: Invalid tool name
            print("Test 1: Invalid tool name...")
            try:
                await client.call_tool("nonexistent_tool")
                print("❌ Expected error for invalid tool name")
                return False
            except Exception as e:
                print(f"✅ Correctly rejected invalid tool: {type(e).__name__}")
            
            # Test 2: Invalid parameters (expect proper error handling)
            print("Test 2: Invalid parameters...")
            try:
                result = await client.call_tool("tinydb_search_memories", {
                    "limit": "invalid_number"  # Should be int
                })
                print("❌ Expected error for invalid parameters")
                return False
            except Exception as e:
                # This is expected - MCP layer should validate parameters
                if "validation" in str(e).lower() or "type" in str(e).lower():
                    print(f"✅ MCP parameter validation working: {type(e).__name__}")
                else:
                    print(f"❌ Unexpected error type: {e}")
                    return False
            
            print("✅ MCP error handling working correctly")
            return True
            
    except Exception as e:
        print(f"❌ MCP error handling test failed: {e}")
        return False


async def test_mcp_response_format():
    """Test MCP response format consistency."""
    print("\n=== Testing MCP Response Format ===")
    
    try:
        from first_mcp import server_impl
        client = Client(server_impl.mcp)
        
        async with client:
            # Test server timestamp addition (MCP server-specific enhancement)
            print("Testing server timestamp addition...")
            
            tools_to_test = [
                ("get_system_info", {}),
                ("count_words", {"text": "test"}),
                ("memory_workflow_guide", {})
            ]
            
            for tool_name, params in tools_to_test:
                result = await client.call_tool(tool_name, params)
                data = result.data
                
                # Check for server timestamps (added by MCP layer)
                if "server_timestamp" in data and "server_timezone" in data:
                    print(f"✅ {tool_name}: Server timestamps present")
                    
                    # Validate timestamp format
                    from datetime import datetime
                    try:
                        datetime.fromisoformat(data["server_timestamp"])
                        print(f"✅ {tool_name}: Valid timestamp format")
                    except ValueError:
                        print(f"❌ {tool_name}: Invalid timestamp format")
                        return False
                else:
                    print(f"❌ {tool_name}: Missing server timestamps")
                    return False
            
            print("✅ MCP response format validation successful")
            return True
            
    except Exception as e:
        print(f"❌ MCP response format test failed: {e}")
        return False


async def main():
    """Run all MCP server implementation tests."""
    print("🚀 Starting MCP Server Implementation Tests\n")
    
    tests = [
        test_mcp_server_connectivity,
        test_mcp_tool_calls, 
        test_mcp_error_handling,
        test_mcp_response_format
    ]
    
    results = []
    for test in tests:
        success = await test()
        results.append(success)
        if not success:
            print(f"\n❌ Test {test.__name__} failed!")
            break
    
    if all(results):
        print("\n🎉 All MCP Server Implementation Tests Passed!")
        return True
    else:
        print("\n❌ MCP Server Implementation Tests Failed!")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)