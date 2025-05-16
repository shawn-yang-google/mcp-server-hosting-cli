"""
Sample search tool implementation.
"""

from typing import Dict, Any, List
from mcp.server.fastmcp import Context, FastMCP
from duckduckgo_search import DDGS
from mcp_host import app_setup

# Initialize search client
search_client = DDGS()

@app_setup.mcp_app.tool()
def web_search(ctx: Context, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search the web for information.
    
    Args:
        ctx: The MCP context
        query: Search query
        max_results: Maximum number of results to return
        
    Returns:
        List of search results
    """
    results = []
    for r in search_client.text(query, max_results=max_results):
        results.append({
            "title": r["title"],
            "link": r["link"],
            "snippet": r["body"]
        })
    return results

@app_setup.mcp_app.tool()
def news_search(ctx: Context, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search for news articles.
    
    Args:
        ctx: The MCP context
        query: Search query
        max_results: Maximum number of results to return
        
    Returns:
        List of news articles
    """
    results = []
    for r in search_client.news(query, max_results=max_results):
        results.append({
            "title": r["title"],
            "link": r["link"],
            "source": r["source"],
            "date": r["date"],
            "snippet": r["body"]
        })
    return results

@app_setup.mcp_app.tool()
def image_search(ctx: Context, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search for images.
    
    Args:
        ctx: The MCP context
        query: Search query
        max_results: Maximum number of results to return
        
    Returns:
        List of image results
    """
    results = []
    for r in search_client.images(query, max_results=max_results):
        results.append({
            "title": r["title"],
            "image_url": r["image"],
            "source_url": r["link"]
        })
    return results 