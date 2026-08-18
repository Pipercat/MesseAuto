# MQTT-Protokoll MesseCar

Kanonische Referenz für alle MQTT-Topics zwischen Raspberry Pi 1, ESP32 Actor und ESP32 Sensor/Aux. Broker: Mosquitto auf Pi 1 (siehe [`HARDWARE.md`](HARDWARE.md), Abschnitt „MQTT-Broker (Mosquitto) auf Pi 1"), erreichbar für die ESPs über den lokalen `MesseCar`-AP (`10.10.10.1:1883`).

Alle Topics tragen den gemeinsamen Präfix `messecar/`. Neue Topics werden ausschließlich hier ergänzt (siehe `TASKS.md`, MA-02-001 Acceptance: „Neue Topics nur mit Update dieser DB" — Update erfolgt in `TASKS.md` **und** hier).

## Basistopics (MA-02-001)

| Topic | Publisher | Subscriber | Zweck |
|---|---|---|---|
| `messecar/actor/status` | ESP Actor | Pi 1 | Online/Offline-Status des ESP Actor, inkl. Last-Will (`offline` bei Verbindungsabbruch, siehe MA-04-002). |
| `messecar/actor/event/button` | ESP Actor | Pi 1 | Einzelne, entprellte Tasterereignisse (Taster 1–10) als Events, kein periodisches Wiederholen. |
| `messecar/actor/state` | ESP Actor | Pi 1 | Aktuell angewandter Actor-Zustand (Licht/Blinker/Lüfter etc.) zur Rücksynchronisation mit Pi 1/UI. |
| `messecar/actor/command` | Pi 1 | ESP Actor | Von UI/API ausgelöste Aktorbefehle (Licht/Blinker/Warnblinker/Lüfter). |
| `messecar/sensor/status` | ESP Sensor/Aux | Pi 1 | Online/Offline-Status des ESP Sensor/Aux, inkl. Last-Will. |
| `messecar/sensor/telemetry` | ESP Sensor/Aux | Pi 1 | Temperatur- und Sitzabstands-Telemetrie. |
| `messecar/pi1/status` | Pi 1 | ESP Actor, ESP Sensor/Aux | Online-Status von Pi 1 selbst, damit ESPs einen Pi-1-Ausfall erkennen können. |

Weitere Topics (Drive-MQTT aus M10, Horn-MQTT aus M11) werden bei Bearbeitung der jeweiligen Tasks (MA-10-017, MA-11-007, MA-11-007A, MA-11-008) hier ergänzt.

## Nachrichtenformat (MA-02-002)

Alle Payloads sind UTF-8-kodiertes JSON mit mindestens folgenden Feldern:

```json
{
  "device": "esp_actor",
  "timestamp_ms": 1755504000000
}
```

- `device`: fester String je Gerät (`esp_actor`, `esp_sensor_aux`, `pi1`).
- `timestamp_ms`: Unix-Zeit in Millisekunden zum Erzeugungszeitpunkt der Nachricht (nicht Empfangszeitpunkt).
- Steuernde Befehle (`*/command`, `drive/command/*`, `horn/command`) enthalten zusätzlich `seq` (monoton steigende Sequenznummer je Quelle), damit veraltete/vertauschte Nachrichten erkennbar sind.
- Alle übrigen Felder sind topic-spezifische Nutzdaten (z. B. `button`, `state`, `temperature_c`).

Beispiel `messecar/actor/event/button`:

```json
{"device": "esp_actor", "timestamp_ms": 1755504000000, "button": 8, "edge": "pressed"}
```

Beispiel `messecar/actor/command`:

```json
{"device": "pi1", "timestamp_ms": 1755504000123, "seq": 42, "function": "blinker_left", "value": true}
```

**Validierung:** Der Empfänger parst jede Nachricht strikt als JSON und prüft `device`/`timestamp_ms` auf Vorhandensein und Typ. Ungültiges JSON oder fehlende Pflichtfelder werden verworfen und mit Topic + Fehlergrund protokolliert, ohne den Prozess zu blockieren. Die konkrete Implementierung dieser Validierung erfolgt mit dem MQTT-Client in MA-03-002 (Pi 1) bzw. MA-04-002/MA-05-001 (ESPs); erst danach ist diese Regel real testbar.

## QoS/Retain (MA-02-003)

| Kategorie | Beispieltopics | QoS | Retain |
|---|---|---|---|
| Events (einmalig) | `actor/event/button`, `horn/state`-Flanken | QoS1 | nein |
| Online/State | `actor/status`, `sensor/status`, `pi1/status` | QoS1 | ja (Last Will ebenfalls retained, damit Offline-Zustand sofort sichtbar ist) |
| Commands | `actor/command`, `drive/command/*`, `horn/command` | QoS1, idempotent über `seq` | nein (Reconnect darf keinen alten Befehl erneut auslösen) |
| Telemetrie | `sensor/telemetry`, `drive/heartbeat` | QoS0 möglich | nein |

Begründung: Nicht-retained Commands verhindern, dass ein Reconnect automatisch die zuletzt gesendete Aktion erneut ausführt (Sicherheitsanforderung aus MA-06-002/MA-10-020). Retained Online/State-Topics erlauben sofortige Zustandsanzeige ohne auf die nächste Publikation warten zu müssen.
