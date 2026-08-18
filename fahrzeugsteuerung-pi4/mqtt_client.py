from __future__ import annotations

import os
import threading
import time
from typing import Any

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover - paho-mqtt is installed on the Pi
    mqtt = None


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "ja"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class MqttClient:
    """Non-blocking MQTT client with automatic reconnect.

    Flask/UI/GPIO must keep working while the broker is unreachable; connect
    and reconnect happen entirely on paho-mqtt's own network thread, never on
    a request-handling thread.
    """

    def __init__(self) -> None:
        self.enabled = _env_bool("MESSEAUTO_MQTT_ENABLED", True)
        self.host = os.getenv("MESSEAUTO_MQTT_HOST", "127.0.0.1")
        self.port = _env_int("MESSEAUTO_MQTT_PORT", 1883)
        self.client_id = os.getenv("MESSEAUTO_MQTT_CLIENT_ID", "messeauto-pi1")
        self.keepalive = _env_int("MESSEAUTO_MQTT_KEEPALIVE", 20)

        self._lock = threading.RLock()
        self._connected = False
        self._last_connect_attempt: float | None = None
        self._last_connected_at: float | None = None
        self._last_disconnected_at: float | None = None
        self._last_error: str | None = None
        self._client: "mqtt.Client | None" = None

        if self.enabled and mqtt is not None:
            self._client = mqtt.Client(client_id=self.client_id, clean_session=True)
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.reconnect_delay_set(min_delay=1, max_delay=30)

    def start(self) -> None:
        if not self.enabled or self._client is None:
            return
        self._try_connect()
        self._client.loop_start()

    def stop(self) -> None:
        if self._client is None:
            return
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:
            pass

    def _try_connect(self) -> None:
        if self._client is None:
            return
        with self._lock:
            self._last_connect_attempt = time.time()
        try:
            self._client.connect_async(self.host, self.port, keepalive=self.keepalive)
        except Exception as error:  # broker unreachable, GPIO/UI must not block on this
            with self._lock:
                self._last_error = str(error)

    def _on_connect(self, client, userdata, flags, reason_code) -> None:  # noqa: ANN001
        with self._lock:
            self._connected = reason_code == 0
            self._last_connected_at = time.time() if self._connected else self._last_connected_at
            self._last_error = None if self._connected else f"connect reason_code={reason_code}"

    def _on_disconnect(self, client, userdata, reason_code) -> None:  # noqa: ANN001
        with self._lock:
            self._connected = False
            self._last_disconnected_at = time.time()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self.enabled,
                "available": mqtt is not None,
                "host": self.host,
                "port": self.port,
                "connected": self._connected,
                "last_connect_attempt": self._last_connect_attempt,
                "last_connected_at": self._last_connected_at,
                "last_disconnected_at": self._last_disconnected_at,
                "last_error": self._last_error,
            }
