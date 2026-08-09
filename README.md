# llano-v12pro-ctrl

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Platform: Linux only](https://img.shields.io/badge/platform-Linux%20only-lightgrey.svg)

> Läuft nur unter Linux, auch wenn der Code in Python geschrieben ist: die Gerätesteuerung nutzt
> `/dev/hidraw*`-ioctls, der Automatikmodus nutzt `systemd --user` und `/sys/class/hwmon` für
> Temperatursensoren. Das sind alles Linux-spezifische Mechanismen ohne Windows-/macOS-Äquivalent
> in diesem Projekt.

Natives Linux-Steuerungstool für das **llano V12 Pro** RGB-Laptop-Kühlpad (Holtek USB-HID
`374a:b101`), dessen offizielle Windows-Software **Myth.Cool** ist. Statt die Windows-App unter
Wine laufen zu lassen (kaputte UI-Texte, nicht funktionierendes Sensor-Dashboard), spricht
`llano-v12pro-ctrl` das Gerät direkt über `/dev/hidraw*` an, reverse-engineered aus echtem USB-Traffic
der Original-App und durch systematische Live-Tests am physischen Gerät.

## Inhaltsverzeichnis

- [Features](#features)
- [Hardware-Hintergrund](#hardware-hintergrund)
- [Installation](#installation)
- [Nutzung](#nutzung)
- [Automatikmodus (Temperatur-Indikator)](#automatikmodus-temperatur-indikator)
- [Lüfter-Erinnerung & Verlaufsprotokoll](#lüfter-erinnerung--verlaufsprotokoll)
- [Protokoll-Dokumentation](#protokoll-dokumentation)
- [Beitragen](#beitragen)
- [Autoren](#autoren)
- [Lizenz](#lizenz)

## Features

- **CLI** (`llano-v12pro-ctrl`): Farbe, Effekt, Effekt-Geschwindigkeit und Helligkeit setzen, Gerät
  komplett ein-/ausschalten, Live-Telemetrie beobachten
- **GUI** (`llano-v12pro-ctrl-gui`, PyQt6): dieselben Funktionen grafisch, inklusive Live-Status-Anzeige
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
- Vollständig dokumentiertes HID-Protokoll (siehe [`protocol.py`](src/llano_v12pro_ctrl/protocol.py)),
  inklusive Diagnose-Befehl für den rohen 64-Byte Input-Report (`llano-v12pro-ctrl raw-input`)

## Hardware-Hintergrund

Das Pad hat **keine software-steuerbare stufenlose Lüfterdrehzahl**. Das ist eine
Hardware/Firmware-Grenze, keine Einschränkung dieses Tools. Die Drehzahl bleibt ausschließlich
über das physische Rad am Pad einstellbar; `llano-v12pro-ctrl` liest sie nur aus (Live-Telemetrie).
Software-seitig steuerbar sind: RGB-Farbe (5 Farben), Lichteffekt (5 Modi), Effekt-Geschwindigkeit,
Helligkeit, sowie ein reiner Ein/Aus-Kill-Switch für die gesamte Einheit (Lüfter + Licht).

Da die Drehzahl selbst nicht regelbar ist, bietet `llano-v12pro-ctrl` stattdessen zwei indirekte
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
sudo cp packaging/70-llano-v12pro-ctrl.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Der Nutzer muss außerdem Mitglied der Gruppe `plugdev` sein:

```bash
sudo usermod -aG plugdev "$USER"   # danach neu einloggen
```

## Nutzung

```bash
llano-v12pro-ctrl status                                      # aktuellen Zustand + Live-Telemetrie anzeigen
llano-v12pro-ctrl light --color red --effect breathing         # Farbe/Effekt setzen
llano-v12pro-ctrl light --brightness 128                       # nur Helligkeit ändern
llano-v12pro-ctrl light --off                                  # Beleuchtung aus (Lüfter läuft weiter)
llano-v12pro-ctrl power off                                    # gesamte Einheit aus (Lüfter + Licht)
llano-v12pro-ctrl monitor                                       # Live-Telemetrie laufend anzeigen
llano-v12pro-ctrl raw-input                                      # rohen 64-Byte Input-Report beobachten (Diagnose)
llano-v12pro-ctrl-gui                                           # grafische Oberfläche starten
```

| Option | Werte |
|---|---|
| `--color` | `red`, `lightblue`, `green`, `purple`, `orange` (oder 0-4) |
| `--effect` | `solid`, `breathing`, `rainbow`, `chase`, `zones` (oder 0-4) |
| `--speed` | `0`-`3` (offiziell validierter Bereich, 0=schnell) |
| `--brightness` | `0`-`255` |

Details zu allen Optionen: `llano-v12pro-ctrl <befehl> --help`.

## Automatikmodus (Temperatur-Indikator)

```bash
cp config/config.example.toml ~/.config/llano-v12pro-ctrl/config.toml   # anpassen nach Bedarf
llano-v12pro-ctrl auto
```

Schaltet die Pad-Farbe je nach CPU-Temperatur um (grün → orange → rot), mit optionalem
GPU-Temperatur-Alarm (lila/breathing), siehe Kommentare in
[`config/config.example.toml`](config/config.example.toml). Für Dauerbetrieb als systemd-User-Service:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/llano-v12pro-ctrl.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now llano-v12pro-ctrl.service
```

Die GUI zeigt den Auto-Modus-Status an und kann den Dienst für die laufende Sitzung
pausieren/fortsetzen (`systemctl --user stop/start`). Der Dienst bleibt dabei `enabled` und läuft
nach dem nächsten Login/Neustart normal weiter.

## Lüfter-Erinnerung & Verlaufsprotokoll

Beide Optionen leben im `auto`-Modus (siehe oben) und sind standardmäßig deaktiviert. Aktivierung
in `~/.config/llano-v12pro-ctrl/config.toml`, siehe kommentierte Beispiele in
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

## Protokoll-Dokumentation

Die vollständige Herleitung des 9-Byte-HID-Feature-Reports (welches Byte was bedeutet, was
Software-schreibbar vs. reines Telemetrie-Feld ist, Messreihen zu Grenzfällen) steht als
Docstring in [`src/llano_v12pro_ctrl/protocol.py`](src/llano_v12pro_ctrl/protocol.py).

Neben dem Feature-Report existiert laut HID-Report-Descriptor auch ein 64-Byte Output- und
Input-Report. Beide wurden bereits getestet, bisher ohne bekannten inhaltsabhängigen Effekt
(vermutlich ungenutztes Boilerplate der Holtek-Referenzvorlage). `llano-v12pro-ctrl raw-input` erlaubt
weiteres manuelles Beobachten des Input-Reports. Bewusst **nicht** implementiert: automatisiertes
Schreiben/Fuzzing des Output-Reports. Blindes Ausprobieren von undokumentierten Report-Bytes ohne
konkrete Hypothese ist ein unnötiges Risiko für unerwartetes Geräteverhalten auf echter Hardware.

## Beitragen

Issues und Pull Requests sind willkommen, insbesondere Rückmeldungen zu anderen llano-V12-Varianten
oder zusätzlichen effect/color-Werten wären hilfreich. Bitte beim Ändern von `protocol.py`/`device.py`
Messreihen/Belege für neue Erkenntnisse mitliefern, analog zum bestehenden Dokumentationsstil.

## Autoren

- [**@Quahuay**](https://github.com/Quahuay) (Maintainer)

## Lizenz

MIT, siehe [LICENSE](LICENSE).
