"""ctypes binding for the allocation-free Rust audio spectrum analyzer.

The Rust library is optional at runtime. The original NumPy FFT remains the
fallback and the reference implementation in tests/test_rust_spectrum.py.
Same-size calls reuse float64 FFT planes and the float32 output plane; Rust
writes only into those buffers and allocates no per-frame heap memory.
"""
import ctypes
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = None
_LOAD_TRIED = False
_SCRATCH = {}


def _register(lib):
    f32p = ctypes.POINTER(ctypes.c_float)
    f64p = ctypes.POINTER(ctypes.c_double)
    lib.ncs_spectrum.restype = ctypes.c_int
    lib.ncs_spectrum.argtypes = [
        f32p, ctypes.c_size_t,  # samples, n
        ctypes.c_double, ctypes.c_double, ctypes.c_double,  # rate, min, max
        ctypes.c_size_t, ctypes.c_double, ctypes.c_double,  # bars, gain, denom
        f64p, f64p, f32p,  # real, imag, output
    ]


def _load():
    global _LIB, _LOAD_TRIED
    if _LOAD_TRIED:
        return _LIB
    _LOAD_TRIED = True
    if sys.platform == "darwin":
        names = ("libncs_spectrum.dylib",)
    elif sys.platform.startswith("linux"):
        names = ("libncs_spectrum.so",)
    elif os.name == "nt":
        names = ("ncs_spectrum.dll", "libncs_spectrum.dll")
    else:
        names = ()
    bases = [os.path.join(_HERE, "native")]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bases.insert(0, meipass)
        bases.insert(1, os.path.join(meipass, "native"))
    for base in bases:
        for name in names:
            path = os.path.join(base, name)
            if not os.path.isfile(path):
                continue
            try:
                lib = ctypes.CDLL(path)
                _register(lib)
                _LIB = lib
                return lib
            except OSError:
                continue
    return None


def available():
    """True if the compiled Rust FFT is available."""
    return _load() is not None


def spectrum(samples, sample_rate, low, high, bars, gain, denominator):
    """Return log-scaled FFT bands in a reused float32 plane.

    `samples` must be a contiguous float32 vector (non-contiguous inputs are
    copied once at the boundary). Do not retain the returned plane across a
    later call with the same shape; the player/visualizer consumes it during
    the current frame.
    """
    lib = _load()
    if lib is None:
        return None
    vector = np.asarray(samples)
    if vector.dtype != np.float32 or not vector.flags.c_contiguous:
        vector = np.ascontiguousarray(vector, dtype=np.float32)
    n = int(vector.size)
    bars = int(bars)
    if n < 2 or n > (1 << 20) or bars < 1 or bars > 512:
        raise ValueError("spectrum size must be power-of-two <= 1M; bars 1..512")
    if n & (n - 1):
        raise ValueError("FFT sample count must be a power of two")
    key = (n, bars)
    planes = _SCRATCH.get(key)
    if planes is None:
        if len(_SCRATCH) >= 8:
            _SCRATCH.clear()
        planes = (np.empty(n, dtype=np.float64),
                  np.empty(n, dtype=np.float64),
                  np.empty(bars, dtype=np.float32))
        _SCRATCH[key] = planes
    real, imag, output = planes
    f32p = ctypes.POINTER(ctypes.c_float)
    f64p = ctypes.POINTER(ctypes.c_double)
    code = lib.ncs_spectrum(
        vector.ctypes.data_as(f32p), n,
        float(sample_rate), float(low), float(high), bars,
        float(gain), float(denominator),
        real.ctypes.data_as(f64p), imag.ctypes.data_as(f64p),
        output.ctypes.data_as(f32p),
    )
    if code != 0:
        raise ValueError("Rust spectrum rejected its input parameters")
    return output
