# MesseAuto Pinout aller Codes

Diese Datei sammelt die Pinbelegungen aus allen aktuell vorhandenen Codes im Projekt.

Wichtig: Die ESP32-Sketches sind einzelne Alternativen bzw. getrennte Geraete. Gleiche GPIO-Nummern duerfen deshalb in verschiedenen Sketches vorkommen. Nicht alle Sketches gleichzeitig auf denselben ESP32 laden.

## Uebersicht

| Code / Datei | Plattform | Zweck |
| --- | --- | --- |
| `fahrzeugsteuerung-pi4/gpio_controller.py` | Raspberry Pi 4 | Weboberflaeche, GPIO-Ausgaenge, Motor-PWM |
| `fahrzeugsteuerung-pi4/pi_drive_controls.py` | Raspberry Pi 4 | Richtungsschalter und Speed-Poti am Pi, serielle Fahrbefehle |
| `esp32-codes/esp32_actor/esp32_actor.ino` | ESP32 Aktor | Licht, Blinker, Luefter, freie Ausgaenge, Motor-PWM |
| `esp32-codes/esp32_sensor/esp32_sensor.ino` | ESP32 Sensor | Abstandssensor und Temperatursensor |
| `esp32-codes/esp32_drive_serial/esp32_drive_serial.ino` | ESP32 Fahrmotor | Empfaengt Fahrbefehle seriell vom Pi |
| `esp32-codes/esp32_fahrregler/esp32_fahrregler.ino` | ESP32 Fahrregler | Motorisierter Drehknopf mit AS5600 und Fahrmotor-Ausgang |
| `esp32-codes/esp32_fahrregler_zwei_regler/esp32_fahrregler_zwei_regler.ino` | ESP32 Fahrregler | Richtungsschalter plus Speed-Poti |
| `motorDialPOC 1/volumeknob/volumeknob.ino` | Mikrocontroller | Original motorisierter Drehknopf-Prototyp |

## Raspberry Pi 4: Fahrzeugsteuerung

Quelle: `fahrzeugsteuerung-pi4/gpio_controller.py`

Die Software nutzt BCM-GPIO-Nummern, nicht die physischen Pin-Nummern.

| Funktion | ID im Code | BCM-GPIO | Physischer Pin | Typ |
| --- | --- | ---: | ---: | --- |
| Unterbodenbeleuchtung | `underbody` | 17 | 11 | Digital |
| Abblendlicht | `lowBeam` | 27 | 13 | Digital |
| Fernlicht | `highBeam` | 25 | 22 | Digital |
| Blinker links | `indicatorLeft` | 26 | 37 | Digital |
| Blinker rechts | `indicatorRight` | 5 | 29 | Digital |
| Warnblinkanlage | `hazard` | 6 | 31 | Digital |
| Frei 1 | `freeOne` | 16 | 36 | Digital |
| Frei 2 | `freeTwo` | 23 | 16 | Digital |
| Luefter | `fan` | 24 | 18 | Digital |
| Motor-PWM | `motor` | 22 | 15 | PWM |

Hinweise:

- Raspberry-Pi-GPIOs arbeiten mit 3,3 V Logik.
- Keine Motoren, Relais-Spulen, Luefter oder LED-Lasten direkt am GPIO betreiben.
- GPIO 22 gibt PWM aus, kein echtes analoges 0-5-V-Signal.

## Raspberry Pi 4: Fahrregler-Bedienelemente

Quelle: `fahrzeugsteuerung-pi4/pi_drive_controls.py`

Diese Variante ist fuer den Aufbau ohne Kabel vom Bedienfeld zum ESP32 gedacht. Richtung und Geschwindigkeit liegen am Raspberry Pi. Der Pi sendet danach per USB/Serial an den ESP32-Fahrmotor:

```json
{"drive": 60}
{"drive": -40}
{"drive": 0}
```

### Direkte Pi-GPIOs

| Funktion | Environment | BCM-GPIO | Physischer Pin | Typ |
| --- | --- | ---: | ---: | --- |
| Richtung rechts / vorwaerts | `MESSEAUTO_PI_DRIVE_FORWARD_GPIO` | 20 | 38 | Digital Input, Pullup |
| Richtung links / rueckwaerts | `MESSEAUTO_PI_DRIVE_REVERSE_GPIO` | 21 | 40 | Digital Input, Pullup |

