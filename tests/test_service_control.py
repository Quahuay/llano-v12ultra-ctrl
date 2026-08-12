"""Tests für die Timeout-Behandlung in gui/service_control.py.

Kein echtes systemctl/schtasks nötig: subprocess.run wird ersetzt. Deckt den
in v0.1.3 behobenen Bug ab: ohne timeout= konnte ein hängender Subprozess-
Aufruf die GUI unbegrenzt einfrieren (beide *_poll_*-Timer in main_window.py
laufen auf dem Qt-Event-Loop-Thread, kein eigener QThread für Subprozesse).
"""

import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from llano_v12ultra_ctrl.gui import service_control  # noqa: E402


def _raise_timeout(*args, **kwargs):
    raise subprocess.TimeoutExpired(cmd=args[0] if args else "?", timeout=kwargs.get("timeout", 0))


class ServiceControlTestCase(unittest.TestCase):
    def setUp(self):
        self._orig_run = subprocess.run

    def tearDown(self):
        subprocess.run = self._orig_run


class TestLinuxTimeouts(ServiceControlTestCase):
    def test_is_active_returns_false_on_timeout(self):
        subprocess.run = _raise_timeout
        self.assertFalse(service_control._is_active_linux())

    def test_start_returns_false_on_timeout(self):
        subprocess.run = _raise_timeout
        self.assertFalse(service_control._start_linux())

    def test_stop_returns_false_on_timeout(self):
        subprocess.run = _raise_timeout
        self.assertFalse(service_control._stop_linux())


class TestWindowsTimeouts(ServiceControlTestCase):
    def test_task_exists_returns_false_on_timeout(self):
        subprocess.run = _raise_timeout
        self.assertFalse(service_control._task_exists_windows())

    def test_is_active_returns_false_on_timeout(self):
        subprocess.run = _raise_timeout
        self.assertFalse(service_control._is_active_windows())

    def test_stop_returns_false_on_timeout(self):
        subprocess.run = _raise_timeout
        self.assertFalse(service_control._stop_windows())

    def test_register_task_returns_false_on_timeout(self):
        subprocess.run = _raise_timeout
        self.assertFalse(service_control._register_task_windows())

    def test_start_returns_false_when_task_query_times_out(self):
        """_start_windows() ruft zuerst _task_exists_windows() auf - auch
        dieser erste Aufruf muss zeitlich begrenzt sein, sonst friert schon
        der Existenz-Check den GUI-Thread ein, bevor `/run` überhaupt
        versucht wird."""
        subprocess.run = _raise_timeout
        self.assertFalse(service_control._start_windows())


class TestTimeoutIsActuallyPassed(ServiceControlTestCase):
    """Stellt sicher, dass timeout= wirklich an subprocess.run durchgereicht
    wird - ein bloßes `except subprocess.TimeoutExpired` ohne timeout=-Kwarg
    würde nie greifen, weil der Aufruf selbst unbegrenzt bliebe."""

    def test_all_call_sites_pass_a_positive_timeout(self):
        seen = []

        def fake_run(*args, **kwargs):
            seen.append(kwargs.get("timeout"))
            raise subprocess.CalledProcessError(1, args[0] if args else "?")

        subprocess.run = fake_run
        functions = (
            service_control._is_active_linux, service_control._stop_linux,
            service_control._start_linux, service_control._task_exists_windows,
            service_control._is_active_windows, service_control._stop_windows,
            service_control._register_task_windows,
        )
        for fn in functions:
            seen.clear()
            # CalledProcessError statt TimeoutExpired: bestätigt, dass die
            # Funktion selbst KEIN zu breites except hat, das auch andere
            # Fehler stillschweigend verschluckt - nur TimeoutExpired soll
            # abgefangen werden.
            with self.assertRaises(subprocess.CalledProcessError, msg=fn.__name__):
                fn()
            self.assertEqual(len(seen), 1, fn.__name__)
            self.assertIsNotNone(seen[0], f"{fn.__name__} ruft subprocess.run ohne timeout= auf")
            self.assertGreater(seen[0], 0, fn.__name__)


if __name__ == "__main__":
    unittest.main()
