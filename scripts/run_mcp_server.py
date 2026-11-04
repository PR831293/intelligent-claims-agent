from __future__ import annotations

import argparse
import importlib

SERVER_MODULES = {
    "case": "capstone_mcp.case_mcp",
    "policy": "capstone_mcp.policy_mcp",
    "documents": "capstone_mcp.documents_mcp",
    "workflow": "capstone_mcp.workflow_mcp",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a capstone FastMCP server")
    parser.add_argument("server", choices=sorted(SERVER_MODULES.keys()))
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    args = parser.parse_args()

    module = importlib.import_module(SERVER_MODULES[args.server])
    module.ensure_capstone_tables()
    if hasattr(module, "seed_reference_data"):
        module.seed_reference_data()
    module.mcp.run(args.transport)


if __name__ == "__main__":
    main()
