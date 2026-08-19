from __future__ import annotations

import json
import logging
from typing import Any, Callable

logger = logging.getLogger("messeauto.actor_button")

# Taster 1-7 aus HARDWARE.md (ESP32 Actor) auf bestehende GPIO-Ausgaenge
# des Pi 1 abgebildet. Taster 8 ist die physische Hupe (MA-11-006A) und wird
# ueber on_horn_button statt toggle_output gefuehrt. Taster 9/10 bleiben Reserve.
BUTTON_OUTPUT_MAP: dict[int, str] = {
    1: "highBeam",
    2: "lowBeam",
    3: "underbody",
    4: "indicatorLeft",
    5: "indicatorRight",
    6: "hazard",
    7: "fan",
}
HORN_BUTTON = 8
RESERVED_BUTTONS = (9, 10)


def handle_button_event(
    payload: bytes,
    toggle_output: Callable[[str], Any],
    on_horn_button: Callable[[bool], Any] | None = None,
) -> None:
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        logger.warning("actor/event/button: ungueltiges JSON verworfen (%s)", error)
        return

    if not isinstance(data, dict) or "device" not in data or "timestamp_ms" not in data:
        logger.warning("actor/event/button: Pflichtfelder fehlen, verworfen: %r", data)
        return

    button = data.get("button")
    edge = data.get("edge")
    try:
        button = int(button)
    except (TypeError, ValueError):
        logger.warning("actor/event/button: ungueltige button-Nummer verworfen: %r", data.get("button"))
        return

    if button == HORN_BUTTON:
        if on_horn_button is not None and edge in ("pressed", "released"):
            on_horn_button(edge == "pressed")
        logger.info("actor/event/button: Taster 8 (Hupe) edge=%s", edge)
        return

    if button in RESERVED_BUTTONS:
        logger.info("actor/event/button: Taster %s (reserviert) edge=%s - nur geloggt, keine Aktion", button, edge)
        return

    output_id = BUTTON_OUTPUT_MAP.get(button)
    if output_id is None:
        logger.warning("actor/event/button: unbekannte Taster-Nummer %s verworfen", button)
        return

    if edge != "pressed":
        return

    toggle_output(output_id)
    logger.info("actor/event/button: Taster %s -> toggle_output(%s)", button, output_id)
