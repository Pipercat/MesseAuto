# MesseAuto – Aufgaben Adminübersicht / System Control

> **Status:** Nur geplant. Dieses Dokument definiert die Adminübersicht vollständig als Aufgabenpaket. Es wird durch das Anlegen dieser Aufgaben noch nichts implementiert.

## Ziel

Auf **Screen 1 / Raspberry Pi 1** soll ein Klick bzw. Tap auf das Logo oben rechts eine versteckte **Adminübersicht / Control Overview** öffnen.

Die normale Messe-/Fahrzeugoberfläche bleibt für Besucher einfach und aufgeräumt. Die Adminübersicht ist für Aufbau, Diagnose, Wartung und Tests gedacht und soll alle relevanten Systemdaten an einer Stelle anzeigen sowie sichere Verwaltungsaktionen anbieten.

```text
Screen 1 – normale Fahrzeugoberfläche
                  │
          Tap/Klick Logo oben rechts
                  │
                  ▼
        Adminübersicht / Control
                  │
      ┌───────────┼────────────┐
      │           │            │
    Pi 1        Pi 2        ESP32 #1/#2
  System       System       Status / WLAN
  Dienste      Dienste      MQTT / Sensoren
  GPIO         DB           Motor / Hupe
      │           │            │
      └───────────┼────────────┘
                  │
           Diagnose / Aktionen
```

---

# M12 – Adminübersicht und System Control

## M12.1 – Einstieg und Zugriff

- [ ] **MA-12-001 – Logo oben rechts als Admin-Einstieg definieren**
  - Auf Screen 1 bleibt das normale Pipercat-/MesseCar-Logo sichtbar.
  - Ein Tap/Klick auf das Logo öffnet die Adminübersicht.
  - Der Einstieg darf die normale Bedienung nicht stören.
  - Kein sichtbarer großer „Admin“-Button auf der normalen Messeoberfläche.
  - Abnahme: Navigation zur Adminübersicht ist eindeutig definiert und auf Touchscreen zuverlässig nutzbar.

- [ ] **MA-12-002 – Rückweg zur normalen Oberfläche definieren**
  - Adminübersicht erhält einen klaren „Zurück zum Fahrzeug“-Button.
  - Nach optional definierbarer Inaktivitätszeit soll automatisch zur normalen Oberfläche zurückgekehrt werden können.
  - Ein Seiten-Neuladen darf nicht versehentlich eine kritische Aktion erneut auslösen.
  - Abnahme: Adminmodus kann jederzeit sicher verlassen werden.

- [ ] **MA-12-003 – Schutz gegen versehentliche Adminaktionen planen**
  - Reine Diagnosewerte dürfen ohne weitere Bestätigung sichtbar sein.
  - Neustarts, Shutdowns und Service-Neustarts benötigen eine zusätzliche Bestätigung.
  - Bestätigungsdialog zeigt exakt Zielgerät und Aktion, z. B. `Raspberry Pi 2 neu starten`.
  - Kritische Aktionen niemals durch einen einzelnen unbestätigten Tap ausführen.
  - Optional später PIN-/Admin-Sperre vorsehen, falls die Messeumgebung dies verlangt.
  - Abnahme: keine kritische Aktion ist mit nur einem versehentlichen Tap ausführbar.

## M12.2 – Gesamtübersicht

- [ ] **MA-12-004 – System-Health-Übersicht für alle Geräte definieren**
  - Eigene Statuskarte für Raspberry Pi 1.
  - Eigene Statuskarte für Raspberry Pi 2.
  - Eigene Statuskarte für ESP32 Actor.
  - Eigene Statuskarte für ESP32 Sensor/Aux inklusive Hupe.
  - Status mindestens: `ONLINE`, `STALE`, `OFFLINE`, `ERROR`.
  - Letzter Kontakt / `last_seen` anzeigen.
  - Abnahme: innerhalb weniger Sekunden ist erkennbar, welches Gerät oder Teilsystem Probleme hat.

