from __future__ import annotations

import argparse
import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient


async def main() -> None:
    parser = argparse.ArgumentParser(description="LangChain MCP adapter connectivity demo")
    parser.add_argument("--case-url", default="http://127.0.0.1:8101/mcp")
    parser.add_argument("--policy-url", default="http://127.0.0.1:8102/mcp")
    args = parser.parse_args()

    connections = {
        "case": {
            "transport": "streamable_http",
            "url": args.case_url,
        },
        "policy": {
            "transport": "streamable_http",
            "url": args.policy_url,
        },
    }

    client = MultiServerMCPClient(connections)
    tools = await client.get_tools()
    print("Loaded MCP tools:")
    for tool in tools:
        print(f"- {tool.name}")

    register_tool = next((tool for tool in tools if tool.name.endswith("register_case")), None)
    get_policy_tool = next((tool for tool in tools if tool.name.endswith("get_policy")), None)

    if register_tool:
        result = await register_tool.ainvoke(
            {
                "case_id": "CLM-LC-DEMO-1",
                "policy_number": "POL-1001",
                "amount": 450.0,
            }
        )
        print("register_case:", result)

    if get_policy_tool:
        result = await get_policy_tool.ainvoke({"policy_number": "POL-1001"})
        print("get_policy:", result)


if __name__ == "__main__":
    asyncio.run(main())
