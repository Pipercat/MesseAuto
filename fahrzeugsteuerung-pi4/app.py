from __future__ import annotations

import atexit
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from actor_button_mapping import handle_button_event
from database_client import DatabaseClient
from esp32_actor_bridge import ESP32ActorBridge
from gpio_controller import create_controller
from mqtt_client import MqttClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
actor_state_logger = logging.getLogger("messeauto.actor_state")


PROJECT_DIR = Path(__file__).resolve().parent
WEB_DIR = PROJECT_DIR / "web"

app = Flask(__name__, static_folder=None)
controller = create_controller()
esp32_actor = ESP32ActorBridge()
database_client = DatabaseClient()
mqtt_client = MqttClient()
heartbeat_interval = float(os.getenv("MESSEAUTO_HEARTBEAT_INTERVAL", "5"))
heartbeat_stop = threading.Event()
last_test_result: dict[str, Any] | None = None
last_test_lock = threading.RLock()
actor_mqtt_state: dict[str, Any] | None = None
actor_mqtt_state_lock = threading.RLock()


def handle_actor_state(topic: str, payload: bytes) -> None:
    global actor_mqtt_state
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        actor_state_logger.warning("actor/state: ungueltiges JSON verworfen (%s)", error)
        return
    if not isinstance(data, dict) or "device" not in data or "timestamp_ms" not in data:
        actor_state_logger.warning("actor/state: Pflichtfelder fehlen, verworfen: %r", data)
        return
    with actor_mqtt_state_lock:
        actor_mqtt_state = data
    actor_state_logger.info("actor/state: aktualisiert von device=%s", data.get("device"))


esp32_actor.start()
mqtt_client.start()
mqtt_client.subscribe(
    "messecar/actor/event/button",
    lambda topic, payload: handle_button_event(payload, controller.toggle_output),
)
mqtt_client.subscribe("messecar/actor/state", handle_actor_state)
atexit.register(controller.shutdown)
atexit.register(esp32_actor.stop)
atexit.register(mqtt_client.stop)
atexit.register(heartbeat_stop.set)


def combined_state() -> dict[str, Any]:
    state = controller.state()
    actor_snapshot = esp32_actor.snapshot()
    actor_outputs = actor_snapshot["actorFeedback"].get("outputs") or {}
    actor_is_pulse_only = actor_snapshot.get("relayMode") == "pulse_only"
    state["esp32Actor"] = actor_snapshot
    state["databasePi"] = database_client.snapshot()
    state["actorFeedback"] = actor_snapshot["actorFeedback"]
    state["effectiveOutputs"] = (
        dict(state["outputs"])
        if not actor_snapshot.get("enabled") or actor_is_pulse_only
        else {**state["outputs"], **actor_outputs}
    )
    with last_test_lock:
        state["lastTestResult"] = dict(last_test_result) if last_test_result else None
    return state


def actor_status_payload(actor_snapshot: dict[str, Any]) -> dict[str, Any]:
    candidates = actor_snapshot.get("candidatePorts") or []
    if not actor_snapshot.get("enabled"):
        status = "standalone"
        message = "ESP32 standalone; keine Pi-Serial-Verbindung"
    elif actor_snapshot.get("connected"):
        status = "connected"
        if actor_snapshot.get("relayMode") == "pulse_only":
            message = "ESP32 Impuls-Relais aktiv"
        else:
            message = actor_snapshot.get("lastMessageType") or "ESP32-Aktor verbunden"
    elif actor_snapshot.get("serialActive"):
        status = "connected"
        message = "Legacy-Serial aktiv"
    elif candidates:
        status = "usb_detected"
        message = "USB erkannt, keine gueltigen ESP-Daten"
    else:
        status = "unknown"
        message = "kein ESP-USB erkannt"

    return {
        "source_device": "esp32_actor",
        "device": "esp32_actor",
        "status": status,
        "message": message,
        "runtime_mode": actor_snapshot.get("runtimeMode"),
        "connected": bool(actor_snapshot.get("connected")),
        "serial_active": bool(actor_snapshot.get("serialActive")),
        "protocol": actor_snapshot.get("protocol"),
        "relay_mode": actor_snapshot.get("relayMode"),
        "pulse_level": actor_snapshot.get("pulseLevel"),
        "idle_mode": actor_snapshot.get("idleMode"),
        "pulse_ms": actor_snapshot.get("pulseMs"),
        "pulse_count": actor_snapshot.get("pulseCount"),
        "last_pulse": actor_snapshot.get("lastPulse"),
        "port": actor_snapshot.get("port"),
        "baudrate": actor_snapshot.get("baudrate"),
        "message_count": actor_snapshot.get("messageCount", 0),
        "unknown_message_count": actor_snapshot.get("unknownMessageCount", 0),
        "decode_error_count": actor_snapshot.get("decodeErrorCount", 0),
        "last_raw_line": actor_snapshot.get("lastRawLine"),
        "candidate_ports": candidates,
        "errors": actor_snapshot.get("actorFeedback", {}).get("errors", []),
    }


