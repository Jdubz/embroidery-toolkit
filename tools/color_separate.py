"""Raster -> one SVG per thread layer, each tagged with how it should be stitched.

The companion to vectorize.py. That one is for single-colour line art; this one
splits flat-colour artwork into layers and lets each layer pick its treatment.

Why per-layer treatment matters: filling and centrelining are not
interchangeable. A 0.23 mm whisker at 0.4 mm row spacing gets zero or one row
of fill and effectively disappears, while the point where a dozen such strokes
converge collects every travel run in the region -- measured at 52 penetrations
/mm^2 on the first attempt here, well past the ~30 where this machine starts
breaking needles. Line art wants a centreline; only genuinely solid areas want
a fill.

  fill  Filled path carrying inkstitch:* parameters, including
        underpath="True" so travel runs under the fill instead of jumping
        across bare fabric.
  line  Filled path with no parameters, for the caller to push through
        fill_to_stroke -> redwork into one continuous running stitch.
  auto  Split the layer by local stroke width at --split-mm and do both:
        the solid parts filled, the thin parts centrelined. Use this when one
        colour carries both, which for hand-drawn artwork is the normal case.
        Measured on the LemonCat's black layer: 58% of its area is under
        0.8 mm wide, but it also has solid masses out to 6.4 mm. Centrelining
        all of it reduced the eyebrows and pupils to spidery skeletons;
        filling all of it lost the whiskers and hit 52 penetrations/mm^2.

Each pixel is assigned to the nearest colour in the declared palette. --skip
colours take part in that assignment but are never stitched, so the fabric
shows through (white eyes on white cloth). Colours in neither list are
background.

Layers are written as L<NN>_<mode>_<hex>.svg into --out-dir; the numbering is
stitch order, so --layer is given bottom layer first.

Usage:
  color_separate.py <image> <out_dir> <width_mm>
      --layer FFD600:fill --layer 000000:line [--skip FFFFFF] ...
"""

from __future__ import annotations

import argparse
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

SVG_NS = "http://www.w3.org/2000/svg"
INK_NS = "http://inkstitch.org/namespace"
ET.register_namespace("", SVG_NS)
ET.register_namespace("inkstitch", INK_NS)

# Ink/Stitch treats a document carrying inkstitch:* parameters but no version
# stamp as a legacy file and raises a modal "Unversioned Ink/Stitch SVG file
# detected" dialog. Headless that dialog never gets an answer and the export
# blocks forever at ~0% CPU. 4 is what the libraries bundled with 3.3.0 declare
# (...\bin\icons\inx\inkstitch-fill_pattern-library.svg). Re-check after an
# Ink/Stitch upgrade.
INKSTITCH_SVG_VERSION = "4"

# Ink/Stitch drops stitches shorter than this document-level setting. Without
# it, 11-18% of the stitches in a generated design came out under 0.5 mm --
# they pile penetrations into one spot, give the upper thread no length to take
# up tension, and work the bobbin thread to the surface. raster.py enforces the
# same floor with _filter_short; Ink/Stitch output bypassed that entirely.
#
# Read from the machine profile, never hard-coded: swapping machines is meant
# to be a one-file edit.
from embroidery_tools import profile as _prof  # noqa: E402

MIN_STITCH_MM = _prof.load()["design_limits"]["min_stitch_mm"]


def hexcol(s: str) -> tuple[int, int, int]:
    """Parse RRGGBB, strictly.

    Strictly, because PowerShell silently evaluates an unquoted 000000 as the
    number 0 and passes "0" through. Padding that to black would be a guess,
    and a wrong guess here quietly stitches the wrong colour.
    """
    raw, s = s, s.lstrip("#")
    if len(s) != 6 or any(c not in "0123456789abcdefABCDEF" for c in s):
        hint = ("  (PowerShell evaluates an unquoted 000000 as the number 0 -- "
                "quote colour arguments: -Layer '000000:line')"
                if raw.strip("0") == "" or len(raw) < 6 else "")
        raise SystemExit(f"bad colour {raw!r}: expected six hex digits, e.g. FFD600{hint}")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def parse_layer(spec: str) -> tuple[str, str]:
    col, _, mode = spec.partition(":")
    mode = (mode or "fill").lower()
    if mode not in ("fill", "line", "auto"):
        raise SystemExit(f"bad layer {spec!r}: mode must be 'fill', 'line' or 'auto'")
    hexcol(col)                      # validate now, fail with a clear message
    return col.lstrip("#").upper(), mode


