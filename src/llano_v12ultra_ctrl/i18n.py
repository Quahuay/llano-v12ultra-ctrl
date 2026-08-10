"""Minimale Übersetzungsschicht für llano-v12ultra-ctrl.

Standardsprache: Englisch. Deutsch lässt sich wählen über (in dieser
Priorität):

1. Umgebungsvariable `LLANO_LANGUAGE=de` (überschreibt alles andere -
   praktisch für einen einzelnen Aufruf, ohne die Config anzufassen)
2. `[general] language = "de"` in config.toml
3. Fallback: Englisch

Bewusst KEIN gettext/.po/.mo-Tooling - das ist für den überschaubaren,
festen String-Umfang dieses Projekts mehr Infrastruktur als nötig. Ein
simples Dict pro Sprache ist einfacher zu lesen, zu diffen und bei PRs zu
reviewen als ein Kompilierschritt.

Nutzung: `from . import i18n` dann `i18n.t("key", **werte)`. Fehlt ein Key
in der aktiven Sprache, wird auf Englisch zurückgefallen; fehlt er auch
dort, wird der Key selbst zurückgegeben (nie ein KeyError zur Laufzeit)."""

import os

DEFAULT_LANGUAGE = "en"
AVAILABLE_LANGUAGES = ("en", "de")

_forced_language = None  # per set_language() erzwungen, z.B. GUI-Dropdown

# ---------------------------------------------------------------- Englisch

