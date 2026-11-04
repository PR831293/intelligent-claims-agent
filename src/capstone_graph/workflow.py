from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass
from typing import Any, Literal
from typing_extensions import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

try:
    from langgraph.checkpoint.postgres import PostgresSaver
except Exception:  # pragma: no cover - optional dependency guard
    PostgresSaver = None


class ClaimState(TypedDict, total=False):
    case_id: str
    policy_number: str
    amount: float
    claim_type: str
    documents: list[dict[str, str]]
    status: str
    missing_documents: list[str]
    summary: dict[str, Any]
    coverage: dict[str, Any]
    assigned_adjuster: str
    assigned_approver: str
    sla_due_hours: int
    human_decision: str
    decision_notes: str
    error: str
    audit: list[str]
    use_interrupts: bool
    resume_documents: list[dict[str, str]]
    auto_decision: str


REQUIRED_BY_TYPE = {
    "medical": ["claim_form", "invoice", "doctor_note"],
    "pharmacy": ["claim_form", "invoice", "prescription"],
    "dental": ["claim_form", "invoice"],
}


@dataclass
class MCPToolbox:
    tools: dict[str, Any]

    @staticmethod
    def _normalize_tool_result(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, list) and raw and isinstance(raw[0], dict) and "text" in raw[0]:
            parsed_items: list[Any] = []
            for item in raw:
                text = item.get("text", "")
                try:
                    parsed_items.append(json.loads(text))
                except json.JSONDecodeError:
                    parsed_items.append({"raw_text": text})
            if len(parsed_items) == 1:
                single = parsed_items[0]
                return single if isinstance(single, dict) else {"value": single}
            return {"items": parsed_items}
        return {"raw": raw}

    async def call(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        tool = self.tools.get(tool_name)
        if not tool:
            return {"error": f"missing_tool:{tool_name}"}

        raw = await tool.ainvoke(payload)
        return self._normalize_tool_result(raw)

    def call_sync(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        tool = self.tools.get(tool_name)
        if not tool:
            return {"error": f"missing_tool:{tool_name}"}

        try:
            raw = tool.invoke(payload) if hasattr(tool, "invoke") else asyncio.run(tool.ainvoke(payload))
        except NotImplementedError:
            raw = asyncio.run(tool.ainvoke(payload))
        return self._normalize_tool_result(raw)


class CapstoneSupervisorWorkflow:
    """Task-3 starter: supervisor + specialists + interrupt nodes."""

    def __init__(self, toolbox: MCPToolbox) -> None:
        self.toolbox = toolbox

    def build(self, checkpointer: Any | None = None):
        graph = StateGraph(ClaimState)

        graph.add_node("supervisor", self.supervisor)
        graph.add_node("intake", self.intake)
        graph.add_node("documents", self.documents)
        graph.add_node("summary", self.summary)
        graph.add_node("routing", self.routing)
        graph.add_node("sla", self.sla)
        graph.add_node("await_documents", self.await_documents)
        graph.add_node("human_review", self.human_review)
        graph.add_node("finalize", self.finalize)
        graph.add_node("manual_review", self.manual_review)

        graph.add_edge(START, "supervisor")
        graph.add_edge("intake", "supervisor")
        graph.add_edge("documents", "supervisor")
        graph.add_edge("summary", "supervisor")
        graph.add_edge("routing", "supervisor")
        graph.add_edge("sla", "supervisor")
        graph.add_edge("human_review", "supervisor")
        graph.add_edge("manual_review", END)
        graph.add_edge("finalize", END)

        return graph.compile(checkpointer=checkpointer or MemorySaver())

    def supervisor(self, state: ClaimState) -> Command[Literal[
        "intake",
        "documents",
        "summary",
        "routing",
        "sla",
        "await_documents",
        "human_review",
        "manual_review",
        "finalize",
    ]]:
        if state.get("error"):
            return Command(goto="manual_review")

        status = state.get("status", "new")
        if status == "new":
            return Command(goto="intake")
        if status == "intake_done":
            return Command(goto="documents")
        if status == "awaiting_documents":
            return Command(goto="await_documents")
        if status == "documents_done":
            return Command(goto="summary")
        if status == "summary_done":
            return Command(goto="routing")
        if status == "routing_done":
            return Command(goto="sla")
        if status == "sla_done":
            return Command(goto="human_review")
        if status in {"approved", "rejected"}:
            return Command(goto="finalize")
        if status == "manual_review":
            return Command(goto="manual_review")
        return Command(goto="manual_review")

    def intake(self, state: ClaimState) -> dict[str, Any]:
        reg = self.toolbox.call_sync(
            "register_case",
            {
                "case_id": state["case_id"],
                "policy_number": state["policy_number"],
                "amount": state["amount"],
            },
        )
        cov = self.toolbox.call_sync(
            "check_coverage",
            {
                "policy_number": state["policy_number"],
                "claim_type": state["claim_type"],
                "amount": state["amount"],
            },
        )
        if reg.get("error"):
            return {"error": reg["error"], "status": "manual_review"}
        if cov.get("error"):
            return {"error": cov["error"], "status": "manual_review"}
        return {
            "status": "intake_done",
            "coverage": cov,
            "audit": ["intake_completed"],
        }

    def documents(self, state: ClaimState) -> dict[str, Any]:
        docs = state.get("documents", [])
        for doc in docs:
            doc_id = doc.get("name", "document")
            content = doc.get("content", "")
            self.toolbox.call_sync(
                "upsert_document",
                {
                    "case_id": state["case_id"],
                    "doc_id": doc_id,
                    "content": content,
                    "doc_type": "unknown",
                },
            )
            self.toolbox.call_sync("classify_document", {"case_id": state["case_id"], "doc_id": doc_id})
            self.toolbox.call_sync("extract_fields", {"case_id": state["case_id"], "doc_id": doc_id})

        required = REQUIRED_BY_TYPE.get(state.get("claim_type", "").lower(), ["claim_form", "invoice"])
        validation = self.toolbox.call_sync(
            "validate_case_documents",
            {"case_id": state["case_id"], "required_docs": required},
        )
        missing = validation.get("missing_documents", [])
        if missing:
            return {"status": "awaiting_documents", "missing_documents": missing}
        return {"status": "documents_done", "missing_documents": []}

    def summary(self, state: ClaimState) -> dict[str, Any]:
        summary_payload = {
            "facts": [f"Case {state['case_id']} amount={state['amount']:.2f}"],
            "evidence": [doc.get("name") for doc in state.get("documents", [])],
            "missing_info": state.get("missing_documents", []),
            "risks": [],
            "next_action": "route",
        }
        save = self.toolbox.call_sync("save_summary", {"case_id": state["case_id"], "summary": summary_payload})
        if save.get("error"):
            return {"error": save["error"], "status": "manual_review"}
        return {"status": "summary_done", "summary": summary_payload}

    def routing(self, state: ClaimState) -> dict[str, Any]:
        adjusters = self.toolbox.call_sync("get_workload", {"role": "adjuster"})
        approvers = self.toolbox.call_sync("get_workload", {"role": "approver"})
        if isinstance(adjusters, dict):
            adjusters = adjusters.get("items", [])
        if isinstance(approvers, dict):
            approvers = approvers.get("items", [])
        if not isinstance(adjusters, list) or not isinstance(approvers, list) or not approvers:
            return {"status": "manual_review", "error": "no_staff_available"}

        adjuster_id = adjusters[0]["staff_id"]
        self.toolbox.call_sync("assign_case", {"case_id": state["case_id"], "adjuster_id": adjuster_id})

        eligible = [a for a in approvers if a.get("approval_limit", 0) >= state["amount"]]
        if not eligible:
            return {"status": "manual_review", "error": "no_approver_limit"}

        approver_id = sorted(eligible, key=lambda x: x.get("workload", 0))[0]["staff_id"]
        req = self.toolbox.call_sync(
            "request_approval",
            {
                "case_id": state["case_id"],
                "approver_id": approver_id,
                "amount": state["amount"],
            },
        )
        if req.get("error"):
            return {"status": "manual_review", "error": req["error"]}

        return {"status": "routing_done", "assigned_adjuster": adjuster_id, "assigned_approver": approver_id}

    def sla(self, state: ClaimState) -> dict[str, Any]:
        due_hours = 4 if state["amount"] >= 5000 else 12
        self.toolbox.call_sync("schedule_sla", {"case_id": state["case_id"], "due_hours": due_hours})
        self.toolbox.call_sync(
            "send_notification",
            {
                "case_id": state["case_id"],
                "recipient": state.get("assigned_approver", "approver"),
                "subject": f"Approval needed for {state['case_id']}",
                "body": "Case is ready for human review.",
            },
        )
        return {"status": "sla_done", "sla_due_hours": due_hours}

    def await_documents(self, state: ClaimState) -> Command[Literal["documents"]]:
        if state.get("use_interrupts", False):
            payload = interrupt(
                {
                    "type": "await_documents",
                    "case_id": state["case_id"],
                    "missing_documents": state.get("missing_documents", []),
                }
            )
            extra_docs = payload.get("documents", []) if isinstance(payload, dict) else []
        else:
            extra_docs = state.get("resume_documents", [])
        return Command(goto="documents", update={"documents": state.get("documents", []) + extra_docs})

    def human_review(self, state: ClaimState) -> dict[str, Any]:
        if state.get("use_interrupts", False):
            payload = interrupt(
                {
                    "type": "human_review",
                    "case_id": state["case_id"],
                    "summary": state.get("summary", {}),
                    "assigned_approver": state.get("assigned_approver"),
                }
            )
            decision = payload.get("decision", "manual_review") if isinstance(payload, dict) else "manual_review"
            notes = payload.get("notes", "") if isinstance(payload, dict) else ""
        else:
            decision = state.get("auto_decision", "approve")
            notes = "Auto decision for skeleton demo mode."

        if decision == "approve":
            return {"status": "approved", "human_decision": "approve", "decision_notes": notes}
        if decision == "reject":
            return {"status": "rejected", "human_decision": "reject", "decision_notes": notes}
        return {"status": "awaiting_documents", "human_decision": "request_info", "decision_notes": notes}

    def finalize(self, state: ClaimState) -> dict[str, Any]:
        return {"status": state.get("status", "approved")}

    def manual_review(self, state: ClaimState) -> dict[str, Any]:
        return {"status": "manual_review"}


def compile_with_postgres(checkpoint_dsn: str, workflow: CapstoneSupervisorWorkflow):
    if PostgresSaver is None:
        raise RuntimeError("langgraph-checkpoint-postgres is not installed")

    saver_cm = PostgresSaver.from_conn_string(checkpoint_dsn)
    saver = saver_cm.__enter__()
    graph = workflow.build(checkpointer=saver)
    graph._capstone_saver_cm = saver_cm  # type: ignore[attr-defined]
    return graph
