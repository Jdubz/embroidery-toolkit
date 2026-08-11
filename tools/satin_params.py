"""Add underlay to satin columns produced by stroke_to_satin.

`stroke_to_satin` emits bare satin columns — inspected output carries
`inkstitch:satin_column` and no underlay attribute of any kind. A satin with no
underlay lies straight on the cloth: it sinks into the weave, the top thread
sits low relative to the bobbin, and bobbin colour shows along the rails.

**The underlay that fixes it depends on the column's width.** Ink/Stitch's own
guidance (inkstitch.org/tutorials/underlay) bands it:

    <= 2.0 mm   centre-walk    a single line down the middle; all there is room for
    2.0-3.5 mm  + contour      a line just inside each rail
    > 3.5 mm    + zigzag       for columns wide enough to need lifting as well

Contour underlay is what anchors the rails: a satin puts every penetration on
two thin lines 0.4 mm apart, so the weave along a rail is perforated and the
lockstitch knot has little to grip. Centre-walk does nothing there.

Width is measured **from the column's own geometry** — the median rail-to-rail
distance, in millimetres. That is the whole point of this file's current shape.
The previous version could not measure, so it joined columns positionally
against the stroke widths `svg_prep` recorded, and that join is fragile:
`stroke_to_satin` renames every id, forces `stroke-width:1px`, and does not
promise one column per input stroke. On the solid LemonCat it turned 9 strokes
into 11 columns, the join refused to guess, and every column fell back to the
same blanket underlay — including four 1.65 mm ones that only wanted
centre-walk.

Two measurement traps, both hit before this worked:

- **Do not count on-curve points to tell a rail from a rung.** A rail is often a
  single cubic, `M x,y C ...`, so it has exactly two on-curve points and looks
  identical to a straight two-point rung. `svgpath.parse_path` records whether a
  curve command contributed, which is the reliable discriminator.
- **Do not measure rung length and call it the width.** Rungs overshoot the
  rails so they reliably cross both: measured on real output they run about
  1.2x the true width. Rail-to-rail distance has no such fudge factor.

Deliberately NOT set: `contour_underlay_inset_mm`. Ink/Stitch v3.3.0 defaults it
to 0.4 mm, inside its own documented 0.4-0.6 mm range. A previous version forced
0.2 here — an invented value, half the vendor default, and against the rule in
CLAUDE.md that a parameter is written only when this machine demands something
different from Ink/Stitch's.

Usage:  satin_params.py <in.svg> <out.svg> [--widths <file>] [--contour]
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from embroidery_tools.svgpath import apply, parse_path, parse_transform

SVG = "http://www.w3.org/2000/svg"
INK = "http://inkstitch.org/namespace"
ET.register_namespace("", SVG)
ET.register_namespace("inkstitch", INK)

# Band edges, from Ink/Stitch's underlay tutorial. Vendor numbers, not machine
# limits, so they do not belong in machine-profile.json.
CONTOUR_MIN_MM = 2.0
ZIGZAG_MIN_MM = 3.5

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--widths", help="stroke-widths.txt from svg_prep.py, used only "
                                 "as a cross-check on the measured widths")
ap.add_argument("--contour", action="store_true",
                help="force contour underlay on every column regardless of width")
a = ap.parse_args()


def doc_units_per_mm(root) -> float | None:
    vb = (root.get("viewBox") or "").split()
    w = root.get("width") or ""
    if len(vb) != 4:
        return None
    m = re.match(r"\s*(-?\d*\.?\d+)\s*(mm|cm|in|px)?\s*$", w)
    if not m:
        return None
    val, unit = float(m.group(1)), (m.group(2) or "px")
    mm = {"mm": val, "cm": val * 10.0, "in": val * 25.4, "px": val * 25.4 / 96.0}[unit]
    return float(vb[2]) / mm if mm else None


def point_to_polyline(pt, poly):
    a0, b0 = poly[:-1], poly[1:]
    ab = b0 - a0
    ap_ = pt - a0
    denom = np.maximum((ab * ab).sum(1), 1e-12)
    t = np.clip((ap_ * ab).sum(1) / denom, 0.0, 1.0)
    proj = a0 + t[:, None] * ab
    return float(np.min(np.hypot(*(pt - proj).T)))


def column_width_mm(el, upm, ancestors) -> float | None:
    """Median rail-to-rail distance of a satin column, in mm."""
    subs = parse_path(el.get("d") or "")
    if not subs:
        return None
    m = parse_transform(el.get("transform"))
    for anc in reversed(ancestors):          # outermost first
        am = parse_transform(anc.get("transform"))
        m = (am[0] * m[0] + am[2] * m[1], am[1] * m[0] + am[3] * m[1],
             am[0] * m[2] + am[2] * m[3], am[1] * m[2] + am[3] * m[3],
             am[0] * m[4] + am[2] * m[5] + am[4], am[1] * m[4] + am[3] * m[5] + am[5])
    for s in subs:
        s["xy"] = np.asarray(apply(m, s["points"]), dtype=float)
        d = np.diff(s["xy"], axis=0)
        s["len"] = float(np.hypot(d[:, 0], d[:, 1]).sum())

    # A rung is a straight two-point crossbar. Anything curved, or with more
    # than two points, is a rail. Curvature is the discriminator, not point
    # count: a rail is frequently a single cubic with two on-curve points.
    rails = [s for s in subs if s["curved"] or len(s["points"]) > 2]
    if len(rails) < 2:                        # degenerate: straight-sided column
        rails = sorted(subs, key=lambda s: -s["len"])[:2]
    if len(rails) < 2:
        return None
    rails = sorted(rails, key=lambda s: -s["len"])[:2]
    A, B = rails[0]["xy"], rails[1]["xy"]
    if len(A) < 2 or len(B) < 2:
        return None
    idx = np.linspace(0, len(A) - 1, min(len(A), 60)).astype(int)
    d = [point_to_polyline(A[i], B) for i in idx]
    return statistics.median(d) / upm if upm else None


def underlay_for(width_mm: float | None) -> dict[str, str]:
    params = {"center_walk_underlay": "True"}
    if width_mm is None or a.contour or width_mm > CONTOUR_MIN_MM:
        params["contour_underlay"] = "True"
    if width_mm is not None and width_mm > ZIGZAG_MIN_MM:
        params["zigzag_underlay"] = "True"
    return params


tree = ET.parse(a.src)
root = tree.getroot()
parents = {c: p for p in root.iter() for c in p}


def chain(el):
    out, n = [], parents.get(el)
    while n is not None:
        out.append(n)
        n = parents.get(n)
    return out


upm = doc_units_per_mm(root)
if upm is None:
    print("  WARNING: cannot establish document scale; widths unknown",
          file=sys.stderr)

columns = [el for el in root.iter()
           if el.get(f"{{{INK}}}satin_column") in ("true", "True", "1")]
widths = [column_width_mm(el, upm, chain(el)) if upm else None for el in columns]

banded: dict[str, int] = {}
for el, w in zip(columns, widths):
    params = underlay_for(w)
    for k, v in params.items():
        el.set(f"{{{INK}}}{k}", v)
    key = "+".join(k.replace("_underlay", "") for k in params)
    banded[key] = banded.get(key, 0) + 1

tree.write(a.dst, encoding="utf-8", xml_declaration=True)
ET.parse(a.dst)      # fail loudly rather than handing a broken document downstream

known = [w for w in widths if w is not None]
if not columns:
    print("  no satin columns found — nothing to underlay")
else:
    if known:
        print(f"  {len(columns)} satin column(s), measured {min(known):.2f}-{max(known):.2f} mm wide")
    else:
        print(f"  {len(columns)} satin column(s), widths could not be measured")
    for key, n in sorted(banded.items()):
        print(f"    {n:3d} x {key}")

# Cross-check against what svg_prep declared. Not used for banding — the point
# of measuring is not to need it — but a systematic disagreement means the
# geometry is being read wrong, and that should be loud rather than silent.
if a.widths and known:
    rows = [ln.split("\t") for ln in
            Path(a.widths).read_text(encoding="utf-8").splitlines() if ln.strip()]
    declared = sorted(float(r[1]) for r in rows if len(r) == 2)
    if declared:
        ratio = statistics.median(sorted(known)) / statistics.median(declared)
        note = "" if 0.9 <= ratio <= 1.1 else "   <-- CHECK: measured widths disagree with the source strokes"
        print(f"  cross-check: declared {min(declared):.2f}-{max(declared):.2f} mm, "
              f"measured/declared median ratio {ratio:.2f}{note}")
