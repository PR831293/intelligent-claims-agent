from fastapi.testclient import TestClient

from intelligent_claims_agent.api import create_app


def _client(tmp_path):
    app = create_app(db_url=f"sqlite+pysqlite:///{tmp_path}/api.db")
    return TestClient(app)


def test_health(tmp_path):
    client = _client(tmp_path)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_start_and_approve_flow_via_api(tmp_path, monkeypatch):
    monkeypatch.setenv("HUMAN_DECISION_API_KEY", "test-key")
    client = _client(tmp_path)

    start_payload = {
        "claim_id": "CLM-API-1",
        "member_id": "MBR-API-1",
        "claim_type": "medical",
        "amount": 400.0,
        "documents": [
            {"name": "claim_form", "content": "Submitted by member."},
            {"name": "invoice", "content": "Billed amount 400."},
            {"name": "doctor_note", "content": "Treatment required."},
        ],
    }
    response = client.post("/claims/start", json=start_payload)
    assert response.status_code == 200
    started = response.json()

    assert started["status"] == "awaiting_human_decision"
    run_id = started["run_id"]

    decision = client.post(
        f"/claims/{run_id}/decision",
        json={"decision": "approve", "notes": "approved by human"},
        headers={"x-api-key": "test-key"},
    )
    assert decision.status_code == 200
    final_state = decision.json()
    assert final_state["status"] == "completed"

    trace = client.get(f"/claims/{run_id}/trace")
    assert trace.status_code == 200
    assert len(trace.json()) > 0


def test_missing_doc_resume_flow_via_api(tmp_path):
    client = _client(tmp_path)

    start_payload = {
        "claim_id": "CLM-API-2",
        "member_id": "MBR-API-2",
        "claim_type": "medical",
        "amount": 1200.0,
        "documents": [
            {"name": "claim_form", "content": "Submitted by member."},
            {"name": "invoice", "content": "Billed amount 1200."},
        ],
    }
    start = client.post("/claims/start", json=start_payload)
    assert start.status_code == 200
    state = start.json()
    assert state["status"] == "awaiting_documents"

    run_id = state["run_id"]
    resume = client.post(
        f"/claims/{run_id}/resume",
        json={"extra_documents": [{"name": "doctor_note", "content": "Added after follow-up."}]},
    )
    assert resume.status_code == 200
    resumed = resume.json()
    assert resumed["status"] == "awaiting_human_decision"


def test_decision_requires_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("HUMAN_DECISION_API_KEY", "secret-key")
    client = _client(tmp_path)

    start_payload = {
        "claim_id": "CLM-API-3",
        "member_id": "MBR-API-3",
        "claim_type": "medical",
        "amount": 100.0,
        "documents": [
            {"name": "claim_form", "content": "Submitted by member."},
            {"name": "invoice", "content": "Billed amount 100."},
            {"name": "doctor_note", "content": "Treatment required."},
        ],
    }
    start = client.post("/claims/start", json=start_payload)
    run_id = start.json()["run_id"]

    unauthorized = client.post(
        f"/claims/{run_id}/decision",
        json={"decision": "approve", "notes": "approved by human"},
    )
    assert unauthorized.status_code == 401

    wrong_key = client.post(
        f"/claims/{run_id}/decision",
        json={"decision": "approve", "notes": "approved by human"},
        headers={"x-api-key": "wrong-key"},
    )
    assert wrong_key.status_code == 401

    authorized = client.post(
        f"/claims/{run_id}/decision",
        json={"decision": "approve", "notes": "approved by human"},
        headers={"x-api-key": "secret-key"},
    )
    assert authorized.status_code == 200


def test_decision_fails_when_api_key_not_configured(tmp_path, monkeypatch):
    monkeypatch.delenv("HUMAN_DECISION_API_KEY", raising=False)
    client = _client(tmp_path)

    start_payload = {
        "claim_id": "CLM-API-4",
        "member_id": "MBR-API-4",
        "claim_type": "medical",
        "amount": 100.0,
        "documents": [
            {"name": "claim_form", "content": "Submitted by member."},
            {"name": "invoice", "content": "Billed amount 100."},
            {"name": "doctor_note", "content": "Treatment required."},
        ],
    }
    start = client.post("/claims/start", json=start_payload)
    run_id = start.json()["run_id"]

    response = client.post(
        f"/claims/{run_id}/decision",
        json={"decision": "approve", "notes": "approved by human"},
        headers={"x-api-key": "anything"},
    )
    assert response.status_code == 503