_EN = {
    # --- gemeinsam (CLI + GUI) ---
    "common.on": "ON",
    "common.off": "OFF",
    "common.yes": "yes",
    "common.no": "NO",

    # --- cli: status ---
    "cli.status.device": "Device:       {path}",
    "cli.status.raw_report": "Raw report:   {hex}",
    "cli.status.checksum_ok": "Checksum ok:  {ok}",
    "cli.status.power": "Overall unit (fan+light, via 'power' command):  {state}",
    "cli.status.fan_speed": "Fan speed:    {rpm} RPM (raw={raw})",
    "cli.status.light": "Light:        {state}",
    "cli.status.color": "Color:        {color}  [{name}]",
    "cli.status.effect": "Effect:       {effect}  [{name}]",
    "cli.status.speed": "Speed:        {speed}  (not monotonic, see protocol.py for details)",
    "cli.status.brightness": "Brightness:   {brightness}  (0=dark, 255=max bright)",

    # --- cli: general errors ---
    "cli.error.invalid_choice": "Invalid {label} '{value}'. Allowed: 0-4 or {names}",
    "cli.error.choice_range": "{label} must be between 0 and 4",
    "cli.error.generic": "Error: {error}",
    "cli.label.color": "color",
    "cli.label.effect": "effect",

    # --- cli: light ---
    "cli.light.off_done": "Light turned off, fan unaffected (raw={raw})",
    "cli.light.set_done": "Set: color={color} [{cname}]  effect={effect} [{ename}]  speed={speed}  brightness={brightness}  (raw={raw})",

    # --- cli: power ---
    "cli.power.on_done": "Overall unit ON (fan + light running again, raw={raw})",
    "cli.power.off_done": "Overall unit OFF (fan AND light fully stopped, raw={raw})",

    # --- cli: fan-speed ---
    "cli.fan_speed.set_done": "Fan speed set to raw={raw} -> report shows {rpm} RPM (raw={raw2})",

    # --- cli: monitor ---
    "cli.monitor.watching": "Watching live telemetry (Ctrl+C to stop)...",
    "cli.monitor.line": "[{ts}] {rpm:>4} RPM  color={color} [{cname}]  effect={effect} [{ename}]  speed={speed}  raw={raw}",

    # --- cli: raw-input ---
    "cli.raw_input.intro": (
        "Watching raw 64-byte input report (Ctrl+C to stop).\n"
        "Diagnostic command: per the analysis so far (see protocol.py) with "
        "no known content-dependent effect/meaning - purely for manual "
        "exploration, nothing is written."
    ),
    "cli.raw_input.line": "[{ts}] {raw}",

    # --- cli: auto ---
    "cli.auto.no_sensor": "No CPU temperature sensor found (coretemp/k10temp). Aborting.",
    "cli.auto.sensor": "Temperature sensor: {path}",
    "cli.auto.thresholds": "Thresholds: {thresholds}  Hysteresis: {hysteresis}°C  Interval: {interval}s",
    "cli.auto.gpu_alert": (
        "GPU alert: from {temp_c}°C (off at {off_temp_c}°C) "
        "-> color={color} effect={effect} (only if GPU >= CPU, 'whichever is hotter wins')"
    ),
    "cli.auto.fan_reminder": (
        "Fan reminder: from {temp_c}°C if speed < {min_rpm} RPM (cooldown {cooldown_s}s)."
    ),
    "cli.auto.fan_curve": "Fan curve: active ({points}), min_change_raw={min_change}",
    "cli.auto.log_path": "History log: {path}",
    "cli.auto.color_change": "[{ts}] CPU={cpu_info}{gpu_info} -> {color_name} [{effect_name}]",
    "cli.auto.fan_curve_change": "[{ts}] CPU={temp:.1f}°C -> fan curve: raw={raw} ({rpm} RPM)",
    "cli.auto.notify_title": "llano-v12ultra-ctrl: fan too slow",
    "cli.auto.notify_body": "CPU {temp:.0f}°C, but only {rpm} RPM. Turn the wheel on the pad up manually?",

    # --- cli: argparse ---
    "cli.parser.description": "Control tool for the llano V12 Ultra cooling pad (Myth.Cool / Holtek 374a:b101)",
    "cli.parser.status.help": "show current device state (color/effect/speed + live telemetry)",
    "cli.parser.light.help": "control lighting (color/effect/speed/off)",
    "cli.parser.light.color.help": "0-4 or red/lightblue/green/purple/orange",
    "cli.parser.light.effect.help": "0-4 or solid/breathing/rainbow/chase/zones",
    "cli.parser.light.speed.help": "0-3 officially used (0=fast..3=slow). Values 4-255 are technically possible but never validated by the original app and not monotonic (see protocol.py)",
    "cli.parser.light.brightness.help": "0-255 (0=dark, 255=max bright)",
    "cli.parser.light.off.help": "turn off the light",
    "cli.parser.power.help": "turn the whole unit (fan+light) fully on/off - pure kill switch, no in-between",
    "cli.parser.fan_speed.help": "set fan speed (dedicated fan command, see protocol.py NACHTRAG 8)",
    "cli.parser.fan_speed.raw.help": "1-100",
    "cli.parser.monitor.help": "continuously show live telemetry",
    "cli.parser.monitor.interval.help": "poll interval in seconds (default 0.3)",
    "cli.parser.raw_input.help": "watch raw 64-byte input report (diagnostic/exploration, read-only)",
    "cli.parser.raw_input.timeout.help": "timeout per read in seconds (default 0.2)",
    "cli.parser.auto.help": "start the temperature-based auto-color daemon (visual temperature indicator)",
    "cli.parser.auto.config.help": "path to config.toml (default ~/.config/llano-v12ultra-ctrl/config.toml)",

    # --- device.py ---
    "device.not_found_linux": "llano V12 Ultra (374a:b101) not found. Is the pad plugged in and the udev rule installed?",
    "device.not_found_windows": "llano V12 Ultra (374a:b101) not found. Is the pad plugged in?",
    "device.open_error": "Device error while opening: {error}",
    "device.call_error": "Device error (possibly unplugged): {error}",

    # --- gui: window/general ---
    "gui.window_title": "llano-v12ultra-ctrl",
    "gui.status_bar.ready": "Ready",
    "gui.status_bar.connected": "Connected",
    "gui.status_bar.disconnected": "Disconnected",
    "gui.disconnect_banner": "⚠ Device not found. Is the pad plugged in?",

    # --- gui: status table ---
    "gui.status.title": "Status",
    "gui.status.field.device": "Device",
    "gui.status.field.fan_speed": "Fan speed",
    "gui.status.field.power": "Overall unit",
    "gui.status.field.light": "Light",
    "gui.status.field.color": "Color",
    "gui.status.field.effect": "Effect",
    "gui.status.field.speed": "Speed",
    "gui.status.field.brightness": "Brightness",
    "gui.status.field.raw": "Raw data",
    "gui.status.field.checksum": "Checksum ok",

    # --- gui: rpm history ---
    "gui.rpm_history.title": "RPM History",

    # --- gui: control group ---
    "gui.control.title": "Controls",
    "gui.control.color": "Color:",
    "gui.control.effect": "Effect:",
    "gui.control.speed": "Speed:",
    "gui.control.brightness": "Brightness:",
    "gui.control.light_on": "Turn light OFF",
    "gui.control.light_off": "Turn light ON",
    "gui.control.power_on": "Turn overall unit OFF",
    "gui.control.power_off": "Turn overall unit ON",
    "gui.speed_label.0": "0 (fast)",
    "gui.speed_label.1": "1 (medium)",
    "gui.speed_label.2": "2 (slow)",
    "gui.speed_label.3": "3 (very slow)",

    # --- gui: fan speed group ---
    "gui.fan_speed.title": "Fan Speed",
    "gui.fan_speed.apply": "Apply",

    # --- gui: profiles ---
    "gui.profiles.title": "Profiles",
    "gui.profiles.empty": "(empty)",
    "gui.profiles.apply": "Apply",
    "gui.profiles.save": "Save…",
    "gui.profiles.delete": "Delete",
    "gui.profiles.default_name": "Profile {n}",
    "gui.profiles.save_dialog.title": "Save profile",
    "gui.profiles.save_dialog.label": "Name:",
    "gui.profiles.save_done": "Profile \"{name}\" saved",
    "gui.profiles.apply_done": "Profile \"{name}\" applied",
    "gui.profiles.delete_dialog.title": "Delete profile",
    "gui.profiles.delete_dialog.text": "Really delete profile \"{name}\"?",

    # --- gui: fan curve ---
    "gui.fan_curve.title": "Fan Curve (Auto Mode)",
    "gui.fan_curve.enable": "Enable fan curve",
    "gui.fan_curve.hint": "Drag a point to move it, click empty space = new point, right-click = remove.",
    "gui.fan_curve.advanced_collapsed": "Advanced Settings ▸",
    "gui.fan_curve.advanced_expanded": "Advanced Settings ▾",
    "gui.fan_curve.table.temp": "Temperature (°C)",
    "gui.fan_curve.table.raw": "Fan speed (raw 1-100)",
    "gui.fan_curve.add_point": "Add point",
    "gui.fan_curve.remove_point": "Remove selected point",
    "gui.fan_curve.save": "Save",
    "gui.fan_curve.save_error_title": "Fan curve",
    "gui.fan_curve.save_error_text": "At least one point is required.",
    "gui.fan_curve.save_done": "Fan curve saved (takes effect next time 'auto' starts)",

    # --- gui: auto group ---
    "gui.auto.title": "Auto Mode (Temperature)",
    "gui.auto.status.unknown": "Status: unknown",
    "gui.auto.status.active": "Status: active",
    "gui.auto.status.paused": "Status: paused",
    "gui.auto.pause": "Pause",
    "gui.auto.resume": "Resume",
    "gui.auto.warning": "Note: Auto mode is active. Manual changes may be overwritten again within a few seconds.",
    "gui.auto.hint": "Pausing only applies to this session. The service stays enabled and runs normally again after the next login/restart.",

    # --- gui: language ---
    "gui.language.title": "Language",
    "gui.language.restart_hint": "Takes effect after restarting the app.",
    "gui.language.en": "English",
    "gui.language.de": "Deutsch",
}

