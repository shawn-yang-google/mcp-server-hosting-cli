"""
Sample calendar tool implementation.
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
from mcp.server.fastmcp import Context
from mcp_host import app_setup

# Initialize events storage
events = []

@app_setup.mcp_app.tool()
def create_event(ctx: Context, title: str, start_time: str, duration_minutes: int = 60) -> Dict[str, Any]:
    """Create a new calendar event.
    
    Args:
        ctx: The MCP context
        title: Title of the event
        start_time: Start time in ISO format (YYYY-MM-DD HH:MM)
        duration_minutes: Duration in minutes
        
    Returns:
        Dict containing event details
    """
    start = datetime.fromisoformat(start_time)
    end = start + timedelta(minutes=duration_minutes)
    
    event = {
        "id": len(events) + 1,
        "title": title,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "duration_minutes": duration_minutes
    }
    
    events.append(event)
    return event

@app_setup.mcp_app.tool()
def list_events(ctx: Context, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """List events within a date range.
    
    Args:
        ctx: The MCP context
        start_date: Start date in ISO format (YYYY-MM-DD)
        end_date: End date in ISO format (YYYY-MM-DD)
        
    Returns:
        List of events in the date range
    """
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)
    
    return [
        event for event in events
        if start <= datetime.fromisoformat(event["start_time"]) <= end
    ]

@app_setup.mcp_app.tool()
def delete_event(ctx: Context, event_id: int) -> Dict[str, Any]:
    """Delete a calendar event.
    
    Args:
        ctx: The MCP context
        event_id: ID of the event to delete
        
    Returns:
        Dict containing the deleted event
    """
    for i, event in enumerate(events):
        if event["id"] == event_id:
            return events.pop(i)
    raise ValueError(f"Event with ID {event_id} not found") 