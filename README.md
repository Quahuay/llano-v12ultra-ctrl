# llano-v12ultra-ctrl

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Platform: Linux getestet, Windows in Arbeit](https://img.shields.io/badge/platform-Linux%20(getestet)%20%2F%20Windows%20(in%20Arbeit)-lightgrey.svg)

> **Vollständig getestet nur unter Linux.** Eine Windows-Portierung ist in Arbeit (siehe
> [Windows-Status](#windows-status)) - Temperatursensoren und Hintergrunddienst-Steuerung sind
> bereits code-seitig vorbereitet (aber ungetestet, keine eigene Windows-Maschine im Dauerbetrieb),
> die eigentliche Geräteansteuerung (`device.py`) läuft aktuell noch ausschließlich über
> Linux-spezifische `/dev/hidraw*`-ioctls.

Natives Linux-Steuerungstool für das **llano V12 Ultra** RGB-Laptop-Kühlpad (Holtek USB-HID
`374a:b101`), dessen offizielle Windows-Software **Myth.Cool** ist. Statt die Windows-App unter
Wine laufen zu lassen (kaputte UI-Texte, nicht funktionierendes Sensor-Dashboard), spricht
`llano-v12ultra-ctrl` das Gerät direkt über `/dev/hidraw*` an, reverse-engineered aus echtem USB-Traffic
der Original-App und durch systematische Live-Tests am physischen Gerät - inklusive einer
**echten, per Live-USB-Capture gefundenen Lüfterdrehzahl-Steuerung** (siehe unten).

## Inhaltsverzeichnis

- [Features](#features)
- [Hardware-Hintergrund](#hardware-hintergrund)
- [Installation](#installation)
- [Nutzung](#nutzung)
- [Automatikmodus (Temperatur-Indikator)](#automatikmodus-temperatur-indikator)
- [Lüfterkurve & Lüfter-Erinnerung](#lüfterkurve--lüfter-erinnerung)
- [Windows-Status](#windows-status)
- [Protokoll-Dokumentation](#protokoll-dokumentation)
- [Beitragen](#beitragen)
- [Autoren](#autoren)
- [Lizenz](#lizenz)

## Features

- **CLI** (`llano-v12ultra-ctrl`): Farbe, Effekt, Effekt-Geschwindigkeit, Helligkeit **und
  Lüfterdrehzahl** setzen, Gerät komplett ein-/ausschalten, Live-Telemetrie beobachten
- **GUI** (`llano-v12ultra-ctrl-gui`, PyQt6): dieselben Funktionen grafisch, inklusive Live-Status-Anzeige,
  Fan-Speed-Regler und Steuerung des Automatik-Dienstes
- **Echte Lüfterdrehzahl-Steuerung** (100 Stufen, ~25 U/min pro Schritt, 300-2800 U/min
  Gesamtbereich): per Live-USB-Capture gegen die echte Hersteller-App gefunden (siehe
  [Hardware-Hintergrund](#hardware-hintergrund)) und live auf echter Hardware verifiziert - jeder
  einzelne der 100 Rohwerte einzeln durchgetestet, kein physisches Rad-Drehen mehr nötig
- **Automatikmodus**: RGB-Farbe (und optional Effekt) schaltet abhängig von CPU-/GPU-Temperatur um
  (visueller Temperatur-Indikator direkt am Pad), optional als systemd-User-Service im Hintergrund
- **Lüfterkurve** (opt-in): bildet die CPU-Temperatur per linearer Interpolation zwischen frei
  konfigurierbaren Punkten auf eine Lüfterdrehzahl ab - in der GUI als editierbare Tabelle
  verfügbar, siehe [Lüfterkurve & Lüfter-Erinnerung](#lüfterkurve--lüfter-erinnerung)
- **RPM-Verlauf** in der GUI (kleine Live-Sparkline der letzten ~2 Minuten Lüfterdrehzahl)
- **Lüfter-Erinnerung**: Desktop-Benachrichtigung, wenn die CPU heiß ist, aber die gemessene
  Drehzahl niedrig bleibt - Übergangslösung, falls die Lüfterkurve (noch) nicht aktiviert ist
- **CSV-Verlaufsprotokoll** (Temperatur/RPM/Farbe über Zeit), opt-in, für spätere Auswertung
- **Kritisch-heiß-Alarm**: hohe Temperatur-Schwellen können statt nur einer anderen Farbe auch
  einen auffälligeren Effekt setzen (z.B. `chase`/Lauflicht)
- Keine externen HID-Bibliotheken nötig: direkte `HIDIOCGFEATURE`/`HIDIOCSFEATURE`-ioctls auf
  `/dev/hidraw*`
- Vollständig dokumentiertes HID-Protokoll (siehe [`protocol.py`](src/llano_v12ultra_ctrl/protocol.py)),
  inklusive Diagnose-Befehl für den rohen 64-Byte Input-Report (`llano-v12ultra-ctrl raw-input`)

## Hardware-Hintergrund

Software-steuerbar sind: Lüfterdrehzahl (raw-Bereich 1-100, ca. 25 U/min pro Schritt, insgesamt
300-2800 U/min), RGB-Farbe (5 Farben), Lichteffekt (5 Modi), Effekt-Geschwindigkeit, Helligkeit,
sowie ein reiner Ein/Aus-Kill-Switch für die gesamte Einheit (Lüfter + Licht). Werte über 100 nimmt
das Gerät zwar noch an, die echte Drehzahl bleibt ab dem Maximum aber stehen - nur die Anzeige
rechnet ohne Begrenzung weiter. Das physische Rad am Pad funktioniert weiterhin parallel als
manuelle Override-Möglichkeit.

Lüfterdrehzahl und Licht sind zwei komplett getrennte HID-Kommandos (siehe
[`protocol.py`](src/llano_v12ultra_ctrl/protocol.py) für das vollständige Byte-Layout). Wie das
Fan-Kommando gefunden wurde, inklusive aller Sackgassen unterwegs, steht in
[HISTORY.md](HISTORY.md).

Der Automatikmodus (siehe unten) kann optional auch die Lüfterdrehzahl temperaturbasiert regeln
(Lüfterkurve, standardmäßig deaktiviert) - siehe
[Lüfterkurve & Lüfter-Erinnerung](#lüfterkurve--lüfter-erinnerung).

## Installation

PyQt6 ist auf vielen Systemen (auch hier) ein **apt/Distro-Paket**, kein pip-Paket. Ein simples
`pip install -e .` scheitert dadurch häufig an PEP 668 (`externally-managed-environment`). Zwei
Wege, je nach System:

<details>
<summary><strong>Weg A: System mit PyQt6 aus der Paketverwaltung (z.B. Debian/Ubuntu)</strong></summary>

```bash
sudo apt install python3-pyqt6   # falls noch nicht vorhanden
```

Danach entweder die mitgelieferten Shim-Skripte verwenden oder das Paket per venv mit
`--system-site-packages` installieren, damit das apt-Paket sichtbar bleibt:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e ".[gui]"
```

</details>

<details>
<summary><strong>Weg B: normales pip/pipx (andere Systeme)</strong></summary>

```bash
pipx install ".[gui]"
# oder nur die CLI, ohne GUI/PyQt6-Abhängigkeit:
pipx install .
```

</details>

### udev-Regel

Damit der eigene Linux-Nutzer ohne root auf das HID-Gerät zugreifen darf:

```bash
sudo cp packaging/70-llano-v12ultra-ctrl.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Der Nutzer muss außerdem Mitglied der Gruppe `plugdev` sein:

```bash
sudo usermod -aG plugdev "$USER"   # danach neu einloggen
```

## Nutzung

```bash
llano-v12ultra-ctrl status                                      # aktuellen Zustand + Live-Telemetrie anzeigen
llano-v12ultra-ctrl light --color red --effect breathing         # Farbe/Effekt setzen
llano-v12ultra-ctrl light --brightness 128                       # nur Helligkeit ändern
llano-v12ultra-ctrl light --off                                  # Beleuchtung aus (Lüfter läuft weiter)
llano-v12ultra-ctrl power off                                    # gesamte Einheit aus (Lüfter + Licht)
llano-v12ultra-ctrl monitor                                       # Live-Telemetrie laufend anzeigen
llano-v12ultra-ctrl raw-input                                      # rohen 64-Byte Input-Report beobachten (Diagnose)
llano-v12ultra-ctrl fan-speed 50                                   # Lüfterdrehzahl setzen (1-100, siehe unten)
llano-v12ultra-ctrl-gui                                           # grafische Oberfläche starten
```

`fan-speed` setzt die Lüfterdrehzahl über ein eigenes HID-Kommando (Wertebereich `1`-`100`, jeder
Wert eine eigene Stufe von ca. 25 U/min: `raw=1` → 300 U/min, `raw=100` → 2800 U/min). Live
verifiziert, jeder einzelne der 100 Werte einzeln getestet (siehe
[Hardware-Hintergrund](#hardware-hintergrund)). Auch in der GUI als eigener Fan-Speed-Regler
verfügbar.

| Option | Werte |
|---|---|
| `--color` | `red`, `lightblue`, `green`, `purple`, `orange` (oder 0-4) |
| `--effect` | `solid`, `breathing`, `rainbow`, `chase`, `zones` (oder 0-4) |
| `--speed` | `0`-`3` (offiziell validierter Bereich, 0=schnell) |
| `--brightness` | `0`-`255` |

Details zu allen Optionen: `llano-v12ultra-ctrl <befehl> --help`.

## Automatikmodus (Temperatur-Indikator)

```bash
cp config/config.example.toml ~/.config/llano-v12ultra-ctrl/config.toml   # anpassen nach Bedarf
llano-v12ultra-ctrl auto
```

Schaltet die Pad-Farbe je nach CPU-Temperatur um (grün → orange → rot), mit optionalem
GPU-Temperatur-Alarm (lila/breathing), siehe Kommentare in
[`config/config.example.toml`](config/config.example.toml). Für Dauerbetrieb als systemd-User-Service:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/llano-v12ultra-ctrl.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now llano-v12ultra-ctrl.service
```

Die GUI zeigt den Auto-Modus-Status an und kann den Dienst für die laufende Sitzung
pausieren/fortsetzen (`systemctl --user stop/start`). Der Dienst bleibt dabei `enabled` und läuft
nach dem nächsten Login/Neustart normal weiter.

## Lüfterkurve & Lüfter-Erinnerung

Alle drei Optionen leben im `auto`-Modus (siehe oben) und sind standardmäßig deaktiviert.
Aktivierung in `~/.config/llano-v12ultra-ctrl/config.toml`, siehe kommentierte Beispiele in
[`config/config.example.toml`](config/config.example.toml) - oder in der GUI im Bereich
"Lüfterkurve (Automatikmodus)" (editierbare Tabelle, Punkte hinzufügen/entfernen, Speichern).

**Lüfterkurve** (`[auto.fan_curve]`): bildet die CPU-Temperatur per linearer Interpolation
zwischen konfigurierten `points` (`temp_c`/`raw`-Paare) auf einen Lüfterdrehzahl-Rohwert ab.
`min_change_raw` verhindert ständiges Nachregeln bei kleinen Temperaturschwankungen - es wird nur
geschrieben, wenn sich der Zielwert um mindestens so viel ändert. Wirkt nur, während `auto` läuft;
das GUI-Formular speichert nur die Konfiguration, wendet sie nicht selbst live an.

**Lüfter-Erinnerung** (`[auto.fan_reminder]`): schickt eine Desktop-Benachrichtigung
(`notify-send`), wenn die CPU-Temperatur `temp_c` erreicht, die gemessene Drehzahl aber unter
`min_rpm` bleibt. `cooldown_s` verhindert wiederholte Benachrichtigungen, solange die Bedingung
anhält. Übergangslösung, falls die Lüfterkurve (noch) nicht aktiviert ist.

**Verlaufsprotokoll** (`[auto.log]`): schreibt bei aktivem `auto`-Modus fortlaufend eine
CSV-Zeile (Zeitstempel, CPU-/GPU-Temperatur, Lüfterdrehzahl, Farbe, Effekt) an den konfigurierten
`path`. Nützlich, um im Nachhinein die eigene Lüfterkurve anhand echter Lastdaten zu verfeinern.

## Windows-Status

Eine Windows-Portierung ist in Arbeit.

| Datei | Status |
|---|---|
| `notify.py` | ✅ Auf `plyer` umgestellt (cross-platform), live unter Linux getestet |
| `temp.py` | ✅ Windows-Zweig für CPU-Temperatur über LibreHardwareMonitor/WMI ergänzt, **ungetestet** |
| `gui/service_control.py` | ✅ Windows-Zweig über `schtasks` (geplante Aufgabe) ergänzt, **ungetestet** |
| `device.py` | ⏳ Noch offen. Ein erster Versuch, auf die cross-platform `hid`-Bibliothek umzusteigen, hat bei einem Testlauf einen USB-Rebind-Vorfall am echten Pad ausgelöst (vermutlich durch gleichzeitige Schreibzugriffe von zwei Prozessen, nicht zwingend ein hidapi-spezifisches Problem) - zurückgestellt, bis das sauber und ohne Risiko für die Hardware nachvollzogen werden kann |

Für alle drei Windows-Zweige gilt: keine Windows-Maschine in der Entwicklungsumgebung verfügbar,
daher ausschließlich code-seitig vorbereitet, nicht praktisch verifiziert. Rückmeldungen von
Windows-Nutzern sind ausdrücklich willkommen (siehe [Beitragen](#beitragen)).

## Protokoll-Dokumentation

Die vollständige Herleitung des 9-Byte-HID-Feature-Reports (welches Byte was bedeutet, was
Software-schreibbar vs. reines Telemetrie-Feld ist, Messreihen zu Grenzfällen) steht als
Docstring in [`src/llano_v12ultra_ctrl/protocol.py`](src/llano_v12ultra_ctrl/protocol.py). Der
komplette HID-Report-Descriptor wurde ausgelesen und bestätigt: das Gerät hat exakt drei Reports,
keine versteckten weiteren Report-IDs - 64-Byte Input, 64-Byte Output, 8-Byte Feature (vollständig
reverse-engineered, inklusive des separaten Fan-Speed-Kommandos). Wie diese Herleitung entstanden
ist, steht in [HISTORY.md](HISTORY.md). `llano-v12ultra-ctrl raw-input` erlaubt weiteres manuelles
Beobachten des Input-Reports.

## Beitragen

Issues und Pull Requests sind willkommen, insbesondere Rückmeldungen zu anderen llano-V12-Varianten
oder zusätzlichen effect/color-Werten wären hilfreich. Bitte beim Ändern von `protocol.py`/`device.py`
Messreihen/Belege für neue Erkenntnisse mitliefern, analog zum bestehenden Dokumentationsstil.

**macOS ist nicht geplant** - das Pad ist explizit nicht für den Einsatz an Mac-Geräten geeignet.

**Primär gepflegt wird Linux.** Windows-Unterstützung ist ein nachträglich hinzugefügtes Ziel, keine
gleichrangige Plattform - Rückmeldungen/PRs dazu sind trotzdem willkommen, haben aber nicht dieselbe
Priorität wie der Linux-Kernbetrieb.

## Autoren

- [**@Quahuay**](https://github.com/Quahuay) (Maintainer)

## Lizenz

MIT, siehe [LICENSE](LICENSE).
