from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DB_PATH = Path("vehicle_tests.db")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_name TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                last_seen TEXT,
                status TEXT NOT NULL DEFAULT 'unknown',
                message TEXT
            );

            CREATE TABLE IF NOT EXISTS raw_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                source_device TEXT,
                payload TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sensor_measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source_device TEXT NOT NULL DEFAULT 'esp32_sensor',
                temperature_c REAL,
                seat_distance_mm REAL,
                seat_position TEXT,
                test_run_id INTEGER,
                valid INTEGER NOT NULL DEFAULT 1,
                message TEXT
            );

            CREATE TABLE IF NOT EXISTS seat_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                test_run_id INTEGER,
                target_position TEXT NOT NULL,
                expected_min_mm REAL,
                expected_max_mm REAL,
                actual_distance_mm REAL,
                passed INTEGER NOT NULL,
                message TEXT
            );

            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                test_name TEXT NOT NULL,
                passed INTEGER NOT NULL,
                severity TEXT,
                message TEXT,
                payload TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                error_type TEXT NOT NULL,
                severity TEXT,
                function_name TEXT,
                message TEXT NOT NULL,
                payload TEXT
            );
            """
        )
        seed_devices(connection)
        mark_device(connection, "database-pi", "connected", "Datenbank-Pi aktiv")


def seed_devices(connection: sqlite3.Connection) -> None:
    devices = {
        "touchscreen-pi": "Fahrzeugbedienung",
        "database-pi": "Datenbank und Auswertung",
        "esp32_actor": "Aktorsteuerung",
        "esp32_sensor": "Temperatur- und Sitzsensorik",
    }
    for device_name, role in devices.items():
        connection.execute(
            """
            INSERT INTO devices (device_name, role, status)
            VALUES (?, ?, 'unknown')
            ON CONFLICT(device_name) DO NOTHING
            """,
            (device_name, role),
        )


def store_event(event_type: str, payload: dict[str, Any]) -> int:
    timestamp = payload.get("timestamp") or payload.get("timestamp_utc") or utc_now()
    source_device = detect_source_device(event_type, payload)
    payload_text = json.dumps(payload, ensure_ascii=False)

    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO raw_events (timestamp, event_type, source_device, payload)
            VALUES (?, ?, ?, ?)
            """,
            (timestamp, event_type, source_device, payload_text),
        )
        event_id = int(cursor.lastrowid)
        route_event(connection, event_type, payload, timestamp, source_device)
        return event_id


def route_event(connection: sqlite3.Connection, event_type: str, payload: dict[str, Any], timestamp: str, source_device: str | None) -> None:
    if source_device:
        upsert_device(connection, source_device, str(payload.get("status") or "connected"), payload.get("message"))

    if event_type == "vehicle_heartbeat":
        upsert_device(connection, "touchscreen-pi", "connected", payload.get("message") or "Fahrzeug-Pi sendet Heartbeat")
        actor = payload.get("esp32_actor")
        if isinstance(actor, dict):
            upsert_device(
                connection,
                "esp32_actor",
                str(actor.get("status") or ("connected" if actor.get("connected") else "unknown")),
                actor.get("message") or actor.get("last_raw_line"),
            )

    if event_type == "actor_status":
        upsert_device(
            connection,
            "esp32_actor",
            str(payload.get("status") or ("connected" if payload.get("connected") or payload.get("serial_active") else "unknown")),
            payload.get("message") or payload.get("last_raw_line"),
        )

    sensor = payload.get("sensor") if isinstance(payload.get("sensor"), dict) else payload
    if event_type in {"sensor_measurement", "sensor_status"} or any(key in sensor for key in ("temperature_c", "seat_distance_mm")):
        sensor_status = "connected" if not sensor.get("errors") and not sensor.get("error_type") else "error"
        upsert_device(connection, "esp32_sensor", sensor_status, sensor.get("message"))
        insert_sensor_measurement(connection, sensor, timestamp)

    if event_type == "seat_test" or payload.get("test") == "seat":
        insert_seat_test(connection, payload, timestamp)

    if event_type in {"test_result", "seat_test"} or "passed" in payload:
        insert_test_result(connection, event_type, payload, timestamp)

    if payload.get("severity") in {"high", "error"} or payload.get("error_type"):
        insert_error(connection, payload, timestamp)


