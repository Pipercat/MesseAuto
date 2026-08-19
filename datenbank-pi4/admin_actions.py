from __future__ import annotations

import subprocess
from typing import Any

RESTARTABLE_SERVICES = ("messeauto-database.service",)


def restart_service(unit_name: str) -> dict[str, Any]:
    if unit_name not in RESTARTABLE_SERVICES:
        return {"ok": False, "error": f"Service '{unit_name}' nicht freigegeben"}
    try:
        subprocess.run(["sudo", "systemctl", "restart", unit_name], check=True, timeout=15)
        return {"ok": True}
    except Exception as error:
        return {"ok": False, "error": str(error)}


def reboot_pi2() -> dict[str, Any]:
    try:
        subprocess.Popen(["sudo", "systemctl", "reboot"])
        return {"ok": True}
    except Exception as error:
        return {"ok": False, "error": str(error)}


def shutdown_pi2() -> dict[str, Any]:
    try:
        subprocess.Popen(["sudo", "systemctl", "poweroff"])
        return {"ok": True}
    except Exception as error:
        return {"ok": False, "error": str(error)}
