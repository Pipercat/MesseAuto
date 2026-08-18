from __future__ import annotations

import os
import platform
import random
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ============================================================
# Pin-Konfiguration
# ============================================================

@dataclass(frozen=True)
class PinDefinition:
    id: str
    label: str
    gpio: int
    group: str
    kind: str = "digital"


PIN_DEFINITIONS: tuple[PinDefinition, ...] = (
    PinDefinition("underbody", "Unterbodenbeleuchtung", 17, "lighting"),
    PinDefinition("lowBeam", "Abblendlicht", 27, "lighting"),
    PinDefinition("highBeam", "Fernlicht", 25, "lighting"),
    PinDefinition("indicatorLeft", "Blinker links", 26, "indicators"),
    PinDefinition("indicatorRight", "Blinker rechts", 5, "indicators"),
    PinDefinition("hazard", "Warnblinkanlage", 6, "indicators"),
    PinDefinition("freeOne", "Frei 1", 16, "extensions"),
    PinDefinition("freeTwo", "Frei 2", 23, "extensions"),
    PinDefinition("fan", "Lüfter", 24, "extensions"),
    PinDefinition("motor", "Motor-PWM", 22, "motor", "pwm"),
)

PIN_BY_ID = {pin.id: pin for pin in PIN_DEFINITIONS}
DIGITAL_IDS = tuple(pin.id for pin in PIN_DEFINITIONS if pin.kind == "digital")
MOTOR_ID = "motor"


# ============================================================
# Hilfsfunktionen
# ============================================================

def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "ja",
    }


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return float(value)
    except ValueError:
        return default


def running_on_raspberry_pi() -> bool:
    model_path = Path("/proc/device-tree/model")

    if model_path.exists():
        try:
            return "raspberry pi" in model_path.read_text(errors="ignore").lower()
        except OSError:
            return False

    return "raspberry" in platform.node().lower()


# ============================================================
# Basis-Controller
# ============================================================

