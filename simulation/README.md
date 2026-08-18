# MesseCar MQTT-Simulator

Simuliert ESP Actor und ESP Sensor/Aux über echtes MQTT (Online-Status inkl. Last-Will, Button-Events, Actor-State, Sensor-Telemetrie), damit Pi 1 und Pi 2 ohne physische ESP-Hardware getestet werden können (MA-08-001).

Der Broker (Mosquitto auf Pi 1) ist nur über `ap0`/`localhost` erreichbar — das Skript muss deshalb **auf Pi 1** laufen.

```bash
python3 simulation/mqtt_simulator.py
```

## Fehlerfälle simulieren (MA-08-002)

```bash
python3 simulation/mqtt_simulator.py --invalid-json         # kaputtes JSON auf sensor/telemetry
python3 simulation/mqtt_simulator.py --delayed-telemetry 5  # Telemetrie alle 5s statt 1 Hz
python3 simulation/mqtt_simulator.py --flap 10               # Actor-Verbindung alle 10s kappen/wiederherstellen
```

Vorherige Datei-basierte Browser-Simulation (localStorage, drei HTML-Fenster) wurde entfernt: Die HTML-Einstiegspunkte waren leer (0 Byte) und bildeten die inzwischen überholte Vor-MQTT-Architektur ab.
