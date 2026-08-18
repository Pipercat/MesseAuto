# MesseAuto – Aufgaben: Fahrzeughupe am zweiten ESP32

> **Status: Nur geplant.** Dieses Dokument definiert ausschließlich neue Aufgaben. Durch das Anlegen dieser Aufgaben wird noch keine Hupe implementiert, keine GPIO-Belegung geändert und kein bestehender ESP-Code angepasst.

## Ziel

Am zweiten ESP32, der ebenfalls in das lokale MesseCar-WLAN eingebunden werden soll, befindet sich ein kleines Lautsprecher-/Verstärkermodul. Dieses soll später als realistische Fahrzeughupe dienen.

Der Raspberry Pi 1 ist die Bedien- und Sollwertquelle. Die Hupe soll vom Touchscreen ausgelöst werden können. Der Pi überträgt dabei **keine Audiodaten**, sondern nur einen zeitkritischen Hupenbefehl über das lokale WLAN/MQTT. Der zweite ESP32 erzeugt bzw. spielt den Hupenton lokal ab und gibt das Audiosignal an das vorhandene PAM8406-Verstärkermodul weiter.

Grundprinzip:

```text
Touchscreen
    │
    ▼
Raspberry Pi 1
    │
    │ WLAN / MQTT
    ▼
ESP32 #2 (Sensor/Aux)
    │
    ├─ lokale Hupenton-Erzeugung / Sample-Wiedergabe
    │
    ▼
PAM8406 Audioverstärker
    │
    ▼
Lautsprecher
```

Die bestehende USB-Sicherheitsregel bleibt unverändert: Zwischen Raspberry Pi und ESP32 wird im realen MesseCar keine dauerhafte USB-Datenverbindung benötigt.

---

# M11 – Fahrzeughupe über ESP32 #2

## M11.1 – Hardware und Audio-Pfad festlegen

- [ ] **MA-11-001 – Zweiten ESP32 als Sensor-/Aux-Controller definieren**
  - Der bisherige zweite ESP32 bleibt für Temperatur- und Abstandssensorik zuständig.
  - Zusätzlich übernimmt er später die lokale Hupenfunktion.
  - Arbeitsbezeichnung im System: `esp32_sensor_aux` oder technisch gleichwertige eindeutige Bezeichnung.
  - Bestehende Sensorfunktionen dürfen durch Audioausgabe nicht blockiert oder zeitlich unzuverlässig werden.
  - Abnahme: Rolle des zweiten ESP ist eindeutig dokumentiert, bevor Code geändert wird.

- [ ] **MA-11-002 – Exakten ESP32-Boardtyp des zweiten ESP bestimmen**
  - Vor Implementierung den tatsächlich verbauten ESP32-Typ dokumentieren.
  - Prüfen, ob der konkrete ESP einen internen DAC besitzt oder ob für Audio I2S/PWM bzw. zusätzliche Audio-Hardware benötigt wird.
  - Keine GPIO-Belegung raten oder vorab fest eintragen.
  - Bestehende Pins für DS18B20 und Abstandssensor berücksichtigen.
  - Abnahme: Boardtyp, verfügbare Audioausgabe und konfliktfreie Pins sind festgelegt.

- [ ] **MA-11-003 – Vorhandenes PAM8406-Modul elektrisch dokumentieren**
  - PAM8406 als Audio-Leistungsverstärker behandeln, nicht als eigenständigen Tongenerator.
  - Versorgung des vorhandenen Moduls prüfen und dokumentieren.
  - Zielversorgung nur innerhalb der zulässigen Modulspannung vorsehen.
  - Audioeingang des PAM8406 muss von einem geeigneten ESP-Audiosignal gespeist werden; Lautsprecher niemals direkt aus einem normalen ESP-GPIO treiben.
  - Lautsprecherimpedanz und Belastbarkeit des vorhandenen Lautsprechers erfassen.
  - Masseführung innerhalb der ESP-/Audioseite dokumentieren; keine neue elektrische Verbindung zum Raspberry Pi erzeugen.
  - Abnahme: Versorgung, Audioeingang, Ausgang und Lautsprecher sind eindeutig dokumentiert.

