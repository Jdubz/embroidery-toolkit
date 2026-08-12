"""Feature width on a binary mask, as local thickness.

Minimum feature size is the defect that keeps recurring in this repo, so the
thing that measures it has to be right. Three ways of getting it wrong, all of
which have been in this codebase:

**Averaging 2*edt over every pixel understates by half.** Across a stroke of
width w the distance transform runs 0 at the edges to w/2 at the centre, so the
mean lands near w/2 and thickening looks like it barely worked.

**An 8-neighbour local-maximum ridge finds almost no medial axis.** `edt >=
maximum_filter(edt, 3)` asks a pixel to beat *every* neighbour, but along a
medial-axis branch the distance transform climbs steadily toward the middle of
the shape, so each branch pixel loses to the neighbour ahead of it and only
isolated peaks survive. It works by accident on uniform thin line art, where edt
is flat along the stroke and the plateau passes — which is why it went unnoticed.
It collapses on anything that tapers. On the I-heart-Screaming forehead star,
15.8 mm² and 6,300 px, it returned **five** ridge pixels, two of them 1-px corner
artefacts, and reported 0.10 mm for a shape 3.3 mm across. That very nearly got
a perfectly stitchable fill deleted as sub-minimum detail.

**Per-direction non-maximum suppression over-fires instead.** Testing each
principal direction separately fixes the taper case, but discretisation makes
interior pixels of a convex shape win in one direction or another, so a 4 mm
disc reported 1.6 mm. Measured, not guessed.

So no ridge at all. This uses **local thickness**: a pixel's thickness is the
diameter of the largest disc that both contains it and fits entirely inside the
mask. That is the standard morphological definition of feature width, it is
exact on bars and discs alike, and it is area-weighted — so "12% of the ink is
under 1 mm" means 12% of the actual ink area, which is the question being asked.

It is computed by granulometry rather than by brute force. Opening the mask with
a disc of radius r is `dilate(edt >= r, disk(r))`, and dilating by a disc is just
"within distance r of", so each radius costs one extra distance transform:

    thickness(p) = 2 * max{ r : dist(p, {edt >= r}) <= r }

Convention: width = 2*edt, so a 1-px line reports 2 px. Every width figure
recorded in this repo uses it; do not "correct" it without restating them.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def thickness_map(mask: np.ndarray, max_r: float | None = None) -> np.ndarray:
    """Local thickness in PIXELS for every pixel of `mask`, 0 elsewhere.

    Radii step by 1 px, which fixes the width quantisation at 2 px. Do not be
    tempted to grow the step with the radius to save time: that was tried, and
    it put the coarse band right on top of the 2-3 mm filled-shape minimum —
    a 4 mm disc came back as 3.65 mm and a 3 mm bar as 2.88 mm.

    Cost is instead bounded by `max_r`, above which thickness saturates. Every
    decision this feeds is a comparison against a small threshold, so the
    distinction between "12 mm wide" and "33 mm wide" buys nothing, while the
    distinction between 0.8 mm and 1.2 mm decides whether artwork survives.
    """
    mask = mask.astype(bool)
    out = np.zeros(mask.shape, dtype=float)
    if not mask.any():
        return out
    edt = ndimage.distance_transform_edt(mask)
    rmax = float(edt.max())
    if max_r is not None:
        rmax = min(rmax, max_r)
    r = 1.0
    while r <= rmax + 1e-9:
        core = edt >= r                      # erosion by a disc of radius r
        if not core.any():
            break
        reach = ndimage.distance_transform_edt(~core)   # dilation of that core
        out[mask & (reach <= r)] = 2.0 * r
        r += 1.0
    # Anything too thin for even the first radius keeps its own distance value,
    # so hairlines report their real width instead of zero.
    thin = mask & (out == 0)
    out[thin] = 2.0 * edt[thin]
    return out


#: Widths saturate here. Well clear of every limit in `design_limits` — the
#: widest is a 3 mm safe filled shape — so no decision is affected, and it keeps
#: a broad keyline from costing hundreds of distance transforms.
SATURATE_MM = 12.0


def widths_mm(mask: np.ndarray, ppm: float, max_mm: float = SATURATE_MM) -> np.ndarray:
    """Local thickness in mm, one sample per ink pixel (area-weighted).

    Area-weighted is the point: "39% of the ink is under 1 mm" then means 39%
    of the actual ink, which is what a digitizer is deciding about. Sampling
    along a skeleton instead weights by axis length, which is proportional to
    area/width and so over-represents exactly the thin features being counted.
    The two differ a lot in practice — on the LemonCat outline, 39% by area
    against 82% along the axis.

    Returns an empty array for an empty mask, so callers must guard before
    taking a percentile.
    """
    mask = mask.astype(bool)
    if not mask.any():
        return np.zeros(0)
    return thickness_map(mask, max_r=max_mm / 2.0 * ppm)[mask] / ppm


def width_mm(mask: np.ndarray, ppm: float, max_mm: float = SATURATE_MM) -> float:
    """One representative width for a single shape: the median over its area."""
    w = widths_mm(mask, ppm, max_mm)
    return float(np.median(w)) if w.size else 0.0


def frac_below_mm(mask: np.ndarray, ppm: float, width_mm_: float) -> float:
    """Fraction of ink area whose local thickness is under `width_mm_`.

    The same question `widths_mm(...) < w` answers, but at **one** radius
    instead of sweeping every radius up to the saturation cap. `thickness_map`
    exists to give a whole distribution; when the only question is "how much of
    this is too thin", the sweep is thrown away — it is two distance transforms
    of work, not fifty.

    It is also the more accurate answer. The sweep steps radii by a whole pixel,
    so it can only place a threshold on an even pixel count and quantises width
    to 2 px; here the radius is `width/2` exactly, whatever that is in pixels.
    So do NOT reimplement this as a percentile of `widths_mm` — the two disagree
    by up to one quantum, and this one is right.

    Returns 0.0 for an empty mask: nothing is too thin when there is nothing.
    """
    mask = mask.astype(bool)
    n = int(mask.sum())
    if not n:
        return 0.0
    r = width_mm_ / 2.0 * ppm
    if r <= 0:
        return 0.0
    core = ndimage.distance_transform_edt(mask) >= r      # erosion by a disc
    if not core.any():
        return 1.0
    reach = ndimage.distance_transform_edt(~core)         # dilation back out
    return 1.0 - float((mask & (reach <= r)).sum()) / n
