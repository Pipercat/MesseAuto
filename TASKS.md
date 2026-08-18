# MesseAuto – Arbeitsplan

Diese Aufgabenliste ist der verbindliche Zielplan für die weitere Entwicklung des MesseAuto/MesseCar-Projekts. Aufgaben sollen in der angegebenen Reihenfolge umgesetzt und erst dann abgehakt werden, wenn die jeweiligen Abnahmekriterien erfüllt sind.

## Zielarchitektur

```text
Physische Taster ─► ESP32 Actor ─┐
                                 │ WLAN / MQTT
Sensorik ────────► ESP32 Sensor ─┼────────► Raspberry Pi 1 ── HTTP/JSON ──► Raspberry Pi 2
                                 │              │                         │
                                 └──────────────┘              GPIO-Impulse / UI      Diagnose / SQLite

USB/Serial ESP32 <-> Pi 1: DEAKTIVIERT, nur als Fallback im Code behalten.
```

Grund: Eine direkte USB-Verbindung verbindet die Masse von ESP32 und Raspberry Pi. Im aktuellen Fahrzeugaufbau entsteht dadurch ein unerwünschter Ground-Pfad/Kurzschluss. Die Funkverbindung muss deshalb der Standardweg sein.

---

## M1 – Kommunikationsarchitektur festziehen

- [ ] **MA-01-001 – MQTT als primären ESP↔Pi-Transport definieren**
  - Raspberry Pi 1 betreibt oder erreicht einen lokalen MQTT-Broker.
  - Keine Cloud-Abhängigkeit.
  - ESP32 Actor und ESP32 Sensor kommunizieren ausschließlich per WLAN/MQTT mit Pi 1.
  - USB/Serial bleibt im Quellcode erhalten, ist standardmäßig deaktiviert.
  - Abnahme: README, HARDWARE und Code verwenden dieselbe Architektur.

- [ ] **MA-01-002 – Eigenes MesseCar-WLAN festlegen**
  - Bevorzugt: Raspberry Pi 1 stellt einen lokalen WLAN-Access-Point bereit.
  - Arbeitsname SSID: `MesseCar`.
  - Das System muss ohne Internet und ohne externen Router funktionieren.
  - ESP32 Actor und Sensor verbinden sich automatisch mit diesem WLAN.
  - Abnahme: Nach Neustart verbinden sich beide ESPs automatisch.

- [ ] **MA-01-003 – MQTT-Broker auf Pi 1 einrichten**
  - Broker: Mosquitto.
  - Nur im lokalen MesseCar-Netz erreichbar.
  - Persistenz ist für reine Live-Zustände nicht erforderlich.
  - LWT/Last-Will für beide ESPs verwenden.
  - Abnahme: Pi 1 empfängt Publish-Nachrichten von beiden ESPs und kann Befehle publizieren.

## M2 – MQTT-Protokoll implementieren

- [ ] **MA-02-001 – Topic-Struktur implementieren**
  - `messecar/actor/status`
  - `messecar/actor/event/button`
  - `messecar/actor/state`
  - `messecar/actor/command`
  - `messecar/sensor/status`
  - `messecar/sensor/telemetry`
  - `messecar/pi1/status`
  - Keine zusätzlichen Topics ohne Dokumentationsupdate.

- [ ] **MA-02-002 – Nachrichtenformat festlegen**
  - JSON UTF-8.
  - Jede Nachricht enthält `device`, `timestamp_ms` und die jeweiligen Nutzdaten.
  - Actor-Button-Beispiel:

    ```json
    {"device":"esp32_actor","timestamp_ms":123456,"button":1}
    ```

  - Sensor-Beispiel:

    ```json
    {"device":"esp32_sensor","timestamp_ms":123456,"temperature_c":23.4,"seat_distance_cm":41.8}
    ```

  - Command-Beispiel:

    ```json
    {"device":"pi1","timestamp_ms":123456,"function":"highBeam","enabled":true}
    ```

- [ ] **MA-02-003 – Retain/QoS-Regeln festlegen**
  - Events wie Tastendrücke: nicht retained.
  - Zustände/Online-Status: retained.
  - QoS 1 für Commands und Button-Events.
  - Telemetrie darf QoS 0 verwenden.

## M3 – Raspberry Pi 1 umbauen

- [ ] **MA-03-001 – Serial standardmäßig deaktivieren**
  - Environment: `MESSEAUTO_SERIAL_ENABLED=false` als Default.
  - Keine automatische Port-Suche bei deaktiviertem Serial.
  - Vorhandene Serial-Funktionen nicht löschen.
  - Abnahme: Pi 1 startet ohne angeschlossene ESPs und öffnet keine `/dev/tty*`-Verbindung.

