# First MCP Server

A comprehensive MCP server for Claude Desktop and other MCP clients, featuring memory management, workspace file I/O, weather data, and utility tools.

## 🚀 What's New in v1.1.0

**Interface Simplified**: Reduced from 52 to 32 tools (38% fewer options) while preserving all essential functionality. **[Read full release notes](./RELEASE_NOTES_v1.1.0.md)**

**Key improvements:**
- ✅ Streamlined tool set focusing on core functionality  
- ✅ Enhanced architecture with proper delegation patterns
- ✅ Improved testing infrastructure
- ✅ Better developer experience with cleaner codebase

## 🎯 For End Users

### Quick Installation

```bash
# Install directly from GitHub (recommended)
pip install git+https://github.com/TobiSan5/first-mcp.git

# Or clone and install locally
git clone https://github.com/TobiSan5/first-mcp.git && cd first-mcp && pip install -e .
```

### Essential Setup

1. **Set environment variables** (create directories for your data):
   ```bash
   # Windows
   setx FIRST_MCP_DATA_PATH "%APPDATA%\FirstMCP"
   setx FIRST_MCP_WORKSPACE_PATH "%USERPROFILE%\Documents\ClaudeWorkspace"
   
   # macOS/Linux  
   export FIRST_MCP_DATA_PATH="$HOME/.local/share/FirstMCP"
   export FIRST_MCP_WORKSPACE_PATH="$HOME/Documents/ClaudeWorkspace"
   ```

2. **Configure your MCP client** (Claude Desktop example):
   ```json
   {
     "mcpServers": {
       "first-mcp": {
         "command": "first-mcp",
         "env": {
           "FIRST_MCP_DATA_PATH": "/path/to/your/data",
           "FIRST_MCP_WORKSPACE_PATH": "/path/to/your/workspace"
         }
       }
     }
   }
   ```

3. **Restart your MCP client** and start using the tools!

### What You Get

**Core Tools (32 total)**:
- **Memory Management**: Store, search, and organize information across sessions
- **File Workspace**: Persistent file storage with tagging and metadata  
- **Weather Data**: Location lookup and weather forecasts
- **Calculator**: Secure math expressions and time differences
- **Database Operations**: Generic TinyDB database management
- **System Utilities**: File listing, text analysis, calendar, system info

**Try these commands in Claude:**
- "Store this important info: [your note]" 
- "Search my memories for python projects"
- "What tools do you have available?"
- "Get weather for Oslo, Norway" 
- "Calculate: 2^10 + 24"
- "Store this code snippet in a file"

## 🛠️ For Developers and Adapters

### Architecture Overview

The package follows a clean 3-layer architecture:
```
MCP Layer (server_impl.py)
├─ Tool registration and MCP protocol handling  
├─ Server timestamps and error formatting
└─ Parameter validation

Server Logic Layer
├─ Business rules and validation
├─ Response formatting  
└─ Environment configuration

Data Processing Layer (memory/, fileio/, etc.)  
├─ Pure data manipulation functions
├─ Database operations
└─ External API integrations
```

### Key Features for Integration

- **Modular Design**: Memory system extracted as reusable package (`src/first_mcp/memory/`)
- **Clean Imports**: All components available via explicit imports
- **Environment-Based Config**: Uses environment variables for all paths and API keys
- **Comprehensive Testing**: 3-tier test structure (MCP protocol, data layer, intelligence layer)
- **Backward Compatible**: Safe to upgrade from previous versions

### Development Setup

```bash
# Clone and set up development environment
git clone https://github.com/TobiSan5/first-mcp.git
cd first-mcp
pip install -e .

# Run tests
python tests/server_implementation/test_mcp_client.py

# Run in debug mode
python -m first_mcp.server --debug
```

### Adding New Tools

Simply add functions with `@mcp.tool()` decorator to `src/first_mcp/server_impl.py`:

```python
@mcp.tool()
def my_custom_tool(input_text: str) -> Dict[str, Any]:
    """
    Your tool description here.
    
    Args:
        input_text: Description of parameter
        
    Returns:
        Dictionary with results
    """
    result = {"processed": input_text.upper()}
    return add_server_timestamp(result)  # Include server timestamp
```

## 📚 Documentation

- **[Release Notes v1.1.0](./RELEASE_NOTES_v1.1.0.md)** - Interface changes and improvements
- **[Package Documentation](./src/first_mcp/__init__.py)** - Development roadmap and version info  
- **[Memory System](./src/first_mcp/memory/)** - Architecture and implementation details
- **[Testing Guide](./tests/)** - 3-tier test structure and examples

## 🌐 MCP Ecosystem

This server works with any **Model Context Protocol (MCP)** compatible application:
- **Claude Desktop** - Primary target
- **Cursor** - IDE integration  
- **VS Code with MCP extension** - Development environment
- **Any MCP client** - Protocol-compliant applications

## 🔧 Environment Variables (Optional)

```bash
# API Keys (for weather functionality)
export OPENWEATHERMAPORG_API_KEY="your_key_here"  
export GOOGLE_API_KEY="your_key_here"

# Data Storage (defaults to current directory if not set)
export FIRST_MCP_DATA_PATH="/custom/data/path"
export FIRST_MCP_WORKSPACE_PATH="/custom/workspace/path" 
```

## 🐛 Troubleshooting

**Common issues:**
1. **"Tools not found"** → Verify MCP client configuration and restart the client
2. **"Import error"** → Ensure package installed in correct Python environment  
3. **"Permission denied"** → Check that data/workspace directories exist and are writable
4. **"No such file"** → Run `first-mcp --debug` to check setup

**Debug mode:**
```bash
python -m first_mcp.server --debug
```

## 📈 Version History

- **v1.1.0** (2025-09-05): Interface optimization - reduced 52→32 tools, architecture improvements
- **v1.0.0**: Initial release with full feature set

---

**License**: MIT | **Author**: Torbjørn Wikestad | **Repo**: [github.com/TobiSan5/first-mcp](https://github.com/TobiSan5/first-mcp)