from __future__ import annotations

import os
from typing import Any

from flask import Flask, jsonify, render_template, request

from database import init_db, latest_dashboard_data, mark_database_online, store_event


app = Flask(__name__)
init_db()


def request_data() -> dict[str, Any]:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@app.get("/")
def dashboard():
    return render_template("dashboard.html", data=latest_dashboard_data())


@app.get("/api/dashboard")
def api_dashboard():
    return jsonify({"ok": True, "data": latest_dashboard_data()})


@app.post("/api/events")
def api_events():
    data = request_data()
    event_type = str(data.get("event_type") or data.get("type") or "unknown")
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else data
    event_id = store_event(event_type, payload)
    return jsonify({"ok": True, "event_id": event_id})


@app.get("/health")
def health():
    mark_database_online()
    return jsonify({"ok": True, "service": "messeauto-database-pi"})


if __name__ == "__main__":
    host = os.getenv("MESSEAUTO_DB_HOST", "0.0.0.0")
    port = int(os.getenv("MESSEAUTO_DB_PORT", "9000"))
    debug = os.getenv("MESSEAUTO_DB_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
    app.run(host=host, port=port, debug=debug, threaded=True)