- [ ] **MA-03-002 – MQTT-Client in Pi 1 ergänzen**
  - Python-Bibliothek: `paho-mqtt`.
  - Automatischer Reconnect.
  - Verbindungsausfall darf Flask/UI/GPIO nicht blockieren.
  - MQTT-Callbacks dürfen keine langen blockierenden Operationen ausführen.

- [ ] **MA-03-003 – Actor-Events über MQTT verarbeiten**
  - `button` 1–10 auf bestehendes `BUTTON_FUNCTIONS`-Mapping abbilden.
  - Reserve-Taster 8–10 nur loggen.
  - Warnblinker verhält sich weiterhin wie bisher.
  - Alte periodische Zustände dürfen keine neuen UI-Befehle zurücksetzen.

- [ ] **MA-03-004 – Pi-Befehle an Actor über MQTT senden**
  - UI/API-Befehle werden auf `messecar/actor/command` publiziert.
  - Der GPIO-Impuls am Pi bleibt unverändert.
  - Actor soll den logischen Zustand übernehmen und zurückmelden.

- [ ] **MA-03-005 – Sensorwerte über MQTT übernehmen**
  - `temperature_c` und `seat_distance_cm` aus `messecar/sensor/telemetry` übernehmen.
  - Ungültige JSON-Nachrichten ignorieren und protokollieren.
  - Wertebereiche plausibilisieren.

- [ ] **MA-03-006 – Kommunikationsstatus in `/api/esp32` erweitern**
  - Pro Gerät: `connected`, `transport`, `last_seen`, optional `rssi`.
  - `transport` muss `mqtt`, `serial` oder `none` sein.
  - Timeout für Offline-Erkennung konfigurierbar machen.

## M4 – ESP32 Actor umbauen

- [ ] **MA-04-001 – WLAN-Verbindung implementieren**
  - Automatischer Reconnect.
  - Taster- und Aktorlogik muss auch bei WLAN-Ausfall weiterlaufen.
  - Keine Endlosschleife, die das Gerät bei fehlendem WLAN blockiert.

- [ ] **MA-04-002 – MQTT-Client implementieren**
  - Eindeutige Client-ID.
  - Last-Will `offline` auf `messecar/actor/status`.
  - Nach Verbindung retained `online` senden.

- [ ] **MA-04-003 – Tastendrücke als Events senden**
  - Nur echte Flanken/Tastendrücke publizieren.
  - Entprellung bleibt aktiv.
  - Kein periodisches Wiederholen eines alten Tastendrucks.

- [ ] **MA-04-004 – Commands von Pi 1 empfangen**
  - `highBeam`, `lowBeam`, `underbody`, `leftIndicator`, `rightIndicator`, `hazard`, `fan` unterstützen.
  - Unbekannte Funktionen ignorieren und seriell debuggen.
  - Nach erfolgreicher Änderung neuen Actor-State publizieren.

## M5 – ESP32 Sensor umbauen

- [ ] **MA-05-001 – WLAN + MQTT hinzufügen**
  - Gleiche Reconnect-Strategie wie Actor.
  - Last-Will und Online-Status.

- [ ] **MA-05-002 – Telemetrie publizieren**
  - Temperatur und Sitzabstand regelmäßig senden.
  - Messrate konfigurierbar, Ziel zunächst 1 Hz.
  - Medianfilter der Abstandsmessung beibehalten.

- [ ] **MA-05-003 – Sensorfehler eindeutig übertragen**
  - Kein fiktiver Messwert bei Sensorfehler.
  - Fehlerstatus als eigenes Feld übertragen.
  - Pi 1 muss `null`/Fehler sauber anzeigen können.

## M6 – Sicherheit und Fehlertoleranz

- [ ] **MA-06-001 – Ground-Trennung dokumentieren**
  - ESP32 und Raspberry Pi dürfen im aktuellen Aufbau nicht per USB verbunden werden.
  - USB nur zum separaten Flashen/Debuggen verwenden, wenn dadurch keine problematische Verbindung zur Fahrzeugschaltung entsteht.
  - Warnhinweis sichtbar in README und HARDWARE.

- [ ] **MA-06-002 – Kommunikationsausfall definieren**
  - MQTT-Ausfall darf keine GPIOs selbstständig umschalten.
  - Letzter Zustand bleibt sichtbar, wird aber als stale/offline markiert.
  - Keine automatische Wiederholung alter Commands nach Reconnect, wenn dadurch unbeabsichtigtes Schalten entstehen könnte.

