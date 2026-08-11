"""Compare a finished design against the artwork it came from.

This is the check that catches *dropped elements* — parts of the source that
never got stitched. Nothing else in the toolkit can see them:

- `validate` reads the PES alone and has no idea what the design was meant to
  be. A design missing its eyebrows validates perfectly.
- The render looks fine, because what *is* stitched is stitched correctly.
- Counting connected regions does not work either. When LemonY lost every solid
  mass — eyebrows, pupils, nose — all ten source regions still reported 44% or
  more coverage, because each was partly traced. The component count showed
  nothing while 34% of the artwork's area went unstitched.

So the measurement that works is area: dilate the stitch path by a tolerance,
subtract it from the source ink, and report what is left and where.

Colours that are deliberately left unstitched (white eyes on white cloth) are
excluded with `skip_hex`, mirroring `color_separate.py --skip`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pyembroidery as pe
from PIL import Image
from scipy import ndimage

from . import profile as prof


@dataclass
class Patch:
    area_mm2: float
    cx_pct: float
    cy_pct: float


@dataclass
class CoverageReport:
    design: Path
    source: Path
    ink_mm2: float = 0.0
    covered_mm2: float = 0.0
    tolerance_mm: float = 0.0
    patches: list[Patch] = field(default_factory=list)

    @property
    def covered_pct(self) -> float:
        return 100.0 * self.covered_mm2 / self.ink_mm2 if self.ink_mm2 else 0.0

    @property
    def missing_mm2(self) -> float:
        return max(0.0, self.ink_mm2 - self.covered_mm2)

    @property
    def missing_pct(self) -> float:
        return 100.0 - self.covered_pct


def _hex_rgb(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    if len(s) != 6:
        raise ValueError(f"bad colour {s!r}: expected six hex digits")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def _stitch_runs(pattern: pe.EmbPattern) -> list[list[tuple[float, float]]]:
    """Stitch points grouped into runs; jumps and trims break a run.

    Travel across a jump is not thread on the fabric, so drawing it would
    credit coverage the finished piece does not have.
    """
    runs, cur = [], []
    for x, y, cmd in pattern.stitches:
        if (cmd & pe.COMMAND_MASK) == pe.STITCH:
            cur.append((x, y))
        else:
            if len(cur) > 1:
                runs.append(cur)
            cur = []
    if len(cur) > 1:
        runs.append(cur)
    return runs


def analyse(design: str | Path, source: str | Path, *,
            skip_hex: tuple[str, ...] = (), tolerance_mm: float = 0.4,
            min_patch_mm2: float = 2.0, overlay: str | Path | None = None,
            thread_mm: float = 0.4, machine: dict | None = None) -> CoverageReport:
    design, source = Path(design), Path(source)
    machine = machine or prof.load()

    img = Image.open(source).convert("RGBA")
    arr = np.array(img)
    H, W = arr.shape[:2]

    ink = arr[:, :, 3] > 128
    if skip_hex:
        # Drop pixels close to a deliberately unstitched colour, so white eyes
        # on white cloth are not reported as missing stitching. The 90 is the
        # same sum-of-channel-differences tolerance used elsewhere in the repo
        # for matching flat artwork colours.
        rgb = arr[:, :, :3].astype(np.int16)
        nearest_skip = np.min(
            [np.abs(rgb - np.array(_hex_rgb(c))).sum(axis=2) for c in skip_hex], axis=0)
        ink = ink & (nearest_skip > 90)

    if not ink.any():
        raise ValueError(f"{source.name}: no stitchable pixels after --skip")

    ys, xs = np.nonzero(ink)
    bb = (xs.min(), xs.max(), ys.min(), ys.max())

    pattern = pe.read(str(design))
    runs = _stitch_runs(pattern)
    if not runs:
        raise ValueError(f"{design.name}: no stitches")

    pts = np.array([p for r in runs for p in r], dtype=float)
    mn, mx = pts.min(axis=0), pts.max(axis=0)
    span = np.maximum(mx - mn, 1e-6)

    def to_px(p):
        return (bb[0] + (p[0] - mn[0]) / span[0] * (bb[1] - bb[0]),
                bb[2] + (p[1] - mn[1]) / span[1] * (bb[3] - bb[2]))

    px_per_mm = (bb[1] - bb[0]) / max(prof.units_to_mm(span[0]), 1e-6)

    stitched = np.zeros((H, W), bool)
    for run in runs:
        prev = to_px(run[0])
        for p in run[1:]:
            cur = to_px(p)
            n = max(2, int(abs(cur[0] - prev[0]) + abs(cur[1] - prev[1])))
            for t in np.linspace(0.0, 1.0, n):
                xx = int(prev[0] + (cur[0] - prev[0]) * t)
                yy = int(prev[1] + (cur[1] - prev[1]) * t)
                if 0 <= xx < W and 0 <= yy < H:
                    stitched[yy, xx] = True
            prev = cur

    tol_px = max(1, int(round(tolerance_mm * px_per_mm)))
    near = ndimage.binary_dilation(stitched, iterations=tol_px)

    per_mm2 = px_per_mm ** 2
    rep = CoverageReport(design=design, source=source, tolerance_mm=tolerance_mm,
                         ink_mm2=ink.sum() / per_mm2,
                         covered_mm2=(ink & near).sum() / per_mm2)

    missing = ink & ~near
    lab, n = ndimage.label(missing)
    if n:
        sizes = ndimage.sum(missing, lab, range(1, n + 1)) / per_mm2
        for idx in np.argsort(sizes)[::-1]:
            if sizes[idx] < min_patch_mm2:
                break
            yy, xx = np.nonzero(lab == idx + 1)
            rep.patches.append(Patch(float(sizes[idx]),
                                     100.0 * xx.mean() / W, 100.0 * yy.mean() / H))

    if overlay:
        # Draw the thread at its TRUE width against the artwork at the same
        # scale. A hairline here is a lie: a single running stitch is one 40 wt
        # thread, about 0.4 mm, and this repo's own minimum for linework is
        # 1.0 mm. Rendered as a hairline the two look identical, which is how a
        # design 3x lighter than its artwork passed visual review.
        half = max(1, int(round(thread_mm / 2 * px_per_mm)))
        out = np.full((H, W, 3), 255, np.uint8)
        out[ink] = (255, 170, 60)                                  # artwork
        out[ndimage.binary_dilation(stitched, iterations=half)] = (0, 90, 200)
        Image.fromarray(out).save(str(overlay))

    return rep
