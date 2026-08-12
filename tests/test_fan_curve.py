"""Tests für die Lüfterkurven-Interpolation."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from llano_v12ultra_ctrl import fan_curve  # noqa: E402

CURVE = [
    {"temp_c": 30, "raw": 1},
    {"temp_c": 50, "raw": 30},
    {"temp_c": 70, "raw": 60},
    {"temp_c": 85, "raw": 100},
]


class TestRawForTemp(unittest.TestCase):
    def test_hits_support_points_exactly(self):
        for point in CURVE:
            self.assertEqual(fan_curve.raw_for_temp(CURVE, point["temp_c"]), point["raw"])

    def test_interpolates_linearly(self):
        # Mitte zwischen 30°C/raw=1 und 50°C/raw=30
        self.assertEqual(fan_curve.raw_for_temp(CURVE, 40), round((1 + 30) / 2))

    def test_clamps_instead_of_extrapolating(self):
        self.assertEqual(fan_curve.raw_for_temp(CURVE, -20), 1)
        self.assertEqual(fan_curve.raw_for_temp(CURVE, 0), 1)
        self.assertEqual(fan_curve.raw_for_temp(CURVE, 200), 100)

    def test_result_always_within_device_range(self):
        for temp in range(-50, 151):
            raw = fan_curve.raw_for_temp(CURVE, temp)
            self.assertTrue(1 <= raw <= 100, f"{temp}°C -> {raw}")

    def test_monotonic_for_monotonic_curve(self):
        values = [fan_curve.raw_for_temp(CURVE, t) for t in range(0, 120)]
        self.assertEqual(values, sorted(values))

    def test_unsorted_points_are_sorted_first(self):
        shuffled = list(reversed(CURVE))
        for temp in (25, 40, 60, 90):
            self.assertEqual(
                fan_curve.raw_for_temp(shuffled, temp),
                fan_curve.raw_for_temp(CURVE, temp),
            )

    def test_single_point_is_constant(self):
        single = [{"temp_c": 50, "raw": 42}]
        for temp in (0, 50, 100):
            self.assertEqual(fan_curve.raw_for_temp(single, temp), 42)

    def test_duplicate_temps_do_not_divide_by_zero(self):
        dupes = [{"temp_c": 50, "raw": 10}, {"temp_c": 50, "raw": 90}]
        raw = fan_curve.raw_for_temp(dupes, 50)
        self.assertTrue(1 <= raw <= 100)

    def test_empty_points_raise(self):
        with self.assertRaises(ValueError):
            fan_curve.raw_for_temp([], 50)

    def test_sorted_points_does_not_mutate_input(self):
        original = list(reversed(CURVE))
        snapshot = [dict(p) for p in original]
        fan_curve.sorted_points(original)
        self.assertEqual(original, snapshot)


if __name__ == "__main__":
    unittest.main()
