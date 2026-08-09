"""Steuerung des llano-v12pro-ctrl.service (systemd --user Auto-Modus-Daemon)
aus der GUI heraus.

Die GUI schaltet den Daemon nur für die laufende Sitzung per stop/start
pausiert (Unit bleibt weiterhin `enabled` und läuft nach dem nächsten
Login/Reboot normal wieder an) - kein dauerhaftes disable/enable, siehe
README.
"""

import subprocess

SERVICE_NAME = "llano-v12pro-ctrl.service"


def is_active() -> bool:
    """True wenn der Auto-Modus-Daemon gerade läuft.

    Wertet den Exit-Code von `systemctl --user is-active` aus (0 = aktiv),
    nicht die stdout-Zeichenkette."""
    result = subprocess.run(
        ["systemctl", "--user", "is-active", "--quiet", SERVICE_NAME],
        capture_output=True,
    )
    return result.returncode == 0


def stop() -> bool:
    """Pausiert den Auto-Modus für diese Sitzung. Gibt True bei Erfolg
    zurück (Exit-Code 0)."""
    result = subprocess.run(["systemctl", "--user", "stop", SERVICE_NAME], capture_output=True)
    return result.returncode == 0


def start() -> bool:
    """Setzt den Auto-Modus fort. Gibt True bei Erfolg zurück (Exit-Code 0)."""
    result = subprocess.run(["systemctl", "--user", "start", SERVICE_NAME], capture_output=True)
    return result.returncode == 0
