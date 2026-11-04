# Intelligent Claims Agent Architecture

This document provides a one-page architecture view for the project deliverable.

## High-Level Diagram

```mermaid
flowchart LR
  User[Operator / Demo User]
  UI[Streamlit UI]
  API[FastAPI Service]
  Orchestrator[ClaimWorkflowService]
  Policy[Policy and Redaction]
  Eval[Evaluation Metrics]

  subgraph MCP_Plane[MCP Tooling Plane]
    CaseMCP[case-mcp]
    PolicyMCP[policy-mcp]
    DocsMCP[documents-mcp]
    WorkflowMCP[workflow-mcp]
  end

  subgraph Data[Persistence]
    DB[(PostgreSQL or SQLite)]
    C1[workflow_checkpoints]
    C2[workflow_events]
    C3[cap_claims]
    C4[cap_documents]
    C5[cap_policies]
    C6[cap_staff]
    C7[cap_audit_log]
  end

  User --> UI
  UI --> API
  API --> Orchestrator
  Orchestrator --> Policy
  Orchestrator --> Eval
  Orchestrator --> DB

  CaseMCP --> DB
  PolicyMCP --> DB
  DocsMCP --> DB
  WorkflowMCP --> DB

  DB --- C1
  DB --- C2
  DB --- C3
  DB --- C4
  DB --- C5
  DB --- C6
  DB --- C7
```

## Runtime Notes

- UI is optional but recommended for demos.
- API enforces a human decision gate for final claim disposition.
- Workflow checkpointing enables pause and resume.
- Event logging provides replay and auditability.
- MCP services expose bounded capabilities over shared data.

## Security and Governance Controls

- Evidence is treated as untrusted input.
- Injection patterns are flagged and routed to manual review.
- PII is redacted in summaries and traces where applicable.
- Human decision endpoint can be protected with API key.
