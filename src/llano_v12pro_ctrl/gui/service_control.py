"""Steuerung des Auto-Modus-Hintergrunddienstes aus der GUI heraus.

Linux: systemd --user Unit `llano-v12pro-ctrl.service`. Live getestet.
Windows: KEIN systemd-Äquivalent - stattdessen eine geplante Aufgabe
(Scheduled Task, `schtasks`), die bei Anmeldung `llano-v12pro-ctrl auto`
startet (siehe README für die Einrichtung, einfacher als ein echter
Windows-Dienst, da kein Admin-Installer nötig ist). **UNGETESTET** - keine
Windows-Maschine in dieser Entwicklungsumgebung verfügbar.

Die GUI schaltet den Daemon nur für die laufende Sitzung pausiert/fortgesetzt
(kein dauerhaftes Deaktivieren der Registrierung) - siehe README.
"""

import subprocess
import sys

SERVICE_NAME = "llano-v12pro-ctrl.service"
WINDOWS_TASK_NAME = "llano-v12pro-ctrl-auto"


def _is_active_linux() -> bool:
    result = subprocess.run(
        ["systemctl", "--user", "is-active", "--quiet", SERVICE_NAME],
        capture_output=True,
    )
    return result.returncode == 0


def _stop_linux() -> bool:
    result = subprocess.run(["systemctl", "--user", "stop", SERVICE_NAME], capture_output=True)
    return result.returncode == 0


def _start_linux() -> bool:
    result = subprocess.run(["systemctl", "--user", "start", SERVICE_NAME], capture_output=True)
    return result.returncode == 0


def _is_active_windows() -> bool:
    """UNGETESTET - siehe Modul-Docstring. `schtasks /query .../v` liefert
    im "Status"-Feld u.a. "Running" oder "Ready" zurück."""
    result = subprocess.run(
        ["schtasks", "/query", "/tn", WINDOWS_TASK_NAME, "/fo", "list", "/v"],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and "Running" in result.stdout


def _stop_windows() -> bool:
    """UNGETESTET. Beendet die laufende Instanz; die Registrierung der
    geplanten Aufgabe selbst bleibt bestehen (kommt beim nächsten Login
    normal wieder, analog zum `enabled`-Zustand unter systemd)."""
    result = subprocess.run(["schtasks", "/end", "/tn", WINDOWS_TASK_NAME], capture_output=True)
    return result.returncode == 0


def _start_windows() -> bool:
    """UNGETESTET. Startet die geplante Aufgabe sofort (statt auf den
    nächsten Login zu warten)."""
    result = subprocess.run(["schtasks", "/run", "/tn", WINDOWS_TASK_NAME], capture_output=True)
    return result.returncode == 0


def is_active() -> bool:
    """True wenn der Auto-Modus-Daemon gerade läuft."""
    if sys.platform == "win32":
        return _is_active_windows()
    return _is_active_linux()


def stop() -> bool:
    """Pausiert den Auto-Modus für diese Sitzung. Gibt True bei Erfolg zurück."""
    if sys.platform == "win32":
        return _stop_windows()
    return _stop_linux()


def start() -> bool:
    """Setzt den Auto-Modus fort. Gibt True bei Erfolg zurück."""
    if sys.platform == "win32":
        return _start_windows()
    return _start_linux()
