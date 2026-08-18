#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKETCH_DIR="$SCRIPT_DIR/esp32_actor"
FQBN="${FQBN:-esp32:esp32:esp32}"

if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "arduino-cli nicht gefunden. Bitte Arduino CLI installieren oder PATH pruefen." >&2
  exit 1
fi

PORT="${1:-${ESP32_PORT:-}}"
if [ -z "$PORT" ]; then
  echo "Kein Port angegeben." >&2
  echo "Verfuegbare Ports:" >&2
  arduino-cli board list >&2 || true
  echo "" >&2
  echo "Aufruf: $0 /dev/cu.SLAB_USBtoUART" >&2
  echo "oder:   ESP32_PORT=/dev/cu.SLAB_USBtoUART $0" >&2
  exit 2
fi

arduino-cli compile --fqbn "$FQBN" "$SKETCH_DIR"
arduino-cli upload -p "$PORT" --fqbn "$FQBN" "$SKETCH_DIR"

echo "ESP32-Aktor geflasht. Danach vom PC abziehen und im Fahrzeug einstecken."
