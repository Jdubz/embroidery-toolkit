"""Prepare a hand-authored SVG for Ink/Stitch, without tracing anything.

This is the best input path there is. `vectorize.py` and `color_separate.py`
exist to recover geometry from pixels; when the artwork is already vector, all
of that guessing disappears — the curves are exact, the stroke widths are
declared rather than measured, and no centrelining is needed because a stroke is
already a stroke.

What it does:

* Sizes the document so the **artwork** ends up at the requested width. An SVG
  canvas usually has margin around the drawing, so setting the document to
  91 mm gives an 75 mm design. The drawing bounds come from Inkscape itself.
* Resolves `fill`, `stroke` and `stroke-width` through ancestors. These are
  inherited CSS properties and are routinely set once on a wrapping `<g>` — read
  them off the element alone and you find two stroked paths in a drawing of
  sixteen.
* Tags each element by what it is:
    filled  -> auto_fill, with underlay and `underpath` travel
    stroked -> `zigzag_stitch` at the stroke's own width, i.e. a satin line
* Reports the real-world width of every stroke so a design whose lines are
  below the machine's minimum is caught before it is stitched, not after.

Usage:
  svg_prep.py <in.svg> <out.svg> --artwork-mm 91 [--spacing 0.4] [--angle 45]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embroidery_tools import profile as prof  # noqa: E402

SVG = "http://www.w3.org/2000/svg"
INK = "http://inkstitch.org/namespace"
ET.register_namespace("", SVG)
ET.register_namespace("inkstitch", INK)

SHAPES = {"path", "polygon", "ellipse", "rect", "circle", "polyline", "line"}
INHERITED = ("fill", "stroke", "stroke-width")

INKSCAPE = next((p for p in (
    Path(r"C:\Program Files\Inkscape\bin\inkscape.exe"),
    Path(r"C:\Program Files (x86)\Inkscape\bin\inkscape.exe")) if p.exists()), None)


def prop(el: ET.Element, name: str, ancestors: list[ET.Element]) -> str | None:
    """Resolve an inherited presentation attribute, element first then upward."""
    for node in [el, *reversed(ancestors)]:
        v = node.get(name)
        if v:
            return v.strip()
        style = node.get("style") or ""
        for part in style.split(";"):
            k, _, val = part.partition(":")
            if k.strip() == name and val.strip():
                return val.strip()
    return None


def drawing_bbox(path: Path) -> tuple[float, float]:
    """Width and height of the drawing in user units, measured by Inkscape."""
    if INKSCAPE is None:
        raise SystemExit("Inkscape not found; needed to measure the drawing bounds")
    out = subprocess.run([str(INKSCAPE), "--query-width", "--query-height", str(path)],
                         capture_output=True, text=True, timeout=120)
    nums = [float(v) for v in out.stdout.split() if v.replace(".", "", 1).isdigit()]
    if len(nums) < 2:
        raise SystemExit(f"could not read drawing bounds from Inkscape: {out.stdout!r} "
                         f"{out.stderr.strip()[:200]}")
    return nums[0], nums[1]


ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--artwork-mm", type=float, required=True,
                help="target width of the DRAWING, not the canvas")
ap.add_argument("--spacing", type=float, default=None, metavar="MM",
                help="fill row spacing; defaults to the machine profile's "
                     "design_limits.fill_density_mm, or to the --cloth variant "
                     "of it")
ap.add_argument("--cloth", choices=("light", "dark", "knits"), default="light",
                metavar="KIND",
                help="what the design is stitched ON, which sets the default "
                     "row spacing. 'dark' tightens it to "
                     "design_limits.fill_density_mm_dark: the validated 0.4 mm "
                     "covers on white and speckles on black, because every "
                     "needle penetration shows the cloth and on black that is a "
                     "dark dot. Explicit --spacing overrides it.")
ap.add_argument("--expand", type=float, default=0.2, metavar="MM",
                help="pull compensation: how far each colour grows outward. "
                     "Every colour expands independently, so at a shared "
                     "boundary BOTH sides claim the same band and the colour "
                     "stitched last drives its needle through the earlier "
                     "one's thread. Lower it when the machine is breaking "
                     "needles; 0 disables it and risks hairline gaps.")
ap.add_argument("--lock-style", default="bowtie", metavar="STYLE",
                help="tack/lock stitch style at the start and end of every run. "
                     "Ink/Stitch's default is half_stitch, which sizes the tie "
                     "at HALF the first stitch, so a fill that happens to begin "
                     "short opens a colour with sub-0.5 mm ties. Pass 'default' "
                     "to leave it alone. Valid in 3.3.0: half_stitch, triangle, "
                     "star, bowtie — see the note in the source.")
ap.add_argument("--no-fill-underlay", action="store_true",
                help="drop the underlay beneath fills. Ink/Stitch turns it on "
                     "by default at 3x the fill spacing, perpendicular to it, "
                     "which is ~20%% of all the thread laid. Underlay is a "
                     "quality feature and the first one to drop when the "
                     "machine is failing.")
ap.add_argument("--skip", action="append", default=[], metavar="RRGGBB",
                help="colour to leave unstitched so the fabric shows through; "
                     "repeatable. Quote it — PowerShell reads 000000 as 0.")
ap.add_argument("--colour-order", nargs="+", metavar="RRGGBB",
                help="explicit stitch order. Default is light to dark, because "
                     "the colour stitched last owns the shared boundary.")
a = ap.parse_args()
if a.spacing is None:
    key = {"light": "fill_density_mm",
           "dark": "fill_density_mm_dark",
           "knits": "fill_density_mm_knits"}[a.cloth]
    a.spacing = prof.design_limit(key, 0.4)
    if a.cloth != "light":
        print(f"  {a.cloth} cloth: row spacing {a.spacing:g} mm "
              f"(design_limits.{key})")

src, dst = Path(a.src), Path(a.dst)
tree = ET.parse(src)
root = tree.getroot()

vb = [float(v) for v in (root.get("viewBox") or "").split()] or None
if not vb:
    raise SystemExit("SVG has no viewBox; cannot establish scale")

bw, bh = drawing_bbox(src)
doc_mm = a.artwork_mm * vb[2] / bw
units_per_mm = vb[2] / doc_mm
root.set("width", f"{doc_mm:.3f}mm")
root.set("height", f"{doc_mm * vb[3] / vb[2]:.3f}mm")
print(f"  drawing {bw:.0f}x{bh:.0f} units in a {vb[2]:.0f}x{vb[3]:.0f} canvas")
print(f"  document set to {doc_mm:.1f} mm so the artwork is "
      f"{a.artwork_mm:.0f} x {a.artwork_mm * bh / bw:.1f} mm")

meta = ET.SubElement(root, f"{{{SVG}}}metadata")
for k, v in (("inkstitch_svg_version", "4"),
             ("min_stitch_len_mm", f"{prof.min_stitch_mm():g}")):
    ET.SubElement(meta, f"{{{INK}}}{k}").text = v

# Only override what there is a machine-specific reason to override.
#
# An earlier version of this file forced about twenty parameters, nearly all of
# them values invented here rather than measured. The rule below came out of
# that clean-up.
#
# (The comment here used to claim Ink/Stitch's satin default was 0.25 mm and
# that overriding it with 0.4 mm caused a sparse stitch-out. Both halves were
# wrong. Ink/Stitch v3.3.0 declares `zigzag_spacing_mm` default=0.4, and the
# satin in designs/out measures 0.40 mm rail-to-rail — so that override was a
# no-op and never caused anything. The real defect was the zigzag *mode*, as
# CLAUDE.md's correction records.)
#
# So the rule now: write a parameter only if the SE700 or this thread demands a
# value different from Ink/Stitch's, and say why. Everything else is left alone,
# because Ink/Stitch's defaults were chosen by people who do this for a living.
#
# Four survive. Everything previously set for fills — angle, staggers,
# max_stitch_length_mm, running_stitch_length_mm, the whole fill_underlay_*
# group — is now default. Strokes get NO parameters at all: they are converted
# to real satin columns by the stroke_to_satin extension, which derives the
# column from the stroke width, and Ink/Stitch's satin defaults handle spacing,
# underlay and pull compensation.
FILL = {
    # 1. Row spacing. Machine/thread specific: 0.4 mm is the validated density
    #    for 40 wt through a 75/11 on this machine (docs/10). From the profile.
    "row_spacing_mm": f"{a.spacing:g}",

    # 2. Travel under the fill instead of jumping over it. THE machine-specific
    #    setting: the SE700 does not trim jumps within a colour, so every jump
    #    is a float you snip by hand, not a machine cost. Measured 275 jumps ->
    #    31 on one design.
    "underpath": "True",

    # 3. Pull compensation. Fabric draws in under stitching; without this,
    #    neighbouring colours leave a hairline of bare fabric between them.
    #    It is also the thing that piles thread on colour boundaries: each
    #    colour grows outward independently, so both sides of a shared edge
    #    claim the same band. Measured on Scream4 — 100% of the forty densest
    #    cells sat on a boundary, at median 4 penetrations/mm2 against 1 in
    #    single-colour areas. Tunable for that reason.
    "expand_mm": f"{a.expand:g}",
}

# 5. Fixed-length tack stitches. Machine-specific, and this machine's specific
#    problem: with one needle, EVERY colour change is a manual rethread, and the
#    first stitches after a rethread are where a marginally tensioned thread
#    gets pulled down into the hook instead of locking. Ink/Stitch's default
#    lock style is `half_stitch`, which sizes the tie at half the first stitch —
#    so the tie inherits whatever the fill happened to start with. Scream4's red
#    pass opened with four 0.30 mm ties, four penetrations in nearly the same
#    hole, giving the take-up almost no thread to work against.
#
#    **Verify any value you set here against the exported stitches.** The style
#    is a string and Ink/Stitch silently ignores one it does not recognise —
#    `back_and_forth` was tried first, on the strength of the docs, and produced
#    a PES byte-identical to the run without it. The docs describe a newer
#    release than the 3.3.0 installed here. Measured on a test fill in 3.3.0:
#
#      half_stitch  0.71 0.78 0.78 0.71   the default; sized off the first stitch
#      triangle     0.76 0.76 0.85
#      star         1.43 1.27 1.26 1.14 0.71
#      bowtie       1.08 1.22 1.00 1.00   every opening stitch >= 1.0 mm
#      back_and_forth / custom            IGNORED, silently identical to default
#
#    bowtie wins on the metric that matters: no near-zero penetrations, and
#    4.3 mm of thread pulled through the take-up before the fill begins, against
#    2.98 mm for the default. The *_scale_mm parameters are deliberately not set
#    — bowtie scales by percent, so writing them would be inert clutter.
if a.lock_style and a.lock_style != "default":
    FILL["lock_start"] = a.lock_style
    FILL["lock_end"] = a.lock_style

# 6. Fill underlay, written ONLY to turn it off. Ink/Stitch defaults it to True
#    (3x the fill row spacing, perpendicular to the fill), so leaving it out
#    means it is on — this is one of the few cases where saying nothing is not
#    the same as accepting the default, because the default is what we want to
#    change. Measured: fills carry ~3.9 mm of thread per mm2 with it against
#    ~2.5 for a bare 0.4 mm fill.
if a.no_fill_underlay:
    FILL["fill_underlay"] = "False"

# 4. is min_stitch_len_mm, set once on the document rather than per element —
#    see the metadata block below.
STROKE: dict[str, str] = {}

min_line = prof.design_limit("safe_satin_width_mm", 1.2)
skips = {c.lstrip("#").upper() for c in (a.skip or [])}


def norm(colour: str | None) -> str | None:
    if not colour:
        return None
    c = colour.strip().lower()
    if c in ("none", "transparent"):
        return None
    return c.lstrip("#").upper() if c.startswith("#") else c.upper()


def luminance(hex6: str) -> float:
    try:
        r, g, b = (int(hex6[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return 0.0
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# One shape can carry both a fill and a stroke — the body is yellow with a black
# outline. Ink/Stitch stitches an element's fill and stroke together, in
# document order, so leaving it whole forces a colour change at every shape.
# Split each shape into separate fill and stroke operations, then group the
# operations by colour: one change for the whole design instead of a dozen.
Op = tuple[str, str, ET.Element, list[ET.Element], float]   # colour, kind, el, ancestors, width_mm
ops: list[Op] = []
n_id = 0


def walk(node: ET.Element, ancestors: list[ET.Element]) -> None:
    global n_id
    for el in list(node):
        tag = el.tag.split("}")[-1]
        if tag == "g":
            walk(el, [*ancestors, el])
            continue
        if tag not in SHAPES:
            continue
        n_id += 1
        if not el.get("id"):
            el.set("id", f"e{n_id}")
        fill = norm(prop(el, "fill", ancestors))
        stroke = norm(prop(el, "stroke", ancestors))
        if fill:
            ops.append((fill, "fill", el, ancestors, 0.0))
        if stroke:
            sw = float(prop(el, "stroke-width", ancestors) or 1)
            ops.append((stroke, "stroke", el, ancestors, sw / units_per_mm))


walk(root, [root])

dropped = [o for o in ops if o[0] in skips]
ops = [o for o in ops if o[0] not in skips]
if not ops:
    raise SystemExit("every operation was skipped; nothing to stitch")

# Skipping a colour is not the same as leaving fabric bare. On screen the white
# eyes sit ON TOP of the yellow body and hide it; in stitches, dropping the
# white just uncovers the yellow underneath and the eyes come out yellow.
#
# To get bare fabric the shape has to become a HOLE in the fill below it. In SVG
# that is one path containing both outlines with fill-rule="evenodd" — the inner
# subpath cuts a hole rather than painting over. Pure string concatenation, no
# boolean geometry needed.
knockouts = [o for o in dropped
             if o[1] == "fill" and o[2].tag.split("}")[-1] == "path" and o[2].get("d")]
if knockouts:
    holes = " ".join(o[2].get("d").strip() for o in knockouts)
    host = next((o for o in ops if o[1] == "fill" and o[2].tag.split("}")[-1] == "path"
                 and o[2].get("d")), None)
    if host is None:
        print("  NOTE     nothing fillable to cut the skipped shapes out of; "
              "they will simply be absent", file=sys.stderr)
    else:
        host[2].set("d", f"{host[2].get('d').strip()} {holes}")
        host[2].set("fill-rule", "evenodd")
        print(f"  knocked out {len(knockouts)} shape(s) as holes in "
              f"#{host[0]} — fabric shows through there")

# Light before dark: pull compensation makes neighbours overlap, and whichever
# colour goes last owns the boundary. Dark covers a light edge cleanly.
if a.colour_order:
    wanted = [c.lstrip("#").upper() for c in a.colour_order]
    rank = {c: i for i, c in enumerate(wanted)}
    ops.sort(key=lambda o: (rank.get(o[0], len(wanted)), o[1] == "stroke"))
else:
    ops.sort(key=lambda o: (luminance(o[0]) * -1, o[1] == "stroke"))

# Rebuild: one element per operation, carrying only that operation's paint.
for child in list(root):
    if child.tag.split("}")[-1] not in ("metadata", "defs"):
        root.remove(child)

import copy  # noqa: E402

thin: list[tuple[str, float]] = []
widths: list[float] = []
n_fill = n_stroke = 0
for idx, (colour, kind, el, ancestors, width_mm) in enumerate(ops, 1):
    node = copy.deepcopy(el)
    for attr in ("style", "fill", "stroke", "stroke-width"):
        node.attrib.pop(attr, None)
    node.set("id", f"{el.get('id')}_{kind}")

    if kind == "fill":
        n_fill += 1
        node.set("fill", f"#{colour}" if len(colour) == 6 else colour)
        node.set("stroke", "none")
        params = FILL
    else:
        n_stroke += 1
        widths.append(width_mm)
        if width_mm < min_line:
            thin.append((node.get("id"), width_mm))
        node.set("fill", "none")
        node.set("stroke", f"#{colour}" if len(colour) == 6 else colour)
        node.set("stroke-width", str(prop(el, "stroke-width", ancestors) or 1))
        params = STROKE
    for k, v in params.items():
        node.set(f"{{{INK}}}{k}", v)

    # Preserve any transform the original inherited from its ancestors.
    tf = [n.get("transform") for n in ancestors if n.get("transform")]
    if tf:
        g = ET.SubElement(root, f"{{{SVG}}}g", {"transform": " ".join(tf)})
        g.append(node)
    else:
        root.append(node)

tree.write(dst, encoding="utf-8", xml_declaration=True)
ET.parse(dst)   # fail loudly rather than handing a broken document downstream

# Ink/Stitch extensions act on a selection passed as --id arguments, so the
# caller needs to know which elements are the strokes to convert into satin
# columns. Write them alongside rather than making the caller re-parse and
# re-derive the inheritance rules.
stroke_ids = [f"{el.get('id')}_stroke" for colour, kind, el, *_ in ops if kind == "stroke"]
ids_file = dst.with_suffix(".stroke-ids.txt")
ids_file.write_text("\n".join(stroke_ids), encoding="utf-8")

# The declared widths, for cross-checking only. satin_params.py measures each
# satin column from its own geometry — it has to, because `stroke_to_satin`
# discards the id, forces `stroke-width:1px`, and does not promise one column
# per input stroke (9 strokes became 11 columns on the solid LemonCat, which is
# what killed the positional join this file used to feed). Keeping the widths
# lets satin_params report a measured/declared ratio, so geometry read wrongly
# shows up as a number rather than as a quietly mis-banded design.
widths_file = dst.with_suffix(".stroke-widths.txt")
widths_file.write_text(
    "\n".join(f"{i}\t{w:.3f}" for i, w in zip(stroke_ids, widths)), encoding="utf-8")

seq = []
for colour, kind, *_ in ops:
    if not seq or seq[-1][0] != colour:
        seq.append([colour, 0])
    seq[-1][1] += 1
print(f"  {n_stroke} stroked -> satin columns (via stroke_to_satin), "
      f"{n_fill} filled -> auto_fill")
print(f"  overrides written: {', '.join(FILL)} + min_stitch_len_mm; "
      f"everything else left at Ink/Stitch defaults")
print(f"  stroke ids -> {ids_file.name}, widths -> {widths_file.name}")
print(f"  stitch order: " + " -> ".join(f"#{c} x{n}" for c, n in seq)
      + f"   ({len(seq) - 1} colour change(s))")
if dropped:
    per = {}
    for c, *_ in dropped:
        per[c] = per.get(c, 0) + 1
    print("  left unstitched: " + ", ".join(f"#{c} x{n}" for c, n in per.items())
          + "  (fabric shows through)")
if widths:
    print(f"  stroke widths on fabric: {min(widths):.2f} - {max(widths):.2f} mm "
          f"(machine minimum {min_line})")
if thin:
    print(f"  WARNING  {len(thin)} stroke(s) below {min_line} mm — these read as "
          f"scratches, not lines:", file=sys.stderr)
    for i, mm in thin[:6]:
        print(f"             {i}: {mm:.2f} mm", file=sys.stderr)
    print(f"           Widen them in the source SVG. Shrinking --artwork-mm makes "
          f"them thinner still.", file=sys.stderr)
print(f"  wrote {dst}")