def send_heartbeat() -> None:
    state = combined_state()
    outputs = state.get("effectiveOutputs") or state.get("outputs") or {}
    active_outputs = sorted(output_id for output_id, active in outputs.items() if active)
    actor_snapshot = state.get("esp32Actor") or {}

    database_client.send_event(
        "vehicle_heartbeat",
        {
            "message": "Fahrzeug-Pi verbunden",
            "mode": state.get("mode"),
            "is_real_hardware": state.get("isRealHardware"),
            "active_outputs": active_outputs,
            "active_output_count": len(active_outputs),
            "motor_percent": (state.get("motor") or {}).get("percent"),
            "esp32_actor": actor_status_payload(actor_snapshot),
            "last_test_result": state.get("lastTestResult"),
        },
    )
    database_client.send_event("actor_status", actor_status_payload(actor_snapshot))


def heartbeat_loop() -> None:
    while not heartbeat_stop.wait(heartbeat_interval):
        try:
            send_heartbeat()
        except Exception:
            pass


heartbeat_thread = threading.Thread(target=heartbeat_loop, name="messeauto-heartbeat", daemon=True)
heartbeat_thread.start()


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
    return jsonify({"ok": True, "state": combined_state()})


@app.get("/api/config")
def api_config():
    return jsonify({"ok": True, "state": combined_state()})


@app.get("/api/metrics")
def api_metrics():
    return jsonify({"ok": True, "metrics": controller.metrics()})


@app.get("/api/esp32/actor")
def api_esp32_actor():
    return jsonify({"ok": True, "esp32Actor": esp32_actor.snapshot()})


@app.post("/api/esp32/actor/probe")
def api_esp32_actor_probe():
    probe = esp32_actor.probe()
    snapshot = esp32_actor.snapshot()
    database_client.send_event("actor_status", actor_status_payload(snapshot))
    return jsonify({"ok": True, "probe": probe, "esp32Actor": snapshot, "state": combined_state()})


@app.post("/api/esp32/actor/pin-pulse")
def api_esp32_actor_pin_pulse():
    data = request_data()
    gpio = data.get("gpio")
    if gpio is None:
        return json_error("Feld 'gpio' fehlt")
    try:
        gpio_number = int(gpio)
    except (TypeError, ValueError):
        return json_error("GPIO muss eine Zahl sein")

    if not esp32_actor.enabled:
        snapshot = esp32_actor.snapshot()
        return jsonify(
            {
                "ok": False,
                "sent": False,
                "error": "ESP32 ist standalone. Pin-Diagnose/Flash nur per PC, nicht ueber den Pi.",
                "esp32Actor": snapshot,
                "state": combined_state(),
            }
        )

    sent = esp32_actor.send_diagnostic_pin(gpio_number, data.get("level"), data.get("durationMs"))
    time.sleep(0.15)
    snapshot = esp32_actor.snapshot()
    database_client.send_event(
        "actor_status",
        {**actor_status_payload(snapshot), "message": f"Diagnoseimpuls GPIO {gpio_number}"},
    )
    return jsonify({"ok": bool(sent), "sent": bool(sent), "esp32Actor": snapshot, "state": combined_state()})