def disk(r: int) -> np.ndarray:
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    return (yy * yy + xx * xx) <= r * r


ap = argparse.ArgumentParser()
ap.add_argument("image")
ap.add_argument("out_dir")
ap.add_argument("width_mm", type=float)
ap.add_argument("--layer", action="append", default=[], metavar="HEX[:fill|line]",
                help="thread layer, bottom first; mode defaults to fill")
ap.add_argument("--skip", action="append", default=[],
                help="colour matched during assignment but left unstitched")
ap.add_argument("--bleed", type=float, default=0.3,
                help="mm each layer extends under the ones above it")
ap.add_argument("--spacing", type=float, default=0.4, help="fill row spacing mm")
ap.add_argument("--angle", type=float, default=45.0, help="fill angle degrees")
ap.add_argument("--stitch-len", type=float, default=3.0)
ap.add_argument("--min-blob-mm2", type=float, default=1.0,
                help="drop speckles smaller than this")
ap.add_argument("--split-mm", type=float, default=1.5,
                help="auto mode: strokes at least this wide are filled, "
                     "narrower ones are centrelined")
a = ap.parse_args()

if not a.layer:
    raise SystemExit("need at least one --layer")

layers_spec = [parse_layer(s) for s in a.layer]
out_dir = Path(a.out_dir)
out_dir.mkdir(parents=True, exist_ok=True)

img = Image.open(a.image).convert("RGBA")
arr = np.array(img)
H, W = arr.shape[:2]
px_per_mm = W / a.width_mm
height_mm = H / px_per_mm

opaque = arr[:, :, 3] > 128
rgb = arr[:, :, :3].astype(np.int16)

# Nearest-colour assignment over the full declared palette. Both stitched and
# skipped colours compete, so an anti-aliased pixel between black linework and
# a white eye lands on whichever it is actually closer to rather than being
# smeared into whichever layer happens to be processed first.
palette = [hexcol(c) for c, _ in layers_spec] + [hexcol(c) for c in a.skip]
dist = np.stack([np.abs(rgb - np.array(c)).sum(axis=2) for c in palette])
owner = np.argmin(dist, axis=0)

min_px = int(a.min_blob_mm2 * px_per_mm * px_per_mm)
bleed_px = int(round(a.bleed * px_per_mm))

FILL_PARAMS = {
    "angle": f"{a.angle:g}",
    "row_spacing_mm": f"{a.spacing:g}",
    "max_stitch_length_mm": f"{a.stitch_len:g}",
    "staggers": "4",
    "expand_mm": "0.2",
    # Route travel under the fill rather than jumping over bare fabric.
    "underpath": "True",
    "underlay_underpath": "True",
    "running_stitch_length_mm": "2.5",
    "fill_underlay": "True",
    "fill_underlay_angle": f"{a.angle - 90:g}",
    "fill_underlay_row_spacing_mm": "2.5",
    "fill_underlay_max_stitch_length_mm": "3",
    "fill_underlay_inset_mm": "0.5",
}


def new_doc() -> ET.Element:
    root = ET.Element(f"{{{SVG_NS}}}svg", {
        "version": "1.1",
        "width": f"{a.width_mm:.3f}mm",
        "height": f"{height_mm:.3f}mm",
        "viewBox": f"0 0 {W} {H}",
    })
    meta = ET.SubElement(root, f"{{{SVG_NS}}}metadata")
    ET.SubElement(meta, f"{{{INK_NS}}}inkstitch_svg_version").text = INKSTITCH_SVG_VERSION
    ET.SubElement(meta, f"{{{INK_NS}}}min_stitch_len_mm").text = f"{MIN_STITCH_MM:g}"
    return root


