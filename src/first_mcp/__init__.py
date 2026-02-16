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

v1.1.0 [COMPLETE - Architecture & Interface Optimization]
- ✅ Tool pruning: 52→32 tools (38% reduction for better UX)
- ✅ Architecture delegation pattern: MCP ↔ Server ↔ Data layers
- ✅ 3-tier test structure: server/data/intelligence separation
- ✅ Proper server timestamp delegation across all tools
- ✅ Essential tools preserved: 17 core tools (10 memory + 7 database)
- ✅ Removed experimental tools: governance, aliases, maintenance

v1.1.1 [NOT RELEASED - stashed]
- Configurable tag limits and MemoryConfig class (abandoned before testing)

v1.2.0 [COMPLETE - Text Similarity Tools]
- ✅ New embeddings.py data layer (generate_embedding, cosine_similarity, weighted_combine_embeddings)
- ✅ compute_text_similarity() MCP tool — with optional context and adjustable weights
- ✅ rank_texts_by_similarity() MCP tool
- ✅ tag_tools.py and semantic_search.py refactored to use embeddings.py (no duplication)
- ✅ --version / -V CLI flag
- ✅ Data processing and MCP layer tests for all embedding functions

v2.0.0 [PLANNED - Modular Architecture + Smart Features]
- 📋 Extract memory system as core package
- 📋 Optional extensions: [workspace], [weather], [all]  
- 📋 Ultra-simplified memory tools (2-4 tools total)
- 📋 Smart tag management integration (from v1.1.0 research)
- 📋 Vector embeddings and semantic search enhancement
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

__version__ = "1.2.0"
__author__ = "Torbjørn Wikestad"
__email__ = "torbjorn.wikestad@gmail.com"

# Version info tuple for programmatic access
VERSION = (1, 2, 0)

# Package metadata
PACKAGE_NAME = "first-mcp"
DESCRIPTION = "A comprehensive MCP (Model Context Protocol) server with memory, workspace, weather, and utility tools"
HOMEPAGE = "https://github.com/TobiSan5/first-mcp"