# First MCP Server

A comprehensive MCP server for Claude Desktop featuring high-performance TinyDB memory management, workspace file I/O, weather data, and calendar functionality.

## 🚀 Version 2.0 Development: PyPI-Ready Distribution

**Latest Updates**: Enhanced PyPI packaging and modular architecture

- **PyPI Distribution**: Professional package structure with `pyproject.toml` and wheel building
- **Multi-platform CI/CD**: Automated testing on Ubuntu, Windows, and macOS
- **CLI Entry Points**: Standalone tools (`first-mcp-memory`, `first-mcp-workspace`)
- **Modular Installation**: Core package with optional extensions
- **Quality Pipeline**: Automated code formatting, linting, type checking, and security scanning

## 📦 Installation Options

### Option 1: PyPI Distribution (Coming Soon)

```bash
# Core package with memory system
pip install first-mcp

# With optional extensions
pip install first-mcp[workspace]  # + File management
pip install first-mcp[weather]    # + Weather services
pip install first-mcp[all]       # + All extensions
```

### Option 2: GitHub Installation (Current)

```bash
# Install from specific branch (v2.0 features)
pip install git+https://github.com/TobiSan5/first-mcp.git@feature/v2-pypi-packaging

# Install from main branch (stable)
pip install git+https://github.com/TobiSan5/first-mcp.git
```

## 🆕 Memory System Extracted as Core Package

The memory system has been **extracted into a reusable core package**:

- **Modular architecture**: Memory system extracted to `src/first_mcp/memory/` package for better organization
- **Clean separation**: Database connections, memory tools, tag management, and semantic search now in separate modules
- **Backward compatibility**: Main `server.py` automatically imports from memory package with fallback to inline implementation
- **Reusable components**: Memory system can now be imported and used in other projects
- **Package structure**:
  - `memory/database.py`: TinyDB connection management
  - `memory/memory_tools.py`: Core memory operations (memorize, search, update, delete)
  - `memory/tag_tools.py`: Tag management and similarity matching
  - `memory/semantic_search.py`: Semantic search helpers
  - `memory/generic_tools.py`: Generic TinyDB database operations
- **Enhanced maintainability**: Easier to test, modify, and extend individual components
- **Import flexibility**: Graceful fallback ensures compatibility across different deployment scenarios

**Technical achievement**: 2000+ lines of memory functionality cleanly extracted into organized, importable modules while maintaining full backward compatibility.

## Features

### Core Tools
- **hello_world**: Simple greeting tool
- **get_system_info**: Returns system information including configured paths
- **count_words**: Analyzes text statistics
- **now**: Returns current date and time in ISO format with timezone
- **list_files**: Lists files in a directory

### Calculator Tools
- **calculate**: Secure mathematical expression evaluator supporting numbers, +, -, *, /, ^, and parentheses
- **calculate_time_difference**: Calculate time difference between two datetime strings with human-readable output

### Weather Tools
- **get_geocode**: Get coordinates for location names using OpenWeatherMap API
- **get_weather**: Get weather forecast for coordinates using Yr.no API

### Memory Management Tools (TinyDB Backend)
- **tinydb_memorize**: Store information using high-performance TinyDB backend with importance levels and expiration
- **tinydb_recall_memory**: Retrieve specific memorized information by ID from TinyDB
- **tinydb_search_memories**: Search memorized information with semantic tag/category expansion (ENHANCED with automatic similarity matching)
- **tinydb_list_memories**: List all memorized information (sorted by importance) from TinyDB
- **tinydb_update_memory**: Edit existing memorized information in TinyDB
- **tinydb_delete_memory**: Delete memorized information by ID from TinyDB
- **tinydb_memory_stats**: Get statistics about memorized information from TinyDB
- **tinydb_get_memory_categories**: Get available categories for organizing memories from TinyDB
- **tinydb_find_similar_tags**: Find similar existing tags for any concept (PRIMARY TAG SUGGESTION TOOL)
- **tinydb_get_all_tags**: Get all existing tags with usage statistics from TinyDB
- **memory_workflow_guide**: Comprehensive memory management guidance combining stored best practices with step-by-step workflows

