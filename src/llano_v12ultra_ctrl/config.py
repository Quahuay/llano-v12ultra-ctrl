"""Config-Handling für llano-v12ultra-ctrl (~/.config/llano-v12ultra-ctrl/config.toml)."""

import os
import tomllib

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/llano-v12ultra-ctrl/config.toml")

DEFAULT_CONFIG = {
    "general": {
        # Sprache für CLI/GUI-Texte. None/"en" = Englisch (Standard), "de" =
        # Deutsch. Kann pro Aufruf zusätzlich über die Umgebungsvariable
        # LLANO_LANGUAGE überschrieben werden (siehe i18n.py) - praktisch
        # für einen einzelnen Aufruf, ohne die Config dauerhaft zu ändern.
        "language": "en",
    },
    "auto": {
        "temp_sensor": None,  # None = automatisch erkennen (coretemp/k10temp)
        "poll_interval_s": 5,
        # Schwellen aufsteigend sortiert: ab dieser Temperatur (°C) wird
        # der zugehörige color/effect/speed-Wert gesetzt. effect/speed sind
        # optional (Default: 0=solid, 0=schnell) - eine hohe Schwelle kann
        # z.B. effect=3 (chase) statt nur eine andere Farbe setzen, um bei
        # kritischer Temperatur deutlicher aufzufallen als ein reiner
        # Farbwechsel.
        "thresholds": [
            {"temp_c": 0, "color": 2},                       # grün = kühl
            {"temp_c": 55, "color": 4},                      # orange = warm
            {"temp_c": 70, "color": 0},                      # rot = heiß
            {"temp_c": 85, "color": 0, "effect": 3, "speed": 0},  # kritisch: rot + Lauflicht
        ],
        # Hysterese in °C, verhindert schnelles Hin-und-Herschalten an der
        # Schwelle.
        "hysteresis_c": 3,
        # GPU-Temperatur-Alarm: übersteuert die obige CPU-Farblogik mit
        # lila+breathing, sobald die GPU heißer als "temp_c" UND heißer als
        # die aktuelle CPU ist ("wer wärmer ist gewinnt"). Eigene Hysterese,
        # da GPU- und CPU-Temperaturkurven unabhängig voneinander schwanken.
        "gpu_alert": {
            "enabled": True,
            "temp_c": 87,
            "hysteresis_c": 5,
            "color": 3,   # lila
            "effect": 1,  # breathing
            "speed": 0,   # 0=schnell (offizieller Bereich 0-3)
        },
        # Erinnerungs-Benachrichtigung (notify-send), z.B. nützlich solange
        # fan_curve (siehe unten) nicht aktiviert ist: erinnert daran, das
        # Rad manuell hochzudrehen, wenn die CPU heiß ist, aber die
        # gemessene Drehzahl niedrig bleibt.
        "fan_reminder": {
            "enabled": False,
            "temp_c": 75,
            "min_rpm": 1500,
            "cooldown_s": 300,
        },
        # Lüfterkurve: bildet die CPU-Temperatur per stückweise linearer
        # Interpolation auf einen fan_speed-Rohwert (1-100) ab, siehe
        # fan_curve.py. Standardmäßig deaktiviert (opt-in) - das physische
        # Rad bleibt sonst die einzige Drehzahlquelle. min_change_raw
        # verhindert ständiges Nachregeln bei kleinen Temperaturschwankungen
        # (nur schreiben, wenn sich der Zielwert um mindestens so viel
        # ändert).
        "fan_curve": {
            "enabled": False,
            "points": [
                {"temp_c": 30, "raw": 1},
                {"temp_c": 50, "raw": 30},
                {"temp_c": 70, "raw": 60},
                {"temp_c": 85, "raw": 100},
            ],
            "min_change_raw": 3,
        },
        # CSV-Verlaufsprotokoll (Zeitstempel/Temperaturen/RPM/Farbe/Effekt),
        # nützlich um im Nachhinein eine passende Radstellung für typische
        # Lasten zu finden. Standardmäßig deaktiviert (opt-in).
        "log": {
            "enabled": False,
            "path": "~/.local/share/llano-v12ultra-ctrl/history.csv",
        },
    }
}