def trace_mask(mask: np.ndarray) -> list[tuple[str, str | None]]:
    """Vectorise a boolean mask, returning (d, transform) per path.

    The transform is not optional. vtracer positions each shape with its own
    `transform="translate(...)"` and leaves the `d` data relative to that.
    Copying only `d` silently collapses every shape toward the origin -- which
    looks like a plausible drawing at first glance, then piles the geometry up
    so fill_to_stroke centrelines the overlap as one blob.
    """
    with tempfile.TemporaryDirectory() as td:
        png, svg = Path(td) / "m.png", Path(td) / "m.svg"
        Image.fromarray(np.where(mask, 0, 255).astype(np.uint8)).convert("RGB").save(png)
        import vtracer
        vtracer.convert_image_to_svg_py(
            str(png), str(svg),
            colormode="binary", mode="spline",
            filter_speckle=4, corner_threshold=60,
            length_threshold=4.0, splice_threshold=45,
        )
        ds = []
        for p in ET.parse(svg).getroot().iter(f"{{{SVG_NS}}}path"):
            d = p.get("d")
            if not d:
                continue
            # vtracer paints the background as one enormous path too. Keep only
            # the dark clusters, which are the mask itself.
            fill = (p.get("fill") or "").lower()
            if fill and fill not in ("#000000", "black", "none"):
                continue
            ds.append((d, p.get("transform")))
        return ds


