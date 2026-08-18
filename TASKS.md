# MesseAuto – zentrale Task-Datenbank

Diese Datei ist die **einzige kanonische Aufgabenliste** für das MesseAuto/MesseCar-Projekt. Es sollen keine separaten Task-Dateien mehr angelegt werden.

## Abarbeitungsregel

Eine KI oder ein Entwickler arbeitet diese Tabelle strikt nach `order` ab:

1. Überspringe Datensätze mit `status=done`.
2. Wähle den kleinsten offenen `order`-Wert, dessen `depends_on` erfüllt ist.
3. Setze den Datensatz beim Start auf `in_progress`.
4. Implementiere ausschließlich den beschriebenen Scope.
5. Prüfe das angegebene `acceptance`-Kriterium.
6. Erst nach erfolgreicher Prüfung auf `done` setzen.
7. Danach mit dem nächsten Datensatz fortfahren.
8. Bei einem echten Hardware-/Informationsblocker `status=blocked` setzen und den Blocker im Feld `notes` dokumentieren; keine Pinbelegung, Hardwareeigenschaft oder Messung erfinden.

Erlaubte Statuswerte: `todo`, `in_progress`, `blocked`, `done`.

Prioritäten: `P0` sicherheits-/fahrkritisch, `P1` Kernfunktion, `P2` Diagnose/Komfort, `P3` optional.

## Zielarchitektur

```text
Screen 1 / Raspberry Pi 1
  ├─ Fahrzeug-UI
  ├─ Adminübersicht über Logo oben rechts
  ├─ GPIO-Fahrzeugfunktionen
  ├─ 2 motorisierte Drehregler + 2 AS5600 + Stepper
  ├─ lokales MesseCar-WLAN / MQTT-Broker
  └─ HTTP/JSON zu Raspberry Pi 2

ESP32 Actor
  ├─ physische Taster / Actor-Funktionen
  └─ Fahrmotor lokal, Sollwerte per WLAN/MQTT

ESP32 Sensor/Aux
  ├─ Temperatur
  ├─ Sitzabstand
  └─ Fahrzeughupe lokal über Audio + PAM8406

Raspberry Pi 2
  ├─ Diagnose
  ├─ Tests
  └─ SQLite-Telemetrie

USB/Serial ESP32 <-> Pi 1
  └─ Legacy-Fallback, im realen Fahrzeug standardmäßig deaktiviert
```

## Task-Datenbank

