from __future__ import annotations

import asyncio
import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import suppress

from langchain_mcp_adapters.client import MultiServerMCPClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = os.path.join(ROOT, ".venv", "bin", "python")


def wait_for_port(port: int, timeout_seconds: int = 20) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.25)
    raise TimeoutError(f"Port {port} did not open within {timeout_seconds}s")


def start_server(name: str, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env["MCP_PORT"] = str(port)
    return subprocess.Popen(
        [PYTHON, "scripts/run_mcp_server.py", name, "--transport", "streamable-http"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


async def verify_calls() -> None:
    connections = {
        "case": {"transport": "streamable_http", "url": "http://127.0.0.1:8101/mcp"},
        "policy": {"transport": "streamable_http", "url": "http://127.0.0.1:8102/mcp"},
        "documents": {"transport": "streamable_http", "url": "http://127.0.0.1:8103/mcp"},
        "workflow": {"transport": "streamable_http", "url": "http://127.0.0.1:8104/mcp"},
    }

    client = MultiServerMCPClient(connections)
    tools = await client.get_tools()
    names = {tool.name for tool in tools}

    required = {
        "register_case",
        "get_policy",
        "upsert_document",
        "validate_case_documents",
        "request_approval",
        "send_notification",
    }
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(f"Missing expected tools: {missing}")

    by_name = {tool.name: tool for tool in tools}

    await by_name["register_case"].ainvoke(
        {
            "case_id": "CLM-SMOKE-1",
            "policy_number": "POL-1001",
            "amount": 300.0,
        }
    )
    await by_name["upsert_document"].ainvoke(
        {
            "case_id": "CLM-SMOKE-1",
            "doc_id": "claim_form",
            "doc_type": "claim_form",
            "content": "Claim form for smoke test",
        }
    )
    await by_name["validate_case_documents"].ainvoke(
        {
            "case_id": "CLM-SMOKE-1",
            "required_docs": ["claim_form", "invoice"],
        }
    )


def main() -> None:
    servers = [
        ("case", 8101),
        ("policy", 8102),
        ("documents", 8103),
        ("workflow", 8104),
    ]
    processes: list[subprocess.Popen] = []

    try:
        for name, port in servers:
            proc = start_server(name, port)
            processes.append(proc)
            wait_for_port(port)

        asyncio.run(verify_calls())
        print("MCP integration smoke test passed")
    finally:
        for proc in processes:
            if proc.poll() is None:
                with suppress(ProcessLookupError):
                    proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    with suppress(ProcessLookupError):
                        proc.kill()

        # Print last log lines for debugging context.
        for proc in processes:
            if proc.stdout is None:
                continue
            lines = proc.stdout.read().splitlines()
            tail = lines[-4:]
            if tail:
                print("\n" + "=" * 40)
                print("server log tail:")
                for line in tail:
                    print(line)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        print(f"MCP integration smoke test failed: {exc}")
        sys.exit(1)
