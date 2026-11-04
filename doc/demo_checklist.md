# Live Demo Checklist and Runbook

## Prerequisites

- Python 3.11+
- Docker and Docker Compose plugin (for containerized demo)
- Local virtual environment for non-container run

## Option A: One-Command Container Demo

1. Build and start services:
   - `docker compose up --build -d`
2. Verify API health:
   - `curl http://127.0.0.1:8000/health`
3. Open UI:
   - http://127.0.0.1:8501
4. Stop services after demo:
   - `docker compose down`

## Option B: Local Python Demo

1. Create environment and install:
   - `python -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r requirements.txt`
2. Start API:
   - `export HUMAN_DECISION_API_KEY=my-local-demo-key`
   - `PYTHONPATH=src python -m uvicorn intelligent_claims_agent.api:app --host 127.0.0.1 --port 8001`
3. Start UI (new shell):
   - `source .venv/bin/activate`
   - `CLAIMS_API_BASE_URL=http://127.0.0.1:8001 PYTHONPATH=src python -m streamlit run streamlit_app.py --server.port 8501`
4. Open UI:
   - http://127.0.0.1:8501

## Scripted Scenario Checklist

- Clean claim runs to human gate and is approved.
- Missing-document claim pauses and resumes after supplemental document.
- Injection claim is routed to safe/manual review path.
- Trace view shows per-step timeline and events.

## Evidence to Capture

- Screenshot of UI with a completed run.
- API health response.
- Trace output for one run id.
- Evaluation metrics block from `python app.py demo`.
