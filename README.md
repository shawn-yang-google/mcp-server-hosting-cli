# MCP Server Hosting CLI

A command-line tool that simplifies to create, configure, and deploy custom MCP (Model Context Protocol) servers. These servers enable you to connect your chosen tools (e.g., Google Calendar) to LLM clients that support MCP.

## Prerequisites

- Python 3.10 or higher
- Google Cloud Platform (GCP) account with:
  - Cloud Run API (`run.googleapis.com`) enabled
  - Artifact Registry API (`artifactregistry.googleapis.com`) enabled
  - Cloud Build API (`cloudbuild.googleapis.com`) enabled
  - Appropriate permissions for your user/service account (see below)
  - GCP credentials configured locally (`gcloud auth login`)

### Required GCP Permissions

To use this tool effectively, the authenticated GCP user or service account needs the following roles or equivalent permissions:

- **Cloud Run Admin** (`roles/run.admin`): To deploy and manage Cloud Run services.
- **Artifact Registry Writer** (`roles/artifactregistry.writer`): To upload container images to Artifact Registry. This also typically includes permissions to read repositories.
- **Artifact Registry Repository Admin** (`roles/artifactregistry.repoAdmin`) or `artifactregistry.repositories.create` and `artifactregistry.repositories.get` permissions: To allow the tool to create the `mcp-server-images` repository in your project/region if it doesn't exist.
- **Service Usage Consumer** (`roles/serviceusage.serviceUsageConsumer`) or `serviceusage.services.enable` permission: To allow the tool to enable necessary APIs.
- **Cloud Build Editor** (`roles/cloudbuild.builds.editor`) or equivalent: To allow Cloud Build to build and push images. The Cloud Build service account (`PROJECT_NUMBER@cloudbuild.gserviceaccount.com`) will also need Artifact Registry Writer permissions on the target repository.

> **Note on Docker Authentication**: While this tool uses `gcloud builds submit` which handles authentication seamlessly with Artifact Registry, if you need to manually push or pull images using `docker` CLI to your Artifact Registry (e.g., `us-docker.pkg.dev`), you can configure Docker to authenticate with your gcloud credentials. For a specific region like `us`, the command would be:
> ```bash
> gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin us-docker.pkg.dev
> ```
> Replace `us-docker.pkg.dev` with the appropriate regional endpoint if your repository is in a different region.

