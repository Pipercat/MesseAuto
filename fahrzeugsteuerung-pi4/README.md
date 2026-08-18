# MesseAuto Fahrzeugsteuerung für Raspberry Pi 4

Fertiges Pi4-Projekt für die Bertrandt-Touchscreen-Oberfläche mit echter GPIO-Ansteuerung.

## Enthalten

- Moderne Touchscreen-Weboberfläche im Bertrandt-Design
- Flask-Backend mit REST-API
- GPIO-Ausgänge nach vorgegebener Pinstruktur
- Motor-PWM auf GPIO 22
- Automatische Testabläufe
- Live-Grafen mit berechneten Messwerten
- Simulationsmodus für Entwicklung außerhalb des Raspberry Pi
- Installskript und systemd-Service

## Projekt auf den Pi kopieren

Beispiel per `scp` vom Mac:

```bash
scp -r "/Users/marvinmayer/Desktop/MesseAuto/fahrzeugsteuerung-pi4" pi@raspberrypi.local:/home/pi/
```

Oder den Ordner per USB-Stick auf den Pi kopieren. Das Installskript erkennt den tatsächlichen Projektpfad automatisch.

## Installation auf dem Pi

```bash
cd /home/pi/fahrzeugsteuerung-pi4
chmod +x install_pi.sh start.sh
./install_pi.sh
sudo systemctl start messeauto.service
```

Danach im Pi-Browser öffnen:

```text
http://localhost:8000
```

Von einem anderen Gerät im gleichen Netzwerk:

```text
http://<pi-ip-adresse>:8000
```

## Manueller Start ohne Service

```bash
cd /home/pi/fahrzeugsteuerung-pi4
./start.sh
```

## Kiosk-Start auf dem Touchscreen

```bash
cd /home/pi/fahrzeugsteuerung-pi4
./kiosk.sh
```

Das öffnet Chromium im Vollbild auf `http://localhost:8000`.

Im Live-Aufbau soll Display 1 am Ende auf dem Home-Screen stehen:

```text
http://127.0.0.1:8000/?screen=home
```

## Pinstruktur

Siehe [PINOUT.md](PINOUT.md).

Kurzfassung:

| Funktion | BCM-GPIO |
| --- | ---: |
| Unterbodenbeleuchtung | 17 |
| Abblendlicht | 27 |
| Fernlicht | 25 |
| Blinker links | 26 |
| Blinker rechts | 5 |
| Warnblinkanlage | 6 |
| Frei 1 | 16 |
| Frei 2 | 23 |
| Lüfter | 24 |
| Motor-PWM | 22 |

## Modi

Standard ist:

```text
MESSEAUTO_GPIO_MODE=auto
```

Auf einem Raspberry Pi wird echte Hardware verwendet. Auf einem Mac oder PC startet die App automatisch im Simulationsmodus.

Manuell erzwingen:

```bash
MESSEAUTO_GPIO_MODE=simulation ./start.sh
MESSEAUTO_GPIO_MODE=gpio ./start.sh
```

## API

```http
GET  /api/state
GET  /api/metrics
GET  /api/esp32/actor
POST /api/output/<id>
POST /api/outputs
POST /api/motor
POST /api/reset
POST /api/test-result
```

Beispiel:

```bash
curl -X POST http://localhost:8000/api/output/lowBeam \
  -H "Content-Type: application/json" \
  -d '{"active": true}'
```

Motor:

```bash
curl -X POST http://localhost:8000/api/motor \
  -H "Content-Type: application/json" \
  -d '{"percent": 50}'
```

## Sicherheit

Die GPIOs liefern nur 3,3 V Logik und dürfen keine Lasten direkt treiben. Für LEDs, Relais, Motor und Lüfter müssen geeignete Treiber- oder Relaismodule verwendet werden.

Die Software nutzt BCM-GPIO-Nummern. Die physischen Pin-Nummern stehen in [PINOUT.md](PINOUT.md).

## Messe-Setup

Live-Datenbank-Pi:

```text
MESSEAUTO_DATABASE_PI_URL=http://10.42.0.12:9000
MESSEAUTO_HEARTBEAT_INTERVAL=5
```

ESP-Aktor:

```text
MESSEAUTO_ESP32_ACTOR_ENABLED=0
```

Der ESP32 ist im finalen Messeaufbau kein laufend verbundenes Pi-Serial-Geraet.
Er wird einmal per PC/Mac geflasht und danach im Fahrzeug eingesteckt. Die
Touchscreen-Steuerung gibt kurze Impulse auf Raspberry-Pi-GPIOs. Diese GPIOs
schalten Relaiskontakte, die parallel zu den echten Buttons auf den ESP32-
Buttonpins liegen. Der ESP sieht dadurch einen normalen Buttondruck und schaltet
den Aktor selbst.

| Touch-Funktion | Pi BCM-GPIO | ESP32 Button-GPIO |
| --- | ---: | ---: |
| Fernlicht | 25 | 33 |
| Abblendlicht | 27 | 15 |
| Unterboden | 17 | 25 |
| Blinker links | 26 | 35 |
| Blinker rechts | 5 | 14 |
| Warnblinker | 6 | 27 |
| Luefter | 24 | 34 |
| Frei 1 | 16 | 13 |
| Frei 2 | 23 | 26 |

Dadurch bleiben manuelle Buttons in derselben Schaltung nutzbar, und der Pi
oeffnet im Betrieb keinen ESP-USB-Port.

Der Status `/api/esp32/actor` bleibt nur als Diagnosehinweis vorhanden und meldet
im Normalbetrieb `standalone_pc_flash`.
