#!/usr/bin/env python3
"""
Script to remove the unintended db_ prefixed tools from server.py
"""

import re

def remove_db_tools():
    """Remove the 7 unintended db_ tools from server.py"""
    
    # List of db_ function names to remove
    db_tools = [
        'db_store_data',
        'db_query_data', 
        'db_update_data',
        'db_delete_data',
        'db_list_tables',
        'db_drop_table',
        'db_get_info'
    ]
    
    # Read the server.py file
    with open('/mnt/c/Dropbox/CODE2/github-origs/first-mcp/server.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"Original file size: {len(content)} characters")
    
    # Remove each db_ tool function
    for tool_name in db_tools:
        print(f"Removing {tool_name}...")
        
        # Pattern to match the complete function definition
        # Matches from @mcp.tool() through the entire function
        pattern = rf'@mcp\.tool\(\)\s*\ndef {tool_name}\(.*?\n(?=@mcp\.tool\(\)|def \w+\(|$|\n# =====|\nif __name__|# Create the MCP server)'
        
        # Use DOTALL flag to match newlines in .*?
        matches = list(re.finditer(pattern, content, re.DOTALL))
        
        if matches:
            # Remove the function (take the last match if there are multiple)
            match = matches[-1]
            print(f"  Found {tool_name} at position {match.start()}-{match.end()}")
            
            # Remove the matched text
            content = content[:match.start()] + content[match.end():]
            print(f"  Removed {tool_name}")
        else:
            print(f"  ⚠️  Function {tool_name} not found or already removed")
    
    print(f"Final file size: {len(content)} characters")
    
    # Write the cleaned content back
    with open('/mnt/c/Dropbox/CODE2/github-origs/first-mcp/server.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ db_ tools removal completed!")

if __name__ == '__main__':
    remove_db_tools()