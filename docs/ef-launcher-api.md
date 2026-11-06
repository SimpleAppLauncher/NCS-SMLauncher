# EF Launcher bridge (desktop NCS-SMLauncher)

The full desktop launcher exposes an authenticated HTTP + SSE API for a client
on the same trusted LAN (for example, the wall-mounted tablet). The lite and
micro desktop profiles do not start the API. Android playback remains owned by
the existing Kotlin/Media3 service; this bridge controls the desktop player's
current library and transport.

## Connect

- Default bind: `0.0.0.0:8765` (all host interfaces; API token required).
- Base URL from the tablet: `http://<desktop-LAN-IP>:8765`.
- Authentication: `Authorization: Bearer <token>` on every request, including
  the SSE stream and artwork. The random token is stored at
  `~/.ncs-smlauncher/api_token` with file mode `0600`; the desktop API panel
  (press `C`) displays it. Do not put it in URLs or logs.
- Set `api_host` to `127.0.0.1` in `~/.ncs-smlauncher/settings.json` to restrict
  access to the desktop itself; set `api_enabled` false to turn the listener
  off. `HASHPLAY_API_PORT` overrides the default port. The legacy `/webhook`
  accepts `?token=` only for loopback callers; LAN callers still need the header.
- This is plain HTTP, not TLS. Use only on a trusted private LAN; a hostile
  network observer could capture a bearer token. The token is constant-time
  checked, required on all bridge routes, and not printed to request logs.

The currently shipped player library is the desktop's scanned local audio
folder plus files that have been downloaded into it; there is no remote NCS
catalogue. Full desktop builds can use libtorrent. `/state.queue` contains the
current scanned library in index order, with paths omitted; the legacy
`GET /tracks` endpoint retains its authenticated full library response.

## `GET /state`

Returns a JSON snapshot (not the legacy `{ok,result}` envelope):

```json
{
  "title": "Track title",
  "artist": "Artist",
  "album": "Album",
  "positionMs": 12500,
  "durationMs": 183000,
  "volume": 0.8,
  "playing": true,
  "artwork": "/art/7c7d9a21b3f4c5d6e7f809ab.jpg",
  "queue": [
    {"id": 0, "title": "Track title", "artist": "Artist",
     "album": "Album", "artwork": "/art/7c7d9a21b3f4c5d6e7f809ab.jpg"}
  ]
}
```

Empty metadata is JSON `null` (or an empty queue); position/duration are
non-negative integer milliseconds, volume is 0..1. Artwork IDs are opaque,
per-library identifiers; absolute disk paths are never returned.

## `GET /events`

Authenticated `text/event-stream`. It immediately sends the same full snapshot
as `event: state`, then sends updated snapshots at most once per second; idle
streams receive SSE comment heartbeats. The server caps concurrent streams at
8. Close the response to disconnect.

```text
event: state
data: {"title":"Track title", ...}

```

## `POST /control`

JSON body with `action` set to `play`, `pause`, `next`, `prev`, `seek`, or
`volume`. Success and errors use the existing JSON control envelope.

```json
{"action":"play"}
{"action":"play","query":"title or artist"}
{"action":"pause"}
{"action":"next"}
{"action":"prev"}
{"action":"seek","positionMs":42000}
{"action":"seek","deltaMs":-5000}
{"action":"volume","value":0.5}
```

`seek` supports absolute `positionMs` or relative `deltaMs`; legacy `seconds`
and `delta` are also accepted. Volume accepts `value` (0..1) or `delta`.
`play` resumes the loaded track when no `query` or `index` is given.

## `GET /art/{id}.jpg`

Returns the cached JPEG bytes for a track in the scanned library. The `id` is
the one in that track's `artwork` field. A missing, stale, or oversized cover
returns 404. The endpoint is authenticated and caps images at 12 MiB.

## Errors and compatibility

- `400`: invalid control action/arguments.
- `401`: missing or invalid bearer token.
- `404`: unknown endpoint or artwork ID.
- `429`: command queue is full.
- `503`: eight SSE streams are already open.
- `504`: the desktop main loop did not service a command in time.

Existing `/status`, `/tracks`, `/tracks/search`, `/play`, `/pause`, `/resume`,
`/next`, `/prev`, `/seek`, `/volume`, `/muted`, `/visualizer`, `/video`, and
`/webhook` routes remain for backwards compatibility. The API schema version
is `2` in `GET /` discovery.
