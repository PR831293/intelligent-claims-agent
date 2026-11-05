# Demo Day Talk Track: Intelligent Claims Agent

## 1) 30-Second Opening

Today I am presenting a governed claims-processing system built with FastAPI, Streamlit, LangGraph, LangChain, and MCP.

The key principle is simple: AI prepares analysis, humans make final decisions.

Our system reduces manual work in intake, document review, routing, and SLA management while preserving compliance through audit trails, pause/resume checkpoints, and human approvals.

## 2) Problem Framing (What pain are we solving?)

Claims teams face five operational issues:

- Intake is manual and slow.
- Document review is repetitive and error-prone.
- Data is scattered across policy, case, and document contexts.
- Routing and approvals introduce queue delays.
- Visibility is poor for both operations and customers.

This solution addresses those issues through orchestration plus governed tool access.

## 3) Architecture Walkthrough (What did we build?)

I usually explain architecture in four layers:

1. Experience layer:
- Streamlit UI for claim submission, status, timeline, and approvals.

2. Application layer:
- FastAPI endpoints expose stable operations: start claim, resume, decision, trace.

3. Orchestration layer:
- Workflow engine executes intake -> documents -> summary -> routing -> SLA -> human review.
- Workflow pauses when data is missing or risk flags are detected.

4. Domain service layer:
- MCP servers provide controlled access to case, policy, documents, and workflow actions.
- All write operations produce auditable records.

## 4) Why this Design (Reasoning you can say out loud)

- API boundary keeps UI and orchestration decoupled.
- MCP boundaries enforce least privilege and tool contracts.
- Checkpoints make long-running claims durable and resumable.
- Human decision gate preserves compliance and accountability.
- Audit logs make all actions inspectable and replayable.

## 5) Database Explanation (Simple and confident)

This project supports SQLite for local development and PostgreSQL for containerized multi-service use.

Core workflow tables:

- workflow_checkpoints: latest workflow snapshot per run.
- workflow_events: append-only event timeline per run.

Capstone MCP tables:

- cap_claims: case master record and summary.
- cap_documents: per-case documents and extracted fields.
- cap_policies: coverage and wording source.
- cap_staff: adjusters/approvers with workload and limits.
- cap_audit_log: append-only before/after mutation records.

The model is intentionally append-heavy for traceability and operational replay.

## 6) Live Demo Flow (Suggested)

## Step 1: Start from business perspective

Say:

We submit a claim with documents and watch the system process intake, document checks, and routing, then pause for human decision.

## Step 2: Show happy path

- Submit a clean claim.
- Show state transitions in UI.
- Show summary and assigned approver.
- Show pause at human review.

Say:

At this point the AI has prepared recommendation context, but cannot finalize the claim.

## Step 3: Show exception path

- Submit missing-document or injection scenario.
- Show pause in awaiting documents or manual review flow.

Say:

This demonstrates governed interruption. The system stops safely, requests missing input, and resumes when conditions are met.

## Step 4: Show auditability

- Open trace/timeline.
- Highlight event sequence and decision record.

Say:

Every step is visible and replayable, which is important for compliance and root-cause analysis.

## Step 5: Human decision

- Approve or reject with rationale.
- Show final state update.

Say:

Final authority is always human-controlled.

## 7) Technical Deep Answers (Panel Q&A)

## Q: Why API when Streamlit could call service directly?

A: API gives a stable contract, validation layer, security boundary, and reuse by other clients. It also decouples release cycles between UI and backend.

## Q: Why MCP instead of direct DB access from agents?

A: MCP constrains tool access by schema and role, enables inspectable calls, and improves governance. It prevents uncontrolled agent behavior and supports safer composition.

## Q: How do you handle crashes and long waits?

A: State snapshots are persisted in checkpoints, events are append-only, and workflow can resume from last valid state.

## Q: How do you prevent prompt injection from documents?

A: Document text is treated as untrusted input. Instruction-like content is flagged and escalated instead of executed.

## Q: Where is compliance enforced?

A: Through human-only final decision, audit logs, explicit workflow status transitions, and least-privilege tool use.

## Q: How do you choose approvers?

A: Routing checks staff approval limits and workload, then requests approval only from eligible approvers.

## Q: What would you improve next for production?

A: Add full RBAC and OIDC for API, FK constraints/indexes, idempotency keys, stronger observability, and CI metric gates.

## 8) “If they go very deep” answers

## On scaling

- Horizontally scale API and MCP servers.
- Move from local SQLite to PostgreSQL cluster.
- Add queueing for heavy document workloads.

## On data consistency

- Introduce explicit DB foreign keys and transactional boundaries across tool calls.
- Add retry/backoff policies and idempotency for mutation endpoints.

## On model governance

- Keep small models for bounded tasks.
- Reserve stronger models for summary/risk reasoning.
- Maintain evaluation thresholds and block regressions in CI.

## 9) 60-Second Closing Script

We built a governed, auditable, human-in-the-loop claims system.

Architecturally, we separated concerns across UI, API, orchestration, and MCP domain services. Operationally, we made long-running cases durable with checkpointing and traceable with append-only events. From a compliance standpoint, AI never finalizes claims; humans do.

The result is a practical foundation that improves speed and visibility without sacrificing control, safety, or explainability.

## 10) Personal Delivery Tips

- Speak in business outcomes first, then technical depth.
- Use one concrete run to explain full flow.
- Keep repeating the governance principle: agents prepare, humans decide.
- When asked “why this choice,” answer with control, traceability, and maintainability.
- End every answer with measurable impact: cycle time, quality, transparency, risk control.
