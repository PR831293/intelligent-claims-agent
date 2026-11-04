from __future__ import annotations

import os

from fastapi import FastAPI, Header, HTTPException

from .api_models import ClaimInputIn, DecisionRequest, ResumeRequest
from .models import ClaimInput, Document, HumanDecision, WorkflowState
from .service import ClaimWorkflowService
from .storage import CheckpointStore


def _to_claim_input(payload: ClaimInputIn) -> ClaimInput:
    return ClaimInput(
        claim_id=payload.claim_id,
        member_id=payload.member_id,
        claim_type=payload.claim_type,
        amount=payload.amount,
        documents=[Document(name=doc.name, content=doc.content) for doc in payload.documents],
    )


def _state_response(state: WorkflowState) -> dict:
    return state.to_dict()


def _map_service_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if message.startswith("Unknown run_id"):
        return HTTPException(status_code=404, detail=message)
    return HTTPException(status_code=400, detail=message)


def create_app(db_url: str | None = None) -> FastAPI:
    app = FastAPI(title="Intelligent Claims Agent API", version="1.0.0")

    selected_db_url = db_url or os.environ.get("DB_URL", "sqlite+pysqlite:///claims_agent.db")
    decision_api_key = os.environ.get("HUMAN_DECISION_API_KEY")
    service = ClaimWorkflowService(CheckpointStore(db_url=selected_db_url))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/claims/start")
    def start_claim(payload: ClaimInputIn) -> dict:
        state = service.start(_to_claim_input(payload))
        return _state_response(state)

    @app.get("/claims/{run_id}/state")
    def get_state(run_id: str) -> dict:
        try:
            state = service.get_state(run_id)
            return _state_response(state)
        except ValueError as exc:
            raise _map_service_error(exc) from exc

    @app.post("/claims/{run_id}/resume")
    def resume_claim(run_id: str, payload: ResumeRequest) -> dict:
        try:
            state = service.resume_with_documents(
                run_id,
                [{"name": doc.name, "content": doc.content} for doc in payload.extra_documents],
            )
            return _state_response(state)
        except ValueError as exc:
            raise _map_service_error(exc) from exc

    @app.post("/claims/{run_id}/decision")
    def submit_decision(
        run_id: str,
        payload: DecisionRequest,
        x_api_key: str | None = Header(default=None),
    ) -> dict:
        if not decision_api_key:
            raise HTTPException(status_code=503, detail="HUMAN_DECISION_API_KEY is not configured")
        if not x_api_key or x_api_key != decision_api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key for human decision")
        try:
            decision = HumanDecision(payload.decision)
            state = service.submit_human_decision(run_id, decision, payload.notes)
            return _state_response(state)
        except ValueError as exc:
            raise _map_service_error(exc) from exc

    @app.get("/claims/{run_id}/trace")
    def get_trace(run_id: str) -> list[dict]:
        trace = service.trace(run_id)
        if not trace:
            # Distinguish between empty trace for unknown run and run with no events.
            try:
                service.get_state(run_id)
            except ValueError as exc:
                raise _map_service_error(exc) from exc
        return trace

    return app


app = create_app()
