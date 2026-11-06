"""Exercise the PortAudio callback with an inert output-stream fixture."""
import os
import sys
import unittest
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path.home() / ".hermes" / "cache" / "scratch"
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HASHPLAY_CONFIG_DIR", str(SCRATCH / "audio-callback-config"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path[:0] = [
    str(ROOT / "tests" / "fixtures" / "no_audio"),
    str(ROOT / "src"),
]

from ncs_launcher import Player  # noqa: E402


class AudioCallbackTests(unittest.TestCase):
    player: Any
    outdata: np.ndarray

    def setUp(self):
        self.player = Player()
        self.player.samples = np.arange(32, dtype=np.float32) / 32
        self.player.pos = 0
        self.player.paused = False
        self.outdata = np.full((4, 1), 99.0, dtype=np.float32)

    def test_active_callback_fills_output_and_advances_ring(self):
        before = np.arange(self.player.ring.size, dtype=np.float32)
        self.player.ring[:] = before
        self.player.pos = 3
        expected_ring = np.roll(before, -4)
        expected_ring[-4:] = self.player.samples[3:7]

        self.player._callback(self.outdata, 4, None, None)

        np.testing.assert_array_equal(self.outdata[:, 0], self.player.samples[3:7])
        self.assertEqual(self.player.pos, 7)
        np.testing.assert_array_equal(self.player.ring, expected_ring)

    def test_paused_callback_outputs_silence_and_fades_ring(self):
        self.player.paused = True
        before = np.arange(self.player.ring.size, dtype=np.float32)
        self.player.ring[:] = before
        expected_ring = np.roll(before, -4)
        expected_ring[-4:] *= 0.9

        self.player._callback(self.outdata, 4, None, None)

        np.testing.assert_array_equal(self.outdata, np.zeros((4, 1), dtype=np.float32))
        np.testing.assert_array_equal(self.player.ring, expected_ring)

    def test_volume_and_mute_are_applied_without_changing_samples(self):
        self.player.volume = 0.5
        self.player._callback(self.outdata, 4, None, None)
        np.testing.assert_allclose(self.outdata[:, 0], self.player.samples[:4] * 0.5)

        self.player.pos = 0
        self.player.muted = True
        self.player._callback(self.outdata, 4, None, None)
        np.testing.assert_array_equal(self.outdata, np.zeros((4, 1), dtype=np.float32))


if __name__ == "__main__":
    unittest.main()
