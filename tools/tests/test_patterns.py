#!/usr/bin/env python
"""Invariant checks for the sewing-pattern side: bag_pattern.py + the player.

Deliberately dependency-free, the same shape as `test_toolkit.py`, so it runs
anywhere the toolkit does:

    py tools/tests/test_patterns.py

Every check here maps to a mistake that is expensive in this domain
specifically. A bad stitch file costs a rebuild; a bad cut costs material, and
a wrong assembly instruction costs the whole bag, because a bound seam cannot
be unpicked -- the holes stay.

The first section is the one that matters most. `patterns/README.md` and
`BoxBound_family.md` both insist a new check is run against a known-good file
before it is trusted, and StadiumTote is that file: hand-computed first, five
revisions deep, every figure published. If the generator disagrees with it, the
generator is wrong.
"""

from __future__ import annotations

import copy
import json
import math
import sys
from fractions import Fraction as F
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

import bag_pattern as B                                    # noqa: E402
import pattern_player as P                                 # noqa: E402

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

FAILURES: list[str] = []
PASSED = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILURES.append(f"{name}: {detail}")
        print(f"  FAIL  {name}  {detail}")


def section(title: str) -> None:
    print(f"\n-- {title} " + "-" * max(0, 56 - len(title)))


STAMP = "2026-01-01T00:00:00+00:00"
SPECS = {p.stem: p for p in sorted((REPO / "patterns" / "specs").glob("*.json"))}
BAGS = {n: B.load(p) for n, p in SPECS.items()}
CONS, CONS_PATH = B.load_construction("box-bound")


# =====================================================================
section("the known-good file: StadiumTote's hand-computed figures")
# Published in patterns/BoxBound_family.md and StadiumTote_12x12x4.md. These
# are not derived from the generator -- they predate it.

t = BAGS["StadiumTote_12x12x4"]
for name, got, want in [
    ("panel width",        t.panel_w,     F(47, 4)),      # 11 3/4
    ("panel height",       t.panel_h,     F(91, 8)),      # 11 3/8
    ("panel face width",   t.face_w,      F(11)),
    ("panel face height",  t.face_h,      F(85, 8)),      # 10 5/8
    ("gusset cut width",   t.gusset_w,    F(4)),
    ("gusset face depth",  t.face_d,      F(13, 4)),      # 3 1/4
    ("ring at stitch line", t.ring,       F(173, 4)),     # 43 1/4
    ("gusset finished",    t.gusset_face, F(129, 4)),     # 32 1/4
    ("zip strip, front",   t.strip_front, F(11, 8)),      # 1 3/8
    ("zip strip, rear",    t.strip_rear,  F(27, 8)),      # 3 3/8
    ("zip panel length",   t.zip_cut,     F(12)),
    ("coil from cut edge", t.coil_c,      F(1)),
    ("binding strip width", t.bind_cut,   F(9, 8)),       # 1 1/8
    ("chassis loop",       t.loop,        F(189, 4)),     # 47 1/4
]:
    check(f"StadiumTote {name}", got == want, f"got {B.frac(got)}, want {B.frac(want)}")

check("StadiumTote ring closes on the stitch-line perimeter",
      t.ring == 2 * (t.face_w + t.face_h),
      "a ring cut to the raw-edge perimeter is 8 x SA too long -- 3 inches here")
check("StadiumTote zip panel reassembles to the gusset width",
      (t.strip_front - t.lap) + t.coil + (t.strip_rear - t.lap) == t.gusset_w)
check("StadiumTote binds in tape, not in its own fraying shell",
      t.bind_mat != t.shell and not t.bind_frays,
      "denim double-fold gives a 7.3 mm mitred corner and will not drive")
check("every bag's nine geometry checks pass",
      all(b.failed() == 0 for b in BAGS.values()),
      str({n: b.failed() for n, b in BAGS.items() if b.failed()}))


# =====================================================================
section("the checks earn their keep -- each fires on a real mistake")

def variant(base: str, **over) -> B.BoxBag:
    s = copy.deepcopy(BAGS[base].spec)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(s.get(k), dict):
            s[k].update(v)
        else:
            s[k] = v
    return B.BoxBag(s)


def failed_named(bag: B.BoxBag, needle: str) -> bool:
    return any(not ok and needle in n for ok, n, _ in bag.checks())


hip1 = variant("HipPack_10x6x3", chassis={"webbing_in": 1.0, "overlap_in": 4.0})
check("1\" webbing on the HipPack fails the coil clearance",
      failed_named(hip1, "coil clears the binding flange"),
      "the ¾\" webbing is structural, not a preference")

denim = variant("HipPack_10x6x3", shell="denim-12oz")
check("a fraying shell bound in itself fails the mitred corner",
      failed_named(denim, "mitred corner"),
      f"{denim.corner_mm:.1f} mm")
check("...and binding it in tape passes",
      not failed_named(variant("HipPack_10x6x3", shell="denim-12oz",
                               binding={"material": "nylon-binding-tape"}),
                       "mitred corner"))

shallow = variant("SlingPack_13x7x4", finished_in={"w": 10, "h": 6, "d": 2})
check("a 2\" deep bag with a chassis fails: the coil and webbing overlap",
      failed_named(shallow, "coil clears the webbing"),
      "which is why BeltPouch and HipPack both declare \"chassis\": null")

over = variant("StadiumTote_12x12x4", finished_in={"w": 12.5, "h": 11.5, "d": 4.125})
check("an over-limit bag fails its declared envelope",
      failed_named(over, "within the declared limit"))


# =====================================================================
section("chassis: absent means yes, only explicit null means no")
# Reading absent as off silently re-centred the StadiumTote's coil and moved
# both its zipper strips. That is what this pair of checks exists to hold.

s = copy.deepcopy(BAGS["StadiumTote_12x12x4"].spec)
s.pop("chassis", None)
check("a spec with no 'chassis' key still gets one", B.BoxBag(s).has_chassis)
s["chassis"] = None
check("an explicit null turns it off", not B.BoxBag(s).has_chassis)
check("...and then the coil sits centred, so the strips are symmetrical",
      B.BoxBag(s).strip_front == B.BoxBag(s).strip_rear)
check("BeltPouch has no chassis", not BAGS["BeltPouch_4x6"].has_chassis)
# 15/16 coil centre − ⅛ half-coil + ½ lap = 21/16. The published figure said
# 15/16, which is frac()'s missing separator, not the geometry.
check("BeltPouch's strips really are symmetrical, at 1 5/16\"",
      BAGS["BeltPouch_4x6"].strip_front == BAGS["BeltPouch_4x6"].strip_rear
      == F(21, 16),
      B.frac(BAGS["BeltPouch_4x6"].strip_front))


# =====================================================================
section("tokens: resolved, or raised -- never passed through")

hip = BAGS["HipPack_10x6x3"]
check("a token resolves to the fraction form",
      hip.resolve("trim to {ring}") == 'trim to 27 3/16"',
      hip.resolve("trim to {ring}"))
check("several tokens in one string",
      hip.resolve("{panel_w} x {panel_h}") == '9⅞" x 5⅞"')
check("text with no token is untouched", hip.resolve("plain") == "plain")
try:
    hip.resolve("the {nonsense} figure")
    check("an unknown token raises", False, "it returned instead")
except B.TokenError as e:
    check("an unknown token raises", True)
    check("...and the message lists what IS available", "ring" in str(e))
try:
    hip.resolve("unclosed {ring")
    check("an unclosed brace raises", False)
except B.TokenError:
    check("an unclosed brace raises", True)

sling = BAGS["SlingPack_13x7x4"]
check("chassis-only tokens are absent without a chassis",
      "loop" not in hip.geometry and "loop" in sling.geometry,
      "so a chassis step that reaches for {loop} on a chassis-less bag fails loudly")
check("handle token exists only with a handle",
      "handle" in sling.geometry and "handle" not in hip.geometry)
check("keeper tokens exist only with keepers",
      "keeper_len" in hip.geometry and "keeper_len" not in sling.geometry)
