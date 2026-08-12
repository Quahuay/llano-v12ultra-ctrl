"""Leiser Update-Checker gegen die GitHub-Releases-API.

Bewusst KEIN Silent-Self-Updater (Sicherheits-/Vertrauensrisiko bei einem
Tool mit rohem HID-Zugriff) - nur eine Versionsprüfung, die dem Nutzer einen
Hinweis + Link zur Release-Seite gibt. Tatsächliches Aktualisieren bleibt
manuell (Installer erneut herunterladen, bzw. beim Paketmanager-Weg
`pacman -Syu`/`apt upgrade`, siehe i18n.py "update.*"-Keys für die
plattformabhängige Formulierung).

Design-Entscheidungen (siehe auch config.py [general].update_check):
- Ergebnis wird in ~/.cache/llano-v12ultra-ctrl/update_check.json
  zwischengespeichert und höchstens einmal pro 24h neu abgefragt - kein
  Netzwerk-Call bei jedem einzelnen CLI-Aufruf (u.a. wichtig für
  `auto`/`monitor`, die in einer Schleife laufen, sowie für Skript-Nutzung).
- Kein Release vorhanden (`/releases/latest` liefert 404) wird als
  "aktuell" behandelt, nicht als Fehler - der 404-Fall ist für ein Projekt
  ohne bisherige Releases der Normalfall, nicht die Ausnahme.
- Jeder Netzwerk-/Parse-Fehler schlägt lautlos fehl (analog zu notify.py) -
  eine fehlende Internetverbindung darf `status`/`auto`/die GUI nie
  blockieren oder zum Absturz bringen.
- Timeout kurz (2s), damit ein hängender Request die CLI nicht spürbar
  verzögert.
"""

import json
import os
import re
import time
import urllib.request

from . import __version__ as CURRENT_VERSION

REPO = "Quahuay/llano-v12ultra-ctrl"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
CACHE_PATH = os.path.expanduser("~/.cache/llano-v12ultra-ctrl/update_check.json")
CACHE_TTL_S = 24 * 60 * 60
TIMEOUT_S = 2.0


def _parse_version(v):
    """Zerlegt eine 'vX.Y.Z'/'X.Y.Z'-Version in ein Tupel für den Vergleich.
    Nicht-numerische Suffixe (z.B. '-beta') werden ignoriert - für dieses
    Projekt reichen einfache dotted-Versionen, keine volle PEP-440-Logik
    nötig."""
    v = v.lstrip("vV")
    parts = re.findall(r"\d+", v)
    return tuple(int(p) for p in parts) or (0,)


def _is_newer(latest, current):
    return _parse_version(latest) > _parse_version(current)


def _read_cache():
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(data):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass  # Cache ist reine Optimierung - ein Schreibfehler darf nichts blockieren


def _fetch_latest_tag():
    """Fragt die GitHub-API ab. Gibt den Tag-Namen zurück, None wenn (noch)
    kein Release existiert (404) oder ein Fehler auftrat."""
    req = urllib.request.Request(
        API_URL, headers={"User-Agent": "llano-v12ultra-ctrl-update-check", "Accept": "application/vnd.github+json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            data = json.load(resp)
        return data.get("tag_name")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # noch kein Release vorhanden - kein Fehler
        return None
    except Exception:
        return None  # Netzwerkfehler, Timeout, kaputtes JSON, ... - lautlos


def check_for_update(current_version=None, force=False):
    """Prüft (mit 24h-Cache) auf eine neuere Version.

    Gibt die neuere Versionsnummer (str, ohne führendes 'v') zurück, wenn
    eine verfügbar ist, sonst None. Wirft nie eine Exception."""
    current_version = current_version or CURRENT_VERSION
    cache = _read_cache() if not force else None
    now = time.time()

    if cache is not None and (now - cache.get("checked_at", 0)) < CACHE_TTL_S:
        latest = cache.get("latest")
    else:
        latest = _fetch_latest_tag()
        _write_cache({"checked_at": now, "latest": latest})

    if latest and _is_newer(latest, current_version):
        return latest.lstrip("vV")
    return None


def installed_via_package_manager():
    """True, wenn dieses Tool erkennbar über dpkg (.deb) oder pacman (Arch/
    AUR) installiert wurde - dort ist der Paketmanager die richtige
    Update-Quelle, ein Download-Link wäre distro-untypisch (siehe
    i18n.py update.gui.package_manager vs. update.gui.available/download).
    Bei MSI/AppImage/aus dem Quellcode installiert liefert dies False."""
    import shutil
    import subprocess

    # dpkg-query liefert auch für ein entferntes, aber nicht gepurgtes Paket
    # returncode 0 (Status dann "deinstall ok config-files"). Der Rückgabewert
    # allein reicht also nicht - sonst bekäme z.B. ein AppImage-Nutzer, der das
    # .deb irgendwann mal installiert hatte, dauerhaft den Hinweis "Update über
    # den Paketmanager" statt des Download-Links. Deshalb den Status-String
    # prüfen. pacman -Q hat das Problem nicht (nicht-null bei unbekanntem Paket).
    checks = (
        ("dpkg-query", ["-W", "-f", "${Status}", "llano-v12ultra-ctrl"], "install ok installed"),
        ("pacman", ["-Q", "llano-v12ultra-ctrl"], None),
    )
    for cmd, args, expect_stdout in checks:
        if not shutil.which(cmd):
            continue
        try:
            result = subprocess.run(
                [cmd] + args, capture_output=True, text=True, errors="replace", timeout=2
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode != 0:
            continue
        if expect_stdout is None or expect_stdout in (result.stdout or ""):
            return True
    return False


# Hinweis: einen asynchronen Wrapper gibt es hier bewusst nicht mehr. Die GUI
# nutzt stattdessen gui/update_worker.py (QThread + pyqtSignal), weil ein roher
# threading.Thread mit Callback nicht sicher aus dem Worker-Thread heraus auf
# Qt-Widgets zugreifen dürfte.
