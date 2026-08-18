# MesseAuto Datenbank-Pi 4

Dieses Paket ist für den zweiten Raspberry Pi gedacht. Es empfängt Ereignisse vom Fahrzeug-Pi, speichert sie in SQLite und zeigt eine lokale Auswertung auf dem Display an.

## Start auf dem Pi

```bash
cd /home/pi/datenbank-pi4
chmod +x install_pi.sh start.sh kiosk.sh
./install_pi.sh
sudo systemctl start messeauto-database.service
```

Dashboard:

```text
http://localhost:9000
```

Vom Fahrzeug-Pi aus:

```bash
MESSEAUTO_DATABASE_PI_URL=http://10.42.0.12:9000 ./start.sh
```

Im finalen Aufbau nutzt der Datenfluss die LAN-Verbindung:

- Datenbank-Pi `eth0`: `10.42.0.12`
- Pruefungs-Pi `eth0`: `10.42.0.11`
- WLAN bleibt nur fuer SSH/Programmierung.

## API

```http
POST /api/events
GET  /api/dashboard
GET  /health
```

Beispiel:

```bash
curl -X POST http://localhost:9000/api/events \
  -H "Content-Type: application/json" \
  -d '{"event_type":"sensor_measurement","payload":{"temperature_c":32.5,"seat_distance_mm":104,"seat_position":"middle","valid":true}}'
```

## Datenbank

Datei:

```text
vehicle_tests.db
```

Tabellen:

- `devices`
- `raw_events`
- `sensor_measurements`
- `seat_tests`
- `test_results`
- `errors`

## Messe-Datenfluss

Der Fahrzeug-Pi schreibt diese Ereignisse:

- `vehicle_heartbeat`: Fahrzeugstatus, aktive Ausgaenge, Motorwert, letzter Teststatus
- `actor_status`: ESP32-Aktorstatus, USB-Port, Protokoll, letzte Rohzeile
- `test_result`: automatische Licht-, Blinker-, Motor-, Luefter- und Gesamttests

Der Datenbank-Pi markiert sich bei Start und bei `/health` selbst als `database-pi connected`.
Wenn keine Sensorwerte vorliegen, zeigt das Dashboard bewusst `Kein Sensor-USB erkannt`.
