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

export MESSEAUTO_GPIO_MODE="${MESSEAUTO_GPIO_MODE:-auto}"
export MESSEAUTO_HOST="${MESSEAUTO_HOST:-0.0.0.0}"
export MESSEAUTO_PORT="${MESSEAUTO_PORT:-8000}"

python app.py
