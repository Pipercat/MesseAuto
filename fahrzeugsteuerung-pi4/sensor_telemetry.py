from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger("messeauto.sensor_telemetry")

# Plausibilitaetsgrenzen fuer den MesseCar-Innenraum-/Vorfuehrbetrieb, nicht
# die vollen Sensor-Datenblattgrenzen. Werte ausserhalb gelten als
# Sensorfehler statt als echte Messung.
TEMPERATURE_MIN_C = -10.0
TEMPERATURE_MAX_C = 60.0
SEAT_DISTANCE_MIN_CM = 2.0
SEAT_DISTANCE_MAX_CM = 400.0


def _plausible_field(data: dict[str, Any], key: str, minimum: float, maximum: float, now_ms: int) -> dict[str, Any]:
    raw = data.get(key)
    if raw is None:
        return {"value": None, "error": "missing", "last_seen": now_ms}
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return {"value": None, "error": "invalid_type", "last_seen": now_ms}
    if not (minimum <= value <= maximum):
        return {"value": None, "error": "out_of_range", "last_seen": now_ms}
    return {"value": value, "error": None, "last_seen": now_ms}


def handle_sensor_telemetry(payload: bytes, store: dict[str, Any], store_lock) -> None:  # noqa: ANN001
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        logger.warning("sensor/telemetry: ungueltiges JSON verworfen (%s)", error)
        return

    if not isinstance(data, dict) or "device" not in data or "timestamp_ms" not in data:
        logger.warning("sensor/telemetry: Pflichtfelder fehlen, verworfen: %r", data)
        return

    now_ms = int(time.time() * 1000)
    temperature = _plausible_field(data, "temperature_c", TEMPERATURE_MIN_C, TEMPERATURE_MAX_C, now_ms)
    seat_distance = _plausible_field(data, "seat_distance_cm", SEAT_DISTANCE_MIN_CM, SEAT_DISTANCE_MAX_CM, now_ms)

    with store_lock:
        store["temperature_c"] = temperature
        store["seat_distance_cm"] = seat_distance

    if temperature["error"]:
        logger.warning("sensor/telemetry: temperature_c verworfen (%s): %r", temperature["error"], data.get("temperature_c"))
    if seat_distance["error"]:
        logger.warning("sensor/telemetry: seat_distance_cm verworfen (%s): %r", seat_distance["error"], data.get("seat_distance_cm"))
