"""Apply atomic operations to an SVG, previewing and logging each one.

Replaces the per-asset scripting that produced `svg_ground_invert`,
`svg_knockout`, `svg_dark_invert` and `svg_recolor`. Those are each a fixed
sequence of a handful of operations; here the sequence is the argument and the
code is fixed.

    svg_edit.py in.svg out.svg --artwork-mm 91 \
        --op "subtract --colour FFD400 --by 000000" \
        --op "subtract --colour FFFFFF --by 000000" \
        --op "subtract --colour FFD400 --by FFFFFF" \
        --op "drop --colour 000000"

That is the whole of LemonCat_solid_on_black. Each op prints what it changed and
writes a numbered preview PNG, so a wrong step is visible at the step that made
it wrong rather than at the end — which is how the yellow eyes, the welded letter
counters and the missing question mark were all caught late.

**Every run writes an op log beside the output.** The log is the declaration:
`--replay` re-applies it, so an interactively-found sequence becomes reproducible
without anyone having to design a file format for it. That was the only real
argument for inventing a pipeline DSL, and recording removes it.

`--list-ops` prints the vocabulary.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embroidery_tools import svgops  # noqa: E402
from embroidery_tools.svgdoc import Doc  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("src", nargs="?")
ap.add_argument("dst", nargs="?")
ap.add_argument("--artwork-mm", type=float,
                help="width the drawing will be stitched at; every mm is of that")
ap.add_argument("--op", action="append", default=[], metavar="'NAME --flag V'",
                help="an operation to apply, in order. Repeatable.")
ap.add_argument("--replay", metavar="LOG.jsonl",
                help="re-apply the ops recorded in a log instead of --op")
ap.add_argument("--preview", metavar="DIR",
                help="write a PNG after every op into DIR (default: no previews)")
ap.add_argument("--preview-ppm", type=float, default=10.0)
ap.add_argument("--fabric", default="141414", metavar="RRGGBB",
                help="cloth colour behind the preview (default near-black)")
ap.add_argument("--log-dir", metavar="DIR",
                help="where to write the op log (default build/ops/)")
ap.add_argument("--list-ops", action="store_true")
a = ap.parse_args()

if a.list_ops:
    print("operations:")
    for name in sorted(svgops.OPS):
        print("  " + svgops.OPS[name]["help"])
    sys.exit(0)

if not (a.src and a.dst and a.artwork_mm):
    ap.error("src, dst and --artwork-mm are required")

specs = list(a.op)
if a.replay:
    for line in Path(a.replay).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            specs.append(json.loads(line)["op"])
if not specs:
    ap.error("nothing to do: pass --op or --replay")


def parse_op(text: str) -> tuple[str, dict]:
    """'subtract --colour FFD400 --by 000000' -> ('subtract', {...})."""
    parts = shlex.split(text)
    if not parts:
        raise SystemExit("empty --op")
    name, rest = parts[0], parts[1:]
    if name not in svgops.OPS:
        raise SystemExit(f"unknown op {name!r}. Known: {', '.join(sorted(svgops.OPS))}")
    kw: dict = {}
    i = 0
    while i < len(rest):
        tok = rest[i]
        if not tok.startswith("--"):
            raise SystemExit(f"{name}: expected a --flag, got {tok!r}")
        key = tok[2:].replace("-", "_")
        if i + 1 < len(rest) and not rest[i + 1].startswith("--"):
            kw[key], i = rest[i + 1], i + 2
        else:
            kw[key], i = True, i + 1
    # Types are declared here rather than guessed: a silently mistyped argument
    # is how a 0.3 mm offset becomes the string "0.3" and does nothing useful.
    for k in ("mm", "lid_above", "to_min", "tolerate", "ppm",
              "factor", "gap", "line_gap", "dx", "dy", "min_width", "min_keep"):
        if k in kw:
            kw[k] = float(kw[k])
    for b in ("band", "band_x"):
        if b in kw and isinstance(kw[b], str):
            lo, _, hi = kw[b].partition(":")
            kw[b] = (float(lo), float(hi))
    return name, kw


doc = Doc.load(a.src, a.artwork_mm)
x0, y0, x1, y1 = doc.bounds
print(f"  {a.src}: {x1 - x0:.0f} units wide -> {a.artwork_mm:g} mm "
      f"({doc.upm:.3f} units/mm)")
print("  " + ", ".join(f"#{c} {v:,.0f} mm2"
                       for c, v in sorted(doc.colours().items(), key=lambda kv: -kv[1])))

preview_dir = Path(a.preview) if a.preview else None
if preview_dir:
    preview_dir.mkdir(parents=True, exist_ok=True)


def write_preview(step: int, label: str) -> None:
    if not preview_dir:
        return
    try:
        import numpy as np
        import shapely
        from PIL import Image
    except ImportError:
        return
    from shapely.ops import unary_union
    layers: dict[str, list] = {}
    for r in doc.regions:
        layers.setdefault(r.colour, []).append(r.geom)
    merged = {c: unary_union(v) for c, v in layers.items()}
    bx0, by0, bx1, by1 = doc.bounds
    ppm, pad = a.preview_ppm, 12
    W = int((bx1 - bx0) / doc.upm * ppm) + 2 * pad
    H = int((by1 - by0) / doc.upm * ppm) + 2 * pad
    xs = bx0 + (np.arange(W) + 0.5 - pad) * doc.upm / ppm
    ys = by0 + (np.arange(H) + 0.5 - pad) * doc.upm / ppm
    gx, gy = np.meshgrid(xs, ys)
    img = np.zeros((H, W, 3), np.uint8)
    img[...] = tuple(int(a.fabric[i:i + 2], 16) for i in (0, 2, 4))
    # Darkest last: a light layer must never paint over a dark one it sits under,
    # which is the order svg_prep stitches in and the error that hid the yellow
    # LemonCat eyes for a whole session.
    for c in sorted(merged, key=lambda h: -(0.2126 * int(h[0:2], 16)
                                            + 0.7152 * int(h[2:4], 16)
                                            + 0.0722 * int(h[4:6], 16))):
        shapely.prepare(merged[c])
        img[shapely.contains_xy(merged[c], gx, gy)] = tuple(
            int(c[i:i + 2], 16) for i in (0, 2, 4))
    out = preview_dir / f"{Path(a.dst).stem}.{step:02d}.{label}.png"
    Image.fromarray(img).save(out)
    print(f"       preview -> {out}")


write_preview(0, "before")
log: list[dict] = []
for n, text in enumerate(specs, 1):
    name, kw = parse_op(text)
    print(f"  [{n}] {text}")
    result = svgops.OPS[name]["fn"](doc, **kw)
    for line in str(result).splitlines():
        print(f"       {line}")
    log.append({"op": text})
    write_preview(n, name)

doc.save(a.dst)

# The log goes in build/, not beside the output. art/prepared/ holds one
# generated derivative per spec and `stitch audit` calls anything else there
# sprawl; build/ is where everything else generated belongs.
REPO = Path(__file__).resolve().parents[1]
logdir = Path(a.log_dir) if a.log_dir else REPO / "build" / "ops"
try:
    logdir.mkdir(parents=True, exist_ok=True)
    logpath = logdir / (Path(a.dst).stem + ".ops.jsonl")
except OSError:
    logpath = Path(a.dst).with_suffix(".ops.jsonl")
logpath.write_text("".join(json.dumps(e) + "\n" for e in log), encoding="utf-8")
print("  " + ", ".join(f"#{c} {v:,.0f} mm2"
                       for c, v in sorted(doc.colours().items(), key=lambda kv: -kv[1])))
print(f"  -> {a.dst}   (ops logged to {logpath.name}; replay with --replay)")
