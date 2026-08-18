#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="messeauto-database.service"
SERVICE_USER="$(id -un)"

echo "Installiere Systempakete..."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip chromium-browser unclutter

echo "Erzeuge Python-Umgebung..."
cd "$PROJECT_DIR"
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Installiere systemd-Service..."
sudo tee "/etc/systemd/system/$SERVICE_NAME" >/dev/null <<SERVICE
[Unit]
Description=MesseAuto Datenbank-Pi
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/.venv/bin/python $PROJECT_DIR/server.py
Environment=MESSEAUTO_DB_HOST=0.0.0.0
Environment=MESSEAUTO_DB_PORT=9000
Restart=on-failure
RestartSec=2
User=$SERVICE_USER

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo "Fertig. Start: sudo systemctl start $SERVICE_NAME"
