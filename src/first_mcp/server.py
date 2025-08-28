#!/usr/bin/env python3
"""
First MCP Server - Main entry point

Author: Torbjørn Wikestad <torbjorn.wikestad@gmail.com>
"""

def main():
    """Main entry point for the MCP server."""
    from first_mcp.server_impl import main as server_main
    server_main()

if __name__ == "__main__":
    main()