- [ ] **MA-06-003 – Not-Aus/All-Off prüfen**
  - `/api/all-off` muss weiterhin lokal am Pi funktionieren.
  - MQTT-Actor erhält zusätzlich passende Off-Commands.
  - Test ohne Actor-Verbindung und mit Actor-Verbindung durchführen.

## M7 – Pi 2 und Diagnose

- [ ] **MA-07-001 – Kommunikationsart anzeigen**
  - Diagnose zeigt für Actor/Sensor Online/Offline, Transport und `last_seen`.

- [ ] **MA-07-002 – MQTT-Ausfall als Testfall ergänzen**
  - Broker offline.
  - Actor offline.
  - Sensor offline.
  - Reconnect.
  - Keine unbeabsichtigten Schaltimpulse beim Reconnect.

- [ ] **MA-07-003 – Telemetrie um Netzwerkstatus erweitern**
  - ESP-Verbindungsstatus in SQLite erfassbar machen.
  - RSSI optional speichern, sofern vom ESP übertragen.

## M8 – PC-Simulation

- [ ] **MA-08-001 – MQTT-Verhalten simulieren**
  - Testbench muss Online/Offline und Nachrichtenfluss darstellen können.
  - Button-Event und Sensor-Telemetrie getrennt simulieren.

- [ ] **MA-08-002 – Fehlerfälle simulierbar machen**
  - Actor offline.
  - Sensor offline.
  - Broker offline.
  - verzögerte Telemetrie.
  - ungültiges JSON.

## M9 – Abschluss und Hardwaretest

- [ ] **MA-09-001 – Test ohne USB-Verbindung durchführen**
  - Pi 1, Actor und Sensor ausschließlich über WLAN/MQTT verbinden.
  - Alle Fahrzeugfunktionen einmal schalten.
  - Alle physischen Taster prüfen.
  - Temperatur und Sitzabstand prüfen.

- [ ] **MA-09-002 – 30-Minuten-Dauertest**
  - Keine spontanen GPIO-Impulse.
  - Keine verlorenen Reconnects.
  - Keine alten Button-Events nach Reconnect.
  - Diagnose/Telemetrie bleibt stabil.

- [ ] **MA-09-003 – Serial-Fallback testen, aber deaktiviert lassen**
  - Nur in sicherem, galvanisch geeignetem Testaufbau.
  - Aktivierung ausschließlich über Konfiguration.
  - Nach Test wieder `MESSEAUTO_SERIAL_ENABLED=false`.

---

# M10 – Motorisierte Drehregler und Fahrantrieb

> **Status:** Nur geplant. Dieser Abschnitt definiert die Aufgaben vollständig; noch nichts davon soll durch das Anlegen dieser Aufgaben implementiert werden.
>
> Die bisherige Bedienung aus Potentiometer für Geschwindigkeit und Schalter für Fahrtrichtung soll später durch zwei motorisierte Drehregler ersetzt werden. Beide Drehregler werden am Raspberry Pi 1 ausgewertet und motorisiert nachgeführt. Der eigentliche Fahrmotor wird vom ESP32 Actor gesteuert. Pi und ESP tauschen dafür nur Sollwerte über WLAN/MQTT aus.

## M10.1 – Hardwarekonzept der zwei Drehregler

- [ ] **MA-10-001 – Zwei motorisierte Drehregler als Zielhardware festlegen**
  - Drehregler A = Fahrtrichtung.
  - Drehregler B = Geschwindigkeit.
  - Jeder Regler besteht aus einem Stepper, einem Magneten und einem berührungslosen Hall-Winkelsensor.
  - Der vorhandene `motorDialPOC` dient als mechanische und funktionale Referenz, wird aber nicht ungeprüft 1:1 übernommen.
  - Beide Regler müssen sowohl von Hand als auch vom Raspberry Pi bewegt werden können.
  - Der Benutzer darf den Regler im normalen Handbetrieb nicht gegen einen dauerhaft bestromten Stepper drehen müssen.
  - Abnahme: Komponenten, Mechanik und gewünschte Bewegungsbereiche beider Regler sind dokumentiert, bevor Code implementiert wird.

