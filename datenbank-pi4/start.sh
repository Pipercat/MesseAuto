#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv --system-site-packages
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

export MESSEAUTO_DB_HOST="${MESSEAUTO_DB_HOST:-0.0.0.0}"
export MESSEAUTO_DB_PORT="${MESSEAUTO_DB_PORT:-9000}"

python server.py
