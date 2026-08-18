#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSH_KEY="${MESSEAUTO_SSH_KEY:-/Users/marvinmayer/.ssh/camserver_migration_ed25519}"
DATA_HOST="${MESSEAUTO_DATA_HOST:-2a01:599:b1f:33b0:b516:7c23:2583:cca6}"
DATA_USER="${MESSEAUTO_DATA_USER:-messedata}"
VEHICLE_HOST="${MESSEAUTO_VEHICLE_HOST:-172.20.10.2}"
VEHICLE_USER="${MESSEAUTO_VEHICLE_USER:-messepi}"

COMMON_SSH=(-i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10)
PROXY_COMMAND="ssh -i $SSH_KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -W %h:%p $DATA_USER@$DATA_HOST"

run_local_checks() {
  python3 -m py_compile \
    "$ROOT_DIR/fahrzeugsteuerung-pi4/app.py" \
    "$ROOT_DIR/fahrzeugsteuerung-pi4/database_client.py" \
    "$ROOT_DIR/fahrzeugsteuerung-pi4/esp32_actor_bridge.py" \
    "$ROOT_DIR/datenbank-pi4/server.py" \
    "$ROOT_DIR/datenbank-pi4/database.py"

  node --check "$ROOT_DIR/fahrzeugsteuerung-pi4/web/app.js"
}

run_data_pi() {
  ssh "${COMMON_SSH[@]}" "$DATA_USER@$DATA_HOST" "$@"
}

run_vehicle_pi() {
  ssh "${COMMON_SSH[@]}" -o "ProxyCommand=$PROXY_COMMAND" "$VEHICLE_USER@$VEHICLE_HOST" "$@"
}

check_kiosk_count() {
  local label="$1"
  local command="$2"
  local count
  count="$(eval "$command" | tr -d '[:space:]')"
  if [[ "$count" != "1" ]]; then
    printf '%s: expected one kiosk main window, got %s\n' "$label" "$count" >&2
    return 1
  fi
}

run_local_checks

run_data_pi 'systemctl is-active messeauto-database.service'
run_data_pi 'curl -fsS http://127.0.0.1:9000/health >/dev/null'
run_data_pi 'curl -fsS http://127.0.0.1:9000/api/dashboard >/dev/null'

run_vehicle_pi 'systemctl is-active messeauto.service'
run_vehicle_pi 'curl -fsS http://127.0.0.1:8000/health >/dev/null'
run_vehicle_pi 'curl -fsS -X POST http://127.0.0.1:8000/api/database/ping >/dev/null'

check_kiosk_count "Display 2" "run_data_pi \"pgrep -a chromium | grep -- '--kiosk' | grep -v -- '--type=' | wc -l\""
check_kiosk_count "Display 1" "run_vehicle_pi \"pgrep -a chromium | grep -- '--kiosk' | grep -v -- '--type=' | wc -l\""

printf 'MesseAuto validation OK\n'
