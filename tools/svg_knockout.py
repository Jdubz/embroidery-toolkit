"""Punch one colour's shapes out of the fill beneath them, keeping them stitchable.

SVG is a painter's model: a shape drawn later hides what is under it, and the
artwork relies on that. Stitching has no such model — every layer is sewn, and
`svg_prep` orders layers **light to dark**, not in document order. When those two
disagree the lower colour is stitched *last* and covers the upper one.

That is not hypothetical. `LemonCat_embroidery_solid_yellow.svg` draws a
full-silhouette yellow body and then two white eyes on top. Luminance order
stitches white first and the yellow body straight over it, so the eyes come out
yellow. `validate` reported nothing, `coverage` reported 100% — the yellow really
does cover the artwork — and only `stitch render` showed it.

`svg_prep --skip` already solves the geometry half of this: to get bare fabric a
shape has to become a **hole** in the fill below, one path carrying both outlines
with `fill-rule="evenodd"`. But `--skip` also drops the shape, which is the
opposite of what is wanted here. This does the same knockout and leaves the shape
in place to be stitched in its own colour.

Pure string concatenation of `d` attributes, exactly as `svg_prep` does it — no
boolean geometry, so curves survive untouched.

    svg_knockout.py in.svg out.svg --knock FFFFFF=FFD400

Reach for it whenever two fills overlap and the upper one is the lighter: check
the stitch order `svg_prep` prints, and if a colour is listed before something
that sits under it in the artwork, it needs knocking out.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from embroidery_tools import svgpath  # noqa: E402

SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)
SHAPES = ("path", "rect", "circle", "ellipse", "polygon", "polyline", "line")


def norm(colour: str | None) -> str | None:
    if not colour:
        return None
    c = colour.strip()
    if c.lower() in ("none", "transparent"):
        return None
    return c.lstrip("#").upper()


def prop(el: ET.Element, name: str, ancestors: list[ET.Element]) -> str | None:
    """Effective paint: the element's own attribute, else the nearest ancestor's.

    Mirrors svg_prep.prop — a fill declared on a <g> is inherited, and reading
    only the element's own attribute would miss it.
    """
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


def walk(node: ET.Element, ancestors: list[ET.Element], out: list):
    for el in list(node):
        tag = el.tag.split("}")[-1]
        if tag == "g":
            walk(el, [*ancestors, el], out)
        elif tag in SHAPES:
            out.append((el, [*ancestors, node]))


def inside(pt, subs) -> bool:
    """Even-odd point-in-path across every subpath of the host."""
    x, y = pt
    n = 0
    for s in subs:
        p = s["points"]
        for i in range(len(p)):
            x0, y0 = p[i]
            x1, y1 = p[(i + 1) % len(p)]
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                n += 1
    return n % 2 == 1


ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--knock", action="append", default=[], required=True,
                metavar="PUNCH=INTO",
                help="cut every PUNCH-coloured fill out of the INTO-coloured "
                     "fill as an even-odd hole, and keep PUNCH stitchable")
a = ap.parse_args()

tree = ET.parse(a.src)
root = tree.getroot()
shapes: list = []
walk(root, [root], shapes)

fills = [(norm(prop(el, "fill", anc)), el) for el, anc in shapes]

for spec in a.knock:
    punch_c, _, into_c = spec.partition("=")
    punch_c, into_c = norm(punch_c), norm(into_c)
    if not punch_c or not into_c:
        raise SystemExit(f"--knock {spec!r} is not PUNCH=INTO with two hex colours")

    punches = [el for c, el in fills
               if c == punch_c and el.tag.split("}")[-1] == "path" and el.get("d")]
    if not punches:
        raise SystemExit(f"--knock {spec}: no #{punch_c} fill path to punch with. "
                         "A knockout that silently does nothing is how the wrong "
                         "colour ends up on fabric.")

    host = next((el for c, el in fills
                 if c == into_c and el.tag.split("}")[-1] == "path" and el.get("d")), None)
    if host is None:
        raise SystemExit(f"--knock {spec}: no #{into_c} fill path to punch into")

    # Registration, not validity: concatenating the wrong geometry still parses
    # and still renders. If a punch does not actually lie inside its host it is
    # not a hole, and the result is an extra outline nobody asked for.
    host_subs = svgpath.parse_path(host.get("d"))
    for el in punches:
        subs = svgpath.parse_path(el.get("d"))
        pts = [p for s in subs for p in s["points"]]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        if not inside((cx, cy), host_subs):
            raise SystemExit(
                f"--knock {spec}: #{punch_c} shape {el.get('id') or '(no id)'} "
                f"centred at {cx:.0f},{cy:.0f} is not inside the #{into_c} fill. "
                "Nothing would be knocked out there.")

    holes = " ".join(el.get("d").strip() for el in punches)
    host.set("d", f"{host.get('d').strip()} {holes}")
    host.set("fill-rule", "evenodd")
    print(f"  knocked {len(punches)} x #{punch_c} out of #{into_c} — "
          f"#{punch_c} now stitches onto bare fabric, not over #{into_c}")

tree.write(a.dst, encoding="utf-8", xml_declaration=True)
ET.parse(a.dst)      # fail loudly rather than handing a broken document downstream
print(f"  -> {a.dst}")
