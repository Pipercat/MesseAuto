"""MesseCar MQTT-Simulator (MA-08-001/MA-08-002).

Simuliert ESP Actor und ESP Sensor/Aux ueber echtes MQTT, damit Pi 1/Pi 2
ohne physische ESP-Hardware getestet werden koennen. Laeuft auf Pi 1
(broker nur ueber ap0/localhost erreichbar, siehe HARDWARE.md).

Normalbetrieb:
    python3 mqtt_simulator.py

Fehlerfaelle (MA-08-002):
    python3 mqtt_simulator.py --invalid-json      # sendet einmalig kaputtes JSON
    python3 mqtt_simulator.py --delayed-telemetry 5   # Telemetrie-Intervall kuenstlich verzoegert
    python3 mqtt_simulator.py --flap 10            # Broker-Verbindung alle 10s kappen/wiederherstellen
"""

from __future__ import annotations

import argparse
import json
import random
import threading
import time

import paho.mqtt.client as mqtt

BROKER_HOST = "127.0.0.1"
BROKER_PORT = 1883

BUTTON_FUNCTIONS = {
    1: "highBeam", 2: "lowBeam", 3: "underbody", 4: "indicatorLeft",
    5: "indicatorRight", 6: "hazard", 7: "fan",
}


def now_ms() -> int:
    return int(time.time() * 1000)


def make_client(client_id: str, status_topic: str) -> mqtt.Client:
    client = mqtt.Client(client_id=client_id, clean_session=True)
    will = json.dumps({"device": client_id, "status": "offline"})
    client.will_set(status_topic, will, qos=1, retain=True)
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=20)
    client.loop_start()
    return client


def publish_json(client: mqtt.Client, topic: str, payload: dict, retain: bool = False) -> None:
    client.publish(topic, json.dumps(payload), qos=1, retain=retain)


def simulate_actor(stop: threading.Event, flap_seconds: int | None) -> None:
    client = make_client("sim_esp_actor", "messecar/actor/status")
    publish_json(client, "messecar/actor/status", {"device": "esp_actor", "timestamp_ms": now_ms(), "status": "online"}, retain=True)
    state = {name: False for name in BUTTON_FUNCTIONS.values()}
    last_flap = time.time()

    while not stop.is_set():
        if flap_seconds and time.time() - last_flap > flap_seconds:
            print("[actor] simuliere Verbindungsabbruch...")
            client.disconnect()
            time.sleep(2)
            client = make_client("sim_esp_actor", "messecar/actor/status")
            publish_json(client, "messecar/actor/status", {"device": "esp_actor", "timestamp_ms": now_ms(), "status": "online"}, retain=True)
            last_flap = time.time()
            print("[actor] wieder verbunden")

        button = random.choice(list(BUTTON_FUNCTIONS))
        function = BUTTON_FUNCTIONS[button]
        publish_json(client, "messecar/actor/event/button", {"device": "esp_actor", "timestamp_ms": now_ms(), "button": button, "edge": "pressed"})
        state[function] = not state[function]
        publish_json(client, "messecar/actor/state", {"device": "esp_actor", "timestamp_ms": now_ms(), "outputs": state})
        publish_json(client, "messecar/actor/event/button", {"device": "esp_actor", "timestamp_ms": now_ms(), "button": button, "edge": "released"})
        stop.wait(random.uniform(2, 6))

    client.publish("messecar/actor/status", json.dumps({"device": "esp_actor", "timestamp_ms": now_ms(), "status": "offline"}), qos=1, retain=True)
    client.loop_stop()
    client.disconnect()


def simulate_sensor(stop: threading.Event, delayed_telemetry: float | None, send_invalid_json: bool) -> None:
    client = make_client("sim_esp_sensor_aux", "messecar/sensor/status")
    publish_json(client, "messecar/sensor/status", {"device": "esp_sensor_aux", "timestamp_ms": now_ms(), "status": "online"}, retain=True)

    if send_invalid_json:
        print("[sensor] sende einmalig ungueltiges JSON...")
        client.publish("messecar/sensor/telemetry", "{kaputt", qos=1)

    temperature = 22.0
    distance = 45.0
    interval = delayed_telemetry if delayed_telemetry else 1.0

    while not stop.is_set():
        temperature += random.uniform(-0.3, 0.3)
        distance += random.uniform(-2, 2)
        publish_json(client, "messecar/sensor/telemetry", {
            "device": "esp_sensor_aux",
            "timestamp_ms": now_ms(),
            "temperature_c": round(temperature, 1),
            "seat_distance_cm": round(max(2, min(400, distance)), 1),
        })
        stop.wait(interval)

    client.publish("messecar/sensor/status", json.dumps({"device": "esp_sensor_aux", "timestamp_ms": now_ms(), "status": "offline"}), qos=1, retain=True)
    client.loop_stop()
    client.disconnect()


def real_esp_online() -> list[str]:
    """Prueft kurz, ob ein echter ESP bereits auf denselben Topics online ist.

    Der Simulator nutzt bewusst dieselben Produktions-Topics wie die echte
    Firmware (testet damit den echten Pi-1/Pi-2-Code) - parallel zu echter
    Hardware wuerde er deren GPIO-Ausgaenge durch simulierte Tasterevents
    real umschalten.
    """

    found: list[str] = []

    def on_message(client, userdata, message):  # noqa: ANN001
        try:
            device = json.loads(message.payload).get("device")
        except (ValueError, AttributeError):
            return
        if device and not str(device).startswith("sim_"):
            found.append(device)

    checker = mqtt.Client(client_id="sim_precheck", clean_session=True)
    checker.on_message = on_message
    checker.connect(BROKER_HOST, BROKER_PORT, keepalive=5)
    checker.subscribe("messecar/actor/status", qos=1)
    checker.subscribe("messecar/sensor/status", qos=1)
    checker.loop_start()
    time.sleep(1.5)
    checker.loop_stop()
    checker.disconnect()
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--invalid-json", action="store_true", help="einmalig kaputtes JSON auf sensor/telemetry senden")
    parser.add_argument("--delayed-telemetry", type=float, default=None, help="Telemetrie-Intervall in Sekunden (statt 1 Hz)")
    parser.add_argument("--flap", type=int, default=None, help="Actor-Verbindung alle N Sekunden kappen/wiederherstellen")
    parser.add_argument("--force", action="store_true", help="trotz erkannter echter ESP-Hardware starten (nicht empfohlen)")
    args = parser.parse_args()

    if not args.force:
        online = real_esp_online()
        if online:
            print(f"ABBRUCH: echte ESP-Hardware bereits online ({', '.join(online)}).")
            print("Der Simulator wuerde real Taster-/Sensorereignisse auf denselben Topics erzeugen")
            print("und damit echte GPIO-Ausgaenge umschalten. ESP trennen oder --force verwenden.")
            return
        print("Kein echter ESP online erkannt, starte Simulator.")

    stop = threading.Event()
    threads = [
        threading.Thread(target=simulate_actor, args=(stop, args.flap), daemon=True),
        threading.Thread(target=simulate_sensor, args=(stop, args.delayed_telemetry, args.invalid_json), daemon=True),
    ]
    for t in threads:
        t.start()

    print("Simulator laeuft. Strg+C zum Beenden.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nBeende Simulator...")
        stop.set()
        for t in threads:
            t.join(timeout=5)


if __name__ == "__main__":
    main()
