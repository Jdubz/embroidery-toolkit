"""Grow or shrink a colour's filled shapes by a measured amount, in millimetres.

Minimum feature size is the defect that keeps recurring here, and until now the
only tool aimed at it could **delete**. `svg_subpath_filter --drop-thin` removes
a subpath measuring under the machine's minimum, which is the right answer when
the detail was never going to survive: the I-heart-Screaming eye veins run
0.36-0.91 mm, and one 0.4 mm thread laid down their length reads as a scratch
however it is digitized.

It is the wrong answer when the thin thing *is* the drawing. PissMuffy's dark
layer measures 0.60 mm median local thickness and MuffyHat's 0.96 mm, both under
the 1.0 mm satin minimum, and neither can be dropped. The only move left was to
centreline them and accept a single running stitch.

This is the other move: thicken the artwork until it is stitchable. It is a
**look change** and should be declared as one — a 0.6 mm line grown to 1.2 mm is
twice the line weight, and on lettering that is the difference between a face
and a bolder cut of it. Grow the least that clears the limit, then look at the
render.

Offsetting is done with Shapely, which is the same engine Ink/Stitch uses for
its own `knockdown_fill` offsets (`extensions/inkstitch/inkstitch/bin/shapely`),
so the geometry matches what the consumer of this file would have produced.
Inkscape is not used: its Path > Outset is GUI-only, absent from the 1213
entries in `inkscape --action-list`, and the two headless substitutes both have
teeth. The Offset live path effect bakes on load/save but `object-to-path`
*reverts* it to `inkscape:original-d` and silently drops the offset; the
stroke-width + `object-stroke-to-path` + `path-union` trick works but rewrites
the style block. Neither is worth a subprocess when the geometry is three lines
of Shapely.

**Even-odd is honoured, so holes stay holes.** Rings are folded with symmetric
difference, which is exactly what `fill-rule="evenodd"` means, and it composes to
any depth — the depth-3 eye glints inside IHeartScreaming_on_black's selected
holes come out right without a special case. Growing a shape shrinks its holes,
which is the correct behaviour and also how a hole disappears.

**Topology is checked, because that is how this goes wrong invisibly.** Two
features 0.8 mm apart merge into one when each grows 0.4 mm, and a 0.5 mm hole
closes. Neither is visible in a render at design size, both are visible on
fabric, and `validate` cannot see either — it looks at stitches, and the stitches
are perfectly good stitches of the wrong shape. So the shell and hole counts are
compared before and after and a change is an error, not a warning. Pass
`--allow-topology-change` when the merge is what you wanted.

This mirrors the guard on `raster._clean_mask`, which compares connected-region
counts rather than area for the same reason: a hairline join or break costs
almost no area and an area test cannot see it.

Widths are area-weighted local thickness from `embroidery_tools.measure` — the
same granulometry every width figure in this repo is quoted in, so "39% of the
ink is under 1 mm" means 39% of the ink.

    svg_offset.py in.svg out.svg --artwork-mm 87 --report
    svg_offset.py in.svg out.svg --artwork-mm 87 --grow 25270A=0.3
    svg_offset.py in.svg out.svg --artwork-mm 87 --to-min 25270A=1.2
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import shapely
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embroidery_tools import profile as prof  # noqa: E402
from embroidery_tools import svggeom as G  # noqa: E402
from embroidery_tools import svgpath  # noqa: E402
from embroidery_tools.measure import frac_below_mm, widths_mm  # noqa: E402

# Region geometry — even-odd folding, boolean results and path emission — lives
# in svggeom, shared with svgops. A private copy in each tool is how
# two tools come to disagree about what fill-rule="evenodd" means.
SVG = G.SVG
SHAPES = G.SHAPES
norm, paint, prop, evenodd, polys, to_d = (
    G.norm, G.paint, G.prop, G.evenodd, G.polys, G.to_d)
ET.register_namespace("", SVG)

#: Raster resolution for the width measurement, px per mm. `thickness_map` steps
#: radii by 1 px, so width quantises to 2 px — 0.125 mm here. That is fine
#: against a 1.0-1.2 mm decision and keeps the `--to-min` search, which measures
#: several times, to a few seconds per colour.
#:
#: **This measures pixel-CENTRE membership, and the other tools in this
#: directory do not.** `svg_subpath_filter` and `svg_dark_invert` rasterise with
#: `PIL.ImageDraw.polygon`, whose fill is boundary-inclusive, so it sets one
#: extra pixel on each side of a shape. Measured on axis-aligned bars of known
#: width at 10, 16, 24, 32 and 40 px/mm, that is a flat **+2 px** overstatement
#: at every resolution — +0.2 mm at the 10 px/mm those tools use, against a
#: 1.0-1.2 mm limit. `shapely.contains_xy` on pixel centres is the unbiased
#: convention and reports 1.000, 2.000 and 3.000 mm for bars of exactly that
#: width; discs come back one quantisation step low (4 mm reads 3.875), which is
#: the 2 px radius step and is symmetric.
#:
#: Not retro-fitted to the other two here, deliberately: every width figure
#: quoted in CLAUDE.md and in this repo's notes came out of the old convention
#: and would have to be restated in the same change. See the note in
#: `embroidery_tools.measure`.
PPM = 16.0

#: Pixels of margin around a measured shape, so the distance transform inside
#: `thickness_map` never runs into the array edge. Two would do; four is free.
PAD_PX = 4

#: Segments per quarter circle in a round join. Shapely's own default is 8; the
#: resulting chord error at 0.3 mm offset is under 1.5 um, far below anything
#: this machine resolves.
QUAD_SEGS = 8

JOINS = {"round": 1, "mitre": 2, "bevel": 3}


def topology(geom) -> tuple[int, int]:
    """(shells, holes). The two counts a merge or a closed hole shows up in."""
    ps = polys(geom)
    return len(ps), sum(len(p.interiors) for p in ps)


ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--artwork-mm", type=float, required=True,
                help="width the drawing will be stitched at; offsets are in mm of that")
ap.add_argument("--grow", action="append", default=[], metavar="RRGGBB=MM",
                help="offset that colour's fills outward by MM. Negative shrinks. "
                     "Repeatable.")
ap.add_argument("--to-min", action="append", default=[], metavar="RRGGBB=MM",
                help="grow that colour by the SMALLEST amount that brings its "
                     "local width up to MM over all but --tolerate percent of "
                     "its ink area. Repeatable.")
ap.add_argument("--tolerate", type=float, default=5.0, metavar="PCT",
                help="percent of a colour's ink area allowed to stay below the "
                     "--to-min target (default 5). Artwork has corners and tips, "
                     "and demanding 100%% would chase them forever.")
ap.add_argument("--join", choices=sorted(JOINS), default="round",
                help="corner treatment when growing (default round). Mitre keeps "
                     "sharp corners sharp but spikes them outward at acute "
                     "angles; round is what Ink/Stitch's own offsets default to.")
ap.add_argument("--mitre-limit", type=float, default=5.0)
ap.add_argument("--curve-samples", type=int, default=24, metavar="N",
                help="polyline segments per curve segment when flattening "
                     "(default 24). Offsetting rewrites geometry, so curves "
                     "cannot survive it; this sets how finely they are "
                     "approximated first.")
ap.add_argument("--ppm", type=float, default=PPM, metavar="PX",
                help=f"measurement raster resolution (default {PPM:g} px/mm)")
ap.add_argument("--allow-topology-change", action="store_true",
                help="proceed when shapes merge or holes close. Say so "
                     "deliberately: neither is visible in a render at design "
                     "size and neither is visible to validate.")
ap.add_argument("--report", action="store_true",
                help="print each colour's width distribution and topology, then "
                     "exit without writing")
a = ap.parse_args()

if not (a.grow or a.to_min or a.report):
    raise SystemExit("nothing to do: pass --grow, --to-min, or --report")

rules: dict[str, float] = {}
for spec in a.grow:
    c, _, v = spec.partition("=")
    if not v:
        raise SystemExit(f"--grow {spec!r} is not RRGGBB=MM")
    rules[norm(c)] = float(v)
targets: dict[str, float] = {}
for spec in a.to_min:
    c, _, v = spec.partition("=")
    if not v:
        raise SystemExit(f"--to-min {spec!r} is not RRGGBB=MM")
    key = norm(c)
    if key in rules:
        raise SystemExit(f"#{key} has both --grow and --to-min. They set the "
                         "same number two different ways; pick one.")
    targets[key] = float(v)

tree = ET.parse(a.src)
root = tree.getroot()

shapes: list[tuple[ET.Element, list[ET.Element]]] = []


def walk(node: ET.Element, ancestors: list[ET.Element]) -> None:
    for el in list(node):
        tag = el.tag.split("}")[-1]
        if tag == "g":
            walk(el, [*ancestors, el])
        elif tag in SHAPES:
            shapes.append((el, [*ancestors, node]))


walk(root, [root])
if not shapes:
    raise SystemExit("no filled shapes found")

# No artwork in this repo carries a transform, and honouring one properly means
# offsetting in the transformed frame and inverting to write back — a non-uniform
# scale makes "0.3 mm" mean two different distances. Refused rather than ignored:
# geometry landing in the wrong place still renders as a plausible drawing and
# still stitches, which is the vtracer registration bug all over again.
skewed = [el for el, anc in shapes if any(n.get("transform") for n in (el, *anc))]
if skewed:
    raise SystemExit(
        f"{len(skewed)} shape(s) carry a transform. This tool offsets in the "
        "document's own coordinates and cannot honour one. Flatten them first: "
        "inkscape --actions='select-all:all;object-to-path;export-overwrite;export-do'")

# Geometry per element, grouped by fill colour. One path per colour is what the
# prepared files in art/prepared carry, but nothing here depends on it.
by_colour: dict[str, list[tuple[ET.Element, object]]] = {}
curved = 0
stroke_only = 0
for el, anc in shapes:
    colour = paint(prop(el, "fill", anc))
    if colour is None:
        stroke_only += 1
        continue
    subs = svgpath.parse_shape(el.tag.split("}")[-1], el.attrib, samples=a.curve_samples)
    if not subs:
        continue
    curved += sum(1 for s in subs if s["curved"])
    geom = evenodd([s["points"] for s in subs])
    if geom is None or geom.is_empty:
        continue
    by_colour.setdefault(colour, []).append((el, geom))

if not by_colour:
    raise SystemExit("no filled geometry found")
if stroke_only:
    print(f"  {stroke_only} shape(s) have no fill and were left alone — this "
          "offsets fills. Use svg_stroke.py to change a stroke's width.")

for want in (*rules, *targets):
    if want not in by_colour:
        raise SystemExit(f"#{want}: nothing in the document is filled #{want}. "
                         "Present: " + ", ".join("#" + c for c in sorted(by_colour)))

allpts = [pt for entries in by_colour.values() for _, g in entries
          for p in polys(g) for pt in p.exterior.coords]
minx = min(p[0] for p in allpts)
maxx = max(p[0] for p in allpts)
upm = (maxx - minx) / a.artwork_mm              # user units per mm
QUANTUM_MM = 2.0 / a.ppm     # thickness_map steps radii by 1 px; width by 2
print(f"  drawing {maxx - minx:.0f} units wide -> {a.artwork_mm:g} mm  ({upm:.3f} units/mm)")
if curved:
    print(f"  {curved} curved subpath(s) flattened at {a.curve_samples} "
          "segments per curve; offsetting rewrites geometry either way")

def rasterise(geom) -> np.ndarray:
    """Bool mask of `geom`: one sample at the centre of each pixel.

    Sized to the geometry's own bounds rather than the whole drawing's, because
    local thickness is local — a colour occupying a corner of the design costs
    a corner-sized grid. Holes and islands-inside-holes need no special handling
    at all: `contains` already answers the even-odd question the geometry was
    built to encode.
    """
    if geom is None or geom.is_empty:
        return np.zeros((1, 1), bool)
    gx0, gy0, gx1, gy1 = geom.bounds
    W = int((gx1 - gx0) / upm * a.ppm) + 2 * PAD_PX + 1
    H = int((gy1 - gy0) / upm * a.ppm) + 2 * PAD_PX + 1
    xs = gx0 + (np.arange(W) + 0.5 - PAD_PX) * upm / a.ppm
    ys = gy0 + (np.arange(H) + 0.5 - PAD_PX) * upm / a.ppm
    gxx, gyy = np.meshgrid(xs, ys)
    shapely.prepare(geom)
    return shapely.contains_xy(geom, gxx, gyy)


def offset(geom, delta_mm: float):
    if delta_mm == 0:
        return geom
    return geom.buffer(delta_mm * upm, quad_segs=QUAD_SEGS,
                       join_style=JOINS[a.join], mitre_limit=a.mitre_limit)


MIN_W = prof.design_limit("min_satin_width_mm", 1.0)
SAFE_W = prof.design_limit("safe_satin_width_mm", 1.2)


def stats(geom, cap_mm: float) -> dict:
    """Area, topology, and the width figures — distribution and thin fractions.

    The two "under" columns come from `frac_below_mm` rather than from counting
    the distribution below a threshold. They are the numbers decisions get made
    on, and thresholding an exact radius beats thresholding a distribution that
    has already been rounded to a whole-pixel radius.
    """
    m = rasterise(geom)
    w = widths_mm(m, a.ppm, max_mm=cap_mm) if m.any() else np.zeros(0)
    shells, holes = topology(geom)
    area = sum(p.area for p in polys(geom)) / upm ** 2
    if not w.size:
        return dict(area=area, shells=shells, holes=holes, p5=0.0, med=0.0,
                    under_min=0.0, under_safe=0.0)
    return dict(area=area, shells=shells, holes=holes,
                p5=float(np.percentile(w, 5)), med=float(np.median(w)),
                under_min=frac_below_mm(m, a.ppm, MIN_W) * 100,
                under_safe=frac_below_mm(m, a.ppm, SAFE_W) * 100)


if a.report:
    print(f"\n  measured at {a.ppm:g} px/mm (widths quantise to {QUANTUM_MM:g} mm); "
          "area-weighted local thickness")
    print("    %-9s %9s %7s %6s %8s %8s %9s %9s"
          % ("colour", "area mm2", "shells", "holes", "p5 mm", "med mm",
             f"<{MIN_W:g}mm", f"<{SAFE_W:g}mm"))
    for c in sorted(by_colour):
        g = unary_union([g for _, g in by_colour[c]])
        s = stats(g, cap_mm=max(3.0, SAFE_W * 2))
        print("    #%-8s %9.1f %7d %6d %8.2f %8.2f %8.0f%% %8.0f%%"
              % (c, s["area"], s["shells"], s["holes"], s["p5"], s["med"],
                 s["under_min"], s["under_safe"]))
    print(f"\n  min satin width {MIN_W:g} mm, safe {SAFE_W:g} mm "
          "(design_limits, reference/machine-profile.json)")
    sys.exit(0)


def solve(colour: str, target_mm: float) -> float:
    """Smallest grow bringing all but `--tolerate` percent of the ink to target.

    A bar grows 2*delta in local thickness, so (target - width)/2 is the right
    first guess; it is only a guess because corners, tips and merging features
    do not follow it. Bracket outward from there, then bisect. Measured every
    step rather than trusted — the estimate is off by a factor of two on a shape
    that is mostly corner.
    """
    geom = unary_union([g for _, g in by_colour[colour]])

    def short(delta: float) -> float:
        """Percent of ink area still under target after growing by `delta`.

        `frac_below_mm`, not a percentile of `widths_mm`: it thresholds at
        exactly target/2 pixels instead of at the nearest whole-pixel radius, so
        the search is not chasing the measurement's own 2 px quantisation. It is
        also two distance transforms rather than a sweep, which is what makes a
        dozen evaluations bearable.
        """
        m = rasterise(offset(geom, delta))
        return frac_below_mm(m, a.ppm, target_mm) * 100

    at0 = short(0.0)
    if at0 <= a.tolerate:
        print(f"  #{colour} already clears {target_mm:g} mm "
              f"({at0:.0f}% under, tolerating {a.tolerate:g}%) — no growth needed")
        return 0.0

    # Saturated just past the target: only "< target" is ever asked of this, and
    # every extra radius in the sweep is another distance transform.
    w0 = widths_mm(rasterise(geom), a.ppm, max_mm=target_mm + 1.0)
    lo, hi = 0.0, max(0.05, (target_mm - float(np.percentile(w0, a.tolerate))) / 2.0)
    for _ in range(6):
        if short(hi) <= a.tolerate:
            break
        lo, hi = hi, hi * 2
    else:
        raise SystemExit(
            f"--to-min {colour}={target_mm:g}: growing to {hi:g} mm still leaves "
            f"{short(hi):.0f}% of the ink under target, against a {a.tolerate:g}% "
            "tolerance. The thin area is not a thin edge, it is most of the "
            "shape — thicken the artwork, or drop the detail with "
            "svg_subpath_filter --drop-thin.")
    for _ in range(6):                       # 6 halvings of the bracket: ~1.6%
        mid = (lo + hi) / 2
        if short(mid) <= a.tolerate:
            hi = mid
        else:
            lo = mid
    # Growing by d adds exactly 2d of local width to a bar — geometry, not
    # measurement. The threshold behind the search is exact too (`frac_below_mm`
    # erodes by target/2 pixels, whatever that is fractionally), so the answer is
    # limited by the raster's own 1 px sampling and not by the 2 px width
    # quantisation that the reported median and p5 columns carry.
    print(f"  #{colour} --to-min {target_mm:g} mm -> grow {hi:.2f} mm, "
          f"adding {2 * hi:.2f} mm of width "
          f"({at0:.0f}% of ink was under target, now {short(hi):.0f}%)")
    return hi


for colour, target in targets.items():
    rules[colour] = solve(colour, target)

cap = max(3.0, SAFE_W * 2)
changed = False
problems: list[str] = []
for colour, delta in rules.items():
    entries = by_colour[colour]
    before = unary_union([g for _, g in entries])
    b = stats(before, cap)
    if delta == 0:
        continue

    grown = [(el, offset(g, delta)) for el, g in entries]
    after = unary_union([g for _, g in grown])
    s = stats(after, cap)

    verb = "grew" if delta > 0 else "shrank"
    print(f"  #{colour} {verb} {abs(delta):.2f} mm: "
          f"{b['area']:.0f} -> {s['area']:.0f} mm2, "
          f"median width {b['med']:.2f} -> {s['med']:.2f} mm, "
          f"under {SAFE_W:g} mm {b['under_safe']:.0f}% -> {s['under_safe']:.0f}%")

    if (s["shells"], s["holes"]) != (b["shells"], b["holes"]):
        what = []
        if s["shells"] != b["shells"]:
            what.append(f"{b['shells']} shape(s) -> {s['shells']}")
        if s["holes"] != b["holes"]:
            what.append(f"{b['holes']} hole(s) -> {s['holes']}")
        msg = (f"#{colour} changed topology: " + ", ".join(what) +
               ". Features merged or holes closed — invisible in a render at "
               "design size and invisible to validate, because the stitches are "
               "good stitches of the wrong shape.")
        if a.allow_topology_change:
            print(f"  WARNING  {msg}", file=sys.stderr)
        else:
            problems.append(msg)

    for el, g in grown:
        d = to_d(g)
        if not d:
            problems.append(f"#{colour} offset to nothing; shrinking too far?")
            continue
        # An offset ellipse is no longer an ellipse and an offset polygon is no
        # longer a polygon — the result is an arbitrary region with holes, and
        # only `d` can carry that. Retag, and drop the geometry attributes that
        # now describe something else, or a renderer draws the old circle.
        if el.tag.split("}")[-1] != "path":
            el.tag = f"{{{SVG}}}path"
            for attr in ("points", "x", "y", "width", "height",
                         "cx", "cy", "r", "rx", "ry"):
                el.attrib.pop(attr, None)
        el.set("d", d)
        el.set("fill-rule", "evenodd")
    changed = True

if problems:
    raise SystemExit("\n".join("  ERROR  " + p for p in problems) +
                     "\n  Nothing was written. Re-run with "
                     "--allow-topology-change if the merge is what you want.")

if not changed:
    print("  no colour needed changing; source copied unaltered")

# svg_prep sizes the document from the DRAWING's bounding box, so growing a shape
# that touches the edge makes the whole design scale down to fit the same
# --artwork-mm. The effect is small but it is real, and it means a feature grown
# to exactly the minimum lands just under it.
newpts = [pt for entries in by_colour.values() for el, _ in entries
          for s in (svgpath.parse_shape(el.tag.split("}")[-1], el.attrib, samples=4) or [])
          for pt in s["points"]]
nw = max(p[0] for p in newpts) - min(p[0] for p in newpts)
drift = nw / (maxx - minx) - 1.0
if abs(drift) > 0.0005:
    print(f"  NOTE     the drawing's bounding box changed by {drift * 100:+.2f}%. "
          f"svg_prep scales the drawing to --artwork-mm, so every width comes out "
          f"{drift * 100:+.2f}% off nominal. Grow a little past the limit, and "
          f"trust `measured` in the manifest.")

tree.write(a.dst, encoding="utf-8", xml_declaration=True)
ET.parse(a.dst)      # fail loudly rather than handing a broken document downstream
print(f"  -> {a.dst}")
