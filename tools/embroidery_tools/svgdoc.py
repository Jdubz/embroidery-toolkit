"""One document model shared by every SVG editing operation.

Seven tools in `tools/` each parse an SVG their own way, and each carries its own
copy of the walk, the paint resolution and the even-odd folding. That is why
`svg_ground_invert` had to be extended twice — once to see strokes at all, once
to cut dropped ink out of what lay under it — and why the fix for one asset kept
being wrong for the next. There was no shared notion of "what is painted here".

This is that notion. A document is a flat list of **paint regions**:

    (element, kind, colour, geometry)

where `kind` is `fill` or `stroke`. One element contributes several regions,
which is exactly how LemonCat's yellow body carries a black outline. A stroke is
turned into a region by buffering its polyline by half its declared width — the
same area `stroke_to_satin` would cover — so a tool asking "what is black here?"
gets the whole drawing rather than the 25% of it that happens to be filled.

**Stroke geometry is read-only.** A stroke can be recoloured, re-widthed or
dropped, but it cannot be reshaped in place, because there is no way to express
an arbitrary region as a stroke. Operations that reshape work on fills. Said out
loud because it is a real limit of the model and not an oversight.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from shapely.geometry import LineString
from shapely.ops import unary_union

from . import svggeom as G
from . import svgpath


@dataclass
class Region:
    """One painted area: an element's fill, or an element's stroke as a region."""
    el: ET.Element
    kind: str                  # "fill" | "stroke"
    colour: str                # RRGGBB
    geom: object               # shapely
    width: float | None = None  # user units, strokes only


class Doc:
    """An SVG parsed into paint regions, and writable back out again."""

    def __init__(self, tree: ET.ElementTree, artwork_mm: float, samples: int = 24):
        self.tree = tree
        self.root = tree.getroot()
        self.samples = samples
        self.artwork_mm = artwork_mm
        self.upm = None          # set once by the first rescan, then frozen
        self.rescan()

    @classmethod
    def load(cls, path, artwork_mm: float, samples: int = 24) -> "Doc":
        return cls(ET.parse(str(path)), artwork_mm, samples)

    # ------------------------------------------------------------------ #

    def rescan(self) -> None:
        """(Re)build the region list from the current XML."""
        shapes = G.shapes_of(self.root)
        if not shapes:
            raise SystemExit("no fillable shapes in this document")
        skewed = G.transformed(shapes)
        if skewed:
            raise SystemExit(
                f"{len(skewed)} shape(s) carry a transform. Every operation here "
                "works in the document's own coordinates and cannot honour one — "
                "geometry in the wrong place still renders as a plausible drawing "
                "and still stitches. Flatten first: inkscape "
                "--actions='select-all:all;object-to-path;export-overwrite;export-do'")

        self.regions: list[Region] = []
        # Elements carrying a stroke, by identity. Resolved through ancestors,
        # because LemonCat declares `stroke` once on a wrapping <g> and reading
        # the element alone finds none — which silently disabled the stroke split
        # in set_fill_geom and let an outline re-trace every cut it should not
        # have followed.
        self._stroked: set[int] = set()
        for el, anc in shapes:
            subs = svgpath.parse_shape(el.tag.split("}")[-1], el.attrib,
                                       samples=self.samples) or []
            if not subs:
                continue
            fc = G.paint(G.prop(el, "fill", anc))
            if fc:
                g = G.evenodd([s["points"] for s in subs])
                if g is not None and not g.is_empty:
                    self.regions.append(Region(el, "fill", fc, g))
            # initial=None: SVG's initial stroke is `none`, unlike fill. Defaulting
            # it to black gives every unstroked element a phantom hairline, which
            # invented 22 cloth pockets out of nothing when it was got wrong.
            sc = G.paint(G.prop(el, "stroke", anc), initial=None)
            if sc:
                self._stroked.add(id(el))
                w = float(G.prop(el, "stroke-width", anc) or 1)
                bufs = [LineString(s["points"]).buffer(w / 2.0, cap_style=1,
                                                       join_style=1)
                        for s in subs if len(s["points"]) >= 2]
                if bufs:
                    self.regions.append(Region(el, "stroke", sc,
                                               unary_union(bufs), w))
        if not self.regions:
            raise SystemExit("nothing in this document is painted")

        allg = unary_union([r.geom for r in self.regions])
        self.bounds = allg.bounds
        # The SCALE is fixed at load; only the extent is live.
        #
        # `upm` used to be recomputed here from the current bounds, which meant a
        # millimetre changed length every time an op resized the drawing. Every
        # later op in the sequence then worked in a different unit: `space-out`
        # widened a test drawing from 17.5 to 22 units and the 2.0 mm gaps it had
        # just made measured back as 1.59 mm. Nothing errors, the geometry is
        # simply wrong by whatever ratio the previous ops happened to introduce —
        # and `drop`, which shrinks the bbox, is in almost every dark-cloth
        # sequence in this repo.
        #
        # `bounds` stays live on purpose: it is the drawing's extent, positional
        # selectors are relative to it, and it genuinely moves when ink is
        # dropped. That drift is real and is the caller's to reason about. A
        # millimetre is not.
        if getattr(self, "upm", None) is None:
            x0, _, x1, _ = self.bounds
            self.upm = (x1 - x0) / self.artwork_mm      # user units per mm

    # ------------------------------------------------------------------ #

    def mm2(self, geom) -> float:
        return 0.0 if geom is None or geom.is_empty else geom.area / self.upm ** 2

    def mm(self, units: float) -> float:
        return units / self.upm

    def at(self, geom) -> str:
        """Centroid as 'x,y' in mm from the drawing's top-left."""
        c = geom.centroid
        x0, y0, _, _ = self.bounds
        return f"{(c.x - x0) / self.upm:.0f},{(c.y - y0) / self.upm:.0f}"

    def centroid_mm(self, geom) -> tuple[float, float]:
        c = geom.centroid
        x0, y0, _, _ = self.bounds
        return (c.x - x0) / self.upm, (c.y - y0) / self.upm

    def colours(self) -> dict[str, float]:
        """Every colour present, with its painted area in mm2.

        Unioned, not summed. Two regions of one colour routinely overlap — a
        fill and the stroke around it, or two shapes sharing an edge — and
        summing reports an area the design does not have. Every number this
        prints gets compared against a measurement somewhere else, so it has to
        mean the same thing.
        """
        by: dict[str, list] = {}
        for r in self.regions:
            by.setdefault(r.colour, []).append(r.geom)
        return {c: self.mm2(unary_union(v)) for c, v in by.items()}

    def select(self, colour: str | None = None, kind: str | None = None) -> list[Region]:
        return [r for r in self.regions
                if (colour is None or r.colour == colour)
                and (kind is None or r.kind == kind)]

    def geom_of(self, colour: str, kind: str | None = None):
        rs = self.select(colour, kind)
        return unary_union([r.geom for r in rs]) if rs else None

    # ------------------------------------------------------------------ #
    # Mutation

    def parent_of(self, el: ET.Element) -> ET.Element | None:
        for parent in self.root.iter():
            if el in list(parent):
                return parent
        return None

    def set_fill_geom(self, region: Region, geom) -> None:
        """Rewrite a fill region's geometry, retagging the element if needed.

        An offset ellipse is no longer an ellipse and a cut polygon is no longer
        a polygon; only `d` can carry an arbitrary region with holes. The stale
        geometry attributes are removed, or a renderer draws the old shape.

        **A stroke on the same element is split off first.** `d` is shared by an
        element's fill and its stroke, so reshaping the fill silently drags the
        outline with it. Cutting LemonCat's linework out of its yellow body made
        the body's own black outline re-trace every whisker and brow, tripling
        the black region; the next operation then cut that inflated black out of
        the eyes and took 333 mm2 instead of 163. Nothing failed — it just
        quietly produced different geometry. The stroke keeps the original path
        on a clone, which is where it was drawn and where it should stay.
        """
        el = region.el
        if id(el) in self._stroked and el.get("d"):
            clone = ET.Element(el.tag, dict(el.attrib))
            clone.set("fill", "none")
            clone.attrib.pop("id", None)
            parent = self.parent_of(el)
            if parent is not None:
                parent.insert(list(parent).index(el) + 1, clone)
                el.set("stroke", "none")
                self._drop_style(el, ("stroke", "stroke-width"))
                self._stroked.discard(id(el))
        if el.tag.split("}")[-1] != "path":
            el.tag = f"{{{G.SVG}}}path"
            for attr in ("points", "x", "y", "width", "height",
                         "cx", "cy", "r", "rx", "ry"):
                el.attrib.pop(attr, None)
        el.set("d", G.to_d(geom))
        el.set("fill-rule", "evenodd")
        region.geom = geom

    def clear_paint(self, region: Region) -> None:
        """Unset one region's paint; remove the element if nothing is left."""
        el = region.el
        if region.kind == "stroke":
            el.set("stroke", "none")
            self._drop_style(el, ("stroke", "stroke-width"))
        else:
            el.set("fill", "none")
            self._drop_style(el, ("fill",))
        # The two properties have opposite initial values, and getting that
        # backwards leaves emptied elements in the document painting black by
        # default. Absent `fill` means BLACK; absent `stroke` means NONE.
        fill_painted = (el.get("fill") or "").strip().lower() != "none"
        stroke_painted = (el.get("stroke") or "none").strip().lower() != "none"
        if not fill_painted and not stroke_painted:
            parent = self.parent_of(el)
            if parent is not None:
                parent.remove(el)

    def set_colour(self, region: Region, colour: str) -> None:
        el = region.el
        attr = "stroke" if region.kind == "stroke" else "fill"
        el.set(attr, f"#{colour}")
        self._drop_style(el, (attr,))
        region.colour = colour

    @staticmethod
    def _drop_style(el: ET.Element, names: tuple[str, ...]) -> None:
        """Remove declarations from `style` so the attribute is the only source.

        `style` wins in a renderer and loses in `svg_prep.prop`, so leaving both
        in place makes a file that previews one way and stitches another.
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

    def add_fill(self, geom, colour: str, ident: str = "added") -> ET.Element | None:
        d = G.to_d(geom)
        if not d:
            return None
        el = ET.Element(f"{{{G.SVG}}}path", {
            "id": ident, "d": d, "fill": f"#{colour}",
            "fill-rule": "evenodd", "stroke": "none",
        })
        self.root.insert(0, el)     # lightest first, matching svg_prep's order
        return el

    def save(self, path) -> None:
        self.tree.write(str(path), encoding="utf-8", xml_declaration=True)
        ET.parse(str(path))   # fail loudly rather than hand on a broken document
