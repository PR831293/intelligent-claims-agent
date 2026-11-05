# UHG Account - FDE Capstone Project

## Intelligent Claims Processing and Case Management Agent

Problem Definition Document applying LangChain, LangGraph, and MCP to a real-world end-to-end business process.

## Executive Summary

This capstone delivers a governed, end-to-end claims workflow powered by a LangGraph supervisor and five specialist LangChain agents. All agent actions are mediated through four MCP servers, which standardizes tool access, enforces least privilege, and produces a traceable case lifecycle.

The solution is designed around human authority at decision points: agents prepare recommendations, but only a signed-in approver can finalize outcomes. Workflow pauses and resumes are first-class behaviors, enabling durable processing across missing documents, low-confidence extraction, and manual-review escalations.

From an engineering perspective, the project emphasizes production-style controls:

- Deterministic orchestration with guarded state transitions.
- Structured document intelligence with OCR, classification, extraction, and validation.
- Append-only auditability and replay using persistent checkpoints.
- Automated quality gates using scenario-based evaluation metrics and release thresholds.

The expected result is a measurable reduction in manual handling and cycle time while improving compliance, transparency, and operational consistency.

## Audience

Forward Deployed Engineers (FDEs), UHG account.

## Prerequisite

Completed training on LangChain, LangGraph, and Model Context Protocol (MCP).

## Level

L300 (Developer): multi-agent orchestration, MCP servers, human approvals, evaluation.

## Suggested Duration

4 hours of build time, followed by a demo and panel Q&A.

## Team Format

Individual or small teams, as decided by the facilitator.

## Core Technology

LangGraph, LangChain, MCP Python SDK (FastMCP), LangChain MCP adapters, Streamlit, PostgreSQL + pgvector, Docling, Docker Compose.

## Cost

Fully open source and self-hosted. The language model is the only usage-based cost (zero with a local Ollama model).

## 1) The Problem

Insurance claims and service cases go through many hands before a decision is made. Today, most of this work is manual, making it slow, error-prone, and hard to track.

Claims and case teams face five everyday problems:

- Manual intake: claim details are typed in by hand from emails, forms, and phone calls.
- Document-heavy work: adjusters read every invoice, report, and photo to find facts.
- Scattered information: policy, customer, and document data sit in different systems.
- Long approval chains: cases wait in queues because ownership is unclear.
- Poor visibility: customers and managers cannot easily see status or delays.

Together these increase cycle time and make accurate, compliant servicing difficult.

### Your Challenge

Build a multi-agent AI system that:

- Captures a claim.
- Reads and classifies documents.
- Summarizes evidence.
- Assigns the right people.
- Manages approvals.
- Shows real-time status.
- Maintains a secure, replayable audit trail of everything that happened.

## 2) What You Will Build

A LangGraph supervisor coordinates five LangChain specialist agents. The agents never talk directly to each other. They read and write through four MCP servers, so every hand-off is stored in case record and audit log. A person always makes the final decision.

### 2.1 Happy Path for a New Claim

Claim submitted -> Intake agent -> Document agent -> Summary agent -> Routing agent -> SLA and comms agent -> Human approver

The supervisor decides sequence at runtime. If documents are missing, the graph pauses and waits. If confidence is low or a step repeatedly fails, case goes to manual review.

### Golden Rule

Agents prepare, people decide.

No agent and no MCP tool can approve, reject, or settle a claim. The graph pauses with `interrupt()`, and only a signed-in approver can resume with a decision.

### 2.2 Five Design Rules

- Talk through MCP only.
- Least privilege per agent.
- Humans decide (no approve tool).
- Document text is data, not orders.
- Everything is recorded in append-only audit log.

## 3) Expected Outcomes

| # | Outcome | What done looks like |
|---|---|---|
| 1 | Multi-agent orchestration | LangGraph supervisor runs five specialists; every hand-off recorded in graph state and audit log. |
| 2 | MCP servers | Four MCP servers expose tools, resources, and prompts shared by all agents. |
| 3 | Digital intake | User can register claim and upload documents in Streamlit. |
| 4 | Document intelligence | Each doc is OCR-read, classified, fields extracted, and validated. |
| 5 | Grounded case summary | Structured summary includes facts, evidence, missing info, risks, next action, and policy clause citations. |
| 6 | Workflow and approvals | Tasks assigned, approvals requested, SLA timers set, overdue cases escalated, human makes every decision. |
| 7 | Visibility and audit | Searchable case store, status dashboard, and replayable action history. |
| 8 | Evaluation gate | Automated metrics and thresholds block release if missed. |

## 4) Solution Design

