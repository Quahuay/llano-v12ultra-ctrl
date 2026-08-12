# llano-v12ultra-ctrl

*[English version](README.md)*

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Platform: Linux (primär) + Windows (Geräteansteuerung getestet)](https://img.shields.io/badge/platform-Linux%20(prim%C3%A4r)%20%2B%20Windows-lightgrey.svg)

> **Primär für Linux entwickelt und gepflegt.** Die eigentliche Geräteansteuerung (`status`/
> `light`/`fan-speed`) ist live gegen echte Hardware unter Windows getestet und funktioniert (siehe
> [Windows-Status](#windows-status)). Temperatursensor-Erkennung und Hintergrunddienst-Steuerung
> sind unter Windows dagegen bisher nur code-seitig vorbereitet, nicht praktisch verifiziert.

Natives Linux-Steuerungstool für das **llano V12 Ultra** RGB-Laptop-Kühlpad (Holtek USB-HID
`374a:b101`), dessen offizielle Windows-Software **Myth.Cool** ist. Statt die Windows-App unter
Wine laufen zu lassen (kaputte UI-Texte, nicht funktionierendes Sensor-Dashboard), spricht
`llano-v12ultra-ctrl` das Gerät direkt über `/dev/hidraw*` an. Das Protokoll wurde aus echtem
USB-Traffic der Original-App und durch systematische Live-Tests am physischen Gerät
reverse-engineered, inklusive einer **echten, per Live-USB-Capture gefundenen
Lüfterdrehzahl-Steuerung** (siehe unten).

### Hinweis zu Markennamen

Dieses Projekt steht in keiner Verbindung zu, wird nicht unterstützt von und ist nicht autorisiert
durch den Hersteller/Vertreiber der Marke **llano** oder der Software **Myth.Cool**. Es handelt
sich um ein unabhängiges, privates Open-Source-Projekt eines einzelnen Nutzers dieser Hardware.
Der Markenname wird ausschließlich beschreibend genannt, um klarzustellen, für welches Gerät
dieses Tool gedacht ist (nominative Nennung zur Wiedererkennbarkeit), nicht um eine Zugehörigkeit,
Empfehlung oder Zusammenarbeit zu suggerieren. Alle Rechte an den genannten Markennamen liegen bei
ihren jeweiligen Inhabern.

## Inhaltsverzeichnis

- [Features](#features)
- [Hardware-Hintergrund](#hardware-hintergrund)
- [Installation](#installation)
- [Sprache](#sprache)
- [Nutzung](#nutzung)
- [Automatikmodus (Temperatur-Indikator)](#automatikmodus-temperatur-indikator)
- [Lüfterkurve & Lüfter-Erinnerung](#lüfterkurve--lüfter-erinnerung)
- [Windows-Status](#windows-status)
- [Paket-Status](#paket-status)
- [Protokoll-Dokumentation](#protokoll-dokumentation)
- [Beitragen](#beitragen)
- [Autoren](#autoren)
- [Lizenz](#lizenz)

## Features

- **CLI** (`llano-v12ultra-ctrl`): Farbe, Effekt, Effekt-Geschwindigkeit, Helligkeit **und
  Lüfterdrehzahl** setzen, Gerät komplett ein-/ausschalten, Live-Telemetrie beobachten
- **GUI** (`llano-v12ultra-ctrl-gui`, PyQt6): dieselben Funktionen grafisch, inklusive kompakter
  Status-Tabelle, separatem RPM-Verlauf, Fan-Speed-Regler, Steuerung des Automatik-Dienstes und bis
  zu fünf speicherbaren Profilen (Licht + Lüfterdrehzahl, ein Klick zum Anwenden)
- **Echte Lüfterdrehzahl-Steuerung** (100 Stufen, ca. 25 U/min pro Schritt, 300 bis 2800 U/min
  Gesamtbereich): per Live-USB-Capture gegen die echte Hersteller-App gefunden (siehe
  [Hardware-Hintergrund](#hardware-hintergrund)) und live auf echter Hardware verifiziert. Jeder
  einzelne der 100 Rohwerte wurde einzeln durchgetestet, kein physisches Rad-Drehen mehr nötig.
- **Automatikmodus**: RGB-Farbe (und optional Effekt) schaltet abhängig von CPU-/GPU-Temperatur um
  (visueller Temperatur-Indikator direkt am Pad), optional als systemd-User-Service im Hintergrund
- **Lüfterkurve** (seit v0.1.3 standardmäßig aktiv): bildet die CPU-Temperatur per linearer Interpolation zwischen frei
  konfigurierbaren Punkten auf eine Lüfterdrehzahl ab. In der GUI als interaktive Grafik verfügbar
  (Punkte ziehen/hinzufügen/entfernen), Zahlenwerte optional über "Erweiterte Einstellungen". Siehe
  [Lüfterkurve & Lüfter-Erinnerung](#lüfterkurve--lüfter-erinnerung).
- **RPM-Verlauf** in der GUI (kleine Live-Sparkline der letzten ca. 2 Minuten Lüfterdrehzahl)
- **Lüfter-Erinnerung**: Desktop-Benachrichtigung, wenn die CPU heiß ist, aber die gemessene
  Drehzahl niedrig bleibt. Übergangslösung, falls die Lüfterkurve noch nicht aktiviert ist.
- **CSV-Verlaufsprotokoll** (Temperatur/RPM/Farbe über Zeit), opt-in, für spätere Auswertung
- **Kritisch-heiß-Alarm**: hohe Temperatur-Schwellen können statt nur einer anderen Farbe auch
  einen auffälligeren Effekt setzen (z.B. `chase`/Lauflicht)
- **Leiser Update-Check** (abschaltbar): einmal alle 24h eine Prüfung gegen die GitHub-Releases-API
  im Hintergrund. Niemals ein stiller Self-Updater, nur ein Hinweis plus Link (oder ein Hinweis
  "Update über den Paketmanager", falls per `.deb`/Arch installiert). Siehe `[general]
  update_check` in [`config/config.example.toml`](config/config.example.toml).
- Keine externen HID-Bibliotheken nötig: direkte `HIDIOCGFEATURE`/`HIDIOCSFEATURE`-ioctls auf
  `/dev/hidraw*`
- Vollständig dokumentiertes HID-Protokoll (siehe [`protocol.py`](src/llano_v12ultra_ctrl/protocol.py)),
  inklusive Diagnose-Befehl für den rohen 64-Byte Input-Report (`llano-v12ultra-ctrl raw-input`)

## Hardware-Hintergrund

Software-steuerbar sind: Lüfterdrehzahl (raw-Bereich 1 bis 100, ca. 25 U/min pro Schritt,
insgesamt 300 bis 2800 U/min), RGB-Farbe (5 Farben), Lichteffekt (5 Modi),
Effekt-Geschwindigkeit, Helligkeit, sowie ein reiner Ein/Aus-Kill-Switch für die gesamte Einheit
(Lüfter + Licht). Werte über 100 nimmt das Gerät zwar noch an, die echte Drehzahl bleibt ab dem
Maximum aber stehen; nur die Anzeige rechnet ohne Begrenzung weiter. Das physische Rad am Pad
funktioniert weiterhin parallel als manuelle Override-Möglichkeit.

Lüfterdrehzahl und Licht sind zwei komplett getrennte HID-Kommandos (siehe
[`protocol.py`](src/llano_v12ultra_ctrl/protocol.py) für das vollständige Byte-Layout). Wie das
Fan-Kommando gefunden wurde, inklusive aller Sackgassen unterwegs, steht in
[HISTORY.md](HISTORY.md).

Der Automatikmodus (siehe unten) kann optional auch die Lüfterdrehzahl temperaturbasiert regeln
(Lüfterkurve, seit v0.1.3 standardmäßig aktiv). Siehe
[Lüfterkurve & Lüfter-Erinnerung](#lüfterkurve--lüfter-erinnerung).

## Installation

HINWEIS: native Installer sind neu. Siehe [Paket-Status](#paket-status) für den genauen
Verifikationsstand. Pakete und Binärdateien hängen an einem
[GitHub Release](https://github.com/Quahuay/llano-v12ultra-ctrl/releases), sobald eine Version
getaggt ist. Passenden Weg für die eigene Plattform wählen:

| Plattform | Wie |
|---|---|
| Windows | `.msi` von [Releases](https://github.com/Quahuay/llano-v12ultra-ctrl/releases) herunterladen und ausführen. Bringt eigenes Python, PyQt6 und `hidapi.dll` mit, keine separate Python-Installation nötig. |
| Debian/Ubuntu (apt-basiert) | `.deb` von Releases herunterladen, dann `sudo apt install ./llano-v12ultra-ctrl_*.deb` |
| Arch-basiert | Selbst bauen aus [`packaging/PKGBUILD`](packaging/PKGBUILD), siehe [`packaging/AUR.md`](packaging/AUR.md). Ein AUR-Paket ist geplant, aber noch nicht veröffentlicht (Status: TBD). |
| Andere Linux-Distros | `.AppImage` von Releases herunterladen, `chmod +x`, direkt ausführen. Keine Installation nötig. Startet standardmäßig die GUI; mit einem CLI-Unterbefehl (z.B. `./llano-v12ultra-ctrl-*.AppImage status`) stattdessen die CLI. |

`.deb`- und Arch-Pakete brauchen trotzdem noch den udev-Regel-Schritt unten. Bei `.deb` erledigt
das ein Postinstall-Hook automatisch, bei Arch pickt udev die Regel beim nächsten Geräte-Event
selbst auf. AppImage und MSI brauchen den Schritt ebenfalls, da sie ohne Root-Rechte laufen und ihn
nicht selbst einrichten können.

### Aus dem Quellcode installieren (pip/pipx)

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

## Sprache

CLI und GUI sind standardmäßig auf Englisch. Deutsch lässt sich wählen über:

- den Sprach-Dropdown oben in der GUI (schreibt in die Config, wirkt nach einem Neustart der App)
- `language = "de"` im Abschnitt `[general]` von `~/.config/llano-v12ultra-ctrl/config.toml`
- die Umgebungsvariable `LLANO_LANGUAGE=de` für einen einzelnen Aufruf, ohne die Config anzufassen:
  ```bash
  LLANO_LANGUAGE=de llano-v12ultra-ctrl status
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

`fan-speed` setzt die Lüfterdrehzahl über ein eigenes HID-Kommando (Wertebereich `1` bis `100`,
jeder Wert eine eigene Stufe von ca. 25 U/min: `raw=1` ergibt 300 U/min, `raw=100` ergibt 2800
U/min). Live verifiziert, jeder einzelne der 100 Werte einzeln getestet (siehe
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

Schaltet die Pad-Farbe je nach CPU-Temperatur um (grün, dann orange, dann rot), mit optionalem
GPU-Temperatur-Alarm (lila/breathing). Siehe Kommentare in
[`config/config.example.toml`](config/config.example.toml). Für Dauerbetrieb als
systemd-User-Service:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/llano-v12ultra-ctrl.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now llano-v12ultra-ctrl.service
```

Die GUI zeigt den Auto-Modus-Status an und kann den Dienst für die laufende Sitzung
pausieren/fortsetzen (`systemctl --user stop/start`). Der Dienst bleibt dabei `enabled` und läuft
nach dem nächsten Login/Neustart normal weiter.

Unter Windows registriert die GUI beim ersten "Fortsetzen"-Klick automatisch eine geplante Aufgabe
(`schtasks`, Trigger "bei Anmeldung", kein Admin nötig) statt eines echten Windows-Diensts. Siehe
[Windows-Status](#windows-status). **Voraussetzung für die Temperaturerkennung:**
[LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) muss laufen
und dessen WMI-Export aktiviert sein. Ohne das bricht `auto` sofort mit "Kein
CPU-Temperatursensor gefunden" ab (live bestätigt).

## Lüfterkurve & Lüfter-Erinnerung

Alle drei Optionen leben im `auto`-Modus (siehe oben). Seit v0.1.3 ist die Lüfterkurve
standardmäßig aktiv (siehe [Hardware-Hintergrund](#hardware-hintergrund)); Lüfter-Erinnerung und
Verlaufsprotokoll bleiben standardmäßig deaktiviert. Konfiguration in
`~/.config/llano-v12ultra-ctrl/config.toml`, siehe kommentierte Beispiele in
[`config/config.example.toml`](config/config.example.toml), oder in der GUI im Bereich
"Lüfterkurve (Automatikmodus)": Punkte per Maus ziehen/hinzufügen/entfernen, `min_change_raw` und
die vollständige Lüfter-Erinnerung (Aktivieren/Temperatur/Drehzahl/Abklingzeit) unter "Erweiterte
Einstellungen" (ebenfalls neu seit v0.1.3). Das Verlaufsprotokoll bleibt reine
Config-Datei-Einstellung, dafür gibt es kein GUI-Formular.

**Lüfterkurve** (`[auto.fan_curve]`): bildet die CPU-Temperatur per linearer Interpolation
zwischen konfigurierten `points` (`temp_c`/`raw`-Paare) auf einen Lüfterdrehzahl-Rohwert ab.
`min_change_raw` verhindert ständiges Nachregeln bei kleinen Temperaturschwankungen, da nur
geschrieben wird, wenn sich der Zielwert um mindestens so viel ändert. Wirkt nur, während `auto`
läuft. Das GUI-Formular speichert nur die Konfiguration - ein laufender `auto`-Daemon (CLI oder der
systemd-/schtasks-Hintergrunddienst) übernimmt die Änderung von selbst innerhalb eines
`poll_interval_s` (kein Neustart nötig, seit v0.1.3).

**Lüfter-Erinnerung** (`[auto.fan_reminder]`): schickt eine Desktop-Benachrichtigung
(`notify-send`), wenn die CPU-Temperatur `temp_c` erreicht, die gemessene Drehzahl aber unter
`min_rpm` bleibt. `cooldown_s` verhindert wiederholte Benachrichtigungen, solange die Bedingung
anhält. Übergangslösung, falls die Lüfterkurve noch nicht aktiviert ist.

**Verlaufsprotokoll** (`[auto.log]`): schreibt bei aktivem `auto`-Modus fortlaufend eine CSV-Zeile
(Zeitstempel, CPU-/GPU-Temperatur, Lüfterdrehzahl, Farbe, Effekt) an den konfigurierten `path`.
Nützlich, um im Nachhinein die eigene Lüfterkurve anhand echter Lastdaten zu verfeinern.

## Windows-Status

| Datei | Status | Anmerkungen |
|---|---|---|
| `device.py` | OK | Live gegen echte Hardware unter Windows 10 getestet (`status`/`light`/`fan-speed`), Lese- und Schreibpfad funktionieren. Braucht zusätzlich die native `hidapi.dll` (nicht im PyPI-Paket `hid` enthalten) irgendwo im DLL-Suchpfad, z.B. neben `python.exe`. Download unter [github.com/libusb/hidapi/releases](https://github.com/libusb/hidapi/releases). |
| `notify.py` | OK | Auf `plyer` umgestellt (cross-platform), live unter Linux getestet. |
| `temp.py` | TEILWEISE | Live getestet, Code funktioniert, bricht aber ohne laufendes [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) (WMI-Export aktiviert) korrekt mit einer klaren Fehlermeldung ab. LibreHardwareMonitor selbst war auf der Testmaschine nicht installiert, der volle Automatikmodus-Regelkreis mit echten Temperaturwerten ist deshalb noch nicht Ende-zu-Ende verifiziert. |
| `gui/service_control.py` | OK | Live getestet. Der `schtasks`-Zweig legt die geplante Aufgabe bei Bedarf automatisch an (`start()`/`stop()`/`is_active()` bestätigt fehlerfrei). Ein Encoding-Bug beim Lesen der `schtasks`-Ausgabe auf einem deutschsprachigen Windows (cp1252 vs. tatsächliche Konsolen-Codepage) wurde dabei gefunden und behoben. |

Rückmeldungen von Windows-Nutzern, insbesondere mit laufendem LibreHardwareMonitor, sind
willkommen (siehe [Beitragen](#beitragen)).

## Paket-Status

| Format | Status | Anmerkungen |
|---|---|---|
| `.msi` (Windows, `packaging/msi/`) | OK | Gebaut per GitHub-Actions-CI (windows-latest, Python 3.12, cx_Freeze). Live getestet auf echter Windows-10-Hardware (`status`/`fan-speed`/CLI funktionieren, "Gerät nicht gefunden" ist korrekt - das Pad war beim Remote-Test nicht angeschlossen). |
| `.deb` (`packaging/deb/`) | OK | Gebaut per CI (fpm), Ende-zu-Ende verifiziert. |
| Arch-`PKGBUILD` (`packaging/PKGBUILD`) | OK | Gebaut per CI (makepkg im archlinux-Container), Ende-zu-Ende verifiziert. Selbst kompilieren: siehe [`packaging/PKGBUILD`](packaging/PKGBUILD)/[`packaging/AUR.md`](packaging/AUR.md). |
| AppImage (`packaging/appimage/`) | OK | Gebaut per CI (appimagetool). Eine .AppImage für alle Linux-Distros ohne eigenes Paket. |
| AUR-Veröffentlichung | TBD | Noch nicht eingereicht. Vollständige, eigenständige Anleitung in [`packaging/AUR.md`](packaging/AUR.md). Selbst kompilieren ohne AUR: siehe oben. |

Alle vier Formate werden im [`release.yml`](.github/workflows/release.yml)
GitHub-Actions-Workflow automatisch bei jedem Push eines `v*`-Tags gebaut und dem jeweiligen
[GitHub Release](https://github.com/Quahuay/llano-v12ultra-ctrl/releases) angehängt.

## Protokoll-Dokumentation

**[PROTOCOL.md](PROTOCOL.md) ist die vollständige Geräte-Referenz** (auf Englisch): jedes Kommando
Byte für Byte, die Prüfsumme, das Telemetrie-Layout, Wertebereiche, beide Transportwege (Linux-ioctl
und Windows-hidapi) sowie lauffähige Minimalbeispiele. So geschrieben, dass man das Pad aus eigenem
Code in beliebiger Sprache ansprechen kann, ohne dieses Projekt zu benutzen. Sie listet außerdem
auf, was getestet wurde und *nicht* funktioniert, damit niemand dieselbe Suche wiederholt.

Die vollständige Herleitung des 9-Byte-HID-Feature-Reports (welches Byte was bedeutet, was
Software-schreibbar vs. reines Telemetrie-Feld ist, Messreihen zu Grenzfällen) steht als
Docstring in [`src/llano_v12ultra_ctrl/protocol.py`](src/llano_v12ultra_ctrl/protocol.py). Der
komplette HID-Report-Descriptor wurde ausgelesen und bestätigt: das Gerät hat exakt drei Reports
und keine versteckten weiteren Report-IDs, nämlich 64-Byte Input, 64-Byte Output und 8-Byte
Feature (vollständig reverse-engineered, inklusive des separaten Fan-Speed-Kommandos). Wie diese
Herleitung entstanden ist, steht in [HISTORY.md](HISTORY.md). `llano-v12ultra-ctrl raw-input`
erlaubt weiteres manuelles Beobachten des Input-Reports.

## Beitragen

Issues und Pull Requests sind willkommen. Insbesondere Rückmeldungen zu anderen
llano-V12-Varianten oder zusätzlichen effect/color-Werten wären hilfreich. Bitte beim Ändern von
`protocol.py`/`device.py` Messreihen oder Belege für neue Erkenntnisse mitliefern, analog zum
bestehenden Dokumentationsstil.

**macOS ist nicht geplant.** Das Pad ist explizit nicht für den Einsatz an Mac-Geräten geeignet.

**Primär gepflegt wird Linux.** Windows-Unterstützung ist ein nachträglich hinzugefügtes Ziel,
keine gleichrangige Plattform. Rückmeldungen und PRs dazu sind trotzdem willkommen, haben aber
nicht dieselbe Priorität wie der Linux-Kernbetrieb.

## Autoren

- [**@Quahuay**](https://github.com/Quahuay) (Maintainer)

## Lizenz

MIT, siehe [LICENSE](LICENSE).

---

*Unabhängiges Community-Projekt, keine Verbindung zum Hersteller/Vertreiber der Marke llano oder*
*von Myth.Cool. Genannte Markennamen dienen nur der Wiedererkennbarkeit, siehe*
*[Hinweis zu Markennamen](#hinweis-zu-markennamen).*
