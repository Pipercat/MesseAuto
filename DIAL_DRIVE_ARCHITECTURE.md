# MesseAuto – Motorisierte Drehregler und Fahrantrieb

Dieses Dokument definiert die verbindliche Zielarchitektur für die beiden motorisierten Drehregler und den Fahrantrieb.

## Ziel

Die bisherige Bedienung aus Potentiometer für Geschwindigkeit und Schalter für Fahrtrichtung wird ersetzt durch zwei motorisierte Drehregler:

1. **Fahrtrichtungsregler** – zeigt physisch nach links oder rechts und ist sowohl von Hand als auch über den Touchscreen bedienbar.
2. **Geschwindigkeitsregler** – stellt 0–100 % dar und ist sowohl von Hand als auch über den Touchscreen bedienbar.

Beide Regler sitzen elektrisch am Raspberry Pi 1. Der eigentliche Fahrmotor und dessen Leistungselektronik sitzen am ESP32 Actor. Pi 1 und ESP32 Actor tauschen die Fahrbefehle ausschließlich über das lokale MesseCar-WLAN/MQTT aus.

```text
                         Raspberry Pi 1
                    ┌───────────────────────┐
Touchscreen ───────►│ Drive/Dial Controller │
                    │                       │
                    │  AS5600 #1 ◄─ Magnet  │◄── Fahrtrichtungsregler von Hand
                    │      │                │
                    │  Stepper #1 ──────────│──► Regler automatisch bewegen
                    │                       │
                    │  AS5600 #2 ◄─ Magnet  │◄── Geschwindigkeitsregler von Hand
                    │      │                │
                    │  Stepper #2 ──────────│──► Regler automatisch bewegen
                    └──────────┬────────────┘
                               │
                        WLAN / MQTT
                               │
                               ▼
                         ESP32 Actor
                    ┌───────────────────────┐
                    │ Fahrmotor-Controller  │
                    │ Richtung + Leistung   │
                    │ Watchdog / Fail-Safe  │
                    └──────────┬────────────┘
                               │
                         Motor-Treiber
                               │
                               ▼
                           Fahrmotor
```

USB zwischen ESP32 und Pi bleibt im realen Fahrzeug deaktiviert.

---

## Referenz aus `motorDialPOC`

Der vorhandene POC verwendet bereits:

- AS5600 Magnetwinkelsensor (`0x36`)
- Stepper mit 4 Leitungen / Half-Step-Sequenz
- 4096 Half-Steps pro Umdrehung in der POC-Logik
- motorisierte Sollwinkelanfahrt
- Freigabe der Motorwicklungen nach Erreichen des Zielwinkels
- Magnet als berührungsloses Winkel-Feedback

Diese Grundidee wird für beide MesseCar-Regler übernommen. Die konkrete GPIO-Belegung am Raspberry Pi wird erst nach Festlegung der finalen Stepper-Treiber verbindlich eingetragen.

## I²C der beiden AS5600

Beide AS5600 verwenden standardmäßig dieselbe Adresse `0x36`. Deshalb wird ein **TCA9548A I²C-Multiplexer** vorgesehen.

```text
Raspberry Pi I²C
      │
      ▼
  TCA9548A
   ├─ Kanal 0 ─► AS5600 Fahrtrichtung
   └─ Kanal 1 ─► AS5600 Geschwindigkeit
```

Damit bleiben die beiden Sensoren eindeutig getrennt und können unabhängig ausgelesen werden.

---

# 1. Fahrtrichtungsregler

## Logischer Zustand

Der Fahrtrichtungsregler besitzt genau zwei gültige Fahrzustände:

```text
LEFT
RIGHT
```

Eine Mittelstellung ist kein gültiger Fahrbefehl. Während der Regler zwischen beiden Positionen bewegt wird, bleibt der zuletzt bestätigte Zustand aktiv, bis die Schaltschwelle mit Hysterese eindeutig überschritten wurde.

## Kalibrierung

Die mechanischen Winkel werden konfigurierbar gehalten:

