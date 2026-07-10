from __future__ import annotations

import glob
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from typing import Any

import serial
from flask import Flask, jsonify, render_template, request

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

BUTTON_FUNCTIONS: dict[int, str | None] = {
    1: "highBeam",
    2: "lowBeam",
    3: "underbody",
    4: "leftIndicator",
    5: "rightIndicator",
    6: "hazard",
    7: "fan",
    8: None,
    9: None,
    10: None,
}

PULSE_SECONDS = float(os.getenv("MESSEAUTO_PULSE_SECONDS", "0.20"))
SERIAL_BAUDRATE = int(os.getenv("MESSEAUTO_SERIAL_BAUDRATE", "115200"))
SERIAL_STALE_SECONDS = float(os.getenv("MESSEAUTO_SERIAL_STALE_SECONDS", "5"))
PORT_SCAN_SECONDS = float(os.getenv("MESSEAUTO_PORT_SCAN_SECONDS", "3"))

app = Flask(__name__)
state_lock = threading.RLock()
serial_lock = threading.Lock()
pulse_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="gpio-pulse")

vehicle_state: dict[str, Any] = {
    "outputs": {pin.id: False for pin in PINS},
    "hazard": False,
    "sensors": {"temperature_c": None, "seat_distance_cm": None},
    "actor_states": {},
    "esp32": {
        "esp32_actor": {"connected": False, "port": None, "last_seen": None},
        "esp32_sensor": {"connected": False, "port": None, "last_seen": None},
    },
    "system": {
        "started_at": time.time(),
        "pulse_seconds": PULSE_SECONDS,
        "serial_baudrate": SERIAL_BAUDRATE,
        "gpio_available": GPIO is not None,
        "api_requests": 0,
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
    if GPIO is None:
        print(f"[GPIO-SIM] Impuls auf BCM {gpio}")
        time.sleep(PULSE_SECONDS)
        return
    try:
        GPIO.output(gpio, GPIO.HIGH)
        time.sleep(PULSE_SECONDS)
    finally:
        GPIO.output(gpio, GPIO.LOW)


def get_pin(function_id: str) -> PinDefinition | None:
    return next((pin for pin in PINS if pin.id == function_id), None)


def send_actor_command(function_id: str, enabled: bool) -> bool:
    """Synchronisiert Display-/API-Befehle mit dem Aktor-ESP."""
    with state_lock:
        port = vehicle_state["esp32"]["esp32_actor"].get("port")
        connected = bool(vehicle_state["esp32"]["esp32_actor"].get("connected"))
    if not connected or not port:
        return False

    command = f"SET {function_id} {1 if enabled else 0}\n".encode("utf-8")
    try:
        with serial_lock:
            connection = serial_devices.get(port)
            if connection is None or not connection.is_open:
                return False
            connection.write(command)
            connection.flush()
        return True
    except (serial.SerialException, OSError):
        return False


def set_function(function_id: str, enabled: bool, *, source: str = "api") -> dict[str, Any]:
    pin = get_pin(function_id)
    if pin is None:
        raise KeyError(function_id)
    with state_lock:
        current = bool(vehicle_state["outputs"][function_id])
        changed = current != enabled
        if changed:
            vehicle_state["outputs"][function_id] = enabled
    if changed:
        pulse_pool.submit(pulse_gpio, pin.gpio)
        if source != "esp32_actor":
            send_actor_command(function_id, enabled)
        print(f"[STATE] {source}: {function_id} -> {enabled}")
    return {"id": function_id, "enabled": enabled, "changed": changed, "gpio": pin.gpio}


def toggle_function(function_id: str, *, source: str = "api") -> dict[str, Any]:
    with state_lock:
        current = bool(vehicle_state["outputs"].get(function_id, False))
    return set_function(function_id, not current, source=source)


def set_hazard(enabled: bool, *, source: str = "api") -> dict[str, Any]:
    with state_lock:
        changed = bool(vehicle_state["hazard"]) != enabled
        vehicle_state["hazard"] = enabled
    left = set_function("leftIndicator", enabled, source=source)
    right = set_function("rightIndicator", enabled, source=source)
    if changed and source != "esp32_actor":
        send_actor_command("hazard", enabled)
    return {"id": "hazard", "enabled": enabled, "changed": changed, "children": [left, right]}


def toggle_hazard(*, source: str = "api") -> dict[str, Any]:
    with state_lock:
        enabled = not bool(vehicle_state["hazard"])
    return set_hazard(enabled, source=source)


def handle_actor_button(button_number: int) -> None:
    function_id = BUTTON_FUNCTIONS.get(button_number)
    if function_id is None:
        print(f"[ESP32] Reserve-Taster {button_number} gedrückt")
        return
    if function_id == "hazard":
        toggle_hazard(source="esp32_actor")
    else:
        if function_id in {"leftIndicator", "rightIndicator"}:
            with state_lock:
                hazard_active = bool(vehicle_state["hazard"])
            if hazard_active:
                set_hazard(False, source="esp32_actor")
        toggle_function(function_id, source="esp32_actor")


def candidate_serial_ports() -> list[str]:
    patterns = ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/serial/by-id/*")
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
        vehicle_state["esp32"][device] = {"connected": True, "port": port, "last_seen": now}

    if device == "esp32_sensor":
        with state_lock:
            for key in ("temperature_c", "seat_distance_cm"):
                if key in payload:
                    vehicle_state["sensors"][key] = payload[key]
        return

    states = payload.get("states")
    if isinstance(states, dict):
        with state_lock:
            vehicle_state["actor_states"] = dict(states)

    event_button = payload.get("event_button")
    if isinstance(event_button, int) and 1 <= event_button <= 10:
        handle_actor_button(event_button)


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
            if isinstance(payload, dict):
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
                time.sleep(1.2)
            except (serial.SerialException, OSError):
                continue
            with serial_lock:
                serial_devices[port] = connection
            threading.Thread(target=serial_reader, args=(port, connection), daemon=True).start()
        time.sleep(PORT_SCAN_SECONDS)


def mark_stale_devices() -> None:
    while True:
        now = time.time()
        with state_lock:
            for info in vehicle_state["esp32"].values():
                last_seen = info.get("last_seen")
                if last_seen is not None and now - last_seen > SERIAL_STALE_SECONDS:
                    info["connected"] = False
        time.sleep(1)


def snapshot_state() -> dict[str, Any]:
    with state_lock:
        return json.loads(json.dumps(vehicle_state))


@app.before_request
def count_request() -> None:
    if request.path.startswith("/api/"):
        with state_lock:
            vehicle_state["system"]["api_requests"] += 1


@app.get("/")
def display():
    return render_template("index.html")


@app.get("/api/health")
def api_health():
    return jsonify({"ok": True, "service": "messeauto-pi1", "time": time.time()})


@app.get("/api/state")
def api_state():
    return jsonify(snapshot_state())


@app.get("/api/pins")
def api_pins():
    return jsonify([asdict(pin) for pin in PINS])


@app.get("/api/sensors")
def api_sensors():
    with state_lock:
        return jsonify(dict(vehicle_state["sensors"]))


@app.get("/api/esp32")
def api_esp32():
    with state_lock:
        return jsonify(json.loads(json.dumps(vehicle_state["esp32"])))


@app.post("/api/functions/<function_id>/toggle")
def api_toggle(function_id: str):
    try:
        result = toggle_hazard() if function_id == "hazard" else toggle_function(function_id)
    except KeyError:
        return jsonify({"error": "Unbekannte Funktion"}), 404
    return jsonify(result)


@app.put("/api/functions/<function_id>")
def api_set(function_id: str):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload.get("enabled"), bool):
        return jsonify({"error": "Feld 'enabled' muss true oder false sein"}), 400
    try:
        result = set_hazard(payload["enabled"]) if function_id == "hazard" else set_function(function_id, payload["enabled"])
    except KeyError:
        return jsonify({"error": "Unbekannte Funktion"}), 404
    return jsonify(result)


@app.post("/api/all-off")
def api_all_off():
    results = []
    set_hazard(False)
    for pin in PINS:
        results.append(set_function(pin.id, False))
    return jsonify({"ok": True, "results": results})


if __name__ == "__main__":
    setup_gpio()
    threading.Thread(target=serial_discovery_loop, daemon=True, name="serial-discovery").start()
    threading.Thread(target=mark_stale_devices, daemon=True, name="serial-watchdog").start()
    try:
        app.run(host="0.0.0.0", port=5000, threaded=True)
    finally:
        pulse_pool.shutdown(wait=False, cancel_futures=True)
        if GPIO is not None:
            GPIO.cleanup()
