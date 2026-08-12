"""Tests für die Auto-Modus-Schleife (cli.cmd_auto) gegen ein Fake-Gerät.

Kein echtes Pad nötig: device.Device und temp.* werden ersetzt. Deckt vor
allem das Verhalten beim Abziehen des Pads ab - Lese- UND Schreibpfad, weil
der Schreibpfad hier eine Zeitlang ungeschützt war und den Daemon mit einem
Traceback beendet hat.
"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from llano_v12ultra_ctrl import cli, protocol  # noqa: E402
from llano_v12ultra_ctrl import device as device_mod  # noqa: E402
from llano_v12ultra_ctrl import notify as notify_mod  # noqa: E402
from llano_v12ultra_ctrl import temp as temp_mod  # noqa: E402


def _report(fan_raw=48):
    return protocol.Report(protocol.build_fan_report(fan_raw))


class FakePad:
    """Fake-Gerät. `fail_writes` lässt die ersten N Schreibzugriffe mit einem
    OSError scheitern (= Pad abgezogen), danach funktionieren sie wieder.
    `stop_after` beendet die Schleife über ein KeyboardInterrupt, so wie
    Strg+C es täte."""

    def __init__(self, fail_writes=0, stop_after=5):
        self.fail_writes = fail_writes
        self.stop_after = stop_after
        self.reads = 0
        self.writes = 0
        self.fan_writes = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        pass

    def get_report(self):
        self.reads += 1
        if self.reads > self.stop_after:
            raise KeyboardInterrupt
        return _report()

    def _maybe_fail(self):
        self.writes += 1
        if self.writes <= self.fail_writes:
            raise OSError(19, "No such device")

    def set_light(self, **kwargs):
        self._maybe_fail()
        return _report()

    def set_fan_speed(self, raw):
        self._maybe_fail()
        self.fan_writes.append(raw)
        return _report(raw)


class AutoLoopTestCase(unittest.TestCase):
    def setUp(self):
        self._orig = (
            device_mod.Device, temp_mod.find_cpu_temp_input,
            temp_mod.read_temp_c, temp_mod.read_gpu_temp_c, notify_mod.send,
        )
        temp_mod.find_cpu_temp_input = lambda: "/fake/sensor"
        temp_mod.read_gpu_temp_c = lambda: None
        notify_mod.send = lambda *a, **k: None
        self.temp_c = 90.0
        temp_mod.read_temp_c = lambda path: self.temp_c

        fd, self.cfg_path = tempfile.mkstemp(suffix=".toml")
        os.close(fd)

    def tearDown(self):
        (device_mod.Device, temp_mod.find_cpu_temp_input,
         temp_mod.read_temp_c, temp_mod.read_gpu_temp_c, notify_mod.send) = self._orig
        if os.path.exists(self.cfg_path):
            os.unlink(self.cfg_path)

    def run_auto(self, pad, config="[auto]\npoll_interval_s = 0\n"):
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write(config)
        device_mod.Device = lambda *a, **k: pad
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.cmd_auto(SimpleNamespace(config=self.cfg_path))
        return rc, buf.getvalue()


class TestDisconnectSurvival(AutoLoopTestCase):
    def test_survives_write_error_and_recovers(self):
        """Regression: set_light lag außerhalb des OSError-Schutzes, ein
        Abziehen des Pads beim Schreiben hat den Daemon getötet."""
        pad = FakePad(fail_writes=2, stop_after=5)
        rc, output = self.run_auto(pad)
        self.assertEqual(rc, 0)
        self.assertGreater(pad.writes, 2, "nach dem Fehler wurde nicht weiter geschrieben")
        self.assertIn("[Errno 19]", output, "Gerätefehler wurde nicht gemeldet")

    def test_survives_read_error(self):
        class FlakyReader(FakePad):
            def get_report(self):
                self.reads += 1
                if self.reads > self.stop_after:
                    raise KeyboardInterrupt
                if self.reads <= 2:
                    raise OSError(19, "No such device")
                return _report()

        rc, output = self.run_auto(FlakyReader(stop_after=5))
        self.assertEqual(rc, 0)
        self.assertIn("[Errno 19]", output)

    def test_survives_sensor_read_error(self):
        """Ein verschwindender hwmon-Pfad (Suspend/Resume) darf ebenso wenig
        durchschlagen wie ein Gerätefehler."""
        calls = {"n": 0}

        def flaky_temp(path):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise OSError(2, "No such file or directory")
            return 90.0

        temp_mod.read_temp_c = flaky_temp
        rc, _ = self.run_auto(FakePad(stop_after=5))
        self.assertEqual(rc, 0)

    def test_clean_exit_without_errors(self):
        pad = FakePad(stop_after=3)
        rc, output = self.run_auto(pad)
        self.assertEqual(rc, 0)
        self.assertNotIn("Errno", output)


class TestFanCurveInLoop(AutoLoopTestCase):
    CONFIG = (
        "[auto]\npoll_interval_s = 0\n\n"
        "[auto.fan_curve]\nenabled = true\nmin_change_raw = 3\n"
        "points = [ { temp_c = 30, raw = 1 }, { temp_c = 85, raw = 100 } ]\n"
    )

    def test_writes_fan_speed_when_enabled(self):
        pad = FakePad(stop_after=3)
        self.run_auto(pad, self.CONFIG)
        self.assertTrue(pad.fan_writes, "Lüfterkurve aktiv, aber nie geschrieben")
        for raw in pad.fan_writes:
            self.assertTrue(1 <= raw <= 100)

    def test_min_change_suppresses_repeat_writes(self):
        """Bei konstanter Temperatur darf nur einmal geschrieben werden."""
        pad = FakePad(stop_after=6)
        self.run_auto(pad, self.CONFIG)
        self.assertEqual(len(pad.fan_writes), 1, f"unnötige Schreibzugriffe: {pad.fan_writes}")

    def test_no_fan_writes_when_disabled(self):
        pad = FakePad(stop_after=3)
        self.run_auto(pad, "[auto]\npoll_interval_s = 0\n")
        self.assertEqual(pad.fan_writes, [])


class TestMissingSensor(AutoLoopTestCase):
    def test_aborts_with_exit_code_1(self):
        temp_mod.find_cpu_temp_input = lambda: None
        pad = FakePad(stop_after=3)
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write("[auto]\npoll_interval_s = 0\n")
        device_mod.Device = lambda *a, **k: pad
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(io.StringIO()):
            rc = cli.cmd_auto(SimpleNamespace(config=self.cfg_path))
        self.assertEqual(rc, 1)
        self.assertEqual(pad.reads, 0, "ohne Sensor darf das Gerät nicht angefasst werden")


if __name__ == "__main__":
    unittest.main()
