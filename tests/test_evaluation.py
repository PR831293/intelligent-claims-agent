from intelligent_claims_agent.demo_data import clean_claim, injection_claim
from intelligent_claims_agent.evaluation import evaluate_runs
from intelligent_claims_agent.models import HumanDecision, WorkflowState, WorkflowStatus


def _state(
    claim,
    *,
    status: WorkflowStatus,
    summary: str = "",
    route: str = "",
    extracted_facts: dict | None = None,
    human_decision: HumanDecision | None = None,
) -> WorkflowState:
    return WorkflowState(
        run_id="run-1",
        status=status,
        current_step="human_review",
        claim=claim,
        summary=summary,
        route=route,
        extracted_facts=extracted_facts or {},
        human_decision=human_decision,
    )


def test_injection_resistance_is_not_based_on_claim_id_suffix():
    claim = injection_claim()
    claim.claim_id = "INJ-ANY-ID"
    run = _state(
        claim,
        status=WorkflowStatus.AWAITING_HUMAN_DECISION,
        extracted_facts={"injection_flags": ["doc matched pattern"]},
    )

    metrics = evaluate_runs([run])

    assert metrics.injection_resistance == 100.0


def test_human_control_compliance_uses_terminal_runs_only():
    terminal_completed = _state(
        clean_claim(),
        status=WorkflowStatus.COMPLETED,
        summary="ready",
        human_decision=HumanDecision.APPROVE,
    )
    terminal_rejected = _state(
        clean_claim(),
        status=WorkflowStatus.REJECTED,
        summary="ready",
        human_decision=HumanDecision.REJECT,
    )
    non_terminal = _state(
        clean_claim(),
        status=WorkflowStatus.AWAITING_DOCUMENTS,
        human_decision=None,
    )

    metrics = evaluate_runs([terminal_completed, terminal_rejected, non_terminal])

    assert metrics.human_control_compliance == 100.0


def test_injection_resistance_defaults_to_100_when_no_injection_cases():
    run = _state(clean_claim(), status=WorkflowStatus.COMPLETED, human_decision=HumanDecision.APPROVE)

    metrics = evaluate_runs([run])

    assert metrics.injection_resistance == 100.0
