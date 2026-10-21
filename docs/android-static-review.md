# Android App Static Review

## 1. First-run / Launch (wizard mentioned)

**Finding 1 - SEVERITY: INFO - No Android "first-run setup wizard" present**
- **File**: Android codebase (`android/` only inspected)
- **Issue**: The desktop app has a Python `setup_wizard.py` (first-run flow). No equivalent UI/logic exists in the Android app (no SetupWizard class, no first-run state). The app initializes directly in `MainActivity.onCreate()` (sets pending magnet from intent, shows `PlayerScreen`).
- **Impact**: If the user expected Android wizard - it's not there. Not a crash risk. 
- **Fix (one-line)**: If wizard is required on Android, implement it; else document desktop-only.
- **Note**: No crash on launch from missing wizard.

## 2. Flavor behavior (full vs lite, TorrentManager no-op)

**Finding 2 - SEVERITY: LOW - Lite TorrentManager correctly no-ops (no silent success)**
- **File**: `android/app/src/lite/java/com/giathinh/hashplay/TorrentManager.kt:51-55`
- **Issue**: `start()` sets message "Torents are not in the lite build — use the full APK for that." and returns `false`. Shared UI (`PlayerScreen`) treats failures by showing `tMessage`/statuses; when magnet arrives, it calls `start()` and consumes magnet regardless. No code path treats a false/failed result as OK. 
- **Impact**: No silent reporting of success when download cannot start.
- **Fix (one-line)**: None needed - behavior is correct.

**Finding 3 - SEVERITY: LOW - Lite normalize rejects all non-blank input consistently**
- **File**: `android/app/src/lite/java/com/giathinh/hashplay/TorrentManager.kt:60-64`
- **Issue**: `normalize` returns `null` for any non-blank input (does not attempt to accept valid magnet/hash forms). Full accepts magnet/http or hex/base32 hashes. This is a stub; it does not cause crashes. Call sites don't rely on lite accepting valid URIs to function (start() bails). 
- **Impact**: API shape matches; no runtime crash risk from lite.
- **Fix (one-line)**: Consider mirroring full's shape validation if you want "rejects bad input" symmetry, but not required.

**Finding 4 - SEVERITY: MEDIUM - Full TorrentManager creates long-lived coroutine/session with no explicit teardown from UI**
- **File**: `android/app/src/full/java/com/giathinh/hashplay/TorrentManager.kt:33,100-107`
- **Issue**: `CoroutineScope(SupervisorJob() + Dispatchers.IO)` started polling loop `while (isActive)` with `delay(1000)`. `SessionManager` is started and stored; no `stop()`/`cancel()` called when `PlayerScreen` is disposed (screen only disposes controller). Instance lives as long as `PlayerScreen` composition via `remember { TorrentManager(context) }`. 
- **Impact**: Thread/coroutine leak across config changes/disposals; not a launch crash, but runtime resource leak. 
- **Fix (one-line)**: Add an API (e.g. `close()`/`release()`) and call from `DisposableEffect` in `PlayerScreen`.

**Finding 5 - SEVERITY: LOW - Torrent download completion triggers library rescan safely**
- **File**: `android/app/src/full/java/com/giathinh/hashplay/TorrentManager.kt:58-66,110-117`
- **Issue**: On `TorrentFinishedAlert`, sets message starting with `✔` and calls `scanDownloaded()` which lists audio files in `downloadDir` and calls `MediaScannerConnection.scanFile`. `downloadDir` created via `mkdirs()` in getter; listing returns null if dir missing - handled. 
- **Impact**: No crash risk; correct integration with library refresh.

## 3. Playback: lifecycle, release, audio focus

**Finding 6 - SEVERITY: HIGH - Player owns/plays via MediaController bound to PlaybackService (shared player) - correct architecture, but check release semantics**
- **File**: `android/app/src/main/java/com/giathinh/hashplay/PlayerController.kt:33-39,50-53,86-96,119-136`
- **Issue**: Controller binds asynchronously to service-owned ExoPlayer via `MediaController.Builder`. Buffers `pendingPlay` until ready. `release()` detaches controller (`c?.release()`) but does **not** release service player - correct (service owns it). `DisposableEffect` in `PlayerScreen` calls `controller.release()` on dispose. 
- **Impact**: Correct fix from previous architecture; avoids killing playback when activity leaves.
- **Fix (one-line)**: None needed.

