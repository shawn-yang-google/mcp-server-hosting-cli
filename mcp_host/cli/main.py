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
import importlib
import inspect
import asyncio
import ast
import sys
from typing import Any, Dict
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

def _load_tool_modules() -> List[Any]:
    """Dynamically discovers and loads tool modules from the 'mcp_host/tools' directory."""
    loaded_modules = []
    # Construct the path to the 'tools' directory relative to this file (main.py)
    # main.py is in mcp_host/cli/, so ../tools points to mcp_host/tools/
    tools_dir_path = os.path.join(os.path.dirname(__file__), "..", "tools")
    
    if not os.path.isdir(tools_dir_path):
        console.print(f"[red]Tools directory not found at: {tools_dir_path}[/red]")
        return []

    for filename in os.listdir(tools_dir_path):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name_simple = filename[:-3]
            # The import path should be relative to the package root (mcp_host)
            # e.g., mcp_host.tools.weather
            module_import_path = f"mcp_host.tools.{module_name_simple}"
            try:
                module = importlib.import_module(module_import_path)
                loaded_modules.append(module)
            except ImportError as e:
                console.print(f"[red]Failed to import tool module '{module_name_simple}': {e}[/red]")
    return loaded_modules

# Load tool modules once at startup, or call this function where needed
ALL_TOOL_MODULES = _load_tool_modules()

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
    
    console.print("[yellow]Searching for tools in mcp_host/tools/...[/yellow]")
    for module in ALL_TOOL_MODULES:
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
    all_available_tools_info = []
    # Use the dynamically loaded modules
    if not ALL_TOOL_MODULES:
        console.print("[red]Error: No tool modules were loaded. Cannot create server.[/red]")
        console.print("[dim]Please ensure your tools are in the 'mcp_host/tools' directory and are importable.[/dim]")
        return

    for module in ALL_TOOL_MODULES:
        all_available_tools_info.extend(get_tool_info(module))
    
    valid_tool_ids = {tool["id"] for tool in all_available_tools_info}
    invalid_tools = [tool_id for tool_id in tool_ids if tool_id not in valid_tool_ids]
    
    if invalid_tools:
        console.print(f"[red]Error: Invalid tool IDs: {', '.join(invalid_tools)}[/red]")
        console.print(f"[dim]Available tool IDs: {', '.join(sorted(list(valid_tool_ids)))}[/dim]")
        return

    try:
        # Organize tools by module
        tool_modules_map = {} # Renamed from tool_modules to avoid conflict with loop var
        for tool_id in tool_ids:
            # Iterate over the dynamically loaded modules
            for module in ALL_TOOL_MODULES:
                if hasattr(module, tool_id):
                    module_name_key = module.__name__.split(".")[-1]
                    if module_name_key not in tool_modules_map:
                        tool_modules_map[module_name_key] = []
                    tool_modules_map[module_name_key].append(tool_id)
                    break
        
        # --- Refactored server file generation ---
        os.makedirs("servers", exist_ok=True)
        
        # 1. Prepare strings for template substitution
        server_name = name
        # Use keys from tool_modules_map for module_keys_string
        module_keys_string = ", ".join(tool_modules_map.keys()) 
        specific_tool_imports_string = "\n".join(
            f'from mcp_host.tools.{module_name} import {", ".join(selected_tools)}'
            for module_name, selected_tools in tool_modules_map.items()
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

@cli.command("call-tool")
def call_tool(
    tool_name: str = typer.Argument(..., help="Name of the tool to call."),
    tool_args: List[str] = typer.Option(
        [],  # Default to an empty list
        "--tool-arg",
        "-ta",
        help="Tool arguments in key=value format. Values are parsed as Python literals (e.g., 'numbers=[1,2,3]', 'enabled=True', 'name=\"Alice\"'). For simple unquoted strings (e.g. 'operation=add'), quotes are optional. Can be specified multiple times."
    ),
    url: Optional[str] = typer.Option(
        None,
        "--url",
        "-u",
        help="URL of the MCP server's SSE endpoint. If provided, this URL is used directly, overriding the name lookup. Example: http://localhost:10000/sse"
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Name of the MCP server (from deployment config) to connect to. Used if --url is not provided."
    ),
):
    """Call a specified tool on an MCP server with given arguments."""
    server_sse_url: str
    if url:
        server_sse_url = url
    else:
        if not name:
            console.print(f"[red]Error: Must define either --url or --name when calling a tool.[/red]")
            raise typer.Exit(code=1)
        # Assuming deployment_manager is available in this scope.
        resolved_url_base = deployment_manager.get_service_url(name)
        if not resolved_url_base:
            console.print(f"[red]Error: Server '{name}' not found or its URL could not be retrieved.[/red]")
            raise typer.Exit(code=1)
        # Append /sse similar to get-server-capabilities logic
        server_sse_url = resolved_url_base + "/sse"

    parsed_tool_kwargs: Dict[str, Any] = {}
    if tool_args:
        for arg_pair in tool_args:
            if "=" not in arg_pair:
                console.print(f"[yellow]Warning: Skipping malformed tool argument '[b]{arg_pair}[/b]'. Expected format: key=value.[/yellow]")
                continue
            
            key, value_str = arg_pair.split("=", 1)
            try:
                # ast.literal_eval is safer than eval and can parse Python literals:
                # strings, numbers, tuples, lists, dicts, booleans, None.
                parsed_tool_kwargs[key] = ast.literal_eval(value_str)
            except (ValueError, SyntaxError):
                # If ast.literal_eval fails (e.g., for an unquoted string like 'add' in 'operation=add'),
                # treat the value as a plain string.
                # This allows users to pass simple strings without needing to quote them,
                # e.g., --tool-arg operation=add
                # If they need to pass a string that looks like a literal (e.g., "True" as a string),
                # they should quote it: --tool-arg "value='True'"
                parsed_tool_kwargs[key] = value_str

    if not tool_name: # Should be caught by typer.Argument(...) being required
        console.print("[red]Error: Tool name is required.[/red]")
        raise typer.Exit(code=1)

    # Assuming call_mcp_tool is defined in the same file or imported.
    asyncio.run(call_mcp_tool(server_sse_url, tool_name, **parsed_tool_kwargs))

async def call_mcp_tool(server_sse_url: str, tool_name: str, **tool_kwargs):
    """
    Connects to an MCP server via SSE, initializes a session,
    and calls a specified tool with the given arguments.
    """
    print(f"Attempting to connect to MCP server at SSE endpoint: {server_sse_url}")
    print(f"Attempting to call tool '{tool_name}' with arguments: {tool_kwargs}")

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

                # Call the specified tool
                print(f"Calling tool: {tool_name} with arguments: {tool_kwargs}")
                # Assuming the method to call a tool is `call_tool`
                # and it accepts tool name and keyword arguments for tool parameters.
                # Adjust if your MCP client library uses a different method or signature.
                result = await session.call_tool(tool_name, tool_kwargs)
                
                print("-" * 30)
                print("Tool call successful. Result:")
                print(result)
                print("-" * 30)

    except ConnectionRefusedError:
        print(f"Error: Connection refused. Ensure the MCP server is running at {server_sse_url} and accessible.")
        sys.exit(1)
    except AttributeError as e:
        # This might happen if session does not have 'call_tool' or the tool_name is wrong
        # leading to an issue within the library when trying to find/call the tool.
        print(f"An error occurred, possibly related to the tool name or client library: {e}")
        print("Please ensure the tool name is correct and the client session object supports 'call_tool'.")
        print("Details:", e.__class__.__name__)
        sys.exit(1)
    except Exception as e:
        # Catching a broader exception for unexpected issues
        print(f"An error occurred during the tool call: {e}")
        print("Details:", e.__class__.__name__)
        # import traceback
        # traceback.print_exc() # Uncomment for more detailed debugging
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