- [ ] **MA-10-002 – Finalen Stepper-Typ und Treiber je Regler festlegen**
  - Prüfen, welcher Stepper tatsächlich im vorhandenen POC verbaut ist.
  - Falls 28BYJ-48/4-phasiger Unipolar-Stepper: je Stepper einen geeigneten ULN2003-Treiber vorsehen.
  - Falls ein anderer Stepper verwendet wird: passenden Treiber, Spannung, Strom und Schrittauflösung dokumentieren.
  - Stepper niemals direkt an Raspberry-Pi-GPIO betreiben.
  - Motorversorgung nicht aus dem 3,3-V-Pin des Raspberry Pi beziehen.
  - Abnahme: finaler Stepper, Treiber und Versorgung sind eindeutig festgelegt.

- [ ] **MA-10-003 – Zwei AS5600 am Raspberry Pi elektrisch planen**
  - Beide AS5600 verwenden standardmäßig I²C-Adresse `0x36`.
  - Deshalb TCA9548A-I²C-Multiplexer einplanen.
  - TCA9548A Kanal 0 = Fahrtrichtungsregler.
  - TCA9548A Kanal 1 = Geschwindigkeitsregler.
  - Raspberry Pi liest beide Sensoren lokal aus.
  - Abnahme: beide AS5600 können unabhängig adressiert und ausgelesen werden.

- [ ] **MA-10-004 – Finale Pi-Pinbelegung für Stepper und I²C definieren**
  - Erst nach Festlegung des Stepper-Treibers durchführen.
  - Bestehende MesseCar-GPIOs berücksichtigen und Pin-Konflikte ausschließen.
  - I²C-Pins des Pi nicht für andere Funktionen blockieren.
  - Pinbelegung anschließend in `HARDWARE.md` ergänzen.
  - Abnahme: keine GPIO-Doppelbelegung und keine Konflikte mit vorhandenen Fahrzeugfunktionen.

## M10.2 – Gemeinsame Dial-Software auf Pi 1

- [ ] **MA-10-005 – Wiederverwendbares Dial-Controller-Modul entwerfen**
  - Eine gemeinsame Softwareabstraktion für beide Regler vorsehen.
  - Jeder Regler besitzt mindestens: Sensor, Stepper-Treiber, Kalibrierung, Sollwinkel, Istwinkel und Betriebszustand.
  - Betriebszustände mindestens: `IDLE`, `MANUAL`, `MOTOR_MOVING`, `SETTLING`, `ERROR`.
  - Beide Regler müssen gleichzeitig arbeiten können.
  - Keine blockierende Motor-Schleife verwenden, die Flask, MQTT oder den zweiten Regler anhält.
  - Abnahme: Schnittstellen und Zustandsautomat sind definiert, bevor Implementierung beginnt.

- [ ] **MA-10-006 – AS5600-Auslesung mit TCA9548A planen**
  - Winkel pro Regler in Grad bereitstellen.
  - 0/360°-Wrap korrekt behandeln.
  - Sensorfehler abfangen.
  - Ziel-Abtastrate pro Regler zunächst 50–100 Hz.
  - Magnet-/Sensorstatus auswerten, soweit vom AS5600 verfügbar.
  - Abnahme: beide Regler liefern unabhängig stabile Istwinkel.

- [ ] **MA-10-007 – Nicht blockierende Stepper-Regelung planen**
  - Stepper zeitbasiert schalten, nicht über lange `while`-Schleifen.
  - Geschlossener Regelkreis: Sollwinkel → Stepperbewegung → AS5600-Istwinkel.
  - Nach Erreichen des Zielwinkels Stepperwicklungen freigeben, sofern Hardware dies erlaubt.
  - Zielposition mit konfigurierbarer Toleranz bestätigen.
  - Timeout für nicht erreichbare Zielposition definieren.
  - Abnahme: beide Stepper können parallel positioniert werden, ohne UI/MQTT zu blockieren.

- [ ] **MA-10-008 – Manuelle Bewegung von automatischer Bewegung unterscheiden**
  - Während `MOTOR_MOVING` dürfen Hall-Winkeländerungen nicht als neuer Benutzerwunsch interpretiert werden.
  - Nach automatischer Positionierung kurze `SETTLING`-Phase vorsehen.
  - Nur echte Handbewegung im Zustand `IDLE/MANUAL` darf einen neuen Sollwert erzeugen.
  - Rückkopplungsschleifen zwischen Stepperbewegung, Hall-Sensor, UI und MQTT verhindern.
  - Abnahme: Screen→Regler erzeugt nicht erneut Regler→Screen→Regler-Schleifen.

## M10.3 – Fahrtrichtungsregler

