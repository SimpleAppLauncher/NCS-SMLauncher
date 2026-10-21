package com.giathinh.hashplay

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge

/**
 * The whole player, as an Activity another app can launch.
 *
 * This is the zero-Compose-knowledge embedding path: start this activity and
 * you have HashPlay's browser, NCS sphere and transport inside your app, with
 * background playback and the system media notification included. It is
 * declared non-exported in the kit's manifest, so only the embedding app (or
 * the system, on its behalf) can start it:
 *
 *     context.startActivity(Intent(context, HashPlayerActivity::class.java))
 *
 * Apps that want the player INSIDE their own UI should compose
 * [EmbeddablePlayerScreen] instead -- this activity is just
 * `setContent { EmbeddablePlayerScreen() }` with edge-to-edge handled.
 */
class HashPlayerActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            HashPlayTheme {
                EmbeddablePlayerScreen()
            }
        }
    }
}