check("back-pocket tokens exist only with a back pocket",
      "bp_upper" in hip.geometry and "bp_upper" not in sling.geometry)

for name, bag in BAGS.items():
    bad = []
    for key in ("assembly", "stitch_schedule", "tools", "checklist"):
        for row in CONS.get(key, []):
            if not bag.applies(row):
                continue
            for v in row.values():
                if isinstance(v, str):
                    try:
                        bag.resolve(v)
                    except B.TokenError as e:
                        bad.append(str(e))
    check(f"every construction token resolves for {name}", not bad, "; ".join(bad[:2]))


# =====================================================================
section("conditions: a bag is told only what applies to it")

steps = {n: [s["title"] for s in b.assembly(CONS)] for n, b in BAGS.items()}
joined = {n: " | ".join(t) for n, t in steps.items()}

check("a chassis-less bag is not told to close a chassis",
      not any("chassis" in joined[n].lower() for n in
              ("BeltPouch_4x6", "HipPack_10x6x3")),
      joined["HipPack_10x6x3"])
check("a bag with one does", "chassis" in joined["SlingPack_13x7x4"].lower())
check("both belted bags get a keeper step",
      all("keeper" in joined[n].lower()
          for n in ("BeltPouch_4x6", "HipPack_10x6x3")))
check("the strap-carried bags do not",
      not any("keeper" in joined[n].lower()
              for n in ("SlingPack_13x7x4", "StadiumTote_12x12x4")))
check("only the anchored keeper step, or the plain one, never both",
      all(sum(1 for t in steps[n] if "keeper" in t.lower()) <= 1 for n in BAGS),
      str({n: [t for t in steps[n] if "keeper" in t.lower()] for n in BAGS}))
check("HipPack gets the anchored keeper step",
      any("anchor" in t.lower() for t in steps["HipPack_10x6x3"]))
check("BeltPouch, which declares no anchor, gets the plain one",
      not any("anchor" in t.lower() for t in steps["BeltPouch_4x6"]))
check("only HipPack builds a two-layer back panel",
      [n for n in BAGS if any("two layers" in t for t in steps[n])]
      == ["HipPack_10x6x3"],
      str({n: [t for t in steps[n] if "two layers" in t] for n in BAGS}))
check("exactly one keeper step applies to any bag",
      all(sum(1 for t in steps[n] if "keeper" in t.lower()) <= 1 for n in BAGS),
      str({n: [t for t in steps[n] if "keeper" in t.lower()] for n in BAGS}))
check("HipPack gets the both-layers keeper step, not the anchor one",
      any("both layers" in t for t in steps["HipPack_10x6x3"])
      and not any("anchor behind" in t for t in steps["HipPack_10x6x3"]))
check("only the fraying shell is told to pre-wash",
      "Pre-wash" in joined["StadiumTote_12x12x4"]
      and not any("Pre-wash" in joined[n] for n in BAGS
                  if n != "StadiumTote_12x12x4"))
check("only the fraying shell is told to fold raw edges under",
      "fold under" in joined["StadiumTote_12x12x4"].lower()
      and "fold under" not in joined["HipPack_10x6x3"].lower())
check("only the bag with no rings gets no D-ring step",
      "D-ring" not in joined["BeltPouch_4x6"]
      and all("D-ring" in joined[n] for n in BAGS if BAGS[n].flags["has_drings"]))
check("the belted bags get no handle step",
      not any("Grab handle" in joined[n] for n in ("BeltPouch_4x6", "HipPack_10x6x3")))
# "Build the back panel" is a title in its own right AND a prefix of
# "Build the back panel's zipped pocket" -- match the title, not a substring.
check("only the bag with applied pockets builds a back panel that way",
      [n for n in BAGS
       if any(t.startswith("Build the back panel") for t in steps[n])]
      == ["StadiumTote_12x12x4"],
      str({n: [t for t in steps[n] if t.startswith("Build the back panel")]
           for n in BAGS}))
check("the applied-pocket step and the panel-pocket step are different steps",
      len({s["title"] for s in CONS["assembly"]}) == len(CONS["assembly"]),
      "a rename once collapsed two of them into one")
check("steps are renumbered after filtering, with no gap",
      all([s["n"] for s in b.assembly(CONS)] == list(range(1, len(b.assembly(CONS)) + 1))
          for b in BAGS.values()),
      "a bag that skips three steps must still read 1, 2, 3")
check("the tote gets the most steps and the pouch the fewest",
      len(steps["StadiumTote_12x12x4"]) > len(steps["HipPack_10x6x3"])
      > len(steps["BeltPouch_4x6"]),
      str({n: len(v) for n, v in steps.items()}))

try:
    BAGS["HipPack_10x6x3"].applies({"when": ["has_wheels"]})
    check("an unknown flag raises", False, "it was treated as false")
except ValueError:
    check("an unknown flag raises", True)
check("every flag a construction row names is in the closed set",
      all(f in B.FLAGS
          for key in ("assembly", "stitch_schedule", "tools", "checklist")
          for row in CONS.get(key, [])
          for f in row.get("when", []) + row.get("unless", [])))


# =====================================================================
section("the split back panel and its keepers")

h = BAGS["HipPack_10x6x3"]
check("both panels are two layers, and the inner ones cut as one row of two",
      {r["piece"] for r in h.cut_list()}
      >= {"Panel, full size", "Panel, outer upper", "Panel, outer lower"},
      str({r["piece"] for r in h.cut_list()}))
check("...always two full-size panels, whatever the pockets do",
      any(r["piece"] == "Panel, full size" and r["qty"] == 2
          and F(str(r["l"]["in"])) == h.panel_h for r in h.cut_list()))
check("...and the outer pieces cut as pairs, one per pocketed panel",
      all(any(r["piece"] == n and r["qty"] == len(b.pockets)
              for r in b.cut_list())
          for b in BAGS.values() if b.pockets
          for n in ("Panel, outer upper", "Panel, outer lower")))
check("there is no separate pocket bag any more",
      not any("pocket bag" in r["piece"].lower() for r in h.cut_list()),
      "the inner panel IS the pocket's inner wall, and it is bound on four edges")
check("no bag without a back pocket splits its panel",
      all(any(r["piece"] == "Front and back panel" and r["qty"] == 2
              for r in b.cut_list())
          for b in BAGS.values() if not b.has_back_pocket))
# The same reassembly test the gusset's zipper panel gets. Two strips lapped
# onto a tape either add back up to the piece they replaced, or the panel comes
# out the wrong size and the ring no longer fits it.
check("the two back pieces reassemble to the panel height",
      (h.bp_upper - h.bp_lap) + h.bp_coil + (h.bp_lower - h.bp_lap) == h.panel_h,
      f"{B.frac(h.bp_upper)} + {B.frac(h.bp_lower)} vs {B.frac(h.panel_h)}")
check("upper 2½\", lower 4⅛\", bag 3⅝\"",
      (h.bp_upper, h.bp_lower, h.bp_bag) == (F(5, 2), F(33, 8), F(29, 8)),
      f"{B.frac(h.bp_upper)} / {B.frac(h.bp_lower)} / {B.frac(h.bp_bag)}")
check("the pocket bag reaches the panel's bottom edge",
      h.bp_bag == h.bp_lower - h.bp_lap,
      "so its sides and bottom are caught in the panel's own binding")
# band = zip_from_top − ½", which is why belt width and pocket depth trade
# against each other off the same 5⅞" of panel.
check("the keeper band is what is left of the upper piece",
      h.bp_band == h.bp_upper - h.bp_lap - h.sa == h.bp_zip - F(1, 2) == F(13, 8))
check("the keepers fit inside that band with room for their tacks",
      h.bp_band >= h.loop_for + F(1, 2), B.frac(h.bp_band))
# --- the pocket is a separate space, and the belt never loads the zip -----
check("the back panel is two layers", h.panel_layers["back"] == 2)
check("the pocket is sealed from the main compartment",
      not any(not ok and "sealed space" in n for ok, n, _ in h.checks()),
      "the inner panel is the main compartment's rear wall, bound on four edges")
