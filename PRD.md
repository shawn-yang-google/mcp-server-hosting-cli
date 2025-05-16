# MCP Server Hosting Service (CLI MVP)

A service that allows users to easily create, configure, and deploy custom MCP (Model Context Protocol) servers through a command-line interface (CLI). These servers enable users to connect their chosen tools (e.g., Google Calendar) to LLM clients that support MCP, such as Python.

## Target Users

Developers, AI practitioners, and technically savvy users who want to extend the capabilities of their LLMs by integrating them with external tools and data sources via MCP.

## Goals

- **Enable User-Defined MCP Servers:** Allow users to select from a predefined list of tools and deploy an MCP server instance that exposes these tools.
- **Simplified Deployment:** Automate the deployment of user-configured MCP servers to a managed cloud environment (Google Cloud Run).
- **Clear Configuration Access:** Provide users with the necessary information (server URL, port, example client code) to connect their MCP clients to their hosted server.

## User Stories / Critical User Journeys (CUJs) - CLI Focus

### CUJ-1: User Onboarding & Setup (Assumed)
- As a developer, I have authenticated with Google Cloud Platform (GCP) and have the necessary permissions to use the hosting service's CLI and deploy resources (e.g., Cloud Run services).
- As a developer, I have installed the MCP Hosting Service CLI.

### CUJ-2: Listing Available Tools
- As a developer, I want to run a CLI command (`mcp-host list-tools`) to see all the available pre-integrated tools I can add to my MCP server.
- The output should clearly list tool names and brief descriptions.

### CUJ-3: Creating and Configuring a New MCP Server
- As a developer, I want to run a CLI command (`mcp-host create-server --name my-awesome-server --tools google-calendar`) to define a new MCP server.
- I can specify a unique name for my server.
- I can provide a comma-separated list of tool identifiers I want to include.
- The CLI should prompt me for any necessary configuration for the selected tools.

### CUJ-4: Deploying an MCP Server
- As a developer, after defining my server, I want to run a CLI command (`mcp-host deploy-server --name my-awesome-server`) to deploy it.
- The CLI should indicate the progress and confirm successful deployment.
- The backend service will dynamically generate the MCP server code, package it into a Docker container, and deploy it as a Google Cloud Run service.

### CUJ-5: Retrieving Server Connection Details
- As a developer, once my server is deployed, I want to run a CLI command (`mcp-host get-config --name my-awesome-server`) to retrieve the connection details.
- The output should include:
  - The unique MCP server URL (provided by Cloud Run).
  - Example Python client code snippets for connecting to the server.

### CUJ-6: Listing My Deployed Servers
- As a developer, I want to run a CLI command (`mcp-host list-my-servers`) to see all the MCP servers I have created and their status (e.g., deploying, running, error).

### CUJ-7: Deleting an MCP Server
- As a developer, I want to run a CLI command (`mcp-host delete-server --name my-awesome-server`) to tear down a deployed MCP server and its associated resources.

## Product Requirements

### Functional Requirements

#### FR-1: Tool Catalog Management (Backend)
- The service must maintain a catalog of supported MCP tools.
- Each tool definition in the catalog should include:
  - Unique identifier (e.g., `google-calendar-read`).
  - Description.
  - Reference to its implementation (Python code implementing the tool logic and MCP decorators).
  - Configuration parameters required (if any).
  - Authentication requirements (e.g., OAuth scopes, API key names).

#### FR-2: User Server Configuration Storage (Backend)
- The service must store user-defined MCP server configurations, including:
  - User identifier.
  - Server name.
  - Selected tools.
  - Tool-specific configurations/credentials (securely stored).
  - Deployment status and Cloud Run service URL.

#### FR-3: Dynamic MCP Server Generation (Backend)
- Given a user's server configuration, the service must dynamically generate a Python MCP server script.
- This script will import and initialize the `FastMCP` server and include the Python functions for the selected tools, decorated with `@mcp.tool()`.

#### FR-4: Dockerization and Deployment (Backend)
- The service must package the generated MCP server script into a standardized Docker image.
- The service must be able to deploy this Docker image as a new, unique Google Cloud Run service.
- Each user server should run as an isolated Cloud Run service.

#### FR-5: Credential Management for Tools (Backend)
- The service must provide a mechanism for users to supply credentials/tokens needed by tools (e.g., API keys, OAuth tokens).
- These credentials must be securely stored (e.g., using GCP Secret Manager) and made available to the corresponding Cloud Run service environment.
- *MVP Simplification:* Initially, this might rely on users manually providing tokens that are then configured as environment variables for the Cloud Run service.

#### FR-6: CLI Interface
- The CLI must support all actions defined in the User Stories (list tools, create server, deploy, get config, list servers, delete server).
- The CLI will interact with the backend API of the MCP Hosting Service.

### Non-Functional Requirements

#### NFR-3: Reliability
- The deployed MCP servers should be reliable. Cloud Run provides good uptime.
- The hosting service itself should be reliable.

#### NFR-4: Maintainability
- The codebase for the backend service and tool implementations should be well-structured and maintainable.

#### NFR-5: Usability (CLI)
- The CLI should be intuitive and provide clear feedback to the user.

## Technical Approach (High-Level)

- **Backend Service:** Python (e.g., FastAPI/Flask) running on Google Cloud Run or App Engine. This service will expose a REST API for the CLI.
- **MCP Server Implementation:** Python, using the `fastmcp` library as per the [MCP Server Quickstart](https://modelcontextprotocol.io/quickstart/server).
- **Tool Implementations:** Each supported tool (e.g., Google Calendar integration) will be a Python module with functions that interact with the respective third-party API and are decorated for MCP.
- **Dynamic Server Generation:** The backend will have templates for `weather.py`-like server files and will populate them with imports and tool functions based on user selection.
- **Containerization:** Docker. A base Dockerfile for Python MCP servers will be used.
- **Deployment Platform:** Google Cloud Run for hosting the dynamically generated user MCP servers.
- **CLI:** Python (e.g., using Click or Typer).

## Out of Scope (for this CLI-Focused MVP)

- **Web-based User Interface:** All interactions are via CLI.
- **User Interface for OAuth Flows:** For tools requiring OAuth, MVP might assume users pre-configure tokens or provide them directly. A guided OAuth flow via the service is out of scope for MVP.
- **Advanced User Management:** Beyond GCP identity.
- **Billing and Quotas:** Users will incur GCP costs directly for their Cloud Run services. No integrated billing within the hosting service itself.
- **Custom User-Provided Tool Code:** Users can only select from a pre-defined list of tools.
- **Advanced Monitoring/Logging Dashboard:** Users will rely on GCP Cloud Logging for their server instances.
- **Complex Tool Dependency Management within the service:** Each tool is assumed to be relatively self-contained or its dependencies managed within the base MCP server Docker image.

## Future Considerations

- Web UI for all user interactions.
- Integrated OAuth flow for easy tool authorization.
- Expanded catalog of pre-built tools.
- Allowing users to provide/upload their own MCP tool code.
- Marketplace for community-contributed tools.
- Built-in monitoring and analytics for MCP server usage.
- Tiered pricing and service plans.

## Success Metrics (MVP)

- Number of unique users deploying at least one MCP server.
- Total number of MCP servers successfully deployed.
- Successful completion rate of CUJs (create, deploy, get-config).
- Qualitative feedback from early adopters on CLI usability and service reliability.
- Time taken for a new user to successfully deploy and connect to an MCP server. 