from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

logger = logging.getLogger("messeauto.mqtt_status")


class MqttStatusStore:
    """Tracks the last known online/offline status of one MQTT device.

    `status` is a JSON payload with `device`/`timestamp_ms`/`status` per
    MQTT.md. `last_seen` is set to receipt time, since a broker-delivered
    Last-Will message carries a pre-registered payload, not a live timestamp
    of the actual disconnect moment.
    """

    def __init__(self, label: str) -> None:
        self.label = label
        self._lock = threading.RLock()
        self._status: str | None = None
        self._last_seen: int | None = None

    def handler(self, topic: str, payload: bytes) -> None:
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            logger.warning("%s: ungueltiges JSON verworfen (%s)", self.label, error)
            return
        if not isinstance(data, dict) or "device" not in data:
            logger.warning("%s: Pflichtfeld 'device' fehlt, verworfen: %r", self.label, data)
            return

        with self._lock:
            self._status = str(data.get("status") or "unknown")
            self._last_seen = int(time.time() * 1000)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"status": self._status, "last_seen": self._last_seen}
