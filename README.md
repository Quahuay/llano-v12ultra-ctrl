# llano-v12ultra-ctrl

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Platform: Linux getestet, Windows in Arbeit](https://img.shields.io/badge/platform-Linux%20(getestet)%20%2F%20Windows%20(in%20Arbeit)-lightgrey.svg)

> **Vollständig getestet nur unter Linux.** Eine Windows-Portierung ist in Arbeit (siehe
> [Windows-Status](#windows-status)) - Temperatursensoren und Hintergrunddienst-Steuerung sind
> bereits code-seitig vorbereitet (aber ungetestet, keine Windows-Maschine verfügbar), die
> eigentliche Geräteansteuerung (`device.py`) läuft aktuell noch ausschließlich über
> Linux-spezifische `/dev/hidraw*`-ioctls.

Natives Linux-Steuerungstool für das **llano V12 Ultra** RGB-Laptop-Kühlpad (Holtek USB-HID
`374a:b101`), dessen offizielle Windows-Software **Myth.Cool** ist. Statt die Windows-App unter
Wine laufen zu lassen (kaputte UI-Texte, nicht funktionierendes Sensor-Dashboard), spricht
`llano-v12ultra-ctrl` das Gerät direkt über `/dev/hidraw*` an, reverse-engineered aus echtem USB-Traffic
der Original-App und durch systematische Live-Tests am physischen Gerät.

## Inhaltsverzeichnis

- [Features](#features)
- [Hardware-Hintergrund](#hardware-hintergrund)
- [Installation](#installation)
- [Nutzung](#nutzung)
- [Automatikmodus (Temperatur-Indikator)](#automatikmodus-temperatur-indikator)
- [Lüfter-Erinnerung & Verlaufsprotokoll](#lüfter-erinnerung--verlaufsprotokoll)
- [Windows-Status](#windows-status)
- [Protokoll-Dokumentation](#protokoll-dokumentation)
- [Beitragen](#beitragen)
- [Autoren](#autoren)
- [Lizenz](#lizenz)

## Features

- **CLI** (`llano-v12ultra-ctrl`): Farbe, Effekt, Effekt-Geschwindigkeit und Helligkeit setzen, Gerät
  komplett ein-/ausschalten, Live-Telemetrie beobachten
- **GUI** (`llano-v12ultra-ctrl-gui`, PyQt6): dieselben Funktionen grafisch, inklusive Live-Status-Anzeige
  und Steuerung des Automatik-Dienstes
- **Automatikmodus**: RGB-Farbe (und optional Effekt) schaltet abhängig von CPU-/GPU-Temperatur um
  (visueller Temperatur-Indikator direkt am Pad), optional als systemd-User-Service im Hintergrund
- **RPM-Verlauf** in der GUI (kleine Live-Sparkline der letzten ~2 Minuten Lüfterdrehzahl)
- **Lüfter-Erinnerung**: Desktop-Benachrichtigung, wenn die CPU heiß ist, aber die gemessene
  Drehzahl niedrig bleibt. Ersatz für einen echten Regelkreis, da die Drehzahl nicht per Software
  setzbar ist (siehe [Hardware-Hintergrund](#hardware-hintergrund))
- **CSV-Verlaufsprotokoll** (Temperatur/RPM/Farbe über Zeit), opt-in, für spätere Auswertung
- **Kritisch-heiß-Alarm**: hohe Temperatur-Schwellen können statt nur einer anderen Farbe auch
  einen auffälligeren Effekt setzen (z.B. `chase`/Lauflicht)
- Keine externen HID-Bibliotheken nötig: direkte `HIDIOCGFEATURE`/`HIDIOCSFEATURE`-ioctls auf
  `/dev/hidraw*`
- Vollständig dokumentiertes HID-Protokoll (siehe [`protocol.py`](src/llano_v12ultra_ctrl/protocol.py)),
  inklusive Diagnose-Befehl für den rohen 64-Byte Input-Report (`llano-v12ultra-ctrl raw-input`)

## Hardware-Hintergrund

Das Pad hat **keine software-steuerbare stufenlose Lüfterdrehzahl**. Das ist eine
Hardware/Firmware-Grenze, keine Einschränkung dieses Tools. Die Drehzahl bleibt ausschließlich
über das physische Rad am Pad einstellbar; `llano-v12ultra-ctrl` liest sie nur aus (Live-Telemetrie).
Software-seitig steuerbar sind: RGB-Farbe (5 Farben), Lichteffekt (5 Modi), Effekt-Geschwindigkeit,
Helligkeit, sowie ein reiner Ein/Aus-Kill-Switch für die gesamte Einheit (Lüfter + Licht).

Da die Drehzahl selbst nicht regelbar ist, bietet `llano-v12ultra-ctrl` stattdessen zwei indirekte
Werkzeuge rund um diese Grenze an (siehe [Lüfter-Erinnerung & Verlaufsprotokoll](#lüfter-erinnerung--verlaufsprotokoll)):
eine Desktop-Erinnerung, das Rad manuell hochzudrehen, und ein optionales Verlaufsprotokoll, um im
Nachhinein die passende Radstellung für typische Lasten zu finden.

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
llano-v12ultra-ctrl-gui                                           # grafische Oberfläche starten
```

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

## Lüfter-Erinnerung & Verlaufsprotokoll

Beide Optionen leben im `auto`-Modus (siehe oben) und sind standardmäßig deaktiviert. Aktivierung
in `~/.config/llano-v12ultra-ctrl/config.toml`, siehe kommentierte Beispiele in
[`config/config.example.toml`](config/config.example.toml).

**Lüfter-Erinnerung** (`[auto.fan_reminder]`): schickt eine Desktop-Benachrichtigung
(`notify-send`), wenn die CPU-Temperatur `temp_c` erreicht, die gemessene Drehzahl aber unter
`min_rpm` bleibt. `cooldown_s` verhindert wiederholte Benachrichtigungen, solange die Bedingung
anhält. Das ist der einzig mögliche indirekte "Regelkreis", da die Drehzahl selbst nicht per
Software gesetzt werden kann. Die Erinnerung richtet sich an den Menschen am physischen Rad.

**Verlaufsprotokoll** (`[auto.log]`): schreibt bei aktivem `auto`-Modus fortlaufend eine
CSV-Zeile (Zeitstempel, CPU-/GPU-Temperatur, Lüfterdrehzahl, Farbe, Effekt) an den konfigurierten
`path`. Nützlich, um im Nachhinein zu sehen, welche Radstellung bei welcher Last tatsächlich
ausreichend Kühlung liefert.

## Windows-Status

Eine Windows-Portierung ist in Arbeit. Architektur-Entscheidung: Python bleibt die Sprache (kein
Java-Rewrite), da sowohl `hidapi` (Python) als auch `hid4java` (Java) nur Wrapper um dieselbe
native `hidapi`-C-Bibliothek sind - der HID-Transport wäre in beiden Sprachen gleich gut
cross-platform, ein Java-Rewrite würde aber ~95% bereits fertigen und getesteten Code (Protokoll,
CLI, GUI, Config) wegwerfen, ohne die eigentlichen OS-spezifischen Baustellen (Temperatursensoren,
Hintergrunddienst, Notifications) zu lösen.

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
Docstring in [`src/llano_v12ultra_ctrl/protocol.py`](src/llano_v12ultra_ctrl/protocol.py).

Der komplette HID-Report-Descriptor wurde ausgelesen und bestätigt: das Gerät hat exakt drei
Reports, keine versteckten weiteren Report-IDs - 64-Byte Input, 64-Byte Output, 8-Byte Feature
(letzterer vollständig reverse-engineered). Zur Frage "kann man die Lüfterdrehzahl doch irgendwie
setzen?" wurde inzwischen erschöpfend getestet:

- **Pcap-Neuanalyse**: der originale USB-Mitschnitt der echten App (460MB) wurde vollständig
  ausgewertet - über 1300 echte SET_REPORT/GET_REPORT-Aufrufe der App, ausnahmslos alle mit
  Report-Typ Feature, keiner mit Report-Typ Output.
- **Vollständiger Fuzz**: alle 64 Output-Report-Positionen x alle 256 Werte (16384
  Schreib-Lese-Zyklen) live gegen echte Hardware getestet - 0 anhaltende Auswirkungen auf den
  zurückgelesenen Zustand.
- Dabei aber ein reproduzierbarer Nebenbefund: **jeder** Schreibvorgang auf den Output-Report löst
  einen kurzen, inhaltsunabhängigen Lichtblitz aus (4/4 bei gezieltem Nachtest bestätigt) - eine
  Firmware-Nebenwirkung des Empfangs, kein steuerbarer Effekt und kein Hinweis auf einen
  Fan-Speed-Pfad.
- **Original-App zerlegt**: `MythCool.exe` und alle `.gpk`-Ressourcen (unverschlüsselte, umbenannte
  Electron-ASAR-Archive) statisch analysiert. Die App hat echten `setFanSpeed()`-Code mit
  Fan-Curve-Logik, der einen `SetLapFanParam`-Befehl an ein natives `usbcenter`-Objekt schickt -
  dessen native Umsetzung wurde in keinem von ~15 geprüften Binaries gefunden. Wichtiger: die
  Pcap-Analyse zeigt, dass selbst die echte App bei 1305 realen Schreibvorgängen 1304 mal die
  Fan-Speed-Position auf 0 setzt - der Pfad wird in der Praxis kaum genutzt. "V12 Pro" existiert
  zudem nicht als Produktname in der App (nur "V12 Ultra") - die frühere Namensannahme dieses
  Projekts war schlicht falsch, siehe [Nachtrag 4](src/llano_v12ultra_ctrl/protocol.py).

Details und die Historie aller Tests stehen im Nachtrag in
[`protocol.py`](src/llano_v12ultra_ctrl/protocol.py). `llano-v12ultra-ctrl raw-input` erlaubt weiteres
manuelles Beobachten des Input-Reports.

## Beitragen

Issues und Pull Requests sind willkommen, insbesondere Rückmeldungen zu anderen llano-V12-Varianten
oder zusätzlichen effect/color-Werten wären hilfreich. Bitte beim Ändern von `protocol.py`/`device.py`
Messreihen/Belege für neue Erkenntnisse mitliefern, analog zum bestehenden Dokumentationsstil.

## Autoren

- [**@Quahuay**](https://github.com/Quahuay) (Maintainer)

## Lizenz

MIT, siehe [LICENSE](LICENSE).