flat = variant("HipPack_10x6x3")
flat.panel_layers["back"] = 1              # as if the pocket were a slot in one layer
check("a single-layer panel with a zip in it is caught",
      any(not ok and "sealed space" in n for ok, n, _ in flat.checks()),
      "the zip would be a second way into the main compartment")

zip_top = B.TURN_IN + h.bp_zip - h.bp_coil / 2
check("every keeper sits above the pocket zip",
      all(F(str(f["v"])) + F(str(f["h"])) <= zip_top
          for f in h.spec["features"]["placements"] if f["kind"] == "belt-loop"),
      f"zip line at {B.frac(zip_top)}")
check("...so the belt load reaches the inner panel without crossing the zip",
      not any(not ok and "bypasses the pocket zip" in n for ok, n, _ in h.checks()))
sunk = variant("HipPack_10x6x3")
sunk.spec["features"]["placements"] = [
    {"kind": "belt-loop", "face": "back", "u": 1.5, "v": 3.0, "w": 1.5, "h": 1.5}]
check("a keeper placed below the zip is caught",
      any(not ok and "bypasses the pocket zip" in n for ok, n, _ in sunk.checks()),
      "it would hang the loaded bag off the lower piece, whose only attachment "
      "upward is the zipper")
check("a bag with no pocket zip is not asked the question",
      not any("bypasses the pocket zip" in n
              for _, n, _ in BAGS["BeltPouch_4x6"].checks()),
      "there is no zip in its panel to bypass")

# --- the divider ----------------------------------------------------------
check("the divider is a piece, inset clear of the binding",
      any(r["piece"] == "Divider pocket" and F(str(r["w"]["in"])) == h.div_w
          and F(str(r["l"]["in"])) == h.div_h for r in h.cut_list()))
check("topstitched, it is cut to the FACE less two insets",
      h.div_attach == "topstitch" and h.div_w == h.face_w - 2 * h.div_inset
      == F(69, 8), B.frac(h.div_w))
check("its usable depth is the cut piece less its own bottom seam",
      h.div_depth == h.div_h - h.div_inset == F(3))
check("it stops short of the mouth so you can reach past it",
      h.div_clear == h.face_h - h.div_inset - h.div_h == F(13, 8))
# Out of the binding it costs three straight runs and gives back a bound edge,
# a layer in the worst seam, and any argument with a rounded corner.
check("out of the binding, it adds nothing to the binding run",
      h.binding == 2 * (2 * h.panel_w + 2 * h.panel_h) - 2 * h.corner_cut_saved,
      "a bound divider would add its own top edge")
bound_div = variant("HipPack_10x6x3", corners={"bottom_in": 0},
                    divider={**h.spec["divider"], "attach": "binding"})
check("...whereas a bound one does add its top edge",
      bound_div.binding == 2 * (2 * h.panel_w + 2 * h.panel_h) + h.panel_w)
check("a bound divider reaching a rounded corner is caught",
      any(not ok and "clears the rounded corners" in n for ok, n, _ in
          variant("HipPack_10x6x3",
                  divider={**h.spec["divider"], "attach": "binding"}).checks()),
      "its own corners would have to be cut to the radius")
check("three channels, and the middle one is the wide one",
      [B.frac(x) for x in
       (F(2, 1) + F(1, 16), F(5), F(2, 1) + F(1, 16))] == ['2 1/16"', '5"', '2 1/16"'])
check("a channel too narrow to hold anything is caught",
      any(not ok and "wide enough to use" in n for ok, n, _ in
          variant("HipPack_10x6x3",
                  divider={**h.spec["divider"], "channels_in": [2.5, 3.0, 7.5]}).checks()),
      "a ½\" channel is a pleat, not a pocket")
check("a divider too tall to reach past is caught",
      any(not ok and "reach past it" in n for ok, n, _ in
          variant("HipPack_10x6x3",
                  divider={**h.spec["divider"], "height_in": 5.25}).checks()))
# A channel line is topstitched through the panel, so it shows outside -- and
# outside is where the embroidery goes.
# The front pocket's outer layer now covers the divider's channel stitching,
# so the logo clash cannot arise -- on a single-layer panel it still can.
bare = copy.deepcopy(h.spec)
bare["panel_pockets"] = {k_: v for k_, v in bare["panel_pockets"].items() if k_ != "front"}
bare["divider"] = {**bare["divider"], "channels_in": [5.0]}
check("channels that would cross the embroidery field are caught",
      any(not ok and "clear the embroidery field" in n
          for ok, n, _ in B.BoxBag(bare).checks()),
      "on a single-layer panel the stitching shows, and cannot be moved after")
check("...and with a pocket over them the question does not arise",
      any(ok and "hidden by the outer layer" in n for ok, n, _ in h.checks()))
check("topstitched, the divider adds no layer to any bound seam",
      h.panel_layers == {"front": 2, "back": 2}
      and h.panel_seam_mm["front"] == h.panel_seam_mm["back"] > h.seam_mm,
      f"{h.panel_layers} / {h.panel_seam_mm}")
check("...and a bound one would",
      bound_div.panel_layers["front"] == 3
      and bound_div.panel_seam_mm["front"] > bound_div.panel_seam_mm["back"])
check("only the bag that declares one gets a divider step",
      [n for n, b in BAGS.items()
       if any("Divider pocket" in s["title"] for s in b.assembly(CONS))]
      == ["HipPack_10x6x3"])
check("the divider shows in the 3D model as an interior pocket",
      any(f["kind"] == "pocket" and f.get("interior") and f.get("derived")
          for f in h.model3d()["features"]))

# --- rounded corners --------------------------------------------------------
# A curve costs neither a mitre nor a clip, and the gusset does not notice: a
# band standing on a curved edge is a developable surface, so a flat strip
# follows it with no easing at all.
check("the bottom corners are curved and the top ones are not",
      h.corner_r == F(3, 2) and h.curved_corners == 2 and h.square_corners == 2)
check("at the cut edge the same corner is one seam allowance further out",
      h.corner_cut_r == h.corner_r + h.sa == F(15, 8))
load = {r["item"]: r["count"] for r in h.assembly_load()}
check("half the mitres are gone, and half the clips with them",
      load["Mitred corners"] == 4 and load["Rounded corners"] == 4
      and load["Gusset corner clips"] == 4,
      str(load))
sq = variant("HipPack_10x6x3", corners={"bottom_in": 0})
sqload = {r["item"]: r["count"] for r in sq.assembly_load()}
check("...against 8 and 8 with square corners",
      sqload["Mitred corners"] == 8 and sqload["Gusset corner clips"] == 8
      and "Rounded corners" not in sqload)
# Each quarter turn replaces 2R of path with pi*R/2.
check("the ring shortens by R × (2 − π/2) per corner",
      h.ring == 2 * (h.face_w + h.face_h) - h.corner_saved == F(435, 16),
      B.frac(h.ring))
check("...and so does the binding, at the cut radius",
      h.binding < sq.binding and h.corner_cut_saved > h.corner_saved,
      f"{B.frac(h.binding)} vs {B.frac(sq.binding)}")
check("the ring still closes on the shortened perimeter",
      h.gusset_face + h.zip_face == h.ring)

check("a curved corner forces bias binding", h.bind_bias and not sq.bind_bias)
# Bias runs diagonally, so it cannot be shelf-nested along the roll. Drawing it
# there would be a picture of something you cannot cut.
check("bias binding is kept out of the nesting layout",
      not any(p["piece"] == "Binding strip"
              for lay in h.layouts() for p in lay["pieces"]),
      str([p["piece"] for lay in h.layouts() for p in lay["pieces"]]))
check("...and straight-grain binding stays in it",
      any(p["piece"] == "Binding strip"
          for lay in sq.layouts() for p in lay["pieces"]))
check("bias is priced off a square instead",
      any("BIAS" in r["item"] and "square" in r["qty"] for r in h.takeoff()),
      "a square of side S yields about S² / w of continuous bias")
check("...and the square really does hold the strip's own area",
      float(h.bias_square) ** 2 >= float(h.binding_buy) * float(h.bind_cut),
      f"{B.frac(h.bias_square)} square for "
      f"{float(h.binding_buy) * float(h.bind_cut):.1f} in²")
