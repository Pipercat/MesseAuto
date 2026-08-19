from __future__ import annotations

import subprocess
from typing import Any, Callable

# MA-12-032: nur explizite, feste Aktionen - keine freie Shell/sudo-Eingabe
# ueber die Weboberflaeche. Servicenamen sind fest verdrahtet, nicht
# nutzergesteuert.
RESTARTABLE_SERVICES = ("messeauto.service", "mosquitto.service")


def restart_service(unit_name: str) -> dict[str, Any]:
    if unit_name not in RESTARTABLE_SERVICES:
        return {"ok": False, "error": f"Service '{unit_name}' nicht freigegeben"}
    try:
        subprocess.run(["sudo", "systemctl", "restart", unit_name], check=True, timeout=15)
        return {"ok": True}
    except Exception as error:
        return {"ok": False, "error": str(error)}


def reboot_pi1(safe_shutdown: Callable[[], None]) -> dict[str, Any]:
    # MA-12-020: vor Reboot alle Ausgaenge sicher aus (Drive/Hupe folgen mit M10/M11).
    try:
        safe_shutdown()
        subprocess.Popen(["sudo", "systemctl", "reboot"])
        return {"ok": True}
    except Exception as error:
        return {"ok": False, "error": str(error)}


def shutdown_pi1(safe_shutdown: Callable[[], None]) -> dict[str, Any]:
    try:
        safe_shutdown()
        subprocess.Popen(["sudo", "systemctl", "poweroff"])
        return {"ok": True}
    except Exception as error:
        return {"ok": False, "error": str(error)}
