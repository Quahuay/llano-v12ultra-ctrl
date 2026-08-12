# Roadmap

*[English version](ROADMAP.md)*

Stand v0.1.3: Jede Fähigkeit, die das Hardware-Protokoll tatsächlich hergibt (Farbe, Effekt,
Effekt-Geschwindigkeit, Helligkeit, Lüfterdrehzahl, Power), ist bereits in CLI *und* GUI
verdrahtet — siehe [PROTOCOL.md](PROTOCOL.md) für die vollständige Byte-Referenz und dessen
Abschnitt "Unsupported operations" für das, was am Gerät ausprobiert wurde und nicht geht (freie
RGB-Werte, einzeln adressierbare LEDs, Display-Content-Manipulation). Diese Roadmap holt also
nichts an der Hardware nach, sondern beschreibt, was sich sinnvoll auf einem fertigen
Protokoll-Mapping aufbauen lässt.

Nur der nächste Meilenstein bekommt eine Versionsnummer. Alles danach ist bewusst nach Thema statt
nach Release gruppiert — das ist ein junges Solo-Projekt, eine datierte Mehr-Versionen-Roadmap
würde sich selbst gegenüber der Öffentlichkeit überversprechen. Siehe
[Beitragen](README.de.md#beitragen), wie man mitreden kann: GitHub Issues und PRs sind der Weg,
wie Punkte hier aufgegriffen, verfeinert oder umpriorisiert werden. Passende
[GitHub Milestones](https://github.com/Quahuay/llano-v12ultra-ctrl/milestones) existieren zu den
Abschnitten unten, damit sich Issues daran einhängen lassen.

## v0.2.0

- **Automatikmodus-GUI fertigstellen** — `[auto.gpu_alert]` und `[auto.log]` existieren aktuell
  nur als config.toml-Abschnitte ohne GUI-Formular (anders als Lüfterkurve und Lüfter-Erinnerung,
  die ihres in v0.1.3 bekommen haben). Der in v0.1.3 gebaute Config-Hot-Reload deckt bereits ab,
  was hier ergänzt wird — damit ist das der günstigste verbleibende Teil dieser Arbeit.
- **`--json`-Output für `status` und `monitor`** — kleinstmöglicher Diff, und die ehrliche
  Voraussetzung für jede Scripting-Integration (siehe "Integration & Scripting" unten), statt
  direkt zu einem Broker oder einer eigenen API-Schicht zu springen.
- **System-Tray-Icon** — aktuell gibt es null Tray-Code in der GUI. Der Automatikmodus-Daemon
  läuft bereits headless (systemd-User-Service / Windows Scheduled Task), aber das GUI-Fenster
  selbst hat weder Minimize-to-Tray noch einen Schnellzugriff. Größte Lücke zwischen dem, was die
  App ist, und wie sie sich verhält.
- **Vordefinierte Lüfterkurven-Presets** ("Standardprogramme", z.B. Silent/Balanced/Performance),
  möglicherweise nach Regelcharakteristik unterschieden (wie aggressiv auf Temperaturänderung
  reagiert wird), nicht nur nach unterschiedlichen Punktmengen. Umfang/Detailtiefe noch offen.
- **Profile um Automatik-/Lüfterkurven-Konfiguration erweitern, nicht nur manuelle Werte** —
  `profiles.py` speichert aktuell Farbe/Effekt/Speed/Helligkeit/Power/Lüfter-Rohwert als statische
  Werte. Ein Profil auch um vollständige Automatik-Konfigurationen zu erweitern (und dazwischen
  umzuschalten) ist ein naheliegender Folgeschritt, sobald es Kurven-Presets gibt.
- **Portable Windows-Version (ohne Installer)** — aktuell gibt es nur die `.msi`. cx_Freeze
  erzeugt dafür bereits als Zwischenschritt einen eigenständigen `build/exe.win-*/`-Ordner, bevor
  er zur MSI verpackt wird (`packaging/msi/cx_freeze_setup.py`); diesen Ordner zusätzlich als ZIP
  anzubieten braucht kein neues Build-Tooling, nur einen weiteren Schritt im bereits bestehenden
  `msi`-Job in [`release.yml`](.github/workflows/release.yml).

## Später (ohne Versionsnummer)

### Integration & Scripting
Baut auf `--json` oben auf, statt direkt dahin vorzugreifen.
- MQTT-Publish (Temperatur-/Lüfter-/RPM-Telemetrie + ein Command-Topic) für Home Assistant und
  Ähnliches
- Shell-Completion (bash/zsh/fish) für die CLI
- Beispiel-Modul für Waybar/Polybar/i3status auf Basis von `--json`
- Anschluss an offene RGB-Ökosystem-Standards (z.B. OpenRGB), damit sich das Pad zusammen mit
  anderer RGB-Peripherie koordinieren lässt statt nur eigenständig
- Musik-/Audio-reaktive Beleuchtung (Farbe/Effekt an Audio-Analyse gekoppelt)

### Desktop-Integration
- Autostart der GUI selbst beim Login (getrennt vom Automatikmodus-Hintergrunddienst, der bereits
  heute automatisch startet)
- Minimize-to-Tray, aufbauend auf dem Tray-Icon aus v0.2.0

### Qualität & Wartung
- Weitere Sprachen über das aktuelle Englisch/Deutsch hinaus
- Linting (z.B. ruff) als CI-Job, nicht nur die bestehende Test-Matrix
- Barrierefreiheits-Durchgang der GUI (Screenreader-Labels, Tastaturnavigation)

## Übernommen aus v0.1.x

Keine neuen Features — offene Punkte aus dem vorherigen Zyklus, die noch offen sind:
- **AUR-Einreichung** — braucht das AUR-Konto des Maintainers, kein Code-Task. Selbst kompilieren
  via `makepkg` funktioniert bereits und ist dokumentiert
  ([`packaging/AUR.md`](packaging/AUR.md)).
- **Windows-Automatikmodus Ende-zu-Ende-Verifikation** — `temp.py` bricht korrekt mit einer
  Fehlermeldung ab, wenn [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor)
  nicht läuft, aber der volle temperaturgesteuerte Regelkreis mit echten Werten ist damit noch
  nicht verifiziert (siehe [Windows-Status](README.de.md#windows-status)). Braucht eine
  Windows-Maschine mit tatsächlich laufendem LibreHardwareMonitor, also Feedback aus der
  Community — siehe [Beitragen](README.de.md#beitragen).

## Explizit nicht geplant

- **macOS** — nicht geplant, siehe [README](README.de.md#beitragen): das Pad ist für Mac-Hardware
  nicht geeignet.
- **Mehrgeräte-Support** (mehrere angeschlossene Pads unterscheiden, oder andere llano-V12-
  Hardware-Varianten jenseits der Ultra unterstützen) — nicht umsetzbar ohne diese zusätzliche
  Hardware vor Ort zum Testen. Würde die Geräteauswahl-Logik in `device.py` auf beiden Plattformen
  und das Config-Schema anfassen (aktuell existiert nirgends ein Geräte-Identifier) — also schon
  vor der Hardware-Zugriffsfrage eine übergreifende Änderung. Feedback zu anderen Varianten ist
  weiterhin willkommen (siehe [Beitragen](README.de.md#beitragen)) — ausgeklammert aus der aktiven
  Planung, nicht aus dem Interesse.
- **Freie/beliebige RGB-Werte, einzeln adressierbare LEDs, Display-Content-Manipulation** — keine
  Software-Lücke, das Gerät selbst unterstützt das nicht; siehe PROTOCOL.md's
  ["Unsupported operations"](PROTOCOL.md) und HISTORY.md's "Checked afterwards, but not pursued
  further" für das, was tatsächlich probiert wurde.
