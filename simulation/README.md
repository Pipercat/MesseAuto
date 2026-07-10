# MesseAuto PC-Simulation

Die Simulation bildet das MesseAuto jetzt mit **drei getrennten Bildschirmen** nach. Dadurch kannst du jeden Raspberry-Pi-Bildschirm separat und zusätzlich einen eigenen ESP-Hardware-Prüfstand öffnen.

## Start

Öffne:

```text
simulation/index.html
```

Danach kannst du einzeln starten:

1. `pi1-screen.html` – Raspberry Pi 1 / Fahrzeugsteuerung
2. `pi2-screen.html` – Raspberry Pi 2 / Test und Diagnose
3. `esp-testbench.html` – beide ESP32, Taster, Sensoren und Aktoren

Über **Alle drei Simulationsfenster öffnen** werden die drei Ansichten in getrennten Browserfenstern gestartet.

## Wichtig: gemeinsame Simulation

Alle drei Fenster benutzen denselben simulierten Fahrzeugzustand über den Browser-Speicher.

Beispiel:

```text
ESP-Prüfstand
Taster 1 drücken
      ↓
ESP32 Actor schaltet Fernlicht
      ↓
Pi 1 zeigt Fernlicht am Fahrzeug
      ↓
Pi 2 zeigt den aktiven Ausgang
      ↓
Telemetrie und Protokoll werden aktualisiert
```

Eine Änderung in einem Fenster ist damit sofort in den anderen Fenstern sichtbar.

## Raspberry Pi 1

Der Pi-1-Screen ist als 1920×1080-Touchoberfläche aufgebaut und enthält:

- eigene Fahrzeugsteuerung
- Abblendlicht
- Fernlicht
- Unterbodenbeleuchtung
- Blinker links und rechts
- Warnblinker
- Lüfter
- große Fahrzeugdarstellung
- Live-Temperatur
- Live-Sitzabstand
- Sitzposition
- ESP-Verbindungsstatus
- aktuellen Ausgangsstatus

## Raspberry Pi 2

Der Pi-2-Screen enthält:

- Lichttest
- Blinkertest
- Lüftertest
- Sensortest
- Gesamtfahrzeugtest
- Alles-aus-Funktion
- Live-Fahrzeugdarstellung
- ESP-Verbindungsstatus
- Telemetrie-Datensätze
- simuliertes 1-Sekunden-Polling
- Systemprotokoll

## ESP-Hardware-Prüfstand

Der ESP-Screen enthält die Hardware, die bei einer echten Simulation von außen bedient werden soll.

### ESP32 Actor

- Taster 1: Fernlicht, GPIO 33
- Taster 2: Abblendlicht, GPIO 15
- Taster 3: Unterbodenbeleuchtung, GPIO 25
- Taster 4: Blinker links, GPIO 35
- Taster 5: Blinker rechts, GPIO 14
- Taster 6: Warnblinker, GPIO 27
- Taster 7: Lüfter, GPIO 34
- Taster 8 bis 10: Reserve

### ESP32 Sensor

- Temperatur-Regler
- Sitzabstand-Regler
- Sensorfehler-Schalter
- simulierte serielle JSON-Ausgabe

### Aktoren

- sichtbarer Scheinwerfer
- NeoPixel-/Unterbodenanzeige
- drehender Lüfter
- ESP-Verbindungsleitungen
- Live-Ereignisprotokoll

## Dateien

```text
simulation/
├── index.html
├── pi1-screen.html
├── pi2-screen.html
├── esp-testbench.html
├── MesseAuto_Simulation.html
├── README.md
└── shared/
    ├── simulation.js
    └── style.css
```

Die alte Datei `MesseAuto_Simulation.html` dient nur noch als Weiterleitung auf den neuen Startbildschirm.

## Hinweis

Im aktuellen Repository waren keine bereits fertigen originalen Pi-Display-Dateien vorhanden. Die beiden Pi-Ansichten sind deshalb anhand der bisherigen MesseAuto-Anforderungen als getrennte 1920×1080-Touchscreens aufgebaut. Sobald die echten Original-Screen-Dateien im Repo liegen, können die Simulationsansichten pixelgenau daran angepasst werden.