check("a square-cornered bag needs no bias square", sq.bias_square == 0)
check("...and bias costs about 30% more to buy",
      h.binding_buy / h.binding > F(3, 2),
      f"{B.frac(h.binding_buy)} bought for {B.frac(h.binding)} needed")
check("a radius tighter than the binding shows is caught",
      any(not ok and "can take a binding" in n for ok, n, _ in
          variant("HipPack_10x6x3", corners={"bottom_in": 0.25}).checks()),
      "the binding cannot lie round a curve narrower than itself")
check("a radius past half the shorter face is caught",
      any(not ok and "leaves a straight run" in n for ok, n, _ in
          variant("HipPack_10x6x3", corners={"bottom_in": 3.0}).checks()),
      "the curves would meet and there would be no flat edge left")
check("square-cornered bags are untouched",
      all(b.corner_r == 0 and not b.bind_bias and b.square_corners == 4
          for n, b in BAGS.items() if n != "HipPack_10x6x3"))
check("the 3D model carries the radius so the preview rounds the same corners",
      h.model3d()["corner_radius"]["in"] == float(h.corner_cut_r))
check("every bag reports what it costs to sew",
      all(len(b.assembly_load()) >= 7 for b in BAGS.values()))

# --- the curve reaches every piece it touches -------------------------------
CURVED = {r["piece"] for r in h.cut_list() if r["corners"] != "square"}
check("the pieces that carry the bottom edge are not rectangles",
      CURVED == {"Panel, full size", "Panel, outer lower", "Divider pocket"},
      str(CURVED))
check("...and the ones that do not are still square",
      all(r["corners"] == "square" for r in h.cut_list()
          if r["piece"] in ("Panel, outer upper", "Gusset", "Belt keeper")))
check("every curved row states its radius in the note",
      all("BOTTOM CORNERS ROUND" in r["note"] for r in h.cut_list()
          if r["corners"] != "square"))
check("the nesting layout carries the radius so it can be drawn",
      any(p.get("r", 0) > 0 for lay in h.layouts() for p in lay["pieces"]),
      "a cutting layout that draws a curved piece as a rectangle is one you cut wrong")
check("a square-cornered bag has no curved pieces",
      all(r["corners"] == "square"
          for r in BAGS["SlingPack_13x7x4"].cut_list()))

# Inset a uniform distance from a curved boundary, a piece's own corners are
# that curve offset inward. Cut square, the divider overhangs by 0.42".
check("the divider's corners are the panel's curve offset by its inset",
      h.div_r == h.corner_r - h.div_inset == F(5, 4), B.frac(h.div_r))
check("a divider inset further than the radius gets no negative curve",
      variant("HipPack_10x6x3",
              divider={**h.spec["divider"], "inset_in": 2.0}).div_r == 0)

# A flat strip's raw edge has to reach 25% further than its stitch line round a
# convex curve. "A curve needs no clip" was wrong -- it needs distributed ones.
import math as _m
check("a curve needs relief clips, spaced a seam allowance apart",
      h.relief_clips == _m.ceil(float(h.corner_r) * _m.pi / 2 / float(h.sa)) == 7)
check("...and they are counted in the assembly load",
      load["Gusset relief clips"] == 28)
check("a square-cornered bag has none",
      sq.relief_clips == 0
      and "Gusset relief clips" not in {r["item"] for r in sq.assembly_load()})

# A rounded bottom corner pinches the pocket too, so the rectangle the cut list
# implies is optimistic. Small here, but it scales with radius and item width.
check("pocket depth accounts for the curve",
      h.pocket_depth_for("back", F("6.42")) < h.pocket_interior("back")[1],
      "the corners come off the pocket as well as the panel")
check("...and the phone still fits",
      h.pocket_depth_for("back", F("6.42")) >= F("3.06"),
      B.frac(h.pocket_depth_for("back", F("6.42"))))
check("a square-cornered pocket loses nothing",
      sq.pocket_depth_for("back", F("6.42")) == sq.pocket_interior("back")[1])
check("an item as wide as the pocket loses the most depth",
      h.pocket_depth_for("back", h.face_w) < h.pocket_depth_for("back", F(4)))

check("the doubled panel makes the thickest seam on the bag",
      h.panel_seam_mm["back"] > h.seam_mm and h.panel_corner_mm["back"] > h.corner_mm
      and abs(h.panel_seam_mm["back"] - 2.5) < 1e-9,
      f"{h.panel_seam_mm} vs {h.seam_mm} mm")
check("the binding is sized from the worst seam, not the average",
      h.bind_cut == F(9, 8) and bound_div.bind_cut == F(5, 4),
      f"{B.frac(h.bind_cut)} for 1.50 mm; {B.frac(bound_div.bind_cut)} for 2.00")
# ceil, not round: 1.1412" rounding to 1⅛" is 0.4 mm short of reaching, and it
# is short in the one direction nobody discovers until halfway round a bag.
check("a strip that has to reach round something rounds UP",
      B.ceil_to(F("1.1412"), 8) == F(5, 4) and B.round_to(F("1.1412"), 8) == F(9, 8))
check("...and a figure that has to fit INSIDE something rounds down",
      B.floor_to(F("1.1412"), 8) == F(9, 8))
check("...and both leave an exact eighth alone",
      B.ceil_to(F(9, 8), 8) == B.floor_to(F(9, 8), 8) == F(9, 8)
      and B.ceil_to(F(1), 8) == B.floor_to(F(1), 8) == F(1))
# Rounding a capacity to NEAREST reports room that is not there: the
# curve-aware pocket depth came out 3.2427" and rounded straight back to the
# 3.25" rectangle answer the curve was meant to correct.
check("the pocket depth is floored, not rounded",
      h.pocket_depth_for("back", F("6.42")) == F(51, 16)
      < B.round_to(F("3.2427"), 16))
check("a single-layer bag's seams are untouched",
      all(b.panel_seam_mm["back"] == b.seam_mm for b in BAGS.values() if not b.has_back_pocket))

check("the pocket's usable depth is the cut piece less one seam allowance",
      h.pocket_interior("back")[1] == h.bp_bag - h.sa == F(13, 4),
      "the sides and bottom are caught in the binding, so it is not interior")
check("a large phone fits the pocket, with little to spare",
      h.pocket_interior("back")[1] >= F("3.06") and h.pocket_interior("back")[1] - F("3.06") < F(1, 4),
      f"{B.frac(h.pocket_interior("back")[1])} against 3.06\"")

deep = variant("HipPack_10x6x3",
               panel_pockets={"back": {"zip_from_top_in": 2.75, "must_hold_in": [6.42, 3.06]},
                        "front": {"zip_from_top_in": 2.75}})
check("a pocket zip moved down for a wider belt stops holding the phone",
      any(not ok and "holds what it must" in n for ok, n, _ in deep.checks()),
      "belt width, pocket depth and panel height all come off the same 5⅞\"")

tight = variant("HipPack_10x6x3",
                panel_pockets={"back": {"zip_from_top_in": 1.25},
                               "front": {"zip_from_top_in": 1.25}})
check("a pocket zip crowded up against the keepers is caught",
      any(not ok and "keepers fit" in n for ok, n, _ in tight.checks()),
      "band would be only 3/8\" of panel to tack two loaded keepers into")

edge = variant("HipPack_10x6x3",
               panel_pockets={"back": {"zip_from_top_in": 0.4},
                              "front": {"zip_from_top_in": 0.4}})
check("a pocket zip inside the binding flange is caught",
      any(not ok and "back pocket coil clears" in n for ok, n, _ in edge.checks()))

check("the keeper cut length wraps the belt and back",
      h.loop_len == 2 * h.loop_for + F(3, 2) == F(7, 2),
      B.frac(h.loop_len))