def insert_sensor_measurement(connection: sqlite3.Connection, sensor: dict[str, Any], timestamp: str) -> None:
    connection.execute(
        """
        INSERT INTO sensor_measurements (
            timestamp, source_device, temperature_c, seat_distance_mm,
            seat_position, test_run_id, valid, message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp,
            sensor.get("source_device") or "esp32_sensor",
            sensor.get("temperature_c"),
            sensor.get("seat_distance_mm"),
            sensor.get("seat_position"),
            sensor.get("test_run_id"),
            1 if sensor.get("valid", True) else 0,
            sensor.get("message") or "; ".join(sensor.get("errors", []) if isinstance(sensor.get("errors"), list) else []),
        ),
    )


def insert_seat_test(connection: sqlite3.Connection, payload: dict[str, Any], timestamp: str) -> None:
    target = payload.get("target") or {}
    sensor = payload.get("sensor") or {}
    connection.execute(
        """
        INSERT INTO seat_tests (
            timestamp, test_run_id, target_position, expected_min_mm,
            expected_max_mm, actual_distance_mm, passed, message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp,
            payload.get("test_run_id"),
            payload.get("target_position") or target.get("label") or "unknown",
            target.get("min"),
            target.get("max"),
            sensor.get("seat_distance_mm") or payload.get("actual_distance_mm"),
            1 if payload.get("passed") else 0,
            payload.get("message"),
        ),
    )


def insert_test_result(connection: sqlite3.Connection, event_type: str, payload: dict[str, Any], timestamp: str) -> None:
    connection.execute(
        """
        INSERT INTO test_results (timestamp, test_name, passed, severity, message, payload)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp,
            payload.get("test") or event_type,
            1 if payload.get("passed") else 0,
            payload.get("severity"),
            payload.get("message"),
            json.dumps(payload, ensure_ascii=False),
        ),
    )


def insert_error(connection: sqlite3.Connection, payload: dict[str, Any], timestamp: str) -> None:
    connection.execute(
        """
        INSERT INTO errors (timestamp, error_type, severity, function_name, message, payload)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp,
            payload.get("error_type") or payload.get("test") or "unknown",
            payload.get("severity"),
            payload.get("function_name"),
            payload.get("message") or "Unbekannter Fehler",
            json.dumps(payload, ensure_ascii=False),
        ),
    )


def upsert_device(connection: sqlite3.Connection, device_name: str, status: str, message: str | None = None) -> None:
    connection.execute(
        """
        INSERT INTO devices (device_name, role, last_seen, status, message)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(device_name) DO UPDATE SET
            last_seen = excluded.last_seen,
            status = excluded.status,
            message = excluded.message
        """,
        (device_name, device_name, utc_now(), status, message),
    )


def mark_device(connection: sqlite3.Connection, device_name: str, status: str, message: str | None = None) -> None:
    upsert_device(connection, device_name, status, message)


def mark_database_online() -> None:
    with connect() as connection:
        upsert_device(connection, "database-pi", "connected", "Datenbank-Pi aktiv")


def detect_source_device(event_type: str, payload: dict[str, Any]) -> str | None:
    if payload.get("source_device"):
        return str(payload["source_device"])
    if event_type == "database_heartbeat":
        return "database-pi"
    if event_type == "actor_status":
        return "esp32_actor"
    if isinstance(payload.get("sensor"), dict):
        return "esp32_sensor"
    if event_type.startswith("vehicle_"):
        return "touchscreen-pi"
    if event_type in {"sensor_measurement", "sensor_status", "seat_test"}:
        return "esp32_sensor"
    return payload.get("device")


def latest_dashboard_data() -> dict[str, Any]:
    with connect() as connection:
        devices = fetch_all(connection, "SELECT * FROM devices ORDER BY device_name")
        sensor_device = next((device for device in devices if device["device_name"] == "esp32_sensor"), None)
        actor_device = next((device for device in devices if device["device_name"] == "esp32_actor"), None)
        analytics = build_analytics(connection)
        latest_tests = [
            format_test_result(row)
            for row in fetch_all(connection, "SELECT * FROM test_results ORDER BY id DESC LIMIT 3")
        ]
        return {
            "devices": devices,
            "latest_sensor": fetch_one(connection, "SELECT * FROM sensor_measurements ORDER BY id DESC LIMIT 1"),
            "latest_tests": latest_tests,
            "seat_tests": fetch_all(connection, "SELECT * FROM seat_tests ORDER BY id DESC LIMIT 10"),
            "errors": fetch_all(connection, "SELECT * FROM errors ORDER BY id DESC LIMIT 10"),
            "sensor_status_message": sensor_message(sensor_device),
            "actor_status_message": device_message(actor_device, "Aktor-ESP noch nicht erkannt"),
            "analytics": analytics,
            "counts": {
                "events": scalar(connection, "SELECT COUNT(*) FROM raw_events"),
                "vehicle_events": scalar(
                    connection,
                    """
                    SELECT COUNT(*) FROM raw_events
                    WHERE event_type IN (
                        'vehicle_heartbeat', 'vehicle_output', 'vehicle_outputs',
                        'vehicle_motor', 'vehicle_reset'
                    )
                    """,
                ),
                "sensor_measurements": scalar(connection, "SELECT COUNT(*) FROM sensor_measurements"),
                "seat_tests": scalar(connection, "SELECT COUNT(*) FROM seat_tests"),
                "errors": scalar(connection, "SELECT COUNT(*) FROM errors"),
                "tests": scalar(connection, "SELECT COUNT(*) FROM test_results"),
                "passed_tests": scalar(connection, "SELECT COUNT(*) FROM test_results WHERE passed = 1"),
            },
        }


