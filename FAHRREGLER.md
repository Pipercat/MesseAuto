# Motorisierter Fahrregler fuer Geschwindigkeit und Vorwaerts/Rueckwaerts

Dieser Regler nutzt das gleiche Prinzip wie der motorisierte Lautstaerkeregler: Ein AS5600 misst die Drehposition, ein kleiner Schrittmotor bewegt den Knopf automatisch auf Sollwerte, und der LED-Ring zeigt den Zustand an.

Fuer das MesseAuto wird daraus ein Fahrregler:

| Knopfstellung | Funktion |
| --- | --- |
| Mitte, ca. 180 Grad | Stop |
| Nach rechts | vorwaerts, Geschwindigkeit steigt bis 100 Prozent |
| Nach links | rueckwaerts, Geschwindigkeit steigt bis 100 Prozent |

Die Firmware liegt hier:

```text
esp32-codes/esp32_fahrregler/esp32_fahrregler.ino
```

## Empfohlene Bauteile

- ESP32 oder kompatibles Board
- AS5600 Magnet-Drehwinkelsensor
- diametral magnetisierter Magnet fuer die Achse
- 28BYJ-48 Schrittmotor mit ULN2003-Treiberplatine fuer den motorisierten Knopf
- Motortreiber fuer den Fahrmotor, z. B. TB6612FNG, DRV8833, BTS7960 oder L298N
- Externe Motorversorgung passend zum Fahrmotor
- Gemeinsame Masse zwischen ESP32, Motortreiber und Motorversorgung
- Optional: 12er NeoPixel-Ring

Wichtig: Den Fahrmotor niemals direkt an den ESP32 anschliessen. Der ESP32 liefert nur Logiksignale.

## Pinbelegung im Sketch

| Funktion | ESP32 GPIO |
| --- | ---: |
| AS5600 SDA/SCL | Default-I2C des Boards |
| Schrittmotor IN1 | 18 |
| Schrittmotor IN2 | 19 |
| Schrittmotor IN3 | 20 |
| Schrittmotor IN4 | 21 |
| NeoPixel-Ring | 28 |
| Fahrmotor PWM | 27 |
| Fahrmotor Richtung IN1 | 25 |
| Fahrmotor Richtung IN2 | 26 |

Wenn dein ESP32 bestimmte GPIOs nicht besitzt, oben im Sketch die Konstanten anpassen:

```cpp
static const int DIAL_MOTOR_PINS[4] = {18, 19, 20, 21};
static const int NEOPIXEL_PIN = 28;
static const int PIN_DRIVE_PWM = 27;
static const int PIN_DRIVE_IN1 = 25;
static const int PIN_DRIVE_IN2 = 26;
```

## Anschluss an einen typischen Motortreiber

TB6612FNG/DRV8833/L298N-Logik:

| Fahrregler | Motortreiber |
| --- | --- |
| `PIN_DRIVE_PWM` | PWM/EN |
| `PIN_DRIVE_IN1` | IN1 |
| `PIN_DRIVE_IN2` | IN2 |
| GND | GND |

Beim TB6612FNG muss `STBY` auf HIGH liegen. Die Motorversorgung kommt an VM/Motor-Versorgung des Treibers, nicht an den ESP32.

## Verhalten

- Manuelles Drehen steuert sofort `targetDrivePercent`.
- Die Ausgabe `actualDrivePercent` folgt mit Rampe, damit das Auto nicht ruckartig losfaehrt.
- Bei Richtungswechseln bremst die Firmware erst auf 0 Prozent und schaltet danach in die Gegenrichtung.
- Der LED-Ring ist weiss bei Stop, gruen bei vorwaerts und rot/orange bei rueckwaerts.

## Kalibrierung

Die wichtigsten Werte stehen oben im Sketch:

```cpp
static const float STOP_ANGLE_DEG = 180.0f;
static const float STOP_DEADBAND_DEG = 8.0f;
static const float REVERSE_MAX_ANGLE_DEG = 20.0f;
static const float FORWARD_MAX_ANGLE_DEG = 340.0f;
```

Wenn der Knopf mechanische Anschlaege hat, setze `REVERSE_MAX_ANGLE_DEG` und `FORWARD_MAX_ANGLE_DEG` auf die echten Endpunkte. Wenn Stop zu empfindlich ist, `STOP_DEADBAND_DEG` groesser machen.

## Serielle Befehle

Der Regler kann auch automatisch synchronisiert werden. Eine JSON-Zeile mit `\n` reicht.

Stop:

```json
{"stop": true}
```

Vorwaerts 60 Prozent:

```json
{"direction": "forward", "percent": 60}
```

Rueckwaerts 35 Prozent:

```json
{"direction": "reverse", "percent": 35}
```

Kurzform mit Vorzeichen:

```json
{"drive": 75}
{"drive": -40}
{"drive": 0}
```

Der Knopf faehrt dabei automatisch zur passenden Position.

## Statusausgabe

Der ESP32 sendet regelmaessig:

```json
{
  "device": "esp32_fahrregler",
  "type": "drive_status",
  "angle_deg": 181.2,
  "target_drive": 0,
  "actual_drive": 0,
  "direction": "stop",
  "speed_percent": 0,
  "dial_move_active": false,
  "errors": []
}
```

Damit kann spaeter der Raspberry Pi den physischen Fahrregler anzeigen oder Sollwerte zuruecksenden.

## Bezug zum vorhandenen Projekt

Der vorhandene Sketch `motorDialPOC 1/volumeknob/volumeknob.ino` ist der reine motorisierte Drehknopf. Der neue Sketch `esp32_fahrregler` erweitert dieses Prinzip um:

- Mittelstellung als Stop
- Vorwaerts/Rueckwaerts-Logik
- PWM-Ausgang fuer Geschwindigkeit
- Richtungsausgaenge fuer H-Bruecke
- sanfte Rampe fuer Richtungswechsel
- serielle JSON-Befehle fuer automatische Synchronisierung
