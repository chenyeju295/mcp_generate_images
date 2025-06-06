# Generated by https://smithery.ai. See: https://smithery.ai/docs/config#dockerfile
FROM python:3.10-slim

WORKDIR /app

# Copy repository files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir fastmcp requests

# Expose any required port if necessary; note: this MCP uses stdio communication

# Set the entrypoint command to run the MCP server
ENTRYPOINT ["python", "mcp_server.py"]
