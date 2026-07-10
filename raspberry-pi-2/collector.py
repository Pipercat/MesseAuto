from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify

PI1_URL = os.getenv("MESSEAUTO_PI1_URL", "http://127.0.0.1:5000").rstrip("/")
POLL_SECONDS = float(os.getenv("MESSEAUTO_POLL_SECONDS", "1.0"))
DB_PATH = Path(os.getenv("MESSEAUTO_DB_PATH", "telemetry.db"))

app = Flask(__name__)
latest_state: dict[str, Any] = {
    "connected": False,
    "last_update": None,
    "state": {},
}


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as connection:
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
        connection.commit()


def save_state(state: dict[str, Any]) -> None:
    sensors = state.get("sensors", {})
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO telemetry (
                created_at,
                temperature_c,
                seat_distance_cm,
                payload_json
            ) VALUES (?, ?, ?, ?)
            """,
            (
                time.time(),
                sensors.get("temperature_c"),
                sensors.get("seat_distance_cm"),
                json.dumps(state, ensure_ascii=False),
            ),
        )
        connection.commit()


def poll_once() -> None:
    response = requests.get(f"{PI1_URL}/api/state", timeout=2)
    response.raise_for_status()
    state = response.json()

    latest_state.update({
        "connected": True,
        "last_update": time.time(),
        "state": state,
    })
    save_state(state)


def collector_loop() -> None:
    while True:
        try:
            poll_once()
        except (requests.RequestException, ValueError) as exc:
            latest_state.update({
                "connected": False,
                "last_update": time.time(),
                "error": str(exc),
            })
        time.sleep(POLL_SECONDS)


@app.get("/api/state")
def api_state():
    return jsonify(latest_state)


@app.get("/api/history")
def api_history():
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT created_at, temperature_c, seat_distance_cm
            FROM telemetry
            ORDER BY id DESC
            LIMIT 300
            """
        ).fetchall()
    return jsonify([dict(row) for row in rows])


if __name__ == "__main__":
    import threading

    init_db()
    threading.Thread(target=collector_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5001, threaded=True)
