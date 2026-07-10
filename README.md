# MesseAuto

Verteilte Steuerungssoftware für das MesseAuto-Projekt.

## Geräte

```text
Raspberry Pi 1 (Hauptsteuerung/API)
├── steuert GPIO-Ausgänge als kurze Impulse
├── verbindet ESP32 Aktorik und ESP32 Sensorik per USB/Serial
├── stellt HTTP-API bereit
└── hält den aktuellen Fahrzeugzustand

Raspberry Pi 2 (Anzeige/Datensammler)
├── fragt Pi 1 zyklisch ab
├── speichert Messwerte lokal in SQLite
└── stellt Statusdaten für eine Anzeige bereit

ESP32 Aktorik
├── liest 10 Fahrzeugtaster
├── schaltet Lichtfunktionen als Toggle
├── steuert Blinker/Warnblinker
├── steuert Unterboden-Neopixel
└── steuert Lüfter

ESP32 Sensorik
├── misst Temperatur
├── misst Sitzabstand
└── sendet JSON-Zeilen über USB/Serial
```

## Ordner

- `raspberry-pi-1/` – zentrale Fahrzeugsteuerung
- `raspberry-pi-2/` – Telemetrie und lokale Datenhaltung
- `esp32-actor/` – Aktorik, Taster und Beleuchtung
- `esp32-sensor/` – Sensorik

## Bekannte Pinbelegung ESP32 Aktorik

| Taster | GPIO | Funktion |
|---|---:|---|
| 1 | 33 | Fernlicht |
| 2 | 15 | Abblendlicht |
| 3 | 25 | Unterbodenbeleuchtung |
| 4 | 35 | Blinker links |
| 5 | 14 | Blinker rechts |
| 6 | 27 | Warnblinker |
| 7 | 34 | Lüfter |
| 8 | 13 | Reserve |
| 9 | 26 | Reserve |
| 10 | 32 | Reserve |

## Raspberry-Pi-GPIOs

Die Steuerung nutzt kurze Impulse statt dauerhaftem HIGH/LOW. Das passt zur bisherigen Anforderung, dass Lampen, Lüfter und weitere Funktionen über Tasterimpulse ein- und ausgeschaltet werden.

| Funktion | BCM GPIO |
|---|---:|
| Unterbodenbeleuchtung | 17 |
| Abblendlicht | 27 |
| Fernlicht | 25 |
| Blinker links | 6 |
| Blinker rechts | 5 |
| Lüfter | 22 |

## Start

### Raspberry Pi 1

```bash
cd raspberry-pi-1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Raspberry Pi 2

```bash
cd raspberry-pi-2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export MESSEAUTO_PI1_URL=http://<IP-VON-PI1>:5000
python collector.py
```

### ESP32

Die jeweiligen `.ino`-Dateien mit Arduino IDE oder PlatformIO flashen.

## Serielles Protokoll

Beide ESP32 senden genau eine JSON-Struktur pro Zeile.

Aktorik:

```json
{"device":"esp32_actor","states":{"highBeam":true,"lowBeam":false}}
```

Sensorik:

```json
{"device":"esp32_sensor","temperature_c":23.4,"seat_distance_cm":41.8}
```

Dadurch kann Pi 1 die Geräte automatisch unterscheiden.