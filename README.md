# NetCoop AI

NetCoop AI is a transparent, rule-based multi-agent network fault diagnosis workbench for the hackathon demo. It does not connect to a live campus network or apply automatic fixes. The website runs five synthetic telemetry scenarios, shows what each agent found, and produces a downloadable JSON report.

## What changed from the starter

The original diagnosis engine is preserved in `netcoop.py`, but the implementation is now readable, validated, and explicit about its message contract. The old Streamlit entrypoint was replaced by a small Flask HTTP application so the project can run consistently in local development and in a production container. The browser UI is a responsive Signal-room dashboard in `public/` with a scenario picker, custom JSON upload, agent handoff trace, evidence summary, and JSON copy/download controls.

## Architecture

The flow is `telemetry → validation → Performance Agent + Infrastructure Agent → structured JSON handoff → Orchestrator correlation → report`. Both agents emit versioned `agent_finding` messages containing `protocol_version`, `message_type`, `message_id`, `agent_id`, `device_id`, `issue`, `severity`, `evidence`, and a `handoff` object addressed to the orchestrator. The final report includes those findings, the handoff list, orchestration steps, confidence label, affected devices, evidence, alternatives, recommended actions, and limitations.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:3000`. The API also exposes `GET /healthz`, `GET /api/scenarios`, `GET /api/scenarios/<scenario>`, and `POST /api/diagnose` with a JSON telemetry body.

## Test

```bash
pytest -q
```

The test suite exercises every supplied fixture (`congestion`, `weak_wifi`, `interface_fault`, `normal`, and `malformed`), both agent message contracts, JSON serialization, warning handling, health/catalog endpoints, diagnosis execution, and non-JSON failure behavior.

## Deploy with Docker

```bash
docker build -t netcoop-ai .
docker run --rm -p 3000:3000 netcoop-ai
```

The production listener honors `PORT` and defaults to `3000`. The managed Webdev deployment uses `Dockerfile` and `/healthz` as its health check.

## Limitations

This is an explainable rule-based baseline, not a trained model or live monitor. Thresholds are illustrative and should be calibrated to a real baseline. A probable diagnosis is not proof of a physical root cause; verify before making changes.
