#!/usr/bin/env python3
"""
First MCP Server - Main entry point

Author: Torbjørn Wikestad <torbjorn.wikestad@gmail.com>
"""

def main():
    """Main entry point for the MCP server."""
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-V"):
        from first_mcp import __version__  # noqa: PLC0415 (works when installed or via src layout)
        print(f"first-mcp {__version__}")
        sys.exit(0)
    from first_mcp.server_impl import main as server_main
    server_main()

if __name__ == "__main__":
    main()