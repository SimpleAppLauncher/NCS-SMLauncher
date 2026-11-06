"""Hard mute for integration tests: never opens PortAudio or an output device."""

class OutputStream:
    def __init__(self, *, samplerate, channels, dtype, blocksize, callback):
        self.samplerate = samplerate
        self.channels = channels
        self.dtype = dtype
        self.blocksize = blocksize
        self.callback = callback
        self.active = False

    def start(self):
        # This is intentionally inert. The test exercises player controls and
        # API state, not audio output; the callback is never scheduled.
        self.active = True

    def stop(self):
        self.active = False

    def close(self):
        self.active = False

    def is_active(self):
        return self.active
