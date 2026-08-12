"""Recover a design's white negative space as real thread, for dark cloth.

Flat sticker artwork gets its whites for free: the ink layer is drawn with holes
in it and the paper shows through. Eyeballs, teeth, lettering, the inside of a
spit droplet — none of it is painted, it is simply *not* covered. On white cloth
an embroidered version inherits that trick exactly, which is why `Scream` is
three colours and needs no white thread at all.

On black cloth the trick inverts and the design collapses. Every one of those
holes now reads black, so the lettering, the teeth and the eyes disappear, and
the ink layer that used to define them is itself invisible against the fabric.

This rebuilds the artwork for that case:

* **The ink layer is dropped.** On dark cloth bare fabric already *is* the ink
  colour, so stitching it spends thread and machine time on something you cannot
  see. Dropping it is not a compromise — the outlines, pupils and tooth gaps all
  still read, because they are the fabric showing between stitched areas. It is
  also the cheaper file: on `Scream` the ink layer is 2,742 mm2 against the
  1,405 mm2 of white that replaces it.
* **Holes that revealed bare paper become a stitched layer** in `--thread`.
* **Holes that revealed another colour are left alone.** This is the part that
  has to be measured rather than assumed. Of the 27 holes in Scream's black
  layer, three sit over the green head, the red heart and the red tongue; fill
  those with white and the white is stitched *under* a colour that is then
  stitched over it, which is the "three or more overlapping stitches" the manual
  blames for broken needles. Coverage is measured per hole against a raster of
  every other colour, not guessed from position.
* **`--promote-at` keeps a chosen ink shape, in the thread colour.** Solid ink
  masses with nothing beneath them just vanish when the layer is dropped. On
  Scream that is the "I" of "I heart Screaming" — a discrete subpath, so it can
  be named by position and stitched white instead.

What this cannot do is split a shape. Scream's outlines, hair and tooth gaps are
one 4,942 mm2 subpath, so "keep the hair but drop the outlines" is not reachable
from this artwork — the hair goes unstitched with the rest. `--keep-ink` stitches
the whole ink layer anyway if you want it tonally present in black-on-black.

    svg_dark_invert.py in.svg out.svg --artwork-mm 87 --ink 000000 --thread FFFFFF
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embroidery_tools import svgpath  # noqa: E402

SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)
PPM = 10.0          # raster resolution for the coverage test, px per mm


def norm(colour: str) -> str:
    c = colour.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in c):
        raise SystemExit(f"'{colour}' is not a 3- or 6-digit hex colour. "
                         "In PowerShell, quote it: '000000', not 000000.")
    return c.upper()


def emit(pts) -> str:
    head = "M %g %g" % pts[0]
    return head + " " + " ".join("L %g %g" % p for p in pts[1:]) + " Z"


ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--artwork-mm", type=float, required=True,
                help="width the drawing will be stitched at; areas are reported in mm2")
ap.add_argument("--ink", required=True, metavar="RRGGBB",
                help="the layer whose holes carry the negative space")
ap.add_argument("--thread", default="FFFFFF", metavar="RRGGBB",
                help="colour to stitch the recovered negative space in (default FFFFFF)")
ap.add_argument("--promote-at", action="append", default=[], metavar="X,Y",
                help="keep the ink shape nearest this mm coordinate, in --thread; "
                     "repeatable")
ap.add_argument("--cloth-frac", type=float, default=0.9, metavar="F",
                help="a hole counts as bare cloth when this fraction of it is "
                     "covered by no other colour (default 0.9)")
ap.add_argument("--keep-ink", action="store_true",
                help="stitch the ink layer as well, for a tonal dark-on-dark read")
ap.add_argument("--report", action="store_true",
                help="print the per-hole classification and exit without writing")
a = ap.parse_args()

ink_c, thread_c = norm(a.ink), norm(a.thread)

tree = ET.parse(a.src)
root = tree.getroot()
paths = [p for p in root.iter(f"{{{SVG}}}path") if p.get("d")]
if not paths:
    raise SystemExit("no <path> elements with geometry")

layers: dict[str, tuple[ET.Element, list]] = {}
for p in paths:
    c = norm(p.get("fill") or "000000")
    subs = svgpath.parse_path(p.get("d"))       # raises on any command it cannot read
    curved = [s for s in subs if s["curved"]]
    if curved:
        raise SystemExit(
            f"#{c} contains {len(curved)} curved subpath(s). This tool re-emits "
            "geometry as polylines, which would silently flatten them. Flatten the "
            "artwork deliberately first, or extend this tool to carry `d` verbatim.")
    if c in layers:
        raise SystemExit(f"#{c} appears on more than one path; expected one path per colour")
    # A 2-point subpath encloses no area and has no interior to rasterise.
    layers[c] = (p, [s["points"] for s in subs if len(s["points"]) >= 3])

if ink_c not in layers:
    raise SystemExit(f"--ink {ink_c}: no path is filled #{ink_c}. Present: "
                     + ", ".join("#" + c for c in layers))
if thread_c in layers and thread_c != ink_c:
    raise SystemExit(f"--thread {thread_c} is already a colour in this document. "
                     "PES merges adjacent blocks sharing a colour, so the recovered "
                     "layer would fuse with it into one pass and one stop.")

ink_el, ink = layers[ink_c]

allpts = [pt for _, subs in layers.values() for s in subs for pt in s]
minx = min(p[0] for p in allpts)
miny = min(p[1] for p in allpts)
maxx = max(p[0] for p in allpts)
maxy = max(p[1] for p in allpts)
upm = (maxx - minx) / a.artwork_mm
print(f"  drawing {maxx - minx:.0f} units wide -> {a.artwork_mm:g} mm  ({upm:.3f} units/mm)")

W = int((maxx - minx) / upm * PPM) + 4
H = int((maxy - miny) / upm * PPM) + 4


def to_px(s):
    return [((x - minx) / upm * PPM + 2, (y - miny) / upm * PPM + 2) for x, y in s]


def raster(s) -> np.ndarray:
    img = Image.new("1", (W, H), 0)
    ImageDraw.Draw(img).polygon(to_px(s), fill=1)
    return np.asarray(img, bool)


def evenodd(subs) -> np.ndarray:
    """XOR of every subpath — that is exactly even-odd fill."""
    acc = np.zeros((H, W), bool)
    for s in subs:
        acc ^= raster(s)
    return acc


others = np.zeros((H, W), bool)
for c, (_, subs) in layers.items():
    if c != ink_c:
        others |= evenodd(subs)

# Nesting depth, as svg_subpath_filter computes it: odd is a hole, even is a fill.
def point_in(pt, s) -> bool:
    x, y = pt
    inside = False
    for i in range(len(s)):
        x0, y0 = s[i]
        x1, y1 = s[(i + 1) % len(s)]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


ancestors = [{j for j, o in enumerate(ink) if j != i and point_in(s[0], o)}
             for i, s in enumerate(ink)]
depth = [len(anc) for anc in ancestors]
children = [{j for j, anc in enumerate(ancestors) if i in anc} for i in range(len(ink))]


def centre_mm(s):
    return ((sum(p[0] for p in s) / len(s) - minx) / upm,
            (sum(p[1] for p in s) / len(s) - miny) / upm)


rows, selected, mixed = [], set(), []
for i, s in enumerate(ink):
    if depth[i] % 2 == 0:
        continue
    m = raster(s).copy()
    for j in children[i]:                       # the hole's own area, not its islands'
        if depth[j] == depth[i] + 1:
            m &= ~raster(ink[j])
    n = int(m.sum())
    if not n:
        continue
    cloth = float((m & ~others).sum()) / n
    cx, cy = centre_mm(s)
    rows.append((i, n / PPM**2, cx, cy, cloth))
    if cloth >= a.cloth_frac:
        selected.add(i)
    elif cloth > 0.10:
        # Below 10% is the rasterised edge of a hole that sits cleanly over
        # another colour, not a real ambiguity — a 68 mm2 hole loses ~4% of its
        # pixels to its own perimeter at this resolution. Warning on that would
        # fire on every correct design, which is how a check stops being read.
        mixed.append((i, n / PPM**2, cx, cy, cloth))

promoted = set()
for spec in a.promote_at:
    tx, ty = (float(t) for t in spec.split(","))
    cand = [i for i in range(len(ink)) if depth[i] % 2 == 0]
    if not cand:
        raise SystemExit("--promote-at: the ink layer has no fill subpaths")
    best = min(cand, key=lambda i: (centre_mm(ink[i])[0] - tx) ** 2
                                 + (centre_mm(ink[i])[1] - ty) ** 2)
    cx, cy = centre_mm(ink[best])
    area = raster(ink[best]).sum() / PPM**2
    print(f"  --promote-at {tx},{ty} -> ink subpath {best} "
          f"({area:.1f} mm2, at {cx:.1f},{cy:.1f}) will stitch in #{thread_c}")
    promoted.add(best)
    selected.add(best)

if a.report:
    print(f"\n  #{ink_c} holes — what lies underneath:")
    print("    %3s %9s %-14s %8s  %s" % ("id", "area mm2", "centre mm", "bare", ""))
    for i, area, cx, cy, cloth in sorted(rows, key=lambda r: -r[1]):
        verdict = f"-> #{thread_c}" if i in selected else "leave as a hole"
        print("    %3d %9.1f %-14s %7.0f%%  %s" % (i, area, f"{cx:.1f},{cy:.1f}",
                                                   cloth * 100, verdict))
    sys.exit(0)

for i, area, cx, cy, cloth in mixed:
    print(f"  WARNING  hole {i} ({area:.1f} mm2 at {cx:.1f},{cy:.1f}) is {cloth*100:.0f}% "
          "bare cloth — neither clearly negative space nor clearly over another "
          "colour. Left as a hole; check it in the render.", file=sys.stderr)

# Emit only regions with no selected ancestor. A selected region already carries
# its descendants as alternating even-odd rings, so emitting a descendant again
# would XOR it back out — the area would silently come out unstitched.
tops = [i for i in sorted(selected) if not (ancestors[i] & selected)]
d_parts: list[str] = []
for i in tops:
    d_parts.append(emit(ink[i]))
    for j in sorted(children[i]):
        d_parts.append(emit(ink[j]))

if not d_parts:
    raise SystemExit("nothing was recovered; the ink layer has no holes over bare cloth")

white = ET.Element(f"{{{SVG}}}path", {
    "id": "recovered_negative_space",
    "d": " ".join(d_parts),
    "fill": f"#{thread_c}",
    "fill-rule": "evenodd",
    "stroke": "none",
})

# Registration, not validity: geometry is copied verbatim, so a bbox outside the
# source means the wrong subpaths were gathered. That renders as a plausible
# drawing and stitches happily — the error only shows up on fabric.
wpts = [p for i in tops for p in ink[i]]
if (min(p[0] for p in wpts) < minx - 1 or max(p[0] for p in wpts) > maxx + 1
        or min(p[1] for p in wpts) < miny - 1 or max(p[1] for p in wpts) > maxy + 1):
    raise SystemExit("recovered layer falls outside the source bounding box")

if not a.keep_ink:
    root.remove(ink_el)
root.insert(0, white)                # lightest first, matching svg_prep's own order

area_mm2 = float((evenodd([ink[i] for i in tops] + [ink[j] for i in tops
                                                    for j in children[i]])).sum()) / PPM**2
ink_mm2 = float(evenodd(ink).sum()) / PPM**2
print(f"  {len(tops)} region(s) recovered as #{thread_c}: {area_mm2:.0f} mm2"
      + (f" (of which {len(promoted)} promoted from ink)" if promoted else ""))
print(f"  #{ink_c} " + (f"kept, {ink_mm2:.0f} mm2 still stitched"
                        if a.keep_ink else
                        f"dropped, {ink_mm2:.0f} mm2 now bare cloth"))

tree.write(a.dst, encoding="utf-8", xml_declaration=True)
ET.parse(a.dst)      # fail loudly rather than handing a broken document downstream
print(f"  -> {a.dst}")
