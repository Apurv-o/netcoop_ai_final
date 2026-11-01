import json

import pytest

from app import app
from netcoop import diagnose, load_sample


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_all_samples_return_structured_reports():
    expectations = {
        "congestion": "diagnosed",
        "weak_wifi": "diagnosed",
        "interface_fault": "diagnosed",
        "normal": "no_anomaly_detected",
        "malformed": "input_error",
    }
    for name, status in expectations.items():
        report = diagnose(load_sample(name))
        assert report["status"] == status
        assert report["report_version"] == "1.0"
        assert isinstance(report["summary"]["recommended_actions"], list)
        json.dumps(report)


def test_two_agents_emit_contract_and_handoffs():
    report = diagnose(load_sample("congestion"))
    assert {finding["agent_id"] for finding in report["agent_findings"]} == {"performance_agent", "infrastructure_agent"}
    for message in report["agent_findings"]:
        assert message["protocol_version"] == "1.0"
        assert message["message_type"] == "agent_finding"
        assert {"agent_id", "device_id", "issue", "severity", "evidence", "handoff"} <= message.keys()
        assert message["handoff"]["to_agent"] == "orchestrator"
    assert len(report["agent_handoffs"]) == len(report["agent_findings"])


def test_malformed_input_stops_before_agents():
    report = diagnose(load_sample("malformed"))
    assert report["status"] == "input_error"
    assert report["agent_findings"] == []
    assert report["validation_messages"]
    assert report["orchestration_log"][0]["status"] == "failed"


def test_partial_metric_warnings_are_preserved():
    report = diagnose({"incident_id": "INC-WARN", "devices": [{"device_id": "edge-1", "metrics": {"latency_ms": "slow", "cpu_pct": 20}}]})
    assert report["status"] == "no_anomaly_detected"
    assert "not numeric" in report["validation_messages"][0]


def test_http_health_catalog_and_diagnosis(client):
    assert client.get("/healthz").get_json()["ok"] is True
    catalog = client.get("/api/scenarios")
    assert catalog.status_code == 200
    assert len(catalog.get_json()["scenarios"]) == 5
    response = client.post("/api/diagnose", json=load_sample("interface_fault"))
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "diagnosed"
    assert "interface fault" in payload["summary"]["suspected_root_cause"].lower()


def test_http_accepts_scenario_envelope_without_skipping_agents(client):
    envelope = client.get("/api/scenarios/congestion").get_json()
    response = client.post("/api/diagnose", json=envelope)
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "diagnosed"
    assert {message["agent_id"] for message in payload["agent_findings"]} == {"performance_agent", "infrastructure_agent"}


def test_http_rejects_non_json(client):
    response = client.post("/api/diagnose", data="not json", content_type="text/plain")
    assert response.status_code == 415
    assert "error" in response.get_json()


def test_static_assets_serve_correctly(client):
    for path in ("/styles.css", "/public/styles.css", "/app.js", "/public/app.js", "/"):
        response = client.get(path)
        assert response.status_code == 200, f"Failed for {path}"


def test_serverless_handler_importable():
    from api.index import app as vercel_app, handler
    assert vercel_app is not None
    assert handler is not None
