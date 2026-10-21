"""ctypes binding for the NCS ball's C core (src/native/ncs_core.c).

The renderer's per-frame math moved into C to stop the ~16 MB/frame of numpy
temporary allocations (the visible symptom: RAM spikes while the ball
animates). This module owns the binding and the preallocated scratch buffers;
ncs_sphere.py dispatches to it when `available()` and otherwise uses its own
numpy code, which stays the reference implementation the equivalence test
(tests/test_ncs_native.py) compares against. The numpy path is therefore NOT
duplicated here -- there is exactly one numpy implementation and one C
implementation, and the test keeps them honest.

The library is built by scripts/build_native.sh. It is OPTIONAL: a machine
without it gets identical-looking output from the numpy path, just with more
allocation churn. Nothing here may raise at import time -- a missing library
is a speed downgrade, not an error.
"""
import ctypes
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = None
_LOAD_TRIED = False


def _load():
    """Find and register the shared library. Never raises."""
    global _LIB, _LOAD_TRIED
    if _LOAD_TRIED:
        return _LIB
    _LOAD_TRIED = True
    names = []
    if sys.platform == "darwin":
        names.append("libncs_core.dylib")
    elif sys.platform.startswith("linux"):
        names.append("libncs_core.so")
    names.append("libncs_core.so")  # explicit override always works
    # A frozen (PyInstaller) bundle has no src/ tree: binaries declared in
    # HashPlay.spec land in sys._MEIPASS. Check there too, so a shipped app
    # gets the fast path instead of silently falling back to numpy.
    bases = [_HERE]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bases.insert(0, meipass)
    for base in bases:
        for name in names:
            path = os.path.join(base, "native" if base == _HERE else "", name)
            if not os.path.exists(path):
                continue
            try:
                lib = ctypes.CDLL(path)
                _register(lib)
                _LIB = lib
                return _LIB
            except OSError:
                continue
    return None


def _register(lib):
    """Declare the two exported functions' signatures."""
    f32p = ctypes.POINTER(ctypes.c_float)
    i32p = ctypes.POINTER(ctypes.c_int)
    # void ncs_project(bx, by, bz, la, lo, n,
    #                  ang, tilt, t, bass, mid, high, disp_amp,
    #                  cx, cy, radius, ridge_lo, ridge_pow,
    #                  cr_, cg_, cb_, dr_, dg_, db_,
    #                  scratch_f, sx, sy, cr, cg, cb, ridge, rim,
    #                  fmin, fmax)
    lib.ncs_project.restype = None
    lib.ncs_project.argtypes = [
        f32p, f32p, f32p, f32p, f32p,   # bx, by, bz, la, lo
        ctypes.c_int,                    # n
        ctypes.c_float, ctypes.c_float, ctypes.c_float,  # ang tilt t
        ctypes.c_float, ctypes.c_float, ctypes.c_float,  # bass mid high
        ctypes.c_float,                  # disp_amp
        ctypes.c_float, ctypes.c_float, ctypes.c_float,  # cx cy radius
        ctypes.c_float, ctypes.c_float,  # ridge_lo, ridge_pow
        ctypes.c_float, ctypes.c_float, ctypes.c_float,  # crest
        ctypes.c_float, ctypes.c_float, ctypes.c_float,  # dark
        f32p, f32p, f32p, f32p, f32p, f32p, f32p, f32p,  # out ptrs
        f32p, f32p,                      # fmin, fmax
    ]
    # void ncs_splat(buf, w, h, n, sx, sy, r, g, b, kdx, kdy, kwt,
    #                k, weight)
    lib.ncs_splat.restype = None
    lib.ncs_splat.argtypes = [
        f32p,                            # buf (h, w, 3)
        ctypes.c_int, ctypes.c_int, ctypes.c_int,        # w, h, n
        f32p, f32p,                      # sx, sy (float32 px coords)
        f32p, f32p, f32p,                # r, g, b
        i32p, i32p, f32p,                # kernel dx, dy, weight
        ctypes.c_int, ctypes.c_float,    # k, weight
    ]


def available():
    """True if the C core is loaded. Cheap after the first call."""
    return _load() is not None


# --- preallocated scratch, keyed by size ------------------------------------
# The whole point is zero per-frame allocation, so every array the C path
# writes lives here, grown only if the point count changes.
_pt_scratch = {}