def build_analytics(connection: sqlite3.Connection) -> dict[str, Any]:
    raw_events = fetch_all(
        connection,
        """
        SELECT id, timestamp, event_type, source_device, payload
        FROM raw_events
        ORDER BY id DESC
        LIMIT 240
        """,
    )
    chronological = list(reversed(raw_events))

    event_types = fetch_all(
        connection,
        """
        SELECT event_type AS label, COUNT(*) AS value
        FROM raw_events
        GROUP BY event_type
        ORDER BY value DESC, event_type
        LIMIT 8
        """,
    )

    sensor_history = fetch_all(
        connection,
        """
        SELECT timestamp, temperature_c, seat_distance_mm, seat_position
        FROM sensor_measurements
        ORDER BY id DESC
        LIMIT 32
        """,
    )
    sensor_history = [format_sensor_point(row) for row in reversed(sensor_history)]

    motor_history: list[dict[str, Any]] = []
    output_history: list[dict[str, Any]] = []
    event_timeline: dict[str, int] = {}
    vehicle_timeline: dict[str, int] = {}
    function_usage: dict[str, int] = {}
    current_outputs: dict[str, bool] = {}
    current_motor_percent: float | None = None

    for event in chronological:
        payload = parse_payload(event.get("payload"))
        event_type = event.get("event_type") or ""
        timestamp = str(event.get("timestamp") or "")
        label = short_time(timestamp)
        bucket = minute_bucket(timestamp)
        event_timeline[bucket] = event_timeline.get(bucket, 0) + 1
        if event_type.startswith("vehicle_"):
            vehicle_timeline[bucket] = vehicle_timeline.get(bucket, 0) + 1

        motor_percent = first_number(payload, ("percent", "motor_percent", "motorPercent", "motor"))
        if motor_percent is None:
            motor_percent = nested_number(payload, "motor_percent")
        if motor_percent is None:
            motor_percent = nested_number(payload, "motorPercent")
        if motor_percent is not None:
            current_motor_percent = clamp_number(motor_percent, 0, 100)
            motor_history.append({"label": label, "value": current_motor_percent})

        active_count = first_number(payload, ("active_output_count", "activeOutputCount"))
        if active_count is None and isinstance(payload.get("active_outputs"), list):
            active_count = len(payload["active_outputs"])
            current_outputs = {str(output_id): True for output_id in payload["active_outputs"]}
        if active_count is None and isinstance(payload.get("outputs"), dict):
            active_count = sum(1 for value in payload["outputs"].values() if value)
            current_outputs.update({str(output_id): bool(active) for output_id, active in payload["outputs"].items()})
        if active_count is None:
            active_outputs = nested_list(payload, "active_outputs") or nested_list(payload, "activeOutputs")
            if active_outputs is not None:
                active_count = len(active_outputs)
                current_outputs = {str(output_id): True for output_id in active_outputs}
        if active_count is None:
            outputs = nested_dict(payload, "outputs")
            if outputs is not None:
                active_count = sum(1 for value in outputs.values() if value)
                current_outputs.update({str(output_id): bool(active) for output_id, active in outputs.items()})
        if active_count is not None:
            output_history.append({"label": label, "value": clamp_number(active_count, 0, 12)})

        if event_type == "vehicle_output":
            output_id = str(payload.get("output_id") or "")
            if output_id:
                function_usage[output_id] = function_usage.get(output_id, 0) + 1
                if "active" in payload:
                    current_outputs[output_id] = bool(payload.get("active"))
        elif event_type == "vehicle_outputs" and isinstance(payload.get("outputs"), dict):
            for output_id, active in payload["outputs"].items():
                key = str(output_id)
                function_usage[key] = function_usage.get(key, 0) + 1
                current_outputs[key] = bool(active)
        elif event_type == "vehicle_reset":
            current_outputs = {output_id: False for output_id in current_outputs}
            current_motor_percent = 0

    recent_events = []
    for event in raw_events[:4]:
        payload = parse_payload(event.get("payload"))
        recent_events.append(
            {
                "time": short_time(str(event.get("timestamp") or "")),
                "type": event_label(event.get("event_type") or "-"),
                "source": source_label(event.get("source_device") or payload.get("source_device") or "-"),
                "message": event_message(payload),
            }
        )

    latest_vehicle_events = []
    for event in raw_events:
        event_type = str(event.get("event_type") or "")
        if event_type not in {"vehicle_output", "vehicle_outputs", "vehicle_motor", "vehicle_reset", "test_result"}:
            continue
        payload = parse_payload(event.get("payload"))
        latest_vehicle_events.append(
            {
                "time": short_time(str(event.get("timestamp") or "")),
                "type": vehicle_event_label(event_type),
                "function": vehicle_function_from_payload(event_type, payload),
                "value": vehicle_value_from_payload(event_type, payload),
            }
        )
        if len(latest_vehicle_events) >= 4:
            break

    test_summary = fetch_all(
        connection,
        """
        SELECT test_name AS label,
               SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) AS passed,
               SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) AS failed,
               COUNT(*) AS total
        FROM test_results
        GROUP BY test_name
        ORDER BY total DESC, test_name
        LIMIT 8
        """,
    )
    function_status = [
        {
            "id": output_id,
            "label": output_label(output_id),
            "active": bool(current_outputs.get(output_id)),
            "usage": function_usage.get(output_id, 0),
        }
        for output_id in (
            "underbody",
            "lowBeam",
            "highBeam",
            "indicatorLeft",
            "indicatorRight",
            "hazard",
            "fan",
            "freeOne",
            "freeTwo",
        )
    ]

    function_usage_rows = [
        {"label": output_label(row["id"]), "value": row["usage"]}
        for row in sorted(function_status, key=lambda item: item["usage"], reverse=True)
        if row["usage"] > 0
    ][:6]

    active_functions = [row for row in function_status if row["active"]]
    visible_function_status = sorted(
        function_status,
        key=lambda item: (not item["active"], -int(item["usage"]), item["label"]),
    )[:4]

    return {
        "eventTypes": [{"label": row["label"], "value": row["value"]} for row in event_types],
        "eventTimeline": [{"label": key, "value": value} for key, value in sorted(event_timeline.items())[-18:]],
        "vehicleTimeline": [{"label": key, "value": value} for key, value in sorted(vehicle_timeline.items())[-18:]],
        "functionUsage": function_usage_rows,
        "functionStatus": visible_function_status,
        "latestVehicleEvents": latest_vehicle_events,
        "sensorHistory": sensor_history,
        "motorHistory": motor_history[-32:],
        "outputHistory": output_history[-32:],
        "recentEvents": recent_events,
        "testSummary": test_summary,
        "currentVehicle": {
            "activeOutputCount": len(active_functions),
            "activeOutputs": [row["label"] for row in active_functions],
            "motorPercent": int(current_motor_percent or 0),
        },
    }


