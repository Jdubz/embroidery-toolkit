"""The Brother/PEC 64-colour thread palette, and matching arbitrary colours to it.

A PES file stores colours as indices into this palette. If you author in an RGB
colour the palette does not contain, something downstream picks the nearest
entry for you — better to choose it deliberately here.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from . import profile as prof


@lru_cache(maxsize=1)
def load(path: Path | None = None) -> list[dict]:
    p = Path(path) if path else prof.PALETTE_PATH
    if not p.is_file():
        raise FileNotFoundError(
            f"Thread palette not found at {p}. Regenerate it with "
            f"`stitch palette --regenerate`."
        )
    with p.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["pec_index"] = int(r["pec_index"])
        r["r"], r["g"], r["b"] = int(r["r"]), int(r["g"]), int(r["b"])
    return rows


def parse_hex(value: str) -> tuple[int, int, int]:
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        raise ValueError(f"'{value}' is not a 3- or 6-digit hex colour")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def _srgb_to_linear(c: int) -> float:
    x = c / 255.0
    return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4


def _to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """sRGB -> CIELAB (D65). Perceptual distance beats raw RGB distance here."""
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505
    # D65 reference white
    x, y, z = x / 0.95047, y / 1.00000, z / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t) + (16 / 116)

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def nearest(colour: str | tuple[int, int, int], count: int = 1) -> list[dict]:
    """Return the `count` closest Brother threads to a colour, nearest first."""
    rgb = parse_hex(colour) if isinstance(colour, str) else colour
    target = _to_lab(rgb)
    scored = []
    for entry in load():
        lab = _to_lab((entry["r"], entry["g"], entry["b"]))
        dist = sum((a - b) ** 2 for a, b in zip(target, lab)) ** 0.5
        scored.append((dist, entry))
    scored.sort(key=lambda s: s[0])
    return [dict(e, delta_e=round(d, 2)) for d, e in scored[:count]]


def regenerate(path: Path | None = None) -> Path:
    """Rewrite the palette CSV from pyembroidery's embedded PEC thread table."""
    import pyembroidery.EmbThreadPec as pec

    out = Path(path) if path else prof.PALETTE_PATH
    rows = []
    for idx, t in enumerate(pec.get_thread_set()):
        if t is None:
            continue
        rows.append(
            {
                "pec_index": idx,
                "brother_code": (t.catalog_number or "").strip(),
                "name": (t.description or "").strip(),
                "hex": "#%06X" % (t.color & 0xFFFFFF),
                "r": (t.color >> 16) & 0xFF,
                "g": (t.color >> 8) & 0xFF,
                "b": t.color & 0xFF,
                "brand": (t.brand or "").strip(),
            }
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    load.cache_clear()
    return out
