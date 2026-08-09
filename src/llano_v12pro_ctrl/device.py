"""Low-Level-Ansteuerung des llano V12 Ultra.

Zwei getrennte Implementierungen, je nach Plattform ausgewählt (`Device`
zeigt unten auf die passende Klasse):

- **Linux** (`_LinuxDevice`): rohe `/dev/hidraw*`-ioctls. Bewusst KEINE
  `hid`/hidapi-Bibliothek, obwohl die theoretisch cross-platform wäre -
  ein Testlauf hat gezeigt, dass `hid.device().open()` auf diesem System
  bei JEDEM Aufruf einen vollständigen USB-Rebind auslöst (reproduzierbar,
  5 von 5 Zyklen, siehe Git-Historie), was für ein Tool, das ständig neu
  öffnet/schließt, ungeeignet ist. Live gegen echte Hardware getestet und
  stabil.
- **Windows** (`_WindowsDevice`): über die `hid`-Bibliothek (hidapi), da es
  unter Windows kein hidraw-Äquivalent gibt. **UNGETESTET** - keine
  Windows-Maschine in dieser Entwicklungsumgebung verfügbar. Ob der auf
  Linux beobachtete Rebind-Effekt dort ebenfalls auftritt, ist unbekannt
  (die Windows-HID-API von hidapi ist eine komplett andere Implementierung
  als der Linux-hidraw-Backend) - vor Produktivnutzung unter Windows selbst
  gegentesten.

`protocol.py` ist in beiden Fällen identisch und unverändert - beide
Implementierungen tauschen exakt das gleiche 9-Byte-Feature-Report-Layout
(Report-ID 0x00 + 7 Body-Bytes + Checksum) aus.
"""

import sys

from . import protocol

VID_INT = 0x374A
PID_INT = 0xB101
INPUT_REPORT_LEN = 64  # laut HID-Report-Descriptor, siehe protocol.py
OUTPUT_REPORT_LEN = 64


class DeviceNotFoundError(RuntimeError):
    pass


# --------------------------------------------------------------- Linux ----

class _LinuxDevice:
    VID = "374A"
    PID = "B101"

    def __init__(self, path=None):
        import ctypes
        import fcntl
        import glob
        import os

        self._ctypes = ctypes
        self._fcntl = fcntl
        self._os = os
        self.path = path or self._find_hidraw_node(glob)
        if not self.path:
            raise DeviceNotFoundError(
                "llano V12 Ultra (374a:b101) nicht gefunden. "
                "Ist das Pad angeschlossen und die udev-Regel installiert?"
            )
        self._fd = os.open(self.path, os.O_RDWR)

    def _find_hidraw_node(self, glob):
        """Sucht /dev/hidraw<N> für VID 374a / PID b101 über sysfs."""
        for uevent_path in glob.glob("/sys/class/hidraw/hidraw*/device/uevent"):
            try:
                with open(uevent_path) as f:
                    content = f.read().upper()
            except OSError:
                continue
            if self.VID in content and self.PID in content:
                hidraw_name = uevent_path.split("/")[4]
                return f"/dev/{hidraw_name}"
        return None

    @staticmethod
    def _ioc(direction, typ, nr, size):
        return (direction << 30) | (ord(typ) << 8) | nr | (size << 16)

    def _hidiocgfeature(self, length):
        return self._ioc(3, "H", 0x07, length)  # _IOC_READ|_IOC_WRITE

    def _hidiocsfeature(self, length):
        return self._ioc(3, "H", 0x06, length)  # _IOC_READ|_IOC_WRITE

    def close(self):
        if self._fd is not None:
            self._os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def get_report(self) -> protocol.Report:
        buf = self._ctypes.create_string_buffer(protocol.REPORT_LEN)
        buf[0] = b"\x00"
        self._fcntl.ioctl(self._fd, self._hidiocgfeature(protocol.REPORT_LEN), buf, True)
        return protocol.Report(buf.raw)

    def set_light(self, color: int, effect: int = 0, speed: int = 0x00, light_on: bool = True, brightness: int = 0xFF, power: bool = True) -> protocol.Report:
        _validate_light_args(color, effect, speed, brightness)
        report = protocol.build_report(color=color, effect=effect, speed=speed, light_on=light_on, brightness=brightness, power=power)
        buf = self._ctypes.create_string_buffer(report, protocol.REPORT_LEN)
        self._fcntl.ioctl(self._fd, self._hidiocsfeature(protocol.REPORT_LEN), buf, True)
        return self.get_report()

    def set_power(self, power: bool) -> protocol.Report:
        current = self.get_report()
        report = protocol.build_report(
            color=current.color, effect=current.effect_raw if current.light_on else 0,
            speed=current.speed, light_on=current.light_on, brightness=current.brightness,
            power=power,
        )
        buf = self._ctypes.create_string_buffer(report, protocol.REPORT_LEN)
        self._fcntl.ioctl(self._fd, self._hidiocsfeature(protocol.REPORT_LEN), buf, True)
        return self.get_report()

    def read_input_report(self, timeout_s: float = 0.2):
        """Liest (mit Timeout) den rohen 64-Byte Input-Report, falls das
        Gerät gerade einen sendet. Siehe protocol.py - rein zur
        Beobachtung/Diagnose. Gibt None zurück, wenn innerhalb des Timeouts
        nichts ankommt."""
        import select
        ready, _, _ = select.select([self._fd], [], [], timeout_s)
        if not ready:
            return None
        return self._os.read(self._fd, INPUT_REPORT_LEN)

    def write_output_report(self, data: bytes):
        """Schreibt auf den 64-Byte Output-Report (Report-ID 0x00
        vorangestellt, mit Nullen aufgefüllt). NUR für gezielte,
        hypothesen-geleitete Tests (siehe protocol.py) - kein
        automatisiertes Fuzzing."""
        if len(data) > OUTPUT_REPORT_LEN:
            raise ValueError(f"data darf höchstens {OUTPUT_REPORT_LEN} Byte lang sein")
        padded = bytes(data) + bytes(OUTPUT_REPORT_LEN - len(data))
        self._os.write(self._fd, bytes([0x00]) + padded)


