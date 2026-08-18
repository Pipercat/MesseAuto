# Pinstruktur

Die Software verwendet BCM-GPIO-Nummern, nicht die physischen Pin-Nummern der 40-poligen Leiste.

| Funktion | BCM-GPIO | Physischer Pin | Typ |
| --- | ---: | ---: | --- |
| Unterbodenbeleuchtung | 17 | 11 | Digital |
| Abblendlicht | 27 | 13 | Digital |
| Fernlicht | 25 | 22 | Digital |
| Blinker links | 26 | 37 | Digital |
| Blinker rechts | 5 | 29 | Digital |
| Warnblinkanlage | 6 | 31 | Digital |
| Frei 1 | 16 | 36 | Digital |
| Frei 2 | 23 | 16 | Digital |
| Lüfter | 24 | 18 | Digital |
| Motor-PWM | 22 | 15 | PWM |

## Wichtige Hardware-Hinweise

- Raspberry-Pi-GPIOs arbeiten mit 3,3 V Logikpegeln.
- GPIOs dürfen nicht direkt Motoren, Lüfter, Relais-Spulen oder LED-Lasten treiben.
- Nutze geeignete Treiberstufen, Relaismodule, MOSFETs, Freilaufdioden und eine saubere Masseverbindung.
- GPIO 22 gibt PWM aus, aber kein echtes analoges 0 bis 5 V Signal.
- Die Anzeige 0,0 bis 5,0 V in der Oberfläche ist ein theoretischer Wert.

## Pegellogik

Standard:

```text
MESSEAUTO_ACTIVE_HIGH=1
MESSEAUTO_MOTOR_ACTIVE_HIGH=1
```

Wenn dein Relaisboard low-aktiv ist:

```text
MESSEAUTO_ACTIVE_HIGH=0
```

Wenn dein Motortreiber low-aktive PWM erwartet:

```text
MESSEAUTO_MOTOR_ACTIVE_HIGH=0
```
