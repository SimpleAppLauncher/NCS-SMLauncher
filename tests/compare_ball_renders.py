#!/usr/bin/env python3
"""Compare the desktop and Android NCS balls numerically, not by eye.

Both renders are measured the same way: fraction of pixels actually lit,
luminance distribution, and how much of the frame is warm gold. Eyeballing a
screenshot is how "the ball looks fine" gets said about a ball that is 99%
black.

    python3 tests/compare_ball_renders.py <desktop.png> <android.png> <x0,y0,x1,y1>
"""
import sys

import numpy as np
from PIL import Image


def stats(label, path, box):
    with Image.open(path) as source:
        im = source.convert("RGB")
        if box:
            im = im.crop(box)
        pixels = np.asarray(im, dtype=np.uint8)

    height, width = pixels.shape[:2]
    n = height * width
    sums = pixels.sum(axis=2, dtype=np.uint16)
    lit_mask = sums > 90
    lit_count = int(np.count_nonzero(lit_mask))
    red = pixels[..., 0].astype(np.int16)
    blue = pixels[..., 2].astype(np.int16)
    warm_count = int(np.count_nonzero(red > blue + 25))

    weights = np.array((0.299, 0.587, 0.114), dtype=np.float64)
    lum = np.einsum("...c,c->...", pixels, weights).reshape(-1)
    p95_index = int(0.95 * n)
    lum.partition(p95_index)

    brightest = None
    if lit_count:
        lit_sums = np.where(lit_mask, sums, 0).reshape(-1)
        brightest_index = int(np.argmax(lit_sums))
        brightest = tuple(
            int(channel) for channel in pixels.reshape(-1, 3)[brightest_index]
        )

    out = {
        "label": label,
        "size": im.size,
        "lit": 100 * lit_count / n,
        "mean": float(lum.mean(dtype=np.float64)),
        "p95": float(lum[p95_index]),
        "warm": 100 * warm_count / n,
        "brightest": brightest,
    }
    print(f"  {label}")
    print(f"    size         : {im.size[0]}x{im.size[1]}")
    print(f"    lit fraction : {out['lit']:5.2f}%")
    print(f"    mean lum     : {out['mean']:6.1f}")
    print(f"    p95 lum      : {out['p95']:6.1f}")
    print(f"    warm(gold)   : {out['warm']:5.2f}%")
    if out["brightest"]:
        print(f"    brightest    : rgb{out['brightest']}")
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    desk = sys.argv[1]
    andr = sys.argv[2]
    box = None
    if len(sys.argv) > 3:
        box = tuple(int(v) for v in sys.argv[3].split(","))

    print("  NCS ball: desktop vs android")
    a = stats("DESKTOP python", desk, None)
    b = stats("ANDROID kotlin", andr, box)
    print()
    print(f"  android is {b['lit'] / max(a['lit'], 0.01):.1f}x as lit "
          f"and {b['mean'] / max(a['mean'], 0.01):.1f}x as bright")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