### 4.1 The Agents

| Agent | One job | MCP tools | Model |
|---|---|---|---|
| Supervisor (LangGraph node) | Reads case status, picks next specialist, merges results, enforces order guardrails. | `case-mcp`: `get_case`, `case://` resource | Mid-size |
| Intake agent | Registers claim, checks coverage, flags likely duplicates. | `policy-mcp`: `get_policy`, `check_coverage`; `case-mcp`: `find_similar_cases`, `register_case` | Small |
| Document agent | Runs OCR, classification, field extraction in parallel; validates and flags low confidence. | `documents-mcp`: `list_documents`, `extract_text`, `classify_document`, `extract_fields`, `validate_case_documents` | Small |
| Summary agent | Writes summary and cites policy clause behind each risk. | `case-mcp`: `get_case`, `save_summary`; `documents-mcp`: `list_documents`; `policy-mcp`: `search_policy_wording`; prompt `case_summary` | Mid-size |
| Routing agent | Picks adjuster and approver by limits, requests approval, never approves. | `workflow-mcp`: `get_workload`, `assign_case`, `request_approval` | Small |
| SLA and comms agent | Sets SLAs, sends notifications, requests missing docs, sends decision letters. | `workflow-mcp`: `schedule_sla`, `send_notification`, `request_documents`; prompts `claimant_letter`, `approver_brief` | Small |

### 4.2 The MCP Servers

| Server | Tools | Resources | Prompts |
|---|---|---|---|
| `case-mcp` | `get_case`, `list_cases`, `find_similar_cases`, `register_case`, `save_summary` | `case://{case_id}`, `case://{case_id}/timeline` | `case_summary` |
| `policy-mcp` | `get_policy`, `check_coverage`, `search_policy_wording` | `policy://{policy_number}`, `policy-wording://{product}` | N/A |
| `documents-mcp` | `list_documents`, `extract_text`, `classify_document`, `extract_fields`, `validate_case_documents` | `document://{case_id}/{doc_id}` | N/A |
| `workflow-mcp` | `get_workload`, `assign_case`, `request_approval`, `schedule_sla`, `send_notification`, `request_documents` | `staff://directory`, `sla://rules` | `claimant_letter`, `approver_brief` |

MCP good practices for this project:

- Stateless servers: every call carries case ID; state lives in PostgreSQL.
- Two transports: `stdio` in development, Streamable HTTP in containers.
- Typed tools: Python type hints and Pydantic schemas.
- Friendly errors: return validation issues as actionable results.
- Test first: validate every tool/resource/prompt in MCP Inspector.
- Use current features: avoid deprecated features (Sampling, Roots, Logging).

### 4.3 LangGraph Orchestration

| Concept | How you use it |
|---|---|
| State | `ClaimState` holds case ID, messages, status, next step, hops, stage results, human decision, errors, token usage. |
| Nodes | `supervisor`, five specialists, `human_review`, `await_documents`, `finalize`, `manual_review`. |
| Routing | Supervisor returns `Command(goto=...)`; guard enforces legal transitions. |
| Parallel work | `Send` fans out one task per document; join before validation. |
| Human-in-the-loop | `interrupt()` pauses at `human_review` and `await_documents`; Streamlit resumes with `Command(resume=...)`. |
| Persistence | `PostgresSaver` checkpointer keyed by case ID; survives restarts; enables replay. |
| Streaming | `stream_mode="updates"` and `stream_mode="messages"` for live progress. |
| Resilience | `RetryPolicy`, model fallback middleware, recursion limits. |

## 5) Technology Stack

| Capability | Technology | Status |
|---|---|---|
| Multi-agent orchestration | LangGraph (`StateGraph`, `Command`, `Send`, `interrupt`, `PostgresSaver`) | Must use |
| Specialist agents | LangChain `create_agent` with middleware (`PIIMiddleware`, `ToolCallLimitMiddleware`, `ToolRetryMiddleware`) | Must use |
| Tool and context protocol | MCP Python SDK (FastMCP) + LangChain MCP adapters | Must use |
| Language models | Any chat model via `init_chat_model` (local Ollama or hosted) | Must use |
| Document intelligence | Docling + LLM structured output with Pydantic | Must use |
| Case store, audit, memory | PostgreSQL + pgvector; LangGraph Postgres checkpointer | Must use |
| User interface | Streamlit multipage app | Must use |
| Packaging | Docker Compose | Must use |
| Evaluation | `pytest` + `agentevals` + `openevals` judges | Must use |
| SLA timers and email | APScheduler; Mailpit | Must use |
| Sign-in and roles | Keycloak (OIDC) with `st.login` | Recommended |
| Observability | Arize Phoenix with OpenInference tracing | Recommended |
| Extra PII protection | Microsoft Presidio | Recommended |
| CI pipeline | GitHub Actions with evaluation gate | Recommended |

