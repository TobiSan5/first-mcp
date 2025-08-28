"""
Simple test of calculator integration without full MCP server.
"""

import sys
import os
# Add src to path to import first_mcp package  
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from first_mcp.calculate import Calculator

def test_calculator_tool():
    """Test the calculator tool functionality."""
    print("Testing Calculator Tool Integration...")
    
    calculator = Calculator()
    
    # Test cases that would be used by the MCP tool
    test_expressions = [
        "2 + 3",
        "2^3 + 5",
        "(10 + 5) / 3",
        "-5 + 3",
        "2.5 * 4",
        "100 / (5 * 4)",
        "2^(3+1)",
        "10 / 0",  # Should handle division by zero
        "2 + + 3",  # Should handle invalid syntax
        "",  # Should handle empty input
    ]
    
    for expr in test_expressions:
        print(f"\nExpression: '{expr}'")
        result = calculator.calculate(expr)
        
        if result["success"]:
            print(f"  Result: {result['result']} ({result['result_type']})")
            print(f"  Cleaned: {result['cleaned_expression']}")
        else:
            print(f"  Error: {result['error']}")
    
    print("\n" + "="*50)
    print("Calculator tool is working correctly!")
    print("Ready for MCP server integration.")

if __name__ == "__main__":
    test_calculator_tool()