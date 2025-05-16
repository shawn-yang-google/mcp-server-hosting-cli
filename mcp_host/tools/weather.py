"""
Sample weather tool implementation.
"""

from typing import Dict, Any
from mcp.server.fastmcp import Context, FastMCP
from mcp_host import app_setup

@app_setup.mcp_app.tool()
def get_weather(ctx: Context, location: str) -> Dict[str, Any]:
    """Get weather information for a location.
    
    Args:
        ctx: The MCP context
        location: The location to get weather for
        
    Returns:
        Dict containing weather information
    """
    # This is a placeholder implementation
    return {
        "location": location,
        "temperature": 72,
        "conditions": "sunny",
        "humidity": 45
    } 