- [ ] **MA-11-004 – Audioausgabe zwischen ESP und PAM8406 festlegen**
  - Bevorzugte Varianten in dieser Reihenfolge prüfen:
    1. interner DAC des konkreten ESP32, falls vorhanden und ausreichend,
    2. I2S-Audio über geeigneten DAC/Codec,
    3. gefilterte PWM nur wenn Qualität und Hardware dafür ausreichend sind.
  - Auswahl nach vorhandenem ESP32, verfügbarer Hardware und gewünschter Hupenqualität treffen.
  - Die endgültige Variante erst nach einem kurzen Hardwaretest festschreiben.
  - Abnahme: definierter Audio-Pfad erzeugt am PAM8406 ein sauberes Signal ohne gefährliche Pegel.

## M11.2 – Hupenton definieren

- [ ] **MA-11-005 – Art des Fahrzeug-Hupentons festlegen**
  - Ziel ist ein glaubwürdiger Fahrzeug-Hupenton, kein einfacher PC-Piepton.
  - Prüfen, ob ein kurzer lokaler WAV/PCM-Sample im Flash des ESP gespeichert oder der Ton synthetisch erzeugt wird.
  - Bevorzugt lokale Sample-Wiedergabe, falls Speicher und Audioausgabe dies sinnvoll erlauben.
  - Sound muss in einer Endlosschleife oder nahtlos wiederholbar sein, solange die Hupe gedrückt wird.
  - Lautstärke so begrenzen, dass PAM8406 und Lautsprecher nicht übersteuert werden.
  - Abnahme: Klangquelle, Format, Samplerate und maximale Lautstärke sind vor Implementierung definiert.

- [ ] **MA-11-006 – Start-/Stop-Verhalten der Hupe festlegen**
  - Hupe verhält sich wie eine echte Fahrzeughupe: nur aktiv, solange der Benutzer den Hupenbutton gedrückt hält.
  - `press` startet die Hupe ohne bewusst wahrnehmbare Verzögerung.
  - `release` beendet sie unmittelbar.
  - Keine Toggle-Logik verwenden.
  - Mehrfach empfangene gleiche Zustände müssen idempotent sein.
  - Abnahme: gedrückt = Hupe aktiv; losgelassen = Hupe aus.

## M11.3 – MQTT-Protokoll für die Hupe

- [ ] **MA-11-007 – MQTT-Topic für Hupenbefehle definieren**
  - Neues Topic: `messecar/horn/command`.
  - Befehl ist absoluter Zustand, kein Toggle.
  - Payload enthält mindestens `device`, `seq`, `timestamp_ms` und `active`.
  - Beispiel:

    ```json
    {"device":"pi1","seq":2201,"timestamp_ms":123456,"active":true}
    ```

  - `active=false` beendet die Hupe.
  - Commands nicht retained publizieren.
  - Abnahme: Topic und Payload sind eindeutig und widerspruchsfrei mit dem restlichen MQTT-System.

- [ ] **MA-11-008 – MQTT-Status der Hupe definieren**
  - Neues Topic: `messecar/horn/state`.
  - ESP meldet den tatsächlich angewendeten Zustand zurück.
  - Payload mindestens: `device`, `timestamp_ms`, `active`, `audio_ok`, optional `rssi` und Fehlercode.
  - Beispiel:

    ```json
    {"device":"esp32_sensor_aux","timestamp_ms":123470,"active":true,"audio_ok":true,"rssi":-49}
    ```

  - Abnahme: Pi kann unterscheiden zwischen angefordertem und tatsächlich bestätigtem Hupenzustand.

- [ ] **MA-11-009 – Hupen-Latenzanforderung festlegen**
  - Pi darf keine Audiodaten über WLAN streamen.
  - Der ESP muss den Ton vollständig lokal erzeugen/abspielen.
  - Ziel: MQTT-Publish unmittelbar nach Touch-Ereignis.
  - Ziel für typische lokale WLAN-Reaktion vom Screen bis Audio-Start: unter 100 ms.
  - Audioverarbeitung auf dem ESP darf MQTT und Sensorik nicht blockieren.
  - Abnahme: Bedienung fühlt sich wie eine direkte Hupe an und nicht wie verzögerte Medienwiedergabe.

