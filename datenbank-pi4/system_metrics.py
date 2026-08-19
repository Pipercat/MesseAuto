from __future__ import annotations

import platform
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import psutil

BOOT_TIME = psutil.boot_time()
DB_PATH = Path("vehicle_tests.db")


def _cpu_temperature_c() -> float | None:
    try:
        output = subprocess.run(
            ["vcgencmd", "measure_temp"], capture_output=True, text=True, timeout=2
        ).stdout.strip()
        return float(output.split("=")[1].split("'")[0])
    except Exception:
        return None


def _throttled_status() -> dict[str, Any] | None:
    try:
        output = subprocess.run(
            ["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=2
        ).stdout.strip()
        raw = int(output.split("=")[1], 16)
        return {
            "raw": output.split("=")[1],
            "under_voltage_now": bool(raw & 0x1),
            "throttled_now": bool(raw & 0x4),
            "under_voltage_occurred": bool(raw & 0x10000),
            "throttled_occurred": bool(raw & 0x40000),
        }
    except Exception:
        return None


def system_metrics() -> dict[str, Any]:
    cpu_percent = psutil.cpu_percent(interval=0.2)
    cpu_percent_per_core = psutil.cpu_percent(interval=0, percpu=True)
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/")

    return {
        "hostname": socket.gethostname(),
        "os": platform.platform(),
        "kernel": platform.release(),
        "uptime_s": time.time() - BOOT_TIME,
        "boot_time": BOOT_TIME,
        "cpu": {"percent": cpu_percent, "percent_per_core": cpu_percent_per_core, "temperature_c": _cpu_temperature_c()},
        "throttled": _throttled_status(),
        "memory": {
            "total_bytes": memory.total,
            "used_bytes": memory.used,
            "available_bytes": memory.available,
            "percent": memory.percent,
        },
        "swap": {"total_bytes": swap.total, "used_bytes": swap.used, "percent": swap.percent},
        "disk": {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "percent": disk.percent,
        },
        "sqlite_db_bytes": DB_PATH.stat().st_size if DB_PATH.exists() else None,
    }


def service_status(unit_names: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for unit in unit_names:
        try:
            output = subprocess.run(
                ["systemctl", "is-active", unit], capture_output=True, text=True, timeout=3
            ).stdout.strip()
            result[unit] = output or "unknown"
        except Exception:
            result[unit] = "unknown"
    return result
