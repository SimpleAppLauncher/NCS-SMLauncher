#!/bin/sh
# Build the optional Rust spectrum-analysis shared library.
#
# The crate has no third-party dependencies and runs an in-place radix-2 FFT
# into Python-owned scratch arrays (no allocation per frame). The NumPy path
# remains the fallback on systems where this build is unavailable.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CRATE=src/native/spectrum
TARGET_DIR="${CARGO_TARGET_DIR:-$CRATE/target}"

command -v cargo >/dev/null 2>&1 || {
    echo "cargo is missing; Rust spectrum stays disabled and NumPy remains active" >&2
    exit 1
}
cargo test --offline --manifest-path "$CRATE/Cargo.toml"
CARGO_TARGET_DIR="$TARGET_DIR" cargo build --offline --release --manifest-path "$CRATE/Cargo.toml"

case "$(uname -s)" in
    Darwin)
        SOURCE="$TARGET_DIR/release/libncs_spectrum.dylib"
        DEST=src/native/libncs_spectrum.dylib
        ;;
    Linux)
        SOURCE="$TARGET_DIR/release/libncs_spectrum.so"
        DEST=src/native/libncs_spectrum.so
        ;;
    MINGW*|MSYS*|CYGWIN*)
        SOURCE="$TARGET_DIR/release/ncs_spectrum.dll"
        DEST=src/native/ncs_spectrum.dll
        ;;
    *)
        echo "No Rust spectrum artifact rule for $(uname -s)" >&2
        exit 1
        ;;
esac
cp "$SOURCE" "$DEST"
echo "built $DEST"
