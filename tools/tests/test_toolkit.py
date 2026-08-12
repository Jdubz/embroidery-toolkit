"""Invariant tests for the embroidery toolkit.

Run:  .venv\\Scripts\\python.exe tools\\tests\\test_toolkit.py

Deliberately dependency-free (no pytest) so it runs anywhere the toolkit does.
Every check here corresponds to a bug that actually shipped at some point in this
repo's history — see CLAUDE.md for the write-ups.
"""

from __future__ import annotations

import math
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pyembroidery as pe  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from embroidery_tools import analyze, convert, flatten, palette, preview, raster, recolor  # noqa: E402
from embroidery_tools import profile as prof  # noqa: E402

FAILURES: list[str] = []
PASSED = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILURES.append(f"{name}: {detail}")
        print(f"  FAIL  {name}  {detail}")


def section(t):
    print(f"\n--- {t} ---")


TMP = Path(tempfile.mkdtemp(prefix="embtest_"))


def make_art(path: Path, size=600) -> Path:
    """Flat art with an enclosed hole and a thin stroke."""
    img = Image.new("RGB", (size, size), "white")
    d = ImageDraw.Draw(img)
    d.ellipse([40, 40, size - 40, size - 40], fill="#1B6CA8")
    d.ellipse([size // 3, size // 3, 2 * size // 3, 2 * size // 3], fill="white")
    d.rectangle([size // 2 - 6, 60, size // 2 + 6, size - 60], fill="#C1443C")
    img.save(path)
    return path


# --------------------------------------------------------------------------- #
section("geometry helpers")

m = np.zeros((40, 40), bool)
m[10:30, 10:30] = True
m[18:22, 18:22] = False          # a hole

for ang in (0, 45, 90, 137):
    frags = raster._scanline_fragments(m, ang, 2.0)
    bad = 0
    for frag in frags:
        for line in frag:
            for p0, p1 in line:
                for p in (p0, p1):
                    xi, yi = int(round(p[0])), int(round(p[1]))
                    if not (0 <= xi < 40 and 0 <= yi < 40 and m[yi, xi]):
                        bad += 1
    check(f"scanline endpoints inside mask @{ang}deg", bad == 0,
          f"{bad} endpoints outside the shape")

# A square with a hole fills as ONE fragment: the rows above and below the hole
# link the two sides, so it can be stitched without ever leaving the shape.
frags = raster._scanline_fragments(m, 0, 2.0)
check("ring-like shape links into one fragment", len(frags) == 1,
      f"{len(frags)} fragments — a hole should not split the region")
check("fragments cover every row with coverage",
      sum(len(f) for f in frags) > 5, f"{sum(len(f) for f in frags)} rows")

path = [(0.0, 0.0), (0.05, 0.0), (0.1, 0.0), (5.0, 0.0), (5.02, 0.0)]
f = raster._filter_short(path, 1.0)
segs = [math.dist(a, b) for a, b in zip(f, f[1:])]
check("filter_short removes sub-threshold stitches",
      all(s >= 1.0 - 1e-9 for s in segs), f"{segs}")
check("filter_short keeps the final point", f[-1] == path[-1], f"{f[-1]}")

p2 = [(0.0, 0.0), (10.0, 0.0)]
locked = raster._add_locks(p2, 2.0)
zero = sum(1 for a, b in zip(locked, locked[1:]) if math.dist(a, b) < 1e-9)
check("add_locks emits no zero-length stitch", zero == 0, f"{zero} found")
check("add_locks brackets the run", len(locked) > len(p2), f"{locked}")
check("add_locks preserves start", locked[0] == p2[0])
check("add_locks preserves end", locked[-1] == p2[-1])
check("add_locks no-op on degenerate path", raster._add_locks([(1.0, 1.0)], 2.0) == [(1.0, 1.0)])

check("filter_short handles 2-point path", raster._filter_short([(0.0, 0.0), (0.1, 0.0)], 5.0)
      == [(0.0, 0.0), (0.1, 0.0)])

sub_a = raster._subdivide((0.0, 0.0), (10.0, 0.0), 3.0, phase=0.0)
sub_b = raster._subdivide((0.0, 0.0), (10.0, 0.0), 3.0, phase=0.5)
check("subdivide honours phase", sub_a[0] != sub_b[0], f"{sub_a[0]} vs {sub_b[0]}")
check("subdivide always ends on p1",
      sub_a[-1] == (10.0, 0.0) and sub_b[-1] == (10.0, 0.0))
check("subdivide respects max length",
      all(math.dist(a, b) <= 3.0 + 1e-6
          for a, b in zip([(0.0, 0.0)] + sub_b, sub_b)), f"{sub_b}")

tp = raster._travel_path(m, (12.0, 12.0), (12.0, 27.0), 200.0)
check("travel_path routes within the shape", tp is not None)
if tp:
    outside = [q for q in tp if not m[int(round(q[1])), int(round(q[0]))]]
    check("travel_path stays inside the mask", not outside, f"{len(outside)} outside")
check("travel_path refuses a point outside the mask",
      raster._travel_path(m, (0.0, 0.0), (12.0, 12.0), 200.0) is None)

# --------------------------------------------------------------------------- #
section("trace end to end")

art = make_art(TMP / "art.png")
out = TMP / "art.pes"
report = raster.trace(art, out, raster.TraceSettings(colors=3))
info = analyze.describe(out)

check("trace produced stitches", info.real_stitches > 100, f"{info.real_stitches}")
check("trace fits the hoop",
      info.width_mm <= prof.max_field_mm()[0] and info.height_mm <= prof.max_field_mm()[1],
      f"{info.width_mm}x{info.height_mm}")
check("reported extent matches the file",
      abs(report.width_mm - info.width_mm) < 0.2,
      f"report {report.width_mm} vs file {info.width_mm}")

lens = []
prev, first = None, False
for x, y, c in pe.read(str(out)).stitches:
    cmd = c & pe.COMMAND_MASK
    if cmd == pe.STITCH:
        if prev is not None and not first:
            lens.append(math.dist(prev, (x, y)) / 10.0)
        first, prev = False, (x, y)
    else:
        prev = (x, y) if cmd == pe.JUMP else None
        first = True
short = [s for s in lens if s < 0.4]
check("no stitches below the minimum length", len(short) <= len(lens) * 0.01,
      f"{len(short)} of {len(lens)} under 0.4mm")
check("no zero-length stitches", not [s for s in lens if s < 1e-6],
      f"{len([s for s in lens if s < 1e-6])} found")
check("max stitch respects the limit", max(lens) <= 3.6, f"max {max(lens):.2f}mm")

# --------------------------------------------------------------------------- #
section("tatami stagger")


def _phase_spread(pes_path, angle, L=30.0):
    """How many distinct penetration phases the fill uses. 1 = aligned columns."""
    pat = pe.read(str(pes_path))
    pts = [(x, y) for x, y, c in pat.stitches
           if (c & pe.COMMAND_MASK) == pe.STITCH]
    th = math.radians(angle)
    d = np.array([math.cos(th), math.sin(th)])
    proj = np.array(pts) @ d
    hist, _ = np.histogram(np.mod(proj, L) / L, bins=10, range=(0, 1))
    return int((hist / hist.sum() > 0.02).sum())


rect = TMP / "rect.png"
_im = Image.new("RGB", (500, 500), "white")
ImageDraw.Draw(_im).rectangle([60, 60, 440, 440], fill="#1B6CA8")
_im.save(rect)

_opts = dict(colors=2, fill_angle_deg=0.0, underlay=False, outline=False,
             travel_mm=0.0)
raster.trace(rect, TMP / "r_off.pes", raster.TraceSettings(stagger_rows=1, **_opts))
raster.trace(rect, TMP / "r_on.pes", raster.TraceSettings(stagger_rows=4, **_opts))
off = _phase_spread(TMP / "r_off.pes", 0.0)
on = _phase_spread(TMP / "r_on.pes", 0.0)
check("stagger spreads needle penetrations", on > off,
      f"{off} phase(s) unstaggered vs {on} staggered — aligned rows perforate "
      f"the fabric in a line and read as ridges")

# --------------------------------------------------------------------------- #
section("PES container")

check("origin starts at 0,0 (Brother convention)",
      info.bounds_units[0] >= -1 and info.bounds_units[1] >= -1,
      f"min ({info.bounds_units[0]}, {info.bounds_units[1]})")
check("hoop code matches the machine", convert.read_pes_hoop(out) == 0,
      f"{convert.read_pes_hoop(out)}")

import struct as _struct  # noqa: E402
head = out.read_bytes()[:20]
check("PES section stripped", _struct.unpack("<I", head[8:12])[0] == 22,
      f"pec offset {_struct.unpack('<I', head[8:12])[0]}")

findings = analyze.validate(info)
codes = {f.code for f in findings if f.severity == analyze.ERROR}
check("fresh trace has no blocking findings", not codes, f"{codes}")
warn = {f.code for f in findings}
check("no pes-origin warning", "pes-origin-centred" not in warn)
check("no pes-section warning", "pes-section-misplaced" not in warn)
check("no pes-hoop warning", "pes-hoop-mismatch" not in warn)

threads = [t.hex_color() for t in pe.read(str(out)).threadlist]
check("thread colours are distinct", len(threads) == len(set(threads)), f"{threads}")


def _luma(hexc):
    h = hexc.lstrip("#")
    return 0.2126 * int(h[0:2], 16) + 0.7152 * int(h[2:4], 16) + 0.0722 * int(h[4:6], 16)


lumas = [_luma(t) for t in threads]
check("layers stitch light to dark",
      all(a >= b - 1e-6 for a, b in zip(lumas, lumas[1:])), f"{threads}")

# round trip through convert
dst = TMP / "art_conv.pes"
convert.convert(out, dst)
ri = analyze.describe(dst)
check("convert preserves stitch count", ri.real_stitches == info.real_stitches,
      f"{ri.real_stitches} vs {info.real_stitches}")
check("convert keeps origin convention", ri.bounds_units[0] >= -1)
check("convert keeps hoop code", convert.read_pes_hoop(dst) == 0)

dstd = TMP / "art.dst"
convert.convert(out, dstd)
check("DST export preserves geometry",
      abs(analyze.describe(dstd).width_mm - info.width_mm) < 0.2)

# --------------------------------------------------------------------------- #
section("runtime + validation maths")

check("runtime counts sewing, trims and rethreads",
      info.runtime_minutes() > info.real_stitches / 400.0,
      "trims/rethreads not included")

big = analyze.DesignInfo(path=Path("x.pes"), width_mm=150, height_mm=150,
                         real_stitches=10, thread_count=1)
codes = {f.code for f in analyze.validate(big)}
check("oversized design is an error", "field-overflow" in codes, f"{codes}")

many = analyze.DesignInfo(path=Path("x.pes"), width_mm=50, height_mm=50,
                          real_stitches=200000, thread_count=1)
check("stitch overflow detected", "stitch-overflow" in {f.code for f in analyze.validate(many)})

bad_name = analyze.DesignInfo(path=Path("my design!.pes"), width_mm=50, height_mm=50,
                              real_stitches=10, thread_count=1)
check("bad filename detected", "filename-charset" in {f.code for f in analyze.validate(bad_name)})

# --------------------------------------------------------------------------- #
section("palette / recolor / flatten")

near = palette.nearest("#FF0000", 3)
check("palette returns requested count", len(near) == 3, f"{len(near)}")
check("palette sorted by distance", near[0]["delta_e"] <= near[1]["delta_e"])
check("palette handles 3-digit hex", palette.nearest("#F00", 1)[0]["hex"] == near[0]["hex"])
try:
    palette.parse_hex("nope")
    check("palette rejects bad hex", False, "no exception")
except ValueError:
    check("palette rejects bad hex", True)

rc_out = TMP / "rc.png"
rep = recolor.recolor(art, rc_out, mappings=[("#C1443C", "#1B6CA8")], drops=["#FFFFFF"])
arr = np.array(Image.open(rc_out).convert("RGBA"))
check("recolor drops to transparency", (arr[:, :, 3] == 0).any())
opaque_cols = {tuple(c) for c in arr[arr[:, :, 3] > 128][:, :3]}
check("recolor merged the mapped colour", len(opaque_cols) <= 2, f"{len(opaque_cols)} colours left")

fl_out = TMP / "fl.png"
frep = flatten.flatten(art, fl_out, colors=3)
check("flatten reduces to the requested palette", frep.unique_after <= 3,
      f"{frep.unique_after}")
check("flatten reports before/after", frep.unique_before >= frep.unique_after)

# --------------------------------------------------------------------------- #
section("preview / render")

svg = TMP / "p.svg"
preview.render_svg(out, svg)
check("svg preview written", svg.stat().st_size > 500)
txt = svg.read_text(encoding="utf-8")
check("svg is well formed", txt.startswith("<svg") and txt.rstrip().endswith("</svg>"))

png = TMP / "p.png"
r = preview.render_realistic(out, png, fabric="#FFFFFF")
check("realistic render written", png.stat().st_size > 1000)
check("render reports size", r["width_mm"] > 0 and r["stitch_runs"] > 0)

# --------------------------------------------------------------------------- #
section("edge cases")

solid = TMP / "solid.png"
Image.new("RGB", (200, 200), "#2E7D4F").save(solid)
try:
    raster.trace(solid, TMP / "solid.pes", raster.TraceSettings(colors=2))
    check("single-colour image traces or errors cleanly", True)
except ValueError as e:
    check("single-colour image traces or errors cleanly", True, f"clean error: {e}")
except Exception as e:
    check("single-colour image traces or errors cleanly", False, f"{type(e).__name__}: {e}")

blank = TMP / "blank.png"
Image.new("RGBA", (200, 200), (0, 0, 0, 0)).save(blank)
try:
    raster.trace(blank, TMP / "blank.pes", raster.TraceSettings(colors=2))
    check("fully transparent image raises a clear error", False, "no exception")
except ValueError:
    check("fully transparent image raises a clear error", True)
except Exception as e:
    check("fully transparent image raises a clear error", False, f"{type(e).__name__}")

tiny = TMP / "tiny.png"
im = Image.new("RGB", (8, 8), "white")
im.putpixel((4, 4), (0, 0, 0))
im.save(tiny)
try:
    raster.trace(tiny, TMP / "tiny.pes", raster.TraceSettings(colors=2))
    check("tiny image handled", True)
except ValueError:
    check("tiny image handled", True, "clean error")
except Exception as e:
    check("tiny image handled", False, f"{type(e).__name__}: {e}")

check("read_pes_hoop ignores non-PES", convert.read_pes_hoop(dstd) is None)
check("rewrite_pes_pec_only ignores non-PES",
      convert.rewrite_pes_pec_only(dstd) is False)

# --------------------------------------------------------------------------- #
section("Ink/Stitch SVG generation")

# These exercise tools/color_separate.py and tools/svg_merge.py, which are
# standalone scripts rather than importable modules, so they run as subprocesses.
import subprocess  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

SVG_NS = "http://www.w3.org/2000/svg"
INK_NS = "http://inkstitch.org/namespace"
PY = sys.executable


def run(script: str, *args) -> subprocess.CompletedProcess:
    return subprocess.run([PY, str(ROOT / script), *[str(a) for a in args]],
                          capture_output=True, text=True)


# Art with two colours, one solid and one thin, plus a colour to leave unstitched.
sep_art = TMP / "sep.png"
_im = Image.new("RGB", (400, 400), "white")
_d = ImageDraw.Draw(_im)
_d.ellipse([40, 40, 360, 360], fill="#FFD600")          # solid body
_d.ellipse([150, 150, 250, 250], fill="#FFFFFF")        # hole, left unstitched
_d.line([60, 200, 340, 200], fill="#000000", width=3)   # thin stroke
_d.rectangle([180, 60, 220, 120], fill="#000000")       # solid block
_im.save(sep_art)

sep_dir = TMP / "layers"
r = run("color_separate.py", sep_art, sep_dir, 80,
        "--layer", "FFD600:fill", "--layer", "000000:auto", "--skip", "FFFFFF")
check("color_separate runs", r.returncode == 0, r.stderr.strip()[-200:])

if r.returncode == 0:
    made = sorted(p.name for p in sep_dir.glob("L*.svg"))
    check("auto mode splits a mixed layer into fill + line",
          any("L01a_fill_" in n for n in made) and any("L01b_line_" in n for n in made),
          str(made))
    check("layer filenames sort into stitch order", made == sorted(made), str(made))

    for f in sep_dir.glob("L*.svg"):
        root = ET.parse(f).getroot()
        # Registration: a dropped vtracer transform collapses geometry toward
        # the origin. Every path must carry its transform through.
        paths = list(root.iter(f"{{{SVG_NS}}}path"))
        check(f"{f.name}: has geometry", len(paths) > 0)
        # The version stamp: without it Ink/Stitch raises a modal migration
        # dialog and blocks forever headless.
        ver = root.find(f"{{{SVG_NS}}}metadata/{{{INK_NS}}}inkstitch_svg_version")
        check(f"{f.name}: carries inkstitch_svg_version", ver is not None and ver.text)
        # Fill params belong only on fill layers.
        has_params = any(k.startswith(f"{{{INK_NS}}}") for p in paths for k in p.attrib)
        check(f"{f.name}: params match its mode",
              has_params == ("_fill_" in f.name))
        if "_fill_" in f.name:
            underpath = paths[0].get(f"{{{INK_NS}}}underpath")
            check(f"{f.name}: routes travel under the fill", underpath == "True")

# PowerShell turns an unquoted 000000 into 0; that must be an error, not black.
r = run("color_separate.py", sep_art, TMP / "bad", 80, "--layer", "0:fill")
check("malformed hex is rejected rather than guessed",
      r.returncode != 0 and "six hex digits" in (r.stdout + r.stderr))

# svg_merge: geometry mismatch must fail, id collisions must be resolved.
def write_svg(path: Path, width: str, ids: list[str]) -> Path:
    root = ET.Element(f"{{{SVG_NS}}}svg", {
        "version": "1.1", "width": width, "height": "40mm", "viewBox": "0 0 100 40"})
    g = ET.SubElement(root, f"{{{SVG_NS}}}g")
    for i in ids:
        ET.SubElement(g, f"{{{SVG_NS}}}path",
                      {"id": i, "d": "M0,0 L10,10", "style": f"fill:none;stroke:url(#{i})"})
    ET.ElementTree(root).write(path)
    return path


a_svg = write_svg(TMP / "m_a.svg", "80mm", ["dup1", "only_a"])
b_svg = write_svg(TMP / "m_b.svg", "80mm", ["dup1", "only_b"])
c_svg = write_svg(TMP / "m_c.svg", "50mm", ["only_c"])

out_svg = TMP / "m_out.svg"
r = run("svg_merge.py", out_svg, a_svg, b_svg)
check("svg_merge resolves duplicate ids instead of failing",
      r.returncode == 0 and "renamed" in r.stdout, (r.stdout + r.stderr).strip()[-200:])
if out_svg.exists():
    mroot = ET.parse(out_svg).getroot()
    mids = [e.get("id") for e in mroot.iter() if e.get("id")]
    check("merged ids are unique", len(mids) == len(set(mids)), str(mids))
    # A rename that does not follow through to url(#...) leaves a dangling ref.
    refs = {m for e in mroot.iter() for v in e.attrib.values()
            for m in __import__("re").findall(r"url\(#([^)]+)\)", v)}
    check("url(#...) references follow the rename", refs <= set(mids),
          str(sorted(refs - set(mids))))

r = run("svg_merge.py", TMP / "m_bad.svg", a_svg, c_svg)
check("svg_merge refuses mismatched geometry rather than rescaling",
      r.returncode != 0 and "geometry mismatch" in (r.stdout + r.stderr))

# satin_params bands underlay by column width, measured from the column's own
# geometry. It used to join columns positionally against svg_prep's declared
# stroke widths, which broke the moment stroke_to_satin turned 9 strokes into
# 11 columns. These build columns whose rail separation is known exactly.
def satin_doc(path: Path, seps_units: list[float], transform: str | None = None) -> Path:
    """A document at 10 units/mm holding one satin column per separation."""
    root = ET.Element(f"{{{SVG_NS}}}svg", {
        "version": "1.1", "width": "10mm", "height": "10mm", "viewBox": "0 0 100 100"})
    for i, sep in enumerate(seps_units):
        # Two rails as cubics — a rail is frequently a single cubic, which is
        # exactly the shape that a point-count test misreads as a rung.
        d = (f"M 0,0 C 10,0 20,0 30,0 "
             f"M 0,{sep} C 10,{sep} 20,{sep} 30,{sep} "
             f"M 0,-2 L 0,{sep + 2} M 30,-2 L 30,{sep + 2}")
        attrs = {"id": f"sat{i}", "d": d, f"{{{INK_NS}}}satin_column": "True"}
        if transform:
            attrs["transform"] = transform
        ET.SubElement(root, f"{{{SVG_NS}}}path", attrs)
    ET.ElementTree(root).write(path)
    return path


def ul(e, name):
    return e.get(f"{{{INK_NS}}}{name}") == "True"


def band(svg_path):
    return [e for e in ET.parse(svg_path).getroot().iter()
            if e.get(f"{{{INK_NS}}}satin_column") == "True"]


#                    1.5 mm     3.0 mm     4.0 mm
sat_in = satin_doc(TMP / "sat_in.svg", [15.0, 30.0, 40.0])
sat_out = TMP / "sat_out.svg"
r = run("satin_params.py", sat_in, sat_out)
check("satin_params runs", r.returncode == 0, (r.stdout + r.stderr).strip()[-200:])
check("widths are measured, not guessed",
      "measured 1.50-4.00 mm" in r.stdout, r.stdout.strip()[-160:])

if sat_out.exists():
    cols = band(sat_out)
    check("every column gets centre-walk", all(ul(e, "center_walk_underlay") for e in cols))
    check("a 1.5 mm column is not given contour underlay", not ul(cols[0], "contour_underlay"))
    check("a 3.0 mm column gets contour underlay", ul(cols[1], "contour_underlay"))
    check("only a column over 3.5 mm gets zigzag underlay",
          not ul(cols[1], "zigzag_underlay") and ul(cols[2], "zigzag_underlay"))
    # An invented 0.2 mm inset put the underlay's own penetrations back on the
    # rail perforation line. Ink/Stitch defaults this to 0.4 mm; leave it alone.
    check("contour inset is left at the Ink/Stitch default, not overridden",
          all(e.get(f"{{{INK_NS}}}contour_underlay_inset_mm") is None for e in cols))

# stroke_to_satin puts the placement in a per-path transform. Ignoring it scales
# every measured width by the transform factor and mis-bands the lot.
sat_tf = satin_doc(TMP / "sat_tf.svg", [15.0], transform="scale(2)")
sat_tf_out = TMP / "sat_tf_out.svg"
r = run("satin_params.py", sat_tf, sat_tf_out)
check("a per-path transform is applied to the measured width",
      "measured 3.00-3.00 mm" in r.stdout, r.stdout.strip()[-160:])
if sat_tf_out.exists():
    check("that transformed column bands as 3 mm, not 1.5 mm",
          ul(band(sat_tf_out)[0], "contour_underlay"))

# A straight stroke produces a column whose rails are plain two-point lines, so
# the curvature test finds no rails and falls through to "the two longest
# subpaths". Rails have to out-measure the rungs for that to pick the right
# pair, which holds for any column longer than it is wide.
sat_straight = TMP / "sat_straight.svg"
_root = ET.Element(f"{{{SVG_NS}}}svg", {
    "version": "1.1", "width": "10mm", "height": "10mm", "viewBox": "0 0 100 100"})
ET.SubElement(_root, f"{{{SVG_NS}}}path", {
    "id": "flat", f"{{{INK_NS}}}satin_column": "True",
    "d": "M 0,0 L 60,0 M 0,30 L 60,30 M 0,-2 L 0,32 M 60,-2 L 60,32"})
ET.ElementTree(_root).write(sat_straight)
r = run("satin_params.py", sat_straight, TMP / "sat_straight_out.svg")
check("a straight-railed column still measures its true 3.0 mm",
      "measured 3.00-3.00 mm" in r.stdout, r.stdout.strip()[-160:])

# No viewBox means no way to convert to millimetres. That must be said out loud
# and fall back to the safe underlay, not silently band everything as narrow.
sat_noscale = TMP / "sat_noscale.svg"
_root = ET.Element(f"{{{SVG_NS}}}svg", {"version": "1.1"})
ET.SubElement(_root, f"{{{SVG_NS}}}path", {
    "id": "s", f"{{{INK_NS}}}satin_column": "True",
    "d": "M 0,0 C 10,0 20,0 30,0 M 0,15 C 10,15 20,15 30,15"})
ET.ElementTree(_root).write(sat_noscale)
r = run("satin_params.py", sat_noscale, TMP / "sat_noscale_out.svg")
check("an unscalable document warns rather than guessing a width",
      "cannot establish document scale" in (r.stdout + r.stderr),
      (r.stdout + r.stderr).strip()[-160:])
if (TMP / "sat_noscale_out.svg").exists():
    check("and falls back to contour underlay, the safe side",
          ul(band(TMP / "sat_noscale_out.svg")[0], "contour_underlay"))

# The count no longer has to match: measuring is per column.
sat_w3 = TMP / "sat_w3.txt"
sat_w3.write_text("a\t1.500\n", encoding="utf-8")      # 1 width, 3 columns
r = run("satin_params.py", sat_in, TMP / "sat_out3.svg", "--widths", sat_w3)
check("a width/column count mismatch is no longer fatal to banding",
      r.returncode == 0 and "measured 1.50-4.00 mm" in r.stdout,
      r.stdout.strip()[-160:])
check("the declared widths are still reported as a cross-check",
      "cross-check" in r.stdout, r.stdout.strip()[-160:])

# --------------------------------------------------------------------------- #
section("spec-driven build and layout audit")

import json  # noqa: E402

from embroidery_tools import build as BLD  # noqa: E402

# ps_args is pure so the command line can be checked without running a build.
# The bug it guards: PowerShell only splits `-Skip A,B` into two values when it
# parses a command line string. Passing argv directly hands over one element,
# so the .ps1 has to split it — and sending each colour as its own -Skip would
# bind only the last. A silent skip-nothing is the worst outcome: the design
# stitches over areas meant to be left as bare cloth.
_spec2 = {"name": "T", "build": {"tool": "svg_to_pes", "input": "a.svg",
                                 "artwork_mm": 87, "skip": ["FFFFFF", "000000"]}}
_a = BLD.ps_args(_spec2, Path("a.svg"), Path("b.pes"))
check("multiple skip colours travel as one comma-joined argument",
      _a[_a.index("-Skip") + 1] == "FFFFFF,000000", " ".join(_a[-4:]))

_spec3 = {"name": "T", "build": {"tool": "svg_to_pes", "input": "a.svg", "artwork_mm": 91,
                                 "options": {"NoFillUnderlay": True, "Spacing": 0.45,
                                             "ContourUnderlay": False, "LockStyle": None}}}
_a = BLD.ps_args(_spec3, Path("a.svg"), Path("b.pes"))
check("a true option becomes a bare switch", "-NoFillUnderlay" in _a)
check("a valued option becomes a pair", "-Spacing" in _a and _a[_a.index("-Spacing") + 1] == "0.45")

# Fill density follows from the declared cloth. Stating it a second time in
# options is a second place to get it wrong, and a spec that says `_on_black`
# while forgetting the density is exactly the file that stitched out speckled.
def _cloth_args(hexc, **opts):
    s = {"name": "T", "cloth": hexc,
         "build": {"tool": "svg_to_pes", "input": "a.svg", "artwork_mm": 90,
                   "options": opts}}
    return BLD.ps_args(s, Path("a.svg"), Path("b.pes"))

check("dark cloth selects the dark row spacing without being told",
      "-Cloth" in _cloth_args("141414")
      and _cloth_args("141414")[_cloth_args("141414").index("-Cloth") + 1] == "dark")
# Yellow is light despite being a strong colour — luminance, not saturation.
check("light cloth passes nothing, so the command line is unchanged",
      "-Cloth" not in _cloth_args("F2F0EB") and "-Cloth" not in _cloth_args("F2C94C"))
# 'knits' is a property of the fabric that no colour can imply, so an explicit
# option has to win over the derivation.
_ck = _cloth_args("141414", Cloth="knits")
check("an explicit Cloth option overrides the derivation",
      _ck.count("-Cloth") == 1 and _ck[_ck.index("-Cloth") + 1] == "knits")
# ps_args is documented as pure and testable; a hand-built spec with no cloth
# must not crash it. validate_spec is where the field is required.
check("a spec without cloth still produces a command line",
      "-Cloth" not in BLD.ps_args(_spec2, Path("a.svg"), Path("b.pes")))

try:
    BLD.validate_spec({"name": "T", "build": {"tool": "svg_to_pes", "input": "a.svg",
                                              "artwork_mm": 90}}, "T.json")
    check("validate_spec requires the cloth colour", False)
except ValueError as e:
    check("validate_spec requires the cloth colour",
          "cloth" in str(e) and "not a substitute" in str(e), str(e)[:120])
check("false and null options are omitted entirely",
      "-ContourUnderlay" not in _a and "-LockStyle" not in _a, " ".join(_a))
check("no skip argument when the spec skips nothing",
      "-Skip" not in BLD.ps_args({"name": "T", "build": {"tool": "svg_to_pes",
                                 "input": "a.svg", "artwork_mm": 91}},
                                 Path("a.svg"), Path("b.pes")))

# The raster path. Same comma-joining rule, and here it is not merely silent:
# PowerShell REFUSES a parameter given twice ("specified more than once"), so a
# list option sent as repeated flags fails the build outright.
_spec4 = {"name": "T", "build": {"tool": "inkstitch_pipeline",
                                 "input": "a.webp", "artwork_mm": 75.8,
                                 "skip": ["FAECCE"],
                                 "options": {"Mode": "layered",
                                             "Layer": ["E6B10C:fill", "25270A:auto"]}}}
_a = BLD.ps_args(_spec4, Path("a.webp"), Path("b.pes"))
check("raster builds call inkstitch_pipeline.ps1",
      any(x.endswith("inkstitch_pipeline.ps1") for x in _a), " ".join(_a[:6]))
check("raster builds pass the image as -Image, not -Svg",
      "-Image" in _a and "-Svg" not in _a)
check("artwork_mm becomes -WidthMm for a raster build",
      _a[_a.index("-WidthMm") + 1] == "75.8")
check("a list option travels as ONE comma-joined argument",
      _a.count("-Layer") == 1 and _a[_a.index("-Layer") + 1] == "E6B10C:fill,25270A:auto",
      " ".join(_a))
check("an empty list option is omitted rather than sent blank",
      "-Layer" not in BLD.ps_args(
          {"name": "T", "build": {"tool": "inkstitch_pipeline", "input": "a.webp",
                                  "artwork_mm": 80, "options": {"Layer": []}}},
          Path("a.webp"), Path("b.pes")))

# color_separate treats any colour in neither --layer nor --skip as background,
# so a raster spec with no layers stitches nothing at all and says so nowhere.
try:
    BLD.validate_spec({"name": "T", "build": {"tool": "inkstitch_pipeline",
                                              "input": "a.webp", "artwork_mm": 80}}, "T.json")
    check("a raster spec with no Layer is rejected", False, "no error raised")
except ValueError as exc:
    check("a raster spec with no Layer is rejected", "options.Layer" in str(exc), str(exc))

# One design may take a sibling's prepared derivative as its input. Filename
# order satisfied that by accident until the designs were renamed —
# IHeartScreaming_on_black sorts BEFORE _on_white, so alphabetical order would
# have digitized the previous run's intermediate instead of failing.
_producer = {"name": "Zebra", "prepare": {"tool": "t", "input": "art/originals/z.svg",
                                          "output": "art/prepared/shared.svg"},
             "build": {"tool": "svg_to_pes", "input": "art/prepared/shared.svg",
                       "artwork_mm": 90}}
_consumer = {"name": "Alpha", "prepare": {"tool": "t", "input": "art/prepared/shared.svg",
                                          "output": "art/prepared/alpha.svg"},
             "build": {"tool": "svg_to_pes", "input": "art/prepared/alpha.svg",
                       "artwork_mm": 90}}
_order = [s["name"] for s in BLD._in_dependency_order([_consumer, _producer])]
check("a spec reading another's prepare output builds after it, whatever it is called",
      _order == ["Zebra", "Alpha"], " -> ".join(_order))

_indep = [{"name": n, "build": {"tool": "svg_to_pes", "input": f"{n}.svg", "artwork_mm": 90}}
          for n in ("Cherry", "Apple", "Banana")]
check("independent specs stay in filename order",
      [s["name"] for s in BLD._in_dependency_order(_indep)] == ["Apple", "Banana", "Cherry"])

_a = {"name": "A", "prepare": {"tool": "t", "input": "art/prepared/b.svg",
                               "output": "art/prepared/a.svg"},
      "build": {"tool": "svg_to_pes", "input": "art/prepared/a.svg", "artwork_mm": 90}}
_b = {"name": "B", "prepare": {"tool": "t", "input": "art/prepared/a.svg",
                               "output": "art/prepared/b.svg"},
      "build": {"tool": "svg_to_pes", "input": "art/prepared/b.svg", "artwork_mm": 90}}
try:
    BLD._in_dependency_order([_a, _b])
    check("a dependency cycle is reported, not silently ordered", False, "no error")
except ValueError as exc:
    check("a dependency cycle is reported, not silently ordered", "cycle" in str(exc))

# A malformed spec must fail with the field named, before the prepare step has
# written anything.
for bad, want in [
    ({"name": "Wrong"}, "must match the filename"),
    ({"name": "T"}, "missing 'build'"),
    ({"name": "T", "build": {"tool": "svg_to_pes", "input": "a.svg"}}, "artwork_mm"),
    ({"name": "T", "build": {"tool": "nope", "input": "a.svg", "artwork_mm": 1}}, "unknown build tool"),
    ({"name": "T", "build": {"tool": "svg_to_pes", "input": "a.svg", "artwork_mm": "big"}}, "must be a number"),
    ({"name": "T", "build": {"tool": "svg_to_pes", "input": "a.svg", "artwork_mm": 1,
                             "skip": "FFFFFF"}}, "must be a list"),
    ({"name": "T", "build": {"tool": "svg_to_pes", "input": "a.svg", "artwork_mm": 1},
      "prepare": {"tool": "svg_subpath_filter", "input": "a.svg"}}, "missing 'output'"),
    ({"name": "T", "build": {"tool": "svg_to_pes", "input": "a.svg", "artwork_mm": 1},
      "prepare": {"tool": "no_such_tool", "input": "a", "output": "b"}}, "no such prepare tool"),
]:
    try:
        BLD.validate_spec(bad, "T.json")
        check(f"malformed spec rejected: {want}", False, "no error raised")
    except ValueError as e:
        check(f"malformed spec rejected: {want}", want in str(e), str(e))

# The manifest is the provenance record. Anything unreadable must degrade to
# "nothing is built" — every design then rebuilds, which is correct — rather
# than raising from a KeyError partway through a build.
_saved = BLD.MANIFEST
try:
    BLD.MANIFEST = TMP / "manifest.json"
    check("a missing manifest reads as no designs", BLD.read_manifest()["designs"] == {})
    BLD.MANIFEST.write_text("{ not json", encoding="utf-8")
    check("a corrupt manifest degrades instead of raising",
          BLD.read_manifest()["designs"] == {})
    BLD.MANIFEST.write_text('{"designs": null}', encoding="utf-8")
    check("a manifest with the wrong shape degrades too",
          BLD.read_manifest()["designs"] == {})
    BLD.MANIFEST.write_text('[1,2,3]', encoding="utf-8")
    check("a manifest that is not even an object degrades too",
          BLD.read_manifest()["designs"] == {})
    # Atomic write: no .tmp left behind, and the content round-trips.
    BLD.write_manifest({"designs": {"X": {"ok": True}}})
    check("the manifest round-trips", BLD.read_manifest()["designs"]["X"]["ok"] is True)
    check("the atomic write leaves no temp file behind",
          not BLD.MANIFEST.with_suffix(".json.tmp").exists())
finally:
    BLD.MANIFEST = _saved

# Staleness must notice each way a build can stop being trustworthy.
_specf = TMP / "SpecT.json"
_specf.write_text(json.dumps({"name": "SpecT", "build": {
    "tool": "svg_to_pes", "input": "x.svg", "artwork_mm": 91}}), encoding="utf-8")
check("a design with no record is stale",
      BLD.is_stale({"name": "SpecT", "_path": _specf}, None) == "never built")
check("a design whose output vanished is stale",
      BLD.is_stale({"name": "NoSuchDesign", "_path": _specf},
                   {"output": {"sha256": "x"}, "spec": {"sha256": "y"}, "inputs": []})
      == "output missing")

# --------------------------------------------------------------------------- #
section("svg path parsing")

from embroidery_tools.svgpath import parse_path, parse_transform, apply  # noqa: E402


def pts(d):
    return [p for s in parse_path(d) for p in s["points"]]


# A straight two-point rung and a rail that is one cubic both have two on-curve
# points. Telling them apart by point count is what broke satin width matching;
# the `curved` flag is the discriminator.
rung = parse_path("M 0,0 L 10,0")[0]
rail = parse_path("M 0,0 C 3,5 7,5 10,0")[0]
check("a straight segment is not marked curved", rung["curved"] is False)
check("a single cubic IS marked curved", rail["curved"] is True)
check("a cubic flattens to many points, not two", len(rail["points"]) > 5,
      str(len(rail["points"])))

check("relative commands track position",
      parse_path("M 10,10 l 5,0 l 0,5")[0]["points"][-1] == (15.0, 15.0),
      str(parse_path("M 10,10 l 5,0 l 0,5")[0]["points"][-1]))
check("H and V are honoured",
      parse_path("M 0,0 H 8 V 6")[0]["points"][-1] == (8.0, 6.0))
check("repeated pairs after M are implicit linetos",
      len(parse_path("M 0,0 1,0 2,0")[0]["points"]) == 3)
check("Z closes the subpath",
      parse_path("M 0,0 L 4,0 L 4,4 Z")[0]["closed"] is True)
check("multiple subpaths are separated",
      len(parse_path("M 0,0 L 1,0 M 5,5 L 6,5")) == 2)

# An arc is parsed via the endpoint-to-centre conversion, not approximated by a
# chord: a half-circle of radius 5 must bulge to y=5, not run straight across.
arc = parse_path("M 0,0 A 5,5 0 0 1 10,0")[0]
check("an arc bulges rather than collapsing to its chord",
      max(abs(p[1]) for p in arc["points"]) > 4.0,
      "max |y| = %.2f" % max(abs(p[1]) for p in arc["points"]))
check("an arc lands on its stated endpoint",
      math.dist(arc["points"][-1], (10.0, 0.0)) < 0.01)

# Silence is the enemy here: an unknown command must raise, not be skipped.
try:
    parse_path("M 0,0 K 5,5")
    check("an unknown path command raises rather than being skipped", False)
except ValueError:
    check("an unknown path command raises rather than being skipped", True)

check("scale transform composes",
      apply(parse_transform("scale(2)"), [(3.0, 4.0)])[0] == (6.0, 8.0))
check("translate transform composes",
      apply(parse_transform("translate(1,2)"), [(3.0, 4.0)])[0] == (4.0, 6.0))
check("nested transforms apply left to right",
      apply(parse_transform("translate(10,0) scale(2)"), [(3.0, 0.0)])[0] == (16.0, 0.0),
      str(apply(parse_transform("translate(10,0) scale(2)"), [(3.0, 0.0)])[0]))
_rot = apply(parse_transform("rotate(90)"), [(1.0, 0.0)])[0]
check("rotate transform composes", abs(_rot[0]) < 1e-9 and abs(_rot[1] - 1.0) < 1e-9,
      str(_rot))

# --------------------------------------------------------------------------- #
section("feature width measurement")

# Minimum feature size is the recurring defect here, so the thing that measures
# it gets shapes whose width is known by construction. Every case below broke a
# previous implementation.
from embroidery_tools.measure import widths_mm as _w  # noqa: E402

PPM_T = 10.0


def med_w(mask):
    return float(np.median(_w(mask, PPM_T)))


_yy, _xx = np.mgrid[0:200, 0:200]

bar = np.zeros((80, 200), bool)
bar[34:46, 20:180] = True
check("horizontal bar measures its true 1.2 mm", abs(med_w(bar) - 1.2) < 0.05, f"{med_w(bar):.2f}")

vbar = np.zeros((200, 80), bool)
vbar[20:180, 25:55] = True
check("vertical bar measures its true 3.0 mm", abs(med_w(vbar) - 3.0) < 0.05, f"{med_w(vbar):.2f}")

# A disc is the case that killed per-direction non-maximum suppression: its
# medial axis is a single point, and discretisation let interior pixels pass
# the ridge test, reporting 1.6 mm for a 4 mm disc.
disc = ((_yy[:120, :120] - 60) ** 2 + (_xx[:120, :120] - 60) ** 2) < 400
check("4 mm disc measures 4 mm, not its radius or less",
      abs(med_w(disc) - 4.0) < 0.05, f"{med_w(disc):.2f}")

# A star is the case that killed the 8-neighbour ridge: the distance transform
# climbs along every branch, so each branch pixel lost to the neighbour ahead
# and the whole shape returned five ridge pixels reading 0.10 mm.
star = np.zeros((160, 160), bool)
_im = Image.new("1", (160, 160), 0)
_pts = []
for _i in range(10):
    _a = -math.pi / 2 + _i * math.pi / 5
    _R = 70 if _i % 2 == 0 else 28
    _pts.append((80 + _R * math.cos(_a), 80 + _R * math.sin(_a)))
ImageDraw.Draw(_im).polygon(_pts, fill=1)
star = np.asarray(_im, bool)
check("a solid star is not mistaken for hairline detail",
      med_w(star) > 3.0, f"median {med_w(star):.2f} mm")
check("the star's widest part is its inscribed circle, not more",
      abs(float(np.max(_w(star, PPM_T))) - 5.6) < 0.3, f"{np.max(_w(star, PPM_T)):.2f}")

# Width is area-weighted: one sample per ink pixel, so "x% is under 1 mm" means
# x% of the actual ink, which is the question a digitizer is asking.
check("one width sample per ink pixel", _w(bar, PPM_T).size == int(bar.sum()))
check("an empty mask yields no samples, rather than a zero", _w(np.zeros((9, 9), bool), PPM_T).size == 0)

# A single-pixel hairline must report something, not vanish — it is exactly the
# case that needs flagging.
hair = np.zeros((40, 40), bool)
hair[20, 5:35] = True
check("a 1-px hairline still reports a width", med_w(hair) > 0, f"{med_w(hair):.2f}")

# Uniform shapes must be uniform: a bar has one width everywhere, so the spread
# across percentiles is what proves the measure is not sampling noise.
_bw = _w(bar, PPM_T)
check("a uniform bar measures uniformly across percentiles",
      float(np.percentile(_bw, 5)) == float(np.percentile(_bw, 95)),
      f"p5 {np.percentile(_bw, 5):.2f} p95 {np.percentile(_bw, 95):.2f}")

# --------------------------------------------------------------------------- #
section("short stitches")

# Sub-minimum stitches put two penetrations in nearly the same hole, which
# draws bobbin thread to the surface and saws the upper thread against the
# needle eye. raster.py filters them at generation time; files from anywhere
# else (Ink/Stitch, purchased designs) only get caught by validate.
check("min_stitch_mm comes from the profile, not a literal",
      prof.min_stitch_mm() == prof.load()["design_limits"]["min_stitch_mm"])
check("TraceSettings inherits the profile's floor",
      raster.TraceSettings().min_stitch_mm == prof.min_stitch_mm())

LONG = int(prof.mm_to_units(2.0))
TINY = int(prof.mm_to_units(0.2))


def make_run(n_lead: int, n_short: int, n_tail: int) -> pe.EmbPattern:
    """One run: normal stitches, a short burst mid-run, then normal again."""
    pat = pe.EmbPattern()
    x = 0
    for _ in range(n_lead):
        pat.add_stitch_absolute(pe.STITCH, x, 0)
        x += LONG
    for _ in range(n_short):
        pat.add_stitch_absolute(pe.STITCH, x, 0)
        x += TINY
    for _ in range(n_tail):
        pat.add_stitch_absolute(pe.STITCH, x, 0)
        x += LONG
    pat.add_thread(pe.EmbThread())
    pat.end()
    return pat


def describe_pattern(pat: pe.EmbPattern, name: str):
    f = TMP / name
    pe.write(pat, str(f))
    return analyze.describe(f)

i = describe_pattern(make_run(10, 6, 10), "short_mid.dst")
check("mid-run short stitches are counted", i.short_stitches_midrun >= 5,
      f"got {i.short_stitches_midrun}")
codes = {f.code: f for f in analyze.validate(i)}
check("mid-run shorts raise a warning",
      codes.get("short-stitches") is not None
      and codes["short-stitches"].severity == analyze.WARNING,
      str(codes.get("short-stitches")))

# Tie-in and tie-off are deliberately short and must stay short. Counting them
# as defects would flag every correctly locked design, and a validator that
# always warns gets ignored.
lock = pe.EmbPattern()
x = 0
for _ in range(3):                       # tie-in
    lock.add_stitch_absolute(pe.STITCH, x, 0)
    x += TINY
for _ in range(20):                      # body
    lock.add_stitch_absolute(pe.STITCH, x, 0)
    x += LONG
for _ in range(3):                       # tie-off
    lock.add_stitch_absolute(pe.STITCH, x, 0)
    x += TINY
lock.add_thread(pe.EmbThread())
lock.end()
i = describe_pattern(lock, "short_locks.dst")
check("lock stitches are not counted as defects", i.short_stitches_midrun == 0,
      f"midrun={i.short_stitches_midrun} of total short {i.short_stitches}")
check("lock stitches are still reported in the total", i.short_stitches > 0)
check("a correctly locked design raises no short-stitch warning",
      not any(f.code == "short-stitches" and f.severity == analyze.WARNING
              for f in analyze.validate(i)))

# The gap across a trim is not a stitch length.
gap = pe.EmbPattern()
gap.add_stitch_absolute(pe.STITCH, 0, 0)
gap.add_stitch_absolute(pe.STITCH, LONG, 0)
gap.add_stitch_absolute(pe.TRIM, LONG, 0)
gap.add_stitch_absolute(pe.STITCH, LONG + 1, 0)     # 0.1mm from the previous
gap.add_stitch_absolute(pe.STITCH, LONG + 1 + LONG, 0)
gap.add_thread(pe.EmbThread())
gap.end()
i = describe_pattern(gap, "short_gap.dst")
check("distance across a trim is not measured as a stitch",
      i.short_stitches == 0, f"got {i.short_stitches}")

# --------------------------------------------------------------------------- #
section("penetration density")

# The manual's own failure mode: "the thread may break or the needle may break
# or bend when embroidering with a stitch density that is too fine or when
# embroidering three or more overlapping stitches." Two needles broke here on
# cells measuring 45-52/mm^2; unchecked travel routing once reached 111.
check("density limits come from the profile",
      prof.design_limit("max_density_per_mm2") == 16
      and prof.design_limit("density_danger_per_mm2") == 30)
check("TraceSettings inherits the density cap",
      raster.TraceSettings().max_density_per_mm2
      == prof.design_limit("max_density_per_mm2"))

STEP = int(prof.mm_to_units(2.0))
DANGER = int(prof.design_limit("density_danger_per_mm2", 30))

# A sane design: stitches spread out, one penetration per cell.
spread = pe.EmbPattern()
for i in range(200):
    spread.add_stitch_absolute(pe.STITCH, (i % 20) * STEP, (i // 20) * STEP)
spread.add_thread(pe.EmbThread())
spread.end()
i = describe_pattern(spread, "dens_ok.dst")
check("a spread-out design reports a low peak", i.density_max <= 2, f"{i.density_max}")
check("a spread-out design raises no density finding",
      not any(f.code == "density-peak" for f in analyze.validate(i)))

# A hot spot: many penetrations piled into one square millimetre, which is what
# travel routing through already-stitched ground produces.
hot = pe.EmbPattern()
for i in range(200):
    hot.add_stitch_absolute(pe.STITCH, (i % 20) * STEP, (i // 20) * STEP)
for i in range(DANGER + 5):                      # all inside one 1 mm cell
    hot.add_stitch_absolute(pe.STITCH, 1 + (i % 3), 1 + (i % 2))
hot.add_thread(pe.EmbThread())
hot.end()
i = describe_pattern(hot, "dens_hot.dst")
check("a hot spot is measured", i.density_max >= DANGER, f"{i.density_max}")
check("cells past the danger line are counted", i.density_cells_danger >= 1)
codes = {f.code: f for f in analyze.validate(i)}
check("a hot spot raises a density warning",
      codes.get("density-peak") is not None
      and codes["density-peak"].severity == analyze.WARNING,
      str(codes.get("density-peak")))
# Averages hide this completely -- that is why the check uses peak and counts.
check("the median stays normal even with a lethal peak",
      i.density_cells > 0 and i.density_max / max(1, i.density_cells) < 1.0)

# --------------------------------------------------------------------------- #
section("satin coverage")

# A satin column's neighbouring stitches are single threads laid side by side.
# Spaced wider than a thread is thick they do not overlap, and fabric — plus the
# bobbin thread crossing underneath — shows between them. A build shipped with
# 0.41 mm spacing against a 0.40 mm thread and the white bobbin swamped the
# black. Renders cannot show this: a sparse comb draws identically to a solid
# column, which is how it passed review.
DENSITY = prof.design_limit("fill_density_mm")
SPARSE = DENSITY * prof.design_limit("satin_sparse_factor")
check("satin coverage is judged against the validated fill density",
      DENSITY == 0.4 and SPARSE > DENSITY)
# The check must NOT flag the density this repo itself calls correct, nor
# Ink/Stitch's own default satin. An earlier version compared against a
# separate 0.4 mm "thread width" and did both, which sent a diagnosis down
# the wrong path for two stitch-outs.
check("the validated density is not itself treated as a defect", DENSITY < SPARSE)

COL_W = int(prof.mm_to_units(2.0))          # a 2 mm wide column


def satin(advance_mm: float, n: int = 120) -> pe.EmbPattern:
    """Zigzag column whose SAME-RAIL advance is advance_mm."""
    step = prof.mm_to_units(advance_mm) / 2.0     # i and i+2 differ by 2*step
    pat = pe.EmbPattern()
    for i in range(n):
        pat.add_stitch_absolute(pe.STITCH, int(i * step), 0 if i % 2 == 0 else COL_W)
    pat.add_thread(pe.EmbThread())
    pat.end()
    return pat


i = describe_pattern(satin(0.25), "satin_tight.dst")
check("tight satin is detected as satin", i.satin_pairs >= 50, f"{i.satin_pairs}")
check("tight satin raises no coverage finding",
      not any(f.code == "satin-coverage" for f in analyze.validate(i)))

# Satin at exactly the validated fill density must be accepted: it is the same
# geometry as a fill rotated 90 degrees, and it is Ink/Stitch's own default.
i = describe_pattern(satin(DENSITY), "satin_default.dst")
check("satin at the validated density raises no warning",
      not any(f.code == "satin-coverage" and f.severity == analyze.WARNING
              for f in analyze.validate(i)),
      f"median {i.satin_advance_p50_mm:.2f}")

i = describe_pattern(satin(SPARSE * 1.6), "satin_sparse.dst")
check("genuinely sparse satin is detected as satin", i.satin_pairs >= 50,
      f"{i.satin_pairs}")
codes = {f.code: f for f in analyze.validate(i)}
check("genuinely sparse satin raises a coverage warning",
      codes.get("satin-coverage") is not None
      and codes["satin-coverage"].severity == analyze.WARNING,
      str(codes.get("satin-coverage")))

# False positives are the real risk: a validator that cries wolf gets ignored.
# A serpentine fill reverses at the end of every row and tie-offs reverse in
# place, and an earlier version counted both — scream2, which contains no satin
# at all, reported 1,176 satin pairs and tripped the warning.
serp = pe.EmbPattern()
row_step = int(prof.mm_to_units(0.4))
x_step = int(prof.mm_to_units(3.0))
for row in range(24):
    xs = range(12) if row % 2 == 0 else range(11, -1, -1)
    for cx in xs:
        serp.add_stitch_absolute(pe.STITCH, cx * x_step, row * row_step)
serp.add_thread(pe.EmbThread())
serp.end()
i = describe_pattern(serp, "satin_serpentine.dst")
check("a serpentine fill is NOT counted as satin", i.satin_pairs == 0,
      f"{i.satin_pairs} pairs")
check("a serpentine fill raises no coverage finding",
      not any(f.code == "satin-coverage" for f in analyze.validate(i)))

# Locks reverse in place; the column-width floor must exclude them.
locks = pe.EmbPattern()
tiny = int(prof.mm_to_units(0.6))
for i2 in range(40):
    locks.add_stitch_absolute(pe.STITCH, (i2 % 2) * tiny, 0)
locks.add_thread(pe.EmbThread())
locks.end()
i = describe_pattern(locks, "satin_locks.dst")
check("in-place lock reversals are NOT counted as satin", i.satin_pairs == 0,
      f"{i.satin_pairs} pairs")

# The generators must tell Ink/Stitch the floor; without it nothing filters.
for f in sep_dir.glob("L*.svg"):
    root = ET.parse(f).getroot()
    el = root.find(f"{{{SVG_NS}}}metadata/{{{INK_NS}}}min_stitch_len_mm")
    check(f"{f.name}: declares min_stitch_len_mm",
          el is not None and float(el.text) == prof.min_stitch_mm())

if out_svg.exists():
    el = ET.parse(out_svg).getroot().find(
        f"{{{SVG_NS}}}metadata/{{{INK_NS}}}min_stitch_len_mm")
    check("merged document declares min_stitch_len_mm (it is what gets exported)",
          el is not None and float(el.text) == prof.min_stitch_mm())

# --------------------------------------------------------------------------- #
section("dark-cloth variants: recolor, knockout, invert")

import subprocess  # noqa: E402

from embroidery_tools import svgpath  # noqa: E402

DARK = TMP / "dark"
DARK.mkdir(exist_ok=True)


def run_tool(name: str, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / f"{name}.py"), *[str(a) for a in args]],
                          capture_output=True, text=True)


# px per mm. PIL fills a polygon inclusively, so the residual error is one pixel
# of perimeter — and the tolerances below have to stay well inside the smallest
# defect being tested. At 8 px/mm the XOR-cancellation bug lands 27 mm2 from the
# right answer, which is close enough to the discretisation error to slip past.
EO_SCALE = 16.0


def eo_area(d: str):
    """Even-odd area of a polyline path, by XOR raster — the same test the
    tools use, so a sign or nesting error shows up as area, not as a crash."""
    subs = [s["points"] for s in svgpath.parse_path(d) if len(s["points"]) >= 3]
    pts = [p for s in subs for p in s]
    w = int(max(p[0] for p in pts) * EO_SCALE) + 4
    h = int(max(p[1] for p in pts) * EO_SCALE) + 4
    acc = np.zeros((h, w), bool)
    for s in subs:
        img = Image.new("1", (w, h), 0)
        ImageDraw.Draw(img).polygon(
            [(x * EO_SCALE + 2, y * EO_SCALE + 2) for x, y in s], fill=1)
        acc ^= np.asarray(img, bool)
    return float(acc.sum()) / EO_SCALE**2, acc


def box(mask, x0, y0, x1, y1):
    """The mm rectangle (x0,y0)-(x1,y1) of an eo_area mask."""
    return mask[int(y0 * EO_SCALE) + 2:int(y1 * EO_SCALE) + 2,
                int(x0 * EO_SCALE) + 2:int(x1 * EO_SCALE) + 2]


def sq(x0, y0, x1, y1) -> str:
    return f"M {x0} {y0} L {x1} {y0} L {x1} {y1} L {x0} {y1} Z"


SVG_HDR = ('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" '
           'viewBox="0 0 100 100">')

# --- svg_recolor ----------------------------------------------------------- #
src = DARK / "recolor_in.svg"
src.write_text(f'{SVG_HDR}<g stroke="#000000"><path id="a" d="{sq(10, 10, 40, 40)}" '
               f'fill="#000000"/><path id="b" d="{sq(50, 50, 90, 90)}" fill="#FF0000" '
               'style="stroke:#000000"/></g></svg>', encoding="utf-8")

dst = DARK / "recolor_out.svg"
r = run_tool("svg_recolor", src, dst, "--map", "000000=FFFFFF")
check("svg_recolor: succeeds", r.returncode == 0, r.stderr[-200:])
if dst.exists():
    txt = dst.read_text(encoding="utf-8")
    check("svg_recolor: remaps fill", 'fill="#FFFFFF"' in txt)
    check("svg_recolor: remaps a stroke inherited from a <g>",
          'stroke="#FFFFFF"' in txt)
    check("svg_recolor: remaps paint inside style=", "stroke:#FFFFFF" in txt)
    check("svg_recolor: leaves unmapped colours alone", 'fill="#FF0000"' in txt)

# A remap matching nothing means the design keeps the colour you meant to change.
r = run_tool("svg_recolor", src, DARK / "x.svg", "--map", "123456=FFFFFF")
check("svg_recolor: refuses a map that matches nothing", r.returncode != 0)
r = run_tool("svg_recolor", src, DARK / "x.svg", "--map", "notahex=FFFFFF")
check("svg_recolor: refuses malformed hex rather than guessing", r.returncode != 0)

# PES merges adjacent blocks sharing a colour: two layers onto one hex is one
# stop and one pass, not two. It may be intended, but it must never be silent.
r = run_tool("svg_recolor", src, DARK / "merge.svg", "--map", "FF0000=000000")
check("svg_recolor: warns when a remap collapses two colours into one",
      "WARNING" in r.stdout and "merges" in r.stdout, r.stdout[-200:])

# --- svg_knockout ---------------------------------------------------------- #
# The LemonB bug: a light shape drawn OVER a darker fill is stitched UNDER it,
# because svg_prep orders by luminance and not by document order.
src = DARK / "knock_in.svg"
src.write_text(f'{SVG_HDR}<path id="body" d="{sq(0, 0, 100, 100)}" fill="#FFD400"/>'
               f'<path id="eye" d="{sq(20, 20, 40, 40)}" fill="#FFFFFF"/></svg>',
               encoding="utf-8")
dst = DARK / "knock_out.svg"
r = run_tool("svg_knockout", src, dst, "--knock", "FFFFFF=FFD400")
check("svg_knockout: succeeds", r.returncode == 0, r.stderr[-200:])
if dst.exists():
    root = ET.parse(dst).getroot()
    body = next(p for p in root.iter(f"{{{SVG_NS}}}path") if p.get("id") == "body")
    check("svg_knockout: host becomes even-odd", body.get("fill-rule") == "evenodd")
    area, _ = eo_area(body.get("d"))
    # 100x100 minus the 20x20 eye. If the hole were merely appended without
    # even-odd, or appended with the same winding, this stays 10,000.
    check("svg_knockout: the punched area is really gone from the host",
          abs(area - (10000 - 400)) < 25, f"{area:.0f} mm2, expected ~9600")
    eye = next(p for p in root.iter(f"{{{SVG_NS}}}path") if p.get("id") == "eye")
    check("svg_knockout: the punch itself stays stitchable", eye.get("d") is not None)

# Registration, not validity: a punch outside its host parses and renders fine.
src2 = DARK / "knock_bad.svg"
src2.write_text(f'{SVG_HDR}<path d="{sq(0, 0, 30, 30)}" fill="#FFD400"/>'
                f'<path d="{sq(60, 60, 80, 80)}" fill="#FFFFFF"/></svg>', encoding="utf-8")
r = run_tool("svg_knockout", src2, DARK / "x.svg", "--knock", "FFFFFF=FFD400")
check("svg_knockout: refuses a punch that is not inside its host", r.returncode != 0)
r = run_tool("svg_knockout", src, DARK / "x.svg", "--knock", "00FF00=FFD400")
check("svg_knockout: refuses a punch colour that is absent", r.returncode != 0)

# --- svg_dark_invert ------------------------------------------------------- #
# One hole over bare cloth, one over green, and a hole->island->hole nest.
ink = " ".join([
    sq(0, 0, 100, 100),        # depth 0, the ink mass
    sq(10, 10, 30, 30),        # depth 1, over nothing      -> recovered
    sq(60, 10, 80, 30),        # depth 1, over green        -> left alone
    sq(10, 60, 40, 90),        # depth 1, over nothing      -> recovered
    sq(18, 68, 32, 82),        # depth 2, island inside it  -> hole in the white
    sq(22, 72, 28, 78),        # depth 3, inside the island -> white again
])
src = DARK / "invert_in.svg"
src.write_text(f'{SVG_HDR}<path d="{sq(55, 5, 85, 35)}" fill="#73B236"/>'
               f'<path d="{ink}" fill="#000000" fill-rule="evenodd"/></svg>',
               encoding="utf-8")
dst = DARK / "invert_out.svg"
r = run_tool("svg_dark_invert", src, dst, "--artwork-mm", "100",
             "--ink", "000000", "--thread", "FFFFFF")
check("svg_dark_invert: succeeds", r.returncode == 0, r.stderr[-300:])
if dst.exists():
    root = ET.parse(dst).getroot()
    fills = {p.get("fill"): p for p in root.iter(f"{{{SVG_NS}}}path")}
    check("svg_dark_invert: drops the ink layer by default", "#000000" not in fills)
    check("svg_dark_invert: keeps the other colours", "#73B236" in fills)
    check("svg_dark_invert: adds the recovered layer", "#FFFFFF" in fills)
    if "#FFFFFF" in fills:
        area, mask = eo_area(fills["#FFFFFF"].get("d"))
        # 400 (plain hole) + 900 - 196 + 36 (the nest). A hole over green would
        # add 400 more; re-emitting the depth-3 subpath top-level would XOR its
        # 36 back out. Both failure modes are visible here and nowhere else.
        check("svg_dark_invert: recovers exactly the bare-cloth area",
              abs(area - 1140) < 15, f"{area:.0f} mm2, expected 1140 "
              "(1108 means the depth-3 subpath was emitted twice and XORed out)")
        check("svg_dark_invert: leaves the hole that sits over another colour",
              not box(mask, 62, 12, 78, 28).any(), "white was stitched under the green")
        check("svg_dark_invert: the island inside a recovered hole stays bare",
              not box(mask, 19, 69, 21, 71).any())
        check("svg_dark_invert: a hole inside that island is recovered again",
              box(mask, 24, 74, 26, 76).all())

r = run_tool("svg_dark_invert", src, DARK / "x.svg", "--artwork-mm", "100",
             "--ink", "000000", "--thread", "73B236")
check("svg_dark_invert: refuses a thread colour already in the document",
      r.returncode != 0)

r = run_tool("svg_dark_invert", src, DARK / "keep.svg", "--artwork-mm", "100",
             "--ink", "000000", "--keep-ink")
if r.returncode == 0:
    kept = {p.get("fill") for p in ET.parse(DARK / "keep.svg").getroot().iter(f"{{{SVG_NS}}}path")}
    check("svg_dark_invert: --keep-ink keeps the ink layer", "#000000" in kept)

# Re-emitting curves as polylines would silently flatten them, and nothing
# downstream can tell a deliberately faceted curve from a damaged one.
curved = DARK / "invert_curved.svg"
curved.write_text(f'{SVG_HDR}<path d="M 10 10 C 20 0 40 0 50 10 L 50 50 L 10 50 Z" '
                  'fill="#000000"/></svg>', encoding="utf-8")
r = run_tool("svg_dark_invert", curved, DARK / "x.svg", "--artwork-mm", "100",
             "--ink", "000000")
check("svg_dark_invert: refuses curved artwork rather than flattening it",
      r.returncode != 0 and "curved" in (r.stdout + r.stderr))

# --------------------------------------------------------------------------- #
section("shape parsing beyond <path>")

# Reading only <path> is a silent-partial-application bug: LemonCat's prepared
# SVG draws ear tufts as <polygon> and pupils as <ellipse>, both filled #000000.
# A tool that walked paths alone would report that layer smaller than it is and
# would offset only part of it, which validate and coverage cannot see.
subs = svgpath.parse_shape("polygon", {"points": "0,0 10,0 10,10 0,10"})
check("parse_shape: polygon becomes one closed subpath",
      subs is not None and len(subs) == 1 and subs[0]["closed"]
      and len(subs[0]["points"]) == 4)

subs = svgpath.parse_shape("circle", {"cx": "5", "cy": "5", "r": "3"})
xs = [p[0] for p in subs[0]["points"]]
check("parse_shape: circle spans 2r", abs((max(xs) - min(xs)) - 6.0) < 0.1,
      f"{max(xs) - min(xs)}")

subs = svgpath.parse_shape("ellipse", {"cx": "0", "cy": "0", "rx": "4", "ry": "2"})
ys = [p[1] for p in subs[0]["points"]]
check("parse_shape: ellipse honours rx and ry separately",
      abs((max(ys) - min(ys)) - 4.0) < 0.1)

subs = svgpath.parse_shape("rect", {"x": "1", "y": "2", "width": "10", "height": "4"})
check("parse_shape: rect becomes its four corners",
      len(subs[0]["points"]) == 4 and subs[0]["points"][2] == (11.0, 6.0))

try:
    svgpath.parse_shape("rect", {"width": "10", "height": "4", "rx": "2"})
    check("parse_shape: rounded rect raises rather than squaring the corners", False)
except ValueError:
    check("parse_shape: rounded rect raises rather than squaring the corners", True)

# None and [] must stay distinguishable: "not a fillable shape" is not the same
# answer as "a shape enclosing no area", and a caller decides differently.
check("parse_shape: returns None for a tag with no fillable interior",
      svgpath.parse_shape("line", {"x1": "0", "y1": "0", "x2": "5", "y2": "5"}) is None)
check("parse_shape: returns [] for a degenerate shape",
      svgpath.parse_shape("rect", {"width": "0", "height": "4"}) == [])

# --------------------------------------------------------------------------- #
section("thin-area fraction")

from embroidery_tools import measure  # noqa: E402

# A 16 px bar at 10 px/mm is 1.6 mm wide under the width = 2*edt convention.
bar = np.zeros((60, 200), bool)
bar[20:36, 10:190] = True
check("frac_below_mm: nothing is thin below the bar's own width",
      measure.frac_below_mm(bar, 10.0, 1.45) < 0.05,
      f"{measure.frac_below_mm(bar, 10.0, 1.45):.3f}")
check("frac_below_mm: everything is thin above it",
      measure.frac_below_mm(bar, 10.0, 1.75) > 0.95,
      f"{measure.frac_below_mm(bar, 10.0, 1.75):.3f}")

# The reason this exists rather than thresholding widths_mm: thickness_map steps
# radii by one pixel, so every width it can report is a multiple of 2 px —
# 0.2 mm here. 1.45 and 1.75 fall strictly between two of those steps, so no
# percentile of the swept distribution can separate them, while an erosion at
# exactly target/2 px can.
w = measure.widths_mm(bar, 10.0, max_mm=4.0)
steps = sorted(set(np.round(w, 6)))
check("frac_below_mm: the swept distribution only lands on 2 px multiples",
      all(abs(v / 0.2 - round(v / 0.2)) < 1e-6 for v in steps),
      f"{steps[:5]}")
check("frac_below_mm: the bar's own width is the 1.6 mm the convention implies",
      abs(float(np.median(w)) - 1.6) < 1e-6, f"{float(np.median(w))}")

check("frac_below_mm: an empty mask has no thin area",
      measure.frac_below_mm(np.zeros((10, 10), bool), 10.0, 1.0) == 0.0)

# --------------------------------------------------------------------------- #
section("svg_offset / svg_stroke")

OFF = TMP / "offset"
OFF.mkdir(exist_ok=True)

# Ink spans x 10..90, so --artwork-mm 80 makes one user unit exactly one mm and
# every number below can be checked by hand.
OFF_SRC = OFF / "in.svg"
OFF_SRC.write_text(
    SVG_HDR
    + '<path id="thin" d="M 10 10 L 90 10 L 90 10.6 L 10 10.6 Z" fill="#111111"/>'
    + '<path id="pair" d="M 10 20 L 90 20 L 90 21 L 10 21 Z '
      'M 10 21.8 L 90 21.8 L 90 22.8 L 10 22.8 Z" fill="#222222"/>'
    + '<path id="holed" fill-rule="evenodd" d="M 10 30 L 30 30 L 30 50 L 10 50 Z '
      'M 19 39 L 21 39 L 21 41 L 19 41 Z" fill="#333333"/>'
    + '<polygon id="tuft" points="40,60 50,60 45,70" fill="#555555"/>'
    + "</svg>", encoding="utf-8")
MM = ("--artwork-mm", "80")


def off_paths(p: Path) -> dict:
    """Every path in an output file, by fill colour."""
    return {el.get("fill"): el for el in ET.parse(p).getroot().iter(f"{{{SVG_NS}}}path")}


def off_bbox(d: str) -> tuple[float, float, float, float]:
    """Exact bounds of an offset result — the crispest check there is.

    Area has to be measured through `eo_area`'s raster, which over-reports by
    about one pixel along the perimeter (~4 mm2 on a 164 mm outline at 16 px/mm)
    and so can only carry a loose tolerance. The bounding box of a Minkowski sum
    is exact arithmetic: growing by r moves every extreme out by exactly r.
    """
    pts = [pt for s in svgpath.parse_path(d) for pt in s["points"]]
    return (min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts))


r = run_tool("svg_offset", OFF_SRC, OFF / "rep.svg", *MM, "--report")
check("svg_offset: --report succeeds and sees every colour",
      r.returncode == 0 and all(c in r.stdout for c in ("#111111", "#555555")),
      r.stderr[-200:])

# A 0.6 x 80 mm bar grown 0.3 mm all round: 48 -> 80.6*1.2 + pi*0.09 = 96.7 mm2.
dst = OFF / "grow.svg"
r = run_tool("svg_offset", OFF_SRC, dst, *MM, "--grow", "111111=0.3")
check("svg_offset: grows a thin bar", r.returncode == 0, r.stderr[-300:])
if dst.exists():
    d = off_paths(dst)["#111111"].get("d")
    bb = off_bbox(d)
    check("svg_offset: every extreme moves out by exactly the offset",
          max(abs(a - b) for a, b in zip(bb, (9.7, 9.7, 90.3, 10.9))) < 0.005,
          f"{tuple(round(v, 3) for v in bb)}")
    # Minkowski sum of an 80 x 0.6 rectangle with a 0.3 disc:
    # 80*0.6 + 2*0.3*80.6 + pi*0.3^2 = 96.64. eo_area reads ~4 mm2 high, being
    # one pixel of a 164 mm perimeter at 16 px/mm.
    area, _ = eo_area(d)
    check("svg_offset: grown area matches the Minkowski sum",
          abs(area - 96.64) < 6.0, f"{area:.1f} mm2, expected 96.6 +/- raster bias")

# Two 1 mm bars 0.8 mm apart merge into one when each grows 0.5 mm. Invisible in
# a render at design size, invisible to validate — so it must be an error.
dst = OFF / "merged.svg"
r = run_tool("svg_offset", OFF_SRC, dst, *MM, "--grow", "222222=0.5")
check("svg_offset: refuses a grow that merges two shapes",
      r.returncode != 0 and "topology" in (r.stdout + r.stderr))
check("svg_offset: writes nothing when it refuses", not dst.exists())

r = run_tool("svg_offset", OFF_SRC, dst, *MM, "--grow", "222222=0.5",
             "--allow-topology-change")
check("svg_offset: --allow-topology-change lets the merge through",
      r.returncode == 0 and dst.exists(), r.stderr[-300:])

# A 2 mm hole closes when the shape around it grows 1.1 mm.
r = run_tool("svg_offset", OFF_SRC, OFF / "closed.svg", *MM, "--grow", "333333=1.1")
check("svg_offset: refuses a grow that closes a hole",
      r.returncode != 0 and "hole" in (r.stdout + r.stderr))

# ...and a smaller grow must leave it open. Even-odd has to survive the round
# trip through Shapely, or the hole silently fills with thread.
dst = OFF / "hole_kept.svg"
r = run_tool("svg_offset", OFF_SRC, dst, *MM, "--grow", "333333=0.2")
check("svg_offset: a grow that clears the hole succeeds", r.returncode == 0,
      r.stderr[-300:])
if dst.exists():
    area, mask = eo_area(off_paths(dst)["#333333"].get("d"))
    check("svg_offset: the hole is still a hole", not box(mask, 19.8, 39.8, 20.2, 40.2).any())
    # Outer 20x20 grown 0.2: 400 + 2*0.2*40 + pi*0.04 = 416.13. The 2x2 hole
    # erodes to 1.6x1.6 less its rounded corners: 2.56 - (4-pi)*0.04 = 2.53.
    check("svg_offset: holed area matches the Minkowski sum",
          abs(area - 413.6) < 6.0, f"{area:.1f} mm2, expected 413.6 +/- raster bias")

dst = OFF / "shrunk.svg"
r = run_tool("svg_offset", OFF_SRC, dst, *MM, "--grow", "333333=-0.2")
if r.returncode == 0 and dst.exists():
    area, _ = eo_area(off_paths(dst)["#333333"].get("d"))
    check("svg_offset: a negative grow shrinks", area < 396.0, f"{area:.1f} mm2")

# An offset ellipse is not an ellipse. Leaving the tag alone would keep the old
# geometry attributes and a renderer would draw the shape it used to be.
dst = OFF / "tuft.svg"
r = run_tool("svg_offset", OFF_SRC, dst, *MM, "--grow", "555555=0.3")
if r.returncode == 0 and dst.exists():
    root_ = ET.parse(dst).getroot()
    check("svg_offset: an offset polygon is retagged as a path",
          not list(root_.iter(f"{{{SVG_NS}}}polygon")) and "#555555" in off_paths(dst))

# Geometry in the wrong place still renders as a plausible drawing and still
# stitches — the vtracer registration bug. Refused rather than ignored.
tf = OFF / "transformed.svg"
tf.write_text(SVG_HDR + '<g transform="scale(2)"><path d="M 10 10 L 90 10 L 90 12 '
              'L 10 12 Z" fill="#111111"/></g></svg>', encoding="utf-8")
r = run_tool("svg_offset", tf, OFF / "x.svg", *MM, "--grow", "111111=0.3")
check("svg_offset: refuses a transform rather than offsetting in the wrong frame",
      r.returncode != 0 and "transform" in (r.stdout + r.stderr))

# --- svg_stroke ------------------------------------------------------------ #
r = run_tool("svg_stroke", OFF_SRC, OFF / "s_thin.svg", *MM, "--stroke", "333333=0.7")
check("svg_stroke: refuses a stroke below the satin minimum",
      r.returncode != 0 and "minimum" in (r.stdout + r.stderr))

r = run_tool("svg_stroke", OFF_SRC, OFF / "s_thin.svg", *MM,
             "--stroke", "333333=0.7", "--allow-thin")
check("svg_stroke: --allow-thin overrides it", r.returncode == 0, r.stderr[-300:])

dst = OFF / "s_key.svg"
r = run_tool("svg_stroke", OFF_SRC, dst, *MM, "--stroke", "333333=1.4:EE2028")
check("svg_stroke: strokes in another colour", r.returncode == 0, r.stderr[-300:])
if dst.exists():
    el = off_paths(dst)["#333333"]
    # One user unit is one mm here, so the written width is the requested one.
    check("svg_stroke: stroke-width is written in user units",
          abs(float(el.get("stroke-width")) - 1.4) < 1e-6, el.get("stroke-width"))
    check("svg_stroke: stroke colour is the one asked for", el.get("stroke") == "#EE2028")
    check("svg_stroke: a new colour is called out",
          "new colour" in r.stdout and "#EE2028" in r.stdout)

# style beats a presentation attribute in a renderer and loses in svg_prep.prop,
# so leaving a stale declaration behind makes the render and the stitch file
# disagree about a colour — and the render is what gets trusted.
styled = OFF / "styled.svg"
styled.write_text(SVG_HDR + '<path d="M 10 10 L 90 10 L 90 30 L 10 30 Z" '
                  'fill="#333333" style="stroke:none;fill-opacity:1"/></svg>',
                  encoding="utf-8")
dst = OFF / "s_style.svg"
r = run_tool("svg_stroke", styled, dst, *MM, "--stroke", "333333=1.4")
if r.returncode == 0 and dst.exists():
    el = off_paths(dst)["#333333"]
    check("svg_stroke: clears a conflicting style declaration",
          "stroke" not in (el.get("style") or "") and el.get("stroke") == "#333333",
          f"style={el.get('style')!r} stroke={el.get('stroke')!r}")
    check("svg_stroke: leaves unrelated style declarations alone",
          "fill-opacity" in (el.get("style") or ""))

# --------------------------------------------------------------------------- #
section("svgdoc / svgops: atomic operations")

from embroidery_tools import svgops  # noqa: E402
from embroidery_tools.svgdoc import Doc  # noqa: E402

OPS = TMP / "ops"
OPS.mkdir(exist_ok=True)

# A group-level stroke, which is how LemonCat is drawn. Body 0..60 wide with a
# 4-unit stroke gives a 64-unit bbox, so --artwork-mm 64 makes one unit one mm.
GROUPED = OPS / "grouped.svg"
GROUPED.write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" '
    'viewBox="-10 -10 100 100"><g stroke="#000000" stroke-width="4">'
    f'<path id="body" d="{sq(0, 0, 60, 40)}" fill="#FFD400"/>'
    f'<path id="mark" d="{sq(20, 10, 40, 14)}" fill="#000000" stroke="none"/>'
    "</g></svg>", encoding="utf-8")

doc = Doc.load(GROUPED, 64.0)
check("svgdoc: resolves a stroke declared on an ancestor <g>",
      any(r.kind == "stroke" and r.colour == "000000" for r in doc.regions))
# SVG's initial stroke is `none`, unlike fill. Defaulting it to black gave every
# unstroked element a phantom hairline and invented 22 cloth pockets from nothing.
check("svgdoc: an explicit stroke=none makes no phantom stroke region",
      len([r for r in doc.regions if r.kind == "stroke"]) == 1,
      f"{[(r.colour, r.kind) for r in doc.regions]}")
check("svgdoc: one element yields both a fill and a stroke region",
      len([r for r in doc.regions if r.el.get('id') == 'body']) == 2)

before_black = doc.mm2(doc.geom_of("000000"))
svgops.OPS["subtract"]["fn"](doc, colour="FFD400", by="000000")
# `d` is shared by an element's fill and its stroke, so reshaping the fill drags
# the outline with it — the body's own keyline came to re-trace every internal
# cut, tripling the black region and over-cutting the next layer.
check("svgops: subtract does not inflate the cutting colour",
      abs(doc.mm2(doc.geom_of("000000")) - before_black) < 1.0,
      f"black {before_black:.0f} -> {doc.mm2(doc.geom_of('000000')):.0f} mm2")
check("svgops: the stroke survives the fill being reshaped",
      any(r.kind == "stroke" and r.colour == "000000" for r in doc.regions))

# A whole layer in ONE path is the normal case, not the exception: PissMuffy's
# 29 letters, eyes, brows and mouth share a single <path>, so an element-level
# filter matches the centroid of the entire design and selects nothing.
BANDED = OPS / "banded.svg"
BANDED.write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" '
    'viewBox="0 0 100 100">'
    f'<path id="both" fill="#000000" d="{sq(0, 0, 20, 10)} {sq(0, 80, 20, 90)}"/>'
    "</svg>", encoding="utf-8")
doc = Doc.load(BANDED, 20.0)
check("svgdoc: two disjoint subpaths are one region", len(doc.regions) == 1)
svgops.OPS["recolour"]["fn"](doc, colour="000000", to="FFFFFF", band=(0.0, 20.0))
cols = doc.colours()
check("svgops: --band splits one element by COMPONENT",
      abs(cols.get("FFFFFF", 0) - 200) < 5 and abs(cols.get("000000", 0) - 200) < 5,
      f"{ {k: round(v) for k, v in cols.items()} }")

doc = Doc.load(BANDED, 20.0)
try:
    svgops.OPS["recolour"]["fn"](doc, colour="000000", to="FFFFFF", band=(40.0, 60.0))
    check("svgops: a band matching nothing is an error, not a silent no-op", False)
except SystemExit:
    check("svgops: a band matching nothing is an error, not a silent no-op", True)

# Dropped on GROUPED rather than BANDED: `mark` is black-only and must vanish,
# while `body` carries a black stroke AND a yellow fill and must survive with
# just the stroke removed. Absent `fill` means black and absent `stroke` means
# none — reading those the same way leaves emptied elements painting black.
doc = Doc.load(GROUPED, 64.0)
svgops.OPS["drop"]["fn"](doc, colour="000000")
ids = {el.get("id") for el in doc.tree.getroot().iter(f"{{{SVG_NS}}}path")}
check("svgops: drop removes an element whose only paint is gone", "mark" not in ids)
check("svgops: drop keeps an element that still has another paint", "body" in ids)
check("svgops: drop leaves no black behind", "000000" not in doc.colours())

# --- end to end through the driver ----------------------------------------- #
dst = OPS / "out.svg"
# --log-dir keeps the test out of the repo's build/. Without it the log defaults
# to build/ops/, which is right for a real build and wrong for a test run.
r = run_tool("svg_edit", GROUPED, dst, "--artwork-mm", "64", "--log-dir", OPS,
             "--op", "subtract --colour FFD400 --by 000000",
             "--op", "drop --colour 000000")
check("svg_edit: applies a sequence", r.returncode == 0, r.stderr[-300:])
log = OPS / (dst.stem + ".ops.jsonl")
check("svg_edit: writes an op log", log.exists(), str(log))

if log.exists():
    dst2 = OPS / "replay.svg"
    r = run_tool("svg_edit", GROUPED, dst2, "--artwork-mm", "64",
                 "--log-dir", OPS, "--replay", log)
    # The log IS the declaration; if replay drifted it would be worthless as one.
    check("svg_edit: --replay reproduces the output byte for byte",
          r.returncode == 0 and dst2.exists()
          and dst2.read_bytes() == dst.read_bytes(), r.stderr[-200:])

r = run_tool("svg_edit", GROUPED, OPS / "x.svg", "--artwork-mm", "64",
             "--op", "subtract --colour ABCDEF --by 000000")
check("svg_edit: an op matching nothing fails loudly",
      r.returncode != 0 and "ABCDEF" in (r.stdout + r.stderr))

r = run_tool("svg_edit", GROUPED, OPS / "x.svg", "--artwork-mm", "64",
             "--op", "nosuchop --colour 000000")
check("svg_edit: an unknown op names the ones that exist",
      r.returncode != 0 and "subtract" in (r.stdout + r.stderr))

# --- gap and widen-negative: the two dark-cloth stitch-out defects ---------- #
# Both answer MuffyHat_on_black coming off the machine (photos/PXL_20260812_
# 064352867.jpg) with the white hat and the gold body reading as one pale mass
# and the knocked-out SOUR PUSS barely legible. Both were clean in `validate`,
# solid in `stitch proof` and invisible in `stitch render` at design size.

# Two 20 mm bars sharing an edge at x=20, one unit per mm.
TOUCHING = OPS / "touching.svg"
TOUCHING.write_text(
    SVG_HDR + f'<path id="a" fill="#FFFFFF" d="{sq(0, 0, 20, 20)}"/>'
            + f'<path id="b" fill="#F6BE00" d="{sq(20, 0, 40, 20)}"/>'
    + "</svg>", encoding="utf-8")
doc = Doc.load(TOUCHING, 40.0)
white, gold = doc.geom_of("FFFFFF"), doc.geom_of("F6BE00")
check("svgops: two colours drawn edge to edge start at zero distance",
      white.distance(gold) < 1e-6)
svgops.OPS["gap"]["fn"](doc, colour="F6BE00", by="FFFFFF", mm=0.8)
sep = doc.geom_of("FFFFFF").distance(doc.geom_of("F6BE00")) / doc.upm
check("svgops: gap opens the declared channel between two colours",
      abs(sep - 0.8) < 0.05, f"{sep:.3f} mm apart")
# The channel comes out of ONE colour: cutting both would move both silhouettes.
check("svgops: gap takes the channel only from the named colour",
      abs(doc.mm2(doc.geom_of("FFFFFF")) - 400) < 1.0,
      f"white {doc.mm2(doc.geom_of('FFFFFF')):.0f} mm2, expected 400")

doc = Doc.load(TOUCHING, 40.0)
msg = svgops.OPS["gap"]["fn"](doc, colour="F6BE00", by="FFFFFF", mm=0.0)
check("svgops: a zero gap changes nothing", "0.0 mm2" in msg or "0 mm2" in msg
      or abs(doc.mm2(doc.geom_of("F6BE00")) - 400) < 1.0, msg)

# A plate with two holes 6 mm apart: wide enough to open, and the op must open
# them without joining them.
def plate(gap_mm: float) -> str:
    """20x10 plate with two 2 mm-wide slots separated by `gap_mm` of material."""
    x0 = 10 - gap_mm / 2 - 2
    x1 = 10 + gap_mm / 2
    return (sq(0, 0, 20, 10)
            + f" M {x0} 3 L {x0} 7 L {x0 + 2} 7 L {x0 + 2} 3 Z"
            + f" M {x1} 3 L {x1} 7 L {x1 + 2} 7 L {x1 + 2} 3 Z")

ROOMY = OPS / "roomy.svg"
ROOMY.write_text(SVG_HDR + f'<path fill="#FFFFFF" fill-rule="evenodd" '
                 f'd="{plate(6.0)}"/></svg>', encoding="utf-8")
def slots_of(doc):
    """(hole count, narrowest slot width in mm) for the plate's knockouts."""
    hs = [p.interiors for r in doc.select("FFFFFF", "fill")
          for p in svgops.G.polys(r.geom)]
    n = sum(len(i) for i in hs)
    from shapely.geometry import Polygon as _P
    from shapely.ops import unary_union as _u
    neg = _u([_P(ring) for i in hs for ring in i]) if n else None
    m = svgops._rasterise(neg, doc.upm, 24.0) if n else None
    return n, (float(np.median(measure.widths_mm(m, 24.0)))
               if n and m is not None and m.any() else 0.0)

doc = Doc.load(ROOMY, 20.0)
before = doc.mm2(doc.geom_of("FFFFFF"))
msg = svgops.OPS["widen-negative"]["fn"](doc, colour="FFFFFF", to_min=3.0)
holes, w = slots_of(doc)
check("svgops: widen-negative opens a knockout that has room",
      "opened 2 hole(s)" in msg and holes == 2, msg)
check("svgops: and the slots really do end up at the target width",
      w >= 3.0 - 0.15, f"narrowest slot now {w:.2f} mm, wanted 3.0")
check("svgops: the widening is paid for out of the surrounding fill",
      doc.mm2(doc.geom_of("FFFFFF")) < before,
      f"{before:.1f} -> {doc.mm2(doc.geom_of('FFFFFF')):.1f} mm2")

# THE ONE THAT SHIPPED. The first version of this op guarded on SHELL count,
# which RISES when widening severs the shape between two holes — read as benign,
# and it was. What it could not see is the holes MERGING into each other, which
# is a closed letter counter. It widened SOUR PUSS until every counter had shut,
# making the lettering less legible than the defect it was fixing. The render
# caught it; the guard did not. For a knockout the topology that matters is the
# hole count, and the opening has to be clamped to preserve it.
TIGHT = OPS / "tight.svg"
TIGHT.write_text(SVG_HDR + f'<path fill="#FFFFFF" fill-rule="evenodd" '
                 f'd="{plate(0.6)}"/></svg>', encoding="utf-8")
doc = Doc.load(TIGHT, 20.0)
msg = svgops.OPS["widen-negative"]["fn"](doc, colour="FFFFFF", to_min=3.0)
holes, _ = slots_of(doc)
check("svgops: widen-negative never merges two knockouts into one",
      holes == 2, f"{holes} hole(s) left, {msg}")
check("svgops: a clamped widen says how far it could not go",
      "CLAMPED" in msg and "would have merged" in msg, msg)

# Slots all but touching: the clamp binds so hard that opening buys nothing.
# Refuse outright rather than half-do it — lettering has an enormous perimeter,
# so even 0.02 mm per side took 71 mm2 out of MuffyHat's crown while moving the
# width figure not at all.
SHUT = OPS / "shut.svg"
SHUT.write_text(SVG_HDR + f'<path fill="#FFFFFF" fill-rule="evenodd" '
                f'd="{plate(0.04)}"/></svg>', encoding="utf-8")
doc = Doc.load(SHUT, 20.0)
before = doc.mm2(doc.geom_of("FFFFFF"))
msg = svgops.OPS["widen-negative"]["fn"](doc, colour="FFFFFF", to_min=3.0)
check("svgops: a widen that would buy nothing is refused, and says why",
      "CANNOT" in msg and "stitch it as thread" in msg, msg)
check("svgops: a refused widen costs no material",
      abs(doc.mm2(doc.geom_of("FFFFFF")) - before) < 1e-6,
      f"{before:.2f} -> {doc.mm2(doc.geom_of('FFFFFF')):.2f} mm2")

from shapely.ops import unary_union  # noqa: E402

# --- pockets: a keyline gap is not a white area ----------------------------- #
# Illustration drawn for light paper sets ink into a HAIRLINE gap in the colour
# beneath it, so the paper reads as an outline around it. Recovering that gap as
# thread put a white halo around both Muffy faces' eyes and mouths, running
# straight into the yellow. Observed on fabric, invisible to every check.
#
# A 30x20 gold plate with two holes: one a 6x6 mm window (a real white area),
# one a 0.3 mm-wide slot (a keyline). Black ink sits inside each so both qualify
# as pockets adjacent to ink.
HALO = OPS / "halo.svg"
HALO.write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="30" '
    'viewBox="0 0 40 30">'
    f'<path fill="#F6BE00" fill-rule="evenodd" d="{sq(0, 0, 30, 20)} '
    f'{sq(3, 3, 9, 9)} {sq(14, 3, 14.3, 17)}"/>'
    f'<path fill="#000000" d="{sq(5, 5, 7, 7)} {sq(14.1, 5, 14.2, 15)}"/>'
    "</svg>", encoding="utf-8")
doc = Doc.load(HALO, 30.0)
msg = svgops.OPS["pockets"]["fn"](doc, adjacent="000000", emit="FFFFFF")
white = doc.geom_of("FFFFFF")
areas = sorted(doc.mm2(p) for p in svgops.G.polys(white))
check("svgops: pockets keeps a real white area and drops the keyline gap",
      len(areas) == 1 and 25 < areas[0] < 36, f"{[round(a, 1) for a in areas]}, {msg}")
check("svgops: and says what it dropped and why",
      "keyline pocket" in msg and "bare cloth" in msg, msg)

# The filter must not be able to silently empty the layer.
doc = Doc.load(HALO, 30.0)
try:
    svgops.OPS["pockets"]["fn"](doc, adjacent="000000", emit="FFFFFF", min_width=20.0)
    check("svgops: pockets fails loudly if the filter leaves nothing", False)
except SystemExit as e:
    check("svgops: pockets fails loudly if the filter leaves nothing",
          "keyline rather than an area" in str(e), str(e)[:120])

# --- scale / space-out / move: redrawing detail that is too small ---------- #
# Four 4x6 mm bars 0.5 mm apart on one row, and a second row 0.4 mm below it —
# the shape of SOUR PUSS, where BOTH the knockout strokes and the thread bridges
# between them are under limit at once and there is no material to move.
def bars(y, n=4, w=4.0, h=6.0, gap=0.5, x0=2.0):
    return " ".join(sq(x0 + i * (w + gap), y, x0 + i * (w + gap) + w, y + h)
                    for i in range(n))

TYPE = OPS / "type.svg"
TYPE.write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" width="60" height="40" '
    f'viewBox="0 0 60 40"><path fill="#000000" d="{bars(2.0)} {bars(8.4)}"/></svg>',
    encoding="utf-8")

doc = Doc.load(TYPE, 17.5)
comps = svgops.G.polys(doc.geom_of("000000"))
rows = svgops._rows_of(doc, comps)
# A nearness test would fuse the two lines: they sit 0.4 mm apart, which is less
# than any sane tolerance, yet they are plainly different rows. Only real
# vertical OVERLAP separates a row from the line below it. The first version
# used a 1 mm nearness tolerance, merged all eight bars into one row, and
# re-spaced them into an interleaved single line.
check("svgops: _rows_of splits lines that are closer than one line apart",
      [len(r) for r in rows] == [4, 4], f"rows {[len(r) for r in rows]}")

doc = Doc.load(TYPE, 17.5)
svgops.OPS["space-out"]["fn"](doc, colour="000000", gap=2.0, line_gap=2.0)
comps = svgops.G.polys(doc.geom_of("000000"))
rows = svgops._rows_of(doc, comps)
gaps = [rw[i + 1].distance(rw[i]) / doc.upm for rw in rows for i in range(len(rw) - 1)]
# Every gap, not just the first: the shift for each component is solved against
# the one before it, which has itself already moved. The bracket for that search
# was sized from the target gap, so a component that had to travel several times
# the target — the fourth letter of SOUR moved 14.5 mm to open a 2.2 mm gap —
# ran off the end of the bracket and quietly came back short. No error, just the
# wrong answer, in the one place a wrong answer is invisible.
check("svgops: space-out opens EVERY gap, not just the first",
      gaps and max(abs(g - 2.0) for g in gaps) < 0.05,
      "gaps " + ", ".join(f"{g:.2f}" for g in gaps))
check("svgops: space-out keeps the rows apart too",
      len(rows) == 2 and abs(unary_union(rows[0]).distance(unary_union(rows[1]))
                             / doc.upm - 2.0) < 0.05)

# Scaling components in place makes neighbours collide, and the union that must
# follow — evenodd would XOR an overlap into a HOLE, not merge it — fuses them
# irreversibly. Every later op then sees one blob: `space-out` reported
# "re-spaced 1 component(s)" and moved nothing at all.
doc = Doc.load(TYPE, 17.5)
try:
    svgops.OPS["scale"]["fn"](doc, colour="000000", factor=1.4)
    check("svgops: scale refuses to fuse components it would collide", False)
except SystemExit as e:
    check("svgops: scale refuses to fuse components it would collide",
          "space-out" in str(e), str(e)[:120])

# Space first, then scale into the room that makes — the order the specs use.
doc = Doc.load(TYPE, 17.5)
svgops.OPS["space-out"]["fn"](doc, colour="000000", gap=2.0, line_gap=2.0)
svgops.OPS["scale"]["fn"](doc, colour="000000", factor=1.25)
comps = svgops.G.polys(doc.geom_of("000000"))
check("svgops: space-out then scale keeps every component distinct",
      len(comps) == 8, f"{len(comps)} component(s)")
w = max(p.bounds[2] - p.bounds[0] for p in comps) / doc.upm
check("svgops: and the components really are 1.25x wider",
      abs(w - 5.0) < 0.1, f"widest bar {w:.2f} mm, expected 5.0")
gaps = [rw[i + 1].distance(rw[i]) / doc.upm
        for rw in svgops._rows_of(doc, comps) for i in range(len(rw) - 1)]
# Scaling closes the gaps again by the growth — this is why the spec asks
# space-out for 1.64 mm to land a 1.2 mm bridge, and why the figure is not 1.2.
check("svgops: scaling closes the gaps it was given, by the growth",
      abs(min(gaps) - 1.0) < 0.1, f"min gap {min(gaps):.2f} mm, expected 1.0")

# A millimetre must not change length part-way through a sequence. `upm` was
# recomputed on every rescan from the current bounds, so any op that resized the
# drawing silently rescaled every op after it — and `drop`, which shrinks the
# bbox, is in almost every dark-cloth sequence here. The extent is allowed to
# move; the scale is not.
doc = Doc.load(TYPE, 17.5)
upm0 = doc.upm
svgops.OPS["space-out"]["fn"](doc, colour="000000", gap=3.0, line_gap=3.0)
check("svgdoc: the mm scale is frozen at load, not re-derived per rescan",
      doc.upm == upm0, f"{upm0:.4f} -> {doc.upm:.4f} units/mm")
gaps = [rw[i + 1].distance(rw[i]) / doc.upm
        for rw in svgops._rows_of(doc, svgops.G.polys(doc.geom_of("000000")))
        for i in range(len(rw) - 1)]
check("svgdoc: so a gap measures back as the gap it was asked for",
      abs(max(gaps) - 3.0) < 0.05 and abs(min(gaps) - 3.0) < 0.05,
      "gaps " + ", ".join(f"{g:.2f}" for g in gaps))

doc = Doc.load(TYPE, 17.5)
at0 = unary_union(svgops.G.polys(doc.geom_of("000000"))).centroid
msg = svgops.OPS["move"]["fn"](doc, colour="000000", dx=3.0, dy=-1.5)
at1 = unary_union(svgops.G.polys(doc.geom_of("000000"))).centroid
check("svgops: move translates by exactly what it was asked",
      abs((at1.x - at0.x) / doc.upm - 3.0) < 1e-6
      and abs((at1.y - at0.y) / doc.upm + 1.5) < 1e-6,
      f"moved {(at1.x - at0.x) / doc.upm:+.3f},{(at1.y - at0.y) / doc.upm:+.3f}")
# A positional op must report what it did, or a silent miss stays silent.
check("svgops: move reports where it landed", "now at" in msg, msg)

# --------------------------------------------------------------------------- #
print(f"\n{'=' * 60}")
print(f"{PASSED} passed, {len(FAILURES)} failed")
for f in FAILURES:
    print(f"  FAILED: {f}")
sys.exit(1 if FAILURES else 0)
