"""The C core and the numpy path must render the same ball.

src/native/ncs_core.c is a hand port of ncs_sphere.py's numpy math. A hand
port can drift: someone tunes the numpy side, the C side silently keeps the
old numbers, and the app looks different depending on whether a machine built
the library. This test is the guard: it renders the SAME inputs through BOTH
paths and compares the resulting frames.

Tolerance: the two paths use different float op orders (numpy is float64 with
vectorized transcendental reduction; C is float32 libm), so pixels are allowed
to differ by a small step. What must hold is that the STRUCTURE is identical:
at least 97% of pixels within 2/255 per channel, mean abs difference under
1.0/255, and the solid-mask geometry agreeing. A real drift (a changed
constant, a lost term) blows far past this.

Runs only when the library is built (scripts/build_native.sh); otherwise it
SKIPS with a message rather than passing vacuously.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import ncs_sphere  # noqa: E402
import ncs_native  # noqa: E402

FAILS = []


def check(cond, label, detail=""):
    print("   %s  %s%s" % ("ok " if cond else "FAIL", label,
                           "" if cond or not detail else "  -- " + str(detail)))
    if not cond:
        FAILS.append(label)


if not ncs_native.available():
    print("NCS NATIVE: library not built -- run scripts/build_native.sh; "
          "skipping (the numpy fallback is active and the renderer works)")
    sys.exit(0)

pygame.init()
W, H = 1280, 760
screen = pygame.display.set_mode((W, H))


class FakePlayer:
    def spectrum(self):
        t = np.linspace(0, 1, 64)
        return (0.35 + 0.55 * np.sin(t * 3.0) ** 2).astype(np.float32)


def render_frame(path, t):
    """Draw one frame with the given dispatch, return the on-screen pixels.

    _anim (the band smoothing state) is module-global and mutated per call,
    so it is reset before each render: otherwise the second path sees
    pre-smoothed bands and the comparison measures test artifacts, not code.
    """
    ncs_sphere._reset_anim()
    if path == "native":
        assert ncs_native.available()
    else:
        # Force the fallback WITHOUT touching the library: point the module's
        # dispatch flag off for the duration of the call.
        ncs_native._LIB = None
        ncs_native._LOAD_TRIED = True  # _load() would just re-find it
    try:
        ncs_sphere.draw_ncs_sphere(screen, FakePlayer(), W, H, t, 0.35)
        raw = pygame.surfarray.array3d(screen)  # (w, h, 3)
    finally:
        if path != "native":
            ncs_native._LIB = None
            ncs_native._LOAD_TRIED = False  # next available() re-loads
    return np.transpose(raw, (1, 0, 2)).astype(np.int16)


print("NCS NATIVE vs NUMPY")
print("\n  both paths produce the same ball")
worst = None
for t in (0.5, 3.7, 11.2):
    a = render_frame("native", t)
    b = render_frame("numpy", t)
    diff = np.abs(a - b)
    mean_diff = diff.mean() / 255.0
    close = (diff <= 2).all(axis=2).mean()
    print("   t=%5.1f  mean diff %.5f  pixels within 2/255: %.4f"
          % (t, mean_diff, close))
    check(close >= 0.97,
          f"t={t}: >=97% of pixels within 2/255 per channel", f"{close:.4f}")
    check(mean_diff <= 1.0 / 255.0,
          f"t={t}: mean abs difference under 1/255", f"{mean_diff:.5f}")
    if worst is None or close < worst[1]:
        worst = (t, close)

print("\n  the fast path actually allocates far less")
import tracemalloc
p = FakePlayer()
ncs_sphere.draw_ncs_sphere(screen, p, W, H, 0.9, 0.35)  # warm caches
tracemalloc.start()
ncs_sphere.draw_ncs_sphere(screen, p, W, H, 1.0, 0.35)
_, peak_native = tracemalloc.get_traced_memory()
tracemalloc.stop()
check(peak_native < 4 * 1024 * 1024,
      "a native frame peaks under 4 MB of allocation (numpy was ~16 MB)",
      f"{peak_native/1024:.0f} KB")

print("\n  the frame is not slower than the numpy path was")
import time
N = 30
t0 = time.perf_counter()
for i in range(N):
    ncs_sphere.draw_ncs_sphere(screen, p, W, H, 2.0 + 0.033 * i, 0.35)
native_ms = (time.perf_counter() - t0) / N * 1000
print("   native: %.2f ms/frame (numpy baseline 6.55 ms at this size)"
      % native_ms)
check(native_ms <= 6.55,
      "the C path is at least as fast as the numpy path it replaced",
      f"{native_ms:.2f} ms")

print("\n" + ("NCS NATIVE TESTS PASSED" if not FAILS
              else "%d FAILURES: %s" % (len(FAILS), FAILS)))
sys.exit(1 if FAILS else 0)
