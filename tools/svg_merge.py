"""Stack several equally-sized SVG layers into one Ink/Stitch document.

Layers are stitched in document order, so they are given bottom layer first --
the same order color_separate.py numbers them.

The layers must already agree on geometry. This refuses to merge documents whose
viewBox or physical size differ rather than scaling them to match: silently
rescaling a layer would misregister it against the others, and a design that is
1 mm out of register looks like a machine fault rather than a tooling bug.

Usage:  svg_merge.py <out.svg> <layer1.svg> <layer2.svg> ...
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SVG_NS = "http://www.w3.org/2000/svg"
INK_NS = "http://inkstitch.org/namespace"
SODIPODI_NS = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("inkstitch", INK_NS)
ET.register_namespace("xlink", XLINK_NS)

# See color_separate.py for why these are mandatory. The merged document is the
# one Ink/Stitch actually exports from, so its metadata is the metadata that
# counts -- settings on the individual layer files do not carry over.
from embroidery_tools import profile as _prof  # noqa: E402

INKSTITCH_SVG_VERSION = "4"
MIN_STITCH_MM = _prof.load()["design_limits"]["min_stitch_mm"]

# Structural elements that must not be copied through: each source carries its
# own, and the merged document gets exactly one fresh set.
DROP = {
    f"{{{SVG_NS}}}metadata",
    f"{{{SODIPODI_NS}}}namedview",
    f"{{{SVG_NS}}}title",
}

if len(sys.argv) < 3:
    raise SystemExit(__doc__)

out = Path(sys.argv[1])
srcs = [Path(p) for p in sys.argv[2:]]

roots = []
for p in srcs:
    if not p.exists():
        raise SystemExit(f"missing layer: {p}")
    roots.append(ET.parse(p).getroot())


def geom(r: ET.Element) -> tuple[str, str, str]:
    return (r.get("viewBox", ""), r.get("width", ""), r.get("height", ""))


def nums(*vals: str) -> tuple[float, ...]:
    """Numeric view of the geometry, so 91mm and 91.000mm compare equal.

    Compared numerically rather than as strings because these documents make a
    round trip through Ink/Stitch, which is free to reformat them.
    """
    out = []
    for v in vals:
        for tok in v.replace(",", " ").split():
            try:
                out.append(float(tok.rstrip("abcdefghijklmnopqrstuvwxyz%")))
            except ValueError:
                return ()
    return tuple(out)


ref = geom(roots[0])
ref_n = nums(*ref)
for p, r in zip(srcs[1:], roots[1:]):
    g = geom(r)
    n = nums(*g)
    ok = (len(n) == len(ref_n) and ref_n
          and all(abs(x - y) <= 1e-3 * max(1.0, abs(y)) for x, y in zip(n, ref_n)))
    if not ok:
        raise SystemExit(
            f"layer geometry mismatch, refusing to merge:\n"
            f"  {srcs[0].name}: viewBox={ref[0]!r} {ref[1]}x{ref[2]}\n"
            f"  {p.name}: viewBox={g[0]!r} {g[1]}x{g[2]}\n"
            f"Regenerate both layers from the same source dimensions and width.")

merged = ET.Element(f"{{{SVG_NS}}}svg", {
    "version": "1.1",
    "width": ref[1],
    "height": ref[2],
    "viewBox": ref[0],
})
meta = ET.SubElement(merged, f"{{{SVG_NS}}}metadata")
ET.SubElement(meta, f"{{{INK_NS}}}inkstitch_svg_version").text = INKSTITCH_SVG_VERSION
ET.SubElement(meta, f"{{{INK_NS}}}min_stitch_len_mm").text = f"{MIN_STITCH_MM:g}"
defs = ET.SubElement(merged, f"{{{SVG_NS}}}defs")

# ids must stay unique across the merged document: a duplicate silently
# repoints every url(#id) reference at whichever copy the renderer sees first,
# and the result still renders, so nothing downstream notices.
#
# Collisions are expected rather than exceptional -- Ink/Stitch restarts its id
# counter on every invocation, so two layers that each went through redwork will
# both contain e.g. underpath_6139. Rename them and rewrite the references.
HREF_ATTRS = ("href", f"{{{XLINK_NS}}}href")


def ids_of(root: ET.Element) -> set[str]:
    return {el.get("id") for el in root.iter() if el.get("id")}


id_sets = [ids_of(r) for r in roots]
clashing: set[str] = set()
for i in range(len(id_sets)):
    for j in range(i + 1, len(id_sets)):
        clashing |= id_sets[i] & id_sets[j]

n_renamed = 0
for n, (p, r) in enumerate(zip(srcs, roots)):
    if n == 0:
        continue                      # first source keeps its ids unchanged
    rename = {i: f"s{n}_{i}" for i in id_sets[n] & clashing}
    if not rename:
        continue
    n_renamed += len(rename)
    for el in r.iter():
        cur = el.get("id")
        if cur in rename:
            el.set("id", rename[cur])
        for key, val in list(el.attrib.items()):
            if key in HREF_ATTRS and val.startswith("#") and val[1:] in rename:
                el.set(key, "#" + rename[val[1:]])
            elif "url(#" in val:
                el.set(key, re.sub(
                    r"url\(#([^)]+)\)",
                    lambda m: f"url(#{rename.get(m.group(1), m.group(1))})", val))

n_defs = 0
for p, r in zip(srcs, roots):
    for el in list(r):
        if el.tag in DROP:
            continue
        if el.tag == f"{{{SVG_NS}}}defs":
            for d in list(el):
                defs.append(d)
                n_defs += 1
            continue
        merged.append(el)

# Belt and braces: prove uniqueness on the merged result rather than trusting
# the renaming above.
final_ids = [el.get("id") for el in merged.iter() if el.get("id")]
if len(final_ids) != len(set(final_ids)):
    dupes = {i for i in final_ids if final_ids.count(i) > 1}
    raise SystemExit(f"duplicate ids survived the merge: {sorted(dupes)[:5]}")

ET.ElementTree(merged).write(out, encoding="utf-8", xml_declaration=True)
ET.parse(out)   # fail loudly rather than handing a broken document downstream

n_paths = sum(1 for _ in merged.iter(f"{{{SVG_NS}}}path"))
note = f", {n_renamed} id(s) renamed to avoid collisions" if n_renamed else ""
print(f"    merged {len(srcs)} layer(s) -> {n_paths} path(s), "
      f"{n_defs} def(s), {ref[1]}x{ref[2]}, XML valid{note}")
