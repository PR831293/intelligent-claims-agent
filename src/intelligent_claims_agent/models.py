from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class WorkflowStatus(str, Enum):
    RUNNING = "running"
    AWAITING_DOCUMENTS = "awaiting_documents"
    AWAITING_HUMAN_DECISION = "awaiting_human_decision"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class HumanDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_INFO = "request_info"


@dataclass
class Document:
    name: str
    content: str


@dataclass
class ClaimInput:
    claim_id: str
    member_id: str
    claim_type: str
    amount: float
    documents: list[Document]


@dataclass
class WorkflowState:
    run_id: str
    status: WorkflowStatus
    current_step: str
    claim: ClaimInput
    missing_documents: list[str] = field(default_factory=list)
    extracted_facts: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    route: str = ""
    sla_due_hours: int = 0
    audit_notes: list[str] = field(default_factory=list)
    human_decision: HumanDecision | None = None
    decision_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["current_step"] = self.current_step
        if self.human_decision is not None:
            data["human_decision"] = self.human_decision.value
        return data

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WorkflowState":
        claim_raw = raw["claim"]
        claim = ClaimInput(
            claim_id=claim_raw["claim_id"],
            member_id=claim_raw["member_id"],
            claim_type=claim_raw["claim_type"],
            amount=claim_raw["amount"],
            documents=[Document(**doc) for doc in claim_raw.get("documents", [])],
        )
        human_decision = raw.get("human_decision")
        return cls(
            run_id=raw["run_id"],
            status=WorkflowStatus(raw["status"]),
            current_step=raw["current_step"],
            claim=claim,
            missing_documents=list(raw.get("missing_documents", [])),
            extracted_facts=dict(raw.get("extracted_facts", {})),
            summary=raw.get("summary", ""),
            route=raw.get("route", ""),
            sla_due_hours=raw.get("sla_due_hours", 0),
            audit_notes=list(raw.get("audit_notes", [])),
            human_decision=HumanDecision(human_decision) if human_decision else None,
            decision_notes=raw.get("decision_notes", ""),
        )


@dataclass
class AuditEvent:
    run_id: str
    step: str
    event_type: str
    message: str
    payload: dict[str, Any] = field(default_factory=dict)