- [ ] **MA-12-005 – Ampel-/Statussystem festlegen**
  - `OK` = System vollständig funktionsfähig.
  - `WARNUNG` = Funktion eingeschränkt, aber System weiterhin bedienbar.
  - `FEHLER` = relevante Funktion ausgefallen.
  - `OFFLINE` = Gerät nicht erreichbar.
  - Jede Warnung muss zusätzlich Text enthalten; Farbe allein genügt nicht.
  - Abnahme: Status bleibt auch ohne Interpretation einzelner Rohdaten verständlich.

- [ ] **MA-12-006 – Gesamtstatus „MesseCar bereit“ definieren**
  - Aus den Einzelzuständen wird ein Gesamtstatus gebildet.
  - Beispiel:
    - `BEREIT` = alle für den Messebetrieb erforderlichen Kernsysteme online.
    - `EINGESCHRÄNKT` = Nebenfunktion wie Hupe/Sensor fehlt.
    - `NICHT BEREIT` = Pi 1, Motorsteuerung oder zentrale Kommunikation ausgefallen.
  - Die Einstufung muss später konfigurierbar sein, damit nicht jede Nebenfunktion den ganzen Messebetrieb blockiert.
  - Abnahme: ein Techniker sieht sofort, ob das Fahrzeug vorführbereit ist.

## M12.3 – Raspberry-Pi-Systemdaten

- [ ] **MA-12-007 – CPU-Auslastung aller Pis anzeigen**
  - Raspberry Pi 1 CPU-Gesamtauslastung in Prozent.
  - Raspberry Pi 2 CPU-Gesamtauslastung in Prozent.
  - Optional pro Core aufklappbar.
  - Aktuelle Werte plus kurze Verlaufshistorie vorsehen.
  - Abnahme: hohe Last ist unmittelbar sichtbar.

- [ ] **MA-12-008 – Arbeitsspeicher anzeigen**
  - Gesamt-RAM.
  - Belegter RAM.
  - Freier/verfügbarer RAM.
  - Prozentuale Auslastung.
  - Swap, sofern aktiv, separat anzeigen.
  - Abnahme: Speicherengpässe sind eindeutig erkennbar.

- [ ] **MA-12-009 – Datenträger/Speicher anzeigen**
  - Gesamtkapazität des Systemlaufwerks.
  - Belegter Speicher.
  - Freier Speicher.
  - Prozentuale Belegung.
  - Für Pi 2 zusätzlich Größe der Telemetrie-/SQLite-Datenbank anzeigen.
  - Warnschwellen vorsehen, z. B. Warnung ab 80 %, kritisch ab 90 %; finale Werte konfigurierbar halten.
  - Abnahme: drohender Speichermangel wird vor einem Ausfall sichtbar.

- [ ] **MA-12-010 – CPU-Temperatur und Thermal-Status anzeigen**
  - CPU-Temperatur beider Pis anzeigen.
  - Thermal-Throttling bzw. entsprechende Systemwarnung anzeigen, sofern verfügbar.
  - Temperaturwarnschwellen konfigurierbar halten.
  - Abnahme: Kühlungsprobleme sind in der Adminübersicht sofort sichtbar.

- [ ] **MA-12-011 – System-Uptime und Bootzeit anzeigen**
  - Uptime von Pi 1.
  - Uptime von Pi 2.
  - Zeitpunkt des letzten Systemstarts.
  - Optional Reboot-Grund anzeigen, sofern zuverlässig erfassbar.
  - Abnahme: spontane Neustarts können leichter erkannt werden.

- [ ] **MA-12-012 – Betriebssystem- und Softwareinformationen anzeigen**
  - Hostname.
  - Betriebssystem/Version.
  - Kernel-Version.
  - MesseCar-Softwareversion/Commit, sofern verfügbar.
  - Python-/Runtime-Version nur in Detailansicht.
  - Abnahme: bei Support ist eindeutig, welche Software auf welchem Pi läuft.

## M12.4 – Netzwerk und Funk

- [ ] **MA-12-013 – Netzwerkstatus von Pi 1 anzeigen**
  - IP-Adresse(n).
  - Ethernet verbunden/nicht verbunden.
  - WLAN/AP aktiv/nicht aktiv.
  - SSID des lokalen MesseCar-Netzes.
  - MQTT-Broker erreichbar/nicht erreichbar.
  - Abnahme: Netzwerkfehler können ohne SSH erkannt werden.