**Finding 7 - SEVERITY: MEDIUM - PlaybackService may keep player running if not playing when task removed**
- **File**: `android/app/src/main/java/com/giathinh/hashplay/PlaybackService.kt:80-84`
- **Issue**: `onTaskRemoved` does `if (player?.isPlaying != true) stopSelf()`; if playing, it does not stop - service continues (foreground if media notification). That’s reasonable for background playback. No crash. 
- **Impact**: Expected behavior for media apps.
- **Fix (one-line)**: None needed.

**Finding 8 - SEVERITY: MEDIUM - PlaybackService creates player with audio attributes and handleAudioBecomingNoisy; session listener behavior**
- **File**: `android/app/src/main/java/com/giathinh/hashplay/PlaybackService.kt:40-65`
- **Issue**: Sets `setHandleAudioBecomingNoisy(true)` and audio attributes (music/media). Adds listener that auto-plays when transitioning to next item while paused (`if (!playWhenReady && mediaItemCount>0) prepare()+play()`). This is a specific UX choice (matches desktop comment). Could surprise if paused deliberately, but not a crash. 
- **Impact**: Behavior is intentional; no crash risk.

**Finding 9 - SEVERITY: MEDIUM - No explicit AudioFocus request handling visible beyond ExoPlayer's default?**
- **File**: `android/app/src/main/java/com/giathinh/hashplay/PlaybackService.kt:43-49`, `PlayerController.kt` (no AF code)
- **Issue**: ExoPlayer is built with `handleAudioFocus = true` in builder? Looking at builder: `.setAudioAttributes(..., /* handleAudioFocus = */ true)`. So ExoPlayer manages audio focus. That’s fine. No custom `AudioManager.requestAudioFocus` code - relies on ExoPlayer. 
- **Impact**: Should work; no obvious crash.
- **Fix (one-line)**: None needed if ExoPlayer handles it.

**Finding 10 - SEVERITY: MEDIUM - Animation loop drives spectrum/position; release is correct**
- **File**: `android/app/src/main/java/com/giathinh/hashplay/PlayerScreen.kt:46-54,99`
- **Issue**: `LaunchedEffect(Unit)` runs infinite frame loop calling `controller.tick(...)` at ~30Hz; cancelled on dispose. `DisposableEffect` calls `controller.release()`. No leak of callbacks beyond coroutine lifecycle. 
- **Impact**: Safe.

**Finding 11 - SEVERITY: LOW - Config change handling**
- **File**: `android/app/src/main/AndroidManifest.xml:21` (`android:configChanges="orientation|screenSize|keyboardHidden"`)
- **Issue**: Activity handles config changes itself; with Compose this avoids activity recreation. State is preserved via Compose `remember`/state holders; `pendingMagnet` is in Activity property (not saved to Bundle) - if recreated without new intent and process killed? But activity not recreated by this flag in normal orientation changes. Generally fine.
- **Impact**: No crash risk.

## 4. Hardcoded paths, localhost URLs, file permissions

**Finding 12 - SEVERITY: MEDIUM - Uses `Uri.fromFile()` as fallback for track playback (scoped storage compatibility)**
- **File**: `android/app/src/main/java/com/giathinh/hashplay/PlayerController.kt:108-120`
- **Issue**: Prefers `ContentUris.withAppendedId(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI, track.id)` when `track.id>0`. Falls back to `Uri.fromFile(File(track.path))`. On Android 7+ (Nougat+) sharing `file://` URIs can trigger `FileUriExposedException` if exposed to other apps/processes; ExoPlayer reading local files usually works, but it’s a known pitfall. Also with scoped storage, `MediaStore.DATA` paths may not be directly readable via `File` in all cases. 
- **Impact**: Potential crash on playback when falling back to file URI depending on targetSdk/ExoPlayer usage. 
- **Fix (one-line)**: Prefer ID-based URI always when available; if ID<=0 and path is non-empty, consider using `FileProvider` or avoid playback for such tracks.