```text
DIRECTION_LEFT_ANGLE_DEG
DIRECTION_RIGHT_ANGLE_DEG
DIRECTION_SWITCH_THRESHOLD_DEG
DIRECTION_HYSTERESIS_DEG
```

Die exakten Winkel werden bei der mechanischen Montage einmal eingelernt und gespeichert. Dadurch ist die Software nicht von einer bestimmten Gehäuseorientierung abhängig.

## Bedienung von Hand

1. Pi liest den AS5600 kontinuierlich.
2. Der Benutzer dreht den Regler.
3. Nach Überschreiten der definierten Richtungsschwelle wird `LEFT` oder `RIGHT` gesetzt.
4. Pi sendet die neue Fahrtrichtung sofort per MQTT an den ESP32 Actor.
5. Nach Ende der manuellen Bewegung darf der Stepper den Regler auf die exakt kalibrierte LEFT-/RIGHT-Position nachführen.

## Bedienung über Touchscreen

1. Benutzer wählt auf dem Screen links oder rechts.
2. Pi setzt den logischen Sollzustand.
3. Pi sendet den Richtungsbefehl sofort an den ESP32 Actor.
4. Gleichzeitig fährt Stepper #1 den physischen Drehregler auf die passende Position.
5. AS5600 #1 bestätigt den tatsächlich erreichten Winkel.
6. UI zeigt Soll- und Istzustand konsistent an.

---

# 2. Geschwindigkeitsregler

## Logischer Zustand

Geschwindigkeit wird intern als normierter Wert geführt:

```text
0.0 ... 1.0
```

Die UI darf zusätzlich 0–100 % anzeigen.

```text
0.00 = Motor aus
0.25 = 25 %
0.50 = 50 %
1.00 = 100 %
```

## Winkelabbildung

Die mechanische Nutzstrecke wird kalibriert:

```text
SPEED_MIN_ANGLE_DEG
SPEED_MAX_ANGLE_DEG
```

Der Bereich wird linear auf 0–100 % abgebildet. Winkel außerhalb des kalibrierten Bereichs werden auf 0 bzw. 100 % begrenzt.

## Bedienung von Hand

1. Pi liest AS5600 #2 lokal mit hoher Rate.
2. Der Winkel wird auf 0–100 % abgebildet.
3. Kleine Sensoränderungen unterhalb eines Deadbands werden ignoriert.
4. Bei echter Änderung wird der neue Sollwert sofort per MQTT übertragen.
5. Der Stepper ist während normaler Handbedienung stromlos/freigegeben, damit der Regler leicht drehbar bleibt.

## Bedienung über Touchscreen

1. Benutzer verändert den Geschwindigkeitswert auf dem Screen.
2. Pi setzt den neuen Sollwert sofort.
3. Pi sendet ihn an den ESP32 Actor.
4. Stepper #2 bewegt den physischen Regler auf den entsprechenden Winkel.
5. AS5600 #2 bildet den geschlossenen Positionsregelkreis.
6. Nach Erreichen des Zielwinkels wird der Stepper wieder freigegeben/stromlos geschaltet.

---

# 3. Lokale Regelung am Raspberry Pi

Die Stepper-Regelung darf **nicht über WLAN** laufen. Pi 1 übernimmt lokal:

- AS5600-Auslesung
- Kalibrierung
- Winkelberechnung
- Stepper-Schritte
- Zielwinkelregelung
- Erkennung manueller Bedienung
- Deadband/Hysterese
- Synchronisation mit dem Touchscreen

Zielwerte für die lokale Schleife:

```text
Hall-Sensor-Abtastrate:      50–100 Hz
UI-Zustandsupdate:           20–30 Hz
Stepper-Regelung:            nicht blockierend, zeitbasiert
Motor nach Zielerreichung:   Wicklungen freigeben
```

Keine blockierende `while`-Schleife wie im POC in der finalen Pi-Anwendung. Die beiden Regler müssen gleichzeitig arbeiten können und Flask/MQTT dürfen nicht blockiert werden.

