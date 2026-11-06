"""Rust FFT must match the existing NumPy spectrum for desktop + disc players."""
import os
import sys
import time
import tracemalloc

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import ncs_spectrum_native as native  # noqa: E402

if not native.available():
    print("RUST SPECTRUM: library not built; run scripts/build_spectrum.sh; "
          "skipping (NumPy reference remains active)")
    raise SystemExit(0)

FAILS = []


def check(label, cond, detail=""):
    print("   %s  %s%s" % ("ok " if cond else "FAIL", label,
                           "" if cond or not detail else "  -- " + str(detail)))
    if not cond:
        FAILS.append(label)


def numpy_reference(samples, sample_rate, bars, low, high, gain):
    window = samples.copy()
    spec = np.abs(np.fft.rfft(window * np.hanning(len(window))))
    freqs = np.fft.rfftfreq(len(window), 1.0 / sample_rate)
    edges = np.geomspace(low, high, bars + 1)
    values = []
    for i in range(bars):
        mask = (freqs >= edges[i]) & (freqs < edges[i + 1])
        values.append(spec[mask].max() if mask.any() else 0.0)
    values = np.array(values, dtype=np.float32)
    values = np.log1p(values * gain) / np.log1p(gain * 5.0)
    return np.clip(values, 0, 1)


print("RUST SPECTRUM vs NUMPY")
N = 4096
rng = np.random.default_rng(417)
cases = [
    ("silence", np.zeros(N, dtype=np.float32), 64, 50.0, 16000.0, 8.0),
    ("440Hz tone", np.sin(2*np.pi*440*np.arange(N)/44100).astype(np.float32),
     64, 50.0, 16000.0, 8.0),
    ("seeded noise", rng.normal(0, 0.18, N).astype(np.float32),
     64, 50.0, 16000.0, 8.0),
    ("disc bands", rng.normal(0, 0.18, N).astype(np.float32),
     32, 50.0, 2000.0, 3.0),
]
for label, samples, bars, low, high, gain in cases:
    expected = numpy_reference(samples, 44100.0, bars, low, high, gain)
    actual = native.spectrum(samples, 44100.0, low, high, bars,
                             gain, np.log1p(gain * 5.0))
    max_error = float(np.max(np.abs(actual - expected)))
    mean_error = float(np.mean(np.abs(actual - expected)))
    print(f"   {label}: max abs {max_error:.3g}; mean abs {mean_error:.3g}")
    check(f"{label}: maximum error <= 2e-5", max_error <= 2e-5,
          f"{max_error:.6g}")
    check(f"{label}: output is finite and bounded", np.isfinite(actual).all()
          and np.all((actual >= 0) & (actual <= 1)))

# The result is backed by reusable scratch; stable output object confirms the
# Python binding does not allocate new arrays on every frame.
s1 = native.spectrum(cases[1][1], 44100.0, 50.0, 16000.0, 64, 8.0,
                     np.log1p(40.0))
s2 = native.spectrum(cases[1][1], 44100.0, 50.0, 16000.0, 64, 8.0,
                     np.log1p(40.0))
check("same-size calls reuse the output plane", s1 is s2)

N_RUNS = 100
start = time.perf_counter()
for _ in range(N_RUNS):
    native.spectrum(cases[1][1], 44100.0, 50.0, 16000.0, 64, 8.0,
                    np.log1p(40.0))
ms = (time.perf_counter() - start) * 1000 / N_RUNS
print(f"   mean frame cost: {ms:.3f} ms")
check("Rust FFT stays under 1 ms/frame", ms < 1.0, f"{ms:.3f} ms")

print("\n" + ("RUST SPECTRUM TESTS PASSED" if not FAILS
              else f"{len(FAILS)} FAILURES: {FAILS}"))
sys.exit(1 if FAILS else 0)