# The rule of thumb is generous on purpose -- a keeper is fitted round the real
# belt and trimmed, not cut to a number. What the generator owes you is the
# guarantee that the generous figure covers what the method actually consumes.
check("the keeper's minimum is fold + tack + belt + two thicknesses, each end",
      h.keeper_min == 2 * B.KEEPER_FOLD_IN + 2 * B.KEEPER_TACK_IN + h.loop_for
      + B.round_to(2 * B.WEBBING_MM / B.MM_PER_IN, 16) == F(25, 8),
      B.frac(h.keeper_min))
check("every keeper is cut long enough, with trim to spare",
      all(b.loop_len > b.keeper_min for b in BAGS.values() if b.loops),
      str({n: (B.frac(b.loop_len), B.frac(b.keeper_min))
           for n, b in BAGS.items() if b.loops}))
tightloop = variant("HipPack_10x6x3",
                    features={**h.spec["features"],
                              "belt_loops": {**h.spec["features"]["belt_loops"],
                                             "width_in": 1.5, "for_in": 1.0}})
tightloop.loop_len = F(5, 2)                      # cut short by hand
check("a keeper too short to fold, tack and arch is caught",
      any(not ok and "long enough to fold" in n for ok, n, _ in tightloop.checks()),
      "it would be unthreadable, and only after both tacks were in")
check("two keepers, not one", h.loop_count == 2)
check("the doubled panel replaced the belt anchor strip",
      not any(r["piece"] == "Belt anchor strip" for r in h.cut_list())
      and not h.loop_anchor,
      "a panel bound on four edges anchors better than a strip caught at two ends")
check("BeltPouch's single keeper still comes out 2\" x 5½\"",
      any(r["piece"] == "Belt keeper" and r["qty"] == 1
          and F(str(r["w"]["in"])) == F(2) and F(str(r["l"]["in"])) == F(11, 2)
          for r in BAGS["BeltPouch_4x6"].cut_list()),
      "the belt_loops migration must not have moved it")
check("BeltPouch declares no anchor, so it gets no anchor strip",
      not any(r["piece"] == "Belt anchor strip"
              for r in BAGS["BeltPouch_4x6"].cut_list()))
check("a keeper narrower than its belt is caught",
      any(not ok and "wide enough for the belt" in n for ok, n, _ in
          variant("HipPack_10x6x3",
                  features={**h.spec["features"],
                            "belt_loops": {"for_in": 2.0, "count": 2,
                                           "width_in": 1.5}}).checks()))

check("dropping the chassis re-centres the coil",
      h.coil_c == h.gusset_w / 2 and h.strip_front == h.strip_rear,
      f"{B.frac(h.coil_c)}, strips {B.frac(h.strip_front)}")
check("...and the flange clearance goes from ¼\" to 15/16\"",
      h.coil_c - h.coil / 2 - h.sa == F(15, 16),
      B.frac(h.coil_c - h.coil / 2 - h.sa))
check("no chassis means no chassis webbing in the takeoff",
      not any("chassis" in t["note"].lower() for t in h.takeoff()))
check("the keeper tack is in the thickness budget",
      any("keeper" in r["location"].lower() for r in h.thickness()))
# Three layers on the front panel put the mitred corner past the ring tack.
check("HipPack's peak is its ring tack again, now the divider is out of the seam",
      abs(h.peak_mm() - (2 * B.WEBBING_MM + 2 * h.shell_mm)) < 1e-9,
      f"{h.peak_mm()} mm")


# =====================================================================
section("technique notes, and the steps that link to them")

WEB = "patterns/techniques/webbing-hardware.md"
for name, bag in BAGS.items():
    steps = bag.assembly(CONS)
    have = {d["path"] for d in CONS["docs"] + bag.docs_declared()}
    dead = [(s["n"], p) for s in steps for p in s["see"] if p not in have]
    check(f"{name}: every step link resolves", not dead, str(dead))
    check(f"{name}: some step links somewhere",
          any(s["see"] for s in steps),
          "a construction whose steps teach no method is a construction that "
          "will grow one paragraph per step instead")

check("the keeper step points at the webbing note",
      all(WEB in next(s for s in b.assembly(CONS) if "keeper" in s["title"].lower())["see"]
          for b in BAGS.values() if b.loops))
check("bags without keepers still link it from the tab and handle steps",
      WEB in {p for s in BAGS["StadiumTote_12x12x4"].assembly(CONS) for p in s["see"]})
check("a dead step link is caught",
      any(not ok and "step link" in n for ok, n, _ in
          B.BoxBag({**BAGS["HipPack_10x6x3"].spec}).package_checks(
              {**CONS, "assembly": [{"n": 1, "title": "x", "body": "y",
                                     "see": ["patterns/techniques/nope.md"]}]})),
      "it would render as nothing, and the step would read as if no method existed")

TECHNIQUES = sorted(p for p in (REPO / "patterns/techniques").glob("*.md")
                    if p.name != "README.md")
INDEX = (REPO / "patterns/techniques/README.md").read_text(encoding="utf-8")
check("there are technique notes to link", len(TECHNIQUES) >= 3,
      str([p.name for p in TECHNIQUES]))

for p in TECHNIQUES:
    note = p.read_text(encoding="utf-8")
    n = p.name
    check(f"{n}: substantial enough to be worth linking", len(note) > 4000, str(len(note)))
    check(f"{n}: carries diagrams as inline SVG", note.count("```svg") >= 1,
          f"{note.count('```svg')} fences")
    # A diagram that exists only as a picture excludes the people most likely
    # to need it, and one with literal colours works in exactly one theme.
    check(f"{n}: every diagram is labelled for a screen reader",
          note.count('role="img"') == note.count("```svg")
          and note.count("aria-label") >= note.count("```svg"),
          f"{note.count('role=\"img\"')} labels for {note.count('```svg')} diagrams")
    check(f"{n}: diagrams draw with theme tokens", note.count("var(--") > 15)
    check(f"{n}: keeps a 'When it goes wrong' table", "When it goes wrong" in note,
          "the failure modes are the part worth writing down")
    check(f"{n}: ends with a 'Used by' line", "*Used by:*" in note)
    check(f"{n}: the techniques index lists it", n in INDEX)
    # A technique note must stand alone -- no bag's dimensions in it.
    check(f"{n}: states no bag's dimensions",
          not any(x in note for x in ("9⅞", "5⅞", "28½", "43¼", "10 × 6 × 3")),
          "a note that quotes one bag's figures cannot be reused by the next")

# The other direction from the dead-link check: a note nobody links is a note
# nobody reads.
linked = {q for s in CONS["assembly"] for q in s.get("see", [])}
check("every technique note is linked from at least one step",
      all(f"patterns/techniques/{p.name}" in linked for p in TECHNIQUES),
      str([p.name for p in TECHNIQUES
           if f"patterns/techniques/{p.name}" not in linked]))
check("...and the generator checks that too",
      any("technique note is linked" in n
          for _, n, _ in BAGS["HipPack_10x6x3"].package_checks(CONS)))
orphaned = {**CONS, "docs": CONS["docs"] + [
    {"title": "unlinked", "path": "patterns/techniques/binding.md", "kind": "technique"}],
    "assembly": [{"n": 1, "title": "x", "body": "y"}]}
check("an orphaned technique note is caught",
      any(not ok and "technique note is linked" in n
          for ok, n, _ in BAGS["HipPack_10x6x3"].package_checks(orphaned)))

# Every step is accounted for: it either teaches a method or deliberately does not.
titles = [s["title"] for s in CONS["assembly"]]
unlinked = [s["title"] for s in CONS["assembly"] if not s.get("see")]
check("most steps reach a method",
      len(unlinked) <= len(titles) // 3,
      f"{len(titles) - len(unlinked)} of {len(titles)} linked; unlinked: {unlinked}")
check("the zipper steps reach the zipper note",
      all(any("zippers.md" in q for q in s.get("see", []))
          for s in CONS["assembly"] if "zip" in s["title"].lower()),
      str([s["title"] for s in CONS["assembly"]
           if "zip" in s["title"].lower() and not any("zippers" in q for q in s.get("see", []))]))
check("the binding steps reach the binding note",
      all(any("binding.md" in q for q in s.get("see", []))
          for s in CONS["assembly"] if "bound" in s["title"].lower()))
