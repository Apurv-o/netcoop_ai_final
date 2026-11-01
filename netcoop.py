"""Transparent, rule-based multi-agent network fault diagnosis engine."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA = Path(__file__).parent / "data"
PROTOCOL_VERSION = "1.0"
REPORT_VERSION = "1.0"
LIMITS = {
    "latency_ms": 150, "packet_loss_pct": 3, "jitter_ms": 30,
    "link_utilization_pct": 85, "cpu_pct": 90, "interface_errors": 10,
    "queue_drops": 50,
}
SCENARIO_META = {
    "congestion": {"title": "Link congestion", "description": "High utilization, loss, jitter, and queue pressure on an uplink.", "signal": "Utilization + queue drops"},
    "weak_wifi": {"title": "Weak Wi-Fi signal", "description": "An access point reports a client-facing signal below the demo threshold.", "signal": "Signal strength"},
    "interface_fault": {"title": "Ethernet / interface fault", "description": "Elevated interface errors point to a physical or negotiation issue.", "signal": "Interface errors"},
    "normal": {"title": "Normal operation", "description": "Healthy synthetic telemetry with no configured anomaly.", "signal": "Baseline"},
    "malformed": {"title": "Malformed input", "description": "An invalid schema demonstrates safe validation failure handling.", "signal": "Validation gate"},
}


def load_sample(name: str) -> dict[str, Any]:
    if name not in SCENARIO_META:
        raise ValueError(f"Unknown scenario: {name}")
    with (DATA / f"{name}.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def scenario_catalog() -> list[dict[str, str]]:
    return [{"id": key, **value} for key, value in SCENARIO_META.items()]


def validate(raw: Any) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    if not isinstance(raw, dict):
        return None, ["Input must be a JSON object."]
    if raw.get("schema_version", PROTOCOL_VERSION) != PROTOCOL_VERSION:
        return None, [f"Unsupported schema_version {raw.get('schema_version')!r}; expected '{PROTOCOL_VERSION}'."]
    devices = raw.get("devices")
    if not isinstance(devices, list) or not devices:
        return None, ["'devices' must be a non-empty list."]
    normalized: list[dict[str, Any]] = []
    for index, device in enumerate(devices):
        if not isinstance(device, dict) or not isinstance(device.get("device_id"), str) or not device["device_id"].strip():
            warnings.append(f"devices[{index}] needs a valid device_id and was ignored.")
            continue
        device_id = device["device_id"].strip()
        metrics = device.get("metrics", {})
        if not isinstance(metrics, dict):
            warnings.append(f"{device_id}: metrics must be an object; device was ignored.")
            continue
        clean_metrics: dict[str, float] = {}
        for metric, value in metrics.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                clean_metrics[metric] = float(value)
            else:
                warnings.append(f"{device_id}: metric {metric!r} is not numeric and was ignored.")
        normalized.append({"device_id": device_id, "device_type": device.get("device_type", "unknown"), "segment": device.get("segment", "unspecified"), "metrics": clean_metrics})
    if not normalized:
        return None, warnings + ["No valid devices remain."]
    return {"incident_id": str(raw.get("incident_id", "INC-DEMO")), "devices": normalized}, warnings


def structured_message(agent_id: str, device_id: str, issue: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    severity = "high" if len(evidence) > 1 else "medium" if evidence else "low"
    return {
        "protocol_version": PROTOCOL_VERSION,
        "message_type": "agent_finding",
        "message_id": f"{agent_id}:{device_id}",
        "agent_id": agent_id,
        "device_id": device_id,
        "issue": issue,
        "severity": severity,
        "evidence": evidence,
        "handoff": {"from_agent": agent_id, "to_agent": "orchestrator", "channel": "structured-json", "purpose": "correlate finding with the other agent's evidence"},
    }


def performance_agent(data: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    monitored = (("latency_ms", "ms", "Latency above demo threshold"), ("packet_loss_pct", "%", "Packet loss above demo threshold"), ("jitter_ms", "ms", "Jitter above demo threshold"), ("link_utilization_pct", "%", "Link utilization above demo threshold"))
    for device in data["devices"]:
        metrics = device["metrics"]
        evidence = [{"metric": metric, "value": metrics[metric], "unit": unit, "interpretation": meaning} for metric, unit, meaning in monitored if metrics.get(metric, 0) > LIMITS[metric]]
        issue = "possible_link_congestion" if any(item["metric"] == "link_utilization_pct" for item in evidence) else "performance_degradation" if evidence else "no_performance_anomaly"
        findings.append(structured_message("performance_agent", device["device_id"], issue, evidence))
    return findings


def infrastructure_agent(data: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    monitored = (("cpu_pct", "%", "CPU utilization above demo threshold"), ("interface_errors", "count", "Interface errors elevated"), ("queue_drops", "count", "Queue drops elevated"))
    for device in data["devices"]:
        metrics = device["metrics"]
        evidence = [{"metric": metric, "value": metrics[metric], "unit": unit, "interpretation": meaning} for metric, unit, meaning in monitored if metrics.get(metric, 0) > LIMITS[metric]]
        if "wifi_signal_dbm" in metrics and metrics["wifi_signal_dbm"] < -72:
            evidence.append({"metric": "wifi_signal_dbm", "value": metrics["wifi_signal_dbm"], "unit": "dBm", "interpretation": "Wi-Fi signal is weak"})
        issue = "possible_interface_fault" if any(item["metric"] == "interface_errors" for item in evidence) else "possible_weak_wifi_signal" if any(item["metric"] == "wifi_signal_dbm" for item in evidence) else "infrastructure_stress" if evidence else "no_infrastructure_anomaly"
        findings.append(structured_message("infrastructure_agent", device["device_id"], issue, evidence))
    return findings


def _invalid_report(messages: list[str]) -> dict[str, Any]:
    return {"report_version": REPORT_VERSION, "protocol_version": PROTOCOL_VERSION, "incident_id": "INC-INVALID", "status": "input_error", "summary": {"status": "input_error", "suspected_root_cause": "Invalid telemetry; diagnosis not run.", "confidence": 0, "confidence_label": "none", "affected_devices": [], "supporting_evidence": [], "alternative_causes": [], "recommended_actions": ["Correct the JSON schema and rerun."], "limitations": messages}, "agent_findings": [], "agent_handoffs": [], "orchestration_log": [{"step": "validation", "status": "failed", "details": messages}], "validation_messages": messages}


def diagnose(raw: Any) -> dict[str, Any]:
    data, warnings = validate(raw)
    if data is None:
        return _invalid_report(warnings)
    findings = performance_agent(data) + infrastructure_agent(data)
    evidence: list[dict[str, Any]] = []
    causes: dict[str, int] = {}
    for finding in findings:
        for item in finding["evidence"]:
            evidence.append({**item, "device_id": finding["device_id"], "agent_id": finding["agent_id"]})
        if finding["evidence"]:
            causes[finding["issue"]] = causes.get(finding["issue"], 0) + 1
    if not evidence:
        cause, status, root, confidence, label, affected = "normal", "no_anomaly_detected", "No configured anomaly was detected in the supplied telemetry.", 0.70, "medium", []
        alternatives = ["Thresholds may not cover every failure mode.", "Missing metrics may hide an issue."]
    else:
        priority = ["possible_interface_fault", "possible_link_congestion", "possible_weak_wifi_signal", "infrastructure_stress", "performance_degradation"]
        cause = sorted(causes, key=lambda value: (-causes[value], priority.index(value) if value in priority else 99))[0]
        roots = {"possible_interface_fault": "Possible interface fault; elevated interface errors need verification.", "possible_link_congestion": "Likely link congestion; high utilization and/or queue drops support this explanation.", "possible_weak_wifi_signal": "Possible weak Wi-Fi signal; the signal measurement is below the demo threshold.", "infrastructure_stress": "Possible infrastructure stress; device health metrics are elevated.", "performance_degradation": "Performance degradation is observed, but the cause is not isolated."}
        root, status = roots.get(cause, "Network anomaly detected; evidence is insufficient to isolate the cause."), "diagnosed"
        affected = sorted({item["device_id"] for item in evidence})
        active_agents = {finding["agent_id"] for finding in findings if finding["evidence"]}
        confidence, label = (0.85, "high") if len(active_agents) >= 2 and len(evidence) >= 3 else (0.70, "medium") if len(active_agents) >= 2 or len(evidence) >= 2 else (0.50, "low")
        alternatives = ["An upstream bottleneck or temporary traffic burst may produce similar symptoms."] if cause == "possible_link_congestion" else ["Collect neighbouring-device metrics and timestamps to test alternative explanations."]
    actions = {"normal": ["No immediate corrective action is indicated.", "Continue monitoring against a normal baseline."], "possible_link_congestion": ["Inspect utilization and traffic distribution.", "Review queue configuration after verification."], "possible_weak_wifi_signal": ["Check access-point placement, obstructions, distance and interference.", "Compare signal quality across nearby clients."], "possible_interface_fault": ["Inspect interface counters, cable/optics, port negotiation and logs.", "Verify with another measurement before replacing hardware."], "infrastructure_stress": ["Review CPU, queue drops and interface counters.", "Check neighbouring devices and sustained load."], "performance_degradation": ["Repeat latency and packet-loss measurements.", "Compare neighbouring segments and upstream services."]}
    handoffs = [finding["handoff"] | {"message_id": finding["message_id"], "issue": finding["issue"]} for finding in findings]
    return {"report_version": REPORT_VERSION, "protocol_version": PROTOCOL_VERSION, "incident_id": data["incident_id"], "status": status, "summary": {"status": status, "suspected_root_cause": root, "confidence": confidence, "confidence_label": label, "affected_devices": affected, "supporting_evidence": evidence, "alternative_causes": alternatives, "recommended_actions": actions.get(cause, actions["performance_degradation"]), "limitations": ["Synthetic/demo thresholds; calibrate to a real network baseline.", "A probable diagnosis is not proof of a physical root cause."]}, "agent_findings": findings, "agent_handoffs": handoffs, "orchestration_log": [{"step": "validation", "status": "passed_with_warnings" if warnings else "passed", "details": warnings}, {"step": "agent_dispatch", "status": "completed", "agents": ["performance_agent", "infrastructure_agent"], "message_count": len(findings)}, {"step": "correlation", "status": "completed", "details": f"Combined {len(evidence)} evidence item(s)."}], "validation_messages": warnings}
