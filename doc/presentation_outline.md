# Presentation Outline

## 1. Problem and Goal

- Claims handling needs speed, consistency, and auditability.
- Final disposition must remain under human control.
- Goal: demonstrate governed multi-agent orchestration with replayable state.

## 2. Solution Architecture

- FastAPI backend for workflow operations.
- Streamlit UI for guided interactive demo.
- Workflow state machine with pause/resume checkpoints.
- MCP services for bounded tool capabilities.
- SQLite/PostgreSQL persistence and audit log.

## 3. Key Design Choices

- Human-in-the-loop decision gate is mandatory for terminal decisions.
- Untrusted evidence policy (prompt injection detection + safe routing).
- PII redaction before summary exposure.
- Event-first observability for replay and explainability.

## 4. Demonstrated Scenarios

- Clean path end-to-end approval.
- Missing document pause/resume.
- Injection-safe escalation.
- High-risk request-info decision.

## 5. Results and Metrics

- task_success: 75.0%
- summary_completeness: 50.0%
- human_control_compliance: 100.0%
- injection_resistance: 100.0%
- pii_leakage_count: 0

## 6. Limitations

- Demo-grade rule patterns rather than production ML classifiers.
- Limited synthetic datasets.
- Current UI focuses on workflow control and trace, not enterprise ops features.

## 7. Next Steps

- Expand policy/routing rules with richer domain coverage.
- Add role-based access, stronger auth, and secrets management.
- Add broader regression suite and load/perf tests.
- Introduce production deployment manifests and monitoring dashboards.
