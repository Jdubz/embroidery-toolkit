"""Remap fill and stroke colours in an SVG, before digitizing.

Thread colour in a PES is a **label** — this machine cannot detect what is on the
spool, so it stops at each change and shows a name while you load whatever you
like. Recolouring therefore changes nothing about how a design stitches.

What it does change is everything around the stitching: the colour shown at each
change on the machine, the swatch in Design Database Transfer, and what
`stitch render` and `stitch proof` show. A one-colour outline drawn in black and
stitched in white on black cloth will preview as an invisible black-on-black
smudge, which is exactly when you most want to see the design.

So this exists to keep the file honest about its own intent, not to change
stitches. Where it *does* matter functionally is layer identity: PES merges
adjacent blocks that share a colour, so mapping two layers onto one hex silently
turns two stops into one and two passes into one. That is a real change, and the
tool reports every merge it causes rather than letting it pass quietly.

    svg_recolor.py in.svg out.svg --map 000000=FFFFFF
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)
PAINT = ("fill", "stroke")


def norm(colour: str) -> str:
    c = colour.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in c):
        raise SystemExit(f"'{colour}' is not a 3- or 6-digit hex colour. "
                         "Refusing to guess — a wrong guess stitches the wrong colour. "
                         "In PowerShell, quote it: '000000', not 000000.")
    return c.upper()


ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--map", action="append", default=[], required=True, metavar="SRC=DST",
                help="repaint every #SRC fill and stroke as #DST")
a = ap.parse_args()

rules: dict[str, str] = {}
for spec in a.map:
    src, _, dst = spec.partition("=")
    if not dst:
        raise SystemExit(f"--map {spec!r} is not SRC=DST")
    rules[norm(src)] = norm(dst)

tree = ET.parse(a.src)
root = tree.getroot()

seen: dict[str, int] = {}          # colours present before, and how many uses
hits: dict[str, int] = {}


def repaint(value: str) -> tuple[str, bool]:
    if not value or value.strip().lower() in ("none", "transparent"):
        return value, False
    try:
        c = norm(value)
    except SystemExit:
        return value, False        # a named colour or url(#...) — leave it alone
    seen[c] = seen.get(c, 0) + 1
    if c in rules:
        hits[c] = hits.get(c, 0) + 1
        return f"#{rules[c]}", True
    return value, False


for el in root.iter():
    for attr in PAINT:
        v = el.get(attr)
        if v is not None:
            new, _ = repaint(v)
            if new != v:
                el.set(attr, new)
    style = el.get("style")
    if style:
        parts = []
        for decl in style.split(";"):
            k, _, v = decl.partition(":")
            if k.strip() in PAINT and v.strip():
                new, _ = repaint(v.strip())
                parts.append(f"{k.strip()}:{new}")
            elif decl.strip():
                parts.append(decl)
        el.set("style", ";".join(parts))

for src, dst in rules.items():
    n = hits.get(src, 0)
    if not n:
        raise SystemExit(f"--map {src}={dst}: nothing in the document is #{src}. "
                         "A remap that matches nothing means the design keeps the "
                         "colour you meant to change.")
    print(f"  #{src} -> #{dst}  ({n} paint attribute(s))")

# PES merges adjacent blocks that share a colour: two layers mapped onto one hex
# become one stop and one pass. Never let that happen silently.
after: dict[str, list[str]] = {}
for c in seen:
    after.setdefault(rules.get(c, c), []).append(c)
for dst, srcs in after.items():
    if len(srcs) > 1:
        print(f"  WARNING  #{dst} is now shared by {len(srcs)} source colours "
              f"({', '.join('#' + s for s in sorted(srcs))}). PES merges adjacent "
              "blocks of one colour, so those layers will stitch as a single pass "
              "with one stop, not several.")

tree.write(a.dst, encoding="utf-8", xml_declaration=True)
ET.parse(a.dst)      # fail loudly rather than handing a broken document downstream
print(f"  -> {a.dst}")
