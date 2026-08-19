from __future__ import annotations

import threading
import time
from typing import Any, Callable

KEEPALIVE_INTERVAL_S = 0.1  # ~10 Hz waehrend die Hupe aktiv ist (MA-11-010)


class HornController:
    """Zentraler Horn-Input-State auf Pi 1 (MA-11-007A/MA-11-014).

    Effektiver Sollzustand = physical_pressed OR screen_pressed. Jede Flanke
    aktualisiert den Zustand sofort; solange effektiv aktiv, laeuft ein
    Keepalive mit ~10 Hz. Ein MQTT-Ausfall beim Publish darf die UI/den
    Zustandsautomat nie blockieren (publish_fn ist best-effort/non-blocking).
    """

    def __init__(self, publish_fn: Callable[[dict[str, Any]], bool]) -> None:
        self._publish_fn = publish_fn
        self._lock = threading.RLock()
        self._physical_pressed = False
        self._screen_pressed = False
        self._effective = False
        self._keepalive_stop = threading.Event()
        self._keepalive_thread: threading.Thread | None = None

    def _effective_state(self) -> bool:
        return self._physical_pressed or self._screen_pressed

    def _apply(self) -> None:
        new_effective = self._effective_state()
        if new_effective == self._effective:
            return
        self._effective = new_effective
        self._publish_fn({"active": new_effective})

        if new_effective:
            self._start_keepalive()
        else:
            self._stop_keepalive()

    def _start_keepalive(self) -> None:
        if self._keepalive_thread and self._keepalive_thread.is_alive():
            return
        self._keepalive_stop.clear()
        self._keepalive_thread = threading.Thread(target=self._keepalive_loop, daemon=True)
        self._keepalive_thread.start()

    def _stop_keepalive(self) -> None:
        self._keepalive_stop.set()

    def _keepalive_loop(self) -> None:
        while not self._keepalive_stop.wait(KEEPALIVE_INTERVAL_S):
            with self._lock:
                if not self._effective:
                    return
            self._publish_fn({"active": True})

    def set_physical(self, pressed: bool) -> None:
        with self._lock:
            self._physical_pressed = pressed
            self._apply()

    def set_screen(self, pressed: bool) -> None:
        with self._lock:
            self._screen_pressed = pressed
            self._apply()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "physical_pressed": self._physical_pressed,
                "screen_pressed": self._screen_pressed,
                "effective": self._effective,
            }
