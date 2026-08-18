# MesseAuto

Verteilte Steuerungs-, Anzeige-, Sensor- und Simulationssoftware für das MesseAuto/MesseCar-Projekt.

## Aktueller Sicherheits- und Architekturstand

> **ESP32 und Raspberry Pi 1 werden im realen Fahrzeug aktuell NICHT per USB miteinander verbunden.**
>
> Eine direkte USB-Verbindung stellt eine gemeinsame Masse zwischen ESP32 und Raspberry Pi her. Im vorhandenen Fahrzeugaufbau entsteht dadurch ein unerwünschter Ground-Pfad/Kurzschluss. Deshalb ist die USB/Serial-Kommunikation standardmäßig deaktiviert und bleibt nur als späterer Fallback im Code erhalten.

Der Zielaufbau verwendet **WLAN + MQTT** als primären Kommunikationsweg zwischen den ESP32 und Raspberry Pi 1. Die Funkstrecke soll vollständig lokal funktionieren und keine Cloud benötigen.

```text
Physische Taster
      │
      ▼
ESP32 Actor ───────── WLAN / MQTT ────────► Raspberry Pi 1 ── HTTP/JSON ──► Raspberry Pi 2
      │                                           │                              │
      ├─ Lüfter / NeoPixel                        ├─ GPIO-Impulse                 ├─ Diagnose-Screen
      └─ Tasterereignisse                         ├─ Fahrzeug-Screen              └─ SQLite-Telemetrie
                                                  │
ESP32 Sensor ──────── WLAN / MQTT ────────────────┘
      │
      ├─ Temperatur
      └─ Sitzabstand

USB/Serial ESP32 <-> Pi 1
      └─ deaktivierter Legacy-Fallback
```

Die vollständige, bereits definierte Umsetzung befindet sich in [`TASKS.md`](TASKS.md).

## Ordner

| Ordner | Gerät / Aufgabe |
|---|---|
| `raspberry-pi-1/` | Hauptsteuerung, GPIO-Impulse, API und Fahrzeug-Display |
| `raspberry-pi-2/` | Diagnose, Tests, Telemetrie, SQLite und zweites Display |
| `esp32-actor/` | 10 Taster, Lüfter, NeoPixel und Tasterereignisse |
| `esp32-sensor/` | Temperatur- und Abstandssensorik |
| `simulation/` | PC-Simulation mit getrennten Pi- und ESP-Fenstern |

# Raspberry Pi 1

Pi 1 ist die zentrale Steuerung.

Funktionen:

- erzeugt kurze GPIO-Impulse statt dauerhaftem HIGH
- stellt eine HTTP-API bereit
- zeigt die Fahrzeugsteuerung im Browser an
- verwaltet den logischen Fahrzeugzustand
- soll zukünftig ESP32 Actor und Sensor primär per WLAN/MQTT anbinden
- enthält weiterhin die alte USB/Serial-Implementierung als deaktivierten Fallback

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

Display:

```text
http://<IP-VON-PI1>:5000/
```

API:

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

## USB/Serial-Fallback

Serial ist standardmäßig deaktiviert:

```text
MESSEAUTO_SERIAL_ENABLED=false
```

Nur in einem hardwareseitig sicheren Aufbau darf der Legacy-Fallback bewusst aktiviert werden:

```bash
export MESSEAUTO_SERIAL_ENABLED=true
```

Die Aktivierung stellt **keine** galvanische Trennung her. Vorher muss hardwareseitig sichergestellt sein, dass die gemeinsame USB-Masse keinen problematischen Strompfad erzeugt.

# Zielkommunikation WLAN / MQTT

Geplant und verbindlich definiert:

- Pi 1 stellt bevorzugt ein eigenes lokales MesseCar-WLAN bereit.
- ESP32 Actor und Sensor verbinden sich automatisch damit.
- lokaler Mosquitto-Broker auf/bei Pi 1
- keine Cloud
- MQTT mit klaren Topics, Online/Offline-Status und Reconnect-Logik
- physische Taster funktionieren auch bei WLAN-Ausfall lokal weiter
- Reconnect darf keine alten Befehle erneut schalten

Vorgesehene Topics:

```text
messecar/actor/status
messecar/actor/event/button
messecar/actor/state
messecar/actor/command
messecar/sensor/status
messecar/sensor/telemetry
messecar/pi1/status
```

Details und Abnahmekriterien: [`TASKS.md`](TASKS.md).

# Raspberry Pi 2

Pi 2 fragt Pi 1 zyklisch ab, speichert Telemetrie und stellt eine Diagnoseoberfläche bereit.

## Start Pi 2

```bash
cd raspberry-pi-2
export MESSEAUTO_PI1_URL=http://<IP-VON-PI1>:5000
chmod +x start.sh
./start.sh
```

Display:

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

# ESP32 Actor

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

Der Sketch ist aktuell für 75 NeoPixel konfiguriert.

Die bestehende Serial-Logik bleibt im Sketch zunächst erhalten, soll aber nicht als normale Fahrzeugverbindung verwendet werden. Die Zielimplementierung überträgt echte Tastendrücke als MQTT-Events und empfängt Zustandsbefehle von Pi 1 über MQTT.

# ESP32 Sensor

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

**Achtung:** Ein 5-V-Echo-Signal eines Ultraschallsensors darf nicht direkt an einen 3,3-V-ESP32-GPIO angeschlossen werden. Pegelwandler oder Spannungsteiler verwenden.

# PC-Simulation

Startdatei:

```text
simulation/index.html
```

Ansichten:

```text
pi1-screen.html     → Raspberry-Pi-1-Fahrzeugdisplay
pi2-screen.html     → Raspberry-Pi-2-Diagnosedisplay
esp-testbench.html  → Taster, Sensoren und Aktoren der ESPs
```

Alle drei Fenster teilen denselben simulierten Zustand über den Browser-Speicher. Die Simulation soll im Zuge des MQTT-Umbaus zusätzlich Offline-/Reconnect- und Kommunikationsfehler abbilden.

# Umgebungsvariablen

## Pi 1

```text
MESSEAUTO_PULSE_SECONDS=0.20
MESSEAUTO_SERIAL_ENABLED=false
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

Vorhanden sind die Codes für Pi 1, Pi 2, ESP32 Actor, ESP32 Sensor, beide Pi-Displays und die PC-Simulation.

**Aktuell umgesetzt:**

- Pi-1-GPIO-/API-/Display-Logik
- Pi-2-Diagnose und SQLite-Telemetrie
- ESP-Actor- und Sensor-Grundlogik
- PC-Simulation
- Legacy-USB/Serial-Code
- USB/Serial auf Pi 1 standardmäßig deaktiviert

**Als nächstes umzusetzen:**

- lokales MesseCar-WLAN
- MQTT-Broker
- MQTT-Client auf Pi 1
- WLAN/MQTT auf beiden ESP32
- definierter Event-/State-/Command-Fluss
- Offline-/Reconnect-Handling
- Diagnose- und Simulationserweiterung

Die Reihenfolge und Definition of Done stehen in [`TASKS.md`](TASKS.md).
