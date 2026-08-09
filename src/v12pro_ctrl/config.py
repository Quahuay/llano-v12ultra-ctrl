"""Config-Handling für v12pro-ctrl (~/.config/v12pro-ctrl/config.toml)."""

import os
import tomllib

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/v12pro-ctrl/config.toml")

DEFAULT_CONFIG = {
    "auto": {
        "temp_sensor": None,  # None = automatisch erkennen (coretemp/k10temp)
        "poll_interval_s": 5,
        # Schwellen aufsteigend sortiert: ab dieser Temperatur (°C) wird
        # der zugehörige fan_mode-Wert gesetzt.
        "thresholds": [
            {"temp_c": 0, "color": 2},   # grün = kühl
            {"temp_c": 55, "color": 4},  # orange = warm
            {"temp_c": 70, "color": 0},  # rot = heiß
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
    }
}


def load_config(path=None):
    path = path or DEFAULT_CONFIG_PATH
    cfg = {"auto": dict(DEFAULT_CONFIG["auto"])}
    cfg["auto"]["thresholds"] = list(DEFAULT_CONFIG["auto"]["thresholds"])
    cfg["auto"]["gpu_alert"] = dict(DEFAULT_CONFIG["auto"]["gpu_alert"])
    if os.path.exists(path):
        with open(path, "rb") as f:
            user_cfg = tomllib.load(f)
        if "auto" in user_cfg:
            cfg["auto"].update(user_cfg["auto"])
    return cfg
