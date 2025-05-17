# Generated MCP server for {{SERVER_NAME}}

from mcp.server.fastmcp import Context, FastMCP
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
import os
import importlib
from mcp.server import Server
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server.sse import SseServerTransport
import uvicorn
import argparse
from starlette.responses import PlainTextResponse
from mcp_host.app_setup import mcp_app
import logging

# --- Dynamically import tool modules ---
try:
    tool_module_keys_str = "{{TOOL_MODULES}}"
    if tool_module_keys_str:
        tool_module_keys = [key.strip() for key in tool_module_keys_str.split(',') if key.strip()]
        for key in tool_module_keys:
            # This makes the module available, e.g., mcp_host.tools.weather
            # The specific tools from these modules are imported in the next block.
            importlib.import_module(f"mcp_host.tools.{key}")
            logging.info(f"Dynamically imported module mcp_host.tools.{key}") # Changed to logging.info
except Exception as e:
    logging.error(f"Failed to load tool modules from the string '{tool_module_keys_str}': {e}", exc_info=True) # Changed to logging.error

# --- Import specific tools ---
# This block will be replaced by the create_server command with concrete import statements
# e.g., from mcp_host.tools.weather import get_weather
# These imports make the tool functions directly available to FastMCP if it discovers them from globals,
# or if they self-register upon import.
{{SPECIFIC_TOOL_IMPORTS}}

# --- Helper function to create Starlette app with SSE ---
def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can serve the provided MCP server with SSE."""
    sse_transport = SseServerTransport("/messages/") # Path for SSE message exchange

    async def handle_sse(request: Request) -> None:
        """Handles the SSE connection for the MCP server."""
        logging.debug(f"SSE connection request: {request}")
        try:
            async with sse_transport.connect_sse(
                    request.scope,
                    request.receive,
                    request._send,  # noqa: SLF001 - Accessing protected member for Starlette integration
            ) as (read_stream, write_stream):
                logging.debug(f"SSE connection established. Running mcp_server...")
                try:
                    await mcp_server.run(
                        read_stream,
                        write_stream,
                        mcp_server.create_initialization_options(),
                    )
                except Exception as e:
                    logging.error(f"Error running MCP server: {e}", exc_info=True)
                    raise
        except Exception as e:
            logging.error(f"Error handling SSE connection: {e}", exc_info=True)
            raise
        

    async def health_check(request: Request) -> PlainTextResponse:
        """Simple health check endpoint."""
        logging.debug(f"Health check requested for {request.url}")
        return PlainTextResponse("OK")

    logging.debug("Creating Starlette app with routes...")
    return Starlette(
        debug=debug,
        routes=[
            Route("/", endpoint=health_check),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse_transport.handle_post_message),
        ],
    )

if __name__ == "__main__":
    # Configure basic logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )

    # For containerized environments, HOST should be 0.0.0.0.
    # PORT environment variable is respected as a default for the port.
    
    parser = argparse.ArgumentParser(description=f"Run MCP SSE-based server for {{SERVER_NAME}}")
    parser.add_argument('--host', default=os.environ.get("HOST", "0.0.0.0"), help='Host to bind to. Defaults to HOST env var or 0.0.0.0.')
    parser.add_argument('--port', type=int, default=int(os.environ.get("PORT", 8080)), help='Port to listen on. Defaults to PORT env var or 8080.')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode for Starlette.')
    args = parser.parse_args()

    logging.info(f"Attempting to start server '{{SERVER_NAME}}' on http://{args.host}:{args.port}") # Changed to logging.info
    logging.debug(f"Parsed arguments: host={args.host}, port={args.port}, debug={args.debug}")
    logging.debug(f"mcp_app instance: {mcp_app}")

    # Access the underlying MCP Server from the FastMCP instance
    # Note: WPS437 suggests avoiding private members, but this is a common pattern for such integrations.
    mcp_server_instance = mcp_app._mcp_server # noqa: WPS437
    logging.debug(f"mcp_server_instance from mcp_app: {mcp_server_instance}")

    if mcp_server_instance is None:
        logging.error("mcp_app._mcp_server is None. Cannot start server.")
        import sys
        sys.exit(1)

    # Create the Starlette application
    logging.debug("Creating Starlette application...")
    starlette_app = create_starlette_app(mcp_server_instance, debug=args.debug)
    logging.debug("Starlette application created.")

    # Run the server with Uvicorn
    logging.debug(f"Starting Uvicorn server on http://{args.host}:{args.port} with debug={args.debug}...")
    try:
        uvicorn.run(starlette_app, host=args.host, port=args.port)
    except Exception as e:
        logging.error(f"Uvicorn failed to start or encountered an error while running server {{SERVER_NAME}} on {args.host}:{args.port}: {e}", exc_info=True) # Changed to logging.error
        import sys
        sys.exit(1)
    logging.debug("Uvicorn server stopped.")