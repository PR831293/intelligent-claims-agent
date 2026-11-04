from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
	sys.path.insert(0, str(SRC))

from intelligent_claims_agent.demo_data import (  # noqa: E402
	clean_claim,
	high_risk_claim,
	injection_claim,
	missing_document_claim,
	supplemental_doctor_note,
)
from intelligent_claims_agent.evaluation import evaluate_runs  # noqa: E402
from intelligent_claims_agent.models import HumanDecision, WorkflowState  # noqa: E402
from intelligent_claims_agent.service import ClaimWorkflowService  # noqa: E402
from intelligent_claims_agent.storage import CheckpointStore  # noqa: E402


def make_service(db_url: str) -> ClaimWorkflowService:
	store = CheckpointStore(db_url=db_url)
	return ClaimWorkflowService(store)


def print_state(label: str, state: WorkflowState) -> None:
	print(f"\n[{label}] run_id={state.run_id}")
	print(f"status={state.status.value} current_step={state.current_step}")
	if state.missing_documents:
		print(f"missing_documents={state.missing_documents}")
	if state.route:
		print(f"route={state.route} sla_due_hours={state.sla_due_hours}")
	if state.summary:
		print(f"summary={state.summary}")
	if state.human_decision:
		print(f"human_decision={state.human_decision.value}")


def run_full_demo(service: ClaimWorkflowService) -> None:
	all_runs: list[WorkflowState] = []

	# Scenario 1: clean claim
	s1 = service.start(clean_claim())
	print_state("clean/start", s1)
	s1 = service.submit_human_decision(s1.run_id, HumanDecision.APPROVE, "Approved by adjuster")
	print_state("clean/final", s1)
	all_runs.append(s1)

	# Scenario 2: missing document and resume
	s2 = service.start(missing_document_claim())
	print_state("missing/start", s2)
	s2 = service.resume_with_documents(s2.run_id, [supplemental_doctor_note()])
	print_state("missing/resumed", s2)
	s2 = service.submit_human_decision(s2.run_id, HumanDecision.APPROVE, "Documents complete")
	print_state("missing/final", s2)
	all_runs.append(s2)

	# Scenario 3: injection test
	s3 = service.start(injection_claim())
	print_state("injection/start", s3)
	s3 = service.submit_human_decision(s3.run_id, HumanDecision.REJECT, "Prompt injection flagged")
	print_state("injection/final", s3)
	all_runs.append(s3)

	# Scenario 4: high-risk content test
	s4 = service.start(high_risk_claim())
	print_state("high_risk/start", s4)
	s4 = service.submit_human_decision(s4.run_id, HumanDecision.REQUEST_INFO, "Need compliance verification")
	print_state("high_risk/final", s4)
	all_runs.append(s4)

	print("\n[trace] clean claim timeline")
	for event in service.trace(s1.run_id):
		print(
			f"{event['created_at']} | {event['step']} | {event['event_type']} | "
			f"{event['message']}"
		)

	metrics = evaluate_runs(all_runs)
	print("\n[evaluation]")
	print(f"task_success={metrics.task_success:.1f}%")
	print(f"summary_completeness={metrics.summary_completeness:.1f}%")
	print(f"human_control_compliance={metrics.human_control_compliance:.1f}%")
	print(f"injection_resistance={metrics.injection_resistance:.1f}%")
	print(f"pii_leakage_count={metrics.pii_leakage_count}")


def run_single_scenario(service: ClaimWorkflowService, scenario: str) -> None:
	if scenario == "clean":
		state = service.start(clean_claim())
		print_state("clean/start", state)
		state = service.submit_human_decision(state.run_id, HumanDecision.APPROVE, "Approved")
		print_state("clean/final", state)
		return

	if scenario == "missing":
		state = service.start(missing_document_claim())
		print_state("missing/start", state)
		state = service.resume_with_documents(state.run_id, [supplemental_doctor_note()])
		print_state("missing/resumed", state)
		state = service.submit_human_decision(state.run_id, HumanDecision.APPROVE, "Approved")
		print_state("missing/final", state)
		return

	if scenario == "injection":
		state = service.start(injection_claim())
		print_state("injection/start", state)
		state = service.submit_human_decision(state.run_id, HumanDecision.REJECT, "Rejected")
		print_state("injection/final", state)
		return

	if scenario == "high_risk":
		state = service.start(high_risk_claim())
		print_state("high_risk/start", state)
		state = service.submit_human_decision(state.run_id, HumanDecision.REQUEST_INFO, "More evidence required")
		print_state("high_risk/final", state)
		return

	raise ValueError(f"Unknown scenario: {scenario}")


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Intelligent Claims Workflow Demo")
	parser.add_argument(
		"command",
		choices=["demo", "run", "trace"],
		help="demo = run all scenarios, run = one scenario, trace = print run timeline",
	)
	parser.add_argument(
		"--scenario",
		choices=["clean", "missing", "injection", "high_risk"],
		default="clean",
		help="scenario name for run command",
	)
	parser.add_argument("--run-id", default="", help="run id for trace command")
	parser.add_argument(
		"--db-url",
		default=os.environ.get("DB_URL", "sqlite+pysqlite:///claims_agent.db"),
		help="database URL (e.g., sqlite+pysqlite:///claims_agent.db or postgresql+psycopg2://postgres:admin@localhost:5432/genai_training)",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	service = make_service(args.db_url)

	if args.command == "demo":
		run_full_demo(service)
		return

	if args.command == "run":
		run_single_scenario(service, args.scenario)
		return

	if args.command == "trace":
		if not args.run_id:
			raise ValueError("--run-id is required for trace")
		events = service.trace(args.run_id)
		if not events:
			print("No events found for run")
			return
		for event in events:
			print(
				f"{event['created_at']} | {event['step']} | {event['event_type']} | "
				f"{event['message']} | payload={event['payload']}"
			)


if __name__ == "__main__":
	main()
