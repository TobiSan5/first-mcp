"""
Incremental test server — lazy-import build-up.

Each batch adds tools with imports inside the function body so
mcp.run() starts immediately and the initialize handshake completes
before any heavy module is loaded.

Entry point: first-mcp-test

Batch 1 (this file): utility + math/time tools — stdlib only, no heavy deps.
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
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("Starting First MCP Test Server...", file=sys.stderr, flush=True)
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
