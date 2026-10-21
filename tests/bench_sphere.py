#!/usr/bin/env python3
"""Benchmark one NCS ball frame, headless, at the window size the app uses."""
import os, sys, time
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, "/Users/giathinh/ncs-music-launcher/src")
import pygame, numpy as np
import ncs_sphere

pygame.init()
W, H = 1280, 760
screen = pygame.display.set_mode((W, H))


class FakePlayer:
    def spectrum(self):
        t = np.linspace(0, 1, 64)
        return (0.35 + 0.55 * np.sin(t * 3.0) ** 2).astype(np.float32)


p = FakePlayer()
# warm-up (initializes geometry/anim caches)
for i in range(3):
    ncs_sphere.draw_ncs_sphere(screen, p, W, H, 0.1 * i, 0.35)

N = 40
t0 = time.perf_counter()
for i in range(N):
    ncs_sphere.draw_ncs_sphere(screen, p, W, H, 1.0 + 0.033 * i, 0.35)
dt = (time.perf_counter() - t0) / N * 1000
import ncs_native
path = "native C" if ncs_native.available() else "numpy fallback"
print(f"{path}: {dt:.2f} ms/frame at {W}x{H} (internal density {ncs_sphere._density()[1]})")

# allocation estimate: count temporaries by tracing one frame with tracemalloc
import tracemalloc
tracemalloc.start()
ncs_sphere.draw_ncs_sphere(screen, p, W, H, 9.9, 0.35)
cur, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
print(f"single frame alloc: {cur/1024:.0f} KB net, {peak/1024:.0f} KB peak")
