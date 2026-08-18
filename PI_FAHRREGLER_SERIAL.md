# Fahrregler am Raspberry Pi, Fahrmotor per Serial am ESP32

Ziel: Keine Kabel vom Richtungsschalter oder Speed-Poti zum ESP32.

Stattdessen:

```text
Richtungsschalter + Speed-Poti -> Raspberry Pi -> USB/Serial -> ESP32 -> Motortreiber -> Fahrmotor
```

## Raspberry Pi Anschluesse

Quelle: `fahrzeugsteuerung-pi4/pi_drive_controls.py`

### Richtungsschalter

3-Stellungen-Schalter `ON-OFF-ON`:

| Funktion | Pi BCM-GPIO | Physischer Pin |
| --- | ---: | ---: |
| rechts / vorwaerts | 20 | 38 |
| links / rueckwaerts | 21 | 40 |
| GND | GND | z. B. 39 |

Logik:

- GPIO20 nach GND = vorwaerts
- GPIO21 nach GND = rueckwaerts
- beide offen = stop
- beide aktiv = stop

### Speed-Poti

Der Raspberry Pi hat keinen Analog-Eingang. Deshalb kommt der Poti an einen MCP3008.

| MCP3008 | Raspberry Pi |
| --- | --- |
| VDD | 3V3 |
| VREF | 3V3 |
| AGND | GND |
| DGND | GND |
| CLK | GPIO11 / physisch 23 |
| DOUT | GPIO9 / physisch 21 |
| DIN | GPIO10 / physisch 19 |
| CS/SHDN | GPIO8 / physisch 24 |
| CH0 | Poti-Schleifer |

Poti:

```text
3V3  -> Poti aussen
CH0  -> Poti Mitte / Schleifer
GND  -> Poti aussen
```

Wichtig: Nur 3,3 V am Poti verwenden.

## ESP32 Fahrmotor

Firmware:

```text
esp32-codes/esp32_drive_serial/esp32_drive_serial.ino
```

| Funktion | ESP32 GPIO |
| --- | ---: |
| Motor PWM / EN | 27 |
| Motor IN1 | 25 |
| Motor IN2 | 26 |

Der ESP32 meldet sich seriell als `esp32_fahrregler`.

## Serielle Befehle

Der Pi sendet automatisch:

```json
{"drive": 60}
{"drive": -40}
{"drive": 0}
```

Wertebereich:

| Wert | Bedeutung |
| ---: | --- |
| `100` | vorwaerts 100 Prozent |
| `60` | vorwaerts 60 Prozent |
| `0` | stop |
| `-40` | rueckwaerts 40 Prozent |
| `-100` | rueckwaerts 100 Prozent |

## Raspberry Pi Setup

SPI aktivieren:

```bash
sudo raspi-config
```

Dann:

```text
Interface Options -> SPI -> Enable
```

Installation:

```bash
cd /home/pi/fahrzeugsteuerung-pi4
./install_pi.sh
sudo systemctl restart messeauto.service
```

## Konfiguration

Defaults:

```text
MESSEAUTO_PI_DRIVE_CONTROLS=auto
MESSEAUTO_PI_DRIVE_FORWARD_GPIO=20
MESSEAUTO_PI_DRIVE_REVERSE_GPIO=21
MESSEAUTO_PI_DRIVE_ADC_CHANNEL=0
```

Wenn der Richtungsschalter anders herum ist, kannst du entweder die Kabel tauschen oder die GPIOs in der Service-Konfiguration tauschen.