## Quick Start

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/shawn-yang-google/mcp-server-hosting-cli.git
    cd mcp-server-hosting-cli/
    ```

2.  **Set up your Python environment and install the package:**
    Ensure you have Python 3.10 or higher.
    ```bash
    # Create and activate a virtual environment (recommended)
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate

    # Install the package in editable mode
    python3 -m pip install -e .
    ```
    This installs the `mcp-host` CLI and its dependencies.

3.  **Authenticate with GCP and set your default project:**
    ```bash
    gcloud auth login
    gcloud config set project <YOUR_GCP_PROJECT_ID> # Replace YOUR_GCP_PROJECT_ID
    ```

4.  **List available tools:**
    This command shows you the tools you can include in your MCP server.
    ```bash
    mcp-host list-tools
    ```

5.  **Create and Deploy a Sample Server:**
    This step allows you to quickly verify your setup and the deployment process.

    *   **Create a server configuration:**
        Replace `<YOUR_SERVER_NAME>` with your desired server name. The tool IDs (e.g., `list_events`, `create_event`, `get_forecast`) should come from the output of `mcp-host list-tools`.
        ```bash
        mcp-host create-server --name <YOUR_SERVER_NAME> --tools <TOOL_IDS>
        ```

    *   **Deploy the server to Google Cloud Run:**
        Make sure your GCP project is correctly set (either via `gcloud config set project <YOUR_PROJECT_ID>` or by using the `--project` flag).
        ```bash
        mcp-host deploy-server --name <YOUR_SERVER_NAME>
        # Or, if you need to specify the project:
        # mcp-host deploy-server --name <YOUR_SERVER_NAME> --project <YOUR_GCP_PROJECT_ID>
        ```

6.  **Get the deployed server's URL:**
    Once deployed, you can retrieve its public URL.
    ```bash
    mcp-host get-server-url --name <YOUR_SERVER_NAME>
    ```

7.  **Discover the deployed server's capabilities:**
    This command will connect to your deployed server and list its available tools, resources, and prompts based on the MCP protocol.
    ```bash
    mcp-host get-server-capabilities --name <YOUR_SERVER_NAME>
    ```

You have now created and deployed your custom MCP server.
You are now ready to use your server anywhere!

Next Steps:
* ["Deploy from Git Repo"](#deploy-from-git-repo) section on how to deploy an existing application from a Git repository.
* ["Creating Custom Tools"](#creating-custom-tools) section on how to add your own custom tools and use the CLI to deploy them.
* ["Programmatic Usage with Deployed Servers"](#programmatic-usage-with-deployed-servers) section on how to programmatically use the deployed server.
* ["CLI Commands"](#cli-commands) section for more details on each command.

## Deploy from Git Repo

This section explains how to deploy an existing application, containerized with a Dockerfile, directly from a Git repository to Google Cloud Run. This is useful if you have a pre-existing service or an MCP server with a custom setup that you manage in its own repository.

### Deploy from Git Repo Quick Start

1.  **Ensure your Git repository is ready:**
    *   Your repository must contain a `Dockerfile`.
    *   Your application within the Docker image should be configured to listen on a specific port. By default, the CLI assumes this port is `8080`. If your application uses a different port, or if you want it to listen on a port specified by the `PORT` environment variable (which Cloud Run sets), you'll need to specify this during deployment.

2.  **Authenticate with GCP and set your default project (if not already done):**
    ```bash
    gcloud auth login
    gcloud config set project <YOUR_GCP_PROJECT_ID> # Replace YOUR_GCP_PROJECT_ID
    ```

3.  **Deploy the application from your Git repository:**
    Replace `<YOUR_SERVICE_NAME>` with the desired name for your Cloud Run service and `<YOUR_GIT_REPO_URL>` with the URL of your Git repository.
    ```bash
    mcp-host deploy-git-repo \
        --name <YOUR_SERVICE_NAME> \
        --git-repo-url <YOUR_GIT_REPO_URL>
    ```
    *   **Specify Dockerfile location (optional):** If your Dockerfile is not at the root of the repository, use the `--dockerfile-path` option:
        ```bash
        mcp-host deploy-git-repo --name <YOUR_SERVICE_NAME> \
            --git-repo-url <YOUR_GIT_REPO_URL> \
            --dockerfile-path path/to/your/Dockerfile
        ```
    *   **Specify Container Port (important):** If your application inside the Docker container listens on a port other than `8080`, or if you want to explicitly set the port that Cloud Run expects, use the `--container-port` option. Your application must be configured to listen on this port, or to respect the `PORT` environment variable which Cloud Run will set to this value.
        ```bash
        mcp-host deploy-git-repo --name <YOUR_SERVICE_NAME> \
            --git-repo-url <YOUR_GIT_REPO_URL> \
            --container-port <YOUR_APP_PORT> # e.g., 3000
        ```
    *   **Specify GCP Project (optional):** If you need to deploy to a specific project, different from your gcloud default:
        ```bash
        mcp-host deploy-git-repo --name <YOUR_SERVICE_NAME> \
            --git-repo-url <YOUR_GIT_REPO_URL> \
            --project <YOUR_GCP_PROJECT_ID>
        ```

4.  **Get the deployed service's URL:**
    Once deployed, retrieve its public URL.
    ```bash
    mcp-host get-server-url --name <YOUR_SERVICE_NAME>
    ```
    If your deployed service is an MCP server, you can then use `get-server-capabilities` and `call-tool` as described in other sections, making sure to use the correct URL and endpoint suffix if it's not the default `/sse`.

### How Deploy from Git Repo Works

When you use the `mcp-host deploy-git-repo` command, the CLI performs the following steps:

1.  **Clones Repository**: The specified Git repository is cloned into a temporary local directory.
2.  **Ensures Artifact Registry**: It verifies that an Artifact Registry repository named `mcp-server-images` exists in your configured GCP project and region, creating it if necessary. This repository will store the Docker images.
3.  **Builds Docker Image**:
    *   It locates the `Dockerfile` within the cloned repository (either at the root or at the path specified by `--dockerfile-path`).
    *   The `mcp_host/backend/docker.sh` script is invoked to build a Docker image using this `Dockerfile` and the cloned repository's root as the build context.
    *   The built image is tagged with a name like `REGION-docker.pkg.dev/PROJECT_ID/mcp-server-images/SERVICE_NAME`.
4.  **Pushes Image**: The newly built Docker image is pushed to your project's Artifact Registry.
5.  **Deploys to Cloud Run**:
    *   The `mcp_host/backend/container.sh` script is then used to deploy the image from Artifact Registry to Google Cloud Run.
    *   The `--container-port` argument provided to the CLI (defaulting to `8080`) is passed to `gcloud run deploy --port`. This tells Cloud Run which port your application inside the container is listening on.
    *   **Important for your application**: Your application code within the Docker container must be configured to listen on this specific port. Alternatively, it can be configured to listen on the port specified by the `PORT` environment variable, as Cloud Run will automatically set this environment variable inside your container to match the value passed to `gcloud run deploy --port`.
6.  **Service URL**: After successful deployment, the CLI can retrieve and display the public URL of your new Cloud Run service.

This process allows you to deploy any containerized application from a Git repository, not just MCP servers generated by this tool, provided it has a valid Dockerfile and is configured correctly for port binding on Cloud Run.

## Creating Custom Tools

You can extend the functionality of your MCP servers by creating custom tools. These tools can perform any action you define in Python, from simple calculations to complex integrations with other APIs.

### Steps to Create a Custom Tool

1.  **File Location**:
    Create a new Python file for your tool (e.g., `my_custom_tool.py`) within the `mcp_host/tools/` directory. This is where the CLI expects to find tool definitions.

2.  **Tool Template**:
    Here's a basic template for a custom tool. You would save this in a file like `mcp_host/tools/my_custom_tool.py`:

    ```python
    # mcp_host/tools/my_custom_tool.py
    from typing import Any

    from mcp.server.fastmcp import Context
    # This line imports the global FastMCP instance (mcp_app), which is used throughout your CLI and generated servers to register tools.
    from mcp_host.app_setup import mcp_app
    # Import other libraries

    # The @mcp_app.tool() decorator registers your Python function (e.g., my_custom_tool_function) as an MCP tool.
    @mcp_app.tool()
    async def my_custom_tool_function(context: Context, **kwargs:Any)->Any:
        """
        A brief description of what your custom tool does.

        This description, along with the input and output definitions,
        will be used by MCP to inform the LLM about the tool's capabilities.

        Args:
            context:
              The `context` argument (type: `mcp.server.fastmcp.Context`) is mandatory
              for tool discovery by the MCP application.
            **kwargs: 
              Define your own keyword arguments.
        """ # The function's docstring serves as the tool's description for the LLM, so ensure it is clear and concise.
        ...
        return ...
    
    # Your custom function should be `async def` if it performs I/O operations (like API calls)
    @mcp_app.tool()
    async def my_async_custom_tool_function(context: Context, **kwargs:Any)->Any:
        """
        A brief description of what your custom tool does.

        This description, along with the input and output definitions,
        will be used by MCP to inform the LLM about the tool's capabilities.

        Args:
            context:
              The `context` argument (type: `mcp.server.fastmcp.Context`) is mandatory
              for tool discovery by the MCP application.
            **kwargs: 
              Define your own keyword arguments.
        """
        # Your tool's logic goes here.
        await ... # await async function/api call.
        return ...

    ```

    You can define multiple tools in one file.
    Just make sure each has the `@mcp_app.tool()` decorator.

### Using Your Custom Tool with the CLI

Once you have created your custom tool file in `mcp_host/tools/`:

1.  **List Available Tools**:
    Run `mcp-host list-tools`. Your tools (e.g., `my_custom_tool_function`) should now appear in the list of available tools. The tool ID will be the function name.

2.  **Create a Server with Your Custom Tool**:
    Use the `mcp-host create-server` command and include the ID of your custom tool in the `--tools` list.
    ```bash
    mcp-host create-server --name my-custom-server --tools my_custom_tool_function,get_forecast
    ```

3.  **Deploy and Use**:
    You can then deploy this server (`mcp-host deploy-server --name <my-custom-server>`) and interact with it (e.g., using `mcp-host call-tool <my_custom_tool_function> --name <my-custom-server> --tool-arg "param1=hello" --tool-arg "param2=123"`) just like any other server created with the CLI.

### How Custom Tools Work

1.  **Automatic Tool Discovery and Server Configuration**:

    When you place your custom tool file (e.g., `my_custom_tool.py`) in the `mcp_host/tools/` directory, the `mcp-host list-tools` command automatically detect it. The tool's name will be the Python function name you defined (e.g., `my_custom_tool_function`).

    The `mcp-host create-server` command streamlines the integration of your custom tool into a new server. If you include your custom tool's function name in the `--tools` argument (e.g., `mcp-host create-server --name <your-server> --tools my_custom_tool_function,...`), the CLI performs these actions:

    *   **Identifies the Tool**: It recognizes `my_custom_tool_function` as a tool and infers its module name from the filename (e.g., `my_custom_tool` from `my_custom_tool.py`).
    *   **Updates Server Template**: In the server code generated from `mcp_host/cli/server_template.py`, it:
        *   Populates the `{{TOOL_MODULES}}` placeholder with the inferred module name (e.g., `my_custom_tool`), adding code like `importlib.import_module(f"mcp_host.tools.my_custom_tool")` to the server.
        *   Populates the `{{SPECIFIC_TOOL_IMPORTS}}` placeholder with a direct import statement for your tool function, such as `from mcp_host.tools.my_custom_tool import my_custom_tool_function`.
    *   **Registers the Tool**: When the generated server starts, these import statements are executed. Importing your tool's module (`my_custom_tool.py`) triggers the `@mcp_app.tool()` decorator, which registers `my_custom_tool_function` with the central `mcp_app` (an instance of FastMCP).
    *   **Runs the Server**: The `server_template.py` logic then uses this updated `mcp_app`, now aware of your custom tool, to initialize and operate the MCP server.

2.  **Model Context Protocol (MCP) Perspective**:
    As highlighted in the [MCP Server Quickstart](https://modelcontextprotocol.io/quickstart/server), `FastMCP` (which `mcp_app` is an instance of) uses Python type hints and docstrings to automatically generate the tool definitions that are exposed via the Model Context Protocol.
    *   Your custom Python function, decorated with `@mcp_app.tool()`, along with its input and output, provides all the necessary information for `FastMCP` to create a valid MCP tool definition.
    *   This definition tells the MCP client (and the LLM) what the tool is called, what it does (from the docstring), the parameters it expects, and what it returns.
    *   The generated server then handles the MCP communication, receives tool invocation requests from the client, executes your Python function with the provided arguments, and sends the result back.

## Programmatic Usage with Deployed Servers

Once your MCP server is deployed and you have its URL (e.g., via `mcp-host get-server-url --name <your-server-name>`), you can interact with it programmatically from your own Python applications or scripts. This allows for more complex workflows, such as integrating MCP tools into larger systems or using them directly with Large Language Models (LLMs).

### 1. Understanding the Server URL and Endpoints

The base URL of your deployed MCP server can be retrieved using `mcp-host get-server-url --name <your-server-name>` (e.g., `https://your-server-abcdefg-uc.a.run.app/`). This server exposes specific URL endpoints for different functionalities:

