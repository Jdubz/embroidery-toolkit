"""Worked example: build a design in code and write a machine-ready PES file.

Run from the repo root:

    .venv\\Scripts\\python.exe tools\\examples\\generate_monogram_frame.py

It emits designs/out/frame.pes — a double-outlined rounded rectangle sized to
leave a safe margin inside the 100 x 100 mm field, plus corner tick marks in a
second colour. Small enough to stitch as a test, real enough to show the shape
of a generator: build geometry in millimetres, convert once at the end, let the
machine profile decide the bounds.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyembroidery as pe

from embroidery_tools import analyze
from embroidery_tools import profile as prof

STITCH_LEN_MM = 2.0  # running-stitch length; 1.8-2.5 mm is the usual range


def mm(v: float) -> float:
    return prof.mm_to_units(v)


def run_line(a: tuple[float, float], b: tuple[float, float]) -> list[tuple[float, float]]:
    """Walk from a to b in STITCH_LEN_MM steps, in millimetres."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    dist = math.hypot(dx, dy)
    steps = max(1, int(dist / STITCH_LEN_MM))
    return [(a[0] + dx * i / steps, a[1] + dy * i / steps) for i in range(steps + 1)]


def rounded_rect(w: float, h: float, radius: float) -> list[tuple[float, float]]:
    """Closed rounded rectangle centred on the origin, in millimetres."""
    hw, hh = w / 2 - radius, h / 2 - radius
    pts: list[tuple[float, float]] = []
    corners = [(hw, hh, 0), (-hw, hh, 90), (-hw, -hh, 180), (hw, -hh, 270)]
    for cx, cy, start in corners:
        arc_steps = max(4, int((radius * math.pi / 2) / STITCH_LEN_MM))
        for i in range(arc_steps + 1):
            angle = math.radians(start + 90 * i / arc_steps)
            pts.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    pts.append(pts[0])
    return pts


def densify(path: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = [path[0]]
    for a, b in zip(path, path[1:]):
        out.extend(run_line(a, b)[1:])
    return out


def main() -> int:
    field_w, field_h = prof.max_field_mm()
    margin = 6.0  # clearance from the edge of the stitchable field
    w, h = field_w - 2 * margin, field_h - 2 * margin

    pattern = pe.EmbPattern()

    # Colour 1: a double outline, the inner one offset 3 mm.
    outer = densify(rounded_rect(w, h, 10.0))
    inner = densify(rounded_rect(w - 6, h - 6, 8.0))
    pattern.add_block([(mm(x), mm(y)) for x, y in outer], "#1F3A93")
    pattern.add_block([(mm(x), mm(y)) for x, y in inner], "#1F3A93")

    # Colour 2: short registration ticks at the four corners.
    tick = 5.0
    hw, hh = w / 2, h / 2
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        a = (sx * (hw - tick), sy * (hh - tick))
        b = (sx * hw, sy * hh)
        pattern.add_block([(mm(x), mm(y)) for x, y in densify([a, b])], "#C0392B")

    pattern.end()

    out_dir = prof.REPO_ROOT / "designs" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "frame.pes"
    pe.write(pattern, str(out), {"pes version": prof.recommended_pes_version()})

    info = analyze.describe(out)
    print(f"Wrote {out}")
    print(f"  {info.width_mm:.1f} x {info.height_mm:.1f} mm, "
          f"{info.real_stitches:,} stitches, {info.thread_count} colours")
    findings = analyze.validate(info)
    for f in findings:
        print(f"  {f.severity.upper()}: {f.message}")
    return 1 if any(f.severity == analyze.ERROR for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
