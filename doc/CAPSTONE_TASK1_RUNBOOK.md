# Capstone Task 1 Runbook (MCP Servers)

## Prerequisites

- Python virtual environment active
- Dependencies installed from requirements.txt

## Start all MCP servers locally (streamable-http)

Open 4 terminals from project root and run:

Terminal 1:
PYTHONPATH=src MCP_PORT=8101 .venv/bin/python scripts/run_mcp_server.py case --transport streamable-http

Terminal 2:
PYTHONPATH=src MCP_PORT=8102 .venv/bin/python scripts/run_mcp_server.py policy --transport streamable-http

Terminal 3:
PYTHONPATH=src MCP_PORT=8103 .venv/bin/python scripts/run_mcp_server.py documents --transport streamable-http

Terminal 4:
PYTHONPATH=src MCP_PORT=8104 .venv/bin/python scripts/run_mcp_server.py workflow --transport streamable-http

## Validate with LangChain MCP adapters

List all discovered tools:
PYTHONPATH=src .venv/bin/python scripts/langchain_mcp_tool_inventory.py

Run specialist integration smoke test:
PYTHONPATH=src .venv/bin/python scripts/langchain_mcp_specialist_demo.py

## Docker Compose option

Stack file:
- docker-compose.capstone.yml

Build image:
- Dockerfile.mcp

Command:
docker compose -f docker-compose.capstone.yml up -d

If Docker socket permissions fail, use local run mode above.
