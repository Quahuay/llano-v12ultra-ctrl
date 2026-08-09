"""Config-Handling für v12pro-ctrl (~/.config/v12pro-ctrl/config.toml)."""

import os
import tomllib

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/v12pro-ctrl/config.toml")

DEFAULT_CONFIG = {
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
        # Erinnerungs-Benachrichtigung (notify-send): die Software kann die
        # Lüfterdrehzahl NICHT setzen (Hardware-Grenze, nur das physische
        # Rad regelt sie). Als Ersatz für einen echten Regelkreis erinnert
        # dieser Alarm den Menschen, das Rad manuell hochzudrehen, wenn die
        # CPU heiß ist, aber die gemessene Drehzahl niedrig bleibt.
        "fan_reminder": {
            "enabled": False,
            "temp_c": 75,
            "min_rpm": 1500,
            "cooldown_s": 300,
        },
        # CSV-Verlaufsprotokoll (Zeitstempel/Temperaturen/RPM/Farbe/Effekt),
        # nützlich um im Nachhinein eine passende Radstellung für typische
        # Lasten zu finden. Standardmäßig deaktiviert (opt-in).
        "log": {
            "enabled": False,
            "path": "~/.local/share/v12pro-ctrl/history.csv",
        },
    }
}


def load_config(path=None):
    path = path or DEFAULT_CONFIG_PATH
    cfg = {"auto": dict(DEFAULT_CONFIG["auto"])}
    cfg["auto"]["thresholds"] = [dict(t) for t in DEFAULT_CONFIG["auto"]["thresholds"]]
    cfg["auto"]["gpu_alert"] = dict(DEFAULT_CONFIG["auto"]["gpu_alert"])
    cfg["auto"]["fan_reminder"] = dict(DEFAULT_CONFIG["auto"]["fan_reminder"])
    cfg["auto"]["log"] = dict(DEFAULT_CONFIG["auto"]["log"])
    if os.path.exists(path):
        with open(path, "rb") as f:
            user_cfg = tomllib.load(f)
        if "auto" in user_cfg:
            cfg["auto"].update(user_cfg["auto"])
    return cfg