### Generic TinyDB Tools
- **tinydb_store_data**: Store data in any TinyDB database with optional ID
- **tinydb_query_data**: Query any TinyDB database with flexible filtering and sorting
- **tinydb_update_data**: Update specific fields in existing records in any TinyDB database
- **tinydb_delete_data**: Delete records from any TinyDB database by ID or conditions
- **tinydb_list_databases**: List all available TinyDB databases with type classification
- **tinydb_get_database_info**: Get detailed information about a specific TinyDB database
- **tinydb_create_database**: Create a new TinyDB database with description

### Workspace File I/O Tools
- **store_workspace_file**: Store text files in configured workspace directory
- **read_workspace_file**: Read text files from workspace with metadata
- **list_workspace_files**: List workspace files with optional tag filtering
- **delete_workspace_file**: Delete files from workspace
- **update_workspace_file_metadata**: Update file descriptions and tags
- **get_workspace_info**: Get workspace statistics and configuration

### Calendar Tools
- **get_calendar**: Get calendar for specified year/month in HTML and text formats
- **get_day_of_week**: Get weekday name for a date in ISO format (YYYY-MM-DD)

## Installation

### Option 1: Direct Installation from GitHub (Recommended)

Install the package directly from GitHub using pip:

```bash
# Install the latest version
pip install git+https://github.com/TobiSan5/first-mcp.git

# Or install a specific version/branch
pip install git+https://github.com/TobiSan5/first-mcp.git@main
```

### Option 2: Clone and Install Locally

```bash
# Clone the repository
git clone https://github.com/TobiSan5/first-mcp.git
cd first-mcp

# Install in development mode
pip install -e .

# Or install normally
pip install .
```

### Environment Setup

After installation, you'll need to configure environment variables and Claude Desktop:

#### 1. Set Environment Variables

Create or update your environment variables:

**On Windows:**
```cmd
# Memory storage location (recommended)
setx FIRST_MCP_DATA_PATH "%APPDATA%\FirstMCP"

# Workspace file storage location
setx FIRST_MCP_WORKSPACE_PATH "%USERPROFILE%\Documents\ClaudeWorkspace"

# API keys (optional - for weather functionality)
setx OPENWEATHERMAPORG_API_KEY "your_openweather_api_key_here"
setx GOOGLE_API_KEY "your_google_ai_api_key_here"
```

**On macOS/Linux:**
```bash
# Add to your ~/.bashrc, ~/.zshrc, or ~/.profile
export FIRST_MCP_DATA_PATH="$HOME/.local/share/FirstMCP"
export FIRST_MCP_WORKSPACE_PATH="$HOME/Documents/ClaudeWorkspace"
export OPENWEATHERMAPORG_API_KEY="your_openweather_api_key_here"
export GOOGLE_API_KEY="your_google_ai_api_key_here"
```

#### 2. Configure Claude Desktop

##### Find Claude Desktop Config Location:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

##### Configure the MCP Server:

1. Copy the example configuration:
   ```bash
   # Navigate to your Claude Desktop config directory
   # Copy the example file from the repository
   cp claude_desktop_config.example.json claude_desktop_config.json
   ```

2. Edit `claude_desktop_config.json` with your paths:
   ```json
   {
     "mcpServers": {
       "first-mcp": {
         "command": "python",
         "args": ["-m", "first_mcp.server"],
         "env": {
           "FIRST_MCP_DATA_PATH": "/path/to/your/data/directory",
           "FIRST_MCP_WORKSPACE_PATH": "/path/to/your/workspace/directory"
         }
       }
     }
   }
   ```

   **Alternative using direct script path:**
   ```json
   {
     "mcpServers": {
       "first-mcp": {
         "command": "python",
         "args": ["/full/path/to/first-mcp/server.py"],
         "env": {
           "FIRST_MCP_DATA_PATH": "/path/to/your/data/directory",
           "FIRST_MCP_WORKSPACE_PATH": "/path/to/your/workspace/directory"
         }
       }
     }
   }
   ```

#### 3. Verify Installation

1. **Test the package import:**
   ```bash
   python -c "import first_mcp; print('First MCP package installed successfully')"
   ```

2. **Test the server:**
   ```bash
   python -m first_mcp.server --debug
   ```

3. **Restart Claude Desktop** completely (quit and relaunch)

4. **Test in Claude Desktop:**
   - Start a new conversation
   - Try: "What memory tools do you have available?"
   - The response should list the TinyDB memory tools

### Troubleshooting

#### Common Issues:

