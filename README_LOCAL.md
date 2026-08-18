# MesseAuto

Interaktives Demonstrationsfahrzeug zur digitalen Fahrzeugsteuerung.

Das Projekt besteht aus zwei Raspberry Pis und optionalen ESP32-Mikrocontrollern:

- Display 1 / Fahrzeug-Pi (`messepi`): Touchscreen, Fahrzeuglogik, GPIO-Impulsrelais und Motor-PWM.
- Display 2 / Datenbank-Pi (`messedata`): SQLite-Datenbank, Live-Dashboard, Testprotokolle und Diagnose.
- ESP32-Aktor: einmal per PC/Mac flashen, danach standalone im Fahrzeug einstecken; keine Pi-Serial-Verbindung im Messebetrieb.
- ESP32-Sensorik: vorbereitet fuer Temperatur, Sitzabstand, Sitzposition und spaetere Sensoren.

## Live-System

| System | Nutzer | Dienst | URL |
| --- | --- | --- | --- |
| Fahrzeug-Pi | `messepi` | `messeauto.service` | `http://127.0.0.1:8000/?screen=home` |
| Datenbank-Pi | `messedata` | `messeauto-database.service` | `http://127.0.0.1:9000/` |

LAN zwischen den Pis:

- Fahrzeug-/Pruefungs-Pi `eth0`: `10.42.0.11`
- Datenbank-Pi `eth0`: `10.42.0.12`
- Datenfluss Fahrzeug -> Datenbank: `http://10.42.0.12:9000`
- WLAN bleibt fuer SSH/Programmierung; die Pi-zu-Pi-Verbindung laeuft ueber LAN.

Auf beiden Desktops liegt `MesseAuto starten.desktop`. Doppelklick startet den
jeweiligen systemd-Dienst neu und oeffnet genau ein Chromium-Kioskfenster auf
der passenden Display-URL.

Der Fahrzeug-Pi sendet periodisch `vehicle_heartbeat`, `actor_status` und Testresultate an den Datenbank-Pi.
`esp32_actor` wird im Normalbetrieb als `standalone` gemeldet, weil der Pi keinen ESP-USB-Port oeffnet.

## Abnahme

Der schnelle Check laeuft vom Mac aus:

```bash
/Users/marvinmayer/Desktop/MesseAuto/scripts/validate_messeauto.sh
```

Danach auf Display 1 alle Ansichten pruefen:

- Home
- Fahrzeug
- Tests
- Pi & Relais

Display 1 muss am Ende wieder auf `/?screen=home` stehen. Display 2 bleibt auf `/`.

## ESP32

Finaler Messestand:

- Keine laufende serielle Verbindung zwischen Fahrzeug-Pi und ESP32.
- Der Fahrzeug-Pi gibt kurze GPIO-Impulse auf Relais.
- Die Relaiskontakte liegen parallel zu den echten Buttons auf den ESP32-Buttonpins.
- Der ESP32 sieht dadurch einen normalen Buttondruck und schaltet den Aktor.
- Der ESP32 wird nur vom PC/Mac aus geflasht und danach im Fahrzeug eingesteckt.

Flashen vom Mac/PC:

```bash
cd /Users/marvinmayer/Desktop/MesseAuto/esp32-codes
./flash_actor_from_pc.sh /dev/cu.SLAB_USBtoUART
```

Der aktive Aktor-Sketch ist `esp32-codes/esp32_actor/esp32_actor.ino`. Er nutzt
die Buttonpins `33, 15, 25, 35, 14, 27, 34, 13, 26, 32`; LOW bedeutet gedrueckt.
GPIO34 und GPIO35 brauchen externe Pullups oder eine vorhandene Button-Platine
mit Pullup.
