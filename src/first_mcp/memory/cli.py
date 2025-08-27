#!/usr/bin/env python3
"""
CLI entry point for first-mcp memory system.

This provides a standalone command-line interface to the memory system,
allowing users to interact with memory storage without running the full MCP server.
"""

import argparse
import json
import sys
from typing import Dict, Any, List
from .memory_tools import (
    tinydb_memorize, 
    tinydb_search_memories, 
    tinydb_update_memory, 
    tinydb_delete_memory,
    tinydb_get_all_memories,
    tinydb_clear_memories
)


def format_memory(memory: Dict[str, Any]) -> str:
    """Format a memory entry for display."""
    return f"ID: {memory.get('id', 'N/A')} | {memory.get('content', 'No content')[:50]}..."


def cmd_memorize(args) -> None:
    """Store a new memory."""
    try:
        result = tinydb_memorize(args.content, args.category, args.tags)
        if result.get("success"):
            print(f"✅ Memorized: {result.get('memory_id')}")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def cmd_search(args) -> None:
    """Search memories."""
    try:
        result = tinydb_search_memories(args.query, args.category, args.tags, args.limit)
        if result.get("success") and result.get("memories"):
            memories = result["memories"]
            print(f"Found {len(memories)} memories:")
            for memory in memories:
                print(f"  {format_memory(memory)}")
        else:
            print("No memories found matching your query.")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def cmd_list(args) -> None:
    """List all memories."""
    try:
        result = tinydb_get_all_memories()
        if result.get("success") and result.get("memories"):
            memories = result["memories"]
            print(f"Total memories: {len(memories)}")
            for memory in memories:
                print(f"  {format_memory(memory)}")
        else:
            print("No memories stored.")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def cmd_delete(args) -> None:
    """Delete a memory."""
    try:
        result = tinydb_delete_memory(args.memory_id)
        if result.get("success"):
            print(f"✅ Deleted memory: {args.memory_id}")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="First MCP Memory System CLI",
        prog="first-mcp-memory"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Memorize command
    memorize_parser = subparsers.add_parser("memorize", help="Store a new memory")
    memorize_parser.add_argument("content", help="Content to memorize")
    memorize_parser.add_argument("--category", help="Memory category")
    memorize_parser.add_argument("--tags", help="Comma-separated tags")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search memories")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--category", help="Filter by category")
    search_parser.add_argument("--tags", help="Comma-separated tags to filter by")
    search_parser.add_argument("--limit", type=int, default=10, help="Maximum results (default: 10)")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all memories")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a memory")
    delete_parser.add_argument("memory_id", help="ID of memory to delete")
    
    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear all memories")
    clear_parser.add_argument("--confirm", action="store_true", help="Confirm deletion")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Route to appropriate command
    if args.command == "memorize":
        cmd_memorize(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "delete":
        cmd_delete(args)
    elif args.command == "clear":
        if args.confirm:
            try:
                result = tinydb_clear_memories()
                if result.get("success"):
                    print("✅ All memories cleared.")
                else:
                    print(f"❌ Error: {result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"❌ Error: {str(e)}")
        else:
            print("⚠️ Use --confirm to clear all memories")


if __name__ == "__main__":
    main()