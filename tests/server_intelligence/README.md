# Server-Side Intelligence Tests

**Layer:** Server-side intelligence layer  
**Testing Focus:** Smart features and algorithmic enhancements  
**Test Pattern:** Direct function testing with real production data  

## Purpose

Tests the intelligent features that enhance user experience through server-side processing:

- Smart tag mapping and consolidation
- Semantic search algorithms  
- Auto-initialization and preference detection
- Tag similarity and clustering
- Content analysis and categorization
- Transparent server-side optimizations

## Test Requirements

- Test intelligence algorithms directly (not through MCP layer)
- **Use real production data** via `FIRST_MCP_DATA_PATH` environment variable
- Validate smart mapping accuracy with actual user tags
- Test semantic search relevance with real content
- Verify transparent enhancements work with production patterns
- Measure performance on actual data volumes

## Production Data Access

Tests in this directory can access production data through:
```python
import os
data_path = os.getenv('FIRST_MCP_DATA_PATH', 'default_test_path')
# Access real TinyDB files: memories, tags, categories
```

This enables:
- Testing with real tag proliferation patterns
- Validating semantic search on actual content
- Measuring consolidation effectiveness on real data
- Performance testing with production data volumes

## Key Components to Test

- `tag_mapper.py` - Smart tag mapping algorithms
- Semantic search enhancements in memory tools
- Auto-initialization logic
- Tag consolidation algorithms
- Content-based tag suggestions

## Test Structure

Tests in this directory should follow the pattern:
```python
from first_mcp.memory.tag_mapper import smart_tag_mapping
import os

def test_smart_tag_mapping_with_production_data():
    # Access production data
    data_path = os.getenv('FIRST_MCP_DATA_PATH')
    # Test intelligence algorithms with real data
    result = smart_tag_mapping(['py', 'code'], 'Python function', max_tags=3)
    # Validate intelligent behavior on real patterns
```