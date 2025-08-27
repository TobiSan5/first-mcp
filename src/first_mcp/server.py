#!/usr/bin/env python3
"""
First MCP Server - Legacy monolithic server (v1.0 compatibility)

This is the original server.py maintained for backward compatibility.
For modular architecture, see individual server modules.

Author: Torbjørn Wikestad <torbjorn.wikestad@gmail.com>
"""

# Re-export the main function from the legacy server
import sys
import os

# Add the project root to Python path to find the legacy server
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

try:
    from server import main as legacy_main
    
    def main():
        """Entry point for legacy server compatibility."""
        print("Starting First MCP Server (Legacy v1.0 compatibility mode)...", file=sys.stderr)
        print("Note: Consider using modular servers: first-mcp-memory, first-mcp-workspace, etc.", file=sys.stderr)
        legacy_main()
        
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"Error: Could not import legacy server: {e}", file=sys.stderr)
    print("Make sure you're running from the project root directory.", file=sys.stderr)
    sys.exit(1)