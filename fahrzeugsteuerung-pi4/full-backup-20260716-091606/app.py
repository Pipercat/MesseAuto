from __future__ import annotations

import atexit
import os
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from gpio_controller import create_controller


PROJECT_DIR = Path(__file__).resolve().parent
WEB_DIR = PROJECT_DIR / "web"

app = Flask(__name__, static_folder=None)
controller = create_controller()
atexit.register(controller.shutdown)


def json_error(message: str, status_code: int = 400):
    response = jsonify({"ok": False, "error": message})
    response.status_code = status_code
    return response


def request_data() -> dict[str, Any]:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@app.errorhandler(ValueError)
def handle_value_error(error: ValueError):
    return json_error(str(error), 400)


@app.errorhandler(RuntimeError)
def handle_runtime_error(error: RuntimeError):
    return json_error(str(error), 500)


@app.get("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.get("/api/state")
def api_state():
    return jsonify({"ok": True, "state": controller.state()})


@app.get("/api/config")
def api_config():
    return jsonify({"ok": True, "state": controller.state()})


@app.get("/api/metrics")
def api_metrics():
    return jsonify({"ok": True, "metrics": controller.metrics()})


@app.post("/api/output/<output_id>")
def api_set_output(output_id: str):
    data = request_data()
    if "active" not in data:
        return json_error("Feld 'active' fehlt")
    return jsonify({"ok": True, "state": controller.set_output(output_id, bool(data["active"]))})


@app.post("/api/outputs")
def api_set_outputs():
    data = request_data()
    changes: dict[str, bool] = {}

    if isinstance(data.get("outputs"), dict):
        changes = {str(output_id): bool(active) for output_id, active in data["outputs"].items()}
    elif isinstance(data.get("ids"), list) and "active" in data:
        changes = {str(output_id): bool(data["active"]) for output_id in data["ids"]}
    else:
        return json_error("Erwarte 'outputs' oder 'ids' plus 'active'")

    return jsonify({"ok": True, "state": controller.set_outputs(changes)})


@app.post("/api/motor")
def api_set_motor():
    data = request_data()
    if "percent" not in data:
        return json_error("Feld 'percent' fehlt")
    return jsonify({"ok": True, "state": controller.set_motor(data["percent"])})


@app.post("/api/reset")
def api_reset():
    return jsonify({"ok": True, "state": controller.reset()})


@app.get("/<path:path>")
def web_file(path: str):
    target = (WEB_DIR / path).resolve()
    if not str(target).startswith(str(WEB_DIR.resolve())) or not target.exists() or not target.is_file():
        return json_error("Datei nicht gefunden", 404)
    return send_from_directory(WEB_DIR, path)


if __name__ == "__main__":
    host = os.getenv("MESSEAUTO_HOST", "0.0.0.0")
    port = int(os.getenv("MESSEAUTO_PORT", "8000"))
    debug = os.getenv("MESSEAUTO_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
    app.run(host=host, port=port, debug=debug, threaded=True)
