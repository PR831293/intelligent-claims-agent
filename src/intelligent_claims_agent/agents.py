from __future__ import annotations

from dataclasses import dataclass

from .models import WorkflowState
from .policy import (
    detect_high_risk_content,
    detect_instruction_injection,
    missing_required_documents,
    redact_pii,
    validate_claim_basics,
)


@dataclass(frozen=True)
class AgentContext:
    name: str
    capabilities: set[str]


def _require(context: AgentContext, capability: str) -> None:
    if capability not in context.capabilities:
        raise PermissionError(f"Agent '{context.name}' lacks capability '{capability}'")


def intake_agent(state: WorkflowState, context: AgentContext) -> list[str]:
    _require(context, "register_case")
    _require(context, "validate_claim")

    notes: list[str] = []
    errors = validate_claim_basics(state.claim)
    if errors:
        notes.extend([f"validation_error: {error}" for error in errors])
        return notes

    state.audit_notes.append("intake completed")
    notes.append("claim registered and validated")
    return notes


def documents_agent(state: WorkflowState, context: AgentContext) -> list[str]:
    _require(context, "read_documents")
    _require(context, "extract_fields")

    notes: list[str] = []
    missing = missing_required_documents(state.claim)
    state.missing_documents = missing
    if missing:
        notes.append(f"missing_documents: {', '.join(missing)}")
        return notes

    injection_flags = detect_instruction_injection(state.claim.documents)
    if injection_flags:
        state.extracted_facts["injection_flags"] = injection_flags
        notes.append("instruction-like content detected and blocked")
        return notes

    high_risk_flags = detect_high_risk_content(state.claim.documents)
    if high_risk_flags:
        state.extracted_facts["high_risk_flags"] = high_risk_flags
        notes.append("high-risk content detected; escalate to manual review")

    combined = "\n".join(f"{doc.name}: {doc.content}" for doc in state.claim.documents)
    state.extracted_facts = {
        "document_count": len(state.claim.documents),
        "raw_excerpt": redact_pii(combined[:700]),
        **({"high_risk_flags": high_risk_flags} if high_risk_flags else {}),
    }
    notes.append("documents processed and pii redacted")
    return notes


def summary_agent(state: WorkflowState, context: AgentContext) -> list[str]:
    _require(context, "generate_summary")

    notes: list[str] = []
    if state.extracted_facts.get("injection_flags"):
        notes.append("summary skipped due to injection risk")
        return notes

    state.summary = (
        f"Claim {state.claim.claim_id} for member {state.claim.member_id} "
        f"type={state.claim.claim_type} amount={state.claim.amount:.2f}. "
        f"Evidence count={state.extracted_facts.get('document_count', 0)}. "
        "No settlement decision made by AI; prepared for human review."
    )
    notes.append("grounded summary prepared")
    return notes


def routing_agent(state: WorkflowState, context: AgentContext) -> list[str]:
    _require(context, "fetch_policy")
    _require(context, "route_case")

    notes: list[str] = []
    amount = state.claim.amount
    if amount >= 5000:
        state.route = "senior_adjuster"
        state.sla_due_hours = 4
    else:
        state.route = "standard_adjuster"
        state.sla_due_hours = 12

    if state.extracted_facts.get("injection_flags"):
        state.route = "manual_review"
        state.sla_due_hours = 2

    if state.extracted_facts.get("high_risk_flags"):
        state.route = "manual_review"
        state.sla_due_hours = min(state.sla_due_hours, 2) if state.sla_due_hours else 2

    notes.append(f"routed to {state.route} with sla={state.sla_due_hours}h")
    return notes


def sla_agent(state: WorkflowState, context: AgentContext) -> list[str]:
    _require(context, "schedule_sla")
    _require(context, "send_notification")

    state.audit_notes.append(f"sla scheduled for {state.sla_due_hours}h")
    return ["sla scheduled and notifications prepared"]
