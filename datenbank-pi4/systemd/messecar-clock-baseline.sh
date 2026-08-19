#!/bin/bash
# Setzt die Systemuhr beim Boot auf einen festen, identischen Zeitpunkt.
# Internet/NTP ist in dieser Umgebung nicht zuverlaessig verfuegbar (mal Pi1,
# mal Pi2, mal keiner) und die Pi-RTCs (fake-hwclock) liefern beim Boot
# unterschiedliche alte Werte. Damit beide Pis IMMER untereinander konsistent
# sind und ab demselben Punkt aufsteigend zaehlen (statt zufaelliger/
# abweichender Uhrzeiten), wird auf beiden Pis identisch ein fester Anker
# gesetzt und echtes NTP bewusst deaktiviert (systemd-timesyncd maskiert) -
# sonst wuerde nur der Pi mit zufaellig funktionierendem Internet abweichen.
date -u -s "2026-01-01 00:00:00"
