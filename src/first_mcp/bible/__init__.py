"""
Bible lookup module for first-mcp.

Provides biblical text lookup by reference string.
Bible text (ESV) is downloaded automatically from github.com/lguenth/mdbible
on first use and cached locally under $FIRST_MCP_DATA_PATH/bible_data/ESV/.

Public API:
    bible_lookup(reference, version="ESV") -> List[Tuple[str, str]]
    parse_reference(reference) -> BibleReference
"""

from .lookup import bible_lookup, parse_reference, BibleReference

__all__ = ["bible_lookup", "parse_reference", "BibleReference"]