---

# 4. Stepper-Hardware

Der Raspberry Pi darf einen Stepper niemals direkt treiben.

Pro Regler wird benötigt:

```text
Raspberry Pi GPIO
      │
      ▼
Stepper-Treiber
      │
      ▼
Stepper-Motor
```

Falls die im POC verwendeten 4-phasigen Stepper/28BYJ-48 weiterverwendet werden, ist pro Stepper z. B. ein passender ULN2003-Treiber vorzusehen. Bei einem späteren Wechsel auf andere Stepper wird der Treiber entsprechend angepasst.

Die Stepper-Versorgung soll nicht aus dem 3,3-V-Pin des Raspberry Pi erfolgen.

---

# 5. Fahrmotor am ESP32 Actor

Der ESP32 Actor übernimmt die zeitkritische lokale Ansteuerung des eigentlichen Fahrmotors.

Er erhält von Pi 1 nur hochrangige Sollwerte:

```text
direction = LEFT | RIGHT
speed = 0.0 ... 1.0
```

Der ESP32 setzt daraus lokal die Signale für den Motor-/Leistungstreiber um. PWM oder Motortreiber-Timing werden **nicht über MQTT ferngesteuert**.

Dadurch bleibt die Motorsteuerung auch bei schwankender WLAN-Latenz deterministisch.

---

# 6. MQTT für Fahrsteuerung

Zusätzliche Topics:

```text
messecar/drive/command/direction
messecar/drive/command/speed
messecar/drive/heartbeat
messecar/drive/state
messecar/dials/state
messecar/dials/status
```

## Richtung

Topic:

```text
messecar/drive/command/direction
```

Payload:

```json
{
  "device": "pi1",
  "seq": 1042,
  "timestamp_ms": 123456,
  "direction": "LEFT"
}
```

- QoS 1
- nicht retained
- idempotenter Set-Befehl, kein Toggle

## Geschwindigkeit

Topic:

```text
messecar/drive/command/speed
```

Payload:

```json
{
  "device": "pi1",
  "seq": 1043,
  "timestamp_ms": 123470,
  "speed": 0.62
}
```

- QoS 0 für geringe Latenz
- nicht retained
- immer absoluter Sollwert, niemals `+/-` Änderung
- neue Werte ersetzen ältere Werte

## Heartbeat

Topic:

```text
messecar/drive/heartbeat
```

Pi sendet zyklisch den aktuell gültigen Gesamtfahrbefehl:

```json
{
  "device": "pi1",
  "seq": 1050,
  "timestamp_ms": 123500,
  "direction": "LEFT",
  "speed": 0.62
}
```

Zielrate:

```text
10 Hz / alle 100 ms
```

Der Heartbeat ist nicht retained.

## Drive-State vom ESP

Topic:

```text
messecar/drive/state
```

Beispiel:

```json
{
  "device": "esp32_actor",
  "timestamp_ms": 123520,
  "direction": "LEFT",
  "speed_target": 0.62,
  "motor_enabled": true,
  "failsafe": false,
  "rssi": -48
}
```

---

# 7. Latenzanforderung

Die Funkstrecke ist nur für Sollwerte zuständig. Ziel für lokale MesseCar-WLAN-Kommunikation:

```text
Regleränderung -> MQTT-Publish:          <= 20 ms nach Erkennung
Pi -> ESP Sollwert sichtbar:             Ziel <= 50 ms typisch
Gesamte spürbare Reaktion:               Ziel < 100 ms
Heartbeat:                               100 ms
ESP-Fail-Safe-Timeout:                   500 ms
```

Die Software muss Sequenznummern verwenden. Der ESP darf einen Befehl mit älterer `seq` als dem zuletzt verarbeiteten Befehl nicht anwenden.

---

# 8. Fail-Safe des Fahrmotors

Der Fahrmotor darf bei Kommunikationsverlust nicht unkontrolliert weiterlaufen.

Verbindliche Regel:

