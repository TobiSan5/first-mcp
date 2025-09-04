"""
First MCP Server - A comprehensive MCP server package.

This package provides modular MCP servers for various functionalities:
- Core utilities (calculator, calendar, system info)
- Memory management with TinyDB backend
- Workspace file management 
- Weather services integration

DEVELOPMENT ROADMAP:

v1.0.0 [CURRENT - COMPLETE]
- ✅ Core MCP server implementation with FastMCP
- ✅ Memory system with TinyDB backend
- ✅ Weather tools (OpenWeatherMap + Yr.no)
- ✅ Workspace file I/O management
- ✅ Math and time calculators
- ✅ Auto-initialization system

v1.1.0 [IN PROGRESS - Smart Tag Management]
- ✅ Vector embeddings system (100% coverage - 659/659 tags)
- ✅ Semantic search enhancement
- ✅ Smart tag mapping algorithm (temp_tag_mapper.py)
- 🔄 Integration testing with MCP client
- 🔄 Tag consolidation and proliferation prevention
- 🔄 Transparent server-side intelligence

v2.0.0 [PLANNED - Modular Architecture]
- 📋 Extract memory system as core package
- 📋 Optional extensions: [workspace], [weather], [all]  
- 📋 Simplified memory tools (2-4 tools instead of 15)
- 📋 Safe operations architecture across all modules
- 📋 Package structure: first-mcp (core) + extensions

v2.1.0 [FUTURE - Advanced Memory Features]
- 📋 Hierarchical tagging system
- 📋 Tag governance and approval workflows
- 📋 Advanced semantic grouping
- 📋 Memory relationship mapping
- 📋 Enhanced search and retrieval

DEVELOPMENT PHILOSOPHY:
- Transparent server-side intelligence
- Zero-complexity user experience
- Package-driven architecture
- Comprehensive testing with real data
- Progressive enhancement approach

Author: Torbjørn Wikestad <torbjorn.wikestad@gmail.com>
"""

__version__ = "1.0.0"
__author__ = "Torbjørn Wikestad"
__email__ = "torbjorn.wikestad@gmail.com"

# Version info tuple for programmatic access
VERSION = (1, 0, 0)

# Package metadata
PACKAGE_NAME = "first-mcp"
DESCRIPTION = "A comprehensive MCP (Model Context Protocol) server with memory, workspace, weather, and utility tools"
HOMEPAGE = "https://github.com/TobiSan5/first-mcp"