*   **Health Check (`/`)**: The root path of the base URL (e.g., `https://your-server-abcdefg-uc.a.run.app/`) serves as a health check. This endpoint returns an "OK" status, allowing services like Google Cloud Run to monitor the server's availability.
*   **SSE Connection (`/sse`)**: The Server-Sent Events (SSE) endpoint is found by appending `/sse` to the base URL (e.g., `https://your-server-abcdefg-uc.a.run.app/sse`). MCP clients use this URL to establish a connection for real-time, bi-directional communication with the server.
*   **Message Posting (`/messages/`)**: For the MCP client to send messages (such as tool invocation requests) to the server as part of the SSE communication, it uses an endpoint typically at `/messages/` relative to the base URL (e.g., `https://your-server-abcdefg-uc.a.run.app/messages/`). The MCP client library generally handles this internally.

When configuring an MCP client to connect to your server, you will primarily use the `/sse` endpoint URL (e.g., `https://your-server-abcdefg-uc.a.run.app/sse`).

### 2. Directly Calling a Tool (Python Example)

You can call tools on your deployed server directly using Python with the `mcp` client library. This is similar to what the `mcp-host call-tool` CLI command does internally.

First, ensure you have the `mcp` library installed in your Python environment. If your project containing the CLI has it, you might already have it. Otherwise:
```bash
pip install mcp
```

