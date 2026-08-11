"""Remap and drop colours in flattened artwork, before digitizing.

Two operations, both of which reduce thread changes on a single-needle machine:

* **map** — merge one colour into another (red into green: one less rethread).
* **drop** — remove a colour entirely so that area is left **unstitched** and the
  garment shows through. This is the cheapest trick in machine embroidery: white
  letters on white cloth need no white thread, no stitches, and no time. It also
  keeps the piece softer, because unstitched fabric still drapes.

Colours are matched to the nearest entry in the image's own flat palette rather
than by exact hex, so hand-typed approximations work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass
class RecolorReport:
    palette_before: list = field(default_factory=list)
    mapped: list = field(default_factory=list)
    dropped: list = field(default_factory=list)
    palette_after: list = field(default_factory=list)


def parse_hex(v: str) -> tuple[int, int, int]:
    s = v.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise ValueError(f"'{v}' is not a 3- or 6-digit hex colour")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _hex(c) -> str:
    return "#%02X%02X%02X" % tuple(int(x) for x in c)


def image_palette(arr: np.ndarray, top: int = 24) -> list[tuple[tuple, float]]:
    """Flat palette with coverage fractions, most common first."""
    rgb = arr[:, :, :3]
    if arr.shape[2] == 4:
        opaque = arr[:, :, 3] > 128
        rgb = rgb[opaque]
    else:
        rgb = rgb.reshape(-1, 3)
    cols, counts = np.unique(rgb.reshape(-1, 3), axis=0, return_counts=True)
    total = counts.sum() or 1
    order = np.argsort(counts)[::-1][:top]
    return [(tuple(int(x) for x in cols[i]), counts[i] / total) for i in order]


def _nearest_in(palette: list[tuple], target: tuple) -> tuple:
    t = np.array(target, dtype=float)
    best, bd = palette[0], None
    for c, _ in ((c, f) for c, f in palette):
        d = float(((np.array(c, dtype=float) - t) ** 2).sum())
        if bd is None or d < bd:
            bd, best = d, c
    return best


def recolor(
    src: str | Path,
    dst: str | Path,
    *,
    mappings: list[tuple[str, str]] | None = None,
    drops: list[str] | None = None,
    drop_lighter_than: int | None = None,
) -> RecolorReport:
    """Apply colour maps and drops. Dropped areas become transparent."""
    src, dst = Path(src), Path(dst)
    img = Image.open(src).convert("RGBA")
    arr = np.array(img)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3].copy()

    pal = image_palette(arr)
    report = RecolorReport(palette_before=[(_hex(c), round(f * 100, 1))
                                           for c, f in pal])
    pal_colors = [(c, f) for c, f in pal]

    # Drops first, so a mapping cannot resurrect a dropped colour.
    for d in drops or []:
        target = _nearest_in(pal_colors, parse_hex(d))
        m = (rgb == np.array(target)).all(axis=2)
        alpha[m] = 0
        report.dropped.append((_hex(target), int(m.sum())))

    if drop_lighter_than is not None:
        lum = rgb.astype(int).sum(axis=2) / 3
        m = (lum >= drop_lighter_than) & (alpha > 0)
        if m.any():
            alpha[m] = 0
            report.dropped.append((f">= luma {drop_lighter_than}", int(m.sum())))

    out_rgb = rgb.copy()
    for a_hex, b_hex in mappings or []:
        a = _nearest_in(pal_colors, parse_hex(a_hex))
        b = _nearest_in(pal_colors, parse_hex(b_hex))
        m = (rgb == np.array(a)).all(axis=2) & (alpha > 0)
        out_rgb[m] = b
        report.mapped.append((_hex(a), _hex(b), int(m.sum())))

    result = np.dstack([out_rgb, alpha]).astype(np.uint8)
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(result, mode="RGBA").save(dst)

    report.palette_after = [(_hex(c), round(f * 100, 1))
                            for c, f in image_palette(result)]
    return report
