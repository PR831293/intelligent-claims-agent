# Intelligent Claims Agent (Learning Project)

This project is a learning-friendly implementation of the requirements shown in your slides:
- Governed multi-agent workflow
- Stateful processing with pause/resume
- Human-only final decision
- Auditability and replay/trace
- Injection detection and PII redaction
- Evaluation gates

## 1) What You Will Build

A Python workflow with specialist agents:
1. Intake
2. Documents
3. Summary
4. Routing
5. SLA & Comms
6. Human decision gate

The workflow supports:
- Missing-document pause and resume
- Injection risk escalation to manual review
- Full event trace for replay
- Persistent checkpoints in SQLite or PostgreSQL

## 2) Project Structure

```text
app.py
requirements.txt
README.md
src/intelligent_claims_agent/
  __init__.py
  agents.py
  demo_data.py
  evaluation.py
  models.py
  policy.py
  service.py
  storage.py
tests/test_workflow.py
```

## 3) Setup

From project root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install includes Streamlit for the interactive UI.

## 4) Run Step-by-Step

### Step 1: Run all demo scenarios

```bash
python app.py demo
```

This runs:
- Clean claim
- Missing document -> resume
- Injection test
- High-risk content test
- Trace replay
- Evaluation metrics

### Step 2: Run one scenario at a time

```bash
python app.py run --scenario clean
python app.py run --scenario missing
python app.py run --scenario injection
python app.py run --scenario high_risk
```

### Step 3: Replay timeline by run id

After running a scenario, copy the `run_id` from output:

```bash
python app.py trace --run-id <RUN_ID>
```

## 5) PostgreSQL Mode (Optional)

Default DB is SQLite. To use PostgreSQL, pass `--db-url`:

```bash
python app.py demo --db-url postgresql+psycopg2://postgres:admin@localhost:5432/genai_training
```

If your local password is different, update the URL.

## 6) How Requirements Map to Code

1. Governance and least privilege:
- `AgentContext` capability checks in `agents.py`

2. Untrusted evidence and injection handling:
- Pattern detection in `policy.py`
- Escalation pause in `service.py`

3. PII protection:
- Redaction utilities in `policy.py`

4. Human-only final authority:
- `submit_human_decision` in `service.py`

5. Auditability and replay:
- Event logging in `storage.py`
- Trace API in `service.py`

6. Stateful pause/resume:
- Checkpoint load/save in `storage.py`
- Resume path in `service.py`

## 7) Run Tests

```bash
PYTHONPATH=src pytest -q
```

## 8) Run API (FastAPI)

Start server:

```bash
# Option A: quick local key
export HUMAN_DECISION_API_KEY=my-local-demo-key

# Option B: generate a strong random key
# export HUMAN_DECISION_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

PYTHONPATH=src uvicorn intelligent_claims_agent.api:app --reload
```

Note: if `HUMAN_DECISION_API_KEY` is not set, the decision endpoint returns `503`.

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## 8.1) Run Interactive UI (Streamlit)

In a second terminal (with the same virtual environment active):

```bash
CLAIMS_API_BASE_URL=http://127.0.0.1:8000 PYTHONPATH=src python -m streamlit run streamlit_app.py --server.port 8501
```

Open:

```text
http://127.0.0.1:8501
```

## 8.2) One-Command Container Run

Start full stack (Postgres + API + Streamlit + MCP services):

```bash
docker compose up --build -d
```

Verify:

```bash
curl http://127.0.0.1:8000/health
```

UI:

```text
http://127.0.0.1:8501
```

Stop:

```bash
docker compose down
```

Start claim:

```bash
curl -X POST http://127.0.0.1:8000/claims/start \
  -H "Content-Type: application/json" \
  -d '{
    "claim_id": "CLM-API-1",
    "member_id": "MBR-API-1",
    "claim_type": "medical",
    "amount": 400,
    "documents": [
      {"name": "claim_form", "content": "Submitted by member."},
      {"name": "invoice", "content": "Billed amount 400."},
      {"name": "doctor_note", "content": "Treatment required."}
    ]
  }'
```

Submit decision:

```bash
curl -X POST http://127.0.0.1:8000/claims/<RUN_ID>/decision \
  -H "Content-Type: application/json" \
  -H "x-api-key: $HUMAN_DECISION_API_KEY" \
  -d '{"decision":"approve","notes":"approved by human"}'
```

Trace timeline:

```bash
curl http://127.0.0.1:8000/claims/<RUN_ID>/trace
```

## 9) Learning Exercises

1. Add a new claim type and required documents in `policy.py`.
2. Add confidence scoring in `summary_agent`.
3. Add SLA breach checker and escalation event.
4. Add API layer (FastAPI) on top of `ClaimWorkflowService`.

## 10) Capstone Migration Starters

The repository now includes starter implementations aligned to the FDE capstone architecture:

- MCP servers: `src/capstone_mcp/`
- LangGraph supervisor skeleton: `src/capstone_graph/workflow.py`
- MCP smoke test harness: `scripts/mcp_integration_smoke.py`

Run MCP smoke test (starts and validates all 4 MCP servers locally):

```bash
PYTHONPATH=src .venv/bin/python scripts/mcp_integration_smoke.py
```

Run optional pytest smoke gate:

```bash
RUN_MCP_SMOKE=1 PYTHONPATH=src pytest -q tests/test_mcp_integration_smoke.py
```

Run LangGraph supervisor skeleton demo (auto-resume interrupts):

```bash
PYTHONPATH=src .venv/bin/python scripts/capstone_graph_demo.py --scenario clean
PYTHONPATH=src .venv/bin/python scripts/capstone_graph_demo.py --scenario missing
```

Run LangGraph interrupt-native demo (explicit interrupt/resume with `Command(resume=...)`):

```bash
PYTHONPATH=src .venv/bin/python scripts/capstone_graph_interrupt_demo.py --scenario clean
PYTHONPATH=src .venv/bin/python scripts/capstone_graph_interrupt_demo.py --scenario missing
```

## 11) Deliverable Artifacts

- Architecture one-pager: `doc/architecture.md`
- Evaluation report: `doc/evaluation_report.md`
- Live demo checklist/runbook: `doc/demo_checklist.md`
- Presentation outline: `doc/presentation_outline.md`
- Canonical compose file: `docker-compose.yml`
