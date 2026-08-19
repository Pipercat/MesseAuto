from __future__ import annotations

import os
from typing import Any

from flask import Flask, jsonify, render_template, request

from admin_actions import RESTARTABLE_SERVICES, reboot_pi2, restart_service, shutdown_pi2
from database import init_db, latest_dashboard_data, live_curves, live_signal_traces, mark_database_online, store_event
from system_metrics import service_status, system_metrics


app = Flask(__name__)
init_db()


@app.after_request
def add_cors_headers(response):
    # Pi 1s Admin-Uebersicht laedt Pi-2-Metriken per Cross-Origin-Fetch aus
    # dem Browser; nur lesende GET-Endpunkte sind betroffen, keine Aktionen
    # werden dadurch von aussen freigegeben.
    response.headers["Access-Control-Allow-Origin"] = "http://10.42.0.11:8000"
    return response


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


@app.get("/api/live-signals")
def api_live_signals():
    window = int(request.args.get("window_seconds", 60))
    return jsonify({"ok": True, "data": live_signal_traces(window)})


@app.get("/api/live-curves")
def api_live_curves():
    window = int(request.args.get("window_seconds", 60))
    return jsonify({"ok": True, "data": live_curves(window)})


@app.get("/api/admin/metrics")
def api_admin_metrics():
    return jsonify({"ok": True, "metrics": system_metrics()})


@app.get("/api/admin/services")
def api_admin_services():
    units = ["messeauto-database.service"]
    return jsonify({"ok": True, "services": service_status(units), "restartable": list(RESTARTABLE_SERVICES)})


@app.post("/api/admin/service/restart")
def api_admin_service_restart():
    data = request_data()
    unit_name = str(data.get("service") or "")
    result = restart_service(unit_name)
    return jsonify(result), (200 if result["ok"] else 400)


@app.post("/api/admin/reboot")
def api_admin_reboot():
    result = reboot_pi2()
    return jsonify(result), (200 if result["ok"] else 400)


@app.post("/api/admin/shutdown")
def api_admin_shutdown():
    result = shutdown_pi2()
    return jsonify(result), (200 if result["ok"] else 400)


@app.get("/health")
def health():
    mark_database_online()
    return jsonify({"ok": True, "service": "messeauto-database-pi"})


if __name__ == "__main__":
    host = os.getenv("MESSEAUTO_DB_HOST", "0.0.0.0")
    port = int(os.getenv("MESSEAUTO_DB_PORT", "9000"))
    debug = os.getenv("MESSEAUTO_DB_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
    app.run(host=host, port=port, debug=debug, threaded=True)