# ------------------------------------------------------------------ Deutsch

_DE = {
    "common.on": "AN",
    "common.off": "AUS",
    "common.yes": "ja",
    "common.no": "NEIN",

    "cli.status.device": "Gerät:        {path}",
    "cli.status.raw_report": "Raw-Report:   {hex}",
    "cli.status.checksum_ok": "Checksum ok:  {ok}",
    "cli.status.power": "Gesamteinheit (Lüfter+Licht, per 'power'-Befehl):  {state}",
    "cli.status.fan_speed": "Lüfterdrehzahl: {rpm} U/min (raw={raw})",
    "cli.status.light": "Beleuchtung:  {state}",
    "cli.status.color": "Farbe:        {color}  [{name}]",
    "cli.status.effect": "Effekt:       {effect}  [{name}]",
    "cli.status.speed": "Geschwindigkeit: {speed}  (nicht monoton, siehe protocol.py für Details)",
    "cli.status.brightness": "Helligkeit:   {brightness}  (0=dunkel, 255=maximal hell)",

    "cli.error.invalid_choice": "Ungültiger {label} '{value}'. Erlaubt: 0-4 oder {names}",
    "cli.error.choice_range": "{label} muss zwischen 0 und 4 liegen",
    "cli.error.generic": "Fehler: {error}",
    "cli.label.color": "Farbe",
    "cli.label.effect": "Effekt",

    "cli.light.off_done": "Beleuchtung ausgeschaltet, Lüfter unbeeinflusst (raw={raw})",
    "cli.light.set_done": "Gesetzt: color={color} [{cname}]  effect={effect} [{ename}]  speed={speed}  brightness={brightness}  (raw={raw})",

    "cli.power.on_done": "Gesamteinheit AN (Lüfter + Licht laufen wieder, raw={raw})",
    "cli.power.off_done": "Gesamteinheit AUS (Lüfter UND Licht komplett gestoppt, raw={raw})",

    "cli.fan_speed.set_done": "Lüfterdrehzahl auf raw={raw} gesetzt -> Report zeigt {rpm} U/min (raw={raw2})",

    "cli.monitor.watching": "Beobachte Live-Telemetrie (Strg+C zum Beenden)...",
    "cli.monitor.line": "[{ts}] {rpm:>4} U/min  color={color} [{cname}]  effect={effect} [{ename}]  speed={speed}  raw={raw}",

    "cli.raw_input.intro": (
        "Beobachte rohen 64-Byte Input-Report (Strg+C zum Beenden).\n"
        "Diagnose-Befehl: laut bisheriger Analyse (siehe protocol.py) ohne "
        "bekannten inhaltsabhängigen Effekt/Bedeutung - rein zum manuellen "
        "Explorieren, es wird nichts geschrieben."
    ),
    "cli.raw_input.line": "[{ts}] {raw}",

    "cli.auto.no_sensor": "Kein CPU-Temperatursensor gefunden (coretemp/k10temp). Abbruch.",
    "cli.auto.sensor": "Temperatursensor: {path}",
    "cli.auto.thresholds": "Schwellen: {thresholds}  Hysterese: {hysteresis}°C  Intervall: {interval}s",
    "cli.auto.gpu_alert": (
        "GPU-Alarm: ab {temp_c}°C (aus bei {off_temp_c}°C) "
        "-> color={color} effect={effect} (nur wenn GPU >= CPU, 'wer wärmer ist gewinnt')"
    ),
    "cli.auto.fan_reminder": (
        "Lüfter-Erinnerung: ab {temp_c}°C wenn Drehzahl < {min_rpm} U/min (Cooldown {cooldown_s}s)."
    ),
    "cli.auto.fan_curve": "Lüfterkurve: aktiv ({points}), min_change_raw={min_change}",
    "cli.auto.log_path": "Verlaufsprotokoll: {path}",
    "cli.auto.color_change": "[{ts}] CPU={cpu_info}{gpu_info} -> {color_name} [{effect_name}]",
    "cli.auto.fan_curve_change": "[{ts}] CPU={temp:.1f}°C -> Lüfterkurve: raw={raw} ({rpm} U/min)",
    "cli.auto.notify_title": "llano-v12ultra-ctrl: Lüfter zu langsam",
    "cli.auto.notify_body": "CPU {temp:.0f}°C, aber nur {rpm} U/min. Rad am Pad manuell hochdrehen?",

    "cli.parser.description": "Steuerung für das llano V12 Ultra Kühlpad (Myth.Cool / Holtek 374a:b101)",
    "cli.parser.status.help": "aktuellen Gerätezustand anzeigen (Farbe/Effekt/Geschwindigkeit + Live-Telemetrie)",
    "cli.parser.light.help": "Beleuchtung steuern (Farbe/Effekt/Geschwindigkeit/Aus)",
    "cli.parser.light.color.help": "0-4 oder red/lightblue/green/purple/orange",
    "cli.parser.light.effect.help": "0-4 oder solid/breathing/rainbow/chase/zones",
    "cli.parser.light.speed.help": "0-3 offiziell genutzt (0=schnell..3=langsam). Werte 4-255 technisch möglich, aber von der Original-App nie validiert und nicht monoton (siehe protocol.py)",
    "cli.parser.light.brightness.help": "0-255 (0=dunkel, 255=maximal hell)",
    "cli.parser.light.off.help": "Beleuchtung ausschalten",
    "cli.parser.power.help": "Gesamte Einheit (Lüfter+Licht) komplett an/aus schalten - reiner Kill-Switch, keine Zwischenstufen",
    "cli.parser.fan_speed.help": "Lüfterdrehzahl setzen (eigenes Fan-Kommando, siehe protocol.py NACHTRAG 8)",
    "cli.parser.fan_speed.raw.help": "1-100",
    "cli.parser.monitor.help": "Live-Telemetrie laufend anzeigen",
    "cli.parser.monitor.interval.help": "Poll-Intervall in Sekunden (default 0.3)",
    "cli.parser.raw_input.help": "Rohen 64-Byte Input-Report beobachten (Diagnose/Exploration, nur Lesen)",
    "cli.parser.raw_input.timeout.help": "Timeout pro Lesevorgang in Sekunden (default 0.2)",
    "cli.parser.auto.help": "Temperaturbasierten Auto-Farb-Daemon starten (visueller Temperatur-Indikator)",
    "cli.parser.auto.config.help": "Pfad zur config.toml (default ~/.config/llano-v12ultra-ctrl/config.toml)",

    "device.not_found_linux": "llano V12 Ultra (374a:b101) nicht gefunden. Ist das Pad angeschlossen und die udev-Regel installiert?",
    "device.not_found_windows": "llano V12 Ultra (374a:b101) nicht gefunden. Ist das Pad angeschlossen?",
    "device.open_error": "Gerätefehler beim Öffnen: {error}",
    "device.call_error": "Gerätefehler (evtl. abgesteckt): {error}",

    "gui.window_title": "llano-v12ultra-ctrl",
    "gui.status_bar.ready": "Bereit",
    "gui.status_bar.connected": "Verbunden",
    "gui.status_bar.disconnected": "Getrennt",
    "gui.disconnect_banner": "⚠ Gerät nicht gefunden. Ist das Pad angeschlossen?",

    "gui.status.title": "Status",
    "gui.status.field.device": "Gerät",
    "gui.status.field.fan_speed": "Lüfterdrehzahl",
    "gui.status.field.power": "Gesamteinheit",
    "gui.status.field.light": "Beleuchtung",
    "gui.status.field.color": "Farbe",
    "gui.status.field.effect": "Effekt",
    "gui.status.field.speed": "Geschwindigkeit",
    "gui.status.field.brightness": "Helligkeit",
    "gui.status.field.raw": "Rohdaten",
    "gui.status.field.checksum": "Checksum ok",

    "gui.rpm_history.title": "RPM-Verlauf",

    "gui.control.title": "Steuerung",
    "gui.control.color": "Farbe:",
    "gui.control.effect": "Effekt:",
    "gui.control.speed": "Geschwindigkeit:",
    "gui.control.brightness": "Helligkeit:",
    "gui.control.light_on": "Beleuchtung AUS",
    "gui.control.light_off": "Beleuchtung AN",
    "gui.control.power_on": "Gesamteinheit AUS",
    "gui.control.power_off": "Gesamteinheit AN",
    "gui.speed_label.0": "0 (schnell)",
    "gui.speed_label.1": "1 (mittel)",
    "gui.speed_label.2": "2 (langsam)",
    "gui.speed_label.3": "3 (sehr langsam)",

    "gui.fan_speed.title": "Fan-Speed",
    "gui.fan_speed.apply": "Anwenden",

    "gui.profiles.title": "Profile",
    "gui.profiles.empty": "(leer)",
    "gui.profiles.apply": "Anwenden",
    "gui.profiles.save": "Speichern…",
    "gui.profiles.delete": "Löschen",
    "gui.profiles.default_name": "Profil {n}",
    "gui.profiles.save_dialog.title": "Profil speichern",
    "gui.profiles.save_dialog.label": "Name:",
    "gui.profiles.save_done": "Profil \"{name}\" gespeichert",
    "gui.profiles.apply_done": "Profil \"{name}\" angewendet",
    "gui.profiles.delete_dialog.title": "Profil löschen",
    "gui.profiles.delete_dialog.text": "Profil \"{name}\" wirklich löschen?",

    "gui.fan_curve.title": "Lüfterkurve (Automatikmodus)",
    "gui.fan_curve.enable": "Lüfterkurve aktivieren",
    "gui.fan_curve.hint": "Punkt ziehen = verschieben, Klick auf freie Fläche = neuer Punkt, Rechtsklick = entfernen.",
    "gui.fan_curve.advanced_collapsed": "Erweiterte Einstellungen ▸",
    "gui.fan_curve.advanced_expanded": "Erweiterte Einstellungen ▾",
    "gui.fan_curve.table.temp": "Temperatur (°C)",
    "gui.fan_curve.table.raw": "Drehzahl (raw 1-100)",
    "gui.fan_curve.add_point": "Punkt hinzufügen",
    "gui.fan_curve.remove_point": "Ausgewählten Punkt entfernen",
    "gui.fan_curve.save": "Speichern",
    "gui.fan_curve.save_error_title": "Lüfterkurve",
    "gui.fan_curve.save_error_text": "Mindestens ein Punkt wird benötigt.",
    "gui.fan_curve.save_done": "Lüfterkurve gespeichert (wirkt beim nächsten Start von 'auto')",

    "gui.auto.title": "Automatikmodus (Temperatur)",
    "gui.auto.status.unknown": "Status: unbekannt",
    "gui.auto.status.active": "Status: aktiv",
    "gui.auto.status.paused": "Status: pausiert",
    "gui.auto.pause": "Pausieren",
    "gui.auto.resume": "Fortsetzen",
    "gui.auto.warning": "Hinweis: Automatikmodus aktiv. Manuelle Änderungen können innerhalb weniger Sekunden wieder überschrieben werden.",
    "gui.auto.hint": "Pausieren gilt nur für diese Sitzung. Der Dienst bleibt aktiviert und läuft nach dem nächsten Login/Neustart normal weiter.",

    "gui.language.title": "Sprache",
    "gui.language.restart_hint": "Wirkt nach einem Neustart der Anwendung.",
    "gui.language.en": "English",
    "gui.language.de": "Deutsch",
}

