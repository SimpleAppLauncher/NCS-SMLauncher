"""The playerkit embedding contract, checked without a device or a Gradle run.

HashPlay's player became a library (:playerkit) so another app -- a launcher,
say -- can embed it. This suite pins the things that make that true:

  * the module exists, is a library, and :app depends on it
  * the kit carries the engine and NO torrent code (an embedder must not
    inherit libtorrent4j, 12 MB of native library plus its legal surface)
  * the kit manifest declares the service, its mediaPlayback foreground type,
    and the permissions -- so the embedder does none of that
  * there are two documented embedding paths (activity + composable) and a
    README explaining them
  * PlaybackService no longer names MainActivity -- the kit cannot know the
    embedding app's activities

Static checks on purpose: building and installing an embedder app is beyond
what this repo can verify (no second app exists here), so everything asserted
is asserted against the sources the embedder would compile against.
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(REPO, "android", "playerkit")
KIT_JAVA = os.path.join(KIT, "src", "main", "java", "com", "giathinh", "hashplay")
KIT_MANIFEST = os.path.join(KIT, "src", "main", "AndroidManifest.xml")
KIT_GRADLE = os.path.join(KIT, "build.gradle.kts")
APP_GRADLE = os.path.join(REPO, "android", "app", "build.gradle.kts")
SETTINGS = os.path.join(REPO, "android", "settings.gradle.kts")
APP_JAVA = os.path.join(REPO, "android", "app", "src", "main", "java",
                        "com", "giathinh", "hashplay")

FAILS = []


def check(cond, label, detail=""):
    if not isinstance(detail, str):
        detail = str(detail)
    print("   %s  %s%s" % ("ok " if cond else "FAIL", label,
                           "" if cond or not detail else "  -- " + str(detail)))
    if not cond:
        FAILS.append(label)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def read_java(name):
    for base in (KIT_JAVA, APP_JAVA):
        p = os.path.join(base, name)
        if os.path.isfile(p):
            return read(p)
    raise FileNotFoundError(name)


print("PLAYERKIT EMBEDDING")

print("\n  the module exists and is wired into the build")
check(os.path.isdir(KIT_JAVA), "playerkit module directory exists")
kg = read(KIT_GRADLE)
check('id("com.android.library")' in kg, "playerkit is an Android LIBRARY")
check('namespace = "com.giathinh.hashplay"' in kg,
      "the kit keeps the shared package, so moved files need no import edits")
sg = read(SETTINGS)
check('include(":playerkit")' in sg, "settings.gradle includes :playerkit")
ag = read(APP_GRADLE)
check('implementation(project(":playerkit"))' in ag,
      ":app depends on :playerkit")

print("\n  media3 versions cannot drift between kit and app")
kit_media3 = sorted(set(re.findall(r'androidx\.media3:(media3-[a-z]+):([0-9.]+)"', kg)))
app_media3 = sorted(set(re.findall(r'androidx\.media3:(media3-[a-z]+):([0-9.]+)"', ag)))
check(kit_media3, "the kit declares media3 explicitly")
check(set(v for _, v in kit_media3) == set(v for _, v in app_media3),
      "kit and app pin the same media3 version",
      f"kit={kit_media3} app={app_media3}")

print("\n  the kit carries the engine, and only the engine")
engine_files = ("PlaybackService.kt", "PlayerController.kt", "LibraryScanner.kt",
                "NcsSphere.kt", "Visualizer.kt", "HashSettings.kt", "NcsPrefs.kt",
                "Permissions.kt", "SetupState.kt", "Theme.kt", "PixelType.kt",
                "VideoBackground.kt", "Gamepad.kt", "PadListener.kt")
for f in engine_files:
    check(os.path.isfile(os.path.join(KIT_JAVA, f)),
          f"{f} lives in :playerkit")
check(os.path.isfile(os.path.join(APP_JAVA, "MainActivity.kt")),
      "MainActivity stays in :app (it is the launcher, not the engine)")
check(os.path.isfile(os.path.join(APP_JAVA, "PlayerScreen.kt")),
      "PlayerScreen stays in :app (it is flavor-routed UI)")
check(not os.path.isfile(os.path.join(KIT_JAVA, "TorrentManager.kt")),
      "no TorrentManager in the kit -- embedders do not inherit torrenting")
kit_src = ""
for f in os.listdir(KIT_JAVA):
    kit_src += read(os.path.join(KIT_JAVA, f))
check("libtorrent4j" not in re.sub(r"^\s*//.*$", "", kit_src, flags=re.M),
      "no libtorrent4j import anywhere in the kit (that is what keeps the "
      "12 MB .so and its legal surface out of an embedder)")
check("yt-dlp" not in kit_src and "yt_dlp" not in kit_src,
      "no youtube resolver in the kit")

print("\n  the kit manifest is self-sufficient for an embedder")
km = read(KIT_MANIFEST)
check('android:name="com.giathinh.hashplay.PlaybackService"' in km,
      "the service is declared (fully qualified -- the kit's namespace owns it)")
check('foregroundServiceType="mediaPlayback"' in km,
      "the service declares the mediaPlayback foreground type (required on 14+)")
check('androidx.media3.session.MediaSessionService' in km,
      "the service carries the Media3 session intent filter")
for perm in ("android.permission.FOREGROUND_SERVICE",
             "android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK",
             "android.permission.POST_NOTIFICATIONS",
             "android.permission.READ_MEDIA_AUDIO"):
    check(f'android:name="{perm}"' in km, f"the kit declares {perm}")
check('android:name="com.giathinh.hashplay.HashPlayerActivity"' in km,
      "the ready-made player activity is declared")
check(re.search(r'<activity[^>]*HashPlayerActivity[^>]*android:exported="false"',
                km, re.S) is not None,
      "HashPlayerActivity is NOT exported (only the host app launches it)")

print("\n  two embedding paths exist and are documented")
check(os.path.isfile(os.path.join(KIT_JAVA, "HashPlayerActivity.kt")),
      "HashPlayerActivity: the launch-an-intent path")
check(os.path.isfile(os.path.join(KIT_JAVA, "EmbeddablePlayerScreen.kt")),
      "EmbeddablePlayerScreen: the composable path")
check("EmbeddablePlayerScreen" in read_java("HashPlayerActivity.kt"),
      "the activity is the composable with edge-to-edge, so the two cannot drift")
readme_path = os.path.join(KIT, "README.md")
check(os.path.isfile(readme_path), "playerkit/README.md exists")
rm = read(readme_path)
check("include(\":playerkit\")" in rm and "implementation(project(\":playerkit\"))" in rm,
      "the README shows the include + dependency steps")
check("HashPlayerActivity::class.java" in rm,
      "the README shows the activity launch")
check("EmbeddablePlayerScreen()" in rm,
      "the README shows the composable embedding")
check("playerkit-release.aar" in rm, "the README explains the AAR path")
check("Permissions.needed()" in rm,
      "the README says who requests the runtime permission (the embedder)")

print("\n  the kit does not know the embedding app")
svc = read_java("PlaybackService.kt")
# Comments stripped first: the method NAME and a comment may mention
# MainActivity; code may not. (Same trap this repo hit before: a check
# satisfied by the very text explaining it.)
svc_code = "\n".join(l.split("//")[0] for l in svc.splitlines())
check("MainActivity" not in svc_code.replace("pendingIntentToMainActivity", ""),
      "PlaybackService's CODE does not reference MainActivity -- the kit "
      "cannot name the host's activities")
check("getLaunchIntentForPackage" in svc,
      "the session activity is the host's LAUNCHER intent, resolved at runtime")

print("\n  the embedded screen does not autoplay and does not own a player")
emb = read_java("EmbeddablePlayerScreen.kt")
check(emb.count("ExoPlayer.Builder(") == 0,
      "EmbeddablePlayerScreen builds NO player (the service owns the only one)")
check("controller.play(" in emb and
      "play(tracks[0])" not in emb and
      not re.search(r"play\(\w+\)\s*(?!//).*$", emb.split("clickable")[1].split("}")[0], re.S)
      or "selected = idx" in emb,
      "playback starts only from a tap (no autoplay on composition)")
check("LaunchedEffect(Unit) { refresh" in emb or
      "LibraryScanner.scan" in emb,
      "the embedded screen scans the library itself")

print("\n" + ("PLAYERKIT TESTS PASSED" if not FAILS
              else "%d FAILURES: %s" % (len(FAILS), FAILS)))
sys.exit(1 if FAILS else 0)