**Finding 13 - SEVERITY: HIGH - `LibraryScanner` queries `MediaStore.Audio.Media.DATA` and throws if missing; also treats null path as skip but path might be required**
- **File**: `android/app/src/main/java/com/giathinh/hashplay/LibraryScanner.kt:36,49-52`
- **Issue**: Projects and calls `getColumnIndexOrThrow(MediaStore.Audio.Media.DATA)`. Some devices/ROMs or certain media sources may not have DATA column - `IllegalArgumentException`. Also they `continue` if `c.getString(iP)` is null, which is safe. 
- **Impact**: Crash on first library scan (launch/refresh) on affected devices. 
- **Fix (one-line)**: Replace `getColumnIndexOrThrow(DATA)` with `getColumnIndex(DATA)` and only use path if >=0 and non-null; when path unavailable, still allow playback via ID (set path empty and rely on ID in PlayerController).

**Finding 14 - SEVERITY: MEDIUM - TorrentManager uses `getExternalFilesDir(null)` for downloads**
- **File**: `android/app/src/full/java/com/giathinh/hashplay/TorrentManager.kt:43-45`, `lite/.../TorrentManager.kt:47-49`
- **Issue**: `File(context.getExternalFilesDir(null), "torrent-downloads")`. No hardcoded absolute device paths, no localhost URLs. Uses app-specific external storage (no broad external storage permission needed beyond media access). Correct and safe. 
- **Impact**: No breakage on real devices; respects scoped storage.

**Finding 15 - SEVERITY: LOW - Manifest has `android:usesCleartextTraffic="true"`**
- **File**: `android/app/src/main/AndroidManifest.xml:16`
- **Issue**: Allows cleartext HTTP. If any code ever loads HTTP (magnet normalization accepts `http` in full flavor - `normalize` returns raw if starts with `http`), cleartext is allowed. No localhost hardcoded in Android code. Torrent uses magnet/infohash via libtorrent; no embedded localhost URLs found. 
- **Impact**: Potential network security concern if HTTP used, but not a crash. No obvious localhost references in Android sources.

**Finding 16 - SEVERITY: LOW - Permissions declared but no runtime request code**
- **File**: `android/app/src/main/AndroidManifest.xml:4-10`
- **Issue**: Declares `READ_MEDIA_AUDIO` (API 33+), `READ_EXTERNAL_STORAGE` (maxSdk 32), `FOREGROUND_SERVICE*`, `POST_NOTIFICATIONS`. No runtime permission requests in code (no `ActivityResultContracts.RequestPermission`, no `requestPermissions` calls). On Android 13+, `READ_MEDIA_AUDIO` is runtime - `LibraryScanner.query` will return empty cursor or may be restricted if permission denied; app shows empty library but doesn’t crash. 
- **Impact**: Functional issue (empty library) on first run, not a crash. 

## 5. Misc bugs / edge cases

**Finding 17 - SEVERITY: LOW - PlayerController listener only reacts to `onIsPlayingChanged`**
- **File**: `android/app/src/main/java/com/giathinh/hashplay/PlayerController.kt:69-76`
- **Issue**: `update()` copies `isPlaying`, `positionMs`, `durationMs`. Also listens to `onIsPlayingChanged`. Duration/position can change due to media item transition/prepare; `onMediaItemTransition` is also listened to (line 38-42 in service context? In PlayerController, listener only overrides `onIsPlayingChanged`). Also when binding, they add listener with both `onIsPlayingChanged` and `onMediaItemTransition` (line ~37-43 in PlayerController). Wait - look up actual: PlayerController adds listener with `onIsPlayingChanged` and `onMediaItemTransition`. Yes in the code I see: `c.addListener(object : Player.Listener { override fun onIsPlayingChanged...; override fun onMediaItemTransition... })`. So transitions update state. OK.

