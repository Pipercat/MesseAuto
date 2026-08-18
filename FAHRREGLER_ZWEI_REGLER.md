# Fahrregler mit Richtung links/rechts und Geschwindigkeit 0-100

Hinweis: Diese Datei beschreibt die alte/alternative Variante, bei der Richtungsschalter und Poti direkt am ESP32 angeschlossen sind. Fuer deinen aktuellen Aufbau mit Bedienelementen am Raspberry Pi nutze `PI_FAHRREGLER_SERIAL.md`.

Das ist die einfache Variante fuer dein MesseAuto:

- Ein 3-Stellungen-Schalter fuer die Richtung
- Ein Potentiometer fuer die Geschwindigkeit von 0 bis 100 Prozent
- Ein Motortreiber fuer den Fahrmotor

Firmware:

```text
esp32-codes/esp32_fahrregler_zwei_regler/esp32_fahrregler_zwei_regler.ino
```

## Bedienung

| Bedienelement | Stellung | Ergebnis |
| --- | --- | --- |
| Richtungsschalter | links | rueckwaerts |
| Richtungsschalter | mitte | stop |
| Richtungsschalter | rechts | vorwaerts |
| Geschwindigkeitspoti | 0-100 Prozent | Motorgeschwindigkeit |

Wenn der Richtungsschalter in der Mitte steht, bleibt der Motor aus, egal wo der Geschwindigkeitspoti steht.

## Bauteile

- ESP32
- 3-Stellungen-Kippschalter oder Schiebeschalter, Typ `ON-OFF-ON`
- 10 kOhm Potentiometer
- Motortreiber, z. B. TB6612FNG, DRV8833, BTS7960 oder L298N
- Fahrmotor mit eigener Motorversorgung

Wichtig: Der ESP32 darf den Fahrmotor nicht direkt treiben. Der Motor muss ueber einen Motortreiber laufen.

## Pinbelegung

| Funktion | ESP32 GPIO | Hinweis |
| --- | ---: | --- |
| Richtung rechts / vorwaerts | 32 | Schalter verbindet nach GND |
| Richtung links / rueckwaerts | 33 | Schalter verbindet nach GND |
| Geschwindigkeit 0-100 | 34 | Schleifer vom 10k-Poti |
| Motor PWM | 27 | an PWM/EN vom Motortreiber |
| Motor Richtung IN1 | 25 | an IN1 vom Motortreiber |
| Motor Richtung IN2 | 26 | an IN2 vom Motortreiber |

## Richtungsschalter anschliessen

Nimm einen `ON-OFF-ON` Schalter mit Mittelstellung.

```text
GPIO33 ---- linker Kontakt
GND   ---- mittlerer Kontakt
GPIO32 ---- rechter Kontakt
```

Die Firmware nutzt `INPUT_PULLUP`. Deshalb muss der Schalter nur nach GND schalten:

- links: GPIO33 wird LOW, rueckwaerts
- mitte: GPIO32 und GPIO33 bleiben HIGH, stop
- rechts: GPIO32 wird LOW, vorwaerts

Wenn dein Schalter anders herum eingebaut ist, einfach GPIO32 und GPIO33 tauschen.

## Geschwindigkeitspoti anschliessen

```text
3V3 ---- aeusserer Poti-Pin
GPIO34 - mittlerer Poti-Pin / Schleifer
GND ---- anderer aeusserer Poti-Pin
```

Wichtig: Nicht 5 V auf GPIO34 geben. Der ESP32-ADC vertraegt nur 3,3 V.

Wenn die Richtung des Potis falsch herum ist, die beiden aeusseren Poti-Pins tauschen.

## Motortreiber anschliessen

Typischer Anschluss:

| ESP32 | Motortreiber |
| --- | --- |
| GPIO27 | PWM / EN |
| GPIO25 | IN1 |
| GPIO26 | IN2 |
| GND | GND |

Motorversorgung und Fahrmotor kommen an den Motortreiber. ESP32-GND und Motortreiber-GND muessen verbunden sein.

Beim TB6612FNG muss `STBY` auf HIGH liegen.

## Sicherheitsverhalten

- Mitte am Richtungsschalter stoppt den Motor.
- Wenn links und rechts gleichzeitig aktiv sind, stoppt die Firmware.
- Die Geschwindigkeit wird sanft gerampt.
- Beim Wechsel von vorwaerts auf rueckwaerts bremst die Firmware erst auf 0 Prozent und schaltet dann um.

## Status per Serial

Der ESP32 sendet regelmaessig:

```json
{"device":"esp32_fahrregler","type":"drive_status","mode":"two_controls","selected_direction":"forward","selected_speed_percent":60,"target_drive":60,"actual_drive":58,"direction":"forward","speed_percent":58,"errors":[]}
```

So kann der Raspberry Pi spaeter anzeigen, welche Richtung und Geschwindigkeit gerade aktiv sind.
