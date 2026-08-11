"""Drop individual subpaths from a flat-colour SVG, by measurement or by position.

Artwork drawn for screen carries detail the machine cannot render. `svg_prep.py`
reports stroke widths, but it cannot see *fills* that are too thin, and this
design is entirely fills: the I-heart-Screaming eye veins measure 0.36-0.91 mm
at their widest against a 1.2 mm safe minimum. Digitizing them faithfully lays
one 0.4 mm thread and reads as a scratch.

Two ways to select, because two different things are being removed:

  --drop-thin RRGGBB=MM   every filled subpath of that colour narrower than MM.
                          A machine constraint, applied by measurement.
  --drop-at RRGGBB=X,Y    the one subpath of that colour whose centroid is
                          nearest X,Y (mm from the drawing's top-left). A
                          deliberate look change, named explicitly so it can
                          never be confused with the constraint above.

Both are scoped to a colour on purpose. An unscoped width rule would delete the
black keyline — it is a single long subpath and measures thin everywhere, so a
global rule would silently erase the whole outline of the design.

**Holes are never dropped.** Under `fill-rule="evenodd"` a subpath nested at odd
depth cuts a hole in its parent; deleting one fills the hole back in, which adds
thread rather than removing it. Depth is computed by containment and odd-depth
subpaths are skipped by every rule.

Widths come from `embroidery_tools.measure`, which rasterises each subpath and
takes its local thickness — the diameter of the largest disc that fits inside
the shape through each pixel. See that module for the two ridge-based methods
this replaced and the shapes that caught each of them out.

Usage:
  svg_subpath_filter.py <in.svg> <out.svg> --artwork-mm 87 --report
  svg_subpath_filter.py <in.svg> <out.svg> --artwork-mm 87 \
      --drop-thin EE2028=1.0 --drop-thin 73B236=1.0 --drop-at 73B236=62.7,19.6
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw

from embroidery_tools.measure import width_mm as _width_mm

SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)
# Rasterisation resolution for measurement. 10 px/mm resolves a 0.3 mm feature
# as 3 px, which is ample for a 1.0-1.2 mm decision, and keeps the measurement
# fast on the large keyline subpaths — cost scales with pixels AND with radius.
PPM = 10.0
TOK = re.compile(r"([MmLlZzHhVv])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")


def parse_subpaths(d: str) -> list[list[tuple[float, float]]]:
    """M/L/H/V/Z only — verified to be all this generator emits."""
    toks = TOK.findall(d)
    out, cur = [], []
    x = y = sx = sy = 0.0
    cmd = None
    i = 0
    while i < len(toks):
        c, num = toks[i]
        if c:
            cmd = c
            i += 1
            if cmd in "Zz":
                if cur:
                    out.append(cur)
                    cur = []
                x, y = sx, sy
            continue
        need = {"M": 2, "L": 2, "H": 1, "V": 1}[cmd.upper()]
        vals = []
        while len(vals) < need and i < len(toks) and not toks[i][0]:
            vals.append(float(toks[i][1]))
            i += 1
        if len(vals) < need:
            break
        rel, u = cmd.islower(), cmd.upper()
        if u == "M":
            if cur:
                out.append(cur)
            x, y = (x + vals[0], y + vals[1]) if rel else (vals[0], vals[1])
            sx, sy = x, y
            cur = [(x, y)]
            cmd = "l" if rel else "L"
        else:
            if u == "L":
                x, y = (x + vals[0], y + vals[1]) if rel else (vals[0], vals[1])
            elif u == "H":
                x = x + vals[0] if rel else vals[0]
            else:
                y = y + vals[0] if rel else vals[0]
            cur.append((x, y))
    if cur:
        out.append(cur)
    return [s for s in out if len(s) >= 3]


def emit(sub: list[tuple[float, float]]) -> str:
    head = "M %s" % " ".join(f"{x:g} {y:g}" for x, y in sub[:1])
    rest = " ".join(f"L {x:g} {y:g}" for x, y in sub[1:])
    return f"{head} {rest} Z"


def poly_area(s):
    a = 0.0
    for i in range(len(s)):
        x0, y0 = s[i]
        x1, y1 = s[(i + 1) % len(s)]
        a += x0 * y1 - x1 * y0
    return abs(a) / 2.0


def point_in(pt, s) -> bool:
    x, y = pt
    inside = False
    for i in range(len(s)):
        x0, y0 = s[i]
        x1, y1 = s[(i + 1) % len(s)]
        if (y0 > y) != (y1 > y):
            xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xi:
                inside = not inside
    return inside


def width_mm(sub, upm) -> float:
    xs = [p[0] for p in sub]
    ys = [p[1] for p in sub]
    w = max(2, int((max(xs) - min(xs)) / upm * PPM) + 4)
    h = max(2, int((max(ys) - min(ys)) / upm * PPM) + 4)
    if w * h > 40_000_000:
        return float("inf")
    img = Image.new("1", (w, h), 0)
    ImageDraw.Draw(img).polygon(
        [((x - min(xs)) / upm * PPM + 2, (y - min(ys)) / upm * PPM + 2) for x, y in sub],
        fill=1)
    m = np.asarray(img, bool)
    if not m.any():
        return 0.0
    return _width_mm(m, PPM)


ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--artwork-mm", type=float, required=True)
ap.add_argument("--drop-thin", action="append", default=[], metavar="RRGGBB=MM")
ap.add_argument("--drop-at", action="append", default=[], metavar="RRGGBB=X,Y")
ap.add_argument("--report", action="store_true")
a = ap.parse_args()


def norm(c):
    return c.strip().lstrip("#").upper()


thin_rules, at_rules = {}, {}
for spec in a.drop_thin:
    c, _, v = spec.partition("=")
    thin_rules[norm(c)] = float(v)
for spec in a.drop_at:
    c, _, v = spec.partition("=")
    at_rules.setdefault(norm(c), []).append(tuple(float(t) for t in v.split(",")))

tree = ET.parse(a.src)
root = tree.getroot()
paths = list(root.iter(f"{{{SVG}}}path"))
if not paths:
    raise SystemExit("no <path> elements")

parsed = [(p, parse_subpaths(p.get("d", ""))) for p in paths]
allpts = [pt for _, subs in parsed for s in subs for pt in s]
minx = min(p[0] for p in allpts)
miny = min(p[1] for p in allpts)
maxx = max(p[0] for p in allpts)
upm = (maxx - minx) / a.artwork_mm          # user units per mm
print(f"  drawing {maxx - minx:.0f} units wide -> {a.artwork_mm:g} mm  ({upm:.3f} units/mm)")

total_dropped = 0
for el, subs in parsed:
    colour = norm(el.get("fill") or "")
    depth = []
    for i, s in enumerate(subs):
        pt = s[0]
        depth.append(sum(1 for j, o in enumerate(subs) if j != i and point_in(pt, o)))
    rows = []
    for i, s in enumerate(subs):
        area = poly_area(s) / upm ** 2
        cx = sum(p[0] for p in s) / len(s)
        cy = sum(p[1] for p in s) / len(s)
        rows.append(dict(i=i, sub=s, area=area, depth=depth[i],
                         cx=(cx - minx) / upm, cy=(cy - miny) / upm,
                         w=width_mm(s, upm)))

    drop = set()
    lim = thin_rules.get(colour)
    if lim is not None:
        for r in rows:
            if r["depth"] % 2 == 0 and r["w"] < lim:
                drop.add(r["i"])
    for tx, ty in at_rules.get(colour, []):
        cand = [r for r in rows if r["depth"] % 2 == 0]
        if cand:
            best = min(cand, key=lambda r: (r["cx"] - tx) ** 2 + (r["cy"] - ty) ** 2)
            drop.add(best["i"])
            print(f"  #{colour} --drop-at {tx},{ty} -> subpath {best['i']} "
                  f"({best['area']:.1f} mm2, {best['w']:.2f} mm, at {best['cx']:.1f},{best['cy']:.1f})")

    if a.report:
        print(f"\n  #{colour}: {len(subs)} subpath(s)")
        print("    %3s %8s %7s %6s  %-14s %s" % ("id", "area mm2", "width", "depth", "centre mm", ""))
        for r in sorted(rows, key=lambda r: -r["area"]):
            kind = "hole" if r["depth"] % 2 else "fill"
            mark = "  <- drop" if r["i"] in drop else ""
            print("    %3d %8.1f %7.2f %6d  %-14s %s%s"
                  % (r["i"], r["area"], r["w"], r["depth"],
                     f"{r['cx']:.1f},{r['cy']:.1f}", kind, mark))
        continue

    if drop:
        keep = [r["sub"] for r in rows if r["i"] not in drop]
        el.set("d", " ".join(emit(s) for s in keep))
        total_dropped += len(drop)
        print(f"  #{colour}: dropped {len(drop)} of {len(subs)} subpath(s), {len(keep)} kept")

if a.report:
    sys.exit(0)

tree.write(a.dst, encoding="utf-8", xml_declaration=True)
ET.parse(a.dst)      # fail loudly rather than handing a broken document downstream
print(f"  dropped {total_dropped} subpath(s) total -> {a.dst}")
