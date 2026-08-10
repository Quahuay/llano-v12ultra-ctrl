"""Profil-Speicherung für die GUI: bis zu 5 benannte Einstellungs-Sätze
(Licht + Lüfterdrehzahl), die sich mit einem Klick wieder anwenden lassen.

Eigene JSON-Datei statt config.toml (~/.config/llano-v12ultra-ctrl/profiles.json):
das ist reine GUI-Bequemlichkeit (kein CLI-/auto-Feature) und JSON passt für
eine feste Liste besser als ein textuelles TOML-Blockersetzen wie bei
config.save_fan_curve."""

import json
import os

DEFAULT_PROFILES_PATH = os.path.expanduser("~/.config/llano-v12ultra-ctrl/profiles.json")
MAX_PROFILES = 5


def load_profiles(path=None):
    """Gibt eine Liste mit genau MAX_PROFILES Einträgen zurück, leere Slots
    als None. Eine fehlende oder kaputte Datei liefert einfach lauter
    leere Slots zurück, statt einen Fehler zu werfen."""
    path = path or DEFAULT_PROFILES_PATH
    slots = [None] * MAX_PROFILES
    if not os.path.exists(path):
        return slots
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return slots
    for i, entry in enumerate(data.get("slots", [])[:MAX_PROFILES]):
        slots[i] = entry
    return slots


def save_profile(slot, name, settings, path=None):
    """Speichert `settings` (dict mit color/effect/speed/brightness/power/
    fan_raw) unter `slot` (0-basiert, 0..MAX_PROFILES-1) mit Anzeigenamen
    `name`."""
    _check_slot(slot)
    path = path or DEFAULT_PROFILES_PATH
    slots = load_profiles(path)
    slots[slot] = {"name": name, **settings}
    _write(slots, path)


def delete_profile(slot, path=None):
    _check_slot(slot)
    path = path or DEFAULT_PROFILES_PATH
    slots = load_profiles(path)
    slots[slot] = None
    _write(slots, path)


def _check_slot(slot):
    if not 0 <= slot < MAX_PROFILES:
        raise ValueError(f"slot muss zwischen 0 und {MAX_PROFILES - 1} liegen")


def _write(slots, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"slots": slots}, f, indent=2, ensure_ascii=False)
        f.write("\n")