_TRANSLATIONS = {"en": _EN, "de": _DE}


def available_languages():
    return AVAILABLE_LANGUAGES


def set_language(lang):
    """Erzwingt eine Sprache für den Rest des Prozesses (z.B. vom GUI-
    Sprachauswahlmenü oder von main() nach dem Auflösen von Config/Env
    aufgerufen). `lang` außerhalb von AVAILABLE_LANGUAGES fällt still auf
    Englisch zurück."""
    global _forced_language
    _forced_language = lang if lang in _TRANSLATIONS else DEFAULT_LANGUAGE


def resolve_language(config=None):
    """Ermittelt die aktive Sprache nach der Priorität aus dem Moduldoc:
    LLANO_LANGUAGE-Env-Var > config.toml [general].language > Englisch.
    Ruft NICHT set_language() auf - das macht der Aufrufer explizit, damit
    z.B. main() die Sprache einmal beim Start festlegen kann."""
    env = os.environ.get("LLANO_LANGUAGE")
    if env in _TRANSLATIONS:
        return env
    if config is not None:
        lang = config.get("general", {}).get("language")
        if lang in _TRANSLATIONS:
            return lang
    return DEFAULT_LANGUAGE


def get_language():
    return _forced_language or DEFAULT_LANGUAGE


def init_language():
    """Lädt die Config und legt die aktive Sprache fest - gemeinsamer
    Einstiegspunkt für CLI (cli.main()) und GUI (gui/app.main()), damit
    beide exakt dieselbe Auflösungsreihenfolge verwenden (siehe
    resolve_language()). Lokaler Import von config, um einen Zyklus zu
    vermeiden (config.py importiert i18n nicht)."""
    from . import config as config_mod

    cfg = config_mod.load_config()
    set_language(resolve_language(cfg))


def t(key, **kwargs):
    """Übersetzt `key` in der aktiven Sprache (siehe get_language()),
    formatiert mit `kwargs` falls angegeben. Fällt auf Englisch zurück,
    wenn der Key in der aktiven Sprache fehlt, und auf den Key selbst,
    wenn er auch dort fehlt (nie ein KeyError zur Laufzeit)."""
    lang = get_language()
    template = _TRANSLATIONS.get(lang, {}).get(key)
    if template is None:
        template = _EN.get(key, key)
    return template.format(**kwargs) if kwargs else template
