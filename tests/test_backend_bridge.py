"""Contract tests for the EF Launcher LAN bridge (real HTTP + SSE, no audio)."""
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import control_api as capi  # noqa: E402

TOKEN = "test-bridge-token-0123456789abcdef"


def request(base, path, body=None, token=TOKEN, timeout=3):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data,
                                 method="GET" if data is None else "POST")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()


def test_start_does_not_do_reverse_dns():
    api = capi.ControlAPI(host="127.0.0.1", port=0, token=TOKEN, timeout=2)
    with mock.patch("socket.getfqdn",
                    side_effect=AssertionError("bind attempted reverse DNS")):
        try:
            assert api.start(), api.last_error
        finally:
            api.stop()


def main():
    print("0) API startup does not reverse-resolve the bind address")
    test_start_does_not_do_reverse_dns()
    print("   ok  bind is local and non-blocking")
    with tempfile.TemporaryDirectory(prefix="ncs-bridge-") as temp:
        art = os.path.join(temp, "cover.jpg")
        art_bytes = b"\xff\xd8\xfftest-jpeg-bytes\xff\xd9"
        with open(art, "wb") as f:
            f.write(art_bytes)
        state = {
            "title": "Test track", "artist": "Test artist", "album": "Test album",
            "position": 1.25, "duration": 10.0, "volume": 0.4,
            "playing": True, "queue": [{"id": 0, "title": "Test track"}],
            "artwork": "/art/cover-id.jpg", "_artwork_id": "cover-id",
            "_artwork_path": art,
        }
        api = capi.ControlAPI(host="127.0.0.1", port=0, token=TOKEN, timeout=2)
        assert api.start(), api.last_error
        port = api._server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        calls = []
        handlers = {
            name: (lambda args, n=name: calls.append((n, args)) or {"action": n})
            for name in ("play", "pause", "next", "prev", "seek", "volume")
        }
        stop = threading.Event()

        def pump():
            while not stop.is_set():
                api.publish(dict(state))
                api.drain(handlers)
                time.sleep(0.005)

        thread = threading.Thread(target=pump, daemon=True)
        thread.start()
        try:
            time.sleep(0.05)
            code, _, payload = request(base, "/state")
            assert code == 200, (code, payload)
            snapshot = json.loads(payload)
            assert snapshot == {
                "title": "Test track", "artist": "Test artist", "album": "Test album",
                "positionMs": 1250, "durationMs": 10000, "volume": 0.4,
                "playing": True, "artwork": "/art/cover-id.jpg",
                "queue": [{"id": 0, "title": "Test track"}],
            }, snapshot

            code, _, payload = request(base, "/control", {
                "action": "seek", "positionMs": 7250,
            })
            assert code == 200, (code, payload)
            assert calls[-1] == ("seek", {"seconds": 7.25}), calls[-1]
            for action, expected in (("play", "play"), ("pause", "pause"),
                                     ("next", "next"), ("prev", "prev")):
                code, _, payload = request(base, "/control", {"action": action})
                assert code == 200, (action, code, payload)
                assert calls[-1] == (expected, {}), calls[-1]
            code, _, payload = request(base, "/control", {
                "action": "volume", "value": 0.7,
            })
            assert code == 200, (code, payload)
            assert calls[-1] == ("volume", {"value": 0.7}), calls[-1]

            code, headers, payload = request(base, "/art/cover-id.jpg")
            assert code == 200 and headers.get_content_type() == "image/jpeg"
            assert payload == art_bytes
            code, _, payload = request(base, "/art/not-current.jpg")
            assert code == 404, (code, payload)

            # Events are an actual streaming response. Read the initial state
            # event, then close; the server must release its connection slot.
            req = urllib.request.Request(base + "/events")
            req.add_header("Authorization", f"Bearer {TOKEN}")
            with urllib.request.urlopen(req, timeout=3) as response:
                assert response.headers.get_content_type() == "text/event-stream"
                first = response.readline().decode().strip()
                second = response.readline().decode().strip()
                assert first.startswith("event: state"), first
                assert second.startswith("data: {"), second
                event_state = json.loads(second[6:])
                assert event_state["title"] == "Test track"

            code, _, _ = request(base, "/state", token=None)
            assert code == 401, code
            code, _, payload = request(base, "/control", {"action": "unknown"})
            assert code == 400, (code, payload)
        finally:
            stop.set()
            api.stop()
            thread.join(timeout=1)
    print("EF LAUNCHER BRIDGE TESTS PASSED")


if __name__ == "__main__":
    main()
