"""
First MCP Server Test Suite

Three-tier testing architecture:

1. server_implementation/  - MCP server layer tests with fastmcp.Client
2. server_intelligence/    - Smart features tests with production data  
3. data_processing/        - Core operations tests with isolated data

Run individual layers:
- python -m pytest tests/server_implementation/
- python -m pytest tests/server_intelligence/  
- python -m pytest tests/data_processing/

Run all tests:
- python -m pytest tests/
"""