# ------------------------------------------------------------- Windows ----

class _WindowsDevice:
    """UNGETESTET - siehe Modul-Docstring."""

    def __init__(self, path=None):
        import hid

        self._dev = hid.device()
        try:
            self._dev.open(VID_INT, PID_INT)
        except OSError as e:
            raise DeviceNotFoundError(
                "llano V12 Ultra (374a:b101) nicht gefunden. Ist das Pad angeschlossen?"
            ) from e
        self.path = f"hid:{VID_INT:04x}:{PID_INT:04x}"

    def close(self):
        if self._dev is not None:
            self._dev.close()
            self._dev = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def get_report(self) -> protocol.Report:
        raw = self._dev.get_feature_report(0x00, protocol.REPORT_LEN)
        return protocol.Report(bytes(raw))

    def set_light(self, color: int, effect: int = 0, speed: int = 0x00, light_on: bool = True, brightness: int = 0xFF, power: bool = True) -> protocol.Report:
        _validate_light_args(color, effect, speed, brightness)
        report = protocol.build_report(color=color, effect=effect, speed=speed, light_on=light_on, brightness=brightness, power=power)
        self._dev.send_feature_report(list(report))
        return self.get_report()

    def set_power(self, power: bool) -> protocol.Report:
        current = self.get_report()
        report = protocol.build_report(
            color=current.color, effect=current.effect_raw if current.light_on else 0,
            speed=current.speed, light_on=current.light_on, brightness=current.brightness,
            power=power,
        )
        self._dev.send_feature_report(list(report))
        return self.get_report()

    def read_input_report(self, timeout_s: float = 0.2):
        raw = self._dev.read(INPUT_REPORT_LEN, timeout_ms=int(timeout_s * 1000))
        return bytes(raw) if raw else None

    def write_output_report(self, data: bytes):
        if len(data) > OUTPUT_REPORT_LEN:
            raise ValueError(f"data darf höchstens {OUTPUT_REPORT_LEN} Byte lang sein")
        padded = bytes(data) + bytes(OUTPUT_REPORT_LEN - len(data))
        self._dev.write([0x00] + list(padded))


def _validate_light_args(color, effect, speed, brightness):
    if not 0 <= color <= 4:
        raise ValueError("color muss zwischen 0 und 4 liegen")
    if not 0 <= effect <= 4:
        raise ValueError("effect muss zwischen 0 und 4 liegen")
    if not 0 <= speed <= 255:
        raise ValueError("speed muss zwischen 0 und 255 liegen")
    if not 0 <= brightness <= 255:
        raise ValueError("brightness muss zwischen 0 und 255 liegen")


Device = _WindowsDevice if sys.platform == "win32" else _LinuxDevice
