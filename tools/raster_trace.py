"""Trace flat-colour raster art into a plain SVG that `svg_edit` can work on.

The raster path (`inkstitch_pipeline`) digitizes straight from pixels, so none
of the geometry operations in `svg_edit` can reach it — and those operations are
where this repo fixes artwork: `offset`, `subtract`, `drop`, `widen-negative`.
Goose_on_black needed exactly that. Its linework is knocked out of the fills
(bare cloth on black) and drawn at 1.14 mm median against the 1.8 mm
`negative_space_mm`, and a raster cannot be widened.

This writes one `<path>` per declared colour, `fill-rule="evenodd"`, in the
order given — which is the painting order, so list the colour that sits on top
last. No `transform` anywhere: vtracer positions every shape with a per-path
`translate(...)`, and `svgdoc` refuses a transform rather than ignore it, so the
offset is baked into the coordinates here. Dropping it instead is the vtracer
registration bug that `color_separate.check_registration` exists for.

**`--background` separates the canvas from the linework, which share a colour.**
Art drawn on a black ground uses the same black for the empty canvas and for
every line inside the drawing, and the two need opposite treatment: the canvas is
not stitched, the lines are the thing being widened. They cannot be told apart by
connectivity — almost every line in the goose runs out to the edge of the
silhouette, so a flood fill from the border takes nearly all of them. Instead,
the silhouette is the morphological CLOSING of everything that is not
background, at `--close-mm`: a gap narrower than twice that is inside the
drawing, a wider one is canvas. Background-coloured pixels inside the silhouette
are emitted as a layer in that colour; outside it, nothing is emitted.

Pick `--close-mm` from the widths it prints. Too small and lines are lost to the
canvas; too large and wide notches between features are swept in as "linework",
which matters only if that layer is then grown.

    raster_trace.py goose.png goose.svg --width-mm 100 \\
        --colour FFFFFF --colour FAC800 --colour 000000 \\
        --background 000000 --close-mm 2.0
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embroidery_tools import measure  # noqa: E402

SVG_NS = "http://www.w3.org/2000/svg"
_TOK = re.compile(r"([A-Za-z])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")


def hexcol(s: str) -> str:
    s = s.strip().lstrip("#").upper()
    if not re.fullmatch(r"[0-9A-F]{6}", s):
        raise SystemExit(f"not a hex colour: {s!r} (quote it in PowerShell: '000000')")
    return s


def rgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def disk(r: int) -> np.ndarray:
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def bake(d: str, dx: float, dy: float) -> str:
    """Add (dx, dy) to every coordinate of an absolute M/L/C/Z path.

    Only what vtracer emits is accepted. Anything else raises: a relative or
    single-axis command would be shifted wrongly, and a wrong shift is a valid
    path in the wrong place — the failure this function exists to prevent.
    """
    out, cmd, args = [], None, []

    def flush():
        if cmd is None:
            return
        if cmd not in "MLCZ":
            raise SystemExit(f"bake: unexpected path command {cmd!r} from vtracer")
        if len(args) % 2:
            raise SystemExit(f"bake: odd coordinate count after {cmd!r}")
        pts = [f"{args[i] + dx:.3f} {args[i + 1] + dy:.3f}" for i in range(0, len(args), 2)]
        out.append(" ".join([cmd] + pts))

    for letter, number in _TOK.findall(d):
        if letter:
            flush()
            cmd, args = letter, []
        else:
            args.append(float(number))
    flush()
    return " ".join(out)


def trace(mask: np.ndarray) -> str:
    """vtracer a boolean mask; every shape baked into one path string."""
    import vtracer
    with tempfile.TemporaryDirectory() as td:
        png, svg = Path(td) / "m.png", Path(td) / "m.svg"
        Image.fromarray(np.where(mask, 0, 255).astype(np.uint8)).convert("RGB").save(png)
        vtracer.convert_image_to_svg_py(
            str(png), str(svg), colormode="binary", mode="spline",
            filter_speckle=4, corner_threshold=60,
            length_threshold=4.0, splice_threshold=45)
        parts = []
        for p in ET.parse(svg).getroot().iter(f"{{{SVG_NS}}}path"):
            fill = (p.get("fill") or "").lower()
            if not p.get("d") or (fill and fill not in ("#000000", "black")):
                continue    # vtracer's own background rectangle
            m = re.fullmatch(r"\s*translate\(\s*([-\d.eE+]+)[\s,]+([-\d.eE+]+)\s*\)\s*",
                             p.get("transform") or "translate(0,0)")
            if not m:
                raise SystemExit(f"trace: transform we cannot bake: {p.get('transform')!r}")
            parts.append(bake(p.get("d"), float(m.group(1)), float(m.group(2))))
        return " ".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--width-mm", type=float, required=True,
                    help="width of the whole canvas in mm; sizes --close-mm and "
                         "--min-area-mm2 (svg_prep rescales to --artwork-mm anyway)")
    ap.add_argument("--colour", action="append", required=True,
                    help="a colour to trace, in painting order (bottom first)")
    ap.add_argument("--background", help="colour of the empty canvas; see module doc")
    ap.add_argument("--close-mm", type=float, default=2.0,
                    help="gaps narrower than twice this are inside the drawing")
    ap.add_argument("--min-area-mm2", type=float, default=1.0,
                    help="drop specks smaller than this (anti-aliasing debris)")
    a = ap.parse_args()

    cols = [hexcol(c) for c in a.colour]
    bg = hexcol(a.background) if a.background else None
    if len(set(cols)) != len(cols):
        raise SystemExit("each --colour once")

    img = np.asarray(Image.open(a.src).convert("RGBA")).astype(np.int32)
    H, W = img.shape[:2]
    ppm = W / a.width_mm
    opaque = img[:, :, 3] > 128
    palette = cols + ([bg] if bg and bg not in cols else [])
    dist = np.stack([((img[:, :, :3] - np.array(rgb(c))) ** 2).sum(axis=2) for c in palette])
    owner = np.where(opaque, dist.argmin(axis=0), -1)

    # Anti-aliasing leaves a one-pixel seam of in-between colours along every
    # edge, and nearest-colour sends it to whichever declared colour happens to
    # be closest — on the goose, mid-grey between white and black is nearer the
    # yellow, so 1,145 yellow specks lined every white/black edge. Dropping
    # specks alone would leave those pixels unassigned and thin both sides by a
    # pixel; hand each one to its nearest real neighbour instead.
    min_px = a.min_area_mm2 * ppm * ppm
    dropped = dict.fromkeys(range(len(palette)), 0)
    for i in range(len(palette)):
        lab, n = ndimage.label(owner == i)
        if not n:
            continue
        sizes = ndimage.sum(owner == i, lab, range(1, n + 1))
        small = np.nonzero(sizes < min_px)[0] + 1
        owner[np.isin(lab, small)] = -1
        dropped[i] = len(small)
    hole = opaque & (owner < 0)
    if hole.any():
        idx = ndimage.distance_transform_edt(owner < 0, return_distances=False,
                                             return_indices=True)
        owner[hole] = owner[idx[0][hole], idx[1][hole]]

    inside = opaque
    if bg:
        ink = opaque & (owner != palette.index(bg))
        r = max(1, int(round(a.close_mm * ppm)))
        padded = np.pad(ink, r + 1)
        closed = ndimage.binary_closing(padded, structure=disk(r))[r + 1:-r - 1, r + 1:-r - 1]
        inside = ndimage.binary_fill_holes(closed | ink)

    # Unitless and equal to the viewBox, like every other SVG in art/: physical
    # size is set downstream by --artwork-mm, not here.
    root = ET.Element(f"{{{SVG_NS}}}svg", {
        "width": str(W), "height": str(H), "viewBox": f"0 0 {W} {H}"})
    print(f"  {W}x{H} px -> {a.width_mm:g} x {H / ppm:.1f} mm, {ppm:.2f} px/mm")
    for c in cols:
        mask = owner == palette.index(c)
        if c == bg:
            mask &= inside
        dropped_c = dropped[palette.index(c)]
        if not mask.any():
            print(f"  #{c}: nothing to trace")
            continue
        widths = measure.widths_mm(mask, ppm)
        role = "  (linework inside the drawing)" if c == bg else ""
        print(f"  #{c}: {mask.sum() / ppm ** 2:,.0f} mm2, median width "
              f"{np.median(widths):.2f} mm, {measure.frac_below_mm(mask, ppm, 1.2) * 100:.0f}% "
              f"under 1.2, {measure.frac_below_mm(mask, ppm, 1.8) * 100:.0f}% under 1.8"
              f"{f', {dropped_c} speck(s) reassigned' if dropped_c else ''}{role}")
        ET.SubElement(root, f"{{{SVG_NS}}}path", {
            "id": f"c{c}", "fill": f"#{c}", "fill-rule": "evenodd",
            "stroke": "none", "d": trace(mask)})

    ET.register_namespace("", SVG_NS)
    Path(a.dst).parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(a.dst, encoding="utf-8", xml_declaration=True)
    ET.parse(a.dst)     # never hand on a file that does not parse
    print(f"  -> {a.dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
