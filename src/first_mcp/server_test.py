"""
Minimal FastMCP test server.

Used for incremental diagnosis: start bare, add features one by one
until Claude Desktop / Claude Code can no longer attach.

Entry point: first-mcp-test
"""

import sys
from typing import Dict, Any
from fastmcp import FastMCP

mcp = FastMCP(name="First MCP Test Server")


@mcp.tool()
def ping() -> Dict[str, Any]:
    """Minimal tool: returns OK."""
    return {"ok": True}


def main():
    print("Starting First MCP Test Server...", file=sys.stderr, flush=True)
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
