# Data Processing Tests

**Layer:** Data processing layer with general functions  
**Testing Focus:** Core data operations and utilities  
**Test Pattern:** Standard unit tests with test data  

## Purpose

Tests the fundamental data processing functions that form the foundation of the system:

- Database operations (TinyDB interactions)
- File I/O and workspace management  
- Mathematical and time calculations
- Weather data processing
- Data validation and sanitization
- Core utility functions

## Test Requirements

- Use isolated test data (not production data)
- Test pure functions with predictable inputs/outputs
- Focus on edge cases and error handling
- Validate data transformations and calculations
- Test database operations with controlled datasets

## Test Isolation

Tests in this directory should:
- Create temporary test databases
- Use mock data for predictable results
- Clean up after test execution
- Not depend on external services (use mocks)

## Key Components to Test

- `memory/memory_tools.py` - Core memory operations
- `fileio.py` - Workspace file management
- `calculate.py` - Mathematical and time utilities  
- `weather.py` - Weather data processing
- Database utilities and helpers
- Data validation functions

## Test Structure

Tests in this directory should follow the pattern:
```python
import tempfile
from first_mcp.memory.memory_tools import tinydb_memorize

def test_memory_storage_with_test_data():
    # Use temporary test database
    with tempfile.TemporaryDirectory() as temp_dir:
        # Test data processing functions directly
        result = tinydb_memorize("test content", "test,tags")
        # Validate data processing behavior
        assert result["success"] is True
```