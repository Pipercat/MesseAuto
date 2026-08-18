from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any


class DatabaseClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("MESSEAUTO_DATABASE_PI_URL", "").strip().rstrip("/")
        self.timeout = float(os.getenv("MESSEAUTO_DATABASE_TIMEOUT", "0.7"))
        self.last_ok: bool | None = None
        self.last_error = ""
        self.last_sent_at: float | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.base_url),
            "url": self.base_url,
            "lastOk": self.last_ok,
            "lastError": self.last_error,
            "lastSentAgeSeconds": None if self.last_sent_at is None else round(time.monotonic() - self.last_sent_at, 2),
        }

    def send_event(self, event_type: str, payload: dict[str, Any]) -> bool:
        if not self.base_url:
            return False

        body = json.dumps(
            {
                "event_type": event_type,
                "payload": {
                    "source_device": "touchscreen-pi",
                    **payload,
                },
            },
            ensure_ascii=False,
        ).encode("utf-8")

        request = urllib.request.Request(
            f"{self.base_url}/api/events",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                self.last_ok = 200 <= response.status < 300
                self.last_error = "" if self.last_ok else f"HTTP {response.status}"
                self.last_sent_at = time.monotonic()
                return self.last_ok
        except (OSError, urllib.error.URLError) as exc:
            self.last_ok = False
            self.last_error = str(exc)
            return False
