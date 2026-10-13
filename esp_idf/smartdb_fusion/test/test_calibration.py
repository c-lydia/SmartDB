import copy
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "calibrate", Path(__file__).parents[1] / "tools/calibrate.py"
)
calibrate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calibrate)


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            "version": "fixture-only",
            "rgb_size": [320, 240],
            "thermal_size": [32, 24],
            "points": [
                {"rgb": [x, y], "thermal": [x * 31 / 319, y * 23 / 239]}
                for x, y in [
                    (0, 0),
                    (319, 0),
                    (0, 239),
                    (319, 239),
                    (160, 60),
                    (80, 180),
                    (240, 170),
                ]
            ],
            "regions": [{"id": "panel", "rect": [0, 0, 319, 239]}],
        }

    def test_known_scale(self):
        h, error = calibrate.fit(self.data)
        self.assertLess(error, 1e-8)
        self.assertAlmostEqual(h[0], 31 / 319)
        self.assertAlmostEqual(h[4], 23 / 239)
        self.assertIn(".enabled=true", calibrate.header(self.data))

    def test_degenerate(self):
        self.data["points"] = [{"rgb": [x, 0], "thermal": [x / 10, 0]} for x in range(6)]
        with self.assertRaises(ValueError):
            calibrate.fit(self.data)

    def test_bad_match(self):
        self.data["points"][-1]["thermal"] = [1, 1]
        with self.assertRaises(ValueError):
            calibrate.fit(self.data)

    def test_bad_region(self):
        self.data["regions"][0]["rect"] = [0, 0, 400, 239]
        with self.assertRaises(ValueError):
            calibrate.header(self.data)

    def test_duplicate_regions(self):
        self.data["regions"].append(copy.deepcopy(self.data["regions"][0]))
        with self.assertRaises(ValueError):
            calibrate.header(self.data)

    def test_nan_and_wrong_size(self):
        self.data["points"][0]["thermal"][0] = float("nan")
        with self.assertRaises(ValueError):
            calibrate.fit(self.data)
        self.data["rgb_size"] = [640, 480]
        with self.assertRaises(ValueError):
            calibrate.fit(self.data)