def despeckle(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """Drop regions below --min-blob-mm2.

    Guarded on region COUNT, not area: an earlier version of the raster tracer
    measured area, passed a 2.2% loss as harmless, and had in fact shattered
    the linework into 26 pieces.
    """
    lab, n = ndimage.label(mask)
    if not n:
        return mask, 0
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    big = np.nonzero(sizes >= min_px)[0] + 1
    if not len(big):
        return mask, 0
    return np.isin(lab, big), n - len(big)


_NUM = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
_TRANSLATE = re.compile(r"^\s*translate\(\s*(-?[\d.eE+-]+)[\s,]+(-?[\d.eE+-]+)\s*\)\s*$")


def check_registration(tag: str, items, mask: np.ndarray) -> None:
    """Fail if traced geometry does not land where the mask is.

    A dropped or misapplied transform still produces a perfectly valid SVG that
    renders as a plausible-looking drawing, just in the wrong place. Nothing
    downstream notices -- Ink/Stitch happily stitches it, the PES validates, and
    the error only shows up on fabric. So compare bounding boxes here.

    The path-data bound is approximate: coordinates are read pairwise, which is
    right for the M/L/C commands vtracer emits, and Bezier control points can
    sit slightly outside the true curve. Only a gross mismatch is treated as an
    error, which is enough to catch a collapse to the origin.
    """
    xs, ys = [], []
    for d, tf in items:
        dx = dy = 0.0
        if tf:
            m = _TRANSLATE.match(tf)
            if not m:
                return          # transform we cannot reason about; skip quietly
            dx, dy = float(m.group(1)), float(m.group(2))
        nums = [float(n) for n in _NUM.findall(d)]
        xs += [n + dx for n in nums[0::2]]
        ys += [n + dy for n in nums[1::2]]
    if not xs or not ys:
        return

    ry, rx = np.nonzero(mask)
    got = (min(xs), min(ys), max(xs), max(ys))
    want = (rx.min(), ry.min(), rx.max(), ry.max())
    tol = 0.10 * max(mask.shape)
    off = max(abs(g - w) for g, w in zip(got, want))
    if off > tol:
        raise SystemExit(
            f"{tag}: traced geometry does not match the mask it came from.\n"
            f"  mask   x[{want[0]},{want[2]}] y[{want[1]},{want[3]}] px\n"
            f"  traced x[{got[0]:.0f},{got[2]:.0f}] y[{got[1]:.0f},{got[3]:.0f}] px\n"
            f"  worst corner off by {off:.0f}px (tolerance {tol:.0f}px).\n"
            f"  Most likely a path transform was dropped when copying vtracer output.")


def emit(tag: str, col: str, mode: str, mask: np.ndarray) -> Path | None:
    """Vectorise one mask and write it as a layer document."""
    if not mask.any():
        print(f"    {tag} #{col} {mode}: EMPTY - skipped")
        return None
    items = trace_mask(mask)
    check_registration(tag, items, mask)

    root = new_doc()
    g = ET.SubElement(root, f"{{{SVG_NS}}}g", {"id": f"{tag}_{col}"})
    n_paths = 0
    for k, (d, tf) in enumerate(items, 1):
        attrs = {"id": f"{tag}_{col}_{k}", "d": d, "style": f"fill:#{col};stroke:none"}
        if tf:
            attrs["transform"] = tf
        # Fill parameters only on fill layers. A line layer is about to be
        # centrelined, so fill settings on it would be meaningless.
        if mode == "fill":
            attrs.update({f"{{{INK_NS}}}{key}": val for key, val in FILL_PARAMS.items()})
        ET.SubElement(g, f"{{{SVG_NS}}}path", attrs)
        n_paths = k
    if not n_paths:
        print(f"    {tag} #{col} {mode}: no traceable geometry - skipped")
        return None

    path = out_dir / f"{tag}_{mode}_{col}.svg"
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    ET.parse(path)   # fail loudly rather than handing a broken document downstream
    area = mask.sum() / (px_per_mm ** 2)
    print(f"    {tag} #{col} {mode}: {n_paths} path(s), {area:.0f} mm^2 -> {path.name}")
    return path


written = []
for i, (col, mode) in enumerate(layers_spec):
    mask, dropped = despeckle(opaque & (owner == i))
    if dropped:
        print(f"    L{i:02d} #{col}: {dropped} speckle(s) dropped")

    # Bleed downward: each layer grows under the ones above it so pull on the
    # top layer cannot open a seam of bare fabric. Kept small -- colour-boundary
    # stacking was previously the biggest source of lethal density peaks.
    if bleed_px:
        above = opaque & np.isin(owner, np.arange(i + 1, len(layers_spec)))
        mask = mask | (ndimage.binary_dilation(mask, iterations=bleed_px) & above)

    if mode != "auto":
        p = emit(f"L{i:02d}", col, mode, mask)
        if p:
            written.append(p)
        continue

    # Opening by a disk of radius split_mm/2 keeps exactly the pixels a disk of
    # that size can reach -- i.e. the parts genuinely at least split_mm across.
    # Everything else is thin appendage. Sub-layers are lettered so filename
    # sort still yields stitch order, and the fill goes down before the line so
    # the linework reads on top.
    r = max(1, int(round(a.split_mm / 2 * px_per_mm)))
    thick = ndimage.binary_opening(mask, structure=disk(r))
    thin = mask & ~thick
    thick, _ = despeckle(thick)
    thin, thin_dropped = despeckle(thin)

    # When the artwork has been prepared so every stroke already exceeds the
    # split width, "thin" is not linework at all — it is the rounding residue
    # left along the corners of thick shapes by the opening. Tracing that
    # produces scattered slivers spread over the whole design, which trips the
    # registration check for a reason that is not a registration error.
    thin_share = thin.sum() / max(1, mask.sum())
    if thin.any() and thin_share < 0.03:
        print(f"    L{i:02d} #{col} auto: thin remainder is {thin_share * 100:.1f}% "
              f"of the layer — corner residue, not linework; discarded")
        thin = np.zeros_like(thin)

    share = thick.sum() / max(1, mask.sum()) * 100
    print(f"    L{i:02d} #{col} auto: split at {a.split_mm:g} mm -> "
          f"{share:.0f}% filled / {100 - share:.0f}% centrelined"
          + (f", {thin_dropped} thin fragment(s) dropped" if thin_dropped else ""))
    for sub, m, md in (("a", thick, "fill"), ("b", thin, "line")):
        p = emit(f"L{i:02d}{sub}", col, md, m)
        if p:
            written.append(p)

if not written:
    raise SystemExit("no layer produced any geometry")
print(f"    {W}x{H}px -> {a.width_mm:.1f} x {height_mm:.1f} mm, {len(written)} layer(s), XML valid")
