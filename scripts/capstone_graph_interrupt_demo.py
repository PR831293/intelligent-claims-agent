from __future__ import annotations

import argparse
import asyncio
import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import suppress
from datetime import datetime
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.types import Command

from capstone_graph.workflow import CapstoneSupervisorWorkflow, MCPToolbox

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


def extract_interrupt_payload(result: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = result.get("__interrupt__")
    if not isinstance(interrupts, list) or not interrupts:
        return None

    first = interrupts[0]
    payload = getattr(first, "value", None)
    if isinstance(payload, dict):
        return payload
    if isinstance(first, dict) and isinstance(first.get("value"), dict):
        return first["value"]
    return None


def run_case_with_interrupts(graph, case_input: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    config = {"configurable": {"thread_id": case_input["case_id"]}}
    pending_input: Any = case_input
    handled_interrupts: list[str] = []

    while True:
        result = graph.invoke(pending_input, config=config)
        payload = extract_interrupt_payload(result)
        if not payload:
            return result, handled_interrupts

        interrupt_type = str(payload.get("type", "unknown"))
        handled_interrupts.append(interrupt_type)

        if interrupt_type == "await_documents":
            resume_payload = {
                "documents": [
                    {
                        "name": "doctor_note",
                        "content": "Uploaded after interrupt resume.",
                    }
                ]
            }
        elif interrupt_type == "human_review":
            resume_payload = {
                "decision": "approve",
                "notes": "Approved by reviewer in interrupt demo.",
            }
        else:
            resume_payload = {"decision": "request_info", "notes": "Unhandled interrupt type."}

        pending_input = Command(resume=resume_payload)


async def load_tools(connections: dict[str, dict[str, str]]):
    client = MultiServerMCPClient(connections)
    return await client.get_tools()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run capstone LangGraph interrupt/resume demo")
    parser.add_argument("--scenario", choices=["clean", "missing"], default="clean")
    args = parser.parse_args()

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

        connections = {
            "case": {"transport": "streamable_http", "url": "http://127.0.0.1:8101/mcp"},
            "policy": {"transport": "streamable_http", "url": "http://127.0.0.1:8102/mcp"},
            "documents": {"transport": "streamable_http", "url": "http://127.0.0.1:8103/mcp"},
            "workflow": {"transport": "streamable_http", "url": "http://127.0.0.1:8104/mcp"},
        }

        tools = asyncio.run(load_tools(connections))
        toolbox = MCPToolbox({tool.name: tool for tool in tools})
        workflow = CapstoneSupervisorWorkflow(toolbox)
        graph = workflow.build()

        suffix = datetime.utcnow().strftime("%H%M%S")

        if args.scenario == "clean":
            case_input = {
                "case_id": f"CLM-GRAPH-INT-CLEAN-{suffix}",
                "policy_number": "POL-1001",
                "amount": 400.0,
                "claim_type": "medical",
                "documents": [
                    {"name": "claim_form", "content": "Submitted by member."},
                    {"name": "invoice", "content": "Billed amount 400."},
                    {"name": "doctor_note", "content": "Treatment required."},
                ],
                "status": "new",
                "use_interrupts": True,
            }
        else:
            case_input = {
                "case_id": f"CLM-GRAPH-INT-MISS-{suffix}",
                "policy_number": "POL-1001",
                "amount": 950.0,
                "claim_type": "medical",
                "documents": [
                    {"name": "claim_form", "content": "Follow-up reimbursement request."},
                    {"name": "invoice", "content": "Total billed amount USD 950."},
                ],
                "status": "new",
                "use_interrupts": True,
            }

        final_state, handled_interrupts = run_case_with_interrupts(graph, case_input)
        print(f"[{args.scenario}] handled_interrupts={','.join(handled_interrupts) if handled_interrupts else 'none'}")
        print(f"[{args.scenario}] final status={final_state.get('status')}")
        print(f"[{args.scenario}] assigned_adjuster={final_state.get('assigned_adjuster')}")
        print(f"[{args.scenario}] assigned_approver={final_state.get('assigned_approver')}")
        print(f"[{args.scenario}] decision={final_state.get('human_decision')}")
        print(f"[{args.scenario}] error={final_state.get('error')}")

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


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        import traceback

        traceback.print_exc()
        print(f"Graph interrupt demo failed: {exc}")
        sys.exit(1)
