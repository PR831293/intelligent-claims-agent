from __future__ import annotations

import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient


async def main() -> None:
    connections = {
        "case": {"transport": "streamable_http", "url": "http://127.0.0.1:8101/mcp"},
        "policy": {"transport": "streamable_http", "url": "http://127.0.0.1:8102/mcp"},
        "documents": {"transport": "streamable_http", "url": "http://127.0.0.1:8103/mcp"},
        "workflow": {"transport": "streamable_http", "url": "http://127.0.0.1:8104/mcp"},
    }
    client = MultiServerMCPClient(connections)
    tools = await client.get_tools()
    print(f"total_tools={len(tools)}")
    for tool in sorted(tools, key=lambda t: t.name):
        print(tool.name)


if __name__ == "__main__":
    asyncio.run(main())
