# MesseAuto

Interaktives Demonstrationsfahrzeug zur digitalen Fahrzeugsteuerung (MesseAuto/MesseCar-Projekt).

Das Projekt besteht aus zwei Raspberry Pis und zwei ESP32-Mikrocontrollern:

- Display 1 / Fahrzeug-Pi (`messepi`): Touchscreen, Fahrzeuglogik, GPIO-Impulsrelais, Motor-PWM, MQTT-Client.
- Display 2 / Datenbank-Pi (`messedata`): SQLite-Datenbank, Live-Diagnose, Testprotokolle.
- ESP32 Actor: 10 Taster, Lüfter, NeoPixel; läuft standalone im Fahrzeug, verbunden per WLAN/MQTT mit Pi 1.
- ESP32 Sensor/Aux: Temperatur, Sitzabstand; WLAN/MQTT vorbereitet, Hardware aktuell nicht angeschlossen.

## Aktueller Sicherheits- und Architekturstand

> **ESP32 und Raspberry Pi 1 werden im realen Fahrzeug NICHT dauerhaft per USB miteinander verbunden.** Eine direkte USB-Verbindung stellt eine gemeinsame Masse her und erzeugt im vorhandenen Fahrzeugaufbau einen unerwünschten Ground-Pfad. USB/Serial ist deshalb standardmäßig deaktiviert und bleibt nur als galvanisch sicherer Legacy-Fallback im Code.

Primärer Kommunikationsweg ist **WLAN + MQTT**, vollständig lokal ohne Cloud: Pi 1 betreibt einen eigenen `MesseCar`-WLAN-AP (`ap0`) mit lokalem Mosquitto-Broker, parallel zur bestehenden WLAN-Nutzung für SSH/Programmierung. Details: [`HARDWARE.md`](HARDWARE.md), Topics/Format: [`MQTT.md`](MQTT.md).

Zusätzlich existiert weiterhin die ältere, rein elektrische Kopplung: Pi 1 gibt kurze GPIO-Impulse auf Relais, deren Kontakte parallel zu den echten Tastern auf denselben ESP32-Buttonpins liegen — der ESP32 sieht dadurch einen normalen Tastendruck. Beide Pfade (Relais-Kopplung und MQTT) sind aktuell gleichzeitig aktiv; siehe `TASKS.md` M9 für den geplanten Volltest ausschließlich über WLAN/MQTT.

Umsetzungsstand aller Einzelaufgaben inkl. Testnachweisen: [`TASKS.md`](TASKS.md).

## Ordner

| Ordner | Gerät / Aufgabe |
|---|---|
| `fahrzeugsteuerung-pi4/` | Pi 1: Hauptsteuerung, GPIO-Impulse, API, MQTT-Client, Fahrzeug-Display |
| `datenbank-pi4/` | Pi 2: Diagnose, Tests, Live-Zustände, Telemetrie, SQLite und zweites Display |
| `esp32-codes/esp32_actor/` | ESP32 Actor: 10 Taster, Lüfter, NeoPixel, WLAN/MQTT |
| `esp32-codes/esp32_sensor/` | ESP32 Sensor/Aux: Temperatur- und Abstandssensorik, WLAN/MQTT (vorbereitet, ungetestet) |
| `simulation/` | MQTT-Simulator für Actor/Sensor ohne physische ESP-Hardware |

## Live-System

| System | Nutzer | Dienst | URL |
| --- | --- | --- | --- |
| Fahrzeug-Pi | `messepi` | `messeauto.service` | `http://127.0.0.1:8000/?screen=home` |
| Datenbank-Pi | `messedata` | `messeauto-database.service` | `http://127.0.0.1:9000/` |

LAN zwischen den Pis:

- Fahrzeug-/Prüfungs-Pi `eth0`: `10.42.0.11`
- Datenbank-Pi `eth0`: `10.42.0.12`
- Datenfluss Fahrzeug → Datenbank: `http://10.42.0.12:9000`
- WLAN bleibt für SSH/Programmierung; die Pi-zu-Pi-Verbindung läuft über LAN.

Auf beiden Desktops liegt `MesseAuto starten.desktop`. Doppelklick startet den jeweiligen systemd-Dienst neu und öffnet genau ein Chromium-Kioskfenster auf der passenden Display-URL.

Der Fahrzeug-Pi sendet periodisch `vehicle_heartbeat`, `actor_status` und Testresultate an den Datenbank-Pi, inklusive MQTT-Transportstatus (`transport`, `connected`, `last_seen`) des ESP32 Actor.

## Abnahme

Der schnelle Check läuft vom Mac aus:

```bash
/Users/marvinmayer/Desktop/MesseAuto/scripts/validate_messeauto.sh
```

Danach auf Display 1 alle Ansichten prüfen: Home, Fahrzeug, Tests, Pi & Relais. Display 1 muss am Ende wieder auf `/?screen=home` stehen, Display 2 bleibt auf `/`.

## ESP32 flashen

Der aktive Actor-Sketch ist `esp32-codes/esp32_actor/esp32_actor.ino` (Buttonpins `33, 15, 25, 35, 14, 27, 34, 13, 26, 32`; LOW bedeutet gedrückt; GPIO34/35 brauchen externe Pullups). Für WLAN/MQTT eine lokale `wifi_credentials.h` neben dem `.ino` anlegen (Vorlage: `wifi_credentials.h.example`, siehe `HARDWARE.md`); diese Datei wird nicht committet.

```bash
cd /Users/marvinmayer/Desktop/MesseAuto/esp32-codes
./flash_actor_from_pc.sh /dev/cu.SLAB_USBtoUART
```

Vor dem Flashen die aktuell laufende Firmware sichern (Backup-first, siehe Vorgehen in `TASKS.md` MA-04-001).

## Simulation ohne Hardware

```bash
python3 simulation/mqtt_simulator.py
```

Läuft auf Pi 1 (Broker nur über `ap0`/`localhost` erreichbar). Bricht automatisch ab, wenn eine echte ESP-Hardware bereits online ist, um Topic-Kollisionen zu vermeiden. Details und Fehlerfall-Flags: `simulation/README.md`.