Anschlusslogik:

| Bedienelement | Anschluss am Pi |
| --- | --- |
| Richtungsschalter rechts | GPIO20 nach GND |
| Richtungsschalter links | GPIO21 nach GND |
| Richtungsschalter mitte | GPIO20 und GPIO21 offen |

### Speed-Poti ueber MCP3008

Der Raspberry Pi hat keinen Analog-Eingang. Fuer den Geschwindigkeitspoti wird deshalb ein MCP3008-ADC ueber SPI verwendet.

| Funktion | Pi BCM-GPIO | Physischer Pin | MCP3008 Pin |
| --- | ---: | ---: | --- |
| SPI MOSI | 10 | 19 | DIN |
| SPI MISO | 9 | 21 | DOUT |
| SPI SCLK | 11 | 23 | CLK |
| SPI CE0 | 8 | 24 | CS/SHDN |
| 3,3 V | 3V3 | 1 oder 17 | VDD und VREF |
| GND | GND | z. B. 6 | AGND und DGND |
| Speed-Poti Schleifer | MCP3008 CH0 | - | CH0 |

Speed-Poti:

| Poti-Pin | Anschluss |
| --- | --- |
| Aussen 1 | 3,3 V |
| Mitte / Schleifer | MCP3008 CH0 |
| Aussen 2 | GND |

Hinweise:

- SPI muss am Raspberry Pi aktiviert sein.
- Fuer die Installation wird `python3-spidev` benoetigt.
- Poti nur mit 3,3 V betreiben, nicht mit 5 V.
- Default-ADC-Kanal: `MESSEAUTO_PI_DRIVE_ADC_CHANNEL=0`.

## ESP32 Aktor

Quelle: `esp32-codes/esp32_actor/esp32_actor.ino`

### Standalone-Button-Eingaenge

Der ESP32 wird einmal per PC/Mac geflasht. Im Messebetrieb gibt es keine
Serial-Verbindung zum Raspberry Pi. Echte Buttons und Pi-Relaiskontakte liegen
parallel auf denselben ESP32-Eingaengen. LOW bedeutet gedrueckt.

| Funktion | Button-Nummer | ESP32 GPIO | Pi-Funktion / Relaisimpuls |
| --- | ---: | ---: | --- |
| Fernlicht | 1 | 33 | `highBeam` |
| Abblendlicht | 2 | 15 | `lowBeam` |
| Unterboden | 3 | 25 | `underbody` |
| Blinker links | 4 | 35 | `indicatorLeft` |
| Blinker rechts | 5 | 14 | `indicatorRight` |
| Warnblinker | 6 | 27 | `hazard` |
| Luefter | 7 | 34 | `fan` |
| Reserve 1 | 8 | 13 | `freeOne` |
| Reserve 2 | 9 | 26 | `freeTwo` |
| Reserve 3 | 10 | 32 | `freeThree` |

### ESP32-Ausgaenge

| Funktion | Konstante | ESP32 GPIO | Typ |
| --- | --- | ---: | --- |
| Abblendlicht | `LOW_BEAM_PIN` | 18 | Digital Output |
| Fernlicht | `HIGH_BEAM_PIN` | 19 | Digital Output |
| Blinker links | `INDICATOR_LEFT_PIN` | 17 | blinkender Digital Output |
| Blinker rechts | `INDICATOR_RIGHT_PIN` | 5 | blinkender Digital Output |
| Unterboden LED-Streifen | `UNDERBODY_PIXEL_PIN` | 0 | NeoPixel, Unterboden = wandernder Regenbogen, Warnblinker = orangener Laufstreifen |
| Luefter | `FAN_PIN` | 22 | Digital Output |
| Frei 1 | `FREE_ONE_PIN` | 25 | wegen gleicher Eingangsbelegung nicht aktiv getrieben |
| Frei 2 | `FREE_TWO_PIN` | 26 | wegen gleicher Eingangsbelegung nicht aktiv getrieben |
| Frei 3 | `FREE_THREE_PIN` | 27 | wegen gleicher Eingangsbelegung nicht aktiv getrieben |

