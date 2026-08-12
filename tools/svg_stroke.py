"""Put a stroke of a declared width on a colour's shapes, so it stitches as satin.

`svg_prep` splits every shape into a fill operation and a stroke operation, and
hands the stroke to Ink/Stitch's `stroke_to_satin` at the width the SVG declares.
So a satin keyline around a shape is not a digitizing setting — it is a
`stroke-width` on the artwork, and there was no tool here that could add one.

Two jobs, and they are different enough to name separately:

* **A keyline in another colour.** `--stroke 73B236=1.2:000000` outlines the
  green with black satin. It costs a colour change, which on a single-needle
  machine is a manual rethread, so the tool says so and checks the total against
  `design_limits.safe_colour_count`.
* **Reading weight in the shape's own colour.** `--stroke 73B236=1.2` strokes
  green with green. `svg_prep` groups operations by colour, so this adds no stop
  and no rethread — it stitches in the same pass as the fill. It is the cheapest
  way to firm up a shape's edge, and unlike `svg_offset` it leaves the fill
  geometry alone.

Reach for `svg_offset` instead when the *shape* is too thin. A stroke thickens
the edge; it cannot rescue a 0.6 mm limb, because the satin still has to be at
least `min_satin_width_mm` wide and it is being asked to sit on a 0.6 mm path.

**A stroke below the machine's satin minimum is refused.** Ink/Stitch will
happily emit a 0.5 mm satin column and the machine will happily sew a comb of
loose thread. `min_satin_width_mm` is the hard floor, `safe_satin_width_mm` the
one to design to; below the safe figure this warns and keeps going, below the
minimum it stops.

**A stroke makes the drawing bigger, and `svg_prep` scales that back down.**
Verified against Inkscape 1.4.4: `--query-width` returns the *visual* bounding
box, so a 10-unit shape with a 2-unit stroke measures 12. `svg_prep` sizes the
document so that measurement lands on `--artwork-mm`, which means adding a
1.2 mm stroke to an 87 mm design shrinks everything by ~1.4% and the stroke
itself arrives at 1.18 mm — just under the 1.2 mm it was asked for. The exact
figure is computed here from the shapes actually being stroked, and reported.

Strokes are written as presentation attributes with any conflicting `style`
declaration removed. That is not tidiness: CSS in `style` beats a presentation
attribute in a real renderer, but `svg_prep.prop` reads the attribute first, so
leaving both in place makes the render and the stitch file disagree about a
colour — and the render is the thing being trusted.

    svg_stroke.py in.svg out.svg --artwork-mm 87 --stroke 73B236=1.2:000000
    svg_stroke.py in.svg out.svg --artwork-mm 87 --clear 73B236
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embroidery_tools import profile as prof  # noqa: E402
from embroidery_tools import svgpath  # noqa: E402

SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)
PAINT = ("stroke", "stroke-width")

#: Every tag `svg_prep` will stitch. LemonCat draws ear tufts as <polygon> and
#: pupils as <ellipse>; stroking only <path> would outline part of a layer.
SHAPES = ("path", "polygon", "polyline", "rect", "circle", "ellipse")


def prop(el: ET.Element, name: str, ancestors: list[ET.Element]) -> str | None:
    """Effective paint, element first then upward — as `svg_prep.prop` resolves it."""
    for node in (el, *reversed(ancestors)):
        style = node.get("style")
        if style:
            for decl in style.split(";"):
                k, _, v = decl.partition(":")
                if k.strip() == name and v.strip():
                    return v.strip()
        v = node.get(name)
        if v:
            return v
    return None


def paint(value: str | None) -> str | None:
    if value is None:
        return "000000"                  # SVG's initial fill really is black
    if value.strip().lower() in ("none", "transparent"):
        return None
    return norm(value)


def norm(colour: str) -> str:
    c = colour.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in c):
        raise SystemExit(f"'{colour}' is not a 3- or 6-digit hex colour. "
                         "Refusing to guess — a wrong guess stitches the wrong "
                         "colour. In PowerShell, quote it: '000000', not 000000.")
    return c.upper()


def drop_style(el: ET.Element, names: tuple[str, ...]) -> None:
    """Remove declarations from `style` so the attribute is the only source.

    `style` wins in a renderer and loses in `svg_prep.prop`. Leaving a stale
    `stroke:none` behind therefore produces a file that previews one way and
    stitches another, which is the class of bug this repo keeps paying for.
    """
    style = el.get("style")
    if not style:
        return
    kept = [d for d in style.split(";")
            if d.strip() and d.partition(":")[0].strip() not in names]
    if kept:
        el.set("style", ";".join(kept))
    else:
        el.attrib.pop("style", None)


ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--artwork-mm", type=float, required=True,
                help="width the drawing will be stitched at; stroke widths are mm of that")
ap.add_argument("--stroke", action="append", default=[], metavar="FILL=MM[:COLOUR]",
                help="stroke every #FILL shape at MM millimetres, in COLOUR if "
                     "given or in #FILL itself otherwise. Repeatable.")
ap.add_argument("--clear", action="append", default=[], metavar="FILL",
                help="remove any stroke from every #FILL shape. Repeatable.")
ap.add_argument("--allow-thin", action="store_true",
                help="write a stroke narrower than the machine's satin minimum. "
                     "It will stitch as a sparse comb; there is no setting that "
                     "makes a sub-minimum satin hold.")
a = ap.parse_args()

if not (a.stroke or a.clear):
    raise SystemExit("nothing to do: pass --stroke or --clear")

MIN_W = prof.design_limit("min_satin_width_mm", 1.0)
SAFE_W = prof.design_limit("safe_satin_width_mm", 1.2)
MAX_COLOURS = prof.design_limit("safe_colour_count", 4)

rules: dict[str, tuple[float, str]] = {}
for spec in a.stroke:
    fill, _, rest = spec.partition("=")
    if not rest:
        raise SystemExit(f"--stroke {spec!r} is not FILL=MM or FILL=MM:COLOUR")
    width, _, colour = rest.partition(":")
    key = norm(fill)
    rules[key] = (float(width), norm(colour) if colour else key)
clears = {norm(c) for c in a.clear}
if rules.keys() & clears:
    raise SystemExit("the same colour is in both --stroke and --clear")

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
    raise SystemExit("no shapes found")

# A transform scales the stroke with the shape, so a width written here in user
# units would arrive as something else. Refused rather than silently wrong.
skewed = [el for el, anc in shapes if any(n.get("transform") for n in (el, *anc))]
if skewed:
    raise SystemExit(
        f"{len(skewed)} shape(s) carry a transform, which scales stroke-width "
        "along with the geometry. Flatten them first: inkscape "
        "--actions='select-all:all;object-to-path;export-overwrite;export-do'")

by_colour: dict[str, list[ET.Element]] = {}
bounds: dict[str, tuple[float, float, float, float]] = {}
for p, anc in shapes:
    c = paint(prop(p, "fill", anc))
    if c is None:
        continue
    by_colour.setdefault(c, []).append(p)
    subs = svgpath.parse_shape(p.tag.split("}")[-1], p.attrib) or []
    pts = [pt for s in subs for pt in s["points"]]
    if not pts:
        continue
    x0, x1 = min(q[0] for q in pts), max(q[0] for q in pts)
    y0, y1 = min(q[1] for q in pts), max(q[1] for q in pts)
    if c in bounds:
        b = bounds[c]
        bounds[c] = (min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1))
    else:
        bounds[c] = (x0, y0, x1, y1)

for want in (*rules, *clears):
    if want not in by_colour:
        raise SystemExit(f"#{want}: nothing in the document is filled #{want}. "
                         "Present: " + ", ".join("#" + c for c in sorted(by_colour)))

minx = min(b[0] for b in bounds.values())
maxx = max(b[2] for b in bounds.values())
upm = (maxx - minx) / a.artwork_mm
print(f"  drawing {maxx - minx:.0f} units wide -> {a.artwork_mm:g} mm  ({upm:.3f} units/mm)")

for colour, (w_mm, stroke_c) in rules.items():
    if w_mm < MIN_W and not a.allow_thin:
        raise SystemExit(
            f"--stroke {colour}={w_mm:g}: below the {MIN_W:g} mm satin minimum "
            f"(design_limits.min_satin_width_mm). A column this narrow lays "
            f"thread that does not meet, and no spacing or underlay setting "
            f"recovers it. Use --allow-thin to override, or svg_offset to "
            f"thicken the shape instead of outlining it.")
    if w_mm < SAFE_W:
        print(f"  WARNING  #{colour} stroke {w_mm:g} mm is under the "
              f"{SAFE_W:g} mm safe width; it will stitch, but check the render.",
              file=sys.stderr)

for colour in clears:
    n = 0
    for el in by_colour[colour]:
        drop_style(el, PAINT)
        for attr in PAINT:
            if el.attrib.pop(attr, None) is not None:
                n += 1
        el.set("stroke", "none")
    print(f"  #{colour}: stroke removed from {len(by_colour[colour])} path(s)")

existing = set(by_colour)
for colour, (w_mm, stroke_c) in rules.items():
    for el in by_colour[colour]:
        drop_style(el, PAINT)
        el.set("stroke", f"#{stroke_c}")
        # A bare number: svg_prep does float() on this, so "1.2px" raises there
        # rather than here, which is the wrong place to find out.
        el.set("stroke-width", f"{w_mm * upm:.4f}".rstrip("0").rstrip("."))
    same = " (same colour as its fill — stitches in that colour's pass, " \
           "no extra stop)" if stroke_c == colour else ""
    print(f"  #{colour}: stroked {w_mm:g} mm in #{stroke_c}, "
          f"{len(by_colour[colour])} path(s){same}")
    if stroke_c not in existing:
        print(f"  NOTE     #{stroke_c} is a new colour: one more stop and one "
              f"more manual rethread on a single-needle machine.")
        existing.add(stroke_c)

if len(existing) > MAX_COLOURS:
    print(f"  WARNING  {len(existing)} colours now, against a comfortable "
          f"{MAX_COLOURS} (design_limits.safe_colour_count). Every change is a "
          f"rethread by hand.", file=sys.stderr)

# What the stroke will actually measure once svg_prep has scaled the document.
# Inkscape reports the VISUAL bounding box, so half the stroke on each side of
# whichever shapes carry it joins the drawing's width, and everything shrinks to
# put that back inside --artwork-mm.
vis_min, vis_max = minx, maxx
for colour, (w_mm, _) in rules.items():
    b = bounds[colour]
    vis_min = min(vis_min, b[0] - w_mm * upm / 2)
    vis_max = max(vis_max, b[2] + w_mm * upm / 2)
scale = (maxx - minx) / (vis_max - vis_min)
if scale < 0.9995:
    print(f"  NOTE     the visual bounding box grows {(1 / scale - 1) * 100:.2f}% "
          f"once stroked, and svg_prep scales the drawing back to "
          f"{a.artwork_mm:g} mm — so:")
    for colour, (w_mm, _) in rules.items():
        eff = w_mm * scale
        flag = ""
        if eff < MIN_W:
            flag = f"  <- now under the {MIN_W:g} mm minimum"
        elif eff < SAFE_W <= w_mm:
            flag = f"  <- now under the {SAFE_W:g} mm safe width"
        print(f"             #{colour} {w_mm:g} mm arrives as {eff:.2f} mm{flag}")

tree.write(a.dst, encoding="utf-8", xml_declaration=True)
ET.parse(a.dst)      # fail loudly rather than handing a broken document downstream
print(f"  -> {a.dst}")
