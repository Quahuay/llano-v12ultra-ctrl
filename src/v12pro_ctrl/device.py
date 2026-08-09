"""Low-Level-Ansteuerung des llano V12 Ultra über /dev/hidraw*.

Gerät wird robust über VID/PID in sysfs gesucht (statt fest an einen
hidraw-Index gebunden zu sein, der sich bei jedem Replug ändern kann).
Voraussetzung: udev-Regel, die dem Nutzer rw-Zugriff auf das Device gibt
(siehe packaging/70-v12pro-ctrl.rules).
"""

import ctypes
import fcntl
import glob
import os

from . import protocol

VID = "374A"
PID = "B101"


class DeviceNotFoundError(RuntimeError):
    pass


def _ioc(direction, typ, nr, size):
    return (direction << 30) | (ord(typ) << 8) | nr | (size << 16)


def _hidiocgfeature(length):
    return _ioc(3, "H", 0x07, length)  # _IOC_READ|_IOC_WRITE


def _hidiocsfeature(length):
    return _ioc(3, "H", 0x06, length)  # _IOC_READ|_IOC_WRITE


def find_hidraw_node():
    """Sucht /dev/hidraw<N> für VID 374a / PID b101 über sysfs."""
    for uevent_path in glob.glob("/sys/class/hidraw/hidraw*/device/uevent"):
        try:
            with open(uevent_path) as f:
                content = f.read().upper()
        except OSError:
            continue
        if VID in content and PID in content:
            hidraw_name = uevent_path.split("/")[4]
            return f"/dev/{hidraw_name}"
    return None


class Device:
    def __init__(self, path=None):
        self.path = path or find_hidraw_node()
        if not self.path:
            raise DeviceNotFoundError(
                "llano V12 Ultra (374a:b101) nicht gefunden. "
                "Ist das Pad angeschlossen und die udev-Regel installiert?"
            )
        self._fd = os.open(self.path, os.O_RDWR)

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def get_report(self) -> protocol.Report:
        buf = ctypes.create_string_buffer(protocol.REPORT_LEN)
        buf[0] = b"\x00"
        fcntl.ioctl(self._fd, _hidiocgfeature(protocol.REPORT_LEN), buf, True)
        return protocol.Report(buf.raw)

    def set_light(self, color: int, effect: int = 0, speed: int = 0x00, light_on: bool = True, brightness: int = 0xFF, power: bool = True) -> protocol.Report:
        if not 0 <= color <= 4:
            raise ValueError("color muss zwischen 0 und 4 liegen")
        if not 0 <= effect <= 4:
            raise ValueError("effect muss zwischen 0 und 4 liegen")
        if not 0 <= speed <= 255:
            raise ValueError("speed muss zwischen 0 und 255 liegen")
        if not 0 <= brightness <= 255:
            raise ValueError("brightness muss zwischen 0 und 255 liegen")
        report = protocol.build_report(color=color, effect=effect, speed=speed, light_on=light_on, brightness=brightness, power=power)
        buf = ctypes.create_string_buffer(report, protocol.REPORT_LEN)
        fcntl.ioctl(self._fd, _hidiocsfeature(protocol.REPORT_LEN), buf, True)
        return self.get_report()

    def set_power(self, power: bool) -> protocol.Report:
        """Schaltet die GESAMTE Einheit (Lüfter + Licht) per kill_flag
        (byte2) an/aus. Reiner Ein/Aus-Schalter, keine Zwischenstufen."""
        current = self.get_report()
        report = protocol.build_report(
            color=current.color, effect=current.effect_raw if current.light_on else 0,
            speed=current.speed, light_on=current.light_on, brightness=current.brightness,
            power=power,
        )
        buf = ctypes.create_string_buffer(report, protocol.REPORT_LEN)
        fcntl.ioctl(self._fd, _hidiocsfeature(protocol.REPORT_LEN), buf, True)
        return self.get_report()
