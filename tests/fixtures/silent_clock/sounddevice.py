"""Virtual sounddevice stream: drives callbacks in memory and discards output.

This module intentionally does not import or open PortAudio, CoreAudio, ALSA,
or any other device. It lets timing/state tests exercise the playback callback
while guaranteeing that generated samples are never sent to speakers.
"""
import threading
import time

import numpy as np


class OutputStream:
    def __init__(self, *, samplerate, channels, dtype, blocksize, callback):
        self.samplerate = int(samplerate)
        self.channels = int(channels)
        self.dtype = np.dtype(dtype)
        self.blocksize = int(blocksize)
        self.callback = callback
        self.active = False
        self.error = None
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self.active:
            return self
        self._stop.clear()
        self.active = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def _run(self):
        frames = self.blocksize or 1024
        interval = frames / max(1, self.samplerate)
        next_tick = time.monotonic()
        while not self._stop.is_set():
            outdata = np.zeros((frames, self.channels), dtype=self.dtype)
            try:
                self.callback(outdata, frames, None, None)
            except Exception as exc:
                self.error = exc
                self.active = False
                return
            finally:
                # Never preserve or route generated samples outside this
                # scratch buffer. The callback's clock/state advances, but the
                # virtual stream has no physical output device.
                outdata.fill(0)
            next_tick += interval
            self._stop.wait(max(0.0, next_tick - time.monotonic()))
        self.active = False

    def stop(self):
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        self.active = False
        return self

    def close(self):
        return self.stop()

    def is_active(self):
        return self.active
