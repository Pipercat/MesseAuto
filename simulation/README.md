# MesseAuto PC-Simulation

In diesem Ordner befindet sich die komplette Standalone-Simulation des MesseAuto-Systems.

## Starten

1. Datei `MesseAuto_Simulation.html` herunterladen oder das Repository klonen.
2. Die Datei per Doppelklick in Chrome, Edge oder Firefox öffnen.
3. Es ist keine Installation und kein lokaler Server nötig.

## Simulierte Geräte

### ESP32 Aktorik

- 10 Fahrzeugtaster
- Fernlicht
- Abblendlicht
- Unterbodenbeleuchtung / NeoPixel
- Blinker links
- Blinker rechts
- Warnblinker
- Lüfter
- Reserve-Taster 8 bis 10
- simulierte serielle JSON-Ausgabe

### ESP32 Sensorik

- Temperatur per Schieberegler
- Sitzabstand per Schieberegler
- automatische Sitzposition vorne / mitte / hinten
- simulierbarer Sensorfehler
- simulierte serielle JSON-Ausgabe

### Raspberry Pi 1

- Hauptsteuerung
- API-Status
- ESP32-Verbindungsstatus
- GPIO-Tabelle
- simulierte 200-ms-Impulse
- API-Aufrufe und Systemzustand

### Raspberry Pi 2

- Telemetrie-Collector
- Polling von Pi 1
- simulierte SQLite-Datenbank
- Datensatz-Zähler
- letzte Sensorwerte

## Virtuelles Fahrzeug

In der Mitte werden die Aktoren direkt sichtbar dargestellt:

- Abblendlicht und Fernlicht
- linke und rechte Blinker
- Warnblinker
- Unterbodenbeleuchtung
- NeoPixel-Effekt
- drehender Lüfter
- Temperatur
- Sitzposition
- Anzahl aktiver Funktionen

## Auto-Demo

Mit `Auto-Demo starten` läuft automatisch ein kompletter Test mit Licht, Unterbodenbeleuchtung, Blinkern, Warnblinker, Lüfter und geänderten Sensorwerten durch.

## Wichtig

Die Simulation verändert keine echte Hardware. Sie bildet die Zustände und Kommunikationswege der aktuellen MesseAuto-Software im Browser nach.