- [ ] **MA-10-009 – Fahrtrichtungsregler mit zwei gültigen Positionen definieren**
  - Gültige Zustände: `LEFT` und `RIGHT`.
  - Die physische Regleranzeige soll entsprechend eindeutig nach links oder rechts zeigen.
  - Eine Zwischenstellung ist kein neuer gültiger Fahrbefehl.
  - Während einer Bewegung bleibt die zuletzt bestätigte Richtung gültig, bis die neue Position eindeutig erkannt wurde.
  - Abnahme: LEFT/RIGHT-Verhalten ist ohne Flattern in der Mitte definiert.

- [ ] **MA-10-010 – Fahrtrichtungsregler kalibrierbar machen**
  - `LEFT`-Winkel einlernen.
  - `RIGHT`-Winkel einlernen.
  - Umschaltschwelle definieren.
  - Hysterese gegen Flattern definieren.
  - Kalibrierwerte persistent speichern.
  - Mechanische Orientierung darf nicht hart im Code vorausgesetzt werden.
  - Abnahme: Regler kann nach Montage neu kalibriert werden, ohne Codeänderung.

- [ ] **MA-10-011 – Manuelle Richtungswahl über Drehregler definieren**
  - Pi überwacht den Hall-Winkel lokal.
  - Beim Drehen bleibt alter Fahrzustand bestehen, bis die neue Richtungsschwelle sicher überschritten ist.
  - Danach Pi-Sollzustand auf `LEFT` oder `RIGHT` setzen.
  - UI unmittelbar synchronisieren.
  - Neue Richtung per Drive-MQTT an ESP senden.
  - Optional den Regler nach Loslassen motorisch auf die exakte Endposition nachführen.
  - Abnahme: Handbewegung ändert Richtung zuverlässig genau einmal.

- [ ] **MA-10-012 – Screen-gesteuerte Richtungswahl definieren**
  - Benutzer wählt `LEFT` oder `RIGHT` auf dem Fahrzeug-Screen.
  - Pi übernimmt den neuen Sollzustand unmittelbar.
  - Pi sendet den neuen Fahrbefehl zum ESP.
  - Parallel fährt Stepper des Richtungsreglers auf die kalibrierte Zielposition.
  - Hall-Sensor bestätigt die reale Reglerposition.
  - UI muss Sollzustand, Istposition und Fehlerzustand unterscheiden können.
  - Abnahme: Screen-Eingabe bewegt den realen Regler ohne Rückkopplungsschleife.

## M10.4 – Geschwindigkeitsregler

- [ ] **MA-10-013 – Geschwindigkeitsbereich als 0–100 % definieren**
  - Intern normierter Sollwert `0.0 ... 1.0`.
  - UI zeigt 0–100 %.
  - `0.0` bedeutet Motor aus.
  - `1.0` bedeutet maximal freigegebene Geschwindigkeit.
  - Mechanischer Minimal- und Maximalwinkel werden kalibriert.
  - Winkel außerhalb des Nutzbereichs werden auf 0 bzw. 100 % begrenzt.
  - Abnahme: Winkel↔Geschwindigkeit ist eindeutig und reproduzierbar.

- [ ] **MA-10-014 – Geschwindigkeitsregler kalibrierbar machen**
  - 0-%-Winkel einlernen.
  - 100-%-Winkel einlernen.
  - lineare Abbildung als Ausgangspunkt verwenden.
  - Deadband gegen AS5600-Rauschen festlegen.
  - Kalibrierwerte persistent speichern.
  - Abnahme: mechanische Toleranzen können ohne Codeänderung ausgeglichen werden.

- [ ] **MA-10-015 – Manuelle Geschwindigkeitsänderung über Drehregler definieren**
  - Stepper im normalen Handbetrieb freigeben/stromlos halten, sofern Hardware dies erlaubt.
  - Hall-Sensor lokal mit hoher Rate lesen.
  - relevante Winkeländerungen auf `0.0 ... 1.0` umrechnen.
  - kleine Änderungen innerhalb Deadband nicht als neuen Fahrbefehl senden.
  - UI sofort mitführen.
  - neuen Sollwert ohne unnötige Verzögerung an den Drive-MQTT-Pfad übergeben.
  - Abnahme: händisches Drehen wirkt direkt und ohne spürbares Nachlaufen.

- [ ] **MA-10-016 – Screen-gesteuerte Geschwindigkeit definieren**
  - Benutzer setzt Geschwindigkeit auf dem Screen.
  - Pi übernimmt den neuen Sollwert unmittelbar.
  - Pi sendet ihn sofort zum ESP.
  - Parallel fährt Stepper des Geschwindigkeitsreglers auf den entsprechenden Winkel.
  - AS5600 bestätigt die reale Position.
  - Nach Zielerreichung Stepper freigeben/stromlos schalten.
  - Abnahme: Screen und realer Drehregler zeigen denselben Wert.

