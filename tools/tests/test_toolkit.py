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
check("false and null options are omitted entirely",
      "-ContourUnderlay" not in _a and "-LockStyle" not in _a, " ".join(_a))
check("no skip argument when the spec skips nothing",
      "-Skip" not in BLD.ps_args({"name": "T", "build": {"tool": "svg_to_pes",
                                 "input": "a.svg", "artwork_mm": 91}},
                                 Path("a.svg"), Path("b.pes")))

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
print(f"\n{'=' * 60}")
print(f"{PASSED} passed, {len(FAILURES)} failed")
for f in FAILURES:
    print(f"  FAILED: {f}")
sys.exit(1 if FAILURES else 0)