class VehicleController:
    mode = "base"

    def __init__(self) -> None:
        self._lock = threading.RLock()

        # Das ist NUR der logische Zustand für die Webseite.
        # Der GPIO selbst bleibt NICHT dauerhaft an.
        self.outputs = {output_id: False for output_id in DIGITAL_IDS}

        self.motor_percent = 0

        # active_high=True:
        # Ruhe = LOW
        # Impuls = kurz HIGH
        #
        # active_high=False:
        # Ruhe = HIGH
        # Impuls = kurz LOW
        self.active_high = _env_bool("MESSEAUTO_ACTIVE_HIGH", True)

        # Impulsdauer für Lampen, Blinker, Lüfter usw.
        self.pulse_duration = _env_float("MESSEAUTO_PULSE_DURATION", 0.12)

        # Motor bleibt weiterhin PWM.
        self.motor_active_high = _env_bool("MESSEAUTO_MOTOR_ACTIVE_HIGH", True)
        self.motor_frequency = _env_int("MESSEAUTO_MOTOR_FREQUENCY", 1000)

    # --------------------------------------------------------
    # Button / Funktion drücken
    # --------------------------------------------------------

    def set_output(self, output_id: str, active: bool | None = None) -> dict[str, Any]:
        """
        Wichtig:
        Diese Funktion setzt KEINEN GPIO dauerhaft auf EIN oder AUS.

        Jeder Aufruf erzeugt nur einen kurzen Impuls.
        Der interne Zustand wird nur für die Webseite umgeschaltet/gespeichert.

        Beispiel:
        1. Klick auf Abblendlicht:
           GPIO 27 gibt kurzen Impuls
           Webseite zeigt Abblendlicht EIN

        2. Klick auf Abblendlicht:
           GPIO 27 gibt kurzen Impuls
           Webseite zeigt Abblendlicht AUS
        """

        if output_id not in DIGITAL_IDS:
            raise ValueError(f"Unbekannter Ausgang: {output_id}")

        with self._lock:
            if active is None:
                self.outputs[output_id] = not self.outputs[output_id]
            else:
                self.outputs[output_id] = bool(active)

            self._pulse_output_locked(output_id)

            return self.state()

    # --------------------------------------------------------
    # Mehrere Funktionen setzen
    # --------------------------------------------------------

    def set_outputs(self, changes: dict[str, bool]) -> dict[str, Any]:
        """
        Auch hier gilt:
        Es werden keine GPIOs dauerhaft geschaltet.

        Für jede Änderung wird nur ein kurzer Impuls ausgegeben.
        """

        unknown = sorted(set(changes) - set(DIGITAL_IDS))

        if unknown:
            raise ValueError(f"Unbekannte Ausgänge: {', '.join(unknown)}")

        with self._lock:
            for output_id, active in changes.items():
                requested_state = bool(active)

                # Nur wenn sich der logische Zustand ändert,
                # wird ein Impuls gesendet.
                if self.outputs[output_id] != requested_state:
                    self.outputs[output_id] = requested_state
                    self._pulse_output_locked(output_id)

            return self.state()

    # --------------------------------------------------------
    # Direktes Umschalten per Button
    # --------------------------------------------------------

    def toggle_output(self, output_id: str) -> dict[str, Any]:
        """
        Diese Methode ist ideal für echte Buttons:
        Jeder Klick toggelt intern EIN/AUS und sendet genau einen Impuls.
        """

        if output_id not in DIGITAL_IDS:
            raise ValueError(f"Unbekannter Ausgang: {output_id}")

        with self._lock:
            self.outputs[output_id] = not self.outputs[output_id]
            self._pulse_output_locked(output_id)

            return self.state()

    # --------------------------------------------------------
    # Nur Impuls ausgeben, ohne logischen Zustand zu ändern
    # --------------------------------------------------------

    def pulse_output(self, output_id: str) -> dict[str, Any]:
        """
        Diese Methode gibt wirklich NUR einen Impuls aus.
        Kein EIN/AUS-Zustand wird verändert.
        """

        if output_id not in DIGITAL_IDS:
            raise ValueError(f"Unbekannter Ausgang: {output_id}")

        with self._lock:
            self._pulse_output_locked(output_id)
            return self.state()

    # --------------------------------------------------------
    # Motor setzen
    # --------------------------------------------------------

    def set_motor(self, percent: int | float) -> dict[str, Any]:
        """
        Der Motor ist weiterhin PWM.
        Nur Lampen/Lüfter/Blinker sind Impuls-Ausgänge.
        """

        try:
            numeric_percent = int(round(float(percent)))
        except (TypeError, ValueError) as exc:
            raise ValueError("Motorwert muss eine Zahl zwischen 0 und 100 sein") from exc

        numeric_percent = max(0, min(100, numeric_percent))

        with self._lock:
            self._set_motor_locked(numeric_percent)
            return self.state()

    # --------------------------------------------------------
    # Reset
    # --------------------------------------------------------

    def reset(self) -> dict[str, Any]:
        """
        Reset setzt nur den internen Webseiten-Zustand zurück.
        GPIOs werden dabei nicht dauerhaft geschaltet.

        Falls eine Funktion intern noch als EIN gespeichert war,
        wird einmal ein Ausschalt-Impuls gesendet.
        """

        with self._lock:
            for output_id in DIGITAL_IDS:
                if self.outputs[output_id]:
                    self.outputs[output_id] = False
                    self._pulse_output_locked(output_id)
                else:
                    self.outputs[output_id] = False

            self._set_motor_locked(0)

            return self.state()

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    def state(self) -> dict[str, Any]:
        with self._lock:
            voltage = round((self.motor_percent / 100) * 5, 2)

            return {
                "mode": self.mode,
                "isRealHardware": self.mode == "gpio",

                # Nur logische Anzeige für die Webseite
                "outputs": dict(self.outputs),

                "motor": {
                    "percent": self.motor_percent,
                    "gpio": PIN_BY_ID[MOTOR_ID].gpio,
                    "frequency": self.motor_frequency,
                    "theoreticalVoltage": voltage,
                },

                "pins": [
                    {
                        "id": pin.id,
                        "label": pin.label,
                        "gpio": pin.gpio,
                        "group": pin.group,
                        "kind": pin.kind,
                    }
                    for pin in PIN_DEFINITIONS
                ],

                "settings": {
                    "digitalGpioMode": "pulse_only",
                    "activeHigh": self.active_high,
                    "pulseDuration": self.pulse_duration,
                    "motorActiveHigh": self.motor_active_high,
                },
            }

    # --------------------------------------------------------
    # Simulierte Messwerte
    # --------------------------------------------------------

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            light_load = sum(
                self.outputs[output_id]
                for output_id in (
                    "underbody",
                    "lowBeam",
                    "highBeam",
                )
            ) * 0.28

            indicator_load = sum(
                self.outputs[output_id]
                for output_id in (
                    "indicatorLeft",
                    "indicatorRight",
                    "hazard",
                )
            ) * 0.16

            fan_load = 0.38 if self.outputs["fan"] else 0

            extension_load = (
                (0.1 if self.outputs["freeOne"] else 0)
                + (0.1 if self.outputs["freeTwo"] else 0)
            )

            motor_load = self.motor_percent * 0.021
            noise = random.uniform(-0.04, 0.04)

            return {
                "source": "calculated",
                "current": round(
                    max(
                        0,
                        0.12
                        + light_load
                        + indicator_load
                        + fan_load
                        + extension_load
                        + motor_load
                        + noise,
                    ),
                    3,
                ),
                "voltage": round(
                    max(
                        0,
                        5
                        - self.motor_percent * 0.004
                        - max(0, noise) * 0.2,
                    ),
                    3,
                ),
                "pwm": self.motor_percent,
            }

    # --------------------------------------------------------
    # Beenden
    # --------------------------------------------------------

    def shutdown(self) -> None:
        self.reset()

    # --------------------------------------------------------
    # Interne Methoden
    # --------------------------------------------------------

    def _pulse_output_locked(self, output_id: str) -> None:
        """
        Simulation:
        Hier passiert elektrisch nichts.
        Die GPIO-Version überschreibt diese Methode.
        """
        pass

    def _set_motor_locked(self, percent: int) -> None:
        self.motor_percent = percent


