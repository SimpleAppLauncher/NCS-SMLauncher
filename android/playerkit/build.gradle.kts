plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.0"
}

// ---------------------------------------------------------------------------
// HashPlay PlayerKit -- the player as a component.
//
// This module holds everything another app needs to play music the HashPlay
// way: the MediaSessionService that owns playback in the background, the
// MediaController wrapper, the library scanner, the NCS sphere, the pixel
// typefaces and the settings store. It deliberately holds NO torrent code and
// NO flavor routing: those are app-layer concerns, and an embedder should not
// inherit them.
//
// The Kotlin package is `com.giathinh.hashplay`, unchanged from when these
// files lived in :app -- moving them across modules without rewriting a single
// import is the point. The namespace matches the package, so the kit's R class
// (fonts) and manifest class references resolve where the sources already are.
//
// Embedding: see playerkit/README.md. Short version -- add the module (or the
// AAR), and either launch HashPlayerActivity or drop EmbeddablePlayerScreen
// into your own Compose tree. The manifest merger carries the service and
// permissions into the embedding app automatically.
// ---------------------------------------------------------------------------
android {
    namespace = "com.giathinh.hashplay"
    compileSdk = 34

    defaultConfig {
        minSdk = 26
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.06.00")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.2")
    // Playback + the media session that makes background playback and the
    // system notification work. Same versions :app pins, so a shared classpath
    // can never desynchronize the two modules.
    implementation("androidx.media3:media3-exoplayer:1.3.1")
    implementation("androidx.media3:media3-session:1.3.1")
    // PlayerView for the video path in VideoBackground.kt. Same reasoning as
    // :app: declared explicitly because exoplayer does not pull it in.
    implementation("androidx.media3:media3-ui:1.3.1")
    // The kit reads prefs and scans MediaStore; coroutines ride in with
    // lifecycle-runtime-ktx transitively, StateFlow needs kotlinx-coroutines.
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
}
