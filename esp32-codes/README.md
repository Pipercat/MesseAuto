# MesseAuto ESP32 Codes

Dieses Paket enthält mehrere Arduino-Sketches:

```text
esp32_actor/esp32_actor.ino
esp32_sensor/esp32_sensor.ino
esp32_drive_serial/esp32_drive_serial.ino
esp32_fahrregler/esp32_fahrregler.ino
esp32_fahrregler_zwei_regler/esp32_fahrregler_zwei_regler.ino
```

## ESP32 Aktorsteuerung

Aufgaben:

- einmal per PC/Mac flashen
- danach im Fahrzeug standalone einstecken
- keine laufende USB-/Serial-Verbindung zum Raspberry Pi im Messebetrieb
- echte Buttons und Pi-Relaiskontakte werden parallel auf dieselben ESP-Eingaenge gelegt
- LOW am Eingang bedeutet: Button gedrueckt

Im finalen Messestand steuert der Raspberry Pi den ESP nicht ueber Serial.
Die Touchscreen-Steuerung gibt kurze Impulse auf Pi-GPIOs. Diese GPIOs schalten
Relais. Der potentialfreie Relaiskontakt liegt parallel zum echten Button am
ESP32-Eingang und zieht diesen Eingang kurz auf LOW. Fuer den ESP ist das exakt
derselbe Zustand wie ein echter Buttondruck.

## ESP32 Buttonbelegung

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

Wichtig: GPIO34 und GPIO35 haben beim klassischen ESP32 keinen internen Pullup.
Wenn diese Pins genutzt werden, brauchen sie externe Pullup-Widerstaende oder
eine vorhandene Button-Platine mit Pullup. Alle anderen Buttonpins werden im
Sketch mit `INPUT_PULLUP` betrieben.

## ESP32 Ausgangsbelegung

| Funktion | ESP32 GPIO | Verhalten |
| --- | ---: | --- |
| Abblendlicht | 18 | dauerhaft an/aus |
| Fernlicht | 19 | dauerhaft an/aus |
| Blinker links | 17 | blinkt bei aktivem Blinker links oder Warnblinker |
| Blinker rechts | 5 | blinkt bei aktivem Blinker rechts oder Warnblinker |
| Unterboden LED-Streifen | 0 | NeoPixel, Unterboden = wandernder Regenbogen, Warnblinker = orangener Laufstreifen |
| Luefter | 22 | dauerhaft an/aus |
| Frei 1 | 25 | wegen gleicher Eingangsbelegung nicht aktiv getrieben |
| Frei 2 | 26 | wegen gleicher Eingangsbelegung nicht aktiv getrieben |
| Frei 3 | 27 | wegen gleicher Eingangsbelegung nicht aktiv getrieben |

Warnblinker nutzt Blinker links, Blinker rechts und den orangenen Laufstreifen
auf dem Unterboden. Der ESP gibt ueber USB-Serial Live-Logs aus, z. B.:

```text
LOG ms=12345 event=button_pressed button=3 pin=GPIO25 function=underbody
LOG ms=12346 event=switch function=underbody state=ON output=NeoPixel GPIO0 rainbow
LOG ms=12420 event=button_released button=3 pin=GPIO25 function=underbody
```

Flashen vom Mac/PC:

```bash
cd esp32-codes
./flash_actor_from_pc.sh /dev/cu.SLAB_USBtoUART
```

Port finden:

```bash
arduino-cli board list
```

Nach dem Flashen den ESP vom PC trennen und in das Fahrzeug einstecken. Nicht als
dauerhafte USB-/Serial-Verbindung an den Fahrzeug-Pi anschliessen.

Optionale PC-Diagnosemeldung:

```json
{"device":"esp32_actor","mode":"standalone_buttons","states":{"highBeam":false,"lowBeam":false,"underbody":false,"leftIndicator":false,"rightIndicator":false,"hazard":false,"fan":false},"buttons":[false,false,false,false,false,false,false,false,false,false]}
```

Status:

```json
{"device":"esp32_actor","mode":"standalone_buttons","states":{"lowBeam":true},"buttons":[false,true,false,false,false,false,false,false,false,false],"event_button":2}
```

Optionale PC-Diagnosekommandos:

```text
SET lowBeam 1
SET lowBeam 0
SET fan 1
```

## ESP32 Sensorik

Aufgaben:

- Temperatur analog messen
- Sitzabstand per Ultraschallsensor messen
- Sitzposition berechnen
- Sensorstatus per JSON über Serial senden

Startmeldung:

```json
{"device":"esp32_sensor","type":"hello","baudrate":115200}
```

Status:

```json
{"device":"esp32_sensor","type":"sensor_status","temperature_c":31.8,"seat_distance_mm":102,"seat_position":"middle","errors":[]}
```

## ESP32 Fahrmotor per Serial

Empfohlene Variante, wenn Richtungsschalter und Speed-Poti am Raspberry Pi angeschlossen sind:

- Der Pi liest die Bedienelemente.
- Der Pi sendet per USB/Serial `{"drive": -100..100}`.
- Der ESP32 steuert PWM + IN1/IN2 am Motortreiber.

Status:

```json
{"device":"esp32_fahrregler","type":"drive_status","mode":"serial_drive","direction":"forward","speed_percent":60,"actual_drive":60,"errors":[]}
```

Pins siehe `../PINOUT_ALLE_CODES.md`.

## ESP32 Fahrregler mit motorisiertem Drehknopf

Aufgaben:

- motorisierten Drehknopf mit AS5600 als Fahrregler nutzen
- Mitte = Stop, rechts = vorwaerts, links = rueckwaerts
- PWM und Richtungssignale fuer einen DC-Motortreiber ausgeben
- Zielwerte per JSON annehmen und den Knopf automatisch synchronisieren

Status:

```json
{"device":"esp32_fahrregler","type":"drive_status","direction":"forward","speed_percent":60,"actual_drive":60,"errors":[]}
```

Details siehe `../FAHRREGLER.md`.

## ESP32 Fahrregler mit zwei Reglern

Empfohlene einfache Variante fuer Richtung plus Geschwindigkeit:

- 3-Stellungen-Schalter links/mitte/rechts fuer rueckwaerts/stop/vorwaerts
- 10k-Potentiometer fuer Geschwindigkeit 0-100 Prozent
- PWM + IN1/IN2 fuer einen DC-Motortreiber

Status:

```json
{"device":"esp32_fahrregler","type":"drive_status","mode":"two_controls","selected_direction":"forward","selected_speed_percent":60,"speed_percent":58,"errors":[]}
```

Details siehe `../FAHRREGLER_ZWEI_REGLER.md`.

## Hinweise

- Pins in den `.ino` Dateien oben anpassen.
- Baudrate ist `115200`.
- Serial ist nur fuer Flash/Werkbank-Diagnose gedacht, nicht fuer die laufende Pi-Steuerung.
- Der Aktor-Sketch nutzt fuer Diagnose bewusst kurze Textkommandos und Relaisimpulse, keine dauerhaft aktiven JSON-Ausgangszustaende.
- Für den Sensor-Sketch ist aktuell HC-SR04 plus analoger LM35/TMP36 vorgesehen.
- Wenn ein anderer Temperatur- oder Abstandssensor verwendet wird, nur die Funktionen `readTemperatureC()` oder `readDistanceMm()` anpassen.
