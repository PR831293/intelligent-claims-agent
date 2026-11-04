from __future__ import annotations

from datetime import datetime

from mcp.server.fastmcp import FastMCP
from sqlalchemy import text

from .common import (
    as_json,
    ensure_capstone_tables,
    from_json,
    make_engine,
    seed_reference_data,
    server_host,
    server_port,
    write_audit,
)

mcp = FastMCP("case-mcp", host=server_host(), port=server_port(8101))


@mcp.tool()
def get_case(case_id: str) -> dict:
    ensure_capstone_tables()
    engine = make_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT case_id, policy_number, amount, status, assigned_adjuster, assigned_approver, summary_json, created_at, updated_at
                FROM cap_claims
                WHERE case_id = :case_id
                """
            ),
            {"case_id": case_id},
        ).mappings().first()
    if not row:
        return {"error": f"Unknown case_id: {case_id}"}
    return {
        "case_id": row["case_id"],
        "policy_number": row["policy_number"],
        "amount": row["amount"],
        "status": row["status"],
        "assigned_adjuster": row["assigned_adjuster"],
        "assigned_approver": row["assigned_approver"],
        "summary": from_json(row["summary_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@mcp.tool()
def list_cases(limit: int = 50) -> list[dict]:
    ensure_capstone_tables()
    engine = make_engine()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT case_id, policy_number, amount, status, assigned_adjuster, assigned_approver, updated_at
                FROM cap_claims
                ORDER BY updated_at DESC
                LIMIT :limit
                """
            ),
            {"limit": max(1, min(limit, 500))},
        ).mappings().all()
    return [dict(row) for row in rows]


@mcp.tool()
def find_similar_cases(claim_type: str, amount: float, tolerance: float = 0.15) -> list[dict]:
    ensure_capstone_tables()
    min_amount = amount * (1 - max(0.01, tolerance))
    max_amount = amount * (1 + max(0.01, tolerance))
    engine = make_engine()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT c.case_id, c.policy_number, c.amount, c.status, c.updated_at
                FROM cap_claims c
                JOIN cap_policies p ON p.policy_number = c.policy_number
                WHERE p.product = :claim_type AND c.amount BETWEEN :min_amount AND :max_amount
                ORDER BY c.updated_at DESC
                LIMIT 10
                """
            ),
            {
                "claim_type": claim_type.lower(),
                "min_amount": min_amount,
                "max_amount": max_amount,
            },
        ).mappings().all()
    return [dict(row) for row in rows]


@mcp.tool()
def register_case(case_id: str, policy_number: str, amount: float) -> dict:
    ensure_capstone_tables()
    seed_reference_data()
    now = datetime.utcnow().isoformat()
    engine = make_engine()
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT case_id, status FROM cap_claims WHERE case_id = :case_id"),
            {"case_id": case_id},
        ).mappings().first()
        if existing:
            return {"error": f"Case already exists: {case_id}", "status": existing["status"]}

        summary = {
            "facts": [],
            "evidence": [],
            "missing_info": [],
            "risks": [],
            "next_action": "intake",
        }
        conn.execute(
            text(
                """
                INSERT INTO cap_claims (
                    case_id, policy_number, amount, status, assigned_adjuster, assigned_approver,
                    summary_json, created_at, updated_at
                ) VALUES (
                    :case_id, :policy_number, :amount, :status, NULL, NULL,
                    :summary_json, :created_at, :updated_at
                )
                """
            ),
            {
                "case_id": case_id,
                "policy_number": policy_number,
                "amount": amount,
                "status": "registered",
                "summary_json": as_json(summary),
                "created_at": now,
                "updated_at": now,
            },
        )
    write_audit(case_id, "intake-agent", "register_case", {}, {"status": "registered"})
    return {"case_id": case_id, "status": "registered"}


@mcp.tool()
def save_summary(case_id: str, summary: dict) -> dict:
    ensure_capstone_tables()
    engine = make_engine()
    now = datetime.utcnow().isoformat()
    with engine.begin() as conn:
        before = conn.execute(
            text("SELECT summary_json FROM cap_claims WHERE case_id = :case_id"),
            {"case_id": case_id},
        ).mappings().first()
        if not before:
            return {"error": f"Unknown case_id: {case_id}"}

        conn.execute(
            text(
                """
                UPDATE cap_claims
                SET summary_json = :summary_json, updated_at = :updated_at
                WHERE case_id = :case_id
                """
            ),
            {
                "summary_json": as_json(summary),
                "updated_at": now,
                "case_id": case_id,
            },
        )
    write_audit(case_id, "summary-agent", "save_summary", from_json(before["summary_json"]), summary)
    return {"case_id": case_id, "saved": True}


@mcp.resource("case://{case_id}")
def case_resource(case_id: str) -> str:
    payload = get_case(case_id)
    return as_json(payload)


@mcp.resource("case://{case_id}/timeline")
def case_timeline_resource(case_id: str) -> str:
    ensure_capstone_tables()
    engine = make_engine()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT actor, action, before_json, after_json, created_at
                FROM cap_audit_log
                WHERE case_id = :case_id
                ORDER BY created_at ASC
                """
            ),
            {"case_id": case_id},
        ).mappings().all()
    return as_json([dict(row) for row in rows])


@mcp.prompt("case_summary")
def case_summary_prompt(case_id: str) -> str:
    return (
        "Create a structured case summary with facts, evidence, missing info, risks, and next action. "
        f"Case id: {case_id}. Cite policy wording for every risk statement."
    )


def main() -> None:
    ensure_capstone_tables()
    seed_reference_data()
    mcp.run("stdio")


if __name__ == "__main__":
    main()
