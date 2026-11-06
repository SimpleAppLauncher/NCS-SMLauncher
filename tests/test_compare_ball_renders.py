"""Tests the render-comparison metrics on tiny deterministic RGB images."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))
from compare_ball_renders import stats  # noqa: E402

SCRATCH = Path.home() / ".hermes" / "cache" / "scratch"
SCRATCH.mkdir(parents=True, exist_ok=True)


class CompareBallRendersTests(unittest.TestCase):
    def test_known_pixel_statistics(self):
        pixels = np.array([
            [[0, 0, 0], [100, 100, 100]],
            [[200, 0, 0], [0, 0, 255]],
        ], dtype=np.uint8)
        with tempfile.TemporaryDirectory(prefix="render-stats-", dir=SCRATCH) as d:
            path = Path(d) / "known.png"
            Image.fromarray(pixels).save(path)
            got = stats("test", str(path), None)

        self.assertEqual(got["size"], (2, 2))
        self.assertAlmostEqual(got["lit"], 75.0)
        self.assertAlmostEqual(got["mean"], (0 + 100 + 59.8 + 29.07) / 4)
        self.assertAlmostEqual(got["p95"], 100.0)
        self.assertAlmostEqual(got["warm"], 25.0)
        self.assertEqual(got["brightest"], (100, 100, 100))

    def test_crop_and_no_lit_pixels(self):
        pixels = np.array([
            [[0, 0, 0], [255, 255, 255]],
            [[255, 0, 0], [0, 0, 255]],
        ], dtype=np.uint8)
        with tempfile.TemporaryDirectory(prefix="render-crop-", dir=SCRATCH) as d:
            path = Path(d) / "crop.png"
            Image.fromarray(pixels).save(path)
            got = stats("test", str(path), (0, 0, 1, 1))

        self.assertEqual(got["size"], (1, 1))
        self.assertEqual(got["lit"], 0.0)
        self.assertEqual(got["mean"], 0.0)
        self.assertEqual(got["p95"], 0.0)
        self.assertEqual(got["warm"], 0.0)
        self.assertIsNone(got["brightest"])


if __name__ == "__main__":
    unittest.main()
