# FDE Capstone Upgrade Plan

## Current Status

This repository is a working governed workflow prototype with FastAPI, persistence, audit events, pause/resume, and human decision controls. It is not yet fully aligned with the full FDE capstone architecture (LangGraph + MCP server mesh + Streamlit + evaluation gate).

## Phase Plan Aligned to Capstone Tasks

### Task 1: Build MCP servers (now scaffolded)

Implemented scaffolding under src/capstone_mcp:
- case_mcp.py
- policy_mcp.py
- documents_mcp.py
- workflow_mcp.py
- common.py

What is already present:
- FastMCP server setup
- Required tool names from capstone statement
- Required resource URI patterns
- Required prompt names
- SQLite/PostgreSQL-compatible table setup

What still remains for Task 1 completion:
- Replace placeholder document extraction with Docling OCR + confidence
- Replace simple policy wording search with pgvector semantic search
- Add complete domain validation and richer tool error schemas
- Add transport setup for streamable-http between containers
- Add MCP Inspector validation checklist for each tool/resource/prompt

### Task 2: Build specialist agents with LangChain

Planned:
- Add LangChain create_agent wrappers for each specialist
- Enforce strict per-agent MCP tool allowlists
- Add PII middleware + tool retry + tool call limits
- Move prompt templates to MCP prompt resources only

### Task 3: Orchestrate with LangGraph

Planned:
- Create ClaimState model for orchestration state
- Implement supervisor node with typed route output
- Add guard checks for valid transitions
- Add Send fan-out for per-document processing
- Add interrupt nodes for human review and await-documents
- Use PostgresSaver checkpointer keyed by case_id

### Task 4: Build Streamlit workspace

Planned:
- Claim intake page
- Queue page
- Case workspace with timeline + live progress
- Approval page (resume with human decision)
- Optional supervisor chat panel grounded on MCP resources

### Task 5: Governance, observability, audit

Planned:
- Append-only action log with actor and before/after state snapshots
- Trace propagation to observability backend (Phoenix)
- SLA breach simulation + notification evidence
- Explicit injection and PII assertions in run output

### Task 6: Evaluation gate

Planned:
- Add golden dataset runner
- Add deterministic metrics and judge-based metrics
- Add threshold assertions and release gate script
- Integrate into CI workflow

## Suggested Execution Order

1. Finalize MCP tools/resources/prompts behavior and schemas
2. Build LangChain specialists against MCP only
3. Add LangGraph supervisor and durable state
4. Layer Streamlit UI and human approval actions
5. Add evaluation harness and CI gate

## Immediate Next Coding Steps

1. Add a scripts/run_mcp_servers.py launcher and streamable-http mode per server
2. Add a minimal docker-compose file for postgres + app + mcp servers
3. Add first LangGraph skeleton with supervisor and one specialist transition
