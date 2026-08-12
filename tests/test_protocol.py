"""Tests für das HID-Report-Layout (protocol.py).

Die Byte-Positionen hier sind gegen echte Hardware verifiziert (siehe die
NACHTRAG-Abschnitte in protocol.py). Diese Tests halten das Layout fest,
damit ein Refactoring es nicht unbemerkt verschiebt.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from llano_v12ultra_ctrl import protocol  # noqa: E402


class TestChecksum(unittest.TestCase):
    def test_formula(self):
        self.assertEqual(protocol.checksum([0, 0, 0, 0, 0, 0, 0]), 0xFF)
        self.assertEqual(protocol.checksum([1, 2, 3, 0, 0, 0, 0]), 0xFF - 6)

    def test_wraps_within_byte(self):
        self.assertEqual(protocol.checksum([0xFF] * 7), (0xFF - 0xFF * 7) & 0xFF)
        self.assertTrue(0 <= protocol.checksum([0xFF] * 7) <= 0xFF)


class TestBuildReport(unittest.TestCase):
    def test_length_and_checksum(self):
        report = protocol.build_report(color=2, effect=1, speed=0, brightness=200)
        self.assertEqual(len(report), protocol.REPORT_LEN)
        self.assertTrue(protocol.Report(report).checksum_ok)

    def test_round_trip_through_report(self):
        report = protocol.Report(
            protocol.build_report(color=3, effect=1, speed=2, brightness=128)
        )
        self.assertEqual(report.color, 3)
        self.assertEqual(report.effect_raw, 1)
        self.assertEqual(report.speed, 2)
        self.assertEqual(report.brightness, 128)
        self.assertTrue(report.light_on)
        self.assertTrue(report.power_on)

    def test_light_off_sets_effect_off(self):
        report = protocol.Report(protocol.build_report(color=0, light_on=False))
        self.assertFalse(report.light_on)
        self.assertTrue(report.power_on)  # Lüfter läuft weiter

    def test_power_off_sets_kill_flag(self):
        report = protocol.Report(protocol.build_report(color=0, power=False))
        self.assertFalse(report.power_on)


class TestBuildFanReport(unittest.TestCase):
    def test_layout(self):
        """Byte-Layout per Live-USB-Capture verifiziert (NACHTRAG 8)."""
        raw = protocol.build_fan_report(48)
        self.assertEqual(len(raw), protocol.REPORT_LEN)
        self.assertEqual(raw[0], 0x00)                            # Report-ID
        self.assertEqual(raw[1], protocol.FAN_SET_BYTE0)          # Kommando
        self.assertEqual(raw[2], 48)                              # Drehzahl
        self.assertEqual(raw[5], protocol.FAN_SUBCOMMAND_TAG)     # Unterkommando
        self.assertEqual(raw[7], 0xFF)
        self.assertTrue(protocol.Report(raw).checksum_ok)

    def test_never_collides_with_light_command(self):
        """byte0 unterscheidet Fan- von Licht-Kommando - sonst würde das eine
        das andere auslösen."""
        self.assertNotEqual(protocol.FAN_SET_BYTE0, protocol.BYTE0_CONST)
        for raw_value in (1, 50, 100):
            self.assertNotEqual(
                protocol.build_fan_report(raw_value)[1],
                protocol.build_report(color=0)[1],
            )


class TestFanRpm(unittest.TestCase):
    def test_verified_reference_points(self):
        """Gegen die Anzeige des Pads gemessen (NACHTRAG 9)."""
        for raw_value, expected_rpm in ((1, 300), (48, 1500), (100, 2800)):
            report = protocol.Report(protocol.build_fan_report(raw_value))
            self.assertEqual(report.fan_rpm, expected_rpm, f"raw={raw_value}")

    def test_monotonic_over_full_range(self):
        rpms = [protocol.Report(protocol.build_fan_report(r)).fan_rpm for r in range(1, 101)]
        self.assertEqual(rpms, sorted(rpms))

    def test_out_of_range_is_clamped(self):
        """Das Gerät nimmt Werte über 100 an und rechnet die Anzeige unbegrenzt
        weiter (die echten 6675 U/min bei raw=255). Die Software klemmt."""
        for raw_value in (0, 101, 200, 255):
            report = protocol.Report(protocol.build_fan_report(raw_value))
            self.assertTrue(300 <= report.fan_rpm <= 2800, f"raw={raw_value} -> {report.fan_rpm}")


class TestReportParsing(unittest.TestCase):
    def test_rejects_short_report(self):
        with self.assertRaises(ValueError):
            protocol.Report(b"\x00\x01\x02")

    def test_detects_bad_checksum(self):
        raw = bytearray(protocol.build_report(color=1))
        raw[8] ^= 0xFF
        self.assertFalse(protocol.Report(bytes(raw)).checksum_ok)

    def test_unknown_names_do_not_raise(self):
        raw = bytearray(protocol.build_report(color=1))
        raw[5] = 99  # unbekannte Farbe
        report = protocol.Report(bytes(raw))
        self.assertIn("99", report.color_name())


if __name__ == "__main__":
    unittest.main()