- [ ] **MA-12-014 – Netzwerkstatus von Pi 2 anzeigen**
  - IP-Adresse.
  - Verbindung zu Pi 1.
  - HTTP/API-Erreichbarkeit.
  - Round-Trip-/Antwortzeit als Diagnosewert.
  - Abnahme: klar sichtbar, ob Pi 2 selbst oder nur die Verbindung zu Pi 1 gestört ist.

- [ ] **MA-12-015 – ESP32-WLAN-Daten anzeigen**
  - ESP32 Actor: Online/Offline, RSSI, IP-Adresse, `last_seen`.
  - ESP32 Sensor/Aux: Online/Offline, RSSI, IP-Adresse, `last_seen`.
  - MQTT-Status pro ESP.
  - Optional Reconnect-Zähler und letzte Disconnect-Ursache.
  - Abnahme: Funkqualität und Verbindungsabbrüche sind diagnostizierbar.

- [ ] **MA-12-016 – Kommunikationslatenz sichtbar machen**
  - Pi 1 ↔ Pi 2 Latenz.
  - Pi 1 ↔ ESP Actor MQTT-Latenz, soweit sinnvoll messbar.
  - Pi 1 ↔ ESP Sensor/Aux MQTT-Latenz.
  - Für die Fahrmotorsteuerung separat aktuelle/typische Command-Latenz vorsehen.
  - Abnahme: Verzögerungen im Fahrbetrieb können von CPU-/Motorproblemen unterschieden werden.

## M12.5 – Dienste und Prozesse

- [ ] **MA-12-017 – Relevante Dienste von Pi 1 anzeigen**
  - MesseCar-Hauptanwendung.
  - Webserver/API.
  - MQTT-Client.
  - Mosquitto-Broker, falls auf Pi 1 betrieben.
  - WLAN-Access-Point-Dienst(e), sofern verwendet.
  - Dial-/Stepper-Service, falls später als eigener Dienst umgesetzt.
  - Status jeweils mindestens `RUNNING`, `STOPPED`, `FAILED`.
  - Abnahme: Dienstefehler sind ohne Terminalzugriff sichtbar.

- [ ] **MA-12-018 – Relevante Dienste von Pi 2 anzeigen**
  - Diagnose-/Collector-Anwendung.
  - Webserver.
  - SQLite-/Telemetrie-Collector-Zustand.
  - Letzter erfolgreicher Poll zu Pi 1.
  - Abnahme: Pi-2-Fehler sind eindeutig lokalisierbar.

- [ ] **MA-12-019 – Service-Neustart als Adminaktion planen**
  - Einzelne Dienste separat neu starten können.
  - Vor jedem Neustart Bestätigung erforderlich.
  - Ergebnis der Aktion anzeigen: erfolgreich/fehlgeschlagen.
  - Während Neustart Status `RESTARTING` anzeigen.
  - Abnahme: z. B. Webserver oder MQTT-Komponente kann neu gestartet werden, ohne den ganzen Pi neu zu booten.

## M12.6 – Geräte-Neustart und Shutdown

- [ ] **MA-12-020 – Raspberry Pi 1 Neustart planen**
  - Button `Pi 1 neu starten`.
  - Deutlicher Bestätigungsdialog.
  - Vor Neustart sichere Fahrzeugzustände herstellen.
  - Fahrmotor-Sollwert auf 0 setzen.
  - Hupe sicher aus.
  - Keine neuen Stepperbewegungen starten.
  - Anschließend geordneten OS-Reboot auslösen.
  - Abnahme: Pi 1 kann aus der Adminübersicht sicher neu gestartet werden.

- [ ] **MA-12-021 – Raspberry Pi 2 Neustart planen**
  - Button `Pi 2 neu starten`.
  - Bestätigung erforderlich.
  - Pi 1 und Fahrzeugsteuerung dürfen davon unbeeinflusst weiterlaufen.
  - Adminübersicht zeigt Pi 2 während des Reboots als `RESTARTING/OFFLINE` und erkennt den Reconnect automatisch.
  - Abnahme: Pi 2 kann separat gewartet werden.