## M11.4 – Sicherheitslogik gegen eine hängenbleibende Hupe

- [ ] **MA-11-010 – Hupen-Lease/Keepalive implementierbar planen**
  - Ein verlorenes `release`-Paket darf nicht dazu führen, dass die Hupe dauerhaft weiterläuft.
  - Während der Benutzer den Button hält, sendet Pi 1 regelmäßig `active=true` als Keepalive.
  - Zielrate zunächst 10 Hz / alle 100 ms.
  - ESP erneuert bei jedem gültigen `active=true` die Hupen-Lease.
  - Wird die Lease nicht rechtzeitig erneuert, schaltet der ESP die Hupe selbstständig ab.
  - Ziel-Timeout zunächst 300 ms, später im Hardwaretest feinabstimmen.
  - Abnahme: Unterbrechen von WLAN oder MQTT bei gedrückter Hupe führt automatisch zum Verstummen.

- [ ] **MA-11-011 – Sequenznummern gegen alte Hupenpakete verwenden**
  - Jeder Hupenbefehl erhält eine monoton steigende `seq`.
  - ESP ignoriert Befehle mit älterer Sequenznummer als der zuletzt akzeptierten.
  - Nach Reconnect darf kein alter `active=true`-Befehl die Hupe starten.
  - Retained Hupenbefehle sind verboten.
  - Abnahme: verspätete oder doppelte MQTT-Pakete können keine unbeabsichtigte Hupe auslösen.

- [ ] **MA-11-012 – Boot- und Reconnect-Sicherheitszustand festlegen**
  - ESP-Bootzustand: Hupe AUS.
  - Pi-Bootzustand: Hupe AUS.
  - MQTT-Reconnect: Hupe bleibt AUS, bis ein neuer aktueller `active=true`-Befehl eingeht.
  - Broker-Neustart darf keine Hupe auslösen.
  - Sensorfehler dürfen die Hupen-Failsafe-Logik nicht deaktivieren.
  - Abnahme: Stromausfall, Neustart und Reconnect bleiben akustisch sicher.

## M11.5 – Raspberry-Pi-/Screen-Aufgaben

- [ ] **MA-11-013 – Hupenbutton in Fahrzeug-Screen vorplanen**
  - Gut erreichbarer Touch-Button mit Fahrzeughupen-Symbol.
  - Button benötigt echte `pointer/touch down`- und `pointer/touch up`-Ereignisse.
  - Gedrückter Zustand muss visuell deutlich sichtbar sein.
  - Verlassen des Buttons bei gedrücktem Pointer sowie Abbruch des Touch-Ereignisses müssen ebenfalls `active=false` auslösen.
  - Kein normales Click-Toggle verwenden.
  - Abnahme: UI-Spezifikation bildet eine echte Hold-to-Honk-Bedienung ab.

- [ ] **MA-11-014 – Pi-Horn-Controller planen**
  - Eine zentrale Logik auf Pi 1 verwaltet den gewünschten Hupenzustand.
  - Bei `pressed`: sofort `active=true` senden und Keepalive starten.
  - Bei `released/cancelled`: sofort `active=false` senden und Keepalive stoppen.
  - MQTT-Ausfall darf UI/Flask nicht blockieren.
  - Der Hupenstatus soll später über die bestehende System-/Diagnose-API verfügbar sein.
  - Abnahme: klar definierter Zustandsautomat ohne Toggle-Mehrdeutigkeit.

## M11.6 – ESP32-Sensor/Aux-Aufgaben

- [ ] **MA-11-015 – Lokalen Horn-Controller auf ESP32 #2 planen**
  - MQTT-Callback darf nur Zustand übernehmen und keine lange Audiowiedergabe blockierend ausführen.
  - Audioausgabe läuft nicht blockierend bzw. in eigener Task/State-Machine.
  - Sensorabfragen müssen während der Hupe weiterlaufen.
  - Hupen-Lease lokal überwachen.
  - `active=false`, Timeout oder Fehler stoppt Audio sofort.
  - Abnahme: Hupe, WLAN/MQTT und Sensorik können gleichzeitig laufen.

