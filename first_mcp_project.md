# First MCP Server Project

A minimal MCP server project for Claude Desktop using Mamba environment management.

## Project Structure

```
C:\Dropbox\CODE2\github-origs\first-mcp\
├── server.py
├── environment.yml
├── requirements.txt
├── claude_desktop_config.json
├── README.md
└── .gitignore
```

## File Contents

### `server.py`

```python
"""
First MCP Server - A minimal example with basic tools
"""

from mcp import FastMCP
from typing import List, Dict, Any
import json
import os
import sys

# Create the MCP server
mcp = FastMCP("First MCP Server")

@mcp.tool()
def hello_world(name: str = "World") -> str:
    """
    A simple greeting tool.
    
    Args:
        name: The name to greet (default: "World")
    
    Returns:
        A friendly greeting message
    """
    return f"Hello, {name}! This is your first MCP server."

@mcp.tool()
def get_system_info() -> Dict[str, Any]:
    """
    Get basic system information.
    
    Returns:
        Dictionary containing system information
    """
    import platform
    
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "current_directory": os.getcwd(),
        "python_executable": sys.executable
    }

@mcp.tool()
def count_words(text: str) -> Dict[str, int]:
    """
    Count words and characters in a text.
    
    Args:
        text: The text to analyze
    
    Returns:
        Dictionary with word count, character count, and line count
    """
    if not text:
        return {"words": 0, "characters": 0, "lines": 0}
    
    words = len(text.split())
    characters = len(text)
    lines = len(text.splitlines())
    
    return {
        "words": words,
        "characters": characters,
        "lines": lines
    }

@mcp.tool()
def list_files(directory: str = ".") -> List[str]:
    """
    List files in a directory.
    
    Args:
        directory: Directory path to list (default: current directory)
    
    Returns:
        List of filenames in the directory
    """
    try:
        if not os.path.exists(directory):
            return [f"Error: Directory '{directory}' does not exist"]
        
        files = []
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isfile(item_path):
                files.append(f"📄 {item}")
            elif os.path.isdir(item_path):
                files.append(f"📁 {item}/")
        
        return sorted(files)
    except Exception as e:
        return [f"Error: {str(e)}"]

def main():
    """Main entry point for the MCP server."""
    print("Starting First MCP Server...", file=sys.stderr)
    print(f"Python executable: {sys.executable}", file=sys.stderr)
    print(f"Current directory: {os.getcwd()}", file=sys.stderr)
    
    # Run the MCP server
    mcp.run()

if __name__ == "__main__":
    main()
```

### `environment.yml`

```yaml
name: fast-mcp
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - pip
  - pip:
    - mcp>=1.0.0
    - fastmcp
```

### `requirements.txt`

```txt
mcp>=1.0.0
fastmcp
```

### `claude_desktop_config.json`

**Location:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "first-mcp": {
      "command": "mamba",
      "args": ["run", "-n", "fast-mcp", "python", "C:\\Dropbox\\CODE2\\github-origs\\first-mcp\\server.py"],
      "env": {
        "PYTHONPATH": "C:\\Dropbox\\CODE2\\github-origs\\first-mcp"
      }
    }
  }
}
```

### `README.md`

```markdown
# First MCP Server

A minimal MCP server example for learning Model Context Protocol with Claude Desktop.

## Features

- **hello_world**: Simple greeting tool
- **get_system_info**: Returns system information
- **count_words**: Analyzes text statistics
- **list_files**: Lists files in a directory

## Setup Instructions

### 1. Create the Mamba Environment

```bash
cd "C:\Dropbox\CODE2\github-origs\first-mcp"
mamba env create -f environment.yml
```

### 2. Activate and Test

```bash
mamba activate fast-mcp
python server.py
```

If working correctly, you should see server startup messages.

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

- "What tools do you have available from my MCP server?"
- "Use the hello_world tool to greet John"
- "Get my system information"
- "Count the words in this paragraph: [your text]"
- "List the files in my project directory"

The server will appear in Claude as "First MCP Server" with 4 available tools.