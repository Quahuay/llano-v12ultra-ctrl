# Roadmap

*[English version](../en/ROADMAP.md)*

Stand v0.1.3: Jede Fähigkeit, die das Hardware-Protokoll tatsächlich hergibt (Farbe, Effekt,
Effekt-Geschwindigkeit, Helligkeit, Lüfterdrehzahl, Power), ist bereits in CLI *und* GUI
verdrahtet. Siehe [PROTOCOL.md](../en/PROTOCOL.md) für die vollständige Byte-Referenz und dessen
Abschnitt "Unsupported operations" für das, was am Gerät ausprobiert wurde und nicht geht (freie
RGB-Werte, einzeln adressierbare LEDs, Display-Content-Manipulation). Diese Roadmap holt also
nichts an der Hardware nach. Sie beschreibt, was sich sinnvoll auf einem fertigen
Protokoll-Mapping aufbauen lässt.

Nur der nächste Meilenstein bekommt eine Versionsnummer. Alles danach ist bewusst nach Thema statt
nach Release gruppiert. Der Grund: das ist ein junges Solo-Projekt, und eine datierte
Mehr-Versionen-Roadmap würde sich selbst gegenüber der Öffentlichkeit überversprechen. Siehe
[Beitragen](README.md#beitragen), wie man mitreden kann. GitHub Issues und PRs sind der Weg, wie
Punkte hier aufgegriffen, verfeinert oder umpriorisiert werden. Passende
[GitHub Milestones](https://github.com/Quahuay/llano-v12ultra-ctrl/milestones) existieren zu den
Abschnitten unten, damit sich Issues daran einhängen lassen.

## v0.2.0

- **Automatikmodus-GUI fertigstellen.** `[auto.gpu_alert]` und `[auto.log]` existieren aktuell nur
  als config.toml-Abschnitte ohne GUI-Formular, anders als Lüfterkurve und Lüfter-Erinnerung, die
  ihres in v0.1.3 bekommen haben. Der in v0.1.3 gebaute Config-Hot-Reload deckt bereits ab, was
  hier ergänzt wird, damit ist das der günstigste verbleibende Teil dieser Arbeit.
- **`--json`-Output für `status` und `monitor`.** Kleinstmöglicher Diff und die ehrliche
  Voraussetzung für jede Scripting-Integration (siehe "Integration & Scripting" unten), statt
  direkt zu einem Broker oder einer eigenen API-Schicht zu springen.
- **System-Tray-Icon.** Aktuell gibt es null Tray-Code in der GUI. Der Automatikmodus-Daemon läuft
  bereits headless als systemd-User-Service oder Windows Scheduled Task, aber das GUI-Fenster
  selbst hat weder Minimize-to-Tray noch einen Schnellzugriff. Das ist die größte Lücke zwischen
  dem, was die App ist, und wie sie sich verhält.
- **Vordefinierte Lüfterkurven-Presets** wie Silent, Balanced und Performance als
  "Standardprogramme", möglicherweise nach Regelcharakteristik unterschieden (wie aggressiv auf
  Temperaturänderung reagiert wird), nicht nur nach unterschiedlichen Punktmengen. Umfang und
  Detailtiefe sind noch offen.
- **Profile, die Automatik- und Lüfterkurven-Konfiguration abdecken, nicht nur manuelle Werte.**
  `profiles.py` speichert aktuell Farbe, Effekt, Speed, Helligkeit, Power und Lüfter-Rohwert als
  statische Werte. Ein Profil auch um vollständige Automatik-Konfigurationen zu erweitern und
  dazwischen umzuschalten ist ein naheliegender Folgeschritt, sobald es Kurven-Presets gibt.
- **Portable Windows-Version ohne Installer.** Aktuell gibt es nur die `.msi`. cx_Freeze erzeugt
  dafür bereits als Zwischenschritt einen eigenständigen `build/exe.win-*/`-Ordner, bevor er zur
  MSI verpackt wird (`packaging/msi/cx_freeze_setup.py`). Diesen Ordner zusätzlich als ZIP
  anzubieten braucht kein neues Build-Tooling, nur einen weiteren Schritt im bereits bestehenden
  `msi`-Job in [`release.yml`](../.github/workflows/release.yml).

## Später, ohne Versionsnummer

### Integration & Scripting
Baut auf `--json` oben auf, statt direkt dahin vorzugreifen.
- MQTT-Publish (Temperatur-, Lüfter- und RPM-Telemetrie plus ein Command-Topic) für Home Assistant
  und Ähnliches
- Shell-Completion (bash/zsh/fish) für die CLI
- Ein Beispiel-Modul für Waybar/Polybar/i3status auf Basis von `--json`
- Anschluss an offene RGB-Ökosystem-Standards wie OpenRGB, damit sich das Pad zusammen mit anderer
  RGB-Peripherie koordinieren lässt statt nur eigenständig
- Musik- und audio-reaktive Beleuchtung, Farbe und Effekt an Audio-Analyse gekoppelt

### Desktop-Integration
- Autostart der GUI selbst beim Login, getrennt vom Automatikmodus-Hintergrunddienst, der bereits
  heute automatisch startet
- Minimize-to-Tray, aufbauend auf dem Tray-Icon aus v0.2.0

### Qualität & Wartung
- Weitere Sprachen über das aktuelle Englisch/Deutsch hinaus
- Linting, etwa ruff, als CI-Job, nicht nur die bestehende Test-Matrix
- Ein Barrierefreiheits-Durchgang der GUI: Screenreader-Labels, Tastaturnavigation

## Übernommen aus v0.1.x

Das sind keine neuen Features, sondern offene Punkte aus dem vorherigen Zyklus.

- **AUR-Einreichung.** Braucht das AUR-Konto des Maintainers, kein Code-Task. Selbst kompilieren
  via `makepkg` funktioniert bereits und ist dokumentiert
  ([`packaging/AUR.md`](../packaging/AUR.md)).
- **Windows-Automatikmodus Ende-zu-Ende-Verifikation.** `temp.py` bricht korrekt mit einer
  Fehlermeldung ab, wenn [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor)
  nicht läuft, aber der volle temperaturgesteuerte Regelkreis mit echten Werten ist damit noch
  nicht verifiziert (siehe [Windows-Status](README.md#windows-status)). Das braucht eine
  Windows-Maschine mit tatsächlich laufendem LibreHardwareMonitor, also Feedback aus der
  Community. Siehe [Beitragen](README.md#beitragen).

## Explizit nicht geplant

- **macOS.** Nicht geplant, siehe [README](README.md#beitragen): das Pad ist für Mac-Hardware
  nicht geeignet.
- **Mehrgeräte-Support**, also mehrere angeschlossene Pads unterscheiden oder andere
  llano-V12-Hardware-Varianten jenseits der Ultra unterstützen. Nicht umsetzbar ohne diese
  zusätzliche Hardware vor Ort zum Testen. Es würde außerdem die Geräteauswahl-Logik in
  `device.py` auf beiden Plattformen und das Config-Schema anfassen, da aktuell nirgends ein
  Geräte-Identifier existiert, also schon vor der Hardware-Zugriffsfrage eine übergreifende
  Änderung. Feedback zu anderen Varianten ist weiterhin willkommen (siehe
  [Beitragen](README.md#beitragen)); ausgeklammert aus der aktiven Planung, nicht aus dem
  Interesse.
- **Freie oder beliebige RGB-Werte, einzeln adressierbare LEDs, Display-Content-Manipulation.**
  Keine Software-Lücke: das Gerät selbst unterstützt das nicht. Siehe PROTOCOL.md's
  ["Unsupported operations"](../en/PROTOCOL.md) und HISTORY.md's "Checked afterwards, but not
  pursued further" für das, was tatsächlich probiert wurde.
