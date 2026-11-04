from intelligent_claims_agent.demo_data import clean_claim, high_risk_claim, missing_document_claim
from intelligent_claims_agent.models import HumanDecision, WorkflowStatus
from intelligent_claims_agent.service import ClaimWorkflowService
from intelligent_claims_agent.storage import CheckpointStore


def test_clean_claim_reaches_human_gate(tmp_path):
    store = CheckpointStore(db_url=f"sqlite+pysqlite:///{tmp_path}/test.db")
    service = ClaimWorkflowService(store)

    state = service.start(clean_claim())

    assert state.status == WorkflowStatus.AWAITING_HUMAN_DECISION
    assert state.current_step == "human_review"


def test_missing_docs_then_resume_and_approve(tmp_path):
    store = CheckpointStore(db_url=f"sqlite+pysqlite:///{tmp_path}/test.db")
    service = ClaimWorkflowService(store)

    state = service.start(missing_document_claim())
    assert state.status == WorkflowStatus.AWAITING_DOCUMENTS

    state = service.resume_with_documents(
        state.run_id,
        [{"name": "doctor_note", "content": "Added after provider follow-up."}],
    )
    assert state.status == WorkflowStatus.AWAITING_HUMAN_DECISION

    state = service.submit_human_decision(state.run_id, HumanDecision.APPROVE, "Looks good")
    assert state.status == WorkflowStatus.COMPLETED


def test_high_risk_claim_pauses_for_human_review(tmp_path):
    store = CheckpointStore(db_url=f"sqlite+pysqlite:///{tmp_path}/test.db")
    service = ClaimWorkflowService(store)

    state = service.start(high_risk_claim())

    assert state.status == WorkflowStatus.AWAITING_HUMAN_DECISION
    assert state.current_step == "human_review"
    assert "high_risk_flags" in state.extracted_facts

    state = service.submit_human_decision(state.run_id, HumanDecision.REQUEST_INFO, "Need compliance checks")
    assert state.status == WorkflowStatus.AWAITING_DOCUMENTS
