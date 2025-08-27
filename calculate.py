"""
Mathematical and datetime calculator module for MCP server.

This module provides secure mathematical expression evaluation and datetime
difference calculations with strict input validation to prevent code injection
and limit operations to safe mathematical and temporal functions.
"""

import re
import ast
import operator
from typing import Union, Dict, Any
from datetime import datetime, timedelta


class Calculator:
    """
    Secure calculator for evaluating mathematical expressions.
    
    Supports basic arithmetic operations: +, -, *, /, ^ (power)
    Only allows numbers, parentheses, and these operators.
    """
    
    # Allowed operators mapping
    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,  # Unary minus
        ast.UAdd: operator.pos,  # Unary plus
    }
    
    def __init__(self):
        """Initialize the calculator."""
        # Pattern to validate allowed characters
        self.allowed_pattern = re.compile(r'^[0-9+\-*/^()\s.]+$')
        # Pattern to detect consecutive operators (except for unary cases)
        self.consecutive_ops = re.compile(r'[+\-*/^]{2,}')
        
    def validate_expression(self, expression: str) -> Dict[str, Any]:
        """
        Validate mathematical expression for security and syntax.
        
        Args:
            expression: Mathematical expression string
            
        Returns:
            Dictionary with validation result and any error messages
        """
        if not expression or not expression.strip():
            return {"valid": False, "error": "Expression cannot be empty"}
        
        # Remove whitespace for validation
        clean_expr = expression.replace(" ", "")
        
        # Check for allowed characters only
        if not self.allowed_pattern.match(clean_expr):
            return {"valid": False, "error": "Expression contains invalid characters. Only numbers, +, -, *, /, ^, and parentheses are allowed"}
        
        # Check for consecutive operators BEFORE replacing ^ with **
        # Allow unary operators at start or after opening parenthesis
        temp_expr = clean_expr
        temp_expr = re.sub(r'^\+', '', temp_expr)  # Remove leading +
        temp_expr = re.sub(r'^\-', '', temp_expr)  # Remove leading -
        temp_expr = re.sub(r'\(\+', '(', temp_expr)  # Remove + after (
        temp_expr = re.sub(r'\(\-', '(-', temp_expr)  # Keep - after ( for unary
        
        if self.consecutive_ops.search(temp_expr.replace('(-', '(')):
            return {"valid": False, "error": "Invalid operator sequence"}
        
        # Now replace ^ with ** for Python evaluation (after validation)
        clean_expr = clean_expr.replace("^", "**")
        
        # Check balanced parentheses
        paren_count = 0
        for char in clean_expr:
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
                if paren_count < 0:
                    return {"valid": False, "error": "Unbalanced parentheses"}
        
        if paren_count != 0:
            return {"valid": False, "error": "Unbalanced parentheses"}
        
        # Check for empty parentheses
        if "()" in clean_expr:
            return {"valid": False, "error": "Empty parentheses are not allowed"}
        
        # Try to parse as AST to catch syntax errors
        try:
            parsed = ast.parse(clean_expr, mode='eval')
            # Additional security check - only allow expression nodes we support
            if not self._is_safe_node(parsed.body):
                return {"valid": False, "error": "Expression contains unsupported operations"}
        except SyntaxError as e:
            return {"valid": False, "error": f"Invalid mathematical expression: {str(e)}"}
        except Exception as e:
            return {"valid": False, "error": f"Expression validation failed: {str(e)}"}
        
        return {"valid": True, "cleaned_expression": clean_expr}
    
    def _is_safe_node(self, node) -> bool:
        """
        Recursively check if AST node contains only allowed operations.
        
        Args:
            node: AST node to check
            
        Returns:
            True if node is safe, False otherwise
        """
        if isinstance(node, ast.Constant):
            # Allow only numbers
            return isinstance(node.value, (int, float))
        
        elif isinstance(node, ast.Num):  # Python < 3.8 compatibility
            return isinstance(node.n, (int, float))
        
        elif isinstance(node, ast.BinOp):
            # Binary operations: check operator and both operands
            return (type(node.op) in self.OPERATORS and 
                    self._is_safe_node(node.left) and 
                    self._is_safe_node(node.right))
        
        elif isinstance(node, ast.UnaryOp):
            # Unary operations: check operator and operand
            return (type(node.op) in self.OPERATORS and 
                    self._is_safe_node(node.operand))
        
        else:
            # Any other node type is not allowed
            return False
    
    def _safe_eval(self, node) -> Union[int, float]:
        """
        Safely evaluate AST node using only allowed operations.
        
        Args:
            node: AST node to evaluate
            
        Returns:
            Numerical result
            
        Raises:
            ValueError: For unsupported operations or evaluation errors
        """
        if isinstance(node, ast.Constant):
            return node.value
        
        elif isinstance(node, ast.Num):  # Python < 3.8 compatibility
            return node.n
        
        elif isinstance(node, ast.BinOp):
            left_val = self._safe_eval(node.left)
            right_val = self._safe_eval(node.right)
            op_func = self.OPERATORS[type(node.op)]
            
            # Handle division by zero
            if isinstance(node.op, ast.Div) and right_val == 0:
                raise ValueError("Division by zero")
            
            # Handle negative bases with fractional exponents
            if isinstance(node.op, ast.Pow) and left_val < 0 and isinstance(right_val, float):
                if right_val != int(right_val):
                    raise ValueError("Cannot raise negative number to fractional power")
            
            return op_func(left_val, right_val)
        
        elif isinstance(node, ast.UnaryOp):
            operand_val = self._safe_eval(node.operand)
            op_func = self.OPERATORS[type(node.op)]
            return op_func(operand_val)
        
        else:
            raise ValueError(f"Unsupported node type: {type(node)}")
    
    def calculate(self, expression: str) -> Dict[str, Any]:
        """
        Calculate result of mathematical expression.
        
        Args:
            expression: Mathematical expression string (e.g., "2 + 3 * (4 - 1)")
            
        Returns:
            Dictionary with calculation result or error information
        """
        try:
            # Validate expression
            validation = self.validate_expression(expression)
            if not validation["valid"]:
                return {
                    "success": False,
                    "error": validation["error"],
                    "expression": expression
                }
            
            cleaned_expr = validation["cleaned_expression"]
            
            # Parse expression into AST
            parsed = ast.parse(cleaned_expr, mode='eval')
            
            # Evaluate using safe evaluation
            result = self._safe_eval(parsed.body)
            
            return {
                "success": True,
                "expression": expression,
                "cleaned_expression": cleaned_expr.replace("**", "^"),
                "result": result,
                "result_type": type(result).__name__
            }
            
        except ZeroDivisionError:
            return {
                "success": False,
                "error": "Division by zero",
                "expression": expression
            }
        except OverflowError:
            return {
                "success": False,
                "error": "Result too large to compute",
                "expression": expression
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "expression": expression
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Calculation failed: {str(e)}",
                "expression": expression
            }


