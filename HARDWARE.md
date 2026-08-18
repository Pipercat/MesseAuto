# Hardware und Pinbelegung

## Sicherheitsregel: ESP32 ↔ Raspberry Pi

Im aktuellen MesseCar-Aufbau dürfen ESP32 und Raspberry Pi 1 **nicht dauerhaft per USB miteinander verbunden werden**.

Grund: Die USB-Verbindung verbindet die Masse des ESP32 mit der Masse des Raspberry Pi. In Verbindung mit der bestehenden Fahrzeug-/Relais-Schaltung entsteht dadurch ein unerwünschter Ground-Pfad bzw. Kurzschluss.

Deshalb gilt aktuell:

```text
ESP32 Actor  ── WLAN/MQTT ──► Raspberry Pi 1
ESP32 Sensor ── WLAN/MQTT ──► Raspberry Pi 1

USB/Serial: standardmäßig deaktivierter Fallback
```

Der vorhandene Serial-Code wird bewusst nicht gelöscht. Er darf später wieder verwendet werden, wenn der Hardwareaufbau eine sichere galvanische Trennung ermöglicht, z. B. durch geeignete Relais-/Isolationshardware ohne problematische gemeinsame Masse.

## ESP32 Actor

### Arduino-Bibliothek

- `Adafruit NeoPixel`

### Taster

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

Die Taster werden als aktiv LOW erwartet. Der bisherige Aufbau mit externen Pull-up-Widerständen und Kondensatoren kann weiterverwendet werden.

### Ausgänge

| Gerät | GPIO |
|---|---:|
| Lüfter | 22 |
| WS2812/NeoPixel | 0 |

Der Sketch ist aktuell für 75 NeoPixel konfiguriert.

## ESP32 Sensor

### Arduino-Bibliotheken

- `OneWire`
- `DallasTemperature`

### Aktuelle Standardpins

| Sensor | Pin |
|---|---:|
| DS18B20 Datenleitung | GPIO 4 |
| Ultraschall Trigger | GPIO 18 |
| Ultraschall Echo | GPIO 19 |

Diese drei Pins sind als anpassbare Standardwerte gesetzt, weil für den Sensor-ESP32 bisher keine endgültige Pinbelegung dokumentiert war.

**Wichtig:** Bei einem 5-V-Ultraschallsensor darf ein 5-V-Echo-Signal nicht direkt an einen 3,3-V-ESP32-GPIO gelegt werden. Nutze einen passenden Pegelwandler oder Spannungsteiler.

## Raspberry Pi 1

| Funktion | BCM GPIO |
|---|---:|
| Unterbodenbeleuchtung | 17 |
| Abblendlicht | 27 |
| Fernlicht | 25 |
| Blinker links | 6 |
| Blinker rechts | 5 |
| Lüfter | 22 |

Die GPIOs geben nur kurze Impulse aus. Ein erneuter Impuls schaltet die jeweilige externe Funktion wieder um.

## Zielverbindung

Raspberry Pi 1 soll ein lokales MesseCar-Netz bereitstellen oder darin betrieben werden. ESP32 Actor und ESP32 Sensor kommunizieren zukünftig per WLAN/MQTT mit Pi 1.

Vorteile für den aktuellen Aufbau:

- keine direkte elektrische Datenverbindung zwischen ESP und Pi
- keine zusätzliche gemeinsame Masse durch USB
- bidirektionale Kommunikation
- mehrere ESP32 ohne zusätzliche Kabel
- vollständig lokal ohne Cloud betreibbar

Die exakte MQTT-Architektur und alle Arbeitsschritte sind in `TASKS.md` definiert.
