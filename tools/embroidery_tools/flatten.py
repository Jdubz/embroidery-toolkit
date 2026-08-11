"""Flatten artwork back to hard-edged colour regions before digitizing.

Written for a specific and easy-to-miss trap: **an AI image that looks like
embroidery is harder to digitize than one that looks like a sticker.**

Ask a generator for "embroidery patch" and it paints simulated satin texture,
thread sheen and fabric weave into the pixels. To your eye that reads as
"embroidery-ready". To a digitizer it is noise — every fake stitch is a slightly
different shade, so colour clustering fragments and the tracer sees tens of
thousands of sub-millimetre regions that will never stitch.

Measured on one real example (`screaming simple.png`, 1254 px):

    before flattening      after
    109,080 unique colours    5
    115,645 regions <1 mm2    34
    0.77 mm typical stroke    1.23 mm     (crossing the 1.2 mm safe threshold)
    colour fit 21.5           10.5

The fix is not subtle and does not need to be: median-filter the texture away,
posterise to the real colour count, then clean each region morphologically.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
from scipy.cluster.vq import kmeans2


@dataclass
class FlattenReport:
    colors: int = 0
    unique_before: int = 0
    unique_after: int = 0
    tiny_before: int = 0
    tiny_after: int = 0


def _count_tiny(
    rgb: np.ndarray, mm_per_px: float, limit_mm2: float = 1.0, max_bins: int = 24
) -> int:
    """Count connected regions below `limit_mm2`.

    Quantises to at most `max_bins` colours first. That is not a shortcut for
    accuracy, it is the only way this terminates: a textured source can carry
    100k+ unique colours, and labelling once per colour would run for hours.
    Binning also matches what the digitizer will actually see.
    """
    img = Image.fromarray(rgb)
    if len(np.unique(rgb.reshape(-1, 3), axis=0)) > max_bins:
        img = img.quantize(colors=max_bins, method=Image.MEDIANCUT).convert("RGB")
    q = np.array(img)

    tiny = 0
    for c in np.unique(q.reshape(-1, 3), axis=0):
        m = (q == c).all(axis=2)
        lab, n = ndimage.label(m)
        if n:
            sizes = ndimage.sum(m, lab, range(1, n + 1)) * mm_per_px ** 2
            tiny += int((sizes < limit_mm2).sum())
    return tiny


def flatten(
    src: str | Path,
    dst: str | Path,
    *,
    colors: int = 5,
    texture_px: int = 9,
    min_region_px: int = 60,
    working_mm: float = 96.0,
) -> FlattenReport:
    """Remove simulated texture and posterise to `colors` flat regions.

    `colors` counts the background. Ask for one more than the design has, or a
    small element (a red heart against green and black) gets merged away.
    """
    src, dst = Path(src), Path(dst)
    img = Image.open(src).convert("RGB")
    w, h = img.size
    mm_per_px = working_mm / max(w, h)

    before = np.array(img)
    report = FlattenReport(colors=colors)
    report.unique_before = len(np.unique(before.reshape(-1, 3), axis=0))
    report.tiny_before = _count_tiny(before, mm_per_px)

    # 1. Kill the texture. Simulated stitches are a few px across, so a median
    #    filter wider than they are removes them while preserving real edges —
    #    which a blur would not.
    sm = img
    for _ in range(2):
        sm = sm.filter(ImageFilter.MedianFilter(texture_px))

    # 2. Posterise to the real colour count. Clamp to the number of distinct
    #    colours actually present — asking k-means for more clusters than there
    #    are unique values yields empty clusters and NaN centroids.
    arr = np.array(sm).astype(np.float64)
    flat = arr.reshape(-1, 3)
    sample = flat[:: max(1, len(flat) // 50000)]
    colors = max(1, min(colors, len(np.unique(sample, axis=0))))
    cent, _ = kmeans2(sample, colors, minit="++", seed=0, iter=30)
    idx = ((flat[:, None, :] - cent[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
    idx = idx.reshape(h, w)

    # 3. Clean each region: close pinholes, remove speckle.
    out = np.zeros((h, w, 3), dtype=np.uint8)
    filled = np.zeros((h, w), dtype=bool)
    for i in range(colors):
        m = idx == i
        m = ndimage.binary_closing(m, np.ones((5, 5)))
        m = ndimage.binary_opening(m, np.ones((5, 5)))
        lab, n = ndimage.label(m)
        if n:
            sizes = ndimage.sum(m, lab, range(1, n + 1))
            keep = np.zeros(n + 1, bool)
            keep[1:] = sizes >= min_region_px
            m = keep[lab]
        out[m] = cent[i].astype(np.uint8)
        filled |= m

    # Anything the cleanup orphaned takes its nearest surviving neighbour,
    # so no holes are left behind.
    if (~filled).any() and filled.any():
        ind = ndimage.distance_transform_edt(
            ~filled, return_distances=False, return_indices=True
        )
        out = out[tuple(ind)]

    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out).save(dst)

    report.unique_after = len(np.unique(out.reshape(-1, 3), axis=0))
    report.tiny_after = _count_tiny(out, mm_per_px)
    return report


def stroke_stats(path: str | Path, working_mm: float = 96.0) -> dict:
    """Typical and thin-tail dark-linework width, in mm at machine scale."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    mm_per_px = working_mm / max(w, h)
    arr = np.array(img).astype(int)
    dark = arr.sum(axis=2) < 200
    if not dark.any():
        return {}
    dt = ndimage.distance_transform_edt(dark) * 2.0 * mm_per_px
    vals = dt[dark]
    return {
        "median_mm": round(float(np.median(vals)), 2),
        "p10_mm": round(float(np.percentile(vals, 10)), 2),
        "max_mm": round(float(vals.max()), 2),
    }
