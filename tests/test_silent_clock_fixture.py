"""The virtual sounddevice clock advances playback without emitting audio."""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "silent_clock")
sys.path.insert(0, FIXTURE)
import sounddevice as virtual_sd  # noqa: E402


calls = []

def callback(outdata, frames, time_info, status):
    outdata[:] = 0.7
    calls.append((outdata, float(outdata[0, 0]), frames))


stream = virtual_sd.OutputStream(samplerate=44100, channels=1, dtype="float32",
                                 blocksize=441, callback=callback)
stream.start()
time.sleep(0.08)
stream.stop()
assert calls, "virtual stream never advanced the callback"
assert abs(calls[0][1] - 0.7) < 1e-6, calls[0][1]
assert not calls[0][0].any(), "sample buffer was not discarded after callback"
assert not stream.active
print("SILENT AUDIO CLOCK TEST PASSED (callback simulated; output discarded)")