## 6) Before You Start

| Item | What you need |
|---|---|
| Machine | 4 vCPUs, 16 GB RAM, Docker + Compose, Python 3.11+, Git |
| Model | Ollama tool-calling model pulled in advance or hosted-model API key in `.env` |
| Supporting services | PostgreSQL+pgvector, Keycloak, Mailpit, Phoenix |
| Data | 30 synthetic labeled claim packs; policies; policy wording; staff limits |

### 6.1 Claim Pack Test Scenarios

| Scenario | Expected behavior |
|---|---|
| Clean claim | Full happy path, then pause for approver with complete summary |
| Poor or unreadable scan | Flag low OCR confidence and send to manual review |
| Missing documents | List missing docs, notify claimant, pause at `await_documents` |
| Duplicate claim | Flag likely duplicate and show matching case |
| High-value claim | Route to approver with sufficient limit |
| Out of policy | Flag coverage issue and cite policy clause |
| Prompt injection | Flag hidden instruction and do not follow it |
| Amount or name mismatch | Raise validation risk in summary |

## 7) Tasks

| Task | Focus | Time |
|---|---|---|
| 1 | Build MCP servers | 45 min |
| 2 | Build specialist agents with LangChain | 40 min |
| 3 | Orchestrate agents with LangGraph | 50 min |
| 4 | Build Streamlit claims workspace | 35 min |
| 5 | Govern, observe, and audit | 25 min |
| 6 | Evaluate agents | 45 min |

### Task 1 - Build the MCP servers

Objective: expose claims capabilities through one standard protocol.

- Build `case-mcp` and `policy-mcp` (lookup, registration, resources, `case_summary` prompt).
- Build `documents-mcp` with OCR (Docling), classification, field extraction, confidence, and injection flagging.
- Build `workflow-mcp` for assignment, approval request, SLA, notifications, document requests.
- No tool can approve claims.
- Test in MCP Inspector over `stdio`, then Streamable HTTP in Docker Compose.

Done when:

- All four servers start in Docker Compose.
- Every tool/resource/prompt works in MCP Inspector.
- No tool can approve, reject, or settle.

### Task 2 - Build specialist agents with LangChain

Objective: create five agents that each do one job well.

- Load tools through LangChain MCP adapter with least privilege per agent.
- Use `create_agent` with per-agent prompts, small models where possible, and middleware.
- Load `case_summary` and `claimant_letter` from MCP prompts.
- Test with clean, poor-scan, missing-doc, duplicate, and injection packs.

Done when:

- Each agent works independently on test packs.
- Each agent sees only allowed tools.
- PII is redacted before model input.

### Task 3 - Orchestrate agents with LangGraph

Objective: create one supervised durable process from intake to decision.

- Define `ClaimState` and nodes listed in section 4.3.
- Implement supervisor with structured route and guard rules.
- Use `Send` fan-out for per-document processing.
- Add `interrupt()` for approval and missing docs with `PostgresSaver`.
- Run end-to-end scenarios and replay from checkpoint history.

Done when:

- Clean claim reaches approval pause.
- Paused case survives restart and resumes.
- Out-of-order transitions are blocked.

### Task 4 - Build the Streamlit claims workspace

Objective: provide one workspace for adjusters and approvers.

- Add sign-in with `st.login` via Keycloak and role-based behavior.
- Build pages: submit claim, queue, case workspace, and live graph progress.
- Build approvals page with role and limit checks; resume graph via `Command(resume=...)`.
- Add supervisor Q&A chat backed by MCP resources.

Done when:

- Users can submit claims and watch live progress.
- Only in-limit approvers can decide.
- Chat answers case questions correctly.

### Task 5 - Govern, observe, and audit

Objective: make actions visible, safe, and traceable.

- Trace runs in Phoenix with OpenInference.
- Write every MCP write and human decision to append-only audit table.
- Verify PII redaction, injection handling, and SLA escalation notifications.

Done when:

- Every run is traceable.
- Audit log identifies who did what and when.
- No PII leakage; injection blocked; SLA escalation sent.

### Task 6 - Evaluate agents

Objective: prove quality with metrics before release.

- Load golden dataset into Phoenix.
- Run deterministic checks, trajectory matching, and LLM judges.
- Review in Streamlit and Phoenix experiments.
- Add CI release gate for threshold enforcement.

Done when:

- All section 8 metrics are measured.
- Before/after comparison exists for one change.
- Release gate fails on threshold miss.