| order | id | phase | status | priority | depends_on | system | task | acceptance | notes |
|---:|---|---|---|---|---|---|---|---|---|
| 10 | MA-01-001 | M1 Netzwerk | todo | P0 | - | Gesamt | MQTT als primären ESP↔Pi-Transport festlegen; vollständig lokal, keine Cloud, USB/Serial nur Legacy-Fallback. | README/HARDWARE/Code-Zielbild widerspruchsfrei; keine aktive USB-Pflicht. | - |
| 20 | MA-01-002 | M1 Netzwerk | todo | P1 | MA-01-001 | Pi1/WLAN | Eigenes lokales MesseCar-WLAN planen; Pi 1 bevorzugt als Access Point, SSID `MesseCar`, Betrieb ohne Internet/externen Router. | Beide ESPs können nach Neustart automatisch in das lokale Netz verbinden. | Credentials später sicher konfigurierbar halten. |
| 30 | MA-01-003 | M1 Netzwerk | todo | P1 | MA-01-002 | Pi1/MQTT | Mosquitto-Broker auf Pi 1 planen/einrichten; nur im lokalen Netz, LWT für ESPs. | Pi 1 kann Publish/Subscribe mit beiden ESPs durchführen. | - |
| 40 | MA-02-001 | M2 MQTT Basis | todo | P1 | MA-01-003 | MQTT | Basistopics definieren: `messecar/actor/status`, `actor/event/button`, `actor/state`, `actor/command`, `sensor/status`, `sensor/telemetry`, `pi1/status`. | Publisher/Subscriber je Topic eindeutig dokumentiert. | Neue Topics nur mit Update dieser DB. |
| 50 | MA-02-002 | M2 MQTT Basis | todo | P1 | MA-02-001 | MQTT | Einheitliches JSON-Format mit `device`, `timestamp_ms` und Nutzdaten; bei steuernden Befehlen zusätzlich Sequenznummern, wo definiert. | Ungültiges JSON wird verworfen und protokolliert; Beispiele/tests vorhanden. | UTF-8. |
| 60 | MA-02-003 | M2 MQTT Basis | todo | P1 | MA-02-002 | MQTT | QoS/Retain-Regeln festlegen: Events nicht retained; Online/State ggf. retained; Commands idempotent; Telemetrie QoS0 möglich. | Reconnect löst keine alten Schaltbefehle aus. | - |
| 70 | MA-03-001 | M3 Pi1 | done | P0 | - | Pi1/Serial | Serial standardmäßig über `MESSEAUTO_SERIAL_ENABLED=false` deaktivieren; Portscan nur bei expliziter Aktivierung. | Pi 1 startet ohne ESP-USB und öffnet keine Serial-Ports. | Bereits umgesetzt; Legacy-Code bleibt vorhanden. |
| 80 | MA-03-002 | M3 Pi1 | todo | P1 | MA-02-003 | Pi1/MQTT | Nicht blockierenden MQTT-Client mit Reconnect in Pi 1 integrieren. | Flask/UI/GPIO laufen bei Broker-Ausfall weiter; Reconnect automatisch. | `paho-mqtt` vorgesehen. |
| 90 | MA-03-003 | M3 Pi1 | todo | P1 | MA-03-002 | Pi1/Actor | Actor-Button-Events 1–10 über MQTT auf bestehendes Mapping abbilden; Reserve 8–10 nur loggen. | Jeder physische Tastendruck löst genau eine erwartete Aktion aus. | Periodische States dürfen UI-Befehle nicht überschreiben. |
| 100 | MA-03-004 | M3 Pi1 | todo | P1 | MA-03-002 | Pi1/Actor | UI/API-Aktorbefehle über `messecar/actor/command` senden und Actor-State zurückführen. | Pi und Actor bleiben logisch synchron; doppelte Nachrichten verursachen keinen Togglefehler. | - |
| 110 | MA-03-005 | M3 Pi1 | todo | P1 | MA-03-002 | Pi1/Sensor | Temperatur und Sitzabstand aus MQTT-Telemetrie übernehmen und plausibilisieren. | `/api/sensors` zeigt gültige Werte/Fehlerzustände und `last_seen`. | Keine fiktiven Werte bei Fehler. |
| 120 | MA-03-006 | M3 Pi1 | todo | P2 | MA-03-002 | Pi1/API | `/api/esp32` um `connected`, `transport`, `last_seen`, optional `rssi`, IP und Fehlerstatus erweitern. | MQTT/Serial/Offline-Zustand pro ESP eindeutig sichtbar. | - |
| 130 | MA-04-001 | M4 ESP Actor | todo | P1 | MA-01-003 | ESP Actor | WLAN-Verbindung mit automatischem Reconnect implementieren; lokale Tasterlogik darf bei WLAN-Ausfall nicht blockieren. | Actor bleibt lokal bedienbar und verbindet sich selbstständig wieder. | - |
| 140 | MA-04-002 | M4 ESP Actor | todo | P1 | MA-04-001 | ESP Actor/MQTT | MQTT-Client mit eindeutiger Client-ID und Last-Will `offline` implementieren. | Online/Offline wird zuverlässig erkannt. | - |
| 150 | MA-04-003 | M4 ESP Actor | todo | P1 | MA-04-002 | ESP Actor | Echte entprellte Tastendrücke als einmalige Events publizieren. | Kein periodisches Wiederholen alter Tastendrücke. | - |
| 160 | MA-04-004 | M4 ESP Actor | todo | P1 | MA-04-002 | ESP Actor | Commands für Licht/Blinker/Warnblinker/Lüfter empfangen und neuen State publizieren. | Bekannte Funktionen reagieren; unbekannte Commands werden sicher ignoriert. | - |
| 170 | MA-05-001 | M5 ESP Sensor/Aux | todo | P1 | MA-01-003 | ESP Sensor/Aux | WLAN + MQTT mit Reconnect, eindeutiger Client-ID, Last-Will und Online-State ergänzen. | Sensor/Aux verbindet nach Neustart automatisch. | Später zusätzlich Hupe, siehe M11. |
| 180 | MA-05-002 | M5 ESP Sensor/Aux | todo | P1 | MA-05-001 | ESP Sensor/Aux | Temperatur und Sitzabstand regelmäßig publizieren; Medianfilter der Distanz beibehalten. | Standardmäßig stabile Telemetrie etwa 1 Hz; Rate konfigurierbar. | - |
| 190 | MA-05-003 | M5 ESP Sensor/Aux | todo | P1 | MA-05-002 | ESP Sensor/Aux | Sensorfehler explizit übertragen; `null`/Fehlercode statt erfundener Messwerte. | Pi 1/Pi 2 zeigen Sensorfehler eindeutig. | - |
| 200 | MA-06-001 | M6 Sicherheit | done | P0 | - | Hardware | Ground-Regel dokumentieren: ESPs und Pi im realen Fahrzeug nicht dauerhaft per USB verbinden; Serial nur in galvanisch sicherem Aufbau. | Warnhinweis im Repo vorhanden. | Bereits dokumentiert. |
| 210 | MA-06-002 | M6 Sicherheit | todo | P0 | MA-03-002 | Gesamt | Kommunikationsausfall definieren: keine spontanen GPIO-/Aktorschaltungen; States als stale/offline markieren; alte Commands nicht wiederholen. | Broker/ESP-Ausfall erzeugt keine unbeabsichtigte Fahrzeugaktion. | - |
| 220 | MA-06-003 | M6 Sicherheit | todo | P0 | MA-03-004 | Pi1/Actor | `/api/all-off` lokal erhalten und passende Off-Commands über MQTT senden. | All-Off funktioniert mit und ohne erreichbaren Actor deterministisch. | Fahrmotor/Hupe separat über ihre Fail-Safes. |
| 230 | MA-07-001 | M7 Pi2 Diagnose | todo | P2 | MA-03-006 | Pi2 | ESP-Kommunikationsart, Online/Offline, RSSI und `last_seen` im Diagnose-Screen anzeigen. | Fehlerquelle ohne SSH erkennbar. | - |
| 240 | MA-07-002 | M7 Pi2 Diagnose | todo | P1 | MA-06-002 | Pi2/Test | Testfälle Broker offline, Actor offline, Sensor/Aux offline und Reconnect hinzufügen. | Kein unbeabsichtigtes Schalten bei allen Fehlerfällen. | - |
| 250 | MA-07-003 | M7 Pi2 Diagnose | todo | P2 | MA-07-001 | Pi2/SQLite | Netzwerk-/ESP-Status optional in Telemetrie speichern, inkl. RSSI/Reconnects. | Verlauf von Verbindungsproblemen auswertbar. | - |
| 260 | MA-08-001 | M8 Simulation | todo | P2 | MA-02-003 | Simulation | MQTT-Nachrichtenfluss, Online/Offline, Button-Events und Sensor-Telemetrie simulieren. | Kernkommunikation ohne Fahrzeughardware testbar. | - |
| 270 | MA-08-002 | M8 Simulation | todo | P2 | MA-08-001 | Simulation | Broker-Ausfall, verzögerte Telemetrie, ungültiges JSON und Reconnect simulieren. | Fehlerfälle reproduzierbar und erwartetes Verhalten sichtbar. | - |
| 280 | MA-09-001 | M9 Integration | todo | P1 | MA-04-004,MA-05-003 | Gesamt | Volltest ausschließlich über WLAN/MQTT ohne ESP↔Pi-USB durchführen. | Alle Fahrzeugfunktionen, Taster und Sensoren funktionieren. | - |
| 290 | MA-09-002 | M9 Integration | todo | P1 | MA-09-001 | Gesamt | 30-Minuten-Dauertest mit Reconnects durchführen. | Keine spontanen GPIO-Impulse, verlorenen Reconnects oder alten Events. | - |
| 300 | MA-09-003 | M9 Integration | todo | P3 | MA-09-002 | Legacy Serial | Serial-Fallback nur in galvanisch sicherem Testaufbau prüfen und anschließend wieder deaktivieren. | Fallback funktioniert; Default bleibt `false`. | - |
| 310 | MA-10-001 | M10 Drehregler | todo | P1 | MA-09-001 | Pi1/Mechanik | Zwei motorisierte Drehregler festlegen: A Fahrtrichtung, B Geschwindigkeit; je Stepper + Magnet + berührungsloser Hall-Winkelsensor; vorhandener `motorDialPOC` als Referenz. | Mechanik, Bewegungsbereich und Komponenten dokumentiert. | Kein Produktivcode vor Hardwarefestlegung. |
| 320 | MA-10-002 | M10 Drehregler | todo | P1 | MA-10-001 | Pi1/Hardware | Finalen Stepper-Typ und Treiber je Regler bestimmen; bei 28BYJ-48 z.B. ULN2003; Stepper nie direkt am Pi treiben. | Spannung, Strom, Treiber und Versorgung eindeutig festgelegt. | - |
| 330 | MA-10-003 | M10 Drehregler | todo | P1 | MA-10-001 | Pi1/I2C | Zwei AS5600 mit gleicher Adresse `0x36` über TCA9548A trennen; Kanal 0 Richtung, Kanal 1 Geschwindigkeit. | Beide Winkel unabhängig lesbar. | - |
| 340 | MA-10-004 | M10 Drehregler | todo | P1 | MA-10-002,MA-10-003 | Pi1/GPIO | Finale konfliktfreie Pinbelegung für Stepper/Treiber/I²C definieren. | Keine Doppelbelegung mit bestehenden GPIO-Funktionen; HARDWARE aktualisiert. | Keine Pins raten. |
| 350 | MA-10-005 | M10 Drehregler | todo | P1 | MA-10-004 | Pi1/Software | Wiederverwendbaren Dial-Controller mit Zuständen `IDLE`, `MANUAL`, `MOTOR_MOVING`, `SETTLING`, `ERROR` entwerfen. | Beide Regler können parallel ohne blockierende Schleifen betrieben werden. | - |
| 360 | MA-10-006 | M10 Drehregler | todo | P1 | MA-10-005 | Pi1/I2C | AS5600-Auslesung über TCA9548A, 0/360-Wrap, Fehler-/Magnetstatus und Zielrate 50–100 Hz je Regler implementieren. | Stabile Winkel beider Regler, Fehler sauber erkannt. | - |
| 370 | MA-10-007 | M10 Drehregler | todo | P1 | MA-10-005,MA-10-006 | Pi1/Stepper | Nicht blockierende geschlossene Stepper-Regelung Sollwinkel→Stepper→Hall-Istwinkel; Toleranz, Timeout, Freigabe nach Ziel. | Beide Stepper parallel positionierbar; UI/MQTT bleiben responsiv. | - |
| 380 | MA-10-008 | M10 Drehregler | todo | P1 | MA-10-007 | Pi1/State | Manuelle Bewegung von Motorbewegung unterscheiden; Stepperbewegung darf nicht als neuer User-Input rückgekoppelt werden. | Keine Screen↔Stepper↔Hall-Endlosschleife. | - |
| 390 | MA-10-009 | M10 Richtung | todo | P1 | MA-10-008 | Pi1/Dial A | Richtungsregler mit genau `LEFT`/`RIGHT` definieren; Zwischenbereich kein neuer Fahrbefehl. | Kein Flattern in Mittelzone. | - |
| 400 | MA-10-010 | M10 Richtung | todo | P1 | MA-10-009 | Pi1/Dial A | LEFT-/RIGHT-Winkel, Umschaltschwelle und Hysterese kalibrierbar/persistent machen. | Nach mechanischer Montage ohne Codeänderung kalibrierbar. | - |
| 410 | MA-10-011 | M10 Richtung | todo | P1 | MA-10-010 | Pi1/Dial A | Manuelles Drehen setzt nach sicherer Schwellenüberschreitung genau einmal LEFT/RIGHT, synchronisiert UI und Drive-State. | Handbedienung zuverlässig, ohne Doppelwechsel. | - |
| 420 | MA-10-012 | M10 Richtung | todo | P1 | MA-10-010,MA-10-007 | Screen/Pi1 | Screen-Auswahl LEFT/RIGHT setzt Sollzustand sofort und bewegt gleichzeitig den physischen Regler; Hall bestätigt Istposition. | Screen und realer Regler bleiben konsistent. | - |
| 430 | MA-10-013 | M10 Geschwindigkeit | todo | P1 | MA-10-008 | Pi1/Dial B | Geschwindigkeit intern `0.0..1.0`, UI 0–100 %, mechanischen Min/Max-Winkel abbilden. | Winkel↔Geschwindigkeit reproduzierbar; 0 = Motor aus. | - |
| 440 | MA-10-014 | M10 Geschwindigkeit | todo | P1 | MA-10-013 | Pi1/Dial B | 0-%-/100-%-Winkel, Deadband und Kalibrierung persistent machen. | Mechanische Toleranzen ohne Codeänderung ausgleichbar. | - |
| 450 | MA-10-015 | M10 Geschwindigkeit | todo | P1 | MA-10-014 | Pi1/Dial B | Manuelle Drehbewegung lokal erfassen, Deadband anwenden, UI sofort mitführen und neuen absoluten Speed-Sollwert erzeugen. | Direkte Bedienung ohne spürbares Nachlaufen. | Stepper im Handbetrieb möglichst freigegeben. |
| 460 | MA-10-016 | M10 Geschwindigkeit | todo | P1 | MA-10-014,MA-10-007 | Screen/Pi1 | Screen-Speed setzt Sollwert sofort und fährt physischen Geschwindigkeitsregler motorisch nach; Hall bestätigt. | Screen und Regler zeigen denselben Wert; Stepper danach freigegeben. | - |
| 470 | MA-10-017 | M10 Drive MQTT | todo | P0 | MA-02-003 | MQTT/Drive | Drive-Topics festlegen: `drive/command/direction`, `drive/command/speed`, `drive/heartbeat`, `drive/state`, `dials/state`, `dials/status`. | Publisher/Subscriber eindeutig dokumentiert. | Prefix `messecar/`. |
| 480 | MA-10-018 | M10 Drive MQTT | todo | P0 | MA-10-017 | MQTT/Drive | Fahrbefehle ausschließlich als absolute Werte mit `seq`/Timestamp; Richtung niemals Toggle, Speed niemals Delta. | ESP ignoriert ältere/reordered Sequenzen. | - |
| 490 | MA-10-019 | M10 Drive MQTT | todo | P0 | MA-10-018 | MQTT/Drive | Low-Latency-Speed: nicht retained, bevorzugt QoS0, Deadband/Rate-Limit; Ziel Publish ≤20 ms nach Erkennung, Pi→ESP typisch ≤50 ms, Reaktion <100 ms. | Latenz später real gemessen und protokolliert. | Keine PWM-Pakete übers WLAN. |
| 500 | MA-10-020 | M10 Drive MQTT | todo | P0 | MA-10-018 | MQTT/Drive | Richtungscommands nicht retained, QoS1, idempotent; ESP bestätigt angewandte Richtung. | Doppelte Zustellung verursacht keinen Doppelwechsel. | - |
| 510 | MA-10-021 | M10 Drive MQTT | todo | P0 | MA-10-018 | MQTT/Drive | Drive-Heartbeat mit aktuellem direction/speed/seq etwa 10 Hz, nicht retained. | ESP erkennt Pi-Ausfall unabhängig von Einzelcommands. | - |
| 520 | MA-10-022 | M10 Fahrmotor | todo | P0 | MA-10-017 | ESP Actor/Motor | Fahrmotor vollständig lokal dem ESP Actor zuordnen; Pi sendet nur direction/speed, ESP erzeugt PWM/Direction/Enable lokal. | Motor-Timing unabhängig von WLAN-Jitter. | - |
| 530 | MA-10-023 | M10 Fahrmotor | todo | P0 | MA-10-022 | Hardware/Motor | Motortyp, Spannung, Maximalstrom und vorhandenen/geeigneten Motor-Treiber bestimmen; Schutzbeschaltung und ESP-Pins erst danach definieren. | Treiber kann Motor sicher in beiden Richtungen und im Zielbereich treiben. | Keine Hardwarewerte erfinden. |
| 540 | MA-10-024 | M10 Fahrmotor | todo | P1 | MA-10-022 | ESP Actor/Motor | `drive/state` mit direction, speed_target, motor_enabled, failsafe, last_drive_seq, optional RSSI/Fehler publizieren. | Pi/Diagnose sehen tatsächlich angewandten Motorzustand. | - |
| 550 | MA-10-025 | M10 Fahrmotor Safety | todo | P0 | MA-10-021,MA-10-022 | ESP Actor/Motor | Drive-Watchdog: kein gültiger Heartbeat für 500 ms → Speed 0, Motor disabled, failsafe true. | WLAN/Broker/Pi-Ausfall stoppt Motor lokal innerhalb Timeout. | Timeout später hardwaretesten. |
| 560 | MA-10-026 | M10 Fahrmotor Safety | todo | P0 | MA-10-025 | ESP Actor/Motor | Boot/Reconnect-Sicherheit: Motor startet immer mit Speed 0; alte/retained Drive-Commands dürfen nie Motorstart auslösen. | Neustart/Reconnect bleibt bewegungssicher. | - |
| 570 | MA-10-027 | M10 Fahrmotor Safety | todo | P0 | MA-10-025 | ESP Actor/Motor | Sicheren Richtungswechsel definieren: zuerst Speed 0, Motorstillstand/definierte Pause, dann Richtung, danach gewünschter Speed. | Kein harter Richtungswechsel unter Last. | Finale Pause/Feedback hardwareabhängig. |
| 580 | MA-10-028 | M10 Dial Fehler | todo | P1 | MA-10-007 | Pi1/Dials | Fehler erkennen: AS5600 fehlt, Magnetproblem, Zieltimeout, Stepper bewegt sich ohne Winkeländerung, Kalibrierung ungültig. | Jeder Fehler führt zu eindeutiger Diagnose und sicherem Zustand. | - |
| 590 | MA-10-029 | M10 Integration | todo | P1 | MA-10-016,MA-10-027 | Simulation | Beide Dials, Screen-Steuerung, Drive-MQTT, Sequenzen, Latenz und Fail-Safe in Simulation abbilden. | End-to-End ohne Hardware reproduzierbar. | - |
| 600 | MA-10-030 | M10 Integration | todo | P0 | MA-10-029,MA-10-023 | Hardwaretest | Hardwaretests: manuell↔Screen, beide Stepper parallel, 100+ Speed-/Richtungsänderungen, WLAN-Ausfall, Motor-Failsafe. | Keine ungewollte Bewegung; typische Bedienreaktion <100 ms. | Erst nach sicherer Verdrahtung. |
| 610 | MA-11-001 | M11 Hupe | todo | P1 | MA-05-001 | ESP Sensor/Aux | Zweiten ESP offiziell als Sensor/Aux-Controller definieren: Sensorik + lokale Hupenfunktion; Sensorik darf durch Audio nicht blockieren. | Rollen und Verantwortlichkeiten eindeutig. | - |
| 620 | MA-11-002 | M11 Hupe | todo | P1 | MA-11-001 | ESP Sensor/Aux | Exakten Boardtyp des zweiten ESP bestimmen und mögliche Audioausgabe (DAC/I2S/PWM) sowie konfliktfreie Pins prüfen. | Boardtyp und nutzbarer Audiopfad eindeutig dokumentiert. | Keine Pins raten. |
| 630 | MA-11-003 | M11 Hupe | todo | P0 | MA-11-002 | Audio/Hardware | PAM8406 als reinen Audio-Leistungsverstärker dokumentieren; Versorgung, Eingang, Lautsprecherimpedanz/-leistung und Masseführung prüfen. | Elektrisch sicherer Audio-Pfad ohne neue Pi-GND-Verbindung festgelegt. | PAM8406 nicht als Tongenerator behandeln. |
| 640 | MA-11-004 | M11 Hupe | todo | P1 | MA-11-002,MA-11-003 | Audio/Hardware | Audiopfad festlegen: interner DAC falls geeignet, sonst I2S-DAC/Codec, gefilterte PWM nur wenn ausreichend. | Sauberes Eingangssignal am PAM8406 im Hardwaretest. | - |
| 650 | MA-11-005 | M11 Hupe | todo | P2 | MA-11-004 | Audio | Realistischen Fahrzeug-Hupenton festlegen; bevorzugt lokaler Sample-Loop oder geeignete Synthese; Lautstärke begrenzen. | Klangquelle, Format/Samplerate und Maximalpegel definiert. | Kein Audio-Streaming übers WLAN. |
| 660 | MA-11-006 | M11 Hupe | todo | P1 | MA-11-005 | UI/Audio | Hold-to-Honk-Verhalten definieren: press=start, release/cancel=stop, niemals Toggle. | Hupe nur aktiv, solange Benutzer gedrückt hält. | - |
| 670 | MA-11-007 | M11 Hupe MQTT | todo | P1 | MA-02-003,MA-11-006 | MQTT/Horn | Topic `messecar/horn/command`; Payload mit `device`,`seq`,`timestamp_ms`,`active`; nicht retained. | Absolute, idempotente Start/Stop-Befehle. | - |
| 680 | MA-11-008 | M11 Hupe MQTT | todo | P2 | MA-11-007 | MQTT/Horn | Topic `messecar/horn/state`; ESP meldet `active`, `audio_ok`, optional RSSI/Fehler. | Pi unterscheidet Soll- und bestätigten Hupenzustand. | - |
| 690 | MA-11-009 | M11 Hupe MQTT | todo | P1 | MA-11-007 | MQTT/Horn | Hupenlatenz optimieren: nur Steuerbefehle übertragen; Ziel Screen→Audio typisch <100 ms. | 100 Start/Stop-Vorgänge ohne merkliche Verzögerung oder verlorenen Stop. | - |
| 700 | MA-11-010 | M11 Hupe Safety | todo | P0 | MA-11-007 | ESP Sensor/Aux | Hupen-Lease/Keepalive: Pi sendet bei gedrückter Hupe ca. 10 Hz; kein Keepalive für zunächst 300 ms → lokal Hupe aus. | WLAN-/Brokerverlust bei gedrückter Hupe verstummt automatisch. | Timeout später testen. |
| 710 | MA-11-011 | M11 Hupe Safety | todo | P0 | MA-11-010 | ESP Sensor/Aux | Sequenznummern verwenden; alte/doppelte `active=true` ignorieren; retained Horn-Command verboten. | Verspätete Pakete können Hupe nicht unbeabsichtigt starten. | - |
| 720 | MA-11-012 | M11 Hupe Safety | todo | P0 | MA-11-010 | Pi1/ESP Aux | Boot/Reconnect immer Hupe AUS; erst neuer aktueller Press darf starten. | Broker-/ESP-/Pi-Neustart bleibt akustisch sicher. | - |
| 730 | MA-11-013 | M11 Hupe UI | todo | P1 | MA-11-006 | Screen1 | Touch-Hupenbutton mit pointer/touch down/up/cancel und sichtbarem Press-State planen. | Verlassen/Abbruch des Touchs sendet sicher `active=false`. | Kein Click-Toggle. |
| 740 | MA-11-014 | M11 Hupe Pi1 | todo | P1 | MA-11-007,MA-11-013 | Pi1 | Horn-Controller: bei press sofort true+Keepalive; bei release/cancel sofort false; MQTT-Ausfall darf UI nicht blockieren. | Zustandsautomat eindeutig und fail-safe. | - |
| 750 | MA-11-015 | M11 Hupe ESP | todo | P1 | MA-11-004,MA-11-010 | ESP Sensor/Aux | Lokalen nicht blockierenden Horn-Controller/Audio-Task implementieren; Sensoren und MQTT laufen parallel. | Hupe, Sensorik und Netzwerk gleichzeitig stabil. | - |
| 760 | MA-11-016 | M11 Hupe Diagnose | todo | P2 | MA-11-015 | ESP/Pi2 | Audiozustände `ready/playing/stopped/audio_error` und Fehlercodes publizieren/anzeigen. | Audiofehler führen sicher zu Hupe AUS und sind diagnostizierbar. | - |
| 770 | MA-11-017 | M11 Hupe Simulation | todo | P2 | MA-11-014,MA-11-015 | Simulation | Press/hold/release, Command/State und optional Browser-Sound simulieren. | Kommunikationslogik ohne Hardware testbar. | - |
| 780 | MA-11-018 | M11 Hupe Simulation | todo | P1 | MA-11-017 | Simulation | Verlorenes release, Brokerverlust, altes true, ESP-Reboot simulieren. | In jedem Fall fällt Hupe innerhalb Fail-Safe auf AUS. | - |
| 790 | MA-11-019 | M11 Hupe Hardwaretest | todo | P0 | MA-11-015 | Audio/Hardware | Audio-Pfad mit geringer Lautstärke testen; PAM8406-Versorgung/Pegel/Lautsprechererwärmung prüfen; kurzer Dauerhupentest. | Stabiler Ton ohne ESP-Reset, Sensorfehler oder Überhitzung. | Akustische Sicherheit beachten. |
| 800 | MA-11-020 | M11 Hupe Integration | todo | P1 | MA-11-019,MA-10-030 | Gesamt | WLAN-Latenz und Parallelbetrieb von Drive, Sensorik und Hupe mit mindestens 100 Hupvorgängen testen. | Keine hängende Hupe; Fahrsteuerung bleibt reaktionsschnell. | - |
| 810 | MA-12-001 | M12 Admin UI | todo | P2 | MA-03-006 | Screen1 | Klick/Tap auf Logo oben rechts öffnet versteckte Adminübersicht; kein großer sichtbarer Adminbutton. | Touch-Navigation zuverlässig; normale UI unbeeinträchtigt. | - |
| 820 | MA-12-002 | M12 Admin UI | todo | P2 | MA-12-001 | Screen1 | Klaren Rückweg `Zurück zum Fahrzeug` und optional Inaktivitäts-Timeout definieren. | Adminmodus jederzeit sicher verlassbar; Reload wiederholt keine Aktion. | - |
| 830 | MA-12-003 | M12 Admin Safety | todo | P0 | MA-12-001 | Admin | Kritische Aktionen immer bestätigen; Zielgerät+Aktion im Dialog; optional PIN-Sperre später. | Kein Reboot/Shutdown/Service-Restart durch einen versehentlichen Tap. | - |
| 840 | MA-12-004 | M12 Admin Overview | todo | P2 | MA-12-001 | Admin | Statuskarten für Pi1, Pi2, ESP Actor und ESP Sensor/Aux mit ONLINE/STALE/OFFLINE/ERROR und `last_seen`. | Fehlergerät innerhalb Sekunden erkennbar. | - |
| 850 | MA-12-005 | M12 Admin Overview | todo | P2 | MA-12-004 | Admin | Ampelsystem OK/WARNUNG/FEHLER/OFFLINE mit Text statt nur Farbe. | Status barrierearm und eindeutig. | - |
| 860 | MA-12-006 | M12 Admin Overview | todo | P2 | MA-12-004 | Admin | Gesamtstatus `BEREIT/EINGESCHRÄNKT/NICHT BEREIT` aus konfigurierbaren Kern-/Nebenfunktionen ableiten. | Techniker sieht sofort Vorführbereitschaft. | - |
| 870 | MA-12-007 | M12 Pi Metrics | todo | P2 | MA-12-001 | Pi1/Pi2 | CPU-Auslastung beider Pis, optional pro Core und kurzer Verlauf. | Hohe Last sichtbar. | - |
| 880 | MA-12-008 | M12 Pi Metrics | todo | P2 | MA-12-001 | Pi1/Pi2 | RAM gesamt/belegt/verfügbar/% und Swap anzeigen. | Speicherengpass erkennbar. | - |
| 890 | MA-12-009 | M12 Pi Metrics | todo | P2 | MA-12-001 | Pi1/Pi2 | Datenträger gesamt/belegt/frei/%; Pi2 zusätzlich SQLite-Größe; Warnschwellen konfigurierbar. | Drohender Speichermangel früh sichtbar. | - |
| 900 | MA-12-010 | M12 Pi Metrics | todo | P2 | MA-12-001 | Pi1/Pi2 | CPU-Temperatur und Thermal-/Throttlingstatus anzeigen. | Kühlungsproblem sichtbar. | - |
| 910 | MA-12-011 | M12 Pi Metrics | todo | P2 | MA-12-001 | Pi1/Pi2 | Uptime, letzter Bootzeitpunkt und optional zuverlässiger Reboot-Grund. | Spontane Neustarts nachvollziehbar. | - |
| 920 | MA-12-012 | M12 Pi Metrics | todo | P2 | MA-12-001 | Pi1/Pi2 | Hostname, OS, Kernel, MesseCar-Version/Commit und Runtime-Details anzeigen. | Support sieht exakt laufende Version. | - |
| 930 | MA-12-013 | M12 Netzwerk | todo | P2 | MA-01-003,MA-12-001 | Pi1 | Pi1 IPs, Ethernet, WLAN/AP, SSID und Broker-Erreichbarkeit anzeigen. | Netzwerkfehler ohne SSH eingrenzbar. | - |
| 940 | MA-12-014 | M12 Netzwerk | todo | P2 | MA-12-001 | Pi2 | Pi2 IP, Verbindung/API zu Pi1 und Round-Trip-Zeit anzeigen. | Pi2- vs. Verbindungsfehler unterscheidbar. | - |
| 950 | MA-12-015 | M12 Netzwerk | todo | P2 | MA-04-002,MA-05-001 | ESPs | Beide ESPs: Online, RSSI, IP, MQTT, `last_seen`, optional Reconnect-Zähler/Disconnect-Grund. | Funkprobleme diagnostizierbar. | - |
| 960 | MA-12-016 | M12 Netzwerk | todo | P2 | MA-12-013,MA-12-015 | Gesamt | Kommunikationslatenzen Pi1↔Pi2, Pi1↔Actor, Pi1↔Sensor/Aux und Drive-Latenz anzeigen. | Verzögerungsquelle lokalisierbar. | - |
| 970 | MA-12-017 | M12 Services | todo | P2 | MA-12-001 | Pi1 | Relevante Pi1-Dienste mit RUNNING/STOPPED/FAILED anzeigen: App/API, MQTT, Mosquitto, AP, ggf. Dial-Service. | Dienstefehler ohne Terminal sichtbar. | - |
| 980 | MA-12-018 | M12 Services | todo | P2 | MA-12-001 | Pi2 | Pi2 Collector/Web/Telemetrie und letzten erfolgreichen Poll anzeigen. | Pi2-Dienstefehler klar. | - |
| 990 | MA-12-019 | M12 Services | todo | P1 | MA-12-003,MA-12-017,MA-12-018 | Admin | Einzelne freigegebene Services per Adminaktion neu starten; Status RESTARTING und Ergebnis anzeigen. | Service-Restart ohne kompletten Pi-Reboot möglich. | Keine freie Shell/sudo-Eingabe. |
| 1000 | MA-12-020 | M12 Reboot | todo | P0 | MA-12-003,MA-10-025,MA-11-012 | Pi1 | Pi1-Reboot: vorher Drive-Speed 0, Motor safe, Hupe aus, keine neue Stepperbewegung; dann geordneter OS-Reboot. | Sicherer Reboot über Adminseite. | - |
| 1010 | MA-12-021 | M12 Reboot | todo | P1 | MA-12-003 | Pi2 | Pi2 separat rebooten; Pi1/Fahrzeug laufen weiter; Admin erkennt RESTARTING/OFFLINE/Reconnect. | Pi2 unabhängig wartbar. | - |
| 1020 | MA-12-022 | M12 Shutdown | todo | P0 | MA-12-003,MA-12-020 | Pi1/Pi2 | Pi1/Pi2 separat herunterfahren; Pi1 vorher Fahrzeug safe; Restart vs Shutdown klar unterscheiden und stärker bestätigen. | Kein versehentliches Ausschalten. | - |
| 1030 | MA-12-023 | M12 ESP Admin | todo | P0 | MA-12-003,MA-10-025,MA-11-012 | ESPs | Beide ESPs per nicht-retained MQTT-Admincommand rebooten; Actor vorher Motor 0/disabled, Sensor/Aux vorher Hupe aus. | ESPs rebooten ohne USB und verbinden danach automatisch. | - |
| 1040 | MA-12-024 | M12 Admin Safety | todo | P0 | MA-12-003 | Admin | Keinen einfachen `Alle Systeme neu starten`-Button anbieten; falls später nötig nur geführte Sequenz. | Ein Tap kann nie komplettes MesseCar offline setzen. | - |
| 1050 | MA-12-025 | M12 Fahrzeugdiagnose | todo | P2 | MA-03-004 | Admin | GPIO-/Fahrzeugzustände für Licht, Blinker, Warnblinker, Lüfter inkl. BCM und letztem Impuls anzeigen. | Softwarezustand und Pinzuordnung nachvollziehbar; Öffnen der Seite schaltet nichts. | - |
| 1060 | MA-12-026 | M12 Dial Diagnose | todo | P2 | MA-10-028 | Admin | Beide motorisierten Dials mit Ist-/Sollwinkel, Prozent/Richtung, Hall-, Stepper-, TCA9548A-, Kalibrier- und Fehlerstatus anzeigen. | Dial-Fehler ohne Debugkonsole eingrenzbar. | - |
| 1070 | MA-12-027 | M12 Drive Diagnose | todo | P1 | MA-10-024 | Admin | Fahrmotorstatus: Actor online, Sollrichtung/-speed, angewandter Zustand, Heartbeat-Alter, Failsafe, letzte seq. | Pi/ESP-State-Abweichung sofort sichtbar. | - |
| 1080 | MA-12-028 | M12 Sensor Diagnose | todo | P2 | MA-05-003 | Admin | Temperatur, Sitzabstand/-position, Sensorfehler, Alter der letzten Messung und optionale Rohwerte anzeigen. | Sensorzustand zentral nachvollziehbar. | - |
| 1090 | MA-12-029 | M12 Horn Diagnose | todo | P2 | MA-11-016 | Admin | Hupe: Soll/ist active, audio_ok, Lease-Alter, letzter Command, Aux-ESP-Status und Audiofehler anzeigen. | Hupenproblem eindeutig lokalisierbar. | - |
| 1100 | MA-12-030 | M12 Logs | todo | P2 | MA-12-001 | Admin/Pi1/Pi2 | Zentralen Ereignis-/Fehlerbereich vorsehen: Reconnects, Failsafes, Sensorfehler, Service-/Rebootaktionen; begrenzte Historie statt unendlicher Logs. | Letzte relevante Störung schnell auffindbar. | Keine sensiblen Secrets anzeigen. |
| 1110 | MA-12-031 | M12 Admin API | todo | P1 | MA-12-007,MA-12-030 | Pi1/Pi2 | Strukturierte System-Metrics-/Health-API für Adminseite definieren; keine Shell-Ausgaben direkt an UI durchreichen. | UI erhält validierte strukturierte Daten. | - |
| 1120 | MA-12-032 | M12 Admin API | todo | P0 | MA-12-003,MA-12-031 | Pi1/Pi2 | Whitelist-Adminaktionen implementieren: nur explizite Service-/Reboot-/Shutdown-/ESP-Kommandos, keine beliebigen Befehle. | Keine allgemeine Remote-Shell über Weboberfläche. | - |
| 1130 | MA-12-033 | M12 Admin Tests | todo | P1 | MA-12-032 | Simulation/Test | Adminaktionen in Simulation/Testmodus prüfen: Bestätigung, Fehlerantwort, Timeout, Ziel offline, Reconnect. | Kein falscher Erfolgsstatus; UI bleibt bedienbar. | - |
| 1140 | MA-12-034 | M12 Admin Tests | todo | P0 | MA-12-020,MA-12-023 | Hardwaretest | Sichere Reboots mit Motor/Hupe/Stepper in verschiedenen Zuständen hardwareseitig prüfen. | Vor jedem kritischen Neustart werden Aktoren sicher. | - |
| 1150 | MA-12-035 | M12 Finish | todo | P1 | MA-12-034,MA-10-030,MA-11-020 | Gesamt | End-to-End-Abnahme: normale UI, Logo→Admin, alle Metrics, Netz/Services, Drive/Dials/Sensor/Hupe, sichere Adminaktionen und Rückkehr zur UI. | Gesamtsystem mindestens 30 Minuten stabil; keine kritischen unbeabsichtigten Aktionen. | Abschluss der aktuellen Backlog-Version. |

## Definition of Done für die gesamte Task-Datenbank

Die aktuelle MesseCar-Ausbaustufe ist erst abgeschlossen, wenn alle nicht explizit als optional markierten Datensätze `status=done` haben und insbesondere:

- ESP↔Pi im realen Fahrzeug ohne dauerhafte USB-Datenverbindung funktioniert.
- WLAN/MQTT lokal und ohne Cloud stabil läuft.
- Fahrmotor bei Kommunikationsverlust lokal sicher auf 0 fällt.
- zwei motorisierte Drehregler manuell und vom Screen synchron bedienbar sind.
- die Hupe lokal auf ESP Sensor/Aux erzeugt wird und bei Kommunikationsverlust automatisch verstummt.
- Screen 1 über das Logo eine vollständige Adminübersicht öffnet.
- CPU, RAM, Speicher, Temperatur, Uptime, Netzwerk, Services, ESPs, Sensoren, Dials, Drive und Hupe diagnostizierbar sind.
- Neustart/Shutdown nur über whitelisted, bestätigte und aktorsichere Aktionen möglich ist.
- Simulation, Fehlerfälle und Hardware-Dauertests erfolgreich abgeschlossen sind.