```text
Kein gültiger Drive-Heartbeat für 500 ms
                │
                ▼
       speed_target = 0.0
       motor_enabled = false
       failsafe = true
```

Nach Wiederverbindung darf der ESP **nicht automatisch einen alten retained Speed-Befehl übernehmen**. Erst ein neuer gültiger Heartbeat/Command von Pi 1 darf den Motor wieder freigeben.

Weitere Regeln:

- Boot des ESP: Geschwindigkeit immer 0.
- Boot von Pi 1: Geschwindigkeit zunächst 0.
- MQTT-Reconnect: zunächst 0, bis neuer Sollzustand aktiv gesendet wurde.
- Richtungswechsel bei laufendem Motor: zuerst Geschwindigkeit auf 0, danach Richtung wechseln, danach gewünschte Geschwindigkeit wieder freigeben.
- Keine Toggle-Befehle für Fahrtrichtung oder Geschwindigkeit.

---

# 9. Zustandsquelle und Synchronisation

Pi 1 ist die zentrale Sollwertquelle für UI und beide Regler.

Priorität:

```text
manuelle Reglerbewegung
        oder
Touchscreen-Eingabe
        │
        ▼
Pi 1 Drive State
        │
        ├─► physische Reglerposition
        ├─► Bildschirm
        └─► MQTT zum ESP32 Actor
```

Der zuletzt bewusst vom Benutzer geänderte Eingang gewinnt. Eine motorisierte Nachführung des Reglers darf anschließend nicht als neue manuelle Benutzereingabe interpretiert und zurückgesendet werden.

Dafür benötigt jeder Regler mindestens die Zustände:

```text
IDLE
MANUAL
MOTOR_MOVING
SETTLING
ERROR
```

Während `MOTOR_MOVING` werden Hall-Winkel zur Regelung genutzt, aber nicht als neue Benutzeranforderung interpretiert.

---

# 10. Fehlerzustände

Pro Regler müssen mindestens erkannt werden:

- AS5600 nicht erreichbar
- ungültiger Magnetstatus / Magnet außerhalb nutzbarem Bereich, sofern auslesbar
- Zielposition innerhalb Timeout nicht erreicht
- Stepper bewegt sich, Hall-Winkel ändert sich nicht
- unerwartete große Winkeländerung
- Kalibrierung fehlt/ungültig

Bei Fehler des Geschwindigkeitsreglers bleibt der Touchscreen bedienbar; der physische Regler wird als Fehler markiert. Ein Kommunikations-/Controllerfehler darf den ESP-Fail-Safe nicht umgehen.

Bei Fehler des Richtungsreglers wird kein automatischer Richtungswechsel aus einer unsicheren Zwischenposition ausgelöst.

---

# 11. Definition of Done

Die neue Regler-/Fahrantriebsarchitektur ist abgeschlossen, wenn:

1. Potentiometer und alter Richtungsschalter durch zwei motorisierte Magnet-Drehregler ersetzt sind.
2. Zwei AS5600 unabhängig am Pi ausgelesen werden können.
3. Beide Stepper gleichzeitig nicht blockierend geregelt werden können.
4. Manuelles Drehen aktualisiert den Screen und den Fahrzustand.
5. Screen-Eingaben bewegen den passenden realen Regler.
6. Der eigentliche Fahrmotor wird ausschließlich lokal vom ESP32 Actor angesteuert.
7. Geschwindigkeit und Richtung werden über WLAN/MQTT mit Sequenznummern übertragen.
8. Die typische Bedienreaktion liegt unter 100 ms.
9. Bei Verlust des Drive-Heartbeats stoppt der ESP den Fahrmotor spätestens nach 500 ms.
10. Nach Reconnect wird kein alter Fahrbefehl automatisch wieder aktiviert.
11. Richtungswechsel erfolgt nur mit vorher auf 0 gesetzter Geschwindigkeit.
12. USB/Serial zwischen Pi und ESP bleibt im realen Aufbau deaktiviert.
