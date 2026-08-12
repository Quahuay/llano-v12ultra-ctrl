"""Tests für den Update-Check (Versionsvergleich, Cache, Paketmanager-Erkennung).

Kein Netzwerkzugriff: _fetch_latest_tag wird ersetzt.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from llano_v12ultra_ctrl import update_check  # noqa: E402


class TestVersionCompare(unittest.TestCase):
    def test_parses_with_and_without_prefix(self):
        self.assertEqual(update_check._parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(update_check._parse_version("1.2.3"), (1, 2, 3))

    def test_newer_detection(self):
        self.assertTrue(update_check._is_newer("0.2.0", "0.1.0"))
        self.assertTrue(update_check._is_newer("1.0.0", "0.9.9"))
        self.assertTrue(update_check._is_newer("0.1.10", "0.1.9"))  # nicht lexikografisch
        self.assertFalse(update_check._is_newer("0.1.0", "0.1.0"))
        self.assertFalse(update_check._is_newer("0.1.0", "0.2.0"))

    def test_differing_component_counts(self):
        self.assertTrue(update_check._is_newer("0.2", "0.1.9"))
        self.assertFalse(update_check._is_newer("0.1", "0.1.1"))


class TestCheckForUpdate(unittest.TestCase):
    def setUp(self):
        self._orig_fetch = update_check._fetch_latest_tag
        self._orig_cache = update_check.CACHE_PATH
        fd, self.cache = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(self.cache)
        update_check.CACHE_PATH = self.cache

    def tearDown(self):
        update_check._fetch_latest_tag = self._orig_fetch
        update_check.CACHE_PATH = self._orig_cache
        if os.path.exists(self.cache):
            os.unlink(self.cache)

    def test_reports_newer_version(self):
        update_check._fetch_latest_tag = lambda: "v9.9.9"
        self.assertEqual(update_check.check_for_update("0.1.0", force=True), "9.9.9")

    def test_silent_when_current(self):
        update_check._fetch_latest_tag = lambda: "v0.1.0"
        self.assertIsNone(update_check.check_for_update("0.1.0", force=True))

    def test_no_release_yet_is_not_an_error(self):
        """/releases/latest liefert 404, solange es kein Release gibt - das ist
        der Normalfall für ein junges Projekt, kein Fehler."""
        update_check._fetch_latest_tag = lambda: None
        self.assertIsNone(update_check.check_for_update("0.1.0", force=True))

    def test_uses_cache_within_ttl(self):
        with open(self.cache, "w", encoding="utf-8") as f:
            json.dump({"checked_at": time.time(), "latest": "v9.9.9"}, f)
        calls = []

        def counting_fetch():
            calls.append(1)
            return "v0.0.1"

        update_check._fetch_latest_tag = counting_fetch
        self.assertEqual(update_check.check_for_update("0.1.0"), "9.9.9")
        self.assertEqual(calls, [], "trotz frischem Cache wurde das Netz befragt")

    def test_refetches_when_cache_stale(self):
        with open(self.cache, "w", encoding="utf-8") as f:
            json.dump({"checked_at": time.time() - update_check.CACHE_TTL_S - 10,
                       "latest": "v0.0.1"}, f)
        update_check._fetch_latest_tag = lambda: "v9.9.9"
        self.assertEqual(update_check.check_for_update("0.1.0"), "9.9.9")

    def test_corrupt_cache_does_not_raise(self):
        with open(self.cache, "w", encoding="utf-8") as f:
            f.write("{kaputt")
        update_check._fetch_latest_tag = lambda: "v9.9.9"
        self.assertEqual(update_check.check_for_update("0.1.0"), "9.9.9")

    def test_network_failure_is_silent(self):
        """Ein Netzwerkfehler darf nie bis in status/auto durchschlagen - der
        Update-Hinweis ist Beiwerk, kein Grund das Kommando zu beenden."""
        import urllib.request

        orig_urlopen = urllib.request.urlopen

        def boom(*args, **kwargs):
            raise OSError("kein Netz")

        urllib.request.urlopen = boom
        self.addCleanup(lambda: setattr(urllib.request, "urlopen", orig_urlopen))
        update_check._fetch_latest_tag = self._orig_fetch
        self.assertIsNone(update_check._fetch_latest_tag())
        self.assertIsNone(update_check.check_for_update("0.1.0", force=True))


class TestPackageManagerDetection(unittest.TestCase):
    """installed_via_package_manager entscheidet, ob der Nutzer einen
    Download-Link oder den Hinweis "Update über den Paketmanager" bekommt."""

    def setUp(self):
        self._orig_run = subprocess.run

    def tearDown(self):
        subprocess.run = self._orig_run

    def _patch(self, available, stdout, returncode=0):
        """Tut so, als wäre nur `available` installiert und liefere `stdout`."""
        import shutil as shutil_mod

        orig_which = shutil_mod.which
        shutil_mod.which = lambda cmd: f"/usr/bin/{cmd}" if cmd == available else None
        self.addCleanup(lambda: setattr(shutil_mod, "which", orig_which))

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, returncode, stdout, "")

        subprocess.run = fake_run

    def test_dpkg_installed(self):
        self._patch("dpkg-query", "install ok installed")
        self.assertTrue(update_check.installed_via_package_manager())

    def test_dpkg_removed_but_not_purged(self):
        """Regression: dpkg-query liefert auch für ein entferntes, aber nicht
        gepurgtes Paket returncode 0. Nur den Rückgabewert zu prüfen hätte
        einem AppImage-Nutzer dauerhaft den falschen Hinweis gezeigt."""
        self._patch("dpkg-query", "deinstall ok config-files")
        self.assertFalse(update_check.installed_via_package_manager())

    def test_dpkg_unknown_package(self):
        self._patch("dpkg-query", "", returncode=1)
        self.assertFalse(update_check.installed_via_package_manager())

    def test_pacman_installed(self):
        self._patch("pacman", "llano-v12ultra-ctrl 0.1.0-1")
        self.assertTrue(update_check.installed_via_package_manager())

    def test_pacman_unknown_package(self):
        self._patch("pacman", "", returncode=1)
        self.assertFalse(update_check.installed_via_package_manager())


if __name__ == "__main__":
    unittest.main()