Hinweis: Bei vielen klassischen ESP32-Boards haben GPIO34 und GPIO35 keine
internen Pullups. Dann externe Pullup-Widerstaende verwenden oder andere
Eingangspins waehlen.

## ESP32 Sensor

Quelle: `esp32-codes/esp32_sensor/esp32_sensor.ino`

| Funktion | Konstante | ESP32 GPIO | Typ |
| --- | --- | ---: | --- |
| Abstand Trigger | `PIN_DISTANCE_TRIG` | 18 | Digital Output |
| Abstand Echo | `PIN_DISTANCE_ECHO` | 19 | Digital Input |
| Temperatur ADC | `PIN_TEMPERATURE_ADC` | 34 | Analog Input |

Hinweise:

- Fuer HC-SR04 Echo bei 5 V einen Spannungsteiler oder Pegelwandler auf 3,3 V nutzen.
- Der Temperaturcode ist fuer LM35 oder TMP36-aehnliche Sensoren vorbereitet.

## ESP32 Fahrmotor per Serial

Quelle: `esp32-codes/esp32_drive_serial/esp32_drive_serial.ino`

Dieser Sketch ist die Gegenstelle zum Pi-Fahrregler. Er empfaengt `{"drive": -100..100}` ueber USB/Serial und steuert den Motortreiber.

| Funktion | Konstante | ESP32 GPIO | Typ |
| --- | --- | ---: | --- |
| Fahrmotor PWM | `PIN_DRIVE_PWM` | 27 | PWM, 1000 Hz, 8 Bit |
| Fahrmotor IN1 | `PIN_DRIVE_IN1` | 25 | Digital Output |
| Fahrmotor IN2 | `PIN_DRIVE_IN2` | 26 | Digital Output |

Serielle Befehle:

| Befehl | Bedeutung |
| --- | --- |
| `{"drive": 60}` | vorwaerts 60 Prozent |
| `{"drive": -40}` | rueckwaerts 40 Prozent |
| `{"drive": 0}` | stop |
| `{"stop": true}` | stop |

Hinweise:

- Der ESP32 meldet sich als `esp32_fahrregler`.
- Wenn laenger als 1200 ms kein Befehl kommt, stoppt der Sketch automatisch.
- Fahrmotor nur ueber Motortreiber anschliessen, nie direkt an den ESP32.

## ESP32 Fahrregler: Motorisierter Drehknopf

Quelle: `esp32-codes/esp32_fahrregler/esp32_fahrregler.ino`

| Funktion | Konstante | ESP32 GPIO | Typ |
| --- | --- | ---: | --- |
| AS5600 SDA/SCL | `Wire.begin()` | Board-Default | I2C |
| Drehknopf-Schrittmotor IN1 | `DIAL_MOTOR_PINS[0]` | 18 | Digital Output |
| Drehknopf-Schrittmotor IN2 | `DIAL_MOTOR_PINS[1]` | 19 | Digital Output |
| Drehknopf-Schrittmotor IN3 | `DIAL_MOTOR_PINS[2]` | 20 | Digital Output |
| Drehknopf-Schrittmotor IN4 | `DIAL_MOTOR_PINS[3]` | 21 | Digital Output |
| NeoPixel-Ring | `NEOPIXEL_PIN` | 28 | Digital Output |
| Fahrmotor PWM | `PIN_DRIVE_PWM` | 27 | PWM, 1000 Hz, 8 Bit |
| Fahrmotor IN1 | `PIN_DRIVE_IN1` | 25 | Digital Output |
| Fahrmotor IN2 | `PIN_DRIVE_IN2` | 26 | Digital Output |

Hinweise:

- AS5600-Adresse im Code: `0x36`.
- GPIO20 und GPIO28 gibt es nicht auf jedem ESP32-Devboard. Falls dein Board diese Pins nicht herausfuehrt, die Konstanten oben im Sketch aendern.
- Fahrmotor nur ueber Motortreiber anschliessen, nie direkt an den ESP32.

## ESP32 Fahrregler: Zwei Regler

Quelle: `esp32-codes/esp32_fahrregler_zwei_regler/esp32_fahrregler_zwei_regler.ino`

