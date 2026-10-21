#!/usr/bin/env python3
"""Render the real desktop app UI to a PNG, fully offscreen.

SDL_VIDEODRIVER=dummy means pygame never opens a window: the app's own
draw_ui/draw_visualizer run against an in-memory surface and the result is
saved as a file. This is how the desktop is shown without ever launching the
GUI -- the standing rule is that the desktop app must not be opened, so this
preview is a fake player plus the real renderer.
"""
import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, "/Users/giathinh/ncs-music-launcher/src")

import numpy as np
import pygame
import ncs_launcher as nl
import ncs_sphere as sphere_mod

pygame.init()
W, H = 1280, 760
pygame.display.set_mode((W, H), pygame.RESIZABLE)
screen = pygame.display.get_surface()
screen.fill((10, 12, 18))

font = pygame.font.SysFont("consolas,menlo,dejavusansmono", 16)
font_big = pygame.font.SysFont("consolas,menlo,dejavusansmono", 20, bold=True)


class FakePlayer:
    """Everything draw_ui and draw_visualizer touch, and nothing they don't."""

    def __init__(self):
        self.track_path = "/music/Never Gonna Give You Up.mp3"
        self.paused = True          # never playing, by construction
        self.volume = 0.8
        self.muted = False
        self.visualizer_mode = 0
        self._t = 1.7

    def spectrum(self):
        t = np.linspace(0, 1, 32)
        return (0.35 + 0.55 * np.sin(t * 3.0 + self._t) ** 2).astype(np.float32)

    def bass(self):
        return 0.42

    def duration(self):
        return 213_000

    def position(self):
        return 47_000

    def track_metadata(self):
        return {"title": "Never Gonna Give You Up", "artist": "Rick Astley"}


tracks = [
    {"path": "/music/A Thousand Years.mp3"},
    {"path": "/music/Never Gonna Give You Up.mp3"},
    {"path": "/music/Sunset Lover (extended).mp3"},
    {"path": "/music/The Night We Met.mp3"},
]

player = FakePlayer()
# The real visualizer (NCS ball) at the real geometry...
nl.draw_visualizer(screen, player, W, H, "radial", player._t, player.track_metadata())
# ...and the real UI chrome on top.
nl.draw_ui(screen, font, font_big, tracks, 1, player, W, H,
           muted=False, folder="/music")

out = "/tmp/desktop_app_preview.png"
pygame.image.save(screen, out)
print("saved", out, os.path.getsize(out), "bytes")
