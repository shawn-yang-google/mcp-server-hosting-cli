"""
Sample calculator tool implementation.
"""

from typing import Dict, Any, List
import math
from mcp.server.fastmcp import Context, FastMCP
from mcp_host import app_setup

@app_setup.mcp_app.tool()
def basic_math(ctx: Context, operation: str, numbers: List[float]) -> Dict[str, Any]:
    """Perform basic mathematical operations.
    
    Args:
        ctx: The MCP context
        operation: One of 'add', 'subtract', 'multiply', 'divide'
        numbers: List of numbers to operate on
        
    Returns:
        Dict containing the result
    """
    if not numbers:
        raise ValueError("At least one number is required")
        
    if operation == "add":
        result = sum(numbers)
    elif operation == "subtract":
        result = numbers[0] - sum(numbers[1:])
    elif operation == "multiply":
        result = math.prod(numbers)
    elif operation == "divide":
        if 0 in numbers[1:]:
            raise ValueError("Division by zero")
        result = numbers[0]
        for n in numbers[1:]:
            result /= n
    else:
        raise ValueError(f"Invalid operation: {operation}")
        
    return {
        "operation": operation,
        "numbers": numbers,
        "result": result
    }

@app_setup.mcp_app.tool()
def advanced_math(ctx: Context, operation: str, number: float) -> Dict[str, Any]:
    """Perform advanced mathematical operations.
    
    Args:
        ctx: The MCP context
        operation: One of 'sqrt', 'sin', 'cos', 'tan', 'log'
        number: Number to operate on
        
    Returns:
        Dict containing the result
    """
    if operation == "sqrt":
        if number < 0:
            raise ValueError("Cannot calculate square root of negative number")
        result = math.sqrt(number)
    elif operation == "sin":
        result = math.sin(math.radians(number))
    elif operation == "cos":
        result = math.cos(math.radians(number))
    elif operation == "tan":
        result = math.tan(math.radians(number))
    elif operation == "log":
        if number <= 0:
            raise ValueError("Cannot calculate logarithm of non-positive number")
        result = math.log(number)
    else:
        raise ValueError(f"Invalid operation: {operation}")
        
    return {
        "operation": operation,
        "number": number,
        "result": result
    }

@app_setup.mcp_app.tool()
def statistics(ctx: Context, numbers: List[float]) -> Dict[str, Any]:
    """Calculate basic statistics.
    
    Args:
        ctx: The MCP context
        numbers: List of numbers
        
    Returns:
        Dict containing statistical results
    """
    if not numbers:
        raise ValueError("At least one number is required")
        
    return {
        "mean": sum(numbers) / len(numbers),
        "median": sorted(numbers)[len(numbers) // 2],
        "min": min(numbers),
        "max": max(numbers),
        "count": len(numbers)
    } 