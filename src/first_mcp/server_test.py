"""
Incremental test server — lazy-import build-up.

Each batch adds tools with imports inside the function body so
mcp.run() starts immediately and the initialize handshake completes
before any heavy module is loaded.

Entry point: first-mcp-test

Batch 1: utility + math/time tools — stdlib only, no heavy deps.
Batch 2: weather, tool_info, embedding, bible tools — all lazy imports.
"""

import os
import sys
from typing import List, Dict, Any

from fastmcp import FastMCP
from .calculate import Calculator, TimedeltaCalculator

mcp = FastMCP(name="First MCP Test Server")

calculator = Calculator()
timedelta_calculator = TimedeltaCalculator()


def add_server_timestamp(response: Dict[str, Any]) -> Dict[str, Any]:
    import time
    from datetime import datetime
    if not isinstance(response, dict):
        response = {"data": response}
    response["server_timestamp"] = datetime.now().isoformat()
    try:
        response["server_timezone"] = time.tzname[time.daylight]
    except (AttributeError, IndexError):
        response["server_timezone"] = "local"
    return response


# ---------------------------------------------------------------------------
# Utility tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_system_info() -> Dict[str, Any]:
    """Get basic system information including memory storage configuration."""
    import platform
    return add_server_timestamp({
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "current_directory": os.getcwd(),
        "python_executable": sys.executable,
        "memory_storage_path": os.getenv('FIRST_MCP_DATA_PATH', os.getcwd()),
        "memory_storage_configured": os.getenv('FIRST_MCP_DATA_PATH') is not None,
        "workspace_path": os.getenv('FIRST_MCP_WORKSPACE_PATH', os.getcwd()),
        "workspace_configured": os.getenv('FIRST_MCP_WORKSPACE_PATH') is not None,
    })


@mcp.tool()
def count_words(text: str) -> Dict[str, Any]:
    """
    Count words and characters in a text.

    Args:
        text: The text to analyze
    """
    if not text:
        return add_server_timestamp({"words": 0, "characters": 0, "lines": 0})
    return add_server_timestamp({
        "words": len(text.split()),
        "characters": len(text),
        "lines": len(text.splitlines()),
    })


@mcp.tool()
def list_files(directory: str = ".") -> List[str]:
    """
    List files in a directory.

    Args:
        directory: Directory path to list (default: current directory)
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


# ---------------------------------------------------------------------------
# Math / time tools
# ---------------------------------------------------------------------------

@mcp.tool()
def calculate(expression: str) -> Dict[str, Any]:
    """
    Perform secure mathematical calculations.

    Args:
        expression: Mathematical expression (e.g. "2 + 3 * (4 - 1)")
    """
    try:
        return add_server_timestamp(calculator.calculate(expression))
    except Exception as e:
        return add_server_timestamp({"success": False, "error": str(e), "expression": expression})


@mcp.tool()
def calculate_time_difference(datetime1: str, datetime2: str) -> Dict[str, Any]:
    """
    Calculate the time difference between two datetime strings.

    Args:
        datetime1: First datetime string (start time)
        datetime2: Second datetime string (end time)
    """
    try:
        return add_server_timestamp(timedelta_calculator.calculate_timedelta(datetime1, datetime2))
    except Exception as e:
        return add_server_timestamp({"success": False, "error": str(e)})


@mcp.tool()
def get_day_of_week(date_string: str) -> Dict[str, Any]:
    """
    Get the day of the week for a given date.

    Args:
        date_string: Date in YYYY-MM-DD format
    """
    from .calendar_tools import get_day_of_week as _get_day_of_week
    return add_server_timestamp(_get_day_of_week(date_string))


@mcp.tool()
def get_calendar(year: int, month: int) -> Dict[str, Any]:
    """
    Get a calendar for a specific month.

    Args:
        year: Year (e.g. 2025)
        month: Month number (1-12)
    """
    from .calendar_tools import get_calendar as _get_calendar
    return add_server_timestamp(_get_calendar(year, month))


# ---------------------------------------------------------------------------
# Batch 2: weather, tool_info, embedding, bible tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_geocode(location: str, limit: int = 3) -> Dict[str, Any]:
    """
    Get coordinates for a location name using OpenWeatherMap geocoding API.

    Args:
        location: Location name (e.g., "Oslo,,NO", "London,GB", "New York,US")
        limit: Maximum number of results (1-5, default: 3)
    """
    from .weather import GeocodingAPI
    try:
        geocoding = GeocodingAPI()
        results = geocoding.geocode(location, limit)
        if not results:
            return add_server_timestamp({"error": f"No results found for location: {location}"})
        formatted_results = [
            {
                "name": r.get('name'),
                "country": r.get('country'),
                "state": r.get('state'),
                "latitude": r.get('lat'),
                "longitude": r.get('lon'),
                "local_names": r.get('local_names', {}),
            }
            for r in results
        ]
        return add_server_timestamp({
            "query": location,
            "results": formatted_results,
            "count": len(formatted_results),
        })
    except Exception as e:
        return add_server_timestamp({"error": str(e)})


@mcp.tool()
def get_weather(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Get weather forecast for given coordinates using Yr.no (MET Norway) API.

    Args:
        latitude: Latitude coordinate (-90 to 90)
        longitude: Longitude coordinate (-180 to 180)
    """
    from .weather import WeatherAPI
    try:
        weather = WeatherAPI()
        result = weather.get_current_weather(latitude, longitude)
        return add_server_timestamp(result)
    except Exception as e:
        return add_server_timestamp({"error": str(e)})