- [ ] **MA-11-016 – Audiofehler diagnostizierbar machen**
  - Mindestens Zustände für `ready`, `playing`, `stopped`, `audio_error` vorsehen.
  - Fehler im Audio-Pfad dürfen den ESP nicht neu starten oder Sensorik blockieren.
  - Fehler über `messecar/horn/state` melden.
  - Diagnose auf Pi 2 später sichtbar machen.
  - Abnahme: Audiofehler sind erkennbar und führen zu sicherem Zustand Hupe AUS.

## M11.7 – Simulation und Tests

- [ ] **MA-11-017 – Hupe in PC-Simulation ergänzen**
  - Touch-Hupenbutton simulierbar machen.
  - `pressed`, `held`, `released` sichtbar darstellen.
  - MQTT-Command und ESP-State getrennt anzeigen.
  - Kein echtes Audiosignal notwendig; visueller/optionaler Browser-Sound reicht für die Simulation.
  - Abnahme: komplette Kommunikationslogik kann ohne Fahrzeughardware getestet werden.

- [ ] **MA-11-018 – Kommunikationsfehler der Hupe simulieren**
  - `active=true` senden und anschließend Broker trennen.
  - verlorenes `active=false` simulieren.
  - verspätetes altes `active=true` simulieren.
  - ESP-Neustart während gedrückter Hupe simulieren.
  - Erwartung in allen Fällen: Hupe fällt innerhalb des definierten Fail-Safe-Zeitfensters auf AUS.

- [ ] **MA-11-019 – Hardwaretest des Audio-Pfads definieren**
  - Zuerst mit geringer Lautstärke testen.
  - Versorgungsspannung am PAM8406 messen.
  - Lautsprecher auf Erwärmung und Verzerrung prüfen.
  - Audioausgang des ESP und Verstärkereingang auf korrekte Pegel prüfen.
  - 30 Sekunden Dauerhupen-Test nur innerhalb sicherer thermischer und akustischer Grenzen durchführen.
  - Abnahme: stabiler Ton ohne Reset von ESP, Sensorfehler oder übermäßige Erwärmung.

- [ ] **MA-11-020 – WLAN-Latenztest für die Hupe definieren**
  - Mindestens 100 Start-/Stop-Vorgänge auslösen.
  - subjektiv und, wenn möglich, per Zeitstempel Start-/Stop-Latenz bewerten.
  - Ziel: typische Reaktion unter 100 ms.
  - Prüfen, ob gleichzeitig Drive-MQTT, Sensor-Telemetrie und Hupenbefehle zuverlässig funktionieren.
  - Abnahme: keine hängenbleibende Hupe, keine verlorenen Stop-Befehle und keine merkliche Beeinträchtigung der Fahrsteuerung.

## Definition of Done für M11

Die Hupenfunktion gilt später erst als abgeschlossen, wenn:

1. Der zweite ESP32 gleichzeitig Sensorik und Hupenfunktion zuverlässig betreibt.
2. Das PAM8406 elektrisch korrekt versorgt und mit einem geeigneten Audiosignal angesteuert wird.
3. Der Hupenton vollständig lokal auf dem ESP entsteht; WLAN überträgt nur Steuerbefehle.
4. Der Touchscreen eine echte Hold-to-Honk-Bedienung bietet.
5. Start und Stop der Hupe typischerweise in weniger als 100 ms reagieren.
6. Ein verlorener Stop-Befehl durch die lokale 300-ms-Lease automatisch abgefangen wird.
7. Alte, retained oder verspätete MQTT-Pakete keine Hupe auslösen können.
8. Boot, Reconnect und Broker-Ausfall immer mit Hupe AUS beginnen bzw. enden.
9. Hupenbetrieb die Temperatur-/Abstandssensorik nicht blockiert.
10. Pi 2 später Hupenstatus und Audiofehler diagnostizieren kann.

## Referenzhardware

Vorhandenes Verstärkermodul: **PAM8406 Digital Stereo Audio Power Amplifier Board**. Laut verlinkter Produktbeschreibung ist das Modul für 2,5–5 V Betriebsspannung (max. 5,5 V) ausgelegt und dient als Class-D-Audioverstärker. Die konkrete Verdrahtung zum vorhandenen ESP32 und Lautsprecher wird erst im Rahmen der oben definierten Hardwareaufgaben finalisiert.