- [ ] **MA-12-022 – Raspberry Pi Shutdown planen**
  - Pi 1 und Pi 2 separat herunterfahrbar.
  - Bei Pi 1 vorher Fahrzeug in sicheren Zustand bringen.
  - Deutlich zwischen `NEUSTART` und `HERUNTERFAHREN` unterscheiden.
  - Herunterfahren benötigt stärkere Bestätigung als ein Service-Neustart.
  - Abnahme: kein versehentliches Ausschalten im Messebetrieb.

- [ ] **MA-12-023 – ESP32 Neustart über Funk planen**
  - ESP32 Actor per MQTT-Admincommand neu startbar machen.
  - ESP32 Sensor/Aux per MQTT-Admincommand neu startbar machen.
  - Commands nicht retained.
  - Für Actor gilt vor Neustart: Fahrmotor sicher auf 0 und disabled.
  - Für Sensor/Aux gilt vor Neustart: Hupe aus.
  - Nach Neustart müssen beide Geräte automatisch wieder ins MesseCar-WLAN und MQTT verbinden.
  - Abnahme: ESPs können ohne USB-Zugriff neu gestartet werden.

- [ ] **MA-12-024 – „Alle Systeme neu starten“ bewusst NICHT als einfachen Button planen**
  - Kein ungeschützter One-Tap-Komplettreboot.
  - Falls später benötigt, nur als geführte Sequenz mit klarer Bestätigung und Reihenfolge.
  - Empfohlene Reihenfolge später definieren, damit Broker/AP nicht vorzeitig verschwindet.
  - Abnahme: eine Fehlbedienung kann nicht das komplette MesseCar mit einem Tap offline setzen.

## M12.7 – Fahrzeug- und Hardwarediagnose

- [ ] **MA-12-025 – GPIO-/Fahrzeugausgänge anzeigen**
  - Aktueller logischer Zustand von Unterbodenlicht, Abblendlicht, Fernlicht, Blinkern, Warnblinker und Lüfter.
  - Zugehörige BCM-GPIOs in Detailansicht.
  - Anzeigen, wann zuletzt ein Impuls ausgelöst wurde.
  - Adminseite darf nicht automatisch beim Öffnen GPIOs schalten.
  - Abnahme: Softwarezustand und reale Ausgangszuordnung sind nachvollziehbar.

- [ ] **MA-12-026 – Motorisierte Drehregler diagnostizieren**
  - Fahrtrichtungsregler: Istwinkel, Sollwinkel, Zustand, Hall-Sensorstatus, Stepperstatus.
  - Geschwindigkeitsregler: Istwinkel, Sollwinkel, Prozentwert, Zustand, Hall-Sensorstatus, Stepperstatus.
  - TCA9548A-/I²C-Status anzeigen.
  - Kalibrierstatus anzeigen.
  - Fehler wie `SENSOR_MISSING`, `NO_MOVEMENT`, `TARGET_TIMEOUT` sichtbar machen.
  - Abnahme: Reglerprobleme sind ohne Debug-Konsole eingrenzbar.

- [ ] **MA-12-027 – Fahrmotorstatus anzeigen**
  - ESP Actor online/offline.
  - Sollrichtung.
  - Sollgeschwindigkeit.
  - tatsächlich angewandter Motorzustand, soweit rückgemeldet.
  - Heartbeat-Alter.
  - Fail-Safe aktiv/inaktiv.
  - Letzte Sequenznummer.
  - Abnahme: klar sichtbar, ob Pi und ESP denselben Fahrzustand sehen.

- [ ] **MA-12-028 – Sensorwerte zentral anzeigen**
  - Temperatur.
  - Sitzabstand/Sitzposition.
  - Sensorfehlerstatus.
  - Zeit seit letzter gültiger Messung.
  - Rohwert optional in Detailansicht.
  - Abnahme: Sensorik kann direkt auf Screen 1 geprüft werden.