def parse_payload(payload_text: Any) -> dict[str, Any]:
    if isinstance(payload_text, dict):
        return payload_text
    if not isinstance(payload_text, str) or not payload_text:
        return {}
    try:
        payload = json.loads(payload_text)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def format_sensor_point(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": short_time(str(row.get("timestamp") or "")),
        "temperature": none_or_number(row.get("temperature_c")),
        "distance": none_or_number(row.get("seat_distance_mm")),
        "position": row.get("seat_position") or "-",
    }


def format_test_result(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **dict(row),
        "display_time": short_time(str(row.get("timestamp") or "")),
        "display_name": concise_test_name(str(row.get("test_name") or "Test")),
        "display_result": "OK" if row.get("passed") else "Fehler",
        "display_message": concise_test_message(str(row.get("message") or "")),
    }


def concise_test_name(value: str) -> str:
    labels = {
        "Gesamttest": "Gesamttest",
        "gesamt": "Gesamttest",
        "all": "Gesamttest",
    }
    return labels.get(value, value[:18])


def concise_test_message(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        return "-"
    if "abgeschlossen" in normalized:
        return "abgeschlossen"
    if "bestanden" in normalized or normalized == "ok":
        return "bestanden"
    if "fehler" in normalized:
        return "Fehler pruefen"
    return value[:22]


def event_message(payload: dict[str, Any]) -> str:
    for key in ("message", "status", "type", "test", "output_id"):
        value = payload.get(key)
        if value not in (None, ""):
            return message_label(str(value))
    if isinstance(payload.get("active_outputs"), list):
        outputs = payload["active_outputs"]
        return f"{len(outputs)} Ausgänge aktiv"
    if isinstance(payload.get("outputs"), dict):
        outputs = [key for key, active in payload["outputs"].items() if active]
        return ", ".join(outputs) if outputs else "alle aus"
    return "-"


def event_label(value: str) -> str:
    labels = {
        "actor_status": "ESP",
        "vehicle_heartbeat": "Heartbeat",
        "vehicle_output": "Ausgang",
        "vehicle_outputs": "Ausgaenge",
        "vehicle_motor": "Motor",
        "test_result": "Test",
        "sensor_measurement": "Sensor",
        "sensor_status": "Sensor",
    }
    return labels.get(value, value.replace("_", " ")[:12])


def source_label(value: str) -> str:
    labels = {
        "esp32_actor": "ESP-Aktor",
        "esp32_sensor": "ESP-Sensor",
        "touchscreen-pi": "Touch-Pi",
        "database-pi": "DB-Pi",
    }
    return labels.get(value, value.replace("_", "-")[:12])


def message_label(value: str) -> str:
    if "USB erkannt" in value:
        return "USB erkannt"
    if value == "usb_detected":
        return "USB erkannt"
    if value == "connected":
        return "verbunden"
    if value == "unknown":
        return "unbekannt"
    return value


def output_label(output_id: str) -> str:
    labels = {
        "underbody": "Unterboden",
        "lowBeam": "Abblendlicht",
        "highBeam": "Fernlicht",
        "indicatorLeft": "Blinker L",
        "indicatorRight": "Blinker R",
        "hazard": "Warnblinker",
        "fan": "Luefter",
        "freeOne": "Frei 1",
        "freeTwo": "Frei 2",
    }
    return labels.get(output_id, output_id)


def vehicle_event_label(event_type: str) -> str:
    labels = {
        "vehicle_output": "Funktion",
        "vehicle_outputs": "Funktionen",
        "vehicle_motor": "Motor",
        "vehicle_reset": "Reset",
        "vehicle_heartbeat": "Heartbeat",
        "test_result": "Test",
    }
    return labels.get(event_type, event_type.replace("_", " "))


def vehicle_function_from_payload(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "vehicle_output":
        return output_label(str(payload.get("output_id") or "-"))
    if event_type == "vehicle_outputs":
        return "Alle Funktionen"
    if event_type == "vehicle_motor":
        return "Motor-PWM"
    if event_type == "vehicle_reset":
        return "Alles"
    if event_type == "test_result":
        return str(payload.get("test") or "Test")
    return "Fahrzeug"


def vehicle_value_from_payload(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "vehicle_output":
        return "an" if payload.get("active") else "aus"
    if event_type == "vehicle_outputs":
        outputs = payload.get("outputs")
        if isinstance(outputs, dict):
            active = sum(1 for value in outputs.values() if value)
            return f"{active} aktiv"
    if event_type == "vehicle_motor":
        percent = none_or_number(payload.get("percent"))
        return f"{int(percent or 0)} %"
    if event_type == "vehicle_reset":
        return "zurueck"
    if event_type == "vehicle_heartbeat":
        active_count = none_or_number(payload.get("active_output_count"))
        motor = none_or_number(payload.get("motor_percent"))
        return f"{int(active_count or 0)} aktiv / {int(motor or 0)} %"
    if event_type == "test_result":
        return "OK" if payload.get("passed") else "Fehler"
    return "-"


def first_number(payload: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = none_or_number(payload.get(key))
        if value is not None:
            return value
    return None


def nested_number(payload: dict[str, Any], key: str) -> float | None:
    stack: list[Any] = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if key in current:
                return none_or_number(current[key])
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return None


def nested_list(payload: dict[str, Any], key: str) -> list[Any] | None:
    value = nested_value(payload, key)
    return value if isinstance(value, list) else None


def nested_dict(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = nested_value(payload, key)
    return value if isinstance(value, dict) else None


def nested_value(payload: dict[str, Any], key: str) -> Any:
    stack: list[Any] = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if key in current:
                return current[key]
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return None


def none_or_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def clamp_number(value: Any, minimum: float, maximum: float) -> float:
    number = none_or_number(value)
    if number is None:
        return minimum
    return max(minimum, min(maximum, number))


def short_time(timestamp: str) -> str:
    if "T" in timestamp:
        return timestamp.split("T", 1)[1][:8]
    return timestamp[:8] if timestamp else "--:--"


def minute_bucket(timestamp: str) -> str:
    if "T" in timestamp:
        return timestamp.split("T", 1)[1][:5]
    return timestamp[:5] if timestamp else "--:--"


def sensor_message(device: dict[str, Any] | None) -> str:
    if not device or device.get("status") in {None, "unknown"}:
        return "Kein Sensor-USB erkannt"
    return device.get("message") or "Sensor-ESP verbunden"


def device_message(device: dict[str, Any] | None, fallback: str) -> str:
    if not device or device.get("status") in {None, "unknown"}:
        return fallback
    return device.get("message") or str(device.get("status"))


LIVE_SIGNALS = (
    "underbody",
    "lowBeam",
    "highBeam",
    "indicatorLeft",
    "indicatorRight",
    "hazard",
    "fan",
)


def live_signal_traces(window_seconds: int = 60) -> dict[str, Any]:
    """Event-based digital live traces for Screen 2 (MA-07-001/001A/001B/001D).

    Reconstructs on/off transitions per signal from the existing
    vehicle_output(s) event log instead of a periodic average - a signal
    change appears at its real event timestamp, not smoothed.
    """

    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - window_seconds

    with connect() as connection:
        rows = fetch_all(
            connection,
            """
            SELECT timestamp, event_type, payload FROM raw_events
            WHERE event_type IN ('vehicle_output', 'vehicle_outputs')
            ORDER BY timestamp ASC
            """,
        )

    transitions: dict[str, list[dict[str, Any]]] = {signal: [] for signal in LIVE_SIGNALS}
    current_state: dict[str, bool] = {signal: False for signal in LIVE_SIGNALS}
    since_ms: dict[str, float] = {signal: now.timestamp() * 1000 for signal in LIVE_SIGNALS}
    on_time_ms: dict[str, float] = {signal: 0.0 for signal in LIVE_SIGNALS}
    activation_count: dict[str, int] = {signal: 0 for signal in LIVE_SIGNALS}

    for row in rows:
        payload = parse_payload(row["payload"])
        try:
            ts = datetime.fromisoformat(row["timestamp"]).timestamp()
        except ValueError:
            continue

        changes: dict[str, bool] = {}
        if row["event_type"] == "vehicle_output" and "output_id" in payload:
            changes[str(payload["output_id"])] = bool(payload.get("active"))
        elif row["event_type"] == "vehicle_outputs" and isinstance(payload.get("outputs"), dict):
            for output_id, active in payload["outputs"].items():
                changes[str(output_id)] = bool(active)

        for signal, active in changes.items():
            if signal not in current_state:
                continue
            if current_state[signal] == active:
                continue
            if current_state[signal] and since_ms[signal] is not None:
                on_time_ms[signal] += max(0.0, ts * 1000 - since_ms[signal])
            if active:
                activation_count[signal] += 1
            current_state[signal] = active
            since_ms[signal] = ts * 1000
            if ts >= cutoff:
                transitions[signal].append({"timestamp_ms": int(ts * 1000), "active": active})

    now_ms = now.timestamp() * 1000
    for signal in LIVE_SIGNALS:
        if current_state[signal]:
            on_time_ms[signal] += max(0.0, now_ms - since_ms[signal])

    return {
        "window_seconds": window_seconds,
        "now_ms": int(now_ms),
        "signals": {
            signal: {
                "active": current_state[signal],
                "since_ms": int(since_ms[signal]),
                "duration_ms": int(now_ms - since_ms[signal]),
                "on_time_ms_total": int(on_time_ms[signal]),
                "activation_count_total": activation_count[signal],
                "transitions": transitions[signal],
            }
            for signal in LIVE_SIGNALS
        },
    }


def fetch_all(connection: sqlite3.Connection, query: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(query).fetchall()]


def fetch_one(connection: sqlite3.Connection, query: str) -> dict[str, Any] | None:
    row = connection.execute(query).fetchone()
    return dict(row) if row else None


def scalar(connection: sqlite3.Connection, query: str) -> int:
    return int(connection.execute(query).fetchone()[0])
