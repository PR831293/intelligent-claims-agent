from __future__ import annotations

from datetime import datetime

from mcp.server.fastmcp import FastMCP
from sqlalchemy import text

from .common import as_json, ensure_capstone_tables, make_engine, seed_reference_data, server_host, server_port, write_audit

mcp = FastMCP("workflow-mcp", host=server_host(), port=server_port(8104))


@mcp.tool()
def get_workload(role: str = "adjuster") -> list[dict]:
    ensure_capstone_tables()
    seed_reference_data()
    engine = make_engine()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT staff_id, role, approval_limit, workload, active
                FROM cap_staff
                WHERE role = :role AND active = 1
                ORDER BY workload ASC, staff_id ASC
                """
            ),
            {"role": role},
        ).mappings().all()
    return [dict(row) for row in rows]


@mcp.tool()
def assign_case(case_id: str, adjuster_id: str) -> dict:
    ensure_capstone_tables()
    engine = make_engine()
    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT staff_id FROM cap_staff WHERE staff_id = :staff_id AND role = 'adjuster' AND active = 1"),
            {"staff_id": adjuster_id},
        ).mappings().first()
        if not exists:
            return {"error": f"Unknown adjuster: {adjuster_id}"}

        before = conn.execute(
            text("SELECT assigned_adjuster FROM cap_claims WHERE case_id = :case_id"),
            {"case_id": case_id},
        ).mappings().first()
        if not before:
            return {"error": f"Unknown case_id: {case_id}"}

        conn.execute(
            text("UPDATE cap_claims SET assigned_adjuster = :adjuster_id, updated_at = :updated_at WHERE case_id = :case_id"),
            {
                "case_id": case_id,
                "adjuster_id": adjuster_id,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
        conn.execute(
            text("UPDATE cap_staff SET workload = workload + 1 WHERE staff_id = :staff_id"),
            {"staff_id": adjuster_id},
        )
    write_audit(case_id, "routing-agent", "assign_case", {"assigned_adjuster": before["assigned_adjuster"]}, {"assigned_adjuster": adjuster_id})
    return {"case_id": case_id, "assigned_adjuster": adjuster_id}


@mcp.tool()
def request_approval(case_id: str, approver_id: str, amount: float) -> dict:
    ensure_capstone_tables()
    engine = make_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT approval_limit FROM cap_staff WHERE staff_id = :staff_id AND role = 'approver' AND active = 1"),
            {"staff_id": approver_id},
        ).mappings().first()
        if not row:
            return {"error": f"Unknown approver: {approver_id}"}
        if row["approval_limit"] < amount:
            return {
                "error": "approval_limit_exceeded",
                "approver_id": approver_id,
                "approval_limit": row["approval_limit"],
                "amount": amount,
            }

        before = conn.execute(
            text("SELECT assigned_approver FROM cap_claims WHERE case_id = :case_id"),
            {"case_id": case_id},
        ).mappings().first()
        if not before:
            return {"error": f"Unknown case_id: {case_id}"}

        conn.execute(
            text("UPDATE cap_claims SET assigned_approver = :approver_id, status = :status, updated_at = :updated_at WHERE case_id = :case_id"),
            {
                "case_id": case_id,
                "approver_id": approver_id,
                "status": "awaiting_human_decision",
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
    write_audit(case_id, "routing-agent", "request_approval", {"assigned_approver": before["assigned_approver"]}, {"assigned_approver": approver_id})
    return {"case_id": case_id, "requested_approver": approver_id, "status": "awaiting_human_decision"}


@mcp.tool()
def schedule_sla(case_id: str, due_hours: int) -> dict:
    write_audit(case_id, "sla-agent", "schedule_sla", {}, {"due_hours": due_hours})
    return {"case_id": case_id, "due_hours": due_hours, "scheduled": True}


@mcp.tool()
def send_notification(case_id: str, recipient: str, subject: str, body: str) -> dict:
    write_audit(
        case_id,
        "sla-agent",
        "send_notification",
        {},
        {"recipient": recipient, "subject": subject, "body": body[:200]},
    )
    return {"case_id": case_id, "sent": True, "recipient": recipient}


@mcp.tool()
def request_documents(case_id: str, missing_documents: list[str]) -> dict:
    write_audit(case_id, "sla-agent", "request_documents", {}, {"missing_documents": missing_documents})
    return {"case_id": case_id, "requested": missing_documents}


@mcp.resource("staff://directory")
def staff_directory_resource() -> str:
    return as_json(get_workload("adjuster") + get_workload("approver"))


@mcp.resource("sla://rules")
def sla_rules_resource() -> str:
    return as_json(
        {
            "standard_adjuster_hours": 12,
            "senior_adjuster_hours": 4,
            "manual_review_hours": 2,
        }
    )


@mcp.prompt("claimant_letter")
def claimant_letter_prompt(case_id: str, missing_documents: list[str]) -> str:
    missing = ", ".join(missing_documents)
    return (
        f"Write a concise and polite claimant update for case {case_id}. "
        f"Explain that these documents are required: {missing}."
    )


@mcp.prompt("approver_brief")
def approver_brief_prompt(case_id: str, summary: str) -> str:
    return (
        f"Create a one-page approval brief for case {case_id}. "
        f"Include evidence, key risks, and recommended next action.\n\n{summary}"
    )


def main() -> None:
    ensure_capstone_tables()
    seed_reference_data()
    mcp.run("stdio")


if __name__ == "__main__":
    main()