| Funktion | Konstante | ESP32 GPIO | Typ |
| --- | --- | ---: | --- |
| Richtung rechts / vorwaerts | `PIN_DIRECTION_FORWARD` | 32 | `INPUT_PULLUP`, Schalter nach GND |
| Richtung links / rueckwaerts | `PIN_DIRECTION_REVERSE` | 33 | `INPUT_PULLUP`, Schalter nach GND |
| Geschwindigkeit 0-100 | `PIN_SPEED_ADC` | 34 | Analog Input |
| Fahrmotor PWM | `PIN_DRIVE_PWM` | 27 | PWM, 1000 Hz, 8 Bit |
| Fahrmotor IN1 | `PIN_DRIVE_IN1` | 25 | Digital Output |
| Fahrmotor IN2 | `PIN_DRIVE_IN2` | 26 | Digital Output |

Anschlusslogik:

| Bedienelement | Anschluss |
| --- | --- |
| Richtungsschalter links | GPIO33 nach GND |
| Richtungsschalter mitte | GPIO32 und GPIO33 offen |
| Richtungsschalter rechts | GPIO32 nach GND |
| Speed-Poti | 3V3 - Schleifer an GPIO34 - GND |

Hinweise:

- Poti nur mit 3,3 V betreiben, nicht mit 5 V.
- ESP32-GND, Motortreiber-GND und Motorversorgung-GND verbinden.
- Bei Richtungswechsel bremst die Firmware erst auf 0 Prozent und schaltet danach um.

## MotorDial POC / Volumeknob

Quelle: `motorDialPOC 1/volumeknob/volumeknob.ino`

| Funktion | Konstante | GPIO | Typ |
| --- | --- | ---: | --- |
| AS5600 SDA/SCL | `Wire.begin()` | Board-Default | I2C |
| Schrittmotor IN1 | `motorPins[0]` | 18 | Digital Output |
| Schrittmotor IN2 | `motorPins[1]` | 19 | Digital Output |
| Schrittmotor IN3 | `motorPins[2]` | 20 | Digital Output |
| Schrittmotor IN4 | `motorPins[3]` | 21 | Digital Output |
| NeoPixel-Ring | `NEOPIXEL_PIN` | 28 | Digital Output |

Hinweise:

- AS5600-Adresse im Code: `0x36`.
- Der Sketch erwartet einen 12er NeoPixel-Ring.
- GPIO20 und GPIO28 sind boardabhaengig.

## Codes ohne eigene Hardware-Pins

| Datei / Bereich | Hinweis |
| --- | --- |
| `datenbank-pi4/*` | Keine GPIO-Pins, nur Datenbank/Webserver |
| `fahrzeugsteuerung-pi4/app.py` | Nutzt `gpio_controller.py`, keine eigene Pinliste |
| `fahrzeugsteuerung-pi4/relay_controller.py` | Nutzt IDs aus `gpio_controller.py`, keine eigenen Pins |
| `fahrzeugsteuerung-pi4/esp32_device_manager.py` | USB/Serial-Erkennung und serielle Fahrbefehle, keine GPIO-Pins |
| `fahrzeugsteuerung-pi4/web/*` | Anzeige/Bedienung, keine eigenen Hardware-Pins |

## Wichtige Konflikte und Hinweise

| Thema | Hinweis |
| --- | --- |
| ESP32 GPIO18/19 | Im Sensor-Sketch Abstandssensor, in Fahrregler-Sketches Schrittmotor. Nur relevant, wenn du Sketches zusammenlegen willst. |
| ESP32 GPIO25/26/27 | Im Aktor-Sketch freie Ausgaenge plus Motor-PWM, in Fahrregler-Sketches Fahrmotor-IN1/IN2/PWM. |
| ESP32 GPIO34 | Wird in mehreren Sketches als analoger Eingang genutzt. GPIO34 ist input-only. |
| GPIO20/28 | Nicht auf jedem ESP32 vorhanden. Board pruefen oder Pins im Sketch aendern. |
| Pi Speed-Poti | Nicht direkt an den Pi anschliessen. Der Pi braucht MCP3008 oder einen anderen ADC. |
| GND | Bei Motorsteuerung immer gemeinsame Masse zwischen ESP32/Pi, Motortreiber und Motorversorgung herstellen. |
