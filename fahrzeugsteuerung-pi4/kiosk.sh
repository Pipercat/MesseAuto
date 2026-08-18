#!/usr/bin/env bash
set -euo pipefail

URL="${MESSEAUTO_URL:-http://localhost:8000}"
PROFILE_DIR="${MESSEAUTO_CHROMIUM_PROFILE:-/tmp/messeauto-display1-profile}"
OZONE_FLAGS=()

if [ -n "${WAYLAND_DISPLAY:-}" ]; then
  OZONE_FLAGS+=(--ozone-platform=wayland)
fi

if command -v unclutter >/dev/null 2>&1; then
  unclutter -idle 0.2 -root >/dev/null 2>&1 &
fi

pkill -x chromium || true
sleep 1

chromium-browser \
  --user-data-dir="$PROFILE_DIR" \
  --kiosk \
  "${OZONE_FLAGS[@]}" \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  "$URL"