1. **Import Error:** Ensure the package is installed in the correct Python environment that Claude Desktop is using
2. **Permission Error:** Make sure the data and workspace directories exist and are writable
3. **Server Not Found:** Verify the `command` and `args` paths in `claude_desktop_config.json`
4. **Environment Variables:** Restart your shell/IDE after setting environment variables

#### Debug Mode:

Run the server in debug mode to test functionality:
```bash
python server.py --debug
```

This will test all imports, database connections, and core functionality.

## Setup Instructions (Legacy/Development)

### 1. Create the Mamba Environment

```bash
cd "C:\Dropbox\CODE2\github-origs\first-mcp"
mamba env create -f environment.yml
```

### 1.1. Set Environment Variables

#### Required for API functionality:
```bash
# Weather functionality
mamba env config vars set OPENWEATHERMAPORG_API_KEY=your_openweather_api_key_here

# AI tag similarity (optional)
mamba env config vars set GOOGLE_API_KEY=your_google_ai_api_key_here
```

#### Configure data storage paths:
```bash
# Memory storage location (recommended)
mamba env config vars set FIRST_MCP_DATA_PATH=C:\Users\YourName\AppData\Roaming\FirstMCP

# Workspace file storage location (recommended)  
mamba env config vars set FIRST_MCP_WORKSPACE_PATH=C:\Users\YourName\Documents\ClaudeWorkspace
```

**Environment Variable Notes:**
- **API Keys**: Weather and AI tag similarity require API keys
- **FIRST_MCP_DATA_PATH**: Controls where memory files are stored (avoids Claude Desktop app directory)
- **FIRST_MCP_WORKSPACE_PATH**: Controls where workspace files are stored
- **Path Spaces**: If paths contain spaces, consider using `subst` command: `subst W: "C:\Path With Spaces"`
- **Google API Key**: Optional - if not provided, tag similarity search will be disabled but other memory features work normally

**Restart environment after setting variables:**
```bash
mamba deactivate
mamba activate fast-mcp
```

### 2. Activate and Test

```bash
mamba activate fast-mcp

# Test with debug mode first
python server.py --debug

# If debug passes, test normal startup
python server.py
```

If working correctly, you should see server startup messages. Use `--debug` flag to troubleshoot import or initialization issues.

### 3. Configure Claude Desktop

Copy the `claude_desktop_config.json` content to:
```
%APPDATA%\Claude\claude_desktop_config.json
```

### 4. Restart Claude Desktop

Completely quit and restart Claude Desktop app.

### 5. Test in Claude

Start a new conversation and try:
- "Use the hello_world tool to greet me"
- "Get system information"
- "Count words in this text: Hello world this is a test"
- "What time is it now?"
- "Calculate: 2^3 + 5 * (10 - 3)"
- "Calculate time difference between '2025-08-12 10:00:00' and '2025-08-12 17:30:00'"
- "Get coordinates for Oslo, Norway"
- "Get weather for latitude 59.9139 longitude 10.7522"
- "Memorize this important info: Always consider updating README.md upon changes"
- "Store this with tags 'development,documentation': Always update README when adding features"  
- "Search for memories about Norway construction"
- "Update memory [id] with new content"
- "List all my memorized information"
- "What categories can I use for organizing memories?"
- "Show me the memory workflow guide"
- "Use tinydb_find_similar_tags to find tags for 'python web frameworks'"
- "Find tags similar to machine learning using tinydb_find_similar_tags"
- "Show me all existing tags using tinydb_get_all_tags"

### Generic TinyDB Tools
- "Store data in my project database: tinydb_store_data with db_name='my_project'"
- "Query my expenses: tinydb_query_data with db_name='expenses' and query_conditions"
- "List all my databases: tinydb_list_databases"
- "Get info about a specific database: tinydb_get_database_info with db_name"
- "List files in the current directory"

## Troubleshooting

### Check Environment
```bash
mamba activate fast-mcp
python -c "import mcp; print('MCP installed successfully')"
```

### Check Logs
View Claude Desktop logs at:
```
%APPDATA%\Claude\logs\mcp.log
```

### Test Server Manually
```bash
mamba activate fast-mcp
cd "C:\Dropbox\CODE2\github-origs\first-mcp"
python server.py
```

## Testing

### Test Client

The project includes a comprehensive test client (`test_client.py`) that validates TinyDB database functionality using FastMCP client integration:

```bash
# Run the test client
mamba activate fast-mcp
python test_client.py
```