# ============================================================
# Simulation
# ============================================================

class SimulationVehicleController(VehicleController):
    mode = "simulation"


# ============================================================
# GPIOZero Controller für echten Raspberry Pi
# ============================================================

class GPIOZeroVehicleController(VehicleController):
    mode = "gpio"

    def __init__(self) -> None:
        super().__init__()

        from gpiozero import DigitalOutputDevice, PWMOutputDevice

        self._digital_devices = {
            output_id: DigitalOutputDevice(
                PIN_BY_ID[output_id].gpio,
                active_high=self.active_high,
                initial_value=False,
            )
            for output_id in DIGITAL_IDS
        }

        self._motor_device = PWMOutputDevice(
            PIN_BY_ID[MOTOR_ID].gpio,
            active_high=self.motor_active_high,
            initial_value=0,
            frequency=self.motor_frequency,
        )

        # Sicherheit:
        # Alle digitalen GPIOs am Anfang in Ruhe.
        for device in self._digital_devices.values():
            device.off()

    # --------------------------------------------------------
    # Das ist der entscheidende Teil:
    # GPIO gibt NUR einen kurzen Impuls aus.
    # Danach ist der GPIO wieder aus.
    # --------------------------------------------------------

    def _pulse_output_locked(self, output_id: str) -> None:
        device = self._digital_devices[output_id]

        device.on()
        time.sleep(self.pulse_duration)
        device.off()

    # --------------------------------------------------------
    # Motor-PWM
    # --------------------------------------------------------

    def _set_motor_locked(self, percent: int) -> None:
        super()._set_motor_locked(percent)
        self._motor_device.value = percent / 100

    # --------------------------------------------------------
    # Beenden
    # --------------------------------------------------------

    def shutdown(self) -> None:
        try:
            self._set_motor_locked(0)

            for output_id in DIGITAL_IDS:
                self.outputs[output_id] = False

            for device in self._digital_devices.values():
                device.off()

        finally:
            for device in self._digital_devices.values():
                device.close()

            self._motor_device.close()


# ============================================================
# Controller erzeugen
# ============================================================

def create_controller() -> VehicleController:
    requested_mode = os.getenv("MESSEAUTO_GPIO_MODE", "auto").strip().lower()

    if requested_mode not in {
        "auto",
        "gpio",
        "real",
        "simulation",
        "sim",
    }:
        raise RuntimeError(
            "MESSEAUTO_GPIO_MODE muss auto, gpio oder simulation sein"
        )

    use_gpio = (
        requested_mode in {"gpio", "real"}
        or (
            requested_mode == "auto"
            and running_on_raspberry_pi()
        )
    )

    if not use_gpio:
        return SimulationVehicleController()

    try:
        return GPIOZeroVehicleController()

    except Exception as exc:
        if requested_mode in {"gpio", "real"} or running_on_raspberry_pi():
            raise RuntimeError(
                f"GPIO konnte nicht initialisiert werden: {exc}"
            ) from exc

        return SimulationVehicleController()