check("the embroidery step reaches the embroidery docs",
      any(q.startswith("docs/") for s in CONS["assembly"]
          if "embroider" in s["title"].lower() for q in s.get("see", [])),
      "the two halves of this repo meet at exactly one step")


# =====================================================================
section("D-rings, and what has to be behind one")

# The StadiumTote's central lesson, made into a rule: a tab box-X'd to one layer
# of shell puts the whole bag into a stitch field.
check("a ring needs a chassis or an anchor behind it",
      all(b.has_chassis or b.flags["has_ring_anchor"]
          for b in BAGS.values() if b.flags["has_drings"]),
      str({n: (b.has_chassis, b.flags["has_ring_anchor"])
           for n, b in BAGS.items() if b.flags["has_drings"]}))
naked = variant("HipPack_10x6x3",
                features={**h.spec["features"], "d_ring_anchor": False})
check("a ring with nothing behind it is caught",
      any(not ok and "something behind them" in n
          for ok, n, _ in naked.package_checks(CONS)),
      "it would tear out of the shell, and only under load")
check("the chassis counts as backing",
      not any(not ok and "something behind them" in n
              for ok, n, _ in BAGS["SlingPack_13x7x4"].package_checks(CONS)))
check("a bag with no rings is not asked for backing",
      not any("something behind them" in n
              for _, n, _ in BAGS["BeltPouch_4x6"].package_checks(CONS)))

check("the anchor spans the gusset's full cut width",
      any(r["piece"] == "D-ring anchor strip" and F(str(r["w"]["in"])) == h.gusset_w
          and r["qty"] == 2 for r in h.cut_list()),
      "both ends have to reach the panel bindings or it anchors nothing")
check("only the anchored bag cuts anchor strips",
      [n for n, b in BAGS.items()
       if any(r["piece"] == "D-ring anchor strip" for r in b.cut_list())]
      == ["HipPack_10x6x3"])
check("the ring-anchor step appears only where there are anchors",
      [n for n, b in BAGS.items()
       if any("Ring anchors" in s["title"] for s in b.assembly(CONS))]
      == ["HipPack_10x6x3"])

# The tack stack changes with what is behind it, and the thickness table has to
# follow -- webbing behind is 1.3 mm, a Cordura anchor is 0.5.
check("the tack stack names what actually backs it",
      "anchor strip" in next(r["stack"] for r in h.thickness() if "D-ring" in r["location"])
      and "internal webbing" in next(r["stack"] for r in
                                     BAGS["SlingPack_13x7x4"].thickness()
                                     if "D-ring" in r["location"]))
check("...and an anchored tack is thinner than a chassis one",
      h.peak_mm() < BAGS["SlingPack_13x7x4"].peak_mm(),
      f"{h.peak_mm()} vs {BAGS['SlingPack_13x7x4'].peak_mm()} mm")

# Nothing that gets tacked may sit under the binding: that is the thickest part
# of the bag. Pieces MEANT to be caught in it are exempt.
check("nothing tacked sits under the binding, on any bag",
      all(not any(not ok and "under the binding" in n
                  for ok, n, _ in b.package_checks(CONS)) for b in BAGS.values()))
buried = variant("HipPack_10x6x3")
buried.spec["features"]["placements"] = [
    {"kind": "dring", "face": "left", "u": 0.3, "v": 1.0}]
check("a tack placed under the binding is caught",
      any(not ok and "under the binding" in n
          for ok, n, _ in buried.package_checks(CONS)),
      "it would land in the thickest stack on the bag")
check("...but a full-width pocket bag caught in the binding is exempt",
      not any(not ok and "under the binding" in n
              for ok, n, _ in BAGS["StadiumTote_12x12x4"].package_checks(CONS)),
      "its sides and bottom reach the flange by design")

check("the sling is derived from the crossbody figure",
      h.sling_cut == B.round_to(h.crossbody + h.sling_takeup, 1) == F(56),
      B.frac(h.sling_cut))
check("and the belt shortened once the sling took its second job",
      h.fit_max == h.waist[1] == F(44) and h.belt_cut == F(50),
      f"{B.frac(h.belt_cut)} from a {B.frac(h.fit_max)} fit")
check("a bag with no rings still sizes its belt for crossbody",
      variant("HipPack_10x6x3", features={"d_rings": 0}).fit_max == h.crossbody,
      "the belt has to do both jobs when nothing else can")
check("the sling appears in the takeoff",
      any("sling" in t["item"].lower() for t in h.takeoff()))
check("both stay rigged at once",
      any("belt" in t["item"].lower() for t in h.takeoff())
      and any("sling" in t["item"].lower() for t in h.takeoff()),
      "belt and sling are separate lengths, so unclipping one leaves the other")


# =====================================================================
section("the wearer, and the comfort figures")

check("the belt is derived from the declared fit range, not typed in",
      h.belt_cut == B.round_to(h.fit_max + h.belt_tail, 1) == F(50),
      B.frac(h.belt_cut))
check("the waist is the binding fit now the sling exists",
      h.fit_max == h.waist[1] == F(44) < h.crossbody,
      "before the rings, the belt had to reach 52\" as well")
check("the belt appears in the takeoff as a derived row",
      any("belt" in t["item"].lower() and "derived" in t["note"].lower()
          for t in h.takeoff()))
check("belt tokens exist only when a wearer is declared",
      "belt_cut" in h.geometry
      and "belt_cut" not in BAGS["BeltPouch_4x6"].geometry)

wide = variant("HipPack_10x6x3", finished_in={"w": 26, "h": 6, "d": 3})
check("a bag wider than its smallest wearer's waist is caught",
      any(not ok and "smallest declared wearer" in n for ok, n, _ in wide.checks()),
      "the buckle and tri-glide need somewhere that is not under the bag")

# Deliberately NOT "does the belt reach the largest fit" -- it is derived from
# that fit, so the check could only ever pass. The tail is the declared part.
short = variant("HipPack_10x6x3", wearer={**h.spec["wearer"], "tail_in": 2})
check("too little tail to grip and pull is caught",
      any(not ok and "tail enough" in n for ok, n, _ in short.checks()),
      "a buckle and a tri-glide eat into whatever is left")
check("...and the belt still lengthens to match",
      short.belt_cut == h.fit_max + 2 < h.belt_cut)

rows = {r["measure"]: r for r in h.comfort()}
check("occlusion tension is reported, not enforced",
      "Belt tension at blood occlusion" in rows
      and not any("occlusion" in n.lower() for _, n, _ in h.checks()),
      "the belt tension a wearer applies has not been measured here")
# 16 kPa x R x w, on the SMALLEST declared waist -- pressure goes as 1/R, so a
# small waist is the worst case, and reporting the largest would flatter it.
r_m = float(h.waist[0]) * B.MM_PER_IN / 1000.0 / (2 * math.pi)
want = B.OCCLUSION_KPA * 1000 * r_m * float(h.loop_for) * B.MM_PER_IN / 1000.0
check("...and it is 16 kPa x radius x belt width",
      abs(float(rows["Belt tension at blood occlusion"]["value"].split()[0]) - want) < 1,
      f"{rows['Belt tension at blood occlusion']['value']} vs {want:.0f} N")
occl_N = lambda bag: float({r["measure"]: r for r in bag.comfort()}
                           ["Belt tension at blood occlusion"]["value"].split()[0])
wider = variant("HipPack_10x6x3",
                features={**h.spec["features"],
                          "belt_loops": {**h.spec["features"]["belt_loops"],
                                         "for_in": 1.5}})
narrower = variant("HipPack_10x6x3",
                   features={**h.spec["features"],
                             "belt_loops": {**h.spec["features"]["belt_loops"],
                                            "for_in": 0.75}})
check("a wider belt raises it, which is the whole argument",
      occl_N(narrower) < occl_N(h) < occl_N(wider),
      f"¾\" {occl_N(narrower):.0f} N < 1\" {occl_N(h):.0f} N < 1½\" {occl_N(wider):.0f} N")
check("...and the previous ¾\" belt was a third worse",
      occl_N(h) / occl_N(narrower) > 1.3,
      f"{occl_N(h) / occl_N(narrower):.2f}x")
