#!/usr/bin/env bash
set -u

LOG_DIR="$HOME/.cache/messeauto"
LOG_FILE="$LOG_DIR/display2-manual-start.log"
mkdir -p "$LOG_DIR"

{
  echo "[$(date --iso-8601=seconds)] Manueller Start Display 2"

  if command -v systemctl >/dev/null 2>&1; then
    sudo -n /usr/bin/systemctl restart messeauto-database.service >/dev/null 2>&1 || true
  fi

  setsid -f "$HOME/.config/messeauto/display2-kiosk-autostart.sh" >/dev/null 2>&1
} >>"$LOG_FILE" 2>&1
