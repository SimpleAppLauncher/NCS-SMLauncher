package com.giathinh.hashplay

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * HashPlay's player as one composable, for embedding in another app's tree.
 *
 * What it carries: the MediaStore library, the NCS sphere, transport
 * (prev/play-pause/next), a seek bar, the in-app gain slider, and -- because
 * the player lives in PlaybackService rather than here -- playback that keeps
 * running when this composable leaves composition or the app goes to the
 * background, with the system media notification on the lock screen and shade.
 *
 * What it deliberately does NOT carry: torrenting, video backgrounds, the
 * settings overlay, and flavor routing. Those are app-layer concerns; an
 * embedder adding this kit should not inherit HashPlay's feature surface, only
 * its player. Embedders who need that surface should use the standalone app.
 *
 * Everything below is built from the same pieces the standalone screens use
 * (PlayerController, LibraryScanner, NcsSphereView, PixelType, HashSettings),
 * so behavior cannot drift between the kit and the app: same engine, same
 * rendering, same defaults.
 *
 * No autoplay anywhere: a track plays only because something called
 * [PlayerController.play], and nothing here does that on composition.
 */
@Composable
fun EmbeddablePlayerScreen() {
    val context = androidx.compose.ui.platform.LocalContext.current
    val scope = rememberCoroutineScope()

    val controller = remember { PlayerController(context) }
    var tracks by remember { mutableStateOf<List<Track>>(emptyList()) }
    var selected by remember { mutableIntStateOf(-1) }
    var gain by remember { mutableFloatStateOf(1.0f) }
    val listState = rememberLazyListState()

    // The stored gain is only the starting level; the service owns it after.
    LaunchedEffect(Unit) {
        val g = HashSettings.gain(
            HashSettings.open(context.applicationContext))
        gain = g
        controller.setVolume(g)
        controller.setPlaylist(tracks)
    }

    // One scan, off the main thread; a failure is shown, never thrown.
    LaunchedEffect(Unit) {
        val found = withContext(Dispatchers.IO) {
            try { LibraryScanner.scan(context) } catch (_: Exception) { emptyList() }
        }
        tracks = found
        controller.setPlaylist(found)
    }

    // Frame driver: refreshes position + spectrum while the composable lives.
    // Playback itself is service-owned and unaffected by this loop's disposal.
    val now by controller.state.collectAsState()
    val spectrum by controller.spectrum.collectAsState()
    LaunchedEffect(controller) {
        while (true) {
            controller.tick((System.nanoTime() / 1_000_000_000.0).toFloat())
            kotlinx.coroutines.delay(33) // ~30 Hz, matching the standalone UI
        }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(Color(0xFF0A0C12))
            .padding(12.dp)
    ) {
        // --- NCS sphere: full-bleed above the transport, no box. ------------
        Box(Modifier.fillMaxWidth().weight(1f)) {
            NcsSphereView(
                mags = spectrum,
                bass = controller.bass(),
                level = controller.level(),
                tier = NcsSphere.Tier.FULL,
                modifier = Modifier.fillMaxSize()
            )
            if (now.title.isNotEmpty()) {
                Column(
                    Modifier.align(Alignment.TopStart),
                    verticalArrangement = Arrangement.spacedBy(2.dp)
                ) {
                    Text(
                        now.title, color = Color(0xFFD8DEE9),
                        fontFamily = PixelType.Body,
                        fontSize = 14.sp, maxLines = 1, overflow = TextOverflow.Ellipsis
                    )
                    if (now.artist.isNotEmpty()) Text(
                        now.artist, color = Color(0xFF6E768C),
                        fontFamily = PixelType.Body,
                        fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis
                    )
                }
            }
        }

        // --- seek bar --------------------------------------------------------
        if (now.durationMs > 0) {
            Slider(
                value = (now.positionMs.toFloat() / now.durationMs).coerceIn(0f, 1f),
                onValueChange = { frac -> controller.seekTo(frac) },
                modifier = Modifier.fillMaxWidth()
            )
        }

        // --- transport -------------------------------------------------------
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("PREV", fontFamily = PixelType.Display,
                color = Color(0xFFD8DEE9), fontSize = 15.sp,
                modifier = Modifier.clickable { controller.skipPrevious() }.padding(14.dp))
            Text(if (now.isPlaying) "PAUSE" else "PLAY", fontFamily = PixelType.Display,
                color = Color(0xFFE3B341), fontSize = 19.sp,
                modifier = Modifier.clickable { controller.togglePause() }.padding(18.dp))
            Text("NEXT", fontFamily = PixelType.Display,
                color = Color(0xFFD8DEE9), fontSize = 15.sp,
                modifier = Modifier.clickable { controller.skipNext() }.padding(14.dp))
        }

        // --- gain: the same in-app gain the settings overlay writes ----------
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("GAIN", color = Color(0xFF6E768C),
                fontFamily = PixelType.Display, fontSize = 10.sp)
            Slider(
                value = gain, onValueChange = {
                    gain = it
                    controller.setVolume(it)
                    val prefs = HashSettings.open(context.applicationContext)
                    HashSettings.setGain(prefs, it)
                },
                valueRange = 0f..1f,
                modifier = Modifier.weight(1f).padding(horizontal = 8.dp)
            )
        }

        // --- library ----------------------------------------------------------
        if (tracks.isEmpty()) {
            Text(
                "no music found -- grant the media permission and rescan",
                color = Color(0xFF6E768C), fontFamily = PixelType.Body,
                fontSize = 11.sp, modifier = Modifier.padding(top = 8.dp)
            )
        } else {
            LazyColumn(Modifier.fillMaxWidth().height(160.dp), state = listState) {
                items(tracks) { t ->
                    val idx = tracks.indexOf(t)
                    val isSel = idx == selected
                    Text(
                        t.title,
                        color = if (isSel) Color(0xFFE3B341) else Color(0xFF9AA4B8),
                        fontFamily = PixelType.Body,
                        fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                selected = idx
                                controller.setPlaylist(tracks)
                                controller.play(t)   // never automatic; only a tap
                            }
                            .padding(vertical = 6.dp, horizontal = 4.dp)
                    )
                }
            }
        }
    }
}
