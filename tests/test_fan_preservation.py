"""Tests dafür, dass Licht-Kommandos die Lüfterdrehzahl nicht zurücksetzen.

Hintergrund: `byte1` des Licht-Kommandos ist dasselbe Feld, das beim Lesen die
Drehzahl liefert. Das Gerät übernimmt den geschriebenen Wert. Wurde dort eine
0 geschrieben, fiel die Drehzahl bei jedem Farbwechsel auf 0 - im
Automatikmodus also mehrmals pro Minute, was die Lüfterkurve unbrauchbar
machte. Am Gerät verifiziert (2026-08-12).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from llano_v12ultra_ctrl import device as device_mod  # noqa: E402
from llano_v12ultra_ctrl import protocol  # noqa: E402


class FakeHidraw:
    """Minimaler hidraw-Ersatz: merkt sich den Gerätezustand als 9-Byte-Report
    und wendet geschriebene Reports so an, wie es die echte Hardware tut."""

    def __init__(self, fan_raw=50):
        body7 = [0x00, fan_raw, 0x00, 0x00, 0x02, 0x00, 0xFF]
        self.state = bytes([0x00] + body7 + [protocol.checksum(body7)])
        self.writes = []

    def apply(self, report):
        self.writes.append(report)
        body = list(report[1:8])
        state = bytearray(self.state)
        if body[0] == protocol.FAN_SET_BYTE0:          # Fan-Kommando
            state[2] = body[1]
        elif body[0] == protocol.BYTE0_CONST:          # Licht-Kommando
            state[2] = body[1]                         # byte1 IST die Drehzahl
            state[3] = body[2]                         # kill flag
            state[4] = body[3]                         # effect
            state[5] = body[4]                         # color
            state[6] = body[5]                         # speed
            state[7] = body[6]                         # brightness
        state[8] = protocol.checksum(list(state[1:8]))
        self.state = bytes(state)


def make_device(fan_raw=50):
    """_LinuxDevice ohne echte Hardware: ioctl-Ebene durch FakeHidraw ersetzt."""
    dev = device_mod._LinuxDevice.__new__(device_mod._LinuxDevice)
    hw = FakeHidraw(fan_raw)

    import ctypes

    dev._ctypes = ctypes
    dev._os = os
    dev._fd = -1
    dev.path = "/dev/fake"

    class FakeFcntl:
        @staticmethod
        def ioctl(fd, request, buf, mutate):
            # Schreiben (HIDIOCSFEATURE) hat 0x06 in den unteren Bits.
            if (request & 0xFF) == 0x06:
                hw.apply(bytes(buf.raw[:protocol.REPORT_LEN]))
            else:
                buf[:protocol.REPORT_LEN] = hw.state
            return 0

    dev._fcntl = FakeFcntl
    dev._hw = hw
    return dev


class TestFanSpeedSurvivesLightCommands(unittest.TestCase):
    def test_set_light_preserves_fan_speed(self):
        dev = make_device(fan_raw=60)
        dev.set_light(color=3, effect=1, speed=0, brightness=200)
        self.assertEqual(dev.get_report().fan_speed_raw, 60)

    def test_repeated_colour_changes_preserve_fan_speed(self):
        """Der Automatikmodus schreibt bei jedem Schwellenwechsel Licht."""
        dev = make_device(fan_raw=42)
        for color in (0, 4, 2, 0, 4, 2):
            dev.set_light(color=color, effect=0, speed=0, brightness=255)
        self.assertEqual(dev.get_report().fan_speed_raw, 42)

    def test_light_off_preserves_fan_speed(self):
        dev = make_device(fan_raw=77)
        dev.set_light(color=2, light_on=False)
        report = dev.get_report()
        self.assertFalse(report.light_on)
        self.assertEqual(report.fan_speed_raw, 77)

    def test_set_power_preserves_fan_speed(self):
        dev = make_device(fan_raw=35)
        dev.set_power(power=False)
        dev.set_power(power=True)
        self.assertEqual(dev.get_report().fan_speed_raw, 35)

    def test_light_command_carries_fan_speed_in_byte1(self):
        """Direkt auf Byte-Ebene: byte1 des geschriebenen Reports muss die
        aktuelle Drehzahl tragen, nicht 0."""
        dev = make_device(fan_raw=88)
        dev.set_light(color=1, effect=0, speed=0, brightness=255)
        light_writes = [w for w in dev._hw.writes if w[1] == protocol.BYTE0_CONST]
        self.assertTrue(light_writes)
        self.assertEqual(light_writes[-1][2], 88, "byte1 traegt nicht die Drehzahl")

    def test_set_fan_speed_still_works(self):
        dev = make_device(fan_raw=10)
        dev.set_fan_speed(90)
        self.assertEqual(dev.get_report().fan_speed_raw, 90)

    def test_fan_speed_then_light_then_fan_speed(self):
        dev = make_device(fan_raw=1)
        dev.set_fan_speed(70)
        dev.set_light(color=0, effect=3, speed=0, brightness=128)
        self.assertEqual(dev.get_report().fan_speed_raw, 70)
        dev.set_fan_speed(20)
        dev.set_light(color=2, effect=0, speed=0, brightness=255)
        self.assertEqual(dev.get_report().fan_speed_raw, 20)


class TestBuildReportByte1(unittest.TestCase):
    def test_byte1_lands_at_offset_2(self):
        report = protocol.build_report(color=0, byte1=55)
        self.assertEqual(report[2], 55)
        self.assertTrue(protocol.Report(report).checksum_ok)

    def test_byte1_defaults_to_zero(self):
        """Der Default bleibt 0. Aufrufer, die die Drehzahl erhalten wollen,
        müssen den aktuellen Wert übergeben - device.set_light tut das."""
        self.assertEqual(protocol.build_report(color=0)[2], 0)

    def test_byte1_is_masked_to_one_byte(self):
        self.assertEqual(protocol.build_report(color=0, byte1=0x1FF)[2], 0xFF)


if __name__ == "__main__":
    unittest.main()
