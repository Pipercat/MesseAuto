from __future__ import annotations

import glob
import json
import os
import threading
import time
from dataclasses import dataclass, asdict
from typing import Any

import serial
from flask import Flask, jsonify, request

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    GPIO = None


@dataclass(frozen=True)
class PinDefinition:
    id: str
    label: str
    gpio: int
    group: str


PINS: tuple[PinDefinition, ...] = (
    PinDefinition("underbody", "Unterbodenbeleuchtung", 17, "lighting"),
    PinDefinition("lowBeam", "Abblendlicht", 27, "lighting"),
    PinDefinition("highBeam", "Fernlicht", 25, "lighting"),
    PinDefinition("leftIndicator", "Blinker links", 6, "lighting"),
    PinDefinition("rightIndicator", "Blinker rechts", 5, "lighting"),
    PinDefinition("fan", "Lüfter", 22, "climate"),
)

PULSE_SECONDS = float(os.getenv("MESSEAUTO_PULSE_SECONDS", "0.20"))
SERIAL_BAUDRATE = int(os.getenv("MESSEAUTO_SERIAL_BAUDRATE", "115200"))

app = Flask(__name__)
state_lock = threading.Lock()
serial_lock = threading.Lock()

vehicle_state: dict[str, Any] = {
    "outputs": {pin.id: False for pin in PINS},
    "sensors": {},
    "esp32": {
        "esp32_actor": {"connected": False, "port": None, "last_seen": None},
        "esp32_sensor": {"connected": False, "port": None, "last_seen": None},
    },
}

serial_devices: dict[str, serial.Serial] = {}


def setup_gpio() -> None:
    if GPIO is None:
        print("[GPIO] RPi.GPIO nicht verfügbar – Simulationsmodus aktiv.")
        return

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    for pin in PINS:
        GPIO.setup(pin.gpio, GPIO.OUT, initial=GPIO.LOW)


def pulse_gpio(gpio: int) -> None:
    """Sendet einen kurzen Impuls. Kein Ausgang bleibt dauerhaft HIGH."""
    if GPIO is None:
        print(f"[GPIO-SIM] Impuls auf BCM {gpio}")
        time.sleep(PULSE_SECONDS)
        return

    GPIO.output(gpio, GPIO.HIGH)
    time.sleep(PULSE_SECONDS)
    GPIO.output(gpio, GPIO.LOW)


def get_pin(function_id: str) -> PinDefinition | None:
    return next((pin for pin in PINS if pin.id == function_id), None)


def set_function(function_id: str, enabled: bool) -> dict[str, Any]:
    pin = get_pin(function_id)
    if pin is None:
        raise KeyError(function_id)

    with state_lock:
        current = bool(vehicle_state["outputs"][function_id])
        changed = current != enabled
        if changed:
            vehicle_state["outputs"][function_id] = enabled

    if changed:
        pulse_gpio(pin.gpio)

    return {
        "id": function_id,
        "enabled": enabled,
        "changed": changed,
        "gpio": pin.gpio,
    }


def toggle_function(function_id: str) -> dict[str, Any]:
    with state_lock:
        current = bool(vehicle_state["outputs"].get(function_id, False))
    return set_function(function_id, not current)


def candidate_serial_ports() -> list[str]:
    patterns = (
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
        "/dev/serial/by-id/*",
    )
    ports: set[str] = set()
    for pattern in patterns:
        ports.update(glob.glob(pattern))
    return sorted(ports)


def handle_serial_message(port: str, payload: dict[str, Any]) -> None:
    device = payload.get("device")
    if device not in {"esp32_actor", "esp32_sensor"}:
        return

    now = time.time()
    with state_lock:
        vehicle_state["esp32"][device] = {
            "connected": True,
            "port": port,
            "last_seen": now,
        }

        if device == "esp32_sensor":
            vehicle_state["sensors"].update({
                key: value
                for key, value in payload.items()
                if key != "device"
            })
        elif device == "esp32_actor" and isinstance(payload.get("states"), dict):
            vehicle_state["actor_states"] = payload["states"]


def serial_reader(port: str, connection: serial.Serial) -> None:
    print(f"[SERIAL] Lese {port}")
    try:
        while connection.is_open:
            raw = connection.readline().decode("utf-8", errors="ignore").strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                print(f"[SERIAL] Ungültiges JSON von {port}: {raw[:120]}")
                continue
            handle_serial_message(port, payload)
    except (serial.SerialException, OSError) as exc:
        print(f"[SERIAL] Verbindung zu {port} beendet: {exc}")
    finally:
        with serial_lock:
            serial_devices.pop(port, None)
        try:
            connection.close()
        except Exception:
            pass


def serial_discovery_loop() -> None:
    while True:
        for port in candidate_serial_ports():
            with serial_lock:
                if port in serial_devices:
                    continue
            try:
                connection = serial.Serial(port, SERIAL_BAUDRATE, timeout=1)
                time.sleep(1.5)
            except (serial.SerialException, OSError):
                continue

            with serial_lock:
                serial_devices[port] = connection
            threading.Thread(
                target=serial_reader,
                args=(port, connection),
                daemon=True,
            ).start()
        time.sleep(3)


def mark_stale_devices() -> None:
    while True:
        now = time.time()
        with state_lock:
            for info in vehicle_state["esp32"].values():
                last_seen = info.get("last_seen")
                if last_seen is not None and now - last_seen > 5:
                    info["connected"] = False
        time.sleep(1)


@app.get("/api/state")
def api_state():
    with state_lock:
        snapshot = json.loads(json.dumps(vehicle_state))
    return jsonify(snapshot)


@app.get("/api/pins")
def api_pins():
    return jsonify([asdict(pin) for pin in PINS])


@app.get("/api/sensors")
def api_sensors():
    with state_lock:
        sensors = dict(vehicle_state["sensors"])
    return jsonify(sensors)


@app.get("/api/esp32")
def api_esp32():
    with state_lock:
        devices = json.loads(json.dumps(vehicle_state["esp32"]))
    return jsonify(devices)


@app.post("/api/functions/<function_id>/toggle")
def api_toggle(function_id: str):
    try:
        result = toggle_function(function_id)
    except KeyError:
        return jsonify({"error": "Unbekannte Funktion"}), 404
    return jsonify(result)


@app.put("/api/functions/<function_id>")
def api_set(function_id: str):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload.get("enabled"), bool):
        return jsonify({"error": "Feld 'enabled' muss true oder false sein"}), 400
    try:
        result = set_function(function_id, payload["enabled"])
    except KeyError:
        return jsonify({"error": "Unbekannte Funktion"}), 404
    return jsonify(result)


if __name__ == "__main__":
    setup_gpio()
    threading.Thread(target=serial_discovery_loop, daemon=True).start()
    threading.Thread(target=mark_stale_devices, daemon=True).start()
    try:
        app.run(host="0.0.0.0", port=5000, threaded=True)
    finally:
        if GPIO is not None:
            GPIO.cleanup()
