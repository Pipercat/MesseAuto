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

## Definition of Done

Der WLAN/MQTT-Umbau gilt erst als abgeschlossen, wenn:

1. Zwischen ESP32 und Raspberry Pi keine USB-Datenverbindung benötigt wird.
2. Actor und Sensor nach Neustart automatisch verbinden.
3. Physische Taster, Pi-UI und GPIO-Impulse konsistent bleiben.
4. Sensorwerte auf Pi 1 und Pi 2 sichtbar sind.
5. Ausfälle und Reconnects keine unbeabsichtigten Schaltvorgänge verursachen.
6. USB/Serial weiterhin im Code vorhanden, aber standardmäßig deaktiviert ist.
7. README, HARDWARE.md und diese Aufgabenliste den realen Aufbau widerspruchsfrei beschreiben.
