"""
First MCP Server - A comprehensive MCP server package (v2.0 Development).

This package provides modular MCP servers with extracted core components:
- Core utilities (calculator, calendar, system info)
- Modular memory system (src/first_mcp/memory/) with TinyDB backend
- Workspace file management 
- Weather services integration
- Reusable memory components for other MCP projects

Version 2.0 features:
- Extracted memory system as importable package
- Enhanced backward compatibility
- Improved maintainability and testability
- Pip installable from GitHub

Author: Torbjørn Wikestad <torbjorn.wikestad@gmail.com>
"""

__version__ = "2.0.0.dev1"
__author__ = "Torbjørn Wikestad"
__email__ = "torbjorn.wikestad@gmail.com"

# Version info tuple for programmatic access
VERSION = (2, 0, 0, "dev1")

# Package metadata
PACKAGE_NAME = "first-mcp"
DESCRIPTION = "A comprehensive MCP (Model Context Protocol) server with memory, workspace, weather, and utility tools"
HOMEPAGE = "https://github.com/TobiSan5/first-mcp"