## M10.5 – WLAN/MQTT für zeitkritische Fahrwerte

- [ ] **MA-10-017 – Drive-MQTT-Topics festlegen**
  - `messecar/drive/command/direction`
  - `messecar/drive/command/speed`
  - `messecar/drive/heartbeat`
  - `messecar/drive/state`
  - `messecar/dials/state`
  - `messecar/dials/status`
  - Drive-Topics getrennt von normalen Licht-/Taster-Topics halten.
  - Abnahme: Topic-Aufgaben, Publisher und Subscriber sind eindeutig dokumentiert.

- [ ] **MA-10-018 – Fahrbefehle als absolute Sollwerte definieren**
  - Richtung immer als `LEFT` oder `RIGHT`, niemals als Toggle.
  - Geschwindigkeit immer als absoluter Wert `0.0 ... 1.0`, niemals als `+/-` Änderung.
  - Jede relevante Nachricht enthält `device`, `seq`, `timestamp_ms` und Nutzdaten.
  - Sequenznummer auf Pi monoton erhöhen.
  - ESP ignoriert veraltete Sequenznummern.
  - Abnahme: alte/reordered MQTT-Nachrichten können keinen neueren Fahrzustand überschreiben.

- [ ] **MA-10-019 – Low-Latency-Regeln für Geschwindigkeit definieren**
  - Geschwindigkeits-Commands nicht retained.
  - Geschwindigkeit bevorzugt QoS 0, damit neue Sollwerte alte Werte schnell ersetzen.
  - Keine MQTT-Nachricht pro minimalem Sensorschritt; Deadband und sinnvolle Änderungsrate verwenden.
  - Ziel: Pi veröffentlicht eine erkannte echte Regleränderung innerhalb von maximal ca. 20 ms nach lokaler Erkennung.
  - Ziel: Pi→ESP typischerweise <=50 ms im lokalen MesseCar-WLAN.
  - Ziel: gesamte subjektive Bedienreaktion <100 ms.
  - Abnahme: Latenz wird später real gemessen und protokolliert.

- [ ] **MA-10-020 – Richtungsbefehle zuverlässig übertragen**
  - Richtung nicht retained.
  - QoS 1 verwenden.
  - Befehl idempotent gestalten.
  - ESP bestätigt aktuell angewendete Richtung in `messecar/drive/state`.
  - Abnahme: verlorene oder doppelte MQTT-Zustellung verursacht keinen Toggle-/Doppelwechsel.

- [ ] **MA-10-021 – Drive-Heartbeat definieren**
  - Pi sendet zyklisch den aktuell gültigen Gesamtfahrbefehl.
  - Zielrate 10 Hz / alle 100 ms.
  - Heartbeat enthält mindestens `seq`, `direction`, `speed`, `timestamp_ms`.
  - Heartbeat nicht retained.
  - Abnahme: ESP kann unabhängig von Einzelcommands erkennen, ob Pi noch aktiv ist.

## M10.6 – Fahrmotor am ESP32 Actor

- [ ] **MA-10-022 – Fahrmotor vollständig dem ESP32 Actor zuordnen**
  - Der eigentliche Fahrmotor wird später vom ESP32 Actor gesteuert.
  - Raspberry Pi gibt keine PWM-Einzelimpulse über WLAN vor.
  - Pi sendet nur `direction` und `speed` als Sollwerte.
  - ESP erzeugt lokal PWM/Richtungslogik für den Motor-/Leistungstreiber.
  - Abnahme: Motor-Timing ist unabhängig von WLAN-Jitter.

- [ ] **MA-10-023 – Finalen Fahrmotor-Treiber festlegen**
  - Motortyp, Versorgungsspannung und maximalen Strom erfassen.
  - passenden Motor-/Leistungstreiber auswählen bzw. vorhandenen prüfen.
  - ESP-Pins für PWM/Direction/Enable erst danach festlegen.
  - benötigte Schutzbeschaltung dokumentieren.
  - Abnahme: Hardware kann den Fahrmotor sicher in beiden Richtungen und im gewünschten Geschwindigkeitsbereich treiben.

- [ ] **MA-10-024 – ESP Drive-State definieren**
  - mindestens `direction`.
  - `speed_target`.
  - `motor_enabled`.
  - `failsafe`.
  - `last_drive_seq`.
  - optional `rssi` und Fehlerstatus.
  - State regelmäßig/bei Änderungen auf `messecar/drive/state` veröffentlichen.
  - Abnahme: Pi und Diagnose können den tatsächlich angewendeten Motorzustand sehen.