**Test Coverage:**
- Database connection and info retrieval
- Data storage with complex structures
- Query operations with filtering and sorting
- Record updates and modifications
- Table listing and statistics
- Complex data structures with nested objects

**Test Output:**
- ✓ Success indicators for passed tests
- ✗ Error indicators with details for failures
- Database statistics before and after operations
- Comprehensive validation of all TinyDB tools

The test client demonstrates:
- How to use FastMCP Client for server integration
- Proper handling of CallToolResult objects
- Testing patterns for MCP tool validation
- Complex data storage and retrieval workflows

## Development

To add new tools, simply add new functions with the `@mcp.tool()` decorator to `server.py`.

Example:
```python
@mcp.tool()
def my_new_tool(param: str) -> str:
    """
    Description of what this tool does.
    
    Args:
        param: Description of parameter
    
    Returns:
        Description of return value
    """
    return f"Processed: {param}"
```

### `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
*.log

# Claude Desktop (if accidentally copied here)
claude_desktop_config.json
```

## Quick Start Commands

```bash
# 1. Navigate to project directory
cd "C:\Dropbox\CODE2\github-origs\first-mcp"

# 2. Create environment
mamba env create -f environment.yml

# 3. Activate environment
mamba activate fast-mcp

# 4. Test server
python server.py

# 5. Configure Claude Desktop (copy config to %APPDATA%\Claude\)

# 6. Restart Claude Desktop
```

## Example Claude Interactions

Once set up, you can ask Claude:

### Core & System Tools
- "What tools do you have available from my MCP server?"
- "Use the hello_world tool to greet John"
- "Get my system information" (shows configured paths)
- "Count the words in this paragraph: [your text]"
- "What time is it now?"
- "List the files in my project directory"

### Calculator Tools
- "Calculate: 2^10 + 24"
- "What is (15 + 25) / 4 - 3?"
- "Calculate the time difference between '2025-08-12 09:00:00' and '2025-08-12 17:30:00'"
- "How long from '2025-01-01' to '2025-12-31'?"

### Weather Tools
- "Get coordinates for Paris, France"
- "Get weather for latitude 48.8566 longitude 2.3522"

### Memory Tools (TinyDB) - Now with Semantic Search!
- "Use tinydb_memorize to store: [your important note]"
- "Search memories for 'python-dev' or 'web-dev'" (automatic tag expansion finds similar tags)
- "Find memories in 'guidelines' category" (automatically matches 'best_practices' if similar)
- "Show me my memory statistics using tinydb_memory_stats"
- "Show me the comprehensive memory workflow guide" (combines best practices + workflow steps)
- "List my memory categories using tinydb_get_memory_categories"
- "Find tags similar to 'programming' using tinydb_find_similar_tags"

### Workspace File Tools
- "Store this text in a file called 'notes.txt': [your content]"
- "Read the file 'notes.txt' from my workspace"
- "List all files in my workspace"
- "Show me workspace information"

### Calendar Tool
- "Show me the calendar for December 2025"
- "Get the calendar for February 2024"

The server will appear in Claude as "First MCP Server" with 35 available tools including high-performance TinyDB backend for memory management.

### Memory Functionality (TinyDB Backend)

The memorization tools provide comprehensive memory management across sessions using a high-performance TinyDB backend:

**Core Features:**
- **tinydb_memorize**: Store information with tags, categories, importance levels (1-5), and expiration dates
- **tinydb_search_memories**: Find memories by content, tags, or category (sorted by importance) - **NOW WITH SEMANTIC SEARCH**
- **tinydb_list_memories**: View all stored memories (highest importance first)
- **tinydb_recall_memory**: Get a specific memory by ID
- **tinydb_update_memory**: Edit existing memories (content, tags, category, importance, expiration)
- **tinydb_delete_memory**: Remove unwanted memories
- **tinydb_memory_stats**: View statistics including importance distribution and expired memories
- **tinydb_get_memory_categories**: Get available categories for organizing memories
- **tinydb_find_similar_tags**: Find existing tags similar to any concept or topic for optimal tagging (PRIMARY TAG SUGGESTION TOOL)
- **tinydb_get_all_tags**: View all existing tags with usage statistics

### 🎯 Semantic Search Enhancement (NEW!)

**Smart Memory Search**: `tinydb_search_memories` now automatically expands your search terms to find more relevant results:

**Tag Expansion:**
- Search for `"python-dev"` → automatically includes memories tagged with `"python"`, `"development"`, etc.
- Search for `"web-dev"` → finds memories with `"web"`, `"frontend"`, `"javascript"` tags
- Search for `"ml"` → matches `"machine-learning"`, `"ai"`, `"data-science"` tags

**Category Validation:**  
- Search with invalid category → helpful error listing all available categories
- Example: `"invalid_category"` → "Category not found. Available: learnings, facts, projects, best_practices..."

**How it works:**
```bash
# Tag expansion: approximate tags find similar ones
"tags": "python-dev" → Found 3 memories (expanded to include "python", "development")