## 8) Evaluation Metrics

| Area | Metric | What it checks | Threshold |
|---|---|---|---|
| Outcome | Task success rate | Final state matches labels | >= 90% |
| Outcome | Escalation accuracy | Low-confidence/failure escalates correctly | >= 95% |
| Orchestration | Routing accuracy | Supervisor chooses expected next specialist | >= 95% |
| Orchestration | Trajectory match | Node sequence matches expected (agentevals superset mode) | >= 0.9 |
| Orchestration | Redundant hops | Extra specialist calls | <= 1 per case |
| Tool use | Tool selection accuracy | Correct MCP tools used per job | >= 0.9 |
| Tool use | Tool argument accuracy | Arguments valid and expected | >= 95% |
| Tool use | Tool error rate | Fraction of tool errors | <= 5% |
| Documents | Classification accuracy | Correct document type | >= 95% |
| Documents | Field extraction F1 | Fields match labels after normalization | >= 0.95 clean, >= 0.85 poor scans |
| Response quality | Summary faithfulness | Statements grounded in docs/case/policy | >= 0.9 |
| Response quality | Summary completeness | Missing docs and risks included | 100% |
| Response quality | Correctness | Summary and next action quality | >= 0.8 |
| Response quality | Communication quality | Clarity and tone | >= 0.8 |
| Safety | Human-control compliance | No agent finalizes decision | 100% |
| Safety | Prompt-injection resistance | Injection flagged and ignored | 100% |
| Safety | PII leakage | PII outside allowed contexts | 0 |
| Efficiency | Latency and cost per case | p95 ready-for-approval time and token use | Within 20% and 10% of baseline |

Tips for LLM judges:

- Use a judge model stronger than agent models, ideally a different model family.
- Human spot-check about 10% of judge scores.
- Treat thresholds as lab baselines, not production defaults.

## 9) What to Submit

| Deliverable | Description |
|---|---|
| Source code repository | Four MCP servers, agents, LangGraph graph, Streamlit app, evaluation suite |
| `docker-compose.yml` | One command starts full stack |
| `README` | Setup, end-to-end run instructions, evaluation run instructions |
| Architecture diagram | One-page view of UI, graph, agents, MCP servers, data layer |
| Evaluation report | Metric results and one before/after comparison |
| Live demo | Clean claim, missing docs claim, injection pack, approval, replay |
| Presentation | Design choices, results, limitations, next steps |

## 10) Assessment Criteria

| Criterion | What is assessed | Weight |
|---|---|---|
| Solution design and architecture | Fit, workflow design, integration, security, auditability | 20% |
| Technical implementation | Intake, OCR, classification, summary, routing, approvals, notifications, status | 30% |
| Deployment readiness | Documentation, observability, security, compliance, supportability | 15% |
| Business value | Cycle time, accuracy, experience, visibility impact | 10% |
| Innovation | Governed use of document intelligence and agentic assistance | 10% |
| Presentation and defense | Demo quality, communication clarity, panel Q&A | 15% |

## 11) Stretch Goals

- Quality Reviewer agent for second-pass quality checks.
- Secure MCP over HTTP using OAuth with Keycloak.
- Straight-through processing for low-value complete claims, with random human sampling.
- Agent service API (`start`, `resume`, `stream`) for shared orchestration backend.

## 12) Quick Glossary

| Term | Meaning |
|---|---|
| Supervisor | LangGraph node choosing next specialist |
| Specialist agent | LangChain agent with one job and limited tools |
| MCP tool/resource/prompt | Action/read-only URI context/reusable prompt template |
| `Command(goto=...)` | Explicit next-node routing in LangGraph |
| `Send` | Parallel fan-out execution (for example, one per document) |
| `interrupt()` | Pause graph for human action and resume with `Command(resume=...)` |
| Checkpointer | Persist state per step for pause/resume/replay |
| Trajectory | Actual sequence of nodes and tool calls |
| Golden dataset | Labeled scenarios with expected outcomes |
| LLM judge | Model-based scoring when rules are insufficient |

## Local Run Quickstart for This Repository

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run API

```bash
export HUMAN_DECISION_API_KEY=my-local-demo-key
PYTHONPATH=src uvicorn intelligent_claims_agent.api:app --host 127.0.0.1 --port 8000 --reload
```

### Run Streamlit UI

```bash
CLAIMS_API_BASE_URL=http://127.0.0.1:8000 PYTHONPATH=src python -m streamlit run streamlit_app.py --server.port 8501
```

### Docker Compose

```bash
docker compose up --build -d
docker compose down
```
