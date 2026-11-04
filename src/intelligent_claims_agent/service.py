from __future__ import annotations

import uuid
from typing import Callable

from .agents import AgentContext, documents_agent, intake_agent, routing_agent, sla_agent, summary_agent
from .models import AuditEvent, ClaimInput, Document, HumanDecision, WorkflowState, WorkflowStatus
from .storage import CheckpointStore

StepHandler = Callable[[WorkflowState, AgentContext], list[str]]


class ClaimWorkflowService:
    """Governed, stateful claim workflow with pause/resume and audit logging."""

    def __init__(self, store: CheckpointStore) -> None:
        self.store = store
        self.step_order: list[tuple[str, StepHandler]] = [
            ("intake", intake_agent),
            ("documents", documents_agent),
            ("summary", summary_agent),
            ("routing", routing_agent),
            ("sla", sla_agent),
        ]
        self.capabilities: dict[str, set[str]] = {
            "intake": {"register_case", "validate_claim"},
            "documents": {"read_documents", "extract_fields"},
            "summary": {"generate_summary"},
            "routing": {"fetch_policy", "route_case"},
            "sla": {"schedule_sla", "send_notification"},
        }

    def start(self, claim: ClaimInput) -> WorkflowState:
        state = WorkflowState(
            run_id=str(uuid.uuid4()),
            status=WorkflowStatus.RUNNING,
            current_step="intake",
            claim=claim,
        )
        self._persist(state)
        return self._run_until_pause_or_end(state)

    def resume_with_documents(self, run_id: str, extra_documents: list[dict[str, str]]) -> WorkflowState:
        state = self._require_state(run_id)
        if state.status != WorkflowStatus.AWAITING_DOCUMENTS:
            raise ValueError(f"Run {run_id} is not waiting for documents")

        for doc in extra_documents:
            state.claim.documents.append(Document(**doc))

        state.missing_documents = []
        state.status = WorkflowStatus.RUNNING
        state.current_step = "documents"
        self._record(state, "system", "resume", "Documents received; resuming workflow", {"added": extra_documents})
        self._persist(state)
        return self._run_until_pause_or_end(state)

    def submit_human_decision(self, run_id: str, decision: HumanDecision, notes: str = "") -> WorkflowState:
        state = self._require_state(run_id)
        if state.status != WorkflowStatus.AWAITING_HUMAN_DECISION:
            raise ValueError(f"Run {run_id} is not waiting for human decision")

        state.human_decision = decision
        state.decision_notes = notes

        if decision == HumanDecision.APPROVE:
            state.status = WorkflowStatus.COMPLETED
            event = "claim approved by human"
        elif decision == HumanDecision.REJECT:
            state.status = WorkflowStatus.REJECTED
            event = "claim rejected by human"
        else:
            state.status = WorkflowStatus.AWAITING_DOCUMENTS
            state.current_step = "documents"
            state.missing_documents = ["human_requested_additional_evidence"]
            event = "human requested more info"

        self._record(state, "human_review", "human_decision", event, {"decision": decision.value, "notes": notes})
        self._persist(state)

        if state.status == WorkflowStatus.AWAITING_DOCUMENTS:
            return state
        return state

    def trace(self, run_id: str) -> list[dict[str, str]]:
        return self.store.list_events(run_id)

    def get_state(self, run_id: str) -> WorkflowState:
        return self._require_state(run_id)

    def _run_until_pause_or_end(self, state: WorkflowState) -> WorkflowState:
        start_index = next((i for i, item in enumerate(self.step_order) if item[0] == state.current_step), 0)
        for step_name, handler in self.step_order[start_index:]:
            state.current_step = step_name
            context = AgentContext(name=step_name, capabilities=self.capabilities[step_name])
            self._record(state, step_name, "step_started", f"{step_name} started", {})

            notes = handler(state, context)
            self._record(state, step_name, "step_completed", f"{step_name} completed", {"notes": notes})

            if step_name == "intake" and any(note.startswith("validation_error") for note in notes):
                state.status = WorkflowStatus.FAILED
                self._record(state, step_name, "failed", "Validation failed", {"errors": notes})
                self._persist(state)
                return state

            if step_name == "documents":
                if state.missing_documents:
                    state.status = WorkflowStatus.AWAITING_DOCUMENTS
                    self._record(
                        state,
                        step_name,
                        "paused",
                        "Awaiting required documents",
                        {"missing_documents": state.missing_documents},
                    )
                    self._persist(state)
                    return state
                if state.extracted_facts.get("injection_flags"):
                    state.status = WorkflowStatus.AWAITING_HUMAN_DECISION
                    state.current_step = "human_review"
                    self._record(
                        state,
                        "human_review",
                        "paused",
                        "Injection risk detected; manual review required",
                        {"flags": state.extracted_facts.get("injection_flags", [])},
                    )
                    self._persist(state)
                    return state
                if state.extracted_facts.get("high_risk_flags"):
                    state.status = WorkflowStatus.AWAITING_HUMAN_DECISION
                    state.current_step = "human_review"
                    self._record(
                        state,
                        "human_review",
                        "paused",
                        "High-risk content detected; manual review required",
                        {"flags": state.extracted_facts.get("high_risk_flags", [])},
                    )
                    self._persist(state)
                    return state

            self._persist(state)

        state.status = WorkflowStatus.AWAITING_HUMAN_DECISION
        state.current_step = "human_review"
        self._record(
            state,
            "human_review",
            "paused",
            "Prepared case for human decision",
            {"route": state.route, "sla_due_hours": state.sla_due_hours},
        )
        self._persist(state)
        return state

    def _require_state(self, run_id: str) -> WorkflowState:
        state = self.store.load_state(run_id)
        if state is None:
            raise ValueError(f"Unknown run_id: {run_id}")
        return state

    def _record(self, state: WorkflowState, step: str, event_type: str, message: str, payload: dict) -> None:
        self.store.save_event(
            AuditEvent(
                run_id=state.run_id,
                step=step,
                event_type=event_type,
                message=message,
                payload=payload,
            )
        )

    def _persist(self, state: WorkflowState) -> None:
        self.store.save_state(state)