# Category validation: helpful errors for invalid categories  
"category": "invalid_category" → Error: "Available categories: learnings, facts, projects..."
```

**Transparency**: The search results show what tag expansions occurred, so you understand why certain memories were found.

**Control**: Set `semantic_search=false` to disable tag expansion and use exact matching when needed.

**Suggested Categories:**
- `user_context`: Location, profession, interests, personal details
- `preferences`: How information should be presented, preferred tools
- `projects`: Ongoing work, previous discussions, project details
- `learnings`: Things learned about user's specific situation
- `corrections`: When initial assumptions were wrong
- `facts`: Important factual information to remember
- `reminders`: Things to remember for future interactions
- `best_practices`: Guidelines and procedures to follow

**Advanced Features:**
- **Importance levels** (1-5) for prioritizing critical information
- **Optional expiration dates** for temporary information
- **Automatic filtering** of expired memories
- **High-performance TinyDB storage**: 
  - `tinydb_memories.json` for memories with CachingMiddleware
  - `tinydb_categories.json` for categories with usage tracking  
  - `tinydb_tags.json` for tags with AI embeddings
  - Legacy data preserved in `legacy/` folder after migration
- **AI-powered tag similarity** using Google's text-embedding-004 model (768 dimensions)
- **Semantic tag discovery** to find relevant existing tags for new memories
- **Persistent usage tracking** for categories and tags

**Recommended TinyDB Tag Workflow:**
1. **Before storing**: Call `memory_workflow_guide()` for step-by-step TinyDB guidance
2. **Check existing tags**: Use `tinydb_find_similar_tags()` for each content concept 
3. **Reuse existing tags**: Prefer existing tags to avoid proliferation
4. **Store memory**: Use `tinydb_memorize()` with selected existing tags + any truly new ones
5. **Verify**: Use `tinydb_search_memories()` to confirm the memory is properly tagged and findable

**Tag Format:**
- Tags are provided as comma-separated strings: `"python,programming,web-development"`
- Tags are automatically registered with AI embeddings when first used
- **IMPORTANT**: Always check for existing similar tags first to maintain consistency

**Improved Search:**
- **Word-based search**: Query "Norway construction" finds memories containing both "Norway" AND "construction"
- **Case-insensitive**: Works regardless of capitalization
- **Tag filtering**: Search by specific tags to find related memories
- **Category filtering**: Filter by memory categories for organization

### Workspace File I/O Functionality

The workspace system provides persistent file storage for Claude across sessions:

**Core Features:**
- **store_workspace_file**: Save text files with descriptions and tags
- **read_workspace_file**: Read files with full metadata
- **list_workspace_files**: Browse files with optional tag filtering
- **delete_workspace_file**: Safe file deletion with metadata cleanup
- **update_workspace_file_metadata**: Update descriptions and tags without changing content
- **get_workspace_info**: View workspace statistics and configuration

**File Organization:**
- **Tags**: Organize files with comma-separated tags: `"notes,important,draft"`
- **Descriptions**: Add meaningful descriptions for each file
- **Language/Content Type**: Specify content type using language parameter:
  - **Single language/type**: Use simple identifiers like `python`, `javascript`, `markdown`, `text`, `json`, `yaml`
  - **Multiple languages/types**: Separate with forward slash `/` for compound types:
    - `markdown/norwegian` - Markdown content in Norwegian language
    - `html/css` - HTML with embedded CSS
    - `text/english` - Plain text in English
    - `python/sql` - Python code with SQL queries
    - `json/config` - JSON used for configuration
- **Metadata tracking**: Automatic timestamps, file sizes, usage statistics
- **Tag filtering**: List files by specific tags for easy organization

**Storage Configuration:**
- **Environment variable**: Set `FIRST_MCP_WORKSPACE_PATH` to control storage location
- **Automatic directory creation**: Workspace directory created automatically if needed
- **Metadata file**: `.workspace_metadata.json` tracks all file information
- **Security**: Basic path traversal protection for safe file operations

**Recommended Workspace Structure:**
```
YourWorkspace/
├── .workspace_metadata.json    # Auto-generated metadata
├── notes.txt                   # Personal notes
├── code-snippets.py           # Code examples  
├── meeting-notes.md           # Meeting records
└── project-ideas.txt          # Ideas and concepts
```

### Calendar Functionality

**get_calendar** provides comprehensive calendar information:

**Features:**
- **HTML format**: Structured table format for easy LLM parsing
- **Text format**: Human-readable fallback
- **Rich metadata**: Month names, days count, leap year detection
- **Current date context**: Highlights current month and day
- **Validation**: Input validation for year (positive) and month (1-12)

**HTML Structure Benefits:**
- **LLM-friendly**: Easy to parse `<td>` elements for specific days
- **Semantic markup**: Proper `<th>` headers for weekdays
- **CSS classes**: Days marked with classes like 'mon', 'tue', etc.
- **Structured data**: Table format makes date relationships clear

**Use Cases:**
- Planning and scheduling
- Date calculations and analysis
- Event planning context
- Historical date references

### Calculator Functionality

The MCP server includes two powerful calculator tools for different computational needs:

#### Mathematical Calculator (`calculate`)

**Features:**
- **Secure expression evaluation**: Uses AST parsing to prevent code injection
- **Supported operations**: Addition (+), subtraction (-), multiplication (*), division (/), power (^)
- **Parentheses support**: Full support for complex nested expressions
- **Number support**: Integers and floating-point numbers
- **Input validation**: Strict character filtering and syntax checking
- **Error handling**: Division by zero, overflow, and invalid syntax detection

**Security Features:**
- **Code injection prevention**: Only mathematical operations allowed
- **AST-based parsing**: Safe evaluation without `eval()`
- **Character filtering**: Only numbers, operators, and parentheses permitted
- **Operator validation**: Prevents malicious operator sequences

**Examples:**
- `calculate("2 + 3 * 4")` → `14`
- `calculate("2^3 + 1")` → `9`
- `calculate("(10 + 5) / 3")` → `5.0`
- `calculate("2^(3+1)")` → `16`

#### Timedelta Calculator (`calculate_time_difference`)

**Features:**
- **Flexible datetime parsing**: Supports multiple date/time formats
- **Human-readable output**: Results in days, hours, minutes, and seconds
- **Bidirectional calculation**: Handles positive and negative time differences
- **Format support**: ISO, regional formats (DD/MM/YYYY, MM/DD/YYYY), date-only, and mixed formats

**Supported Formats:**
- **ISO format**: `2025-08-12T14:30:00`, `2025-08-12T14:30:00Z`
- **Standard format**: `2025-08-12 14:30:00`, `2025-08-12 14:30`
- **Date only**: `2025-08-12`
- **Regional formats**: `12/08/2025 14:30`, `08/12/2025`, `12-08-2025`
- **Mixed formats**: Different formats for each datetime input

**Output Format:**
- **Positive difference**: `"5 hours, 30 minutes, and 45 seconds"`
- **Multi-day**: `"3 days, 6 hours, and 30 minutes"`
- **Negative difference**: `"-2 days and 4 hours"`
- **Same time**: `"0 seconds"`

**Detailed Components:**
- Individual days, hours, minutes, seconds values
- Total seconds for precise calculations
- Negative flag for time direction
- Original and parsed datetime strings

**Examples:**
- `calculate_time_difference("2025-08-12 10:00:00", "2025-08-12 15:30:45")`
  → `"5 hours, 30 minutes, and 45 seconds"`
- `calculate_time_difference("2025-08-12", "2025-08-15")`
  → `"3 days"`
- `calculate_time_difference("2025-08-15 14:00", "2025-08-12 10:00")`
  → `"-3 days and 4 hours"`

**Use Cases:**
- **Work time calculation**: Calculate hours worked between clock-in and clock-out
- **Project duration**: Determine time spent on tasks or projects
- **Event planning**: Calculate time until/since events
- **Age calculation**: Determine time elapsed since birth dates
- **Scheduling**: Calculate meeting durations and time gaps