Here's an example of how to connect to the server and call a tool:

```python
import asyncio
from mcp import ClientSession
from mcp.client.sse_client import sse_client

async def direct_tool_call_example(server_sse_url: str, tool_name: str, tool_args: dict):
    """
    Example of directly calling a tool on a deployed MCP server.
    """
    print(f"Attempting to connect to MCP server at SSE endpoint: {server_sse_url}")
    print(f"Attempting to call tool '{tool_name}' with arguments: {tool_args}")

    try:
        # Establish the SSE connection
        async with sse_client(server_sse_url) as (readable_stream, writable_stream):
            print("SSE connection established.")

            # Create and initialize an MCP client session
            async with ClientSession(readable_stream, writable_stream) as session:
                print("Initializing MCP session...")
                await session.initialize()
                print("MCP session initialized successfully.")
                
                # Call the specified tool
                print(f"Calling tool: {tool_name} with arguments: {tool_args}")
                result = await session.call_tool(tool_name, tool_args)
                
                print("-" * 30)
                print("Tool call successful.")
                # Assuming `result` has a `.content` attribute holding the tool's output
                print("Result content:", result.content) 
                print("-" * 30)
                return result.content

    except ConnectionRefusedError:
        print(f"Error: Connection refused. Ensure the MCP server is running at {server_sse_url} and accessible.")
    except Exception as e:
        print(f"An error occurred during the tool call: {e}")
        print("Details:", e.__class__.__name__)
    return None

# Example of how to run this:
# async def main():
#     server_url = "YOUR_SERVER_SSE_URL_HERE"  # Replace with the URL from 'mcp-host get-server-url'
#     # Example: calling a 'get_forecast' tool
#     # Ensure 'get_forecast' is one of the tools deployed on your server
#     # and it expects 'latitude' and 'longitude' arguments.
#     # content = await direct_tool_call_example(
#     #     server_sse_url=server_url,
#     #     tool_name="get_forecast", 
#     #     tool_args={"latitude": 37.3688, "longitude": -122.0363}
#     # )
#     # if content:
#     #     print("Retrieved content from tool call:", content)
#
# if __name__ == "__main__":
# asyncio.run(main())
```