- [ ] **MA-12-029 – Hupenstatus anzeigen**
  - Sensor/Aux-ESP online/offline.
  - Hupe aktuell aktiv/inaktiv.
  - Letzter Hupencommand.
  - Keepalive-/Timeout-Status.
  - Audio-/Verstärkerstatus soweit softwareseitig diagnostizierbar.
  - Abnahme: erkennbar, ob ein Hupenproblem aus Netzwerk, ESP oder Audiosektion stammt.

## M12.8 – Testfunktionen

- [ ] **MA-12-030 – Admin-Testbereich definieren**
  - Separate Sektion `Tests` innerhalb der Adminübersicht.
  - Tests niemals automatisch beim Öffnen starten.
  - Jeder Test zeigt Ziel, erwartetes Verhalten und Ergebnis.
  - Bestehende Pi-2-Testlogik nach Möglichkeit wiederverwenden statt duplizieren.
  - Abnahme: Wartungstests sind klar vom normalen Fahrzeugbetrieb getrennt.

- [ ] **MA-12-031 – Licht- und Blinker-Einzeltests integrieren**
  - Abblendlicht.
  - Fernlicht.
  - Unterboden.
  - Blinker links.
  - Blinker rechts.
  - Warnblinker.
  - Testbuttons müssen dieselbe sichere Backendlogik wie normale Bedienung nutzen.
  - Abnahme: einzelne Fahrzeugfunktionen können kontrolliert getestet werden.

- [ ] **MA-12-032 – Lüftertest integrieren**
  - Lüfter gezielt testbar.
  - Zustand und Rückmeldung anzeigen.
  - Nach Test klar definierten Endzustand herstellen.
  - Abnahme: Lüfter kann isoliert geprüft werden.

- [ ] **MA-12-033 – Drehregler-Selbsttest planen**
  - Hall-Sensoren lesen.
  - Magnetstatus prüfen.
  - Kleine kontrollierte Stepperbewegung je Regler.
  - Rückmeldung prüfen, ob sich Hall-Winkel passend verändert.
  - Test darf den Fahrmotor nicht aktivieren.
  - Abnahme: mechanischer Regleraufbau kann unabhängig vom Fahrantrieb geprüft werden.

- [ ] **MA-12-034 – Hupentest integrieren**
  - Kurzer definierter Testton/Hupenimpuls.
  - Maximale Testdauer begrenzen.
  - Stop/Failsafe muss auch im Test greifen.
  - Abnahme: Hupe kann aus der Adminübersicht geprüft werden, ohne dauerhaft hängen zu bleiben.

- [ ] **MA-12-035 – Fahrmotor-Testmodus streng getrennt planen**
  - Nicht als normaler One-Tap-Test bereitstellen.
  - Nur bei explizitem Admin-Testmodus.
  - Geschwindigkeit für Diagnose begrenzen.
  - Richtungswechsel nur im Stillstand.
  - Deutliche Warnung im UI.
  - Not-Aus/Stop während des Tests immer sichtbar.
  - Abnahme: Motor kann später sicher diagnostiziert werden, ohne versehentlich volle Leistung auszulösen.

## M12.9 – Logs und Fehlerdiagnose

- [ ] **MA-12-036 – Zentrale Ereignis-/Fehlerliste anzeigen**
  - Letzte Systemfehler chronologisch.
  - Quelle: Pi 1, Pi 2, ESP Actor, ESP Sensor/Aux.
  - Zeitstempel.
  - Schweregrad: Info/Warnung/Fehler/Kritisch.
  - Fehlercode plus verständlicher Text.
  - Abnahme: Techniker muss nicht mehrere Logdateien durchsuchen, um die letzte Störung zu finden.

- [ ] **MA-12-037 – Relevante Logs begrenzt im UI anzeigen**
  - Letzte N Logzeilen pro Dienst/Gerät.
  - Keine unbegrenzten Logs in den Browser laden.
  - Filter nach Quelle und Fehlerstufe.
  - Automatische Aktualisierung ohne die UI zu blockieren.
  - Abnahme: schnelle Diagnose direkt am Fahrzeug möglich.

