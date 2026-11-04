from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text

from .models import AuditEvent, WorkflowState


class CheckpointStore:
    """Persist workflow checkpoints and audit events in PostgreSQL or SQLite."""

    def __init__(self, db_url: str = "sqlite+pysqlite:///claims_agent.db") -> None:
        self.engine = create_engine(db_url, future=True)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS workflow_checkpoints (
                        run_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        current_step TEXT NOT NULL,
                        state_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS workflow_events (
                        id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        step TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        message TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
            )

    def save_state(self, state: WorkflowState) -> None:
        payload = json.dumps(state.to_dict())
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO workflow_checkpoints (run_id, status, current_step, state_json, updated_at)
                    VALUES (:run_id, :status, :current_step, :state_json, :updated_at)
                    ON CONFLICT(run_id) DO UPDATE SET
                        status = excluded.status,
                        current_step = excluded.current_step,
                        state_json = excluded.state_json,
                        updated_at = excluded.updated_at
                    """
                ),
                {
                    "run_id": state.run_id,
                    "status": state.status.value,
                    "current_step": state.current_step,
                    "state_json": payload,
                    "updated_at": now,
                },
            )

    def load_state(self, run_id: str) -> WorkflowState | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                text("SELECT state_json FROM workflow_checkpoints WHERE run_id = :run_id"),
                {"run_id": run_id},
            ).mappings().first()

        if not row:
            return None
        state_raw = json.loads(row["state_json"])
        return WorkflowState.from_dict(state_raw)

    def save_event(self, event: AuditEvent) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO workflow_events (id, run_id, step, event_type, message, payload_json, created_at)
                    VALUES (:id, :run_id, :step, :event_type, :message, :payload_json, :created_at)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "run_id": event.run_id,
                    "step": event.step,
                    "event_type": event.event_type,
                    "message": event.message,
                    "payload_json": json.dumps(event.payload),
                    "created_at": now,
                },
            )

    def list_events(self, run_id: str) -> list[dict[str, Any]]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT step, event_type, message, payload_json, created_at
                    FROM workflow_events
                    WHERE run_id = :run_id
                    ORDER BY created_at ASC, id ASC
                    """
                ),
                {"run_id": run_id},
            ).mappings().all()

        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "step": row["step"],
                    "event_type": row["event_type"],
                    "message": row["message"],
                    "payload": json.loads(row["payload_json"]),
                    "created_at": row["created_at"],
                }
            )
        return result