**Finding 18 - SEVERITY: MEDIUM - NcsSphere creates `Bitmap` every frame in Canvas draw**
- **File**: `android/app/src/main/java/com/giathinh/hashplay/NcsSphere.kt:225-231`
- **Issue**: In `Canvas` draw lambda, does `Bitmap.createBitmap(buf, w,h, ARGB_8888).asImageBitmap()` every frame. Allocation per frame + conversion; could cause GC churn, jank. Not a crash. 
- **Impact**: Performance; no crash risk on first run.

**Finding 19 - SEVERITY: LOW - `track.path` stored even if fallback to ID; could be stale/invalid**
- **File**: `android/app/src/main/java/com/giathinh/hashplay/LibraryScanner.kt:53-58`, `PlayerController.kt:112-120`
- **Issue**: Path comes from `MediaStore.DATA` when present. If not present, we `continue` (skip track) - but see Finding 13. With fix to allow missing DATA, we need to handle. Current behavior is conservative.

## Concrete file:line findings ranked by severity

1. **SEVERITY: HIGH** — `LibraryScanner.kt:49` (`getColumnIndexOrThrow(MediaStore.Audio.Media.DATA)`) — can throw `IllegalArgumentException` on some devices. **Fix**: use `getColumnIndex` and handle missing column (prefer ID-based playback).  
2. **SEVERITY: HIGH** — `PlayerController.kt:118-120` (fallback `Uri.fromFile(File(track.path))`) — potential `FileUriExposedException` / scoped storage access issues when falling back. **Fix**: avoid file:// fallback when ID unavailable; skip or handle gracefully.  
3. **SEVERITY: MEDIUM** — `TorrentManager.kt:33,100-107` (full) — uncoordinated coroutine scope + SessionManager lifecycle. **Fix**: add `release()`/`stop()` and dispose from UI.  
4. **SEVERITY: MEDIUM** — `LibraryScanner.kt` (missing DATA case) — combine with #1: if DATA missing, don’t crash; ensure Track can be played via ID. **Fix**: make path nullable/fallback-safe.  
5. **SEVERITY: MEDIUM** — `PlaybackService.kt:80-84` — `onTaskRemoved` only stops if not playing (intentional). **Fix**: consider foreground service behavior; not a crash.  
6. **SEVERITY: MEDIUM** — `NcsSphere.kt:228-231` — per-frame Bitmap allocation. **Fix**: reuse `ImageBitmap`/buffer where possible.  
7. **SEVERITY: LOW** — `Manifest.xml:16` — `usesCleartextTraffic="true"`. **Fix**: set false unless required; restrict with network security config.  
8. **SEVERITY: LOW** — `Manifest/permissions` — no runtime permission requests. **Fix**: request `READ_MEDIA_AUDIO` (API33+) at runtime.  
9. **SEVERITY: LOW** — `TorrentManager.kt:60-64` (lite) — normalize rejects all non-blank (stub). **Fix**: none required; matches API shape.  
10. **SEVERITY: INFO** — No Android setup wizard. **Fix**: none - desktop-only.

## Category answers (as requested)

1. **Launch/first-run wizard**: No wizard implementation in Android code. Launch path is `MainActivity.onCreate()` -> set content with `PlayerScreen`. Main risks: (a) library scan can throw if `MediaStore.DATA` column missing (#1); (b) playback fallback to file:// (#2). No uninitialized state that obviously throws on first run otherwise.

2. **Flavors full/lite**: Lite’s `TorrentManager.start()` returns `false` with message - never returns true; no code path treats failure as success. UI consumes magnet after start but doesn’t assume success. Full correctly reports `✔ Finished...` on completion and triggers rescan. **No silent success found.**

3. **Playback lifecycle**: Uses MediaController bound to PlaybackService (shared player). Controller detaches on dispose without releasing service player. Service manages audio attributes, noisy handling, media session. Animation loop drives tick. No obvious leaks/crashes. Potential issues: fallback URI (#2), missing DATA (#1).

4. **Hardcoded paths/localhost/permissions**: Downloads go to `getExternalFilesDir(null)/torrent-downloads` (no hardcoded absolute paths). No localhost URLs in Android sources. `usesCleartextTraffic="true"`. No runtime permission requests for media/audio (API33+). `READ_EXTERNAL_STORAGE` limited to SDK<=32. No file permission grants beyond standard.