- [ ] **MA-12-038 – Kommunikationsereignisse protokollieren**
  - MQTT connect/disconnect.
  - ESP reconnect.
  - Pi-2-Verbindungsverlust.
  - Drive-Failsafe ausgelöst.
  - Horn-Failsafe ausgelöst.
  - Serial-Fallback aktiviert/deaktiviert.
  - Abnahme: Kommunikationsprobleme lassen sich zeitlich nachvollziehen.

## M12.10 – Admin-Backend/API

- [ ] **MA-12-039 – Einheitliches Admin-Status-API planen**
  - Pi 1 stellt einen aggregierten Adminstatus bereit.
  - Werte aus Pi 1 lokal erfassen.
  - Pi-2-Werte über definierte Systemstatus-API beziehen.
  - ESP-Werte über MQTT-Status/Telemetrie beziehen.
  - API trennt Diagnosewerte von Verwaltungsaktionen.
  - Abnahme: Frontend benötigt keine direkten SSH-/Shell-Zugriffe.

- [ ] **MA-12-040 – Admin-Aktions-API planen**
  - Separate Endpunkte/Aktionen für Service-Restart, Reboot, Shutdown und ESP-Reboot.
  - Keine beliebigen Shellcommands vom Browser akzeptieren.
  - Nur explizit erlaubte Aktionen als Whitelist.
  - Parameter validieren.
  - Jede Aktion protokollieren.
  - Abnahme: Adminübersicht kann niemals als allgemeine Remote-Shell missbraucht werden.

- [ ] **MA-12-041 – Berechtigungskonzept für privilegierte Systemaktionen definieren**
  - Webanwendung nicht pauschal als root betreiben.
  - Nur exakt benötigte Systemaktionen privilegieren.
  - Für systemd/reboot/shutdown ein eng begrenztes Konzept vorsehen.
  - Keine frei zusammensetzbaren `sudo`-Befehle aus HTTP-Daten.
  - Abnahme: minimale notwendige Rechte statt Vollzugriff.

## M12.11 – UI-Design

- [ ] **MA-12-042 – Adminübersicht für 1920×1080 Touchscreen gestalten**
  - Professionelles technisches Layout passend zur normalen MesseCar-Oberfläche.
  - Große touchfähige Elemente.
  - Hauptstatus ohne Scrollen sichtbar.
  - Detailbereiche dürfen scrollen oder auf Unterseiten liegen.
  - Keine winzigen Desktop-Admin-Tabellen.
  - Abnahme: aus ca. 1–2 m Entfernung sind Kernzustände lesbar.

- [ ] **MA-12-043 – Empfohlene Hauptbereiche der Adminseite festlegen**
  - `Übersicht`
  - `Geräte`
  - `Fahrzeug`
  - `Netzwerk`
  - `Dienste`
  - `Tests`
  - `Logs`
  - `Systemaktionen`
  - Navigation bevorzugt als große Tabs/Kacheln.
  - Abnahme: Funktionen sind logisch gruppiert und innerhalb weniger Taps erreichbar.

- [ ] **MA-12-044 – Live-Aktualisierung ohne komplettes Reload planen**
  - Systemmetriken automatisch aktualisieren.
  - Schnelle Fahrzeug-/Kommunikationswerte häufiger aktualisieren als Speicher/Uptime.
  - Beispielziel:
    - Fahr-/ESP-Status: ca. 2–5 Hz.
    - CPU/RAM/Temperatur: ca. 1 Hz.
    - Speicher/Uptime/Versionen: alle 5–10 s ausreichend.
  - Aktualisierung darf Pi 1 nicht unnötig belasten.
  - Abnahme: Adminseite wirkt live, ohne selbst zum Performanceproblem zu werden.

## M12.12 – Performance und Verlauf

- [ ] **MA-12-045 – Kurze Performance-Historie vorsehen**
  - CPU-Auslastung.
  - RAM-Auslastung.
  - CPU-Temperatur.
  - Netzwerk-/MQTT-Latenz.
  - Nur kurze Diagnosehistorie für die Oberfläche, z. B. letzte 5–15 Minuten.
  - Keine unnötig große Datenbank auf Pi 1 erzeugen.
  - Abnahme: Lastspitzen lassen sich erkennen, ohne ein vollwertiges Monitoring-System zu bauen.