def _point_buffers(n):
    s = _pt_scratch.get(n)
    if s is None:
        if len(_pt_scratch) > 4:
            _pt_scratch.clear()
        f32 = np.float32
        s = {
            "scratch_f": np.zeros(n, f32),
            "sx": np.zeros(n, f32),
            "sy": np.zeros(n, f32),
            "cr": np.zeros(n, f32),
            "cg": np.zeros(n, f32),
            "cb": np.zeros(n, f32),
            "ridge": np.zeros(n, f32),
            "rim": np.zeros(n, f32),
            "fmin": np.zeros(1, f32),
            "fmax": np.zeros(1, f32),
        }
        _pt_scratch[n] = s
    return s


def project(bx, by, bz, la, lo, ang, tilt, t, bass, mid, high,
            disp_amp, cx, cy, radius, ridge_lo, ridge_pow,
            crest, dark):
    """Rotation -> field -> projection -> shading, in C.

    bx/by/bz are the CONTIGUOUS per-axis planes of the base cloud (a strided
    pts[:, i] view reads garbage through ctypes -- see the geometry cache
    comment in ncs_sphere.py). Returns (sx, sy, cr, cg, cb, ridge, rim) as
    numpy arrays over the REUSED scratch buffers -- the caller must not hold
    references across frames (ncs_sphere.py consumes them within the same
    call, like the Android port does with its scratch planes).
    """
    lib = _load()
    n = bx.shape[0]
    s = _point_buffers(n)
    f32p = ctypes.POINTER(ctypes.c_float)

    lib.ncs_project(
        bx.ctypes.data_as(f32p),
        by.ctypes.data_as(f32p),
        bz.ctypes.data_as(f32p),
        la.ctypes.data_as(f32p),
        lo.ctypes.data_as(f32p),
        n,
        ang, tilt, t, bass, mid, high, disp_amp, cx, cy, radius,
        ridge_lo, ridge_pow,
        crest[0], crest[1], crest[2], dark[0], dark[1], dark[2],
        s["scratch_f"].ctypes.data_as(f32p),
        s["sx"].ctypes.data_as(f32p),
        s["sy"].ctypes.data_as(f32p),
        s["cr"].ctypes.data_as(f32p),
        s["cg"].ctypes.data_as(f32p),
        s["cb"].ctypes.data_as(f32p),
        s["ridge"].ctypes.data_as(f32p),
        s["rim"].ctypes.data_as(f32p),
        s["fmin"].ctypes.data_as(f32p),
        s["fmax"].ctypes.data_as(f32p),
    )
    # The planes are float32, the PRE-truncation values: the splat receives
    # them directly (C casts per tap, identical to numpy's .astype(int32)),
    # which avoids converting a plane per frame. The caller truncates for
    # any integer use (the numpy fallback path does its own cast).
    return (s["sx"], s["sy"], s["cr"], s["cg"], s["cb"], s["ridge"], s["rim"])


_kernel_scratch = None


def _kernel_buffers():
    global _kernel_scratch
    if _kernel_scratch is None:
        _kernel_scratch = {
            "dx": np.zeros(16, np.int32),
            "dy": np.zeros(16, np.int32),
            "wt": np.zeros(16, np.float32),
        }
    return _kernel_scratch


def splat(buf, w, h, sx, sy, r, g, b, offsets, weight=1.0):
    """Kernel scatter in C. `buf` must be the caller's reused accumulator."""
    lib = _load()
    n = sx.shape[0]
    k = len(offsets)
    if k > 16:
        raise ValueError("kernel larger than the C core's 16-tap scratch")
    kb = _kernel_buffers()
    for j, off in enumerate(offsets):
        kb["dx"][j] = off[0]
        kb["dy"][j] = off[1]
        kb["wt"][j] = off[2] if len(off) == 3 else 1.0

    f32p = ctypes.POINTER(ctypes.c_float)
    i32p = ctypes.POINTER(ctypes.c_int)
    lib.ncs_splat(
        buf.ctypes.data_as(f32p),
        w, h, n,
        sx.ctypes.data_as(f32p),          # float32 px coords (pre-truncation)
        sy.ctypes.data_as(f32p),
        r.ctypes.data_as(f32p),
        g.ctypes.data_as(f32p),
        b.ctypes.data_as(f32p),
        kb["dx"].ctypes.data_as(i32p),
        kb["dy"].ctypes.data_as(i32p),
        kb["wt"].ctypes.data_as(f32p),
        k, float(weight),
    )
    return buf
