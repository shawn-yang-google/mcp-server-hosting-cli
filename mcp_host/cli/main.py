"""
CLI entry point for the MCP Hosting Service.
"""

import typer
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
import os
import asyncio
import sys
from typing import Any
from urllib.parse import urlparse
import importlib
import inspect
import subprocess
import http.server
import socketserver
import time
import datetime
from mcp.server.fastmcp import Context, FastMCP
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

from ..backend.deployment import DeploymentManager
from ..tools import weather, calendar, search, calculator

cli = typer.Typer(
    name="mcp-host",
    help="MCP Server Hosting Service CLI",
    add_completion=False,
)
console = Console()

# Constants for SSE Server
SSE_PORT = 10000
SSE_HOST = "localhost"

# SSE Handler Class
class SSEHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/events':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*') # Allow all origins
            self.end_headers()
            try:
                while True:
                    # Send current time as an event
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    message = f"data: Server time: {current_time}\n\n"
                    self.wfile.write(message.encode('utf-8'))
                    self.wfile.flush()
                    time.sleep(1)  # Send an event every 1 second
            except BrokenPipeError:
                # Client disconnected
                console.print("[yellow]SSE Client disconnected.[/yellow]")
            except ConnectionAbortedError:
                console.print("[yellow]SSE Connection aborted by client.[/yellow]")
            except Exception as e:
                console.print(f"[red]An error occurred in SSE handler: {e}[/red]")
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>SSE Client</title>
            </head>
            <body>
                <h1>Server-Sent Events (SSE)</h1>
                <div id="sse-data">Waiting for data...</div>

                <script>
                    const eventSource = new EventSource('/events');
                    const sseDataDiv = document.getElementById('sse-data');

                    eventSource.onmessage = function(event) {
                        const newElement = document.createElement("p");
                        newElement.textContent = event.data;
                        sseDataDiv.appendChild(newElement);
                        // Scroll to the bottom
                        window.scrollTo(0, document.body.scrollHeight);
                    };

                    eventSource.onerror = function(err) {
                        console.error("EventSource failed:", err);
                        sseDataDiv.textContent = "Error connecting to SSE. Check console.";
                        eventSource.close();
                    };
                </script>
            </body>
            </html>
            """
            self.wfile.write(html_content.encode('utf-8'))
        else:
            self.send_error(404, "File not found")

def _run_sse_server(host: str, port: int):
    with socketserver.TCPServer((host, port), SSEHandler) as httpd:
        console.print(f"[green]Serving SSE on http://{host}:{port}/events[/green]")
        console.print(f"Open http://{host}:{port}/ to view the client.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            console.print("\n[yellow]Keyboard interrupt received, shutting down SSE server.[/yellow]")
            httpd.server_close()

@cli.command()
def serve_sse(
    host: str = typer.Option(SSE_HOST, "--host", "-h", help="Hostname for the SSE server"),
    port: int = typer.Option(SSE_PORT, "--port", "-p", help="Port for the SSE server"),
):
    """Run a simple Server-Sent Events (SSE) server."""
    _run_sse_server(host, port)

def get_gcloud_project():
    """Try to get the default GCP project from gcloud config."""
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        project_id = result.stdout.strip()
        return project_id if project_id else "your-project-id"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "your-project-id"

# Initialize deployment manager
deployment_manager = DeploymentManager(
    project_id=os.getenv("GCP_PROJECT_ID") or get_gcloud_project(),
    region=os.getenv("GCP_REGION", "us-central1")
)

def get_tool_info(module):
    """Get tool information from a module."""
    tools = []
    # Instead of looking for attributes, just collect all functions with docstrings
    # that appear to be MCP tools (taking ctx as first parameter)
    for name, func in inspect.getmembers(module, inspect.isfunction):
        # Skip helper or internal functions
        if name.startswith('_'):
            continue
        
        # Get signature to check for Context parameter
        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            # Check if it looks like an MCP tool (has ctx parameter)
            if len(params) > 0 and params[0] == 'ctx':
                tools.append({
                    "id": name,
                    "name": name.replace("_", " ").title(),
                    "description": func.__doc__ or "",
                    "version": "0.1.0", 
                    "author": "MCP Hosting Service"
                })
        except (ValueError, TypeError):
            # Skip functions with invalid signatures
            pass
            
    return tools

@cli.command()
def list_tools():
    """List all available pre-integrated tools."""
    table = Table(title="Available Tools")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Description", style="yellow")
    table.add_column("Version", style="blue")
    table.add_column("Author", style="magenta")

    # Get tools from each module
    all_tools = []
    
    # Debug info
    console.print("[yellow]Searching for tools in modules...[/yellow]")
    for module in [weather, calendar, search, calculator]:
        console.print(f"[cyan]Module: {module.__name__}[/cyan]")
        for name, func in inspect.getmembers(module, inspect.isfunction):
            console.print(f"  Function: {name}")
            console.print(f"  Attributes: {[attr for attr in dir(func) if attr.startswith('_mcp') or attr.startswith('__mcp')]}")
        all_tools.extend(get_tool_info(module))

    for tool in all_tools:
        table.add_row(
            tool["id"],
            tool["name"],
            tool["description"],
            tool["version"],
            tool["author"]
        )

    console.print(table)

@cli.command()
def create_server(
    name: str = typer.Option(..., help="Name of the MCP server"),
    tools: str = typer.Option(..., help="Comma-separated list of tool identifiers"),
):
    """Create and configure a new MCP server."""
    # Parse tool list
    tool_ids = [t.strip() for t in tools.split(",")]
    
    # Validate tools
    all_tools = []
    for module in [weather, calendar, search, calculator]:
        all_tools.extend(get_tool_info(module))
    
    valid_tool_ids = {tool["id"] for tool in all_tools}
    invalid_tools = [tool_id for tool_id in tool_ids if tool_id not in valid_tool_ids]
    
    if invalid_tools:
        console.print(f"[red]Error: Invalid tool IDs: {', '.join(invalid_tools)}[/red]")
        return

    try:
        # Organize tools by module
        tool_modules = {}
        for tool_id in tool_ids:
            for module in [weather, calendar, search, calculator]:
                if hasattr(module, tool_id):
                    module_name_key = module.__name__.split(".")[-1]
                    if module_name_key not in tool_modules:
                        tool_modules[module_name_key] = []
                    tool_modules[module_name_key].append(tool_id)
                    break
        
        # --- Refactored server file generation ---
        os.makedirs("servers", exist_ok=True)
        
        # 1. Prepare strings for template substitution
        server_name = name
        module_keys_string = ", ".join(tool_modules.keys())
        specific_tool_imports_string = "\n".join(
            f'from mcp_host.tools.{module_name} import {", ".join(tools)}'
            for module_name, tools in tool_modules.items()
        )

        try:
            # Correct path assuming main.py is in mcp_host/cli/ and template is mcp_host/cli/server_template.py
            template_path = os.path.join(os.path.dirname(__file__), "server_template.py")
            with open(template_path, "r") as f:
                template_content = f.read()
        except FileNotFoundError:
            console.print(f"[red]Error: Server template file not found at {template_path}[/red]")
            return

        # 4. Substitute placeholders in the template
        server_code = template_content.replace("{{SERVER_NAME}}", server_name)
        server_code = server_code.replace("{{SPECIFIC_TOOL_IMPORTS}}", specific_tool_imports_string)
        server_code = server_code.replace("{{TOOL_MODULES}}", module_keys_string)
        
        # 5. Write the final server script to servers/{name}.py
        server_py_path = f"servers/{server_name}.py"
        with open(server_py_path, "w") as f:
            f.write(server_code)
        # --- End of refactored server file generation ---
        
        console.print(f"[green]Successfully created server '{server_name}'[/green]")
        console.print(f"  Server script: {server_py_path}")
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")

@cli.command()
def deploy_server(
    name: str = typer.Option(..., help="Name of the MCP server to deploy"),
    project: str = typer.Option(None, help="GCP project ID to deploy to (overrides environment variable)"),
):
    """Deploy the configured MCP server."""
    server_file = f"servers/{name}.py"
    if not os.path.exists(server_file):
        console.print(f"[red]Error: Server '{name}' not found[/red]")
        return

    try:
        # Create temporary deployment manager with project override if provided
        deploy_manager = deployment_manager
        if project:
            deploy_manager = DeploymentManager(
                project_id=project,
                region=deployment_manager.region
            )
            console.print(f"[yellow]Using project: {project}[/yellow]")

        # Deploy to Cloud Run
        console.print(f"[yellow]Deploying server '{name}' to Cloud Run...[/yellow]")
        service_url = deploy_manager.deploy_server(name, server_file)
        
        console.print(f"[green]Successfully deployed server '{name}'[/green]")
        console.print(Panel(f"Server URL: {service_url}", title="Deployment Info"))
        
    except Exception as e:
        console.print(f"[red]Error deploying server: {str(e)}[/red]")

@cli.command()
def list_servers():
    """List all deployed MCP servers."""
    if not os.path.exists("servers"):
        console.print("[yellow]No servers found[/yellow]")
        return

    table = Table(title="Deployed Servers")
    table.add_column("Name", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("URL", style="magenta")

    for server_file in os.listdir("servers"):
        if server_file.endswith(".py"):
            name = server_file[:-3]
            try:
                service_url = deployment_manager.get_service_url(name)
                status = "Running" if service_url else "Not Deployed"
                table.add_row(name, status, service_url or "N/A")
            except Exception:
                table.add_row(name, "Error", "N/A")

    console.print(table)

@cli.command()
def delete_server(
    name: str = typer.Option(..., help="Name of the MCP server to delete"),
):
    """Delete a deployed MCP server."""
    server_file = f"servers/{name}.py"
    if not os.path.exists(server_file):
        console.print(f"[red]Error: Server '{name}' not found[/red]")
        return

    try:
        # Delete from Cloud Run
        console.print(f"[yellow]Deleting server '{name}' from Cloud Run...[/yellow]")
        deployment_manager.delete_server(name)
        
        # Remove server file
        os.remove(server_file)
        console.print(f"[green]Successfully deleted server '{name}'[/green]")
    except Exception as e:
        console.print(f"[red]Error deleting server: {str(e)}[/red]")

@cli.command()
def get_server_url(
    name: str = typer.Option(..., help="Name of the MCP server to get the URL for"),
):
    """Get the URL of a deployed MCP server."""
    console.print(f"[yellow]Fetching URL for server '{name}'...[/yellow]")
    service_url = deployment_manager.get_service_url(name)

    if service_url:
        console.print(Panel(f"Server URL: {service_url}", title=f"URL for {name}"))
    else:
        console.print(f"[red]Could not retrieve URL for server '{name}'. It might not be deployed or an error occurred.[/red]")

@cli.command("get-server-capabilities")
def get_server_capabilities(
    url: Optional[str] = typer.Option(None, "--url", "-u", help="URL of the MCP server. If provided, this URL is used directly, overriding the name lookup. Example: http://localhost:10000/sse"),
    name: str = typer.Option(..., help="Name of the MCP server to generate a client script for"),
):
    """Generate a client script for an MCP server."""
    if not url:
        url = deployment_manager.get_service_url(name) + "/sse"
        if not url:
            console.print(f"[red]Error: Server '{name}' not found[/red]")
            return
    asyncio.run(discover_mcp_capabilities(url))

def print_items(name: str, items_list: list) -> None:
    """Print items with formatting.

    Args:
        name: Category name (e.g., "tools", "resources", "prompts")
        items_list: A list of items to print.
    """
    print(f"\nAvailable {name}:")
    if items_list:
        for item in items_list:
            print(f" * {item}")
    else:
        print(f"No {name} available.")

async def discover_mcp_capabilities(server_sse_url: str):
    """
    Connects to an MCP server via SSE, initializes a session,
    and lists its available tools, resources, and prompts.
    """
    print(f"Attempting to connect to MCP server at SSE endpoint: {server_sse_url}")

    try:
        # Establish the SSE connection
        async with sse_client(server_sse_url) as (readable_stream, writable_stream):
            print("SSE connection established.")

            # Create and initialize an MCP client session using the SSE streams
            async with ClientSession(readable_stream, writable_stream) as session:
                print("Initializing MCP session...")
                await session.initialize()
                print("MCP session initialized successfully.")
                print("-" * 30) # Separator

                # Fetch and print tools
                tools_result = await session.list_tools()
                # Assuming tools_result is an object with a 'tools' attribute list
                # or the result itself is the list. Adjust if the structure is different.
                # Example: if tools_result is like {'tools': ['tool1', 'tool2']}
                print_items("tools", getattr(tools_result, 'tools', [])) # Safely get 'tools' or empty list

                # Fetch and print resources
                resources_result = await session.list_resources()
                print_items("resources", getattr(resources_result, 'resources', []))

                # Fetch and print prompts
                prompts_result = await session.list_prompts()
                print_items("prompts", getattr(prompts_result, 'prompts', []))

                print("-" * 30)
                print("Discovery complete.")

    except ConnectionRefusedError:
        print(f"Error: Connection refused. Ensure the MCP server is running at {server_sse_url} and accessible.")
        sys.exit(1)
    except Exception as e:
        # Catching a broader exception can be helpful for unexpected issues
        # from the mcp library or network.
        print(f"An error occurred: {e}")
        print("Details:", e.__class__.__name__)
        # You might want to print the traceback for more detailed debugging if needed:
        # import traceback
        # traceback.print_exc()
        sys.exit(1)


def get_tool_info(module):
    """Get tool information from a module."""
    tools = []
    # Instead of looking for attributes, just collect all functions with docstrings
    # that appear to be MCP tools (taking ctx as first parameter)
    for name, func in inspect.getmembers(module, inspect.isfunction):
        # Skip helper or internal functions
        if name.startswith('_'):
            continue
        
        # Get signature to check for Context parameter
        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            # Check if it looks like an MCP tool (has ctx parameter)
            if len(params) > 0 and params[0] == 'ctx':
                tools.append({
                    "id": name,
                    "name": name.replace("_", " ").title(),
                    "description": func.__doc__ or "",
                    "version": "0.1.0", 
                    "author": "MCP Hosting Service"
                })
        except (ValueError, TypeError):
            # Skip functions with invalid signatures
            pass
            
    return tools

def main():
    cli() 