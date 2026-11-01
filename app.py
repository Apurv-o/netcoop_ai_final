"""HTTP interface for the NetCoop AI diagnosis workbench."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from netcoop import diagnose, load_sample, scenario_catalog

ROOT = Path(__file__).parent
app = Flask(__name__, static_folder="public", static_url_path="/public")


@app.get("/healthz")
def health() -> Any:
    return jsonify({"ok": True, "service": "netcoop-ai"})


@app.get("/api/scenarios")
def scenarios() -> Any:
    return jsonify({"scenarios": scenario_catalog()})


@app.get("/api/scenarios/<name>")
def scenario(name: str) -> Any:
    try:
        return jsonify({"scenario": name, "telemetry": load_sample(name)})
    except (ValueError, FileNotFoundError):
        return jsonify({"error": "Unknown scenario."}), 404


@app.post("/api/diagnose")
def run_diagnosis() -> Any:
    if not request.is_json:
        return jsonify({"error": "Expected a JSON request body."}), 415
    try:
        payload = request.get_json(silent=False)
    except Exception as exc:  # Flask's decoder error varies by version.
        return jsonify({"error": f"Could not parse JSON: {exc}"}), 400
    # The scenario endpoint intentionally returns {scenario, telemetry} for
    # inspection. Accept that same envelope so callers cannot accidentally
    # send the catalog wrapper instead of the telemetry body.
    if isinstance(payload, dict) and isinstance(payload.get("telemetry"), dict):
        payload = payload["telemetry"]
    return jsonify(diagnose(payload))


@app.get("/")
def index() -> Any:
    return send_from_directory(ROOT / "public", "index.html")


@app.get("/<path:path>")
def public_file(path: str) -> Any:
    candidate = ROOT / "public" / path
    if candidate.is_file():
        return send_from_directory(ROOT / "public", path)
    return send_from_directory(ROOT / "public", "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3000"))
    app.run(host="0.0.0.0", port=port, debug=False)
