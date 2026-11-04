from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
import streamlit as st

st.set_page_config(page_title="Intelligent Claims Agent UI", page_icon=":material/analytics:", layout="wide")


WORKFLOW_STEPS = [
    ("intake", "Intake agent"),
    ("documents", "Document agent"),
    ("summary", "Summary agent"),
    ("routing", "Routing agent"),
    ("sla", "SLA and comms agent"),
    ("human_review", "Human approver"),
]

STEP_STATUS_META = {
    "pending": {"label": "Pending", "color": "blue", "icon": ":material/schedule:"},
    "active": {"label": "Active", "color": "orange", "icon": ":material/play_arrow:"},
    "paused": {"label": "Paused", "color": "red", "icon": ":material/pause_circle:"},
    "completed": {"label": "Completed", "color": "green", "icon": ":material/check_circle:"},
}


def default_documents(claim_type: str, include_required: bool) -> list[dict[str, str]]:
    base = [
        {"name": "claim_form", "content": "Submitted by member."},
        {"name": "invoice", "content": "Billed amount from provider."},
    ]
    if include_required:
        if claim_type == "medical":
            base.append({"name": "doctor_note", "content": "Treatment required."})
        elif claim_type == "pharmacy":
            base.append({"name": "prescription", "content": "Medication prescribed by physician."})
    return base


def init_state() -> None:
    st.session_state.setdefault("active_run_id", "")
    st.session_state.setdefault("run_id_input", "")
    st.session_state.setdefault("latest_state", None)
    st.session_state.setdefault("latest_trace", [])
    st.session_state.setdefault("latest_trace_run_id", "")
    st.session_state.setdefault("approver_signed_in", False)
    st.session_state.setdefault("approver_name", "")
    st.session_state.setdefault("approver_api_key", "my-local-demo-key")


def api_call(
    api_base: str,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int | None, dict[str, Any] | list[dict[str, Any]] | str]:
    url = f"{api_base.rstrip('/')}{path}"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.request(method, url, json=payload, headers=headers)
        try:
            body = response.json()
        except Exception:
            body = response.text
        return response.status_code, body
    except Exception as exc:  # pragma: no cover
        return None, str(exc)


def show_status_banner(state: dict[str, Any] | None) -> None:
    if not state:
        st.info("No active run selected. Start a claim or paste a run ID.")
        return

    status = state.get("status", "unknown")
    if status == "awaiting_documents":
        st.warning("Workflow paused: waiting for required documents.")
    elif status == "awaiting_human_decision":
        st.info("Workflow paused at human approval gate. Agents prepare, people decide.")
    elif status in {"completed", "rejected"}:
        st.success(f"Workflow finished with status: {status}")
    elif status == "failed":
        st.error("Workflow moved to manual review because validation or policy checks failed.")
    else:
        st.info(f"Workflow running. Current status: {status}")


def render_workflow_rail(state: dict[str, Any] | None) -> None:
    st.subheader("Happy path workflow")
    st.caption("Claim submitted -> intake -> documents -> summary -> routing -> SLA and comms -> human approver")

    if not state:
        current_step = "intake"
        current_index = 0
    else:
        current_step = str(state.get("current_step", "intake"))
        step_keys = [step for step, _ in WORKFLOW_STEPS]
        current_index = step_keys.index(current_step) if current_step in step_keys else 0

    lines: list[str] = []
    for idx, (key, label) in enumerate(WORKFLOW_STEPS):
        if state and key == current_step:
            marker = "▶"
        elif idx < current_index:
            marker = "✓"
        else:
            marker = "○"
        lines.append(f"{marker} {label}")

    st.markdown("\n\n".join(lines))

    if state and state.get("status") == "awaiting_documents":
        missing_docs = state.get("missing_documents", [])
        st.caption(f"Missing documents: {', '.join(missing_docs) if missing_docs else 'unknown'}")


def step_statuses(state: dict[str, Any] | None) -> list[tuple[str, str, str]]:
    keys = [key for key, _ in WORKFLOW_STEPS]
    labels = {key: label for key, label in WORKFLOW_STEPS}

    if not state:
        statuses = {key: "pending" for key in keys}
        statuses["intake"] = "active"
        return [(key, labels[key], statuses[key]) for key in keys]

    status = str(state.get("status", "running"))
    current_step = str(state.get("current_step", "intake"))
    current_idx = keys.index(current_step) if current_step in keys else 0
    statuses = {key: "pending" for key in keys}

    for idx, key in enumerate(keys):
        if idx < current_idx:
            statuses[key] = "completed"

    if status in {"completed", "rejected"}:
        for key in keys:
            statuses[key] = "completed"
        return [(key, labels[key], statuses[key]) for key in keys]

    if status in {"awaiting_documents", "awaiting_human_decision", "failed"}:
        statuses[current_step] = "paused"
    else:
        statuses[current_step] = "active"

    return [(key, labels[key], statuses[key]) for key in keys]