@mcp.tool()
def tool_info(tool_name: str) -> Dict[str, Any]:
    """
    Return detailed documentation for a named tool.

    Call with tool_name="list" to see which tools have extended documentation.

    Args:
        tool_name: Name of the tool (e.g. "tinydb_search_memories"), or "list".
    """
    docs_dir = os.path.join(os.path.dirname(__file__), 'tool_docs')
    if tool_name == "list":
        try:
            available = sorted(f[:-3] for f in os.listdir(docs_dir) if f.endswith('.md'))
        except Exception:
            available = []
        return add_server_timestamp({"success": True, "available": available})
    path = os.path.join(docs_dir, f"{tool_name}.md")
    if not os.path.exists(path):
        try:
            available = sorted(f[:-3] for f in os.listdir(docs_dir) if f.endswith('.md'))
        except Exception:
            available = []
        return add_server_timestamp({
            "success": False,
            "error": f"No documentation file found for '{tool_name}'.",
            "available": available,
        })
    with open(path, encoding="utf-8") as fh:
        content = fh.read()
    return add_server_timestamp({"success": True, "tool_name": tool_name, "documentation": content})


@mcp.tool()
def compute_text_similarity(
    query: str,
    text: str,
    context: str = "",
    text_weight: float = 0.7,
    context_weight: float = 0.3,
) -> Dict[str, Any]:
    """
    Compute semantic similarity between a query and a text, with optional context weighting.

    Requires GOOGLE_API_KEY environment variable.

    Args:
        query: Reference text or semantic label to compare against
        text: Primary text to evaluate
        context: Optional surrounding context. Ignored if empty.
        text_weight: Weight for the text embedding when context is used. Default: 0.7
        context_weight: Weight for the context embedding. Default: 0.3
    """
    from .embeddings import compute_text_similarity as _compute_text_similarity
    result = _compute_text_similarity(query, text, context, text_weight, context_weight)
    return add_server_timestamp(result)


@mcp.tool()
def rank_texts_by_similarity(query: str, candidates: List[str]) -> Dict[str, Any]:
    """
    Rank a list of texts by semantic similarity to a query text.

    Requires GOOGLE_API_KEY environment variable.

    Args:
        query: Reference text to compare against
        candidates: List of texts to rank
    """
    from .embeddings import rank_texts_by_similarity as _rank_texts_by_similarity
    result = _rank_texts_by_similarity(query, candidates)
    return add_server_timestamp(result)


@mcp.tool()
def bible_lookup(reference: str, bible_version: str = "ESV") -> Dict[str, Any]:
    """
    Look up biblical text by reference.

    Bible text is downloaded automatically from github.com/lguenth/mdbible on first
    use and cached locally. Subsequent calls are served from the local cache.

    Args:
        reference: Biblical reference string. Supports single verse ("Gen 1:1"),
            verse range ("Gen 1:1-10"), chapter ("Gen 1"), chapter range ("Gen 1-4"),
            or multiple references semicolon-separated ("John 3:16; Rom 6:23").
        bible_version: Translation to use. Default "ESV". Currently only "ESV" is supported.
    """
    from .bible import bible_lookup as _bible_lookup
    try:
        verses = _bible_lookup(reference, version=bible_version)
        return add_server_timestamp({
            "success": True,
            "reference": reference,
            "version": bible_version,
            "verse_count": len(verses),
            "verses": [{"reference": ref, "text": text} for ref, text in verses],
        })
    except Exception as e:
        return add_server_timestamp({"error": str(e)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("Starting First MCP Test Server...", file=sys.stderr, flush=True)
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