def load_config(path=None):
    path = path or DEFAULT_CONFIG_PATH
    cfg = {"general": dict(DEFAULT_CONFIG["general"]), "auto": dict(DEFAULT_CONFIG["auto"])}
    cfg["auto"]["thresholds"] = [dict(t) for t in DEFAULT_CONFIG["auto"]["thresholds"]]
    cfg["auto"]["gpu_alert"] = dict(DEFAULT_CONFIG["auto"]["gpu_alert"])
    cfg["auto"]["fan_reminder"] = dict(DEFAULT_CONFIG["auto"]["fan_reminder"])
    cfg["auto"]["fan_curve"] = dict(DEFAULT_CONFIG["auto"]["fan_curve"])
    cfg["auto"]["fan_curve"]["points"] = [dict(p) for p in DEFAULT_CONFIG["auto"]["fan_curve"]["points"]]
    cfg["auto"]["log"] = dict(DEFAULT_CONFIG["auto"]["log"])
    if os.path.exists(path):
        with open(path, "rb") as f:
            user_cfg = tomllib.load(f)
        if "general" in user_cfg:
            cfg["general"].update(user_cfg["general"])
        if "auto" in user_cfg:
            cfg["auto"].update(user_cfg["auto"])
    return cfg


def save_fan_curve(enabled, points, min_change_raw=3, path=None):
    """Schreibt (nur) den [auto.fan_curve]-Abschnitt in die Config-Datei,
    ohne andere Abschnitte anzutasten. Erhält bestehende Config-Inhalte,
    da tomllib nur lesen kann - der Rest der Datei wird textuell
    unverändert übernommen, nur der [auto.fan_curve]-Block wird ersetzt
    oder angehängt."""
    path = path or DEFAULT_CONFIG_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)

    lines = [
        "[auto.fan_curve]",
        f"enabled = {'true' if enabled else 'false'}",
        f"min_change_raw = {int(min_change_raw)}",
        "points = [",
    ]
    for p in sorted_points_for_save(points):
        lines.append(f'    {{ temp_c = {p["temp_c"]}, raw = {p["raw"]} }},')
    lines.append("]")
    block = "\n".join(lines) + "\n"

    existing = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = f.read()

    if "[auto.fan_curve]" in existing:
        before, _, after = existing.partition("[auto.fan_curve]")
        # alles bis zur naechsten Top-Level/[auto.*]-Ueberschrift oder
        # Dateiende gehoert noch zum alten Block und wird ersetzt.
        rest_lines = after.split("\n")
        cut = len(rest_lines)
        for i, line in enumerate(rest_lines[1:], start=1):
            if line.startswith("["):
                cut = i
                break
        after = "\n".join(rest_lines[cut:])
        new_content = before + block + after
    else:
        sep = "\n" if existing and not existing.endswith("\n") else ""
        new_content = existing + sep + ("\n" if existing else "") + block

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)


def sorted_points_for_save(points):
    return sorted(points, key=lambda p: p["temp_c"])


def save_language(language, path=None):
    """Schreibt (nur) den [general]-Abschnitt in die Config-Datei, nach
    demselben Textersetzungs-Muster wie save_fan_curve - siehe dort für die
    Begründung (tomllib kann nur lesen, der Rest der Datei bleibt
    unverändert)."""
    path = path or DEFAULT_CONFIG_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)

    block = f'[general]\nlanguage = "{language}"\n'

    existing = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = f.read()

    if "[general]" in existing:
        before, _, after = existing.partition("[general]")
        rest_lines = after.split("\n")
        cut = len(rest_lines)
        for i, line in enumerate(rest_lines[1:], start=1):
            if line.startswith("["):
                cut = i
                break
        after = "\n".join(rest_lines[cut:])
        new_content = before + block + after
    else:
        sep = "\n" if existing and not existing.endswith("\n") else ""
        new_content = existing + sep + ("\n" if existing else "") + block

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
