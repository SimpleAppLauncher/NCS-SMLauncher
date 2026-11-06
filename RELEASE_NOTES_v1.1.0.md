# HashPlay 1.1.0

Stable release for the desktop app and Android flavors.

## Included

- Desktop HashPlay for macOS arm64, Linux x86_64, and Windows x64.
- Android full, lite, and NCS APKs.
- Rust spectrum analysis on desktop builds where the native library is present, with the existing NumPy fallback retained.
- Authenticated EF Launcher HTTP/SSE bridge on the full desktop build, with new-install defaults documented in `docs/ef-launcher-api.md`.
- Startup fix so the desktop control API does not perform a synchronous reverse-DNS lookup while binding.

## Verification

- Every Python file is compiled individually before release.
- Desktop tests run headlessly without opening an audio device or playing sound.
- CI builds all desktop platforms and all Android flavors.
- Release assets include SHA256 checksums generated beside the assets.

## Known limits

- Nokia tablet visual QA must be listed as pending unless the device was unlocked and the UI was actually inspected.
- The in-app updater only offers stable releases by default.
