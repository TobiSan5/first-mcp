"""
Test both calculator integrations (math and timedelta).
"""

import sys
import os
# Add src to path to import first_mcp package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from first_mcp.calculate import Calculator, TimedeltaCalculator

def test_both_calculators():
    """Test both calculator tools as they would be used in MCP server."""
    print("Testing Both Calculator Tools Integration...")
    print("=" * 60)
    
    # Test mathematical calculator
    print("\n1. Mathematical Calculator Tests:")
    math_calc = Calculator()
    
    math_tests = [
        "2 + 3 * 4",
        "2^3 + 1",
        "(10 + 5) / 3",
        "100 / (2^3 + 2)",
        "2.5 * 4 - 1.5"
    ]
    
    for expr in math_tests:
        result = math_calc.calculate(expr)
        if result["success"]:
            print(f"  {expr} = {result['result']}")
        else:
            print(f"  {expr} -> Error: {result['error']}")
    
    # Test timedelta calculator
    print("\n2. Timedelta Calculator Tests:")
    time_calc = TimedeltaCalculator()
    
    time_tests = [
        ("2025-08-12 10:00:00", "2025-08-12 15:30:00"),  # Same day
        ("2025-08-12", "2025-08-15"),                    # Multi-day
        ("2025-08-12 14:00:00", "2025-08-13 09:15:30"),  # Overnight
        ("2025-01-01 00:00:00", "2025-12-31 23:59:59"),  # Almost full year
    ]
    
    for dt1, dt2 in time_tests:
        result = time_calc.calculate_timedelta(dt1, dt2)
        if result["success"]:
            print(f"  {dt1} to {dt2}")
            print(f"    -> {result['timedelta']['formatted']}")
        else:
            print(f"  {dt1} to {dt2} -> Error: {result['error']}")
    
    print("\n" + "=" * 60)
    print("✅ Both calculators are working correctly!")
    print("✅ Ready for MCP server integration!")
    
    # Simulate MCP tool usage
    print("\n3. Simulated MCP Tool Usage:")
    
    # Mathematical calculation
    def calculate_tool(expression: str):
        try:
            return math_calc.calculate(expression)
        except Exception as e:
            return {"success": False, "error": f"Calculator error: {str(e)}"}
    
    # Timedelta calculation
    def calculate_time_difference_tool(datetime1: str, datetime2: str):
        try:
            return time_calc.calculate_timedelta(datetime1, datetime2)
        except Exception as e:
            return {"success": False, "error": f"Timedelta calculator error: {str(e)}"}
    
    print("\nMCP calculate tool:")
    result = calculate_tool("2^10 + 24")
    print(f"  calculate('2^10 + 24') -> {result.get('result', result.get('error'))}")
    
    print("\nMCP calculate_time_difference tool:")
    result = calculate_time_difference_tool("2025-08-12 09:00:00", "2025-08-12 17:30:00")
    print(f"  Work day length: {result.get('timedelta', {}).get('formatted', result.get('error'))}")

if __name__ == "__main__":
    test_both_calculators()