- [ ] **MA-12-046 – Ressourcengrenzen und Warnungen definieren**
  - CPU dauerhaft hoch.
  - RAM knapp.
  - Speicher knapp.
  - CPU-Temperatur hoch.
  - MQTT-Latenz zu hoch.
  - ESP-RSSI schwach.
  - Telemetrie veraltet.
  - Schwellenwerte konfigurierbar halten.
  - Abnahme: Probleme werden proaktiv als Warnung angezeigt.

## M12.13 – Start-/Bootverhalten

- [ ] **MA-12-047 – Bootstatus in Adminübersicht abbilden**
  - Nach Start von Pi 1 einzelne Komponenten nacheinander als `STARTING`/`ONLINE` anzeigen.
  - Pi 2 und ESPs dürfen später online kommen, ohne Fehlzustände dauerhaft festzuschreiben.
  - Während Boot kein alter retained Fahr-/Hupencommand aktiviert werden.
  - Abnahme: Startsequenz ist für den Techniker nachvollziehbar.

- [ ] **MA-12-048 – Recovery nach Geräte-Reboot definieren**
  - Adminseite erkennt Reboot eines Geräts automatisch.
  - Status durchläuft `RESTARTING/OFFLINE/ONLINE`.
  - Alte Warnungen werden nach erfolgreichem Recovery entsprechend abgeschlossen, nicht einfach unsichtbar gelöscht.
  - Abnahme: Neustarts lassen sich vollständig von der Adminseite verfolgen.

## M12.14 – Simulation und Tests

- [ ] **MA-12-049 – Adminübersicht in PC-Simulation vorsehen**
  - Simulierte CPU-/RAM-/Speicherwerte.
  - Geräte online/offline schaltbar.
  - Dienstefehler simulierbar.
  - MQTT-Latenz und RSSI simulierbar.
  - Reboot-/Restart-Aktionen simulieren, ohne Host-PC tatsächlich neu zu starten.
  - Abnahme: Adminseite kann ohne Fahrzeughardware entwickelt und getestet werden.

- [ ] **MA-12-050 – Sicherheits- und Fehlbedienungstests definieren**
  - Mehrfachklick auf Reboot.
  - Browser-Reload während Aktion.
  - Pi 2 offline bei Neustartversuch.
  - ESP offline bei Rebootcommand.
  - MQTT-Ausfall während Adminaktion.
  - Motor läuft bei angefordertem Pi-1-Reboot.
  - Hupe aktiv bei angefordertem Sensor/Aux-ESP-Reboot.
  - Abnahme: jede kritische Aktion endet definiert und sicher.

---

# Definition of Done – Adminübersicht

Die Adminübersicht gilt erst als fertig umgesetzt, wenn:

1. das Logo oben rechts auf Screen 1 zuverlässig zur Adminübersicht führt,
2. Pi 1, Pi 2 und beide ESP32 mit Online-/Fehlerstatus sichtbar sind,
3. CPU, RAM, Speicher, Temperatur und Uptime beider Pis angezeigt werden,
4. Netzwerk-, MQTT- und Kommunikationszustände sichtbar sind,
5. Fahrmotor, Drehregler, Sensorik, GPIO-Funktionen und Hupe diagnostizierbar sind,
6. relevante Dienste angezeigt und kontrolliert neu gestartet werden können,
7. Pi 1 und Pi 2 einzeln sicher rebootet und heruntergefahren werden können,
8. beide ESP32 sicher über Funk neu gestartet werden können,
9. kritische Aktionen bestätigt, geloggt und gegen versehentliche Mehrfachausführung geschützt sind,
10. vor Pi-1-/Actor-Reboots der Fahrmotor sicher auf 0 geht und vor Aux-ESP-Reboot die Hupe sicher aus ist,
11. keine beliebigen Shellcommands vom Browser ausgeführt werden können,
12. die Oberfläche auf dem 1920×1080-Touchscreen professionell und schnell bedienbar ist,
13. Fehlerfälle und Neustarts in Simulation und Hardwaretests geprüft wurden,
14. die normale Messeoberfläche durch die Adminfunktionen nicht unnötig komplizierter wird.
