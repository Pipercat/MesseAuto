from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, render_template, request

PI1_URL = os.getenv("MESSEAUTO_PI1_URL", "http://127.0.0.1:5000").rstrip("/")
POLL_SECONDS = max(0.2, float(os.getenv("MESSEAUTO_POLL_SECONDS", "1.0")))
DB_PATH = Path(os.getenv("MESSEAUTO_DB_PATH", "telemetry.db"))
REQUEST_TIMEOUT = float(os.getenv("MESSEAUTO_REQUEST_TIMEOUT", "2.0"))

app = Flask(__name__)
state_lock = threading.RLock()
latest_state: dict[str, Any] = {
    "connected": False,
    "last_update": None,
    "last_success": None,
    "error": None,
    "state": {},
    "poll_seconds": POLL_SECONDS,
    "pi1_url": PI1_URL,
}


def db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db_connection() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                temperature_c REAL,
                seat_distance_cm REAL,
                payload_json TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_created_at ON telemetry(created_at)")
        connection.commit()


def save_state(state: dict[str, Any]) -> None:
    sensors = state.get("sensors", {})
    with db_connection() as connection:
        connection.execute(
            """
            INSERT INTO telemetry (created_at, temperature_c, seat_distance_cm, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                time.time(),
                sensors.get("temperature_c"),
                sensors.get("seat_distance_cm"),
                json.dumps(state, ensure_ascii=False, separators=(",", ":")),
            ),
        )
        connection.commit()


def poll_once() -> None:
    response = requests.get(f"{PI1_URL}/api/state", timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    state = response.json()
    if not isinstance(state, dict):
        raise ValueError("Pi 1 hat keinen gültigen Objekt-Zustand geliefert")
    now = time.time()
    with state_lock:
        latest_state.update({
            "connected": True,
            "last_update": now,
            "last_success": now,
            "error": None,
            "state": state,
        })
    save_state(state)


def collector_loop() -> None:
    while True:
        started = time.monotonic()
        try:
            poll_once()
        except (requests.RequestException, ValueError, OSError) as exc:
            with state_lock:
                latest_state.update({"connected": False, "last_update": time.time(), "error": str(exc)})
        elapsed = time.monotonic() - started
        time.sleep(max(0.05, POLL_SECONDS - elapsed))


def telemetry_stats() -> dict[str, Any]:
    with db_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS records, MAX(created_at) AS newest,
                   AVG(temperature_c) AS avg_temperature_c,
                   MIN(temperature_c) AS min_temperature_c,
                   MAX(temperature_c) AS max_temperature_c
            FROM telemetry
            """
        ).fetchone()
    return dict(row)


@app.get("/")
def display():
    return render_template("index.html")


@app.get("/api/health")
def api_health():
    return jsonify({"ok": True, "service": "messeauto-pi2", "time": time.time()})


@app.get("/api/state")
def api_state():
    with state_lock:
        return jsonify(json.loads(json.dumps(latest_state)))


@app.get("/api/history")
def api_history():
    try:
        limit = min(2000, max(1, int(request.args.get("limit", "300"))))
    except ValueError:
        return jsonify({"error": "limit muss eine Zahl sein"}), 400
    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT created_at, temperature_c, seat_distance_cm
            FROM telemetry ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.get("/api/stats")
def api_stats():
    return jsonify(telemetry_stats())


@app.post("/api/tests/<test_name>")
def api_test(test_name: str):
    tests = {
        "lights": ["lowBeam", "highBeam", "underbody"],
        "indicators": ["leftIndicator", "rightIndicator", "hazard"],
        "fan": ["fan"],
        "all": ["lowBeam", "highBeam", "underbody", "leftIndicator", "rightIndicator", "fan"],
    }
    if test_name == "all_off":
        response = requests.post(f"{PI1_URL}/api/all-off", timeout=REQUEST_TIMEOUT)
        return (response.content, response.status_code, {"Content-Type": "application/json"})
    if test_name not in tests:
        return jsonify({"error": "Unbekannter Test"}), 404

    results = []
    for function_id in tests[test_name]:
        response = requests.post(f"{PI1_URL}/api/functions/{function_id}/toggle", timeout=REQUEST_TIMEOUT)
        results.append({"function": function_id, "status": response.status_code})
        time.sleep(0.15)
    return jsonify({"ok": True, "test": test_name, "results": results})


if __name__ == "__main__":
    init_db()
    threading.Thread(target=collector_loop, daemon=True, name="pi1-collector").start()
    app.run(host="0.0.0.0", port=5001, threaded=True)
