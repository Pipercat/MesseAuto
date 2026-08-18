from __future__ import annotations

import glob
import json
import os
import re
import threading
import time
from typing import Any

try:
    import serial
except ImportError:  # pragma: no cover - pyserial is installed on the Pi
    serial = None


DIGITAL_OUTPUTS = (
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


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "ja"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _first_present(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


class ESP32ActorBridge:
    def __init__(self) -> None:
        self.enabled = _env_bool("MESSEAUTO_ESP32_ACTOR_ENABLED", False)
        self.baudrate = _env_int("MESSEAUTO_ESP32_ACTOR_BAUDRATE", 115200)
        self.timeout_seconds = _env_float("MESSEAUTO_ESP32_ACTOR_TIMEOUT", 3.0)
        self.scan_interval = _env_float("MESSEAUTO_ESP32_ACTOR_SCAN_INTERVAL", 2.0)
        self.include_gpio_uart = _env_bool("MESSEAUTO_ESP32_SCAN_GPIO_UART", False)
        self.relay_active_high = _env_bool("MESSEAUTO_ESP32_RELAY_ACTIVE_HIGH", False)
        self.relay_pulse_ms = _env_int("MESSEAUTO_ESP32_RELAY_PULSE_MS", 250)

        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._scan_thread = threading.Thread(target=self._scan_loop, name="esp32-actor-scan", daemon=True)
        self._readers: dict[str, SerialReader] = {}
        self._active_port: str | None = None
        self._port_errors: dict[str, str] = {}
        self._last_seen: float | None = None
        self._last_message_type: str | None = None
        self._protocol: str | None = None
        self._relay_mode: str | None = None
        self._pulse_level: str | None = None
        self._idle_mode: str | None = None
        self._pulse_ms: int | None = None
        self._pulse_count: int | None = None
        self._last_pulse: str | None = None
        self._message_count = 0
        self._unknown_message_count = 0
        self._decode_error_count = 0
        self._last_raw_line: str | None = None
        self._last_raw_seen: float | None = None
        self._last_probe_sent: float | None = None
        self._outputs: dict[str, bool] = {}
        self._motor_percent: int | None = None
        self._raw: dict[str, Any] | None = None
        self._errors: list[str] = []

    def start(self) -> None:
        if self.enabled:
            self._scan_thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            readers = list(self._readers.values())
        for reader in readers:
            reader.stop()

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            age = None if self._last_seen is None else round(now - self._last_seen, 2)
            raw_age = None if self._last_raw_seen is None else round(now - self._last_raw_seen, 2)
            connected = bool(self._active_port and age is not None and age <= self.timeout_seconds)
            serial_active = bool(raw_age is not None and raw_age <= self.timeout_seconds)
            errors = list(self._errors[-5:])
            if serial is None:
                errors.append("pyserial nicht installiert")
            if not self.enabled:
                errors.append("ESP32 standalone: keine Pi-Serial-Verbindung")
            return {
                "enabled": self.enabled,
                "runtimeMode": "serial_bridge" if self.enabled else "standalone_pc_flash",
                "connected": connected,
                "serialActive": serial_active,
                "protocol": self._protocol,
                "relayMode": self._relay_mode,
                "pulseLevel": self._pulse_level,
                "idleMode": self._idle_mode,
                "pulseMs": self._pulse_ms,
                "pulseCount": self._pulse_count,
                "lastPulse": self._last_pulse,
                "port": self._active_port,
                "baudrate": self.baudrate,
                "lastSeenAgeSeconds": age,
                "lastRawAgeSeconds": raw_age,
                "lastProbeAgeSeconds": None if self._last_probe_sent is None else round(now - self._last_probe_sent, 2),
                "lastMessageType": self._last_message_type,
                "messageCount": self._message_count,
                "unknownMessageCount": self._unknown_message_count,
                "decodeErrorCount": self._decode_error_count,
                "lastRawLine": self._last_raw_line,
                "actorFeedback": {
                    "outputs": dict(self._outputs),
                    "motorPercent": self._motor_percent,
                    "relayMode": self._relay_mode,
                    "pulseLevel": self._pulse_level,
                    "idleMode": self._idle_mode,
                    "pulseMs": self._pulse_ms,
                    "pulseCount": self._pulse_count,
                    "lastPulse": self._last_pulse,
                    "errors": errors,
                    "raw": self._raw,
                },
                "portErrors": dict(self._port_errors),
                "candidatePorts": self._candidate_ports(),
            }

    def send_outputs(self, outputs: dict[str, bool]) -> bool:
        if not self.enabled:
            return False
        payload = {key: bool(value) for key, value in outputs.items() if key in DIGITAL_OUTPUTS}
        if not payload:
            return False
        sent = False
        self._send_relay_config()
        for output_id, active in payload.items():
            sent = self._write_line(f"PULSE {output_id} {1 if active else 0}") or sent
        return sent

    def send_motor(self, percent: int | float) -> bool:
        if not self.enabled:
            return False
        try:
            numeric_percent = int(round(float(percent)))
        except (TypeError, ValueError):
            numeric_percent = 0
        numeric_percent = max(0, min(100, numeric_percent))
        pulse_serial_ok = self._write_line(f"MOTOR {numeric_percent}")

        legacy_pwm = max(0, min(80, int(round(numeric_percent * 0.8))))
        direction = _env_int("MESSEAUTO_LEGACY_MOTOR_DIRECTION", 0)
        legacy_ok = self._write_line(f"{legacy_pwm}:{1 if direction == 1 else 0}:0")
        return pulse_serial_ok or legacy_ok

    def reset(self) -> bool:
        if not self.enabled:
            return False
        pulse_serial_ok = self._write_line("RESET")
        legacy_ok = self._write_line("0:0:1")
        return pulse_serial_ok or legacy_ok

    def send_diagnostic_pin(self, gpio: int, level: str | None = None, duration_ms: int | None = None) -> bool:
        if not self.enabled:
            return False
        if level is None:
            level = "HIGH" if self.relay_active_high else "LOW"
        normalized_level = "HIGH" if str(level).strip().lower() in {"1", "true", "high", "on"} else "LOW"
        try:
            duration = max(40, min(1200, int(duration_ms or self.relay_pulse_ms)))
        except (TypeError, ValueError):
            duration = self.relay_pulse_ms
        self._send_relay_config()
        return self._write_line(f"PULSE_PIN {int(gpio)} {normalized_level} {duration}")

    def probe(self) -> dict[str, Any]:
        if not self.enabled:
            return {
                "sent": False,
                "configSent": False,
                "pulseSerialSent": False,
                "legacySent": False,
                "readerCount": 0,
                "commands": [],
                "message": "ESP32 ist im Messebetrieb standalone; Flash/Diagnose nur per PC.",
            }

        with self._lock:
            readers = list(self._readers.values())
            self._last_probe_sent = time.monotonic()

        config_ok = self._send_relay_config()
        ping_ok = self._write_line("PING")
        pulse_serial_ok = self._write_line("MOTOR 0")
        legacy_ok = self._write_line("0:0:0")
        return {
            "sent": bool(config_ok or ping_ok or pulse_serial_ok or legacy_ok),
            "configSent": bool(config_ok),
            "pulseSerialSent": bool(ping_ok or pulse_serial_ok),
            "legacySent": bool(legacy_ok),
            "readerCount": len(readers),
            "commands": ["relay mode", "pulse ms", "PING", "MOTOR 0", "legacy 0:0:0"],
        }

    def _send_relay_config(self) -> bool:
        mode = "ACTIVE_HIGH" if self.relay_active_high else "ACTIVE_LOW"
        mode_ok = self._write_line(f"MODE {mode}")
        pulse_ok = self._write_line(f"PULSE_MS {self.relay_pulse_ms}")
        return bool(mode_ok or pulse_ok)

    def _write(self, payload: dict[str, Any]) -> bool:
        return self._write_line(json.dumps(payload, separators=(",", ":")))

    def _write_line(self, line: str) -> bool:
        with self._lock:
            reader = self._readers.get(self._active_port or "")
            if reader is None and len(self._readers) == 1:
                reader = next(iter(self._readers.values()))
        if reader is None:
            return False
        try:
            return reader.write_line(line)
        except Exception as exc:
            with self._lock:
                self._port_errors[reader.port] = str(exc)
            return False

    def _scan_loop(self) -> None:
        while not self._stop.is_set():
            if serial is not None:
                self._ensure_readers()
            self._expire_if_stale()
            self._stop.wait(self.scan_interval)

    def _ensure_readers(self) -> None:
        for port in self._candidate_ports():
            with self._lock:
                if port in self._readers:
                    continue
                reader = SerialReader(
                    port,
                    self.baudrate,
                    self._handle_raw_line,
                    self._handle_message,
                    self._handle_decode_error,
                    self._handle_reader_close,
                )
                self._readers[port] = reader
            reader.start()

    def _candidate_ports(self) -> list[str]:
        if not self.enabled:
            return []

        explicit_ports = os.getenv("MESSEAUTO_ESP32_PORTS", "").strip()
        if explicit_ports:
            return [port.strip() for port in explicit_ports.split(",") if port.strip()]

        ports: list[str] = []
        for pattern in ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/serial/by-id/*"):
            ports.extend(glob.glob(pattern))
        if self.include_gpio_uart:
            ports.extend(glob.glob("/dev/ttyAMA0"))

        unique: dict[str, str] = {}
        for port in ports:
            unique[os.path.realpath(port)] = port
        return [unique[key] for key in sorted(unique)]

    def _handle_message(self, port: str, message: dict[str, Any]) -> None:
        if str(message.get("device", "")).strip() != "esp32_actor":
            with self._lock:
                self._unknown_message_count += 1
            return

        with self._lock:
            self._active_port = port
            self._last_seen = time.monotonic()
            self._last_message_type = str(message.get("type", "unknown"))
            self._protocol = str(message.get("protocol") or "json_status")
            self._relay_mode = message.get("relay_mode") or message.get("relayMode") or self._relay_mode
            self._pulse_level = message.get("pulse_level") or message.get("pulseLevel") or self._pulse_level
            self._idle_mode = message.get("idle_mode") or message.get("idleMode") or self._idle_mode

            pulse_ms = _safe_int(_first_present(message, "pulse_ms", "pulseMs"))
            if pulse_ms is not None:
                self._pulse_ms = pulse_ms
            pulse_count = _safe_int(_first_present(message, "pulse_count", "pulseCount"))
            if pulse_count is not None:
                self._pulse_count = pulse_count
            last_pulse = message.get("last_pulse") or message.get("lastPulse")
            if last_pulse is not None:
                self._last_pulse = last_pulse
            self._message_count += 1
            self._raw = message
            self._errors = list(message.get("errors") or [])

            outputs = message.get("logical_outputs") or message.get("outputs")
            if isinstance(outputs, dict):
                self._outputs = {key: bool(outputs.get(key)) for key in DIGITAL_OUTPUTS if key in outputs}

            motor_percent = message.get("motor_percent")
            if motor_percent is None:
                motor_percent = message.get("motorPercent")
            if motor_percent is not None:
                try:
                    self._motor_percent = max(0, min(100, int(round(float(motor_percent)))))
                except (TypeError, ValueError):
                    pass

    def _handle_raw_line(self, port: str, line: str) -> None:
        with self._lock:
            self._active_port = port
            self._last_raw_seen = time.monotonic()
            self._last_raw_line = line[:180]

    def _handle_decode_error(self, port: str, line: str) -> None:
        if self._handle_legacy_line(port, line):
            return

        stripped = line.strip()
        if not stripped.startswith("{") or not stripped.endswith("}"):
            with self._lock:
                self._active_port = port
                self._last_raw_seen = time.monotonic()
            return

        with self._lock:
            self._active_port = port
            self._last_raw_seen = time.monotonic()
            self._decode_error_count += 1
            self._last_raw_line = stripped[:180]

    def _handle_legacy_line(self, port: str, line: str) -> bool:
        if "Empfangen" not in line and "PWM:" not in line:
            return False

        pwm_match = re.search(r"PWM:\s*(\d+)", line)
        dir_match = re.search(r"Dir:\s*(\d+)", line)
        brake_match = re.search(r"Brake:\s*(true|false|0|1)", line, re.IGNORECASE)

        raw = {
            "device": "esp32_actor",
            "type": "legacy_motor_status",
            "line": line[:180],
        }
        if pwm_match:
            legacy_pwm = max(0, min(80, int(pwm_match.group(1))))
            raw["legacy_pwm"] = legacy_pwm
            self._motor_percent = max(0, min(100, int(round(legacy_pwm / 0.8))))
        if dir_match:
            raw["legacy_direction"] = int(dir_match.group(1))
        if brake_match:
            brake_value = brake_match.group(1).lower()
            raw["legacy_brake"] = brake_value in {"true", "1"}

        with self._lock:
            self._active_port = port
            self._last_seen = time.monotonic()
            self._last_raw_seen = self._last_seen
            self._last_message_type = "legacy_motor_status"
            self._protocol = "legacy"
            self._message_count += 1
            self._last_raw_line = line[:180]
            self._raw = raw
            self._errors = []
        return True

    def _handle_reader_close(self, port: str, error: str) -> None:
        with self._lock:
            self._readers.pop(port, None)
            if error:
                self._port_errors[port] = error
            if self._active_port == port:
                self._active_port = None

    def _expire_if_stale(self) -> None:
        with self._lock:
            if self._last_seen is None:
                return
            if time.monotonic() - self._last_seen > self.timeout_seconds:
                self._active_port = None


class SerialReader:
    def __init__(
        self,
        port: str,
        baudrate: int,
        on_raw_line,
        on_message,
        on_decode_error,
        on_close,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.on_raw_line = on_raw_line
        self.on_message = on_message
        self.on_decode_error = on_decode_error
        self.on_close = on_close
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"esp32-actor-{port}", daemon=True)
        self._write_lock = threading.Lock()
        self._connection: Any | None = None

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._write_lock:
            if self._connection is not None:
                try:
                    self._connection.close()
                except Exception:
                    pass

    def write_line(self, line: str) -> bool:
        text = line.rstrip("\r\n") + "\n"
        with self._write_lock:
            if self._connection is None:
                return False
            self._connection.write(text.encode("utf-8"))
            self._connection.flush()
            return True

    def _run(self) -> None:
        try:
            with serial.Serial(self.port, self.baudrate, timeout=0.2) as connection:
                with self._write_lock:
                    self._connection = connection
                try:
                    connection.reset_input_buffer()
                except Exception:
                    pass

                buffer = ""
                while not self._stop.is_set():
                    raw_chunk = connection.read(connection.in_waiting or 1)
                    if not raw_chunk:
                        continue
                    buffer += raw_chunk.decode("utf-8", errors="ignore")
                    if len(buffer) > 4096:
                        buffer = buffer[-2048:]

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            self.on_raw_line(self.port, line)
                            self.on_message(self.port, json.loads(line))
                        except json.JSONDecodeError:
                            self.on_decode_error(self.port, line)
                            continue
        except Exception as exc:
            self.on_close(self.port, str(exc))
        finally:
            with self._write_lock:
                self._connection = None