check("but the wider belt no longer fits the keeper band",
      any(not ok and "keepers fit clear" in n for ok, n, _ in wider.checks()),
      "which is the bound from above meeting the bound from below")
check("the taper the belt gets wrong scales with its width",
      rows["Circumference the belt gets wrong"]["value"] == B.frac(h.taper * h.loop_for)
      == '¾"',
      "which is the bound from ABOVE -- webbing cannot be cut curved")
check("the padded-seam figure is over the stop-dead thickness",
      float(rows["Bound seam if the back panel were padded"]["value"].split()[0])
      > B.STACK_STOP_MM,
      "so 'no padding' is arithmetic, not taste")
check("the slider park side follows the declared handedness",
      "left" in rows["Pocket sliders park"]["value"],
      "a right-handed wearer pulls it rightward, so it parks left")
check("every comfort row states its basis",
      all(len(r["basis"]) > 40 for r in h.comfort()),
      "a figure with no provenance is a figure that drifts")
check("every bag reports capacity against the tested band",
      all(any(r["measure"] == "Capacity" for r in b.comfort()) for b in BAGS.values()))
check("the construction cites its sources",
      len(CONS.get("sources", [])) >= 5
      and all(s["url"].startswith("https://") and s.get("gives")
              for s in CONS["sources"]))


# =====================================================================
section("the 3D model")

for name, bag in BAGS.items():
    m = bag.model3d()
    fin = {"w": bag.W, "h": bag.H, "d": bag.D}
    pairs = {"front": ("w", "h"), "back": ("w", "h"), "left": ("d", "h"),
             "right": ("d", "h"), "top": ("w", "d"), "bottom": ("w", "d")}
    ok = all(F(str(m["faces"][f]["w"]["in"])) == fin[a]
             and F(str(m["faces"][f]["h"]["in"])) == fin[b]
             for f, (a, b) in pairs.items())
    check(f"{name}: every face is the right two dimensions", ok)
    kinds = {ft["kind"] for ft in m["features"]}
    check(f"{name}: every feature kind is one the renderer knows",
          kinds <= set(B.FEATURE_KINDS), str(kinds - set(B.FEATURE_KINDS)))
    check(f"{name}: the zip is derived, not declared",
          any(ft["kind"] == "zip" and ft.get("derived") for ft in m["features"]))
    bad = [c for ok_, n, c in bag.package_checks(CONS)
           if not ok_ and "placements" in n]
    check(f"{name}: every placement sits on its face", not bad, "; ".join(bad))

check("the derived zip sits where the cut list says the coil does",
      all(abs(next(f for f in b.model3d()["features"] if f["kind"] == "zip")["v"]
              - float(B.TURN_IN + b.coil_c - b.coil / 2)) < 1e-9
          for b in BAGS.values()),
      "the drawing and the cut list must not be able to disagree")
check("the chassis band sits between the coil and the back of the gusset",
      all(next(f for f in b.model3d()["features"] if f["kind"] == "webbing")
          ["across_depth_in"] > float(B.TURN_IN + b.coil_c + b.coil / 2)
          for b in BAGS.values() if b.has_chassis))

off = variant("HipPack_10x6x3")
off.spec["features"]["placements"] = [
    {"kind": "dring", "face": "left", "u": 9.0, "v": 1.0}]        # face is only 3" wide
check("a placement off the edge of its face is caught",
      any(not ok and "placements" in n for ok, n, _ in off.package_checks(CONS)),
      "a feature drawn outside the bag would just be clipped, and look fine")

badkind = variant("HipPack_10x6x3")
badkind.spec["features"]["placements"] = [
    {"kind": "grommet", "face": "front", "u": 1, "v": 1, "w": 1, "h": 1}]
check("an unknown feature kind is caught",
      any(not ok and "placements" in n for ok, n, _ in badkind.package_checks(CONS)),
      "the renderer would silently draw nothing")


# =====================================================================
section("cut list, nesting and takeoff")

for name, bag in BAGS.items():
    rows = bag.cut_list()
    check(f"{name}: the cut list has both panels", any(r["qty"] == 2 for r in rows))
    check(f"{name}: every row names a real material",
          all(r["material"] in B.MATERIALS for r in rows),
          str({r["material"] for r in rows} - set(B.MATERIALS)))
    check(f"{name}: every cut size is positive",
          all(r["w"]["in"] > 0 and r["l"]["in"] > 0 for r in rows))
    check(f"{name}: the gusset is cut long",
          any(r["piece"] == "Gusset" and F(str(r["l"]["in"])) == bag.gusset_cut + 3
              for r in rows),
          "the ring's true length depends on the allowance you achieve")

    for lay in bag.layouts():
        ps = lay["pieces"]
        check(f"{name}/{lay['material']}: nothing exceeds the roll width",
              all(p["x"] + p["w"] <= lay["roll_width_in"] + 1e-9 for p in ps),
              str([p["piece"] for p in ps if p["x"] + p["w"] > lay["roll_width_in"] + 1e-9]))
        overlaps = [(a["piece"], b["piece"])
                    for i, a in enumerate(ps) for b in ps[i + 1:]
                    if a["x"] < b["x"] + b["w"] - 1e-9 and b["x"] < a["x"] + a["w"] - 1e-9
                    and a["y"] < b["y"] + b["h"] - 1e-9 and b["y"] < a["y"] + a["h"] - 1e-9]
        check(f"{name}/{lay['material']}: no two pieces overlap", not overlaps,
              str(overlaps[:3]))
        area = sum(p["w"] * p["h"] for p in ps)
        check(f"{name}/{lay['material']}: the nest holds every piece's area",
              area <= lay["roll_width_in"] * lay["used"]["in"] + 1e-6)

    check(f"{name}: webbing and tape are never nested on a roll",
          all(not B.mat(lay["material"]).get("by_length") for lay in bag.layouts()))

check("the tote nests vinyl and denim separately",
      {l["material"] for l in BAGS["StadiumTote_12x12x4"].layouts()}
      >= {"vinyl-20ga", "denim-12oz"})
check("the tote's binding is bought by length, not nested",
      any("nylon-binding-tape" in t["item"] for t in BAGS["StadiumTote_12x12x4"].takeoff()))
check("binding strips add up to at least the buy length",
      all(sum(bag.binding_strips()) >= bag.binding_buy for bag in BAGS.values()))
check("the buy length exceeds the length actually needed",
      all(bag.binding_buy > bag.binding for bag in BAGS.values()),
      "mitres and joins are not free")


# =====================================================================
section("thickness is derived, never copied")

check("the ring tack stack is two layers of tab, the shell and its backing",
      all(any(abs(r["mm"] - (2 * B.WEBBING_MM + b.shell_mm
                             + (B.WEBBING_MM if b.has_chassis else b.shell_mm))) < 1e-9
              for r in b.thickness() if "D-ring" in r["location"])
          for b in BAGS.values() if b.flags["has_drings"]))
check("a fraying shell bound in itself doubles the binding layers",
      B.BoxBag(variant("HipPack_10x6x3", shell="denim-12oz").spec).bind_layers == 4)
check("the tote's plain bound seam is 2.3 mm",
      abs(t.seam_mm - 2.26) < 0.01, f"{t.seam_mm:.2f}")
check("the tote's mitred corner is 3.3 mm",
      abs(t.corner_mm - 3.26) < 0.01, f"{t.corner_mm:.2f}")
check("every bag is under the stop-dead thickness",
      all(b.peak_mm() <= B.STACK_STOP_MM for b in BAGS.values()),
      str({n: b.peak_mm() for n, b in BAGS.items() if b.peak_mm() > B.STACK_STOP_MM}))
check("every material row carries all four columns",
      all({"mm", "frays"} <= set(v) and ("roll_in" in v or v.get("by_length"))
          for v in B.MATERIALS.values()),
      "add a row rather than guessing a thickness")


# =====================================================================
section("interior volume")

