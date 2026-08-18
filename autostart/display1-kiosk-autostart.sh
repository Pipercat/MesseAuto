#!/usr/bin/env bash
set -u

LOG_DIR="$HOME/.cache/messeauto"
LOG_FILE="$LOG_DIR/display1-kiosk-autostart.log"
mkdir -p "$LOG_DIR"

{
  echo "[$(date --iso-8601=seconds)] MesseAuto Display 1 Autostart"

  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  if [ -S "$XDG_RUNTIME_DIR/bus" ]; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
  fi
  if [ -z "${WAYLAND_DISPLAY:-}" ] && [ -S "$XDG_RUNTIME_DIR/wayland-0" ]; then
    export WAYLAND_DISPLAY="wayland-0"
  fi
  if [ -n "${WAYLAND_DISPLAY:-}" ]; then
    export XDG_SESSION_TYPE="wayland"
    unset DISPLAY
  elif [ -z "${DISPLAY:-}" ] && [ -S /tmp/.X11-unix/X0 ]; then
    export DISPLAY=":0"
  fi

  for _ in $(seq 1 45); do
    if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  export MESSEAUTO_URL="http://127.0.0.1:8000/?screen=home"
  export MESSEAUTO_CHROMIUM_PROFILE="/tmp/messeauto-display1-profile"
  exec /home/messepi/Desktop/fahrzeugsteuerung-pi4/kiosk.sh
} >>"$LOG_FILE" 2>&1