class TimedeltaCalculator:
    """
    Calculator for computing time differences between two datetime strings.
    
    Supports various datetime formats and returns results in a human-readable
    format showing days, hours, minutes, and seconds.
    """
    
    def __init__(self):
        """Initialize the timedelta calculator."""
        # Common datetime formats to try
        self.common_formats = [
            "%Y-%m-%d %H:%M:%S",      # 2025-08-12 14:30:00
            "%Y-%m-%d %H:%M",         # 2025-08-12 14:30
            "%Y-%m-%d",               # 2025-08-12
            "%Y-%m-%dT%H:%M:%S",      # 2025-08-12T14:30:00
            "%Y-%m-%dT%H:%M:%SZ",     # 2025-08-12T14:30:00Z
            "%Y-%m-%dT%H:%M:%S.%f",   # 2025-08-12T14:30:00.123456
            "%Y-%m-%dT%H:%M:%S.%fZ",  # 2025-08-12T14:30:00.123456Z
            "%d/%m/%Y %H:%M:%S",      # 12/08/2025 14:30:00
            "%d/%m/%Y %H:%M",         # 12/08/2025 14:30
            "%d/%m/%Y",               # 12/08/2025
            "%m/%d/%Y %H:%M:%S",      # 08/12/2025 14:30:00
            "%m/%d/%Y %H:%M",         # 08/12/2025 14:30
            "%m/%d/%Y",               # 08/12/2025
            "%d-%m-%Y %H:%M:%S",      # 12-08-2025 14:30:00
            "%d-%m-%Y %H:%M",         # 12-08-2025 14:30
            "%d-%m-%Y",               # 12-08-2025
        ]
    
    def _parse_datetime(self, datetime_str: str) -> Dict[str, Any]:
        """
        Parse datetime string using multiple format attempts.
        
        Args:
            datetime_str: String representation of datetime
            
        Returns:
            Dictionary with parsed datetime or error information
        """
        if not datetime_str or not datetime_str.strip():
            return {"success": False, "error": "Datetime string cannot be empty"}
        
        clean_str = datetime_str.strip()
        
        # Try common formats manually
        for fmt in self.common_formats:
            try:
                parsed_dt = datetime.strptime(clean_str, fmt)
                return {
                    "success": True,
                    "datetime": parsed_dt,
                    "original": datetime_str,
                    "parsed_as": fmt
                }
            except ValueError:
                continue
        
        return {
            "success": False,
            "error": f"Unable to parse datetime '{datetime_str}'. Supported formats include: YYYY-MM-DD HH:MM:SS, YYYY-MM-DD, DD/MM/YYYY HH:MM:SS, MM/DD/YYYY HH:MM:SS, ISO format, etc.",
            "original": datetime_str
        }
    
    def _format_timedelta(self, td: timedelta) -> Dict[str, Any]:
        """
        Format timedelta into human-readable components.
        
        Args:
            td: timedelta object
            
        Returns:
            Dictionary with formatted time components
        """
        total_seconds = int(abs(td.total_seconds()))
        is_negative = td.total_seconds() < 0
        
        # Calculate components
        days = total_seconds // 86400  # 24 * 60 * 60
        remaining = total_seconds % 86400
        
        hours = remaining // 3600  # 60 * 60
        remaining = remaining % 3600
        
        minutes = remaining // 60
        seconds = remaining % 60
        
        # Create formatted strings
        components = []
        if days > 0:
            components.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            components.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            components.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds > 0:
            components.append(f"{seconds} second{'s' if seconds != 1 else ''}")
        
        if not components:
            formatted = "0 seconds"
        elif len(components) == 1:
            formatted = components[0]
        elif len(components) == 2:
            formatted = f"{components[0]} and {components[1]}"
        else:
            formatted = f"{', '.join(components[:-1])}, and {components[-1]}"
        
        if is_negative:
            formatted = f"-{formatted}"
        
        return {
            "days": days if not is_negative else -days,
            "hours": hours if not is_negative else -hours,
            "minutes": minutes if not is_negative else -minutes,
            "seconds": seconds if not is_negative else -seconds,
            "total_seconds": td.total_seconds(),
            "formatted": formatted,
            "is_negative": is_negative
        }
    
    def calculate_timedelta(self, datetime1: str, datetime2: str) -> Dict[str, Any]:
        """
        Calculate time difference between two datetime strings.
        
        Args:
            datetime1: First datetime string
            datetime2: Second datetime string
            
        Returns:
            Dictionary with timedelta calculation result
            
        Note:
            Result is datetime2 - datetime1, so:
            - Positive result means datetime2 is after datetime1
            - Negative result means datetime2 is before datetime1
        """
        try:
            # Parse first datetime
            parsed1 = self._parse_datetime(datetime1)
            if not parsed1["success"]:
                return {
                    "success": False,
                    "error": f"Failed to parse first datetime: {parsed1['error']}",
                    "datetime1": datetime1,
                    "datetime2": datetime2
                }
            
            # Parse second datetime
            parsed2 = self._parse_datetime(datetime2)
            if not parsed2["success"]:
                return {
                    "success": False,
                    "error": f"Failed to parse second datetime: {parsed2['error']}",
                    "datetime1": datetime1,
                    "datetime2": datetime2
                }
            
            # Calculate timedelta (datetime2 - datetime1)
            dt1 = parsed1["datetime"]
            dt2 = parsed2["datetime"]
            td = dt2 - dt1
            
            # Format the result
            formatted = self._format_timedelta(td)
            
            return {
                "success": True,
                "datetime1": {
                    "original": datetime1,
                    "parsed": dt1.isoformat(),
                    "format_used": parsed1["parsed_as"]
                },
                "datetime2": {
                    "original": datetime2,
                    "parsed": dt2.isoformat(),
                    "format_used": parsed2["parsed_as"]
                },
                "timedelta": formatted,
                "calculation_note": "Result is datetime2 - datetime1"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Timedelta calculation failed: {str(e)}",
                "datetime1": datetime1,
                "datetime2": datetime2
            }


def test_calculator():
    """Test the calculator functionality."""
    print("Testing Calculator...")
    
    calc = Calculator()
    
    test_cases = [
        "2 + 3",
        "10 - 4 * 2",
        "2^3",
        "(5 + 3) * 2",
        "100 / (5 * 4)",
        "-5 + 3",
        "2.5 * 4",
        "10 / 0",  # Should fail
        "2 + + 3",  # Should fail
        "eval('2+3')",  # Should fail
        "import os",  # Should fail
        "",  # Should fail
    ]
    
    for expr in test_cases:
        result = calc.calculate(expr)
        print(f"'{expr}' -> {result}")


if __name__ == "__main__":
    test_calculator()