hip_i = BAGS["HipPack_10x6x3"].interior()
# The rounded corners take a bite out of the cross-section, not just the
# perimeter -- 2% here. A stated capacity that ignores the shape is wrong.
check("HipPack interior is 1.59 L, the corners taken off",
      abs(hip_i["litres"] - 1.59) < 0.01, str(hip_i))
check("...and it is less than the face rectangle would give",
      hip_i["in3"] < float(BAGS["HipPack_10x6x3"].face_w
                           * BAGS["HipPack_10x6x3"].face_h
                           * BAGS["HipPack_10x6x3"].face_d))
check("interior is the face box, not the outside",
      all(b.interior()["w"]["in"] < b.finished_w() if hasattr(b, "finished_w")
          else b.interior()["w"]["in"] < float(b.W) for b in BAGS.values()))
check("a square-cornered bag's volume is the three faces multiplied out",
      all(abs(b.interior()["in3"] - float(b.face_w * b.face_h * b.face_d)) < 0.01
          for b in BAGS.values() if not b.corner_r))
check("...and a rounded one loses exactly the corner bites",
      all(abs(b.interior()["in3"]
              - (float(b.face_w * b.face_h)
                 - float(b.corner_r) ** 2 * (1 - math.pi / 4) * b.curved_corners)
              * float(b.face_d)) < 0.01
          for b in BAGS.values() if b.corner_r))


# =====================================================================
section("the package")

pkgs = {}
for name, bag in BAGS.items():
    pkgs[name] = bag.package(SPECS[name], CONS, CONS_PATH, STAMP)

for name, pkg in pkgs.items():
    for k in P.REQUIRED:
        check(f"{name}: package has {k}", k in pkg)
    check(f"{name}: round-trips through JSON",
          json.loads(json.dumps(pkg, ensure_ascii=False)) == pkg)
    check(f"{name}: schema version is stamped",
          pkg["schema_version"] == B.SCHEMA_VERSION == P.SCHEMA_VERSION)
    check(f"{name}: every geometry figure carries both forms",
          all(set(v) == {"in", "text"} and isinstance(v["in"], float)
              for v in pkg["geometry"].values()))
    check(f"{name}: provenance names the spec and the construction",
          pkg["provenance"]["spec"]["path"].endswith(f"{name}.json")
          and pkg["provenance"]["construction"]["path"].endswith("box-bound.json"))
    check(f"{name}: every doc body is inlined",
          all(d["body"].strip() for d in pkg["docs"]),
          str([d["path"] for d in pkg["docs"] if not d["body"].strip()]))
    prose = [v for row in pkg["assembly"] + pkg["checklist"] + pkg["tools"]
             + pkg["stitch_schedule"] for v in row.values() if isinstance(v, str)]
    check(f"{name}: no unresolved token survived into the package",
          not [s for s in prose if "{" in s],
          "a token that survives reads as literal text at the machine: "
          + str([s for s in prose if "{" in s][:1]))
    check(f"{name}: every check reports a detail",
          all(c["detail"] for c in pkg["checks"]))

check("the same inputs give the same package",
      BAGS["HipPack_10x6x3"].package(SPECS["HipPack_10x6x3"], CONS, CONS_PATH, STAMP)
      == pkgs["HipPack_10x6x3"],
      "only generated_at may vary, and it is passed in")

h = BAGS["HipPack_10x6x3"].package(SPECS["HipPack_10x6x3"], CONS, CONS_PATH, "later")
check("...and only the timestamp moves when the stamp does",
      {k: v for k, v in h.items() if k != "provenance"}
      == {k: v for k, v in pkgs["HipPack_10x6x3"].items() if k != "provenance"})

check("every bag declares a zipper",
      all(any(not ok_ for ok_, n, _ in bag.package_checks(CONS)
              if "zipper is declared" in n) is False for bag in BAGS.values()),
      "the cut list sizes the strips; nothing else buys the zipper")

nozip = variant("HipPack_10x6x3", hardware=[{"item": "D-rings", "qty": 2}])
check("a bag with no zipper in its hardware is caught",
      any(not ok_ and "zipper" in n for ok_, n, _ in nozip.package_checks(CONS)))

nodoc = variant("StadiumTote_12x12x4",
                docs=[{"title": "gone", "path": "patterns/nope.md", "kind": "pattern"}])
check("a missing supporting doc is caught",
      any(not ok_ and "docs exist" in n for ok_, n, _ in nodoc.package_checks(CONS)))


# =====================================================================
section("the player's own validation")

check("the packages on disk validate", not P.validate(list(pkgs.values())),
      "; ".join(P.validate(list(pkgs.values()))[:2]))

wrong = copy.deepcopy(pkgs["HipPack_10x6x3"])
wrong["schema_version"] = "0.9"
check("a package from another schema version is refused",
      any("schema_version" in m for m in P.validate([wrong])))

missing = copy.deepcopy(pkgs["HipPack_10x6x3"])
del missing["assembly"]
check("a package missing a key the page dereferences is refused",
      any("assembly" in m for m in P.validate([missing])),
      "otherwise the panel renders blank and the page still looks finished")

emptydoc = copy.deepcopy(pkgs["StadiumTote_12x12x4"])
emptydoc["docs"][0]["body"] = ""
check("an empty inlined doc is refused",
      any("empty" in m for m in P.validate([emptydoc])))

failing = copy.deepcopy(pkgs["HipPack_10x6x3"])
failing["checks"][0]["ok"] = False
check("a package carrying a failed check is refused",
      any("FAILED check" in m for m in P.validate([failing])))

lib = P.library(list(pkgs.values()))
check("the library is ordered smallest bag first",
      [p["name"] for p in lib["patterns"]][0] == "BeltPouch_4x6"
      and [p["name"] for p in lib["patterns"]][-1] == "StadiumTote_12x12x4",
      str([p["name"] for p in lib["patterns"]]))
check("doc bodies are hoisted out of the patterns",
      all("body" not in d for p in lib["patterns"] for d in p["docs"]))
check("...and every referenced path is in the hoisted map",
      all(d["path"] in lib["docs"] for p in lib["patterns"] for d in p["docs"]))
check("the shared construction notes appear once, not four times",
      len(lib["docs"]) < sum(len(p["docs"]) for p in lib["patterns"]))
check("quick help lists the technique note first",
      lib["help"][0]["kind"] == "technique", str([d["kind"] for d in lib["help"]]))
check("the template still has its placeholder",
      P.PLACEHOLDER in P.TEMPLATE.read_text(encoding="utf-8"))
check("nothing in the inlined JSON can close the script tag",
      "</script>" not in json.dumps(lib, ensure_ascii=False).replace("<", "\\u003c"))


# =====================================================================
section("frac renders the way a cutting mat is marked")

for x, want in [(F(1, 2), '½"'), (F(3, 8), '⅜"'), (F(9, 8), '1⅛"'),
                (F(3, 16), '3/16"'), (F(4), '4"'), (F(173, 4), '43¼"'),
                (F(91, 8), '11⅜"')]:
    check(f"frac({x}) is {want}", B.frac(x) == want, B.frac(x))

# A whole number concatenated onto a textual sixteenth reads as a different,
# entirely plausible measurement -- and it shipped, in every published cut
# list, understating the BeltPouch's zip strips by ⅜". The geometry was right
# the whole time, so nothing else could have caught it.
for x, want in [(F(21, 16), '1 5/16"'), (F(5, 16), '5/16"'),
                (F(17, 16), '1 1/16"'), (F(31, 16), '1 15/16"'),
                (F(23, 16), '1 7/16"')]:
    check(f"frac({x}) is {want}", B.frac(x) == want, B.frac(x))
check("no rendered fraction is ambiguous with a smaller one",
      all(" " in B.frac(F(n, 16)) for n in range(17, 32) if n % 2),
      "1 5/16 must not render as 15/16")
check("round_to snaps to a mark you can find", B.round_to(F(23, 32), 8) == F(3, 4))


print(f"\n{'=' * 60}")
print(f"{PASSED} passed, {len(FAILURES)} failed")
for f in FAILURES:
    print(f"  FAILED: {f}")
sys.exit(1 if FAILURES else 0)
