"""Shared vector geometry for the SVG tailoring tools.

`svgpath` turns path data into points. This turns those points into *regions* —
even-odd areas, boolean results, and path data again — which is what any tool
that rewrites artwork rather than merely measuring it needs.

It exists because `svg_offset` and `svgops` both need the same six operations,
and a private copy in each is how two tools come to disagree about what
`fill-rule="evenodd"` means. Everything here is exact vector work on
Shapely geometries; nothing rasterises. Rasterising is for *measuring* (see
`measure`), never for producing geometry that will be stitched.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import shapely
from shapely.geometry import MultiPolygon, Polygon

from . import svgpath

SVG = "http://www.w3.org/2000/svg"

#: Every tag `svg_prep` will stitch the fill of. Walking only <path> is a
#: silent-partial-application bug: LemonCat draws ear tufts as <polygon> and
#: pupils as <ellipse>, both filled #000000, so a path-only tool reports that
#: layer smaller than it is and rewrites part of it.
SHAPES = ("path", "polygon", "polyline", "rect", "circle", "ellipse")


def norm(colour: str) -> str:
    c = colour.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in c):
        raise SystemExit(f"'{colour}' is not a 3- or 6-digit hex colour. "
                         "Refusing to guess — a wrong guess rewrites the wrong "
                         "layer. In PowerShell, quote it: '000000', not 000000.")
    return c.upper()


def paint(value: str | None, initial: str | None = "000000") -> str | None:
    """Normalise a paint value; None when nothing is painted.

    `initial` is what an ABSENT declaration means, and it differs by property:
    SVG's initial `fill` is black but its initial `stroke` is `none`. Defaulting
    both to black gives every unstroked element a phantom hairline stroke —
    which on Muffy invented 22 extra cloth pockets and 27 extra ink elements out
    of nothing. Always pass `initial=None` when resolving a stroke.
    """
    if value is None:
        return initial
    if value.strip().lower() in ("none", "transparent"):
        return None
    return norm(value)


def prop(el: ET.Element, name: str, ancestors: list[ET.Element]) -> str | None:
    """Effective paint: the element's own declaration, else the nearest ancestor's.

    Same resolution order as `svg_prep.prop`. A fill set once on a wrapping <g>
    is inherited by everything inside it, and reading the element alone finds no
    fill at all — which would silently default a whole group to black.
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


def shapes_of(root: ET.Element) -> list[tuple[ET.Element, list[ET.Element]]]:
    """Every fillable shape in the document, with its ancestor chain."""
    out: list[tuple[ET.Element, list[ET.Element]]] = []

    def walk(node: ET.Element, ancestors: list[ET.Element]) -> None:
        for el in list(node):
            tag = el.tag.split("}")[-1]
            if tag == "g":
                walk(el, [*ancestors, el])
            elif tag in SHAPES:
                out.append((el, [*ancestors, node]))

    walk(root, [root])
    return out


def transformed(shapes) -> list[ET.Element]:
    """Shapes carrying a transform, on themselves or any ancestor.

    Callers refuse rather than ignore these. Geometry in the wrong place still
    renders as a plausible drawing and still stitches — the vtracer
    registration bug — so a transform silently dropped is invisible until it is
    on fabric.
    """
    return [el for el, anc in shapes if any(n.get("transform") for n in (el, *anc))]


def evenodd(rings: list[list[tuple[float, float]]]):
    """Fold rings with symmetric difference — precisely `fill-rule="evenodd"`.

    Nesting depth is never computed, and does not need to be: XOR gives holes,
    islands inside holes, and holes inside those islands the same treatment.
    That is the rule `svg_dark_invert` had to learn the hard way, when emitting
    a depth-3 subpath XORed it back out of the design.
    """
    geom = None
    for ring in rings:
        if len(ring) < 3:
            continue
        p = Polygon(ring)
        if not p.is_valid:
            # A self-intersecting ring is not a malformed file — a figure-eight
            # outline is legal SVG. make_valid resolves it into the region a
            # renderer would paint, instead of raising from inside a boolean op.
            p = shapely.make_valid(p)
        geom = p if geom is None else geom.symmetric_difference(p)
    return geom


def geometry_of(el: ET.Element, samples: int = 16):
    """The even-odd region a single shape element paints."""
    subs = svgpath.parse_shape(el.tag.split("}")[-1], el.attrib, samples=samples) or []
    return evenodd([s["points"] for s in subs])


def polys(geom) -> list[Polygon]:
    """Every polygon in a geometry, dropping degenerate lines and points.

    `make_valid` and `symmetric_difference` can return a GeometryCollection
    carrying stray lines where two rings touch at a single vertex. Those enclose
    no area and stitch as nothing.
    """
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]


def fmt(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0", "-") else s


def to_d(geom) -> str:
    """Path data for `fill-rule="evenodd"`: every ring as its own closed subpath."""
    parts = []
    for p in polys(geom):
        for ring in (p.exterior, *p.interiors):
            pts = list(ring.coords)
            if len(pts) > 1 and pts[0] == pts[-1]:
                pts = pts[:-1]          # Z closes it; a repeat is a zero-length edge
            if len(pts) < 3:
                continue
            parts.append("M " + " L ".join(f"{fmt(x)} {fmt(y)}" for x, y in pts) + " Z")
    return " ".join(parts)
