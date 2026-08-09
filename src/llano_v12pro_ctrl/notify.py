"""Desktop-Benachrichtigungen für llano-v12pro-ctrl, cross-platform über
`plyer` (dispatcht selbst auf notify-send/Desktop-Portals unter Linux,
Toast-Notifications unter Windows, NSUserNotificationCenter unter macOS -
kein eigenes sys.platform-Verzweigen nötig).

Die Lüfterdrehzahl ist eine reine Hardware-Grenze (siehe protocol.py):
Software kann sie nicht setzen, nur das physische Rad am Pad regelt sie.
Als Ersatz für einen echten Regelkreis kann `cmd_auto` (cli.py) den
Menschen per Desktop-Notification erinnern, das Rad manuell hochzudrehen,
wenn die CPU heiß ist, die gemessene Drehzahl aber niedrig bleibt.

Live auf Linux getestet (notify-send-Backend). Windows/macOS-Backends von
plyer selbst nicht in dieser Umgebung getestet (keine passende Maschine
verfügbar) - plyer ist aber eine etablierte, breit genutzte Bibliothek
genau für diesen Zweck.

Bekannte Einschränkung: plyers öffentliche notify()-Fassade nimmt keinen
"urgency"-Parameter entgegen (nur intern von einzelnen Linux-Backends
unterstützt) - alle Benachrichtigungen laufen daher mit normaler
Dringlichkeit, unabhängig vom früheren `urgency`-Argument dieser Funktion.
"""

APP_NAME = "llano-v12pro-ctrl"

_warned_missing = False


def send(title, body):
    """Schickt eine Desktop-Notification über plyer.

    Schlägt lautlos fehl (mit einmaliger Warnung auf stdout), wenn auf
    diesem System kein Notification-Backend verfügbar ist - der
    Auto-Daemon soll dadurch nicht abstürzen oder bei jedem Poll erneut
    warnen."""
    global _warned_missing
    try:
        from plyer import notification

        notification.notify(title=title, message=body, app_name=APP_NAME, timeout=10)
    except Exception as e:
        if not _warned_missing:
            print(f"Hinweis: Desktop-Benachrichtigungen nicht verfügbar ({e}).")
            _warned_missing = True
