#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="messeauto.service"
SERVICE_USER="$(id -un)"
GPIO_GROUP_LINE=""

if getent group gpio >/dev/null; then
  GPIO_GROUP_LINE="SupplementaryGroups=gpio"
fi

echo "Installiere Systempakete..."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-gpiozero python3-lgpio chromium-browser unclutter

echo "Erzeuge Python-Umgebung..."
cd "$PROJECT_DIR"
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Installiere systemd-Service..."
sudo tee "/etc/systemd/system/$SERVICE_NAME" >/dev/null <<SERVICE
[Unit]
Description=MesseAuto Fahrzeugsteuerung
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/.venv/bin/python $PROJECT_DIR/app.py
Environment=MESSEAUTO_GPIO_MODE=auto
Environment=MESSEAUTO_HOST=0.0.0.0
Environment=MESSEAUTO_PORT=8000
Environment=MESSEAUTO_ACTIVE_HIGH=1
Environment=MESSEAUTO_MOTOR_ACTIVE_HIGH=1
Environment=MESSEAUTO_MOTOR_FREQUENCY=1000
Environment=MESSEAUTO_DATABASE_PI_URL=http://10.42.0.12:9000
Environment=MESSEAUTO_DATABASE_TIMEOUT=1.0
Environment=MESSEAUTO_HEARTBEAT_INTERVAL=5
Environment=MESSEAUTO_ESP32_ACTOR_ENABLED=1
Environment=MESSEAUTO_ESP32_ACTOR_BAUDRATE=115200
Environment=MESSEAUTO_ESP32_ACTOR_TIMEOUT=3
Environment=MESSEAUTO_ESP32_PORTS=/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0
Environment=MESSEAUTO_PULSE_DURATION=0.12
Restart=on-failure
RestartSec=2
User=$SERVICE_USER
$GPIO_GROUP_LINE

[Install]
WantedBy=multi-user.target
SERVICE
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo
echo "Fertig."
echo "Start:   sudo systemctl start $SERVICE_NAME"
echo "Status:  sudo systemctl status $SERVICE_NAME"
echo "Browser: http://localhost:8000"
echo
echo "Kiosk optional im Pi-Browser:"
echo "chromium-browser --kiosk http://localhost:8000"
