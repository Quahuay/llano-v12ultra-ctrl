"""Fehlertoleranter Wrapper um device.Device für die GUI.

Kapselt das try/except-Muster für device.DeviceNotFoundError (Pad beim
Öffnen nicht gefunden) und OSError (Pad wird während einer laufenden
Session abgesteckt - der bereits offene Dateideskriptor liefert dann einen
ioctl-Fehler statt einer sauberen Exception), damit main_window.py das
nicht in jedem Button-/Timer-Handler wiederholen muss.
"""

from .. import device as device_mod
from .. import i18n


def try_open():
    """Versucht, das Gerät zu öffnen.

    Gibt (Device, None) bei Erfolg zurück, sonst (None, Fehlertext)."""
    try:
        return device_mod.Device(), None
    except device_mod.DeviceNotFoundError as e:
        return None, str(e)
    except OSError as e:
        return None, i18n.t("device.open_error", error=e)


def safe_call(dev, fn):
    """Ruft fn(dev) auf und fängt Geräte-Fehler ab.

    Gibt (Report, None) bei Erfolg zurück, sonst (None, Fehlertext) - z.B.
    wenn das Pad zwischen zwei Aufrufen abgesteckt wurde."""
    try:
        return fn(dev), None
    except device_mod.DeviceNotFoundError as e:
        return None, str(e)
    except OSError as e:
        return None, i18n.t("device.call_error", error=e)
