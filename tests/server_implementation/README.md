# Server Implementation Tests

**Layer:** MCP server based on FastMCP library  
**Testing Focus:** MCP tool integration and client communication  
**Test Pattern:** Uses `fastmcp.Client` instance  

## Purpose

Tests the MCP server layer that exposes tools via FastMCP framework. This layer handles:

- MCP tool registration and discovery
- Client-server communication 
- Tool parameter validation
- Response formatting with server timestamps
- Error handling and status codes

## Test Requirements

- Must use `fastmcp.Client` for authentic MCP protocol testing
- Should test actual tool calls through MCP layer
- Focus on integration between FastMCP and underlying modules
- Validate MCP-specific features (tool discovery, parameter passing, response format)

## Test Structure

Tests in this directory should follow the pattern:
```python
from fastmcp import FastMCP
from fastmcp.testing import Client

def test_mcp_tool_integration():
    # Test actual MCP tool calls
    client = Client(server_instance)
    result = client.call_tool("tool_name", param1="value")
    # Validate MCP response format
```