Replace `"YOUR_SERVER_SSE_URL_HERE"`, `"get_forecast"`, and `{"latitude": 37.3688, "longitude": -122.0363}` with your actual server URL, a tool name available on that server, and its corresponding arguments.

### 3. Integrating with Large Language Models (LLMs)

A powerful use case for MCP servers is to provide tools to LLMs. The LLM can then decide when to use these tools to answer queries or perform actions. The following example demonstrates how you might integrate your MCP server's tools with an LLM like Anthropic's Claude. For details, refer to the [MCP client official doc](https://modelcontextprotocol.io/quickstart/client#query-processing-logic).


## CLI Commands

### List Available Tools
```bash
mcp-host list-tools
```
Lists all available tools that can be added to your MCP server, including their descriptions and required configurations.

### Create a New Server
```bash
mcp-host create-server --name <server-name> --tools <tool1,tool2,...>
```
Creates a new MCP server configuration with the specified tools.

Options:
- `--name`: Unique name for your server
- `--tools`: Comma-separated list of tool IDs (use the exact IDs shown in the first column of `list-tools` output)

Example:
```bash
mcp-host create-server --name my-server --tools list_events,create_event,get_forecast
```

> **Important**: You must use the exact tool IDs as shown in the first column of the `list-tools` output. For example, use the tool ID `get_forecast` (not the module `weather`) and tool ID `list_events` (not the module `calendar`).

### Deploy a Server
```bash
mcp-host deploy-server --name <server-name> [--project <gcp-project-id>] [--container-port <port>] [--startup-probe-path <path>]
```
Deploys your configured MCP server to Google Cloud Run. The server is an ASGI application built with Starlette and run using Uvicorn, utilizing Server-Sent Events (SSE) for communication. This command uses the `Dockerfile` at the root of the `mcp-server-hosting-cli` project and the `server_template.py`.

Options:
- `--name`: Name of your server to deploy
- `--project`: (Optional) GCP project ID to deploy to (overrides environment variable or gcloud config).
- `--container-port` / `-cp`: (Optional) The port the application inside the Docker container listens on. Defaults to `8080`. The `server_template.py` (used for this command) respects the `PORT` environment variable set by Cloud Run to this value.
- `--startup-probe-path` / `-spp`: (Optional) HTTP GET path for the Cloud Run startup probe (e.g., `/healthz`, `/api/health`). If not specified, Cloud Run uses its default path (`/`).

> **Note**: The tool detects your GCP project in the following order:
> 1. `--project` parameter if provided.
> 2. `GCP_PROJECT_ID` environment variable if set (you can `export GCP_PROJECT_ID=<your-project>` before running `mcp-host` commands to set a default for the session).
> 3. The default project from `gcloud config get-value project`.
> To avoid specifying the project each time for a session, `export GCP_PROJECT_ID=<your-project-id>` or set your gcloud default project with `gcloud config set project your-project-id`.

Example:
```bash
mcp-host deploy-server --name my-weather-server --project my-gcp-project --container-port 3001 --startup-probe-path /health
```

### Deploy from Git Repository
```bash
mcp-host deploy-git-repo --name <service-name> --git-repo-url <git-url> [--dockerfile-path <path/in/repo>] [--container-port <port>] [--startup-probe-path <path>] [--env KEY=VALUE ...] [--project <gcp-project-id>]
```
Clones a Git repository, builds its Docker image using the specified (or root) Dockerfile, and deploys it to Google Cloud Run.

Options:
- `--name` / `-n`: (Required) Unique name for your new Cloud Run service.
- `--git-repo-url` / `-g`: (Required) URL of the Git repository.
- `--dockerfile-path` / `-d`: (Optional) Path to the Dockerfile within the repository. Defaults to `Dockerfile` at the repository root.
- `--container-port` / `-cp`: (Optional) The port your application inside the Docker container listens on. Defaults to `8080`. Your application must be configured to use this port or respect the `PORT` environment variable set by Cloud Run to this value.
- `--startup-probe-path` / `-spp`: (Optional) HTTP GET path for the Cloud Run startup probe (e.g., `/healthz`, `/api/status`). If not specified, Cloud Run uses its default path (`/`). This is useful if your application's health check endpoint is not at the root.
- `--env` / `-e`: (Optional) Environment variables to set in the container (e.g., `KEY=VALUE`). Can be specified multiple times. This is crucial for passing configuration like API keys or OAuth client credentials.
- `--project` / `-p`: (Optional) GCP project ID to deploy to (overrides default project context).

**Important Note on `PUBLIC_URL` for OAuth Callbacks:**
Some applications deployed from Git (especially those implementing an OAuth2 flow, like the `g2n-mcp-gcal-sse` example) require an environment variable (e.g., `PUBLIC_URL`) to be set to their own public-facing URL. This is used to construct correct redirect URIs for the OAuth provider. Since the public URL is only known *after* the first deployment, you might need a two-step process:
1. Deploy the service initially (potentially without `PUBLIC_URL`, or with a placeholder if the app requires one to start).
2. Get the assigned service URL using `mcp-host get-server-url --name <service-name> --raw`.
3. Re-run the `mcp-host deploy-git-repo` command, this time adding `--env "PUBLIC_URL=<the_obtained_url>"` to update the service with the correct public URL.

Example:
```bash
# Deploy a custom app from Git that needs API keys and a specific health check path
mcp-host deploy-git-repo \
    --name my-custom-data-app \
    --git-repo-url https://github.com/my-user/my-data-app.git \
    --container-port 3000 \
    --startup-probe-path /api/v1/health \
    --env "API_KEY=abcdef12345" \
    --env "DATABASE_URL=..."

# Example for an app like g2n-mcp-gcal-sse requiring OAuth credentials and PUBLIC_URL
# (assuming MY_CLIENT_ID, MY_CLIENT_SECRET are set in your shell)
# Step 1: Initial Deploy (PUBLIC_URL might be missing or incorrect for now)
mcp-host deploy-git-repo \
    --name my-gcal-mcp \
    --git-repo-url https://github.com/gabriel-g2n/g2n-mcp-gcal-sse.git \
    --container-port 3001 \
    --startup-probe-path /health \
    --env "GOOGLE_CLIENT_ID=$MY_CLIENT_ID" \
    --env "GOOGLE_CLIENT_SECRET=$MY_CLIENT_SECRET"

# Step 2: Get the URL (use --raw for scripting)
SERVICE_URL=$(mcp-host get-server-url --name my-gcal-mcp --raw)

# Step 3: Update the service with the correct PUBLIC_URL
if [ -n "$SERVICE_URL" ]; then
  mcp-host deploy-git-repo \
      --name my-gcal-mcp \
      --git-repo-url https://github.com/gabriel-g2n/g2n-mcp-gcal-sse.git \
      --container-port 3001 \
      --startup-probe-path /health \
      --env "GOOGLE_CLIENT_ID=$MY_CLIENT_ID" \
      --env "GOOGLE_CLIENT_SECRET=$MY_CLIENT_SECRET" \
      --env "PUBLIC_URL=$SERVICE_URL"
else
  echo "Failed to get service URL for my-gcal-mcp."
fi

# After this, you would typically need to go through the app's /auth flow in a browser
# to authorize it with Google Calendar, before its MCP /sse endpoint is active.
```

### Get Server URL
```bash
mcp-host get-server-url --name <server-name> [--raw]
```
Retrieves and displays the public URL of a deployed MCP server.

Options:
- `--name`: The name of the deployed server.
- `--raw`: (Optional) Output only the raw URL string, without any formatting. Useful for scripting.

Example:
```bash
mcp-host get-server-url --name my-server
# For scripting:
MY_URL=$(mcp-host get-server-url --name my-server --raw)
```

### List Your Servers
```bash
mcp-host list-servers
```
Lists locally configured MCP servers (from the `servers/` directory) and shows their deployment statuses on Cloud Run.

Example:
```bash
mcp-host list-servers
```

### Delete Your Server
```bash
mcp-host delete-server  --name <server-name>
```
Delete both locally configured MCP servers (from the `servers/` directory) and remotely deployed MCP servers in CloudRun.

Example:
```bash
mcp-host delete-server --name my-server
```

### Get Server Capabilities
```bash
mcp-host get-server-capabilities [--name <server-name>] [--url <full-mcp-endpoint-url>] [--endpoint-suffix <suffix>]
```
Connects to a deployed MCP server and lists its available tools, resources, and prompts.
You must provide either `--name` (to look up a server deployed by this tool) or a direct `--url`.

Options:
- `--name` / `-n`: (Optional) The name of the deployed server. Used if `--url` is not provided. The command will fetch the base service URL and append the `--endpoint-suffix`.
- `--url` / `-u`: (Optional) Full direct URL of the MCP server's capabilities endpoint. If provided, this is used as-is, ignoring `--name` and `--endpoint-suffix`. Example: `https://your-server.a.run.app/custom/mcp_endpoint`
- `--endpoint-suffix` / `-es`: (Optional) Suffix to append to the base server URL when `--name` is used and `--url` is not. Defaults to `/sse`. Use `""` for no suffix if the base URL itself is the endpoint.

Example:
```bash
# Using server name (assumes default /sse suffix for MCP endpoint)
mcp-host get-server-capabilities --name my-mcp-server

# Using server name with a custom endpoint suffix
mcp-host get-server-capabilities --name my-mcp-server --endpoint-suffix /api/mcp

# Using a direct full URL to the MCP endpoint
mcp-host get-server-capabilities --url https://my-other-server.a.run.app/actual-mcp-path
```

### Call a Tool on a Server
```bash
mcp-host call-tool <tool-name> [--name <server-name>] [--url <full-mcp-endpoint-url>] [--endpoint-suffix <suffix>] [--tool-arg <key=value> ...]
```
Connects to a deployed MCP server and calls a specified tool with the given arguments.
You must provide either `--name` (to look up a server deployed by this tool) or a direct `--url`.

Options:
- `<tool-name>`: (Required) The name of the tool to call.
- `--name` / `-n`: (Optional) The name of the deployed server. Used if `--url` is not provided. The command will fetch the base service URL and append the `--endpoint-suffix`.
- `--url` / `-u`: (Optional) Direct full URL of the MCP server's endpoint (typically the SSE endpoint for MCP). If provided, this is used as-is. Example: `https://your-server.a.run.app/custom/sse_or_messages_path`
- `--endpoint-suffix` / `-es`: (Optional) Suffix to append to the base server URL when `--name` is used and `--url` is not. Defaults to `/sse`. Use `""` for no suffix.
- `--tool-arg` / `-ta`: (Optional) Argument for the tool, in `key=value` format. Can be specified multiple times.

Example:
```bash
# Call 'advanced_math' on 'my-calculator-server' (assumes default /sse suffix)
mcp-host call-tool advanced_math --name my-calculator-server \
    --tool-arg "operation=sqrt" \
    --tool-arg "number=25"

# Call 'basic_math' using a direct URL to its MCP endpoint
mcp-host call-tool basic_math --url https://your-server.a.run.app/my-mcp-handler \
    --tool-arg "operation=add" \
    --tool-arg "numbers=[10,20,30]"
```