def render_timeline_cards(state: dict[str, Any] | None) -> None:
    st.subheader("Step timeline")
    cards = step_statuses(state)
    rows = [cards[i : i + 3] for i in range(0, len(cards), 3)]
    for row in rows:
        cols = st.columns(3)
        for idx, (key, label, status_key) in enumerate(row):
            meta = STEP_STATUS_META[status_key]
            with cols[idx]:
                with st.container(border=True):
                    st.caption(label)
                    st.badge(meta["label"], icon=meta["icon"], color=meta["color"])
                    st.caption(f"Step key: {key}")


def update_run_state(api_base: str, run_id: str) -> None:
    if not run_id.strip():
        st.error("Run ID is required.")
        return
    code, body = api_call(api_base, "GET", f"/claims/{run_id}/state")
    if code == 200 and isinstance(body, dict):
        st.session_state.active_run_id = run_id
        st.session_state.run_id_input = run_id
        st.session_state.latest_state = body
        load_trace_for_run(api_base, run_id)
        st.toast("State refreshed", icon=":material/check_circle:")
        st.rerun()
    else:
        st.error(f"Could not load state ({code}): {body}")


def load_trace_for_run(api_base: str, run_id: str, *, toast: bool = False) -> None:
    if not run_id.strip():
        return
    code, body = api_call(api_base, "GET", f"/claims/{run_id}/trace")
    if code == 200 and isinstance(body, list):
        st.session_state.latest_trace = body
        st.session_state.latest_trace_run_id = run_id
        if toast:
            st.toast("Trace loaded", icon=":material/history:")


init_state()

st.title("Intelligent claims control center")
st.caption("Interactive supervisor view with pause and resume controls, plus human-only approval.")

with st.sidebar:
    st.header("Connection and approver")
    api_base = st.text_input("API base URL", value="http://127.0.0.1:8001", key="api_base_url")

    health_code, _ = api_call(api_base, "GET", "/health")
    if health_code == 200:
        st.success("API online")
    else:
        st.warning("API is not responding")

    with st.form("approver_signin_form"):
        st.text_input("Approver name", key="approver_name", placeholder="e.g. APR-01")
        st.text_input("Decision API key", key="approver_api_key", type="password")
        sign_in = st.form_submit_button("Sign in as approver", type="primary")
        if sign_in:
            if st.session_state.approver_name.strip() and st.session_state.approver_api_key.strip():
                st.session_state.approver_signed_in = True
                st.toast("Approver session active", icon=":material/verified_user:")
            else:
                st.session_state.approver_signed_in = False
                st.error("Approver name and API key are required.")

    if st.session_state.approver_signed_in:
        st.success(f"Signed in: {st.session_state.approver_name}")
    if st.button("Sign out approver"):
        st.session_state.approver_signed_in = False
        st.session_state.approver_name = ""
        st.toast("Approver signed out", icon=":material/logout:")

state = st.session_state.latest_state if isinstance(st.session_state.latest_state, dict) else None
if st.session_state.active_run_id and st.session_state.latest_trace_run_id != st.session_state.active_run_id:
    load_trace_for_run(api_base, st.session_state.active_run_id)
show_status_banner(state)
render_workflow_rail(state)
render_timeline_cards(state)

left, right = st.columns([1.1, 1])

