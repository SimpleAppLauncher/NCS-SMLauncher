#!/bin/sh
# Compile the NCS ball's C core into a shared library.
#
# The desktop renderer optionally uses this library (loaded via ctypes from
# src/ncs_native.py) to compute the ball's per-frame math without numpy's
# per-frame allocation churn (~16 MB/frame, see ncs_core.c's header comment).
# If the library is missing, the renderer falls back to the numpy path
# transparently -- building it is a speed upgrade, not a requirement.
#
# Output: src/native/libncs_core.dylib (macOS) / libncs_core.so (Linux)
# Idempotent: safe to run on every build; cheap (one C file, -O2).

set -eu
cd "$(dirname "$0")/.."

SRC=src/native/ncs_core.c
OUT_MAC=src/native/libncs_core.dylib
OUT_LINUX=src/native/libncs_core.so

CC=${CC:-cc}
CFLAGS=${NCS_CFLAGS:--O2 -fPIC -ffast-math}

case "$(uname -s)" in
    Darwin)
        # -undefined dynamic_lookup: python does not need to link anything;
        # this library uses only libm.
        $CC $CFLAGS -shared -o "$OUT_MAC" "$SRC"
        echo "built $OUT_MAC"
        ;;
    Linux)
        $CC $CFLAGS -shared -o "$OUT_LINUX" "$SRC" -lm
        echo "built $OUT_LINUX"
        ;;
    *)
        echo "no native build rule for $(uname -s); the numpy fallback stays active" >&2
        exit 1
        ;;
esac
