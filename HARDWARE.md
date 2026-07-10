# Hardware und Pinbelegung

## ESP32 Aktorik

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

## ESP32 Sensorik

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

## Verbindung

Beide ESP32 werden per USB mit Raspberry Pi 1 verbunden und senden JSON-Zeilen mit 115200 Baud. Pi 1 erkennt die Geräte über das Feld `device` automatisch.
