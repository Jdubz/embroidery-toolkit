"""Raster -> SVG for the Ink/Stitch pipeline.

Emits an SVG sized in real millimetres, because everything downstream —
Ink/Stitch's line widths, stitch lengths, the hoop check — is in mm. An SVG
with no physical units gets interpreted at 96 dpi and the design comes out the
wrong size.

Usage:  vectorize.py <image> <out.svg> <width_mm>
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

src, dst, width_mm = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])

img = Image.open(src).convert("RGBA")
arr = np.array(img)

# vtracer has no alpha handling: composite onto white and let it trace the dark
# linework. Without this a transparent background traces as a giant black slab.
if (arr[:, :, 3] < 250).any():
    flat = Image.new("RGB", img.size, "white")
    flat.paste(img, mask=img.split()[3])
else:
    flat = img.convert("RGB")

# Redwork centrelines everything it is given, which is right for strokes and
# destructive for solid shapes: a filled eyebrow or pupil collapses to a spur or
# a small starburst and reads as missing. Measure before converting rather than
# discovering it in the render.
SOLID_MM = 1.5
_ink = np.array(flat).astype(int).sum(axis=2) < 384
if _ink.any():
    from scipy import ndimage

    _ppm = _ink.shape[1] / width_mm
    _r = max(1, int(round(SOLID_MM / 2 * _ppm)))
    _yy, _xx = np.ogrid[-_r:_r + 1, -_r:_r + 1]
    _solid = ndimage.binary_opening(_ink, structure=(_yy ** 2 + _xx ** 2) <= _r * _r)
    _share = _solid.sum() / _ink.sum() * 100
    if _share >= 10:
        print(f"    WARNING: {_share:.0f}% of the artwork is at least {SOLID_MM} mm wide, "
              f"i.e. solid rather than stroke.")
        print(f"             Redwork will centreline those areas and they will read as "
              f"missing.")
        print(f"             Use:  -Mode layered -Layer '<hex>:auto'  to fill them "
              f"and centreline the rest.")

with tempfile.TemporaryDirectory() as td:
    tmp_png = Path(td) / "flat.png"
    flat.save(tmp_png)

    import vtracer
    vtracer.convert_image_to_svg_py(
        str(tmp_png), str(dst),
        colormode="binary",       # line art: black shapes on white
        mode="spline",            # smooth curves, not polygons
        filter_speckle=6,
        corner_threshold=60,
        length_threshold=4.0,
        splice_threshold=45,
    )

# Post-process with a real XML parser, not regex.
#
# vtracer writes width/height in pixels and emits anonymous paths. Two things
# have to change: restate the document in millimetres (everything downstream —
# Ink/Stitch line widths, stitch lengths, the hoop check — is in mm), and give
# every path an id, because Inkscape extensions act on a *selection* supplied as
# --id=<id> arguments.
#
# An earlier version did this by regex and produced `<path .../ id="p1"/>`,
# which libxml rejected. Ink/Stitch then reported a parse error and passed the
# document through unchanged while still exiting 0.
import xml.etree.ElementTree as ET  # noqa: E402

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

tree = ET.parse(dst)
root = tree.getroot()

pw = float(re.sub(r"[^\d.]", "", root.get("width", "0")) or 0)
ph = float(re.sub(r"[^\d.]", "", root.get("height", "0")) or 0)
if not pw or not ph:
    raise SystemExit("traced SVG has no usable width/height")
height_mm = width_mm * ph / pw

if not root.get("viewBox"):
    root.set("viewBox", f"0 0 {pw:g} {ph:g}")
root.set("width", f"{width_mm:.3f}mm")
root.set("height", f"{height_mm:.3f}mm")

count = 0
for el in root.iter(f"{{{SVG_NS}}}path"):
    if not el.get("id"):
        count += 1
        el.set("id", f"p{count}")

tree.write(dst, encoding="utf-8", xml_declaration=True)

# Fail loudly rather than handing a broken document downstream.
ET.parse(dst)
print(f"    {pw:.0f}x{ph:.0f}px -> {width_mm:.1f} x {height_mm:.1f} mm, "
      f"{count} paths tagged, XML valid")
