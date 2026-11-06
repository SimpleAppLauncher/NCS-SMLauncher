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
- Release assets include SHA256 checksums generated beside the assets. Verify after download with `shasum -a 256 -c SHA256SUMS.txt`.
- Repository: https://github.com/SimpleAppLauncher/NCS-SMLauncher
- Nokia T20 visual QA verified on Android 13: HashPlay NCS opened to the track list and mirror visualizer without playback.
- Updater verified from 1.0.1: stable v1.1.0 is offered by default; the running v1.1.0 build does not offer itself.

## Known limits

- The in-app updater only offers stable releases by default.
