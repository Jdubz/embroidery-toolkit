"""Prepare source artwork for a machine with a minimum feature size.

Flat line art drawn for screen routinely has strokes far below what an
embroidery machine can render. On the SE700 at a 91 mm design width, 39% of the
LemonCat outline's ink area measures under the 1.0 mm minimum linework width,
with a median of 1.20 mm. Digitizing that faithfully is the mistake: a single
running stitch is one 40 wt thread, about 0.4 mm, and it reads as a scratch
rather than a line.

(An earlier version of this docstring put the median at 0.67 mm and "roughly
half the drawing" below the minimum. Both came from a broken width function —
see `embroidery_tools.measure` — and both overstated the problem. The corrected
figures reproduce the independently recorded "44% of its ink area is >= 1.5 mm
across" for this same artwork exactly.)

This fixes the artwork rather than fighting it downstream:

  --min-line-mm   grow every stroke to at least the machine's minimum, WITHOUT
                  thickening areas that are already wide enough. Also makes
                  strokes uniform, which matters for things like whiskers where
                  inconsistent weight reads as a mistake.
  --erase         delete a rectangular region, for accents that muddy the design
                  at this size.
  --drop-mm2      delete specks below an area.

Deterministic and repeatable — the same input always gives the same output,
which is what you want for a step that sits in front of a digitizer.

Usage:
  artwork_prep.py <in.png> <out.png> --width-mm 91 [--min-line-mm 1.2]
                  [--erase X,Y,W,H]... [--drop-mm2 1.0] [--report]
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

from embroidery_tools.measure import widths_mm


def disk(r: int) -> np.ndarray:
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    return (yy * yy + xx * xx) <= r * r


# Width measurement lives in embroidery_tools.measure. It used to be a local
# ridge-of-the-distance-transform function here, and it was wrong on anything
# that tapers: it reported 0.10 mm for a shape 3.3 mm across. See that module
# for what replaced it and why. Same 2*edt convention, so recorded figures for
# uniform line art are unchanged; compact shapes now read correctly instead of
# far too thin.


def grow_to_min_width(mask: np.ndarray, min_mm: float, ppm: float
                      ) -> tuple[np.ndarray, dict]:
    """Bring thin strokes up to a minimum width, leaving wide areas alone.

    Method: find the medial axis (ridge of the distance transform), keep only
    the part of it running through strokes narrower than the target, and stamp
    a disk of the target radius along it. A stroke's centreline with a disk of
    radius w/2 swept along it is exactly a stroke of width w, so thin lines come
    out at the target and uniform — which is what makes whiskers match each
    other instead of varying with however the artwork was drawn.

    Two wrong approaches, both tried:

    * Dilating the whole mask inflates the solid masses as well, closes the gap
      between eyebrow and eye, and turns the face into a blob.
    * Iteratively dilating "pixels whose distance transform is below target"
      does the same thing for a subtler reason: the distance transform is small
      near the edge of *every* shape, thick ones included, so the test selects a
      band around all boundaries. Measured on the LemonCat: 727 mm² became
      2,798 mm² and 10 separate regions merged into 1.
    """
    R = max(1, int(round(min_mm / 2.0 * ppm)))
    half = ndimage.distance_transform_edt(mask)

    # Ridge of the distance transform ~ the medial axis. A pixel on the ridge is
    # no closer to the edge than any of its neighbours.
    #
    # This deliberately keeps the 8-neighbour test that `widths_mm` had to
    # abandon. The two jobs are different: measuring needs a width for every
    # part of the shape, whereas growing needs a centreline to stamp discs
    # along, and only in the *thin* parts. On a uniform thin stroke the distance
    # transform is flat along the axis, so the plateau passes the test and the
    # ridge comes out dense and connected — which is exactly the case this
    # function is for. Its blind spot is tapering and compact shapes, and those
    # are the ones it is supposed to leave alone anyway.
    ridge = mask & (half >= ndimage.maximum_filter(half, size=3) - 1e-6) & (half > 0)
    thin_ridge = ridge & (half < R)
    if not thin_ridge.any():
        return mask, {"grown_mm2": 0.0, "regions_before": ndimage.label(mask)[1],
                      "regions_after": ndimage.label(mask)[1]}

    out = mask | ndimage.binary_dilation(thin_ridge, structure=disk(R))
    return out, {
        "grown_mm2": (out.sum() - mask.sum()) / ppm ** 2,
        "regions_before": ndimage.label(mask)[1],
        "regions_after": ndimage.label(out)[1],
    }


ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--width-mm", type=float, required=True,
                help="the design width this artwork will be stitched at")
ap.add_argument("--min-line-mm", type=float, default=0.0,
                help="grow strokes thinner than this up to it (0 = off)")
ap.add_argument("--erase", action="append", default=[], metavar="X,Y,W,H",
                help="erase a box, in %% of image size; repeatable")
ap.add_argument("--drop-mm2", type=float, default=0.0,
                help="delete disconnected specks smaller than this")
ap.add_argument("--report", action="store_true",
                help="print the stroke-width distribution and stop")
a = ap.parse_args()

img = Image.open(a.src).convert("RGBA")
arr = np.array(img)
H, W = arr.shape[:2]
ppm = W / a.width_mm

opaque = arr[:, :, 3] > 128
ink = opaque & (arr[:, :, :3].astype(int).sum(axis=2) < 200)
if not ink.any():
    raise SystemExit(f"{a.src}: no dark ink found")


def describe(mask: np.ndarray, label: str) -> None:
    w = widths_mm(mask, ppm)
    n = ndimage.label(mask)[1]
    print(f"  {label:<10} area {mask.sum() / ppm ** 2:6.0f} mm²  {n:3d} region(s)  "
          f"width p25 {np.percentile(w, 25):.2f}  p50 {np.percentile(w, 50):.2f}  "
          f"p90 {np.percentile(w, 90):.2f} mm")


describe(ink, "before")
if a.report:
    # Area-weighted: widths_mm returns one sample per ink pixel, so this is the
    # share of the actual ink area that is too thin, not the share of samples
    # along some skeleton.
    below = (widths_mm(ink, ppm) < 1.0).mean() * 100
    print(f"  {below:.0f}% of the ink AREA is under 1.0 mm — the machine's minimum linework width")
    sys.exit(0)

out = ink.copy()

# Erase first: no point thickening something that is about to be deleted.
for spec in a.erase:
    try:
        x, y, w, h = (float(v) for v in spec.split(","))
    except ValueError:
        raise SystemExit(f"bad --erase {spec!r}: expected X,Y,W,H in percent")
    x0, x1 = int(x / 100 * W), int((x + w) / 100 * W)
    y0, y1 = int(y / 100 * H), int((y + h) / 100 * H)
    removed = out[y0:y1, x0:x1].sum() / ppm ** 2
    out[y0:y1, x0:x1] = False
    print(f"  erased     {removed:6.1f} mm² at ({x:.0f},{y:.0f}) {w:.0f}x{h:.0f}%")

if a.min_line_mm:
    out, st = grow_to_min_width(out, a.min_line_mm, ppm)
    print(f"  thickened  +{st['grown_mm2']:.0f} mm² to reach a {a.min_line_mm} mm floor")
    # Topology guard, the same rule used elsewhere in this repo: growing strokes
    # must not weld separate elements together. Area alone would not catch it —
    # bridging two whiskers costs almost no pixels.
    if st["regions_after"] < st["regions_before"]:
        print(f"  WARNING    regions {st['regions_before']} -> {st['regions_after']}: "
              f"thickening has merged separate elements. Lower --min-line-mm, or "
              f"the artwork's gaps are too tight for this design size.",
              file=sys.stderr)

if a.drop_mm2:
    lab, n = ndimage.label(out)
    if n:
        sizes = ndimage.sum(out, lab, range(1, n + 1)) / ppm ** 2
        keep = np.nonzero(sizes >= a.drop_mm2)[0] + 1
        dropped = n - len(keep)
        if dropped:
            out = np.isin(lab, keep)
            print(f"  dropped    {dropped} speck(s) under {a.drop_mm2} mm²")

describe(out, "after")

# Write RGBA, preserving the transparent background so the separator's
# opaque-pixel logic still works.
res = np.zeros((H, W, 4), np.uint8)
res[out] = (0, 0, 0, 255)
Image.fromarray(res).save(a.dst)
print(f"  wrote      {a.dst}")
