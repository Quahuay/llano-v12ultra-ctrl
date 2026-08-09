"""Desktop-Benachrichtigungen für v12pro-ctrl.

Die Lüfterdrehzahl ist eine reine Hardware-Grenze (siehe protocol.py):
Software kann sie nicht setzen, nur das physische Rad am Pad regelt sie.
Als Ersatz für einen echten Regelkreis kann `cmd_auto` (cli.py) den
Menschen per Desktop-Notification erinnern, das Rad manuell hochzudrehen,
wenn die CPU heiß ist, die gemessene Drehzahl aber niedrig bleibt.
"""

import shutil
import subprocess

_warned_missing = False


def send(title, body, urgency="normal"):
    """Schickt eine Desktop-Notification per notify-send, falls verfügbar.

    Schlägt lautlos fehl (mit einmaliger Warnung auf stdout), wenn
    notify-send auf dem System nicht installiert ist oder kein
    Notification-Daemon läuft - der Auto-Daemon soll dadurch nicht
    abstürzen oder bei jedem Poll erneut warnen."""
    global _warned_missing
    if shutil.which("notify-send") is None:
        if not _warned_missing:
            print("Hinweis: notify-send nicht gefunden, Desktop-Benachrichtigungen deaktiviert.")
            _warned_missing = True
        return
    try:
        subprocess.run(
            ["notify-send", "--urgency", urgency, "--app-name", "v12pro-ctrl", title, body],
            capture_output=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
