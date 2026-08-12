"""Tests für das Config-Handling.

Schwerpunkt: die textuellen Schreibfunktionen (save_language, save_fan_curve).
Die schreiben den TOML-Block per String-Manipulation neu, weil tomllib nur
lesen kann - das ist die fehleranfälligste Stelle im Projekt, und genau dort
sind zwei Bugs aufgetreten (siehe test_save_language_adds_missing_key und
test_save_fan_curve_preserves_min_change_raw).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from llano_v12ultra_ctrl import config as config_mod  # noqa: E402


class ConfigTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".toml")
        os.close(fd)
        os.unlink(self.path)  # Datei soll erst existieren, wenn ein Test sie anlegt

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def write(self, content):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(content)

    def read(self):
        with open(self.path, encoding="utf-8") as f:
            return f.read()

    def load(self):
        return config_mod.load_config(path=self.path)


class TestLoadConfig(ConfigTestCase):
    def test_defaults_without_file(self):
        cfg = self.load()
        self.assertEqual(cfg["general"]["language"], "en")
        self.assertTrue(cfg["general"]["update_check"])
        self.assertEqual(cfg["auto"]["poll_interval_s"], 5)

    def test_partial_subsection_keeps_other_defaults(self):
        """Ein Nutzer, der nur einen Key einer Sub-Section setzt, darf nicht
        die restlichen Defaults dieser Sub-Section verlieren."""
        self.write("[auto.fan_reminder]\nenabled = true\n")
        reminder = self.load()["auto"]["fan_reminder"]
        self.assertTrue(reminder["enabled"])
        self.assertEqual(reminder["temp_c"], 75)      # Default erhalten
        self.assertEqual(reminder["min_rpm"], 1500)   # Default erhalten
        self.assertEqual(reminder["cooldown_s"], 300)

    def test_user_points_replace_defaults_wholesale(self):
        self.write("[auto.fan_curve]\npoints = [ { temp_c = 40, raw = 20 } ]\n")
        points = self.load()["auto"]["fan_curve"]["points"]
        self.assertEqual(points, [{"temp_c": 40, "raw": 20}])

    def test_defaults_are_not_shared_between_calls(self):
        """load_config muss tief genug kopieren, sonst verändert ein Aufrufer
        über das zurückgegebene Dict die Defaults für alle weiteren Aufrufe."""
        first = self.load()
        first["auto"]["fan_curve"]["points"].append({"temp_c": 99, "raw": 99})
        first["auto"]["gpu_alert"]["temp_c"] = 1
        second = self.load()
        self.assertNotIn({"temp_c": 99, "raw": 99}, second["auto"]["fan_curve"]["points"])
        self.assertEqual(second["auto"]["gpu_alert"]["temp_c"], 87)


class TestSaveLanguage(ConfigTestCase):
    def test_creates_file_when_missing(self):
        config_mod.save_language("de", path=self.path)
        self.assertEqual(self.load()["general"]["language"], "de")

    def test_replaces_existing_key(self):
        self.write('[general]\nlanguage = "en"\nupdate_check = false\n')
        config_mod.save_language("de", path=self.path)
        cfg = self.load()
        self.assertEqual(cfg["general"]["language"], "de")
        self.assertFalse(cfg["general"]["update_check"])

    def test_save_language_adds_missing_key(self):
        """Regression: existierte [general] ohne language-Key, hat die Funktion
        still gar nichts geschrieben - die Schleife ersetzte nur eine bereits
        vorhandene Zeile. Die GUI meldete trotzdem Erfolg."""
        self.write("[general]\nupdate_check = false\n\n[auto]\npoll_interval_s = 5\n")
        config_mod.save_language("de", path=self.path)
        cfg = self.load()
        self.assertEqual(cfg["general"]["language"], "de")
        self.assertFalse(cfg["general"]["update_check"])   # anderer Key bleibt
        self.assertEqual(cfg["auto"]["poll_interval_s"], 5)  # andere Sektion bleibt

    def test_adds_section_when_only_other_sections_exist(self):
        self.write("[auto]\npoll_interval_s = 9\n")
        config_mod.save_language("de", path=self.path)
        cfg = self.load()
        self.assertEqual(cfg["general"]["language"], "de")
        self.assertEqual(cfg["auto"]["poll_interval_s"], 9)

    def test_preserves_comments(self):
        self.write("[general]\n# Sprache der Oberflaeche\nupdate_check = true\n")
        config_mod.save_language("de", path=self.path)
        self.assertIn("# Sprache der Oberflaeche", self.read())

    def test_result_stays_parseable_after_repeated_saves(self):
        self.write("[general]\nupdate_check = false\n\n[auto]\npoll_interval_s = 5\n")
        for lang in ("de", "en", "de", "de"):
            config_mod.save_language(lang, path=self.path)
            self.assertEqual(self.load()["general"]["language"], lang)
        self.assertEqual(self.load()["auto"]["poll_interval_s"], 5)


class TestSaveFanCurve(ConfigTestCase):
    def test_round_trip(self):
        points = [{"temp_c": 70, "raw": 60}, {"temp_c": 30, "raw": 1}]
        config_mod.save_fan_curve(True, points, min_change_raw=5, path=self.path)
        curve = self.load()["auto"]["fan_curve"]
        self.assertTrue(curve["enabled"])
        self.assertEqual(curve["min_change_raw"], 5)
        # beim Speichern nach temp_c sortiert
        self.assertEqual(curve["points"], [{"temp_c": 30, "raw": 1}, {"temp_c": 70, "raw": 60}])

    def test_save_fan_curve_preserves_min_change_raw(self):
        """Regression: die GUI übergab hart min_change_raw=3 und hat damit
        einen vom Nutzer konfigurierten Wert beim Speichern der Kurve
        überschrieben. Die GUI liest den Wert jetzt vorher aus."""
        self.write("[auto.fan_curve]\nenabled = true\nmin_change_raw = 12\n"
                   "points = [ { temp_c = 40, raw = 20 } ]\n")
        curve = self.load()["auto"]["fan_curve"]
        config_mod.save_fan_curve(
            curve["enabled"], curve["points"],
            min_change_raw=curve["min_change_raw"], path=self.path,
        )
        self.assertEqual(self.load()["auto"]["fan_curve"]["min_change_raw"], 12)

    def test_leaves_other_sections_untouched(self):
        self.write('[general]\nlanguage = "de"\n\n[auto]\npoll_interval_s = 7\n\n'
                   "[auto.gpu_alert]\nenabled = false\ntemp_c = 91\n")
        config_mod.save_fan_curve(True, [{"temp_c": 50, "raw": 30}], path=self.path)
        cfg = self.load()
        self.assertEqual(cfg["general"]["language"], "de")
        self.assertEqual(cfg["auto"]["poll_interval_s"], 7)
        self.assertFalse(cfg["auto"]["gpu_alert"]["enabled"])
        self.assertEqual(cfg["auto"]["gpu_alert"]["temp_c"], 91)
        self.assertTrue(cfg["auto"]["fan_curve"]["enabled"])

    def test_repeated_saves_do_not_duplicate_block(self):
        for raw in (10, 20, 30):
            config_mod.save_fan_curve(True, [{"temp_c": 50, "raw": raw}], path=self.path)
        self.assertEqual(self.read().count("[auto.fan_curve]"), 1)
        self.assertEqual(self.load()["auto"]["fan_curve"]["points"], [{"temp_c": 50, "raw": 30}])

    def test_language_and_fan_curve_saves_coexist(self):
        """Beide Schreibfunktionen fassen dieselbe Datei textuell an."""
        config_mod.save_language("de", path=self.path)
        config_mod.save_fan_curve(True, [{"temp_c": 60, "raw": 40}], min_change_raw=8, path=self.path)
        config_mod.save_language("en", path=self.path)
        cfg = self.load()
        self.assertEqual(cfg["general"]["language"], "en")
        self.assertTrue(cfg["auto"]["fan_curve"]["enabled"])
        self.assertEqual(cfg["auto"]["fan_curve"]["min_change_raw"], 8)
        self.assertEqual(cfg["auto"]["fan_curve"]["points"], [{"temp_c": 60, "raw": 40}])


if __name__ == "__main__":
    unittest.main()
