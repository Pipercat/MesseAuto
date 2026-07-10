# MesseAuto

Verteilte Steuerungs-, Anzeige-, Sensor- und Simulationssoftware für das MesseAuto-Projekt.

## Systemaufbau

```text
Physische Taster
      │
      ▼
ESP32 Aktorik ── USB/JSON ──► Raspberry Pi 1 ── HTTP/JSON ──► Raspberry Pi 2
      │                              │                              │
      ├─ Lüfter / NeoPixel           ├─ GPIO-Impulse               ├─ Diagnose-Screen
      └─ Tasterereignisse             ├─ Fahrzeug-Screen            └─ SQLite-Telemetrie
                                      │
ESP32 Sensorik ── USB/JSON ───────────┘
      │
      ├─ Temperatur
      └─ Sitzabstand
```

## Ordner

| Ordner | Gerät / Aufgabe |
|---|---|
| `raspberry-pi-1/` | Hauptsteuerung, GPIO-Impulse, ESP-Erkennung, API und Fahrzeug-Display |
| `raspberry-pi-2/` | Diagnose, Tests, Telemetrie, SQLite und zweites Display |
| `esp32-actor/` | 10 Taster, Lüfter, NeoPixel und Tasterereignisse |
| `esp32-sensor/` | Temperatur- und Abstandssensorik |
| `simulation/` | PC-Simulation mit getrennten Pi- und ESP-Fenstern |

# Raspberry Pi 1

Pi 1 ist die zentrale Steuerung.

Funktionen:

- erkennt beide ESP32 automatisch über USB
- liest JSON-Zeilen mit 115200 Baud
- verarbeitet physische Tasterereignisse des ESP32
- erzeugt kurze GPIO-Impulse statt dauerhaftem HIGH
- stellt eine HTTP-API bereit
- zeigt die originale Fahrzeugsteuerung im Browser an
- verhindert, dass periodische alte ESP-Zustände Displaybefehle überschreiben

## GPIO-Belegung Pi 1

| Funktion | BCM GPIO |
|---|---:|
| Unterbodenbeleuchtung | 17 |
| Abblendlicht | 27 |
| Fernlicht | 25 |
| Blinker links | 6 |
| Blinker rechts | 5 |
| Lüfter | 22 |

## Start Pi 1

```bash
cd raspberry-pi-1
chmod +x start.sh
./start.sh
```

Display im Browser:

```text
http://<IP-VON-PI1>:5000/
```

Wichtige API-Endpunkte:

```text
GET  /api/health
GET  /api/state
GET  /api/pins
GET  /api/sensors
GET  /api/esp32
POST /api/functions/<id>/toggle
PUT  /api/functions/<id>
POST /api/all-off
```

# Raspberry Pi 2

Pi 2 fragt Pi 1 zyklisch ab, speichert Telemetrie und stellt eine Diagnoseoberfläche bereit.

## Start Pi 2

```bash
cd raspberry-pi-2
export MESSEAUTO_PI1_URL=http://<IP-VON-PI1>:5000
chmod +x start.sh
./start.sh
```

Display im Browser:

```text
http://<IP-VON-PI2>:5001/
```

API:

```text
GET  /api/health
GET  /api/state
GET  /api/history?limit=300
GET  /api/stats
POST /api/tests/lights
POST /api/tests/indicators
POST /api/tests/fan
POST /api/tests/all
POST /api/tests/all_off
```

Die SQLite-Datei `telemetry.db` wird automatisch erzeugt und ist absichtlich in `.gitignore` ausgeschlossen.

# ESP32 Aktorik

Datei:

```text
esp32-actor/esp32_actor.ino
```

Benötigte Arduino-Bibliothek:

- `Adafruit NeoPixel`

## Taster

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

Die Taster werden als aktiv LOW mit externen Pull-ups erwartet.

Direkte ESP-Ausgänge:

| Gerät | GPIO |
|---|---:|
| Lüfter | 22 |
| WS2812 / NeoPixel | 0 |

Der Sketch ist für 75 NeoPixel konfiguriert.

Wichtig: Der ESP sendet bei einem echten Tastendruck zusätzlich `event_button`. Pi 1 reagiert nur auf dieses Ereignis. Regelmäßige Statuspakete dienen nur zur Anzeige und überschreiben keine Pi-Befehle mehr.

Beispiel:

```json
{"device":"esp32_actor","states":{"highBeam":true},"event_button":1}
```

# ESP32 Sensorik

Datei:

```text
esp32-sensor/esp32_sensor.ino
```

Benötigte Arduino-Bibliotheken:

- `OneWire`
- `DallasTemperature`

Aktuelle Standardpins:

| Sensor | GPIO |
|---|---:|
| DS18B20 Datenleitung | 4 |
| Ultraschall Trigger | 18 |
| Ultraschall Echo | 19 |

Die Abstandsmessung verwendet mehrere Messungen und einen Medianfilter gegen Ausreißer.

Beispiel:

```json
{"device":"esp32_sensor","temperature_c":23.40,"seat_distance_cm":41.8,"uptime_ms":123456}
```

**Achtung:** Ein 5-V-Echo-Signal eines Ultraschallsensors darf nicht direkt an einen 3,3-V-ESP32-GPIO angeschlossen werden. Pegelwandler oder Spannungsteiler verwenden.

# PC-Simulation

Startdatei:

```text
simulation/index.html
```

Die Simulation enthält drei getrennte Ansichten:

```text
pi1-screen.html     → Raspberry-Pi-1-Fahrzeugdisplay
pi2-screen.html     → Raspberry-Pi-2-Diagnosedisplay
esp-testbench.html  → Taster, Sensoren und Aktoren der ESPs
```

Alle drei Fenster teilen denselben simulierten Zustand über den Browser-Speicher.

# Umgebungsvariablen

## Pi 1

```text
MESSEAUTO_PULSE_SECONDS=0.20
MESSEAUTO_SERIAL_BAUDRATE=115200
MESSEAUTO_SERIAL_STALE_SECONDS=5
MESSEAUTO_PORT_SCAN_SECONDS=3
```

## Pi 2

```text
MESSEAUTO_PI1_URL=http://127.0.0.1:5000
MESSEAUTO_POLL_SECONDS=1.0
MESSEAUTO_DB_PATH=telemetry.db
MESSEAUTO_REQUEST_TIMEOUT=2.0
```

# Aktueller Stand

Die Codes für alle vier Geräte, beide echten Pi-Displays und die PC-Simulation sind vorhanden. Die noch hardwareabhängigen Punkte sind die endgültige Sensor-Pinbelegung und der konkrete ESP32-Boardtyp beim Kompilieren.