@app.get("/health")
def health():
    actor_snapshot = esp32_actor.snapshot()
    return jsonify(
        {
            "ok": True,
            "service": "messeauto-fahrzeug-pi",
            "mode": controller.mode,
            "databasePi": database_client.snapshot(),
            "esp32Actor": {
                "enabled": actor_snapshot["enabled"],
                "runtimeMode": actor_snapshot.get("runtimeMode"),
                "connected": actor_snapshot["connected"],
                "serialActive": actor_snapshot["serialActive"],
                "protocol": actor_snapshot.get("protocol"),
                "relayMode": actor_snapshot.get("relayMode"),
                "pulseLevel": actor_snapshot.get("pulseLevel"),
                "idleMode": actor_snapshot.get("idleMode"),
                "pulseMs": actor_snapshot.get("pulseMs"),
                "port": actor_snapshot["port"],
                "baudrate": actor_snapshot["baudrate"],
            },
            "lastTestResult": combined_state().get("lastTestResult"),
        }
    )


@app.post("/api/output/<output_id>")
def api_set_output(output_id: str):
    data = request_data()
    if "active" not in data:
        return json_error("Feld 'active' fehlt")
    state = controller.set_output(output_id, bool(data["active"]))
    esp32_actor.send_outputs({output_id: state["outputs"][output_id]})
    mqtt_client.publish_command(
        "messecar/actor/command", {"function": output_id, "value": state["outputs"][output_id]}
    )
    database_client.send_event("vehicle_output", {"output_id": output_id, "active": state["outputs"][output_id]})
    return jsonify({"ok": True, "state": combined_state()})


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

    state = controller.set_outputs(changes)
    esp32_actor.send_outputs({output_id: state["outputs"][output_id] for output_id in changes})
    for output_id in changes:
        mqtt_client.publish_command(
            "messecar/actor/command", {"function": output_id, "value": state["outputs"][output_id]}
        )
    database_client.send_event(
        "vehicle_outputs",
        {"outputs": {output_id: state["outputs"][output_id] for output_id in changes}},
    )
    return jsonify({"ok": True, "state": combined_state()})


@app.post("/api/motor")
def api_set_motor():
    data = request_data()
    if "percent" not in data:
        return json_error("Feld 'percent' fehlt")
    controller.set_motor(data["percent"])
    esp32_actor.send_motor(data["percent"])
    database_client.send_event("vehicle_motor", {"percent": data["percent"]})
    return jsonify({"ok": True, "state": combined_state()})


@app.post("/api/reset")
def api_reset():
    controller.reset()
    esp32_actor.reset()
    database_client.send_event("vehicle_reset", {})
    return jsonify({"ok": True, "state": combined_state()})


@app.post("/api/database/ping")
def api_database_ping():
    ok = database_client.send_event("vehicle_ping", {"message": "Fahrzeug-Pi verbunden"})
    return jsonify({"ok": ok, "databasePi": database_client.snapshot(), "state": combined_state()})


@app.post("/api/test-result")
def api_test_result():
    global last_test_result

    data = request_data()
    test_name = str(data.get("test") or data.get("test_name") or "unknown")
    passed = bool(data.get("passed"))
    payload = {
        "test": test_name,
        "passed": passed,
        "severity": data.get("severity") or ("info" if passed else "error"),
        "message": data.get("message") or ("Test bestanden" if passed else "Test fehlgeschlagen"),
        "steps": data.get("steps") if isinstance(data.get("steps"), list) else [],
        "metrics": data.get("metrics") if isinstance(data.get("metrics"), dict) else {},
        "state": {
            "mode": controller.mode,
            "esp32_actor": actor_status_payload(esp32_actor.snapshot()),
        },
    }

    with last_test_lock:
        last_test_result = dict(payload)

    ok = database_client.send_event("test_result", payload)
    return jsonify({"ok": True, "stored": ok, "state": combined_state(), "databasePi": database_client.snapshot()})


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