## M10.7 – Sicherheitslogik für WLAN-Fahrmotor

- [ ] **MA-10-025 – Fahrmotor-Watchdog auf ESP definieren**
  - Kein gültiger Drive-Heartbeat für 500 ms → Geschwindigkeit auf 0.
  - Motor deaktivieren.
  - `failsafe=true` setzen.
  - ESP-Boot startet immer mit Geschwindigkeit 0.
  - Abnahme: WLAN-/Broker-/Pi-Ausfall kann den Motor nicht dauerhaft mit altem Sollwert weiterlaufen lassen.

- [ ] **MA-10-026 – Sicheren MQTT-Reconnect definieren**
  - Speed- und Direction-Commands nicht retained.
  - Nach Reconnect keinen alten Speed-Befehl automatisch übernehmen.
  - Motor bleibt auf 0, bis ein neuer gültiger Drive-Heartbeat/Command vom Pi eintrifft.
  - Sequenznummern verhindern Anwendung verspäteter Pakete.
  - Abnahme: Netzwerkunterbrechung und Wiederverbindung führen nicht zu einem spontanen Motorstart.

- [ ] **MA-10-027 – Sicheren Richtungswechsel während Fahrt definieren**
  - Wenn `speed > 0`, Richtungswechsel nicht unmittelbar unter Last durchführen.
  - zuerst Sollgeschwindigkeit auf 0.
  - auf bestätigten Stillstands-/0-Speed-Zustand wechseln.
  - danach Richtung setzen.
  - anschließend gewünschte Geschwindigkeit wieder freigeben.
  - benötigte Wartezeit/Bestätigung später anhand realer Motorhardware festlegen.
  - Abnahme: kein harter elektrischer/mechanischer Richtungswechsel unter Last.

## M10.8 – UI und Kalibrierung

- [ ] **MA-10-028 – Fahrzeug-Screen um Fahrtrichtung erweitern**
  - klare LEFT/RIGHT-Auswahl.
  - aktuellen Sollzustand anzeigen.
  - reale Dial-Position anzeigen bzw. Status ableiten.
  - Fehler/Offline-Zustand sichtbar machen.
  - Screen-Bedienung muss auch funktionieren, wenn der physische Regler einen Fehler hat.

- [ ] **MA-10-029 – Fahrzeug-Screen um Geschwindigkeitssteuerung erweitern**
  - Bedienwert 0–100 %.
  - aktuellen Sollwert anzeigen.
  - reale Dial-Position/Feedback anzeigen.
  - Motor-/ESP-Failsafe sichtbar anzeigen.
  - UI darf keine unnötige Rate an MQTT-Nachrichten erzeugen.

- [ ] **MA-10-030 – Dial-Kalibrierungsseite ergänzen**
  - Rohwinkel beider AS5600 anzeigen.
  - Fahrtrichtung LEFT/RIGHT einlernen.
  - Geschwindigkeit 0/100 % einlernen.
  - Hysterese/Deadband konfigurierbar machen.
  - Stepper einzeln testweise bewegen.
  - Magnet-/Sensorstatus anzeigen.
  - Konfiguration persistent speichern.

## M10.9 – Fehlerdiagnose

- [ ] **MA-10-031 – Fehlerzustände pro Drehregler definieren**
  - AS5600 nicht erreichbar.
  - TCA9548A/Kanal nicht erreichbar.
  - Magnet außerhalb des nutzbaren Bereichs, soweit erkennbar.
  - Zielwinkel nicht innerhalb Timeout erreicht.
  - Stepper wird angesteuert, aber Hall-Winkel ändert sich nicht plausibel.
  - ungültige/fehlende Kalibrierung.
  - Fehler dürfen die restliche Pi-Anwendung nicht blockieren.

- [ ] **MA-10-032 – Verhalten bei Fehler des Geschwindigkeitsreglers definieren**
  - Touchscreen bleibt bedienbar.
  - physischer Dial wird als fehlerhaft markiert.
  - keine unkontrollierte automatische Stepperbewegung.
  - Fahrmotor bleibt weiterhin durch ESP-Watchdog geschützt.

- [ ] **MA-10-033 – Verhalten bei Fehler des Richtungsreglers definieren**
  - keine neue Fahrtrichtung aus einer unsicheren Zwischenposition ableiten.
  - letzter bestätigter Zustand bleibt sichtbar.
  - Screen kann weiterhin eine bewusste Richtungsvorgabe liefern, sofern Gesamtsystem dies zulässt.
  - Fehlerzustand deutlich anzeigen.

