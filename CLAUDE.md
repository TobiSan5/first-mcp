# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Model Context Protocol (MCP) server** project built with Python and FastMCP. The server provides basic tools for Claude Desktop integration including greeting, system info, text analysis, and file listing capabilities.

## Development Environment Setup

### Environment Management
- Uses **Mamba/Conda** for Python environment management
- Environment name: `fast-mcp`
- Python version: 3.13

### Common Commands

```bash
# Create environment (first time only)
mamba env create -f environment.yml

# Activate environment
mamba activate fast-mcp

# Run/test the MCP server
python server.py

# Install new dependencies
mamba activate fast-mcp
pip install package_name
# Then update requirements.txt and environment.yml
```

### Testing the Server
- Run `python server.py` to start the server
- Check for startup messages in stderr
- Test individual tools by examining the FastMCP framework behavior

## Architecture

### Core Structure
- **Single-file server**: All MCP tools are defined in `server.py`
- **FastMCP framework**: Uses `@mcp.tool()` decorators to expose functions
- **STDIO transport**: Server communicates via standard input/output

### Key Components
- `FastMCP("First MCP Server")`: Main server instance
- Tool functions: `hello_world`, `get_system_info`, `count_words`, `list_files`
- Each tool has proper type hints and docstrings following Google docstring format

### Adding New Tools
Add functions with the `@mcp.tool()` decorator to `server.py`:

```python
@mcp.tool()
def tool_name(param: str) -> ReturnType:
    """
    Tool description.
    
    Args:
        param: Parameter description
    
    Returns:
        Return value description
    """
    return result
```

## Claude Desktop Integration

### Configuration Location
Claude Desktop config: `%APPDATA%\Claude\claude_desktop_config.json`

### Server Registration
The server is registered as "first-mcp" and runs via:
```json
{
  "mcpServers": {
    "first-mcp": {
      "command": "mamba",
      "args": ["run", "-n", "fast-mcp", "python", "<path>/server.py"]
    }
  }
}
```

### Deployment Steps
1. Update `claude_desktop_config.example.json` with correct paths
2. Copy config to Claude Desktop location
3. Restart Claude Desktop completely
4. Test tools in new Claude conversation

## Dependencies

### Core Dependencies
- **fastmcp**: >=2.11.0 - Core MCP framework
- **tinydb**: >=4.8.0 - High-performance JSON database
- **requests**: >=2.31.0 - HTTP requests for weather APIs
- **google-genai**: >=0.2.0 - AI embeddings for semantic search
- **numpy**: >=1.24.0 - Numerical operations for embeddings

### Development Dependencies
- **pytest**: >=7.0.0 - Testing framework
- **black**: >=23.0.0 - Code formatting
- **ruff**: >=0.1.0 - Fast linting
- **mypy**: >=1.0.0 - Type checking
- **build**: >=0.10.0 - Package building
- **twine**: >=4.0.0 - PyPI uploading

## Development Best Practices

### Code Quality
- **Always run quality tools**: `ruff check`, `black`, `mypy` before commits
- **Test package builds**: `python -m build && pip install dist/*.whl`
- **Update documentation**: README.md, ROADMAP.md after significant changes
- **Use TodoWrite tool**: Plan extensive steps and track progress

### Git Workflow
- **Feature branches**: Work on `feature/v2-*` branches for v2.0 development
- **Manual authentication**: Git push commands require manual GitHub auth
- **Branch protection**: main/develop branches have CI requirements
- **Clean history**: Use meaningful commit messages with co-author attribution

### Testing Patterns
- **FastMCP Client**: Use `test_client.py` pattern for tool testing
- **Memory system**: Test all TinyDB operations for data integrity
- **Package installation**: Verify `pip install -e .` works correctly
- **CLI tools**: Test entry points (`first-mcp-memory`, `first-mcp-workspace`)

### Architecture Guidelines
- **Modular design**: Extract functionality to `src/first_mcp/` packages
- **Backward compatibility**: Maintain graceful fallbacks in `server.py`
- **Environment variables**: Use for configuration (data paths, API keys)
- **CLI entry points**: Add to `pyproject.toml` for new tools

### Memory Guidelines
- **Package-first**: Import from `src.first_mcp.memory` when available
- **TinyDB backend**: Prefer TinyDB tools over legacy implementations
- **Semantic search**: Leverage tag similarity for better search results
- **Tag consistency**: Use `tinydb_find_similar_tags` before creating new tags

### Future Vision
- **PyPI ecosystem**: Professional package distribution and versioning
- **Modular servers**: Specialized MCP servers for different domains
- **Cloud deployment**: Docker support and cloud-native features
- **Community plugins**: Third-party extensions and integrations

## V2.0 Development Context

### Current Branch: `feature/v2-pypi-packaging`
- Enhanced PyPI distribution configuration
- Multi-platform CI/CD testing
- Professional package structure
- CLI entry points for modular tools

### Completed V2.0 Milestones
- ✅ Memory system extraction and modularization
- ✅ PyPI packaging infrastructure
- ✅ GitHub Actions CI/CD pipeline
- ✅ Professional branching strategy
- ✅ Multi-platform build testing

### Next Steps
- Feature branch development (`v2-modular-servers`, `v2-workspace-extension`)
- Integration testing across branches
- Version 2.0 release preparation
- PyPI publication setup

### Development Workflow
1. **Feature development** on dedicated branches
2. **Quality checks** before merging (ruff, black, mypy)
3. **Package testing** with build and installation verification
4. **CI validation** across platforms before merge
5. **Documentation updates** for significant changes