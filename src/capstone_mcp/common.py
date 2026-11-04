from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text

DEFAULT_DB_URL = os.environ.get("DB_URL", "sqlite+pysqlite:///claims_agent.db")


def server_host(default: str = "0.0.0.0") -> str:
    return os.environ.get("MCP_HOST", default)


def server_port(default: int) -> int:
    try:
        return int(os.environ.get("MCP_PORT", str(default)))
    except ValueError:
        return default


def make_engine(db_url: str | None = None):
    return create_engine(db_url or DEFAULT_DB_URL, future=True)


def ensure_capstone_tables(db_url: str | None = None) -> None:
    engine = make_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS cap_claims (
                    case_id TEXT PRIMARY KEY,
                    policy_number TEXT,
                    amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    assigned_adjuster TEXT,
                    assigned_approver TEXT,
                    summary_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS cap_documents (
                    case_id TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    doc_type TEXT,
                    content TEXT NOT NULL,
                    extracted_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (case_id, doc_id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS cap_policies (
                    policy_number TEXT PRIMARY KEY,
                    product TEXT NOT NULL,
                    wording TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS cap_staff (
                    staff_id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    approval_limit REAL NOT NULL,
                    workload INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS cap_audit_log (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    before_json TEXT NOT NULL,
                    after_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
        )


def seed_reference_data(db_url: str | None = None) -> None:
    engine = make_engine(db_url)
    now = datetime.utcnow().isoformat()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO cap_policies (policy_number, product, wording, active, created_at)
                VALUES
                    ('POL-1001', 'medical', 'Medical plan covers medically necessary treatment with prior authorization rules.', 1, :now),
                    ('POL-2001', 'pharmacy', 'Pharmacy plan covers prescribed medication subject to formulary constraints.', 1, :now)
                ON CONFLICT(policy_number) DO NOTHING
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO cap_staff (staff_id, role, approval_limit, workload, active, created_at)
                VALUES
                    ('adj-01', 'adjuster', 0, 3, 1, :now),
                    ('adj-02', 'adjuster', 0, 1, 1, :now),
                    ('apr-01', 'approver', 1000, 2, 1, :now),
                    ('apr-02', 'approver', 10000, 4, 1, :now)
                ON CONFLICT(staff_id) DO NOTHING
                """
            ),
            {"now": now},
        )


def write_audit(case_id: str, actor: str, action: str, before: dict[str, Any], after: dict[str, Any], db_url: str | None = None) -> None:
    import uuid

    engine = make_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO cap_audit_log (id, case_id, actor, action, before_json, after_json, created_at)
                VALUES (:id, :case_id, :actor, :action, :before_json, :after_json, :created_at)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "case_id": case_id,
                "actor": actor,
                "action": action,
                "before_json": json.dumps(before),
                "after_json": json.dumps(after),
                "created_at": datetime.utcnow().isoformat(),
            },
        )


def as_json(value: Any) -> str:
    return json.dumps(value)


def from_json(raw: str) -> Any:
    return json.loads(raw)
