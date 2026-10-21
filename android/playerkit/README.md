# HashPlay PlayerKit

The HashPlay player as a component. One Android library module (`:playerkit`)
that any app can depend on to get: background music playback with a system
media notification, a MediaStore library scanner, the NCS sphere visualizer,
the 8-bit pixel typefaces, and the in-app gain — without inheriting HashPlay's
app-specific surface (torrenting, flavor routing, video backgrounds).

## What's inside

| Piece | File | What it gives you |
|---|---|---|
| Playback service | `PlaybackService.kt` | The ONE ExoPlayer, wrapped in a Media3 `MediaSessionService`. Plays in the background, shows the lock-screen / shade notification, answers Bluetooth + headset + Assistant. |
| Player handle | `PlayerController.kt` | Compose-friendly `StateFlow` state, queue management, skip/seek/gain, broken-track skipping. Binds to the service asynchronously; a play pressed before binding is not lost. |
| Library | `LibraryScanner.kt` | `MediaStore` audio scan that cannot crash (no `DATA` column dependence, lenient columns, `SecurityException` handled). `Track.uri()` is scoped-storage-safe. |
| Visualizer | `NcsSphere.kt`, `Visualizer.kt` | The NCS ball (reused per-frame buffers, no per-frame allocation) and the bar visualizer. |
| First-run + permissions | `SetupState.kt`, `Permissions.kt` | Runtime permission requests for `READ_MEDIA_AUDIO` (+`POST_NOTIFICATIONS` on 13+) and a never-nags-again first-run gate. |
| Look | `Theme.kt`, `PixelType.kt`, `HashSettings.kt`, `NcsPrefs.kt` | The dark theme, Silkscreen + Pixelify Sans typefaces (OFL, bundled), and the settings store. |
| Ready-made UI | `HashPlayerActivity.kt`, `EmbeddablePlayerScreen.kt` | A complete player you can launch as an Activity or drop into your Compose tree. |

## Adding it to your app

### Option A: include the module (source)

1. Copy `playerkit/` into your project (or add it as a git submodule).
2. In your `settings.gradle.kts`:
   ```kotlin
   include(":playerkit")
   ```
3. In your app module's `build.gradle.kts`:
   ```kotlin
   dependencies {
       implementation(project(":playerkit"))
   }
   ```

### Option B: the AAR

Build it from this repo:

```
cd android && ./gradlew :playerkit:assembleRelease
# → playerkit/build/outputs/aar/playerkit-release.aar
```

…then drop the AAR into your app's `libs/` with
`implementation(files("libs/playerkit-release.aar"))` plus the dependencies
listed in `playerkit/build.gradle.kts` (Compose BOM, media3 1.3.1,
lifecycle-runtime-ktx, kotlinx-coroutines-android).

### What the manifest merger does for you

The kit's manifest declares `PlaybackService` (with
`android:foregroundServiceType="mediaPlayback"`), `HashPlayerActivity`, and
the permissions the engine needs (`FOREGROUND_SERVICE`,
`FOREGROUND_SERVICE_MEDIA_PLAYBACK`, `POST_NOTIFICATIONS`, `READ_MEDIA_AUDIO`,
`READ_EXTERNAL_STORAGE` capped at SDK 32). Depending on the module is enough;
you do not re-declare any of it.

## Using it

### Zero-effort: launch the activity

```kotlin
startActivity(Intent(context, HashPlayerActivity::class.java))
```

You get the full player UI (library, NCS sphere, transport, seek, gain) as a
screen in your app. It is `exported="false"`: only your app can launch it.

### Composable: embed the screen

```kotlin
HashPlayTheme {
    EmbeddablePlayerScreen()
}
```

`EmbeddablePlayerScreen` is self-contained: it scans the library, binds the
player, and renders. Put it in a nav destination, a bottom sheet, a pane —
anywhere a composable goes.

### Headless: your UI, the kit's engine

Skip the provided UI entirely and talk to `PlayerController` yourself:

```kotlin
val controller = remember { PlayerController(context) }
val now by controller.state.collectAsState()
// drive it once per frame:
controller.tick(seconds)
// then: controller.play(track) / .togglePause() / .skipNext() / .seekTo(frac)
```

Declare `PlaybackService` usage implicitly by depending on the kit; the
service starts when the first `MediaController` binds.

## Runtime permission

The kit declares permissions but an embedded UI must still REQUEST them (the
standalone app's `SetupScreen` does this; `EmbeddablePlayerScreen` currently
shows an empty-library hint if they are missing). Call
`Permissions.needed()` / `Permissions.granted(context, it)` and launch a
`RequestMultiplePermissions` launcher — same pattern as `SetupScreen.kt`.

## What background playback means here

- Audio continues when the app is backgrounded or the screen is off — the
  service owns the player, not the UI.
- Swiping the app from Recents stops playback intentionally (`onTaskRemoved`),
  matching the desktop's semantics: leaving the app means leaving the music.
- The media notification is how the user controls background playback; on
  Android 13+ `POST_NOTIFICATIONS` must be granted for the notification to
  appear (playback is unaffected either way).

## Deliberately NOT in the kit

Torrenting (libtorrent4j — a 12 MB native library and a legal surface you may
not want), YouTube/video backgrounds, the settings overlay, and the
`full`/`lite`/`ncs` flavor split. If you want all of that, use the standalone
HashPlay app.
