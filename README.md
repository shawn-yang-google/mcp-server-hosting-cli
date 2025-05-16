# MCP Server Hosting CLI

A command-line tool that makes it easy to create, configure, and deploy custom MCP (Model Context Protocol) servers. These servers enable you to connect your chosen tools (e.g., Google Calendar) to LLM clients that support MCP.

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
- **Service Usage Consumer** (`roles/serviceusage.serviceUsageConsumer`) or `serviceusage.services.enable` permission: To allow enabling necessary APIs if they are not already enabled.
- **Cloud Build Editor** (`roles/cloudbuild.builds.editor`) or equivalent: To allow Cloud Build to build and push images. The Cloud Build service account (`PROJECT_NUMBER@cloudbuild.gserviceaccount.com`) will also need Artifact Registry Writer permissions on the target repository.

> **Note on Docker Authentication**: While this tool uses `gcloud builds submit` which handles authentication seamlessly with Artifact Registry, if you ever need to manually push or pull images using `docker` CLI to your Artifact Registry (e.g., `us-docker.pkg.dev`), you can configure Docker to authenticate using your gcloud credentials. For a specific region like `us`, the command would be:
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
    This allows you to quickly verify your setup and the deployment process.

    *   **Create a server configuration:**
        Replace `<YOUR_SERVER_NAME>` with your desired server name. The tool IDs (e.g., `list_events`, `create_event`, `get_weather`, etc) should come from the output of `mcp-host list-tools`.
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

You have created and deployed your custom MCP servers.
You are now ready to use it anywhere!
Refer to the "CLI Commands" section for more details on each command and further customization.

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
- `--tools`: Comma-separated list of tool IDs (exact IDs shown in the first column of `list-tools` output)

Example:
```bash
mcp-host create-server --name my-server --tools list_events,create_event,get_weather
```

> **Important**: You must use the exact tool IDs as shown in the first column of the `list-tools` output. For example, use `get_weather` (not `weather`) and `list_events` (not `calendar`).

### Deploy a Server
```bash
mcp-host deploy-server --name <server-name> [--project <gcp-project-id>]
```
Deploys your configured MCP server to Google Cloud Run. The server is an ASGI application built with Starlette and run using Uvicorn, utilizing Server-Sent Events (SSE) for communication.

Options:
- `--name`: Name of your server to deploy
- `--project`: (Optional) GCP project ID to deploy to (overrides environment variable or gcloud config)

> **Note**: The tool detects your GCP project in the following order:
> 1. `--project` parameter if provided
> 2. `GCP_PROJECT_ID` environment variable if set
> 3. Default project from `gcloud config get-value project`
> To avoid specifying the project each time, set your default project with `gcloud config set project your-project-id`

Example:
```bash
mcp-host deploy-server --name my-server --project my-gcp-project
```

### Get Server URL
```bash
mcp-host get-server-url --name <server-name>
```
Retrieves and displays the public URL of a deployed MCP server.

Options:
- `--name`: The name of the deployed server.

Example:
```bash
mcp-host get-server-url --name my-server
```

### List Your Servers
```bash
mcp-host list-servers
```
Lists locally configured MCP servers (from the `servers/` directory) and shows their deployment status on Cloud Run.

Example:
```bash
mcp-host delete-server --name my-server
```