FROM python:3.10-slim

ARG DEPLOY_DIR_ARG

WORKDIR /app

# Set PYTHONPATH to include the current WORKDIR where mcp_host will be.
ENV PYTHONPATH /app

# Copy the mcp_host library. This assumes mcp_host is at the root of the build context.
COPY mcp_host ./mcp_host

# Copy the server-specific requirements.txt from DEPLOY_DIR_ARG 
# (e.g., from deploy/my-calendar-server/requirements.txt to /app/requirements.txt)
# and install dependencies.
COPY ${DEPLOY_DIR_ARG}/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server script from DEPLOY_DIR_ARG 
# (e.g., from deploy/my-calendar-server/server.py to /app/server.py)
COPY ${DEPLOY_DIR_ARG}/server.py ./server.py

# The server.py is the entrypoint for your MCP server.
CMD ["python", "server.py"] 