## M10.10 – Simulation und Tests

- [ ] **MA-10-034 – Zwei motorisierte Drehregler in PC-Simulation ergänzen**
  - manuellen Winkel simulieren.
  - automatische Steppernachführung simulieren.
  - LEFT/RIGHT-Logik simulieren.
  - 0–100-%-Geschwindigkeit simulieren.
  - Zustände `MANUAL`, `MOTOR_MOVING`, `SETTLING`, `ERROR` darstellen.

- [ ] **MA-10-035 – Drive-MQTT in Simulation ergänzen**
  - Direction Command.
  - Speed Command.
  - Heartbeat.
  - Drive-State vom ESP.
  - einstellbare Netzwerkverzögerung und Paketverlust.
  - veraltete Sequenznummern testen.

- [ ] **MA-10-036 – Latenztest definieren**
  - Zeit von realer/manueller Regleränderung bis Pi-Erkennung messen.
  - Publish-Zeitpunkt erfassen.
  - Empfang am ESP erfassen.
  - Motor-Ausgangsänderung erfassen.
  - Median, typische und Worst-Case-Latenz dokumentieren.
  - Ziel: subjektive Reaktion <100 ms im lokalen WLAN.

- [ ] **MA-10-037 – Watchdog-/Reconnect-Test definieren**
  - WLAN am ESP unterbrechen.
  - MQTT-Broker stoppen.
  - Pi 1 stoppen.
  - prüfen, dass Motor spätestens nach 500 ms auf 0/Failsafe geht.
  - Verbindung wiederherstellen.
  - prüfen, dass kein alter Speed-Befehl automatisch startet.

- [ ] **MA-10-038 – Richtungswechsel unter Last testen**
  - mit niedriger Geschwindigkeit starten.
  - Gegenrichtung anfordern.
  - prüfen: Speed→0, Richtung wechseln, danach erneute Freigabe.
  - erst nach erfolgreichem Niedriglasttest höhere Geschwindigkeiten prüfen.

- [ ] **MA-10-039 – Parallelbetrieb beider Dials testen**
  - beide Hall-Sensoren gleichzeitig lesen.
  - beide Stepper gleichzeitig bewegen.
  - UI parallel bedienen.
  - MQTT parallel senden.
  - keine Blockierung oder gegenseitige Störung zulassen.

## M10 – Definition of Done

Dieser Umbau gilt erst als abgeschlossen, wenn:

1. Potentiometer und alter Richtungsschalter durch zwei motorisierte Magnet-Drehregler ersetzt sind.
2. Beide AS5600 unabhängig am Raspberry Pi ausgelesen werden.
3. Beide Stepper gleichzeitig nicht blockierend geregelt werden können.
4. Manuelles Drehen den Pi-/UI-Sollzustand aktualisiert.
5. Screen-Eingaben den passenden physischen Drehregler motorisch nachführen.
6. Der tatsächliche Fahrmotor lokal vom ESP32 Actor gesteuert wird.
7. Pi nur absolute Richtung-/Geschwindigkeits-Sollwerte über WLAN/MQTT sendet.
8. Fahrbefehle Sequenznummern besitzen und alte Pakete ignoriert werden.
9. Die typische Bedienreaktion im lokalen WLAN unter 100 ms liegt.
10. Der ESP bei fehlendem Drive-Heartbeat spätestens nach 500 ms den Motor deaktiviert.
11. Nach WLAN/MQTT-Reconnect kein alter Fahrbefehl automatisch reaktiviert wird.
12. Richtungswechsel nicht unter aktiver Motorleistung erfolgt.
13. Fehler eines Dial-Sensors oder Steppers die restliche MesseCar-Anwendung nicht blockieren.
14. USB/Serial zwischen Pi und ESP im realen Aufbau weiterhin deaktiviert bleibt.

## Definition of Done

Der WLAN/MQTT-Umbau gilt erst als abgeschlossen, wenn:

1. Zwischen ESP32 und Raspberry Pi keine USB-Datenverbindung benötigt wird.
2. Actor und Sensor nach Neustart automatisch verbinden.
3. Physische Taster, Pi-UI und GPIO-Impulse konsistent bleiben.
4. Sensorwerte auf Pi 1 und Pi 2 sichtbar sind.
5. Ausfälle und Reconnects keine unbeabsichtigten Schaltvorgänge verursachen.
6. USB/Serial weiterhin im Code vorhanden, aber standardmäßig deaktiviert ist.
7. README, HARDWARE.md und diese Aufgabenliste den realen Aufbau widerspruchsfrei beschreiben.
