"""
Test the timedelta calculator functionality.
"""

import sys
import os
# Add src to path to import first_mcp package  
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from first_mcp.calculate import TimedeltaCalculator

def test_timedelta_calculator():
    """Test the timedelta calculator functionality."""
    print("Testing TimedeltaCalculator...")
    
    calc = TimedeltaCalculator()
    
    test_cases = [
        # Same day time difference
        ("2025-08-12 10:00:00", "2025-08-12 15:30:45"),
        
        # Multi-day difference
        ("2025-08-12", "2025-08-15"),
        
        # Negative difference (second date before first)
        ("2025-08-15 14:00:00", "2025-08-12 10:00:00"),
        
        # Different date formats
        ("12/08/2025 10:00", "15/08/2025 16:30"),
        
        # ISO format
        ("2025-08-12T10:00:00", "2025-08-12T15:30:45"),
        
        # Mixed formats
        ("2025-08-12", "15/08/2025 10:30"),
        
        # Minutes and seconds only
        ("2025-08-12 10:00:00", "2025-08-12 10:05:30"),
        
        # Exact same time
        ("2025-08-12 10:00:00", "2025-08-12 10:00:00"),
        
        # Invalid first datetime
        ("invalid-date", "2025-08-12 10:00:00"),
        
        # Invalid second datetime
        ("2025-08-12 10:00:00", "invalid-date"),
        
        # Empty datetime
        ("", "2025-08-12 10:00:00"),
    ]
    
    for i, (dt1, dt2) in enumerate(test_cases, 1):
        print(f"\nTest {i}: '{dt1}' to '{dt2}'")
        result = calc.calculate_timedelta(dt1, dt2)
        
        if result["success"]:
            print(f"  Parsed datetime1: {result['datetime1']['parsed']}")
            print(f"  Parsed datetime2: {result['datetime2']['parsed']}")
            print(f"  Time difference: {result['timedelta']['formatted']}")
            print(f"  Components: {result['timedelta']['days']}d {result['timedelta']['hours']}h {result['timedelta']['minutes']}m {result['timedelta']['seconds']}s")
            print(f"  Total seconds: {result['timedelta']['total_seconds']}")
        else:
            print(f"  Error: {result['error']}")
    
    print("\n" + "="*60)
    print("TimedeltaCalculator testing complete!")

if __name__ == "__main__":
    test_timedelta_calculator()