with left:
    with st.container(border=True):
        st.subheader("1) Submit a claim")
        with st.form("start_claim_form"):
            claim_type = st.selectbox("Claim type", ["medical", "pharmacy", "dental"], index=0)
            include_required_doc = st.toggle("Include required document for happy path", value=True)
            claim_id_default = f"CLM-UI-{uuid.uuid4().hex[:6].upper()}"
            member_id_default = f"MBR-UI-{uuid.uuid4().hex[:6].upper()}"
            claim_id = st.text_input("Claim ID", value=claim_id_default)
            member_id = st.text_input("Member ID", value=member_id_default)
            amount = st.number_input("Amount", min_value=1.0, value=400.0, step=50.0)

            docs_default = default_documents(claim_type, include_required_doc)
            docs_text = st.text_area(
                "Documents JSON",
                value=json.dumps(docs_default, indent=2),
                height=190,
            )

            submit_claim = st.form_submit_button("Start claim", type="primary")

        if submit_claim:
            try:
                documents = json.loads(docs_text)
                payload = {
                    "claim_id": claim_id,
                    "member_id": member_id,
                    "claim_type": claim_type,
                    "amount": float(amount),
                    "documents": documents,
                }
                code, body = api_call(api_base, "POST", "/claims/start", payload=payload)
                if code == 200 and isinstance(body, dict):
                    st.session_state.active_run_id = str(body.get("run_id", ""))
                    st.session_state.run_id_input = st.session_state.active_run_id
                    st.session_state.latest_state = body
                    load_trace_for_run(api_base, st.session_state.active_run_id)
                    st.success(f"Claim started. Run ID: {st.session_state.active_run_id}")
                    st.rerun()
                else:
                    st.error(f"Start claim failed ({code}): {body}")
            except json.JSONDecodeError as exc:
                st.error(f"Invalid document JSON: {exc}")

with right:
    with st.container(border=True):
        st.subheader("2) Run operations")
        run_id_input = st.text_input("Run ID", key="run_id_input")

        action_col_1, action_col_2 = st.columns(2)
        with action_col_1:
            if st.button("Refresh state", width="stretch"):
                update_run_state(api_base, run_id_input)
        with action_col_2:
            if st.button("Load trace", width="stretch"):
                load_trace_for_run(api_base, run_id_input, toast=True)

        current_state = st.session_state.latest_state if isinstance(st.session_state.latest_state, dict) else None

        if current_state and current_state.get("status") == "awaiting_documents":
            with st.form("resume_form"):
                st.caption("Workflow is paused. Provide missing documents to resume.")
                resume_docs_text = st.text_area(
                    "Extra documents JSON",
                    value=json.dumps([
                        {"name": "doctor_note", "content": "Uploaded after pause."},
                    ], indent=2),
                    height=130,
                )
                resume_submit = st.form_submit_button("Resume with documents", type="primary")

            if resume_submit:
                try:
                    resume_docs = json.loads(resume_docs_text)
                    code, body = api_call(
                        api_base,
                        "POST",
                        f"/claims/{run_id_input}/resume",
                        payload={"extra_documents": resume_docs},
                    )
                    if code == 200 and isinstance(body, dict):
                        st.session_state.latest_state = body
                        load_trace_for_run(api_base, run_id_input)
                        st.success("Workflow resumed.")
                        st.rerun()
                    else:
                        st.error(f"Resume failed ({code}): {body}")
                except json.JSONDecodeError as exc:
                    st.error(f"Invalid resume document JSON: {exc}")

        human_gate_open = bool(current_state and current_state.get("status") == "awaiting_human_decision")
        if human_gate_open:
            st.subheader("3) Human decision gate")
            st.caption("Golden rule: only a signed-in human approver can finalize this claim.")
            with st.form("decision_form"):
                decision = st.selectbox("Decision", ["approve", "reject", "request_info"], index=0)
                notes = st.text_input("Decision notes", value="Reviewed and approved by human approver.")
                decision_submit = st.form_submit_button("Submit decision", type="primary")

            if decision_submit:
                if not st.session_state.approver_signed_in:
                    st.error("Sign in as approver in the sidebar before submitting a decision.")
                else:
                    headers = {"x-api-key": st.session_state.approver_api_key}
                    code, body = api_call(
                        api_base,
                        "POST",
                        f"/claims/{run_id_input}/decision",
                        payload={"decision": decision, "notes": notes},
                        headers=headers,
                    )
                    if code == 200 and isinstance(body, dict):
                        st.session_state.latest_state = body
                        load_trace_for_run(api_base, run_id_input)
                        st.success("Human decision submitted.")
                        st.rerun()
                    else:
                        st.error(f"Decision failed ({code}): {body}")

st.subheader("Run details")
details_col_1, details_col_2 = st.columns(2)

with details_col_1:
    with st.expander("Current state", expanded=True):
        if isinstance(st.session_state.latest_state, dict):
            st.json(st.session_state.latest_state)
        else:
            st.write("No state loaded yet.")

with details_col_2:
    with st.expander("Audit trace", expanded=True):
        trace = st.session_state.latest_trace
        if isinstance(trace, list) and trace:
            st.dataframe(trace, width="stretch")
        else:
            st.write("No trace loaded yet.")
