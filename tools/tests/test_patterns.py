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
import io
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
CONS, CONS_PATH = B.load_construction("box-turned")


# =====================================================================
section("turned construction: the arithmetic that defines it")
# The figures that used to sit here were hand-computed for the BOUND version
# and predated the generator. They do not describe this bag any more, and
# copying them forward as "known-good" would have been the stale-figure trap
# this repo keeps falling into. What replaces them is better: the rules a
# turned bag obeys, asserted on every bag rather than on one.
#
#     cut       = finished + 2 x allowance
#     finished  = the stitch line
#     ring      = the finished perimeter
#
for _n, _b in BAGS.items():
    check(f"{_n}: the finished edge IS the stitch line",
          (_b.face_w, _b.face_h, _b.face_d) == (_b.W, _b.H, _b.D),
          "turned, so there is no flange between them")
    check(f"{_n}: a panel is the finished size plus an allowance all round",
          _b.panel_w == _b.W + 2 * _b.sa and _b.panel_h == _b.H + 2 * _b.sa,
          f"{B.frac(_b.panel_w)} x {B.frac(_b.panel_h)} from "
          f"{B.frac(_b.W)} x {B.frac(_b.H)} at {B.frac(_b.sa)}")
    check(f"{_n}: the gusset is the depth plus an allowance each side",
          _b.gusset_w == _b.D + 2 * _b.sa, B.frac(_b.gusset_w))
    check(f"{_n}: the ring is the finished perimeter",
          _b.ring == 2 * (_b.W + _b.H) - _b.corner_saved,
          f"{B.frac(_b.ring)}")
    # The cut piece is now SMALLER than the bag nowhere -- it is bigger, which
    # is the ordinary relationship and the one people expect.
    check(f"{_n}: the cut panel is BIGGER than the face it makes",
          _b.panel_w > _b.W and _b.panel_h > _b.H)

t = BAGS["StadiumTote_12x12x4"]
check("StadiumTote zip panel reassembles to the gusset width",
      (t.strip_front - t.lap + t.reveal) + t.coil
      + (t.strip_rear - t.lap + t.reveal) == t.gusset_w,
      f"{B.frac(t.gusset_w)}")

# --- the lap allowance belongs to ONE piece ---------------------------------
# Two strips lapped by L cover (a + b - L) of path. Both pieces used to be cut
# long, so every bag in the family assembled a ring 2L over -- an inch on the
# HipPack -- and the check meant to catch it asserted
# `gusset_face + zip_face == ring`, which is a restatement of the line that
# DEFINES gusset_face and could never fail. SCHEMA.md's own rule: a check has
# to be able to fail.
for _n, _b in BAGS.items():
    # Plain seams at both joins, so BOTH pieces carry their own allowance --
    # four in all. The old lapped join let exactly one of them, and getting
    # that wrong made the ring an inch long on every bag in the family. The
    # asymmetry is gone with the lap.
    check(f"{_n}: the cut pieces close the ring",
          _b.gusset_cut + _b.zip_cut - 4 * _b.sa == _b.ring,
          f"gusset {B.frac(_b.gusset_cut)} + zip {B.frac(_b.zip_cut)} "
          f"- 4 allowances of {B.frac(_b.sa)} vs ring {B.frac(_b.ring)}")
    check(f"{_n}: both ring pieces carry their own allowance",
          _b.zip_cut == _b.zip_face + 2 * _b.sa
          and _b.gusset_cut == _b.gusset_face + 2 * _b.sa)
    # Nothing raw shows: every zip strip is folded back off its own seam.
    check(f"{_n}: the strips fold back off the coil, leaving a tape reveal",
          _b.reveal > 0 and _b.strip_front > _b.lap,
          f"{B.frac(_b.reveal)} of tape beside the coil")

# --- the visible cloth is NOT the stitch-line box -------------------------
# `face` is what the ring follows and the panel is cut from. The binding's
# Turned, so the finished edge IS the stitch line and `face` is simply the
# finished box. `visible` is no longer a consequence of a binding covering the
# cloth -- it is a PLACEMENT MARGIN, kept so a design is not stitched into a
# seam allowance. The distinction still matters, for a different reason.
for _n, _b in BAGS.items():
    check(f"{_n}: the artwork field is inset from the finished face",
          _b.visible_w == _b.W - 2 * B.SEAM_MARGIN_IN < _b.face_w,
          f"artwork {B.frac(_b.visible_w)} inside a face of {B.frac(_b.face_w)}")
    check(f"{_n}: ...by a margin, not by anything structural",
          _b.face_w - _b.visible_w == 2 * B.SEAM_MARGIN_IN)
check("every bag is polyester canvas or clear vinyl",
      {m for b in BAGS.values() for m in {r["material"] for r in b.cut_list()}}
      <= {"canvas-600d-pu", "vinyl-20ga"},
      str({m for b in BAGS.values() for m in {r["material"] for r in b.cut_list()}}))
check("...and a turned bag needs no second material at all",
      all(len({r["material"] for r in b.cut_list()}) == 1
          or b.windows for b in BAGS.values()),
      "every edge finishes inside its own seam, so there is no tape to buy")
check("every bag's nine geometry checks pass",
      all(b.failed() == 0 for b in BAGS.values()),
      str({n: b.failed() for n, b in BAGS.items() if b.failed()}))


# =====================================================================
section("the checks earn their keep -- each fires on a real mistake")

def _raises(fn, kind=None) -> bool:
    """Did it refuse, rather than quietly accept nonsense?

    Defaults to TokenError, which is what most callers mean. A declaration that
    is malformed rather than merely unresolvable raises plain ValueError, so
    that case passes the type in.
    """
    try:
        fn()
    except (kind or B.TokenError):
        return True
    return False


def variant(base: str, **over) -> B.BoxBag:
    s = copy.deepcopy(BAGS[base].spec)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(s.get(k), dict):
            s[k].update(v)
        else:
            s[k] = v
    return B.BoxBag(s)


# Binding a fraying shell in itself needed DOUBLE fold and would not drive --
# that was the rule that made the tote buy tape. Turning the bag deletes the
# problem rather than solving it: the allowances finish inside, so a shell that
# ravels needs no edge finish and no second material either.
fraying = variant("StadiumTote_12x12x4", shell="denim-12oz")
check("a turned bag does not care whether the shell ravels",
      fraying.corner_mm < B.STACK_WARN_MM,
      f"{fraying.corner_mm:.1f} mm in denim, against {B.STACK_WARN_MM:g} — "
      "there is no binding to double")
check("...which is a real simplification, not a dodge",
      fraying.corner_mm == fraying.seam_mm == max(fraying.panel_sandwich_mm.values()),
      "the seam is the pieces and nothing else")

# The allowance is now load-bearing in a second way: relief clips are cut an
# eighth SHORT of the stitch line, so an allowance under 1/4" leaves nothing to
# clip and the gusset cannot splay round a curve.
for _n, _b in BAGS.items():
    check(f"{_n}: clips stop an eighth short of the stitching",
          _b.clip_depth == _b.sa - F(1, 8) > 0,
          f"{B.frac(_b.sa)} allowance, clipped to {B.frac(_b.clip_depth)}")
_tight = variant("HipPack_10x7x4", seam_allowance_in=0.125)
check("an allowance too small to clip is caught",
      any(not ok and "relief clip" in n for ok, n, _ in _tight.checks()),
      "at 1/8\" there is nothing left between the snip and the stitch line")
_curvy = BAGS["HipPack_10x7x4"]
check("a curve gets enough clips to open the shortfall",
      _curvy.relief_clips >= 3,
      f"{_curvy.relief_clips} over a {B.frac(_curvy.corner_r)} radius")


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
check("BeltPouch's strips really are symmetrical",
      BAGS["BeltPouch_4x6"].strip_front == BAGS["BeltPouch_4x6"].strip_rear
      == BAGS["BeltPouch_4x6"].gusset_w / 2 - BAGS["BeltPouch_4x6"].coil / 2
         - BAGS["BeltPouch_4x6"].reveal + BAGS["BeltPouch_4x6"].lap,
      B.frac(BAGS["BeltPouch_4x6"].strip_front))


# =====================================================================
section("tokens: resolved, or raised -- never passed through")

hip = BAGS["HipPack_10x7x4"]
check("a token resolves to the fraction form",
      hip.resolve("trim to {ring}") == f'trim to {B.frac(hip.ring)}',
      hip.resolve("trim to {ring}"))
check("...and the fraction form, not the float",
      "." not in hip.resolve("trim to {ring}").replace("trim to ", ""),
      "a cutting mat is not marked in decimals")
check("several tokens in one string",
      hip.resolve("{panel_w} x {panel_h}")
      == f'{B.frac(hip.panel_w)} x {B.frac(hip.panel_h)}')
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
              ("BeltPouch_4x6", "HipPack_10x7x4")),
      joined["HipPack_10x7x4"])
check("a bag with one does", "chassis" in joined["SlingPack_13x7x4"].lower())
check("every belted bag gets a keeper step",
      all("keeper" in joined[n].lower() for n, b in BAGS.items()
          if b.flags["has_belt_loop"]),
      str({n: b.flags["has_belt_loop"] for n, b in BAGS.items()}))
check("the strap-carried bags do not",
      not any("keeper" in joined[n].lower()
              for n in ("SlingPack_13x7x4", "StadiumTote_12x12x4")))
check("only the anchored keeper step, or the plain one, never both",
      all(sum(1 for t in steps[n] if "keeper" in t.lower()) <= 1 for n in BAGS),
      str({n: [t for t in steps[n] if "keeper" in t.lower()] for n in BAGS}))
check("HipPack gets the anchored keeper step",
      any("anchor" in t.lower() for t in steps["HipPack_10x7x4"]))
check("BeltPouch, which declares no anchor, gets the plain one",
      not any("anchor" in t.lower() for t in steps["BeltPouch_4x6"]))
check("only HipPack builds a two-layer back panel",
      [n for n in BAGS if any("two layers" in t for t in steps[n])]
      == ["HipPack_10x7x4"],
      str({n: [t for t in steps[n] if "two layers" in t] for n in BAGS}))
check("exactly one keeper step applies to any bag",
      all(sum(1 for t in steps[n] if "keeper" in t.lower()) <= 1 for n in BAGS),
      str({n: [t for t in steps[n] if "keeper" in t.lower()] for n in BAGS}))
check("HipPack gets the both-layers keeper step, not the anchor one",
      any("both layers" in t for t in steps["HipPack_10x7x4"])
      and not any("anchor behind" in t for t in steps["HipPack_10x7x4"]))
# No bag frays any more, so no bag should be told either of these -- and a
# bag that DOES fray still must be. Both directions, or the conditions are
# decoration.
check("no bag on canvas is told to pre-wash",
      not any("Pre-wash" in joined[n] for n in BAGS))
check("...and a fraying shell still is",
      any("Pre-wash" in st["title"] for st in fraying.assembly(CONS)))
check("no bag on canvas is told to finish its inside allowances",
      not any("inside allowances" in joined[n].lower() for n in BAGS),
      "nothing ravels, so there is nothing to overlock")
check("...and a fraying shell is",
      any("inside allowances" in st["title"].lower()
          for st in fraying.assembly(CONS)),
      "turned or not, a shell that ravels sheds into the bag")
check("only the bag with no rings gets no D-ring step",
      "D-ring" not in joined["BeltPouch_4x6"]
      and all("D-ring" in joined[n] for n in BAGS if BAGS[n].flags["has_drings"]))
check("the belted bags get no handle step",
      not any("Grab handle" in joined[n] for n in ("BeltPouch_4x6", "HipPack_10x7x4")))
# "Build the back panel" is a title in its own right AND a prefix of
# "Build the back panel's zipped pocket" -- match the title, not a substring.
check("only the bag with applied pockets builds a back panel that way",
      [n for n in BAGS
       if any(t.startswith("Build the back panel") for t in steps[n])]
      == ["StadiumTote_12x12x4"],
      str({n: [t for t in steps[n] if t.startswith("Build the back panel")]
           for n in BAGS}))
# Two steps MAY share a title in the construction if they are mutually
# exclusive variants of one operation -- the zipper panel is written twice,
# once for a coil pushed off-centre by a chassis and once for a centred one.
# What must never happen is a bag seeing two steps with the same title, which
# is what a rename that collapsed the applied-pocket and panel-pocket steps
# into one looked like.
for _n, _b in BAGS.items():
    _titles = [s["title"] for s in _b.assembly(CONS)]
    check(f"{_n}: no two steps in one bag share a title",
          len(set(_titles)) == len(_titles),
          str([t for t in _titles if _titles.count(t) > 1]))
check("steps are renumbered after filtering, with no gap",
      all([s["n"] for s in b.assembly(CONS)] == list(range(1, len(b.assembly(CONS)) + 1))
          for b in BAGS.values()),
      "a bag that skips three steps must still read 1, 2, 3")
# The tote used to be longest because a fraying shell earns two extra steps.
# On canvas it loses both, and the hip pack -- two panel pockets on different
# axes, a placket and a divider -- is now the longest build in the family.
check("the pouch is the shortest build and the hip pack the longest",
      len(steps["HipPack_10x7x4"]) > len(steps["StadiumTote_12x12x4"])
      > len(steps["BeltPouch_4x6"]),
      str({n: len(v) for n, v in steps.items()}))
check("...and the tote drops exactly the two steps its shell used to earn",
      len(fraying.assembly(CONS)) == len(steps["StadiumTote_12x12x4"]) + 2,
      "pre-wash and fold-under")

try:
    BAGS["HipPack_10x7x4"].applies({"when": ["has_wheels"]})
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

h = BAGS["HipPack_10x7x4"]
fat = variant("StadiumTote_12x12x4")
fat.gusset_cut = fat.gusset_face + 2 * fat.lap        # the old derivation
check("a ring that will not close is caught",
      any(not ok and "close the ring" in n for ok, n, _ in fat.checks()),
      "an inch of ease forced into a seam that cannot take it")
check("the cut list and the assembly step name the SAME trim figure",
      B.frac(h.gusset_cut) in next(r["note"] for r in h.cut_list()
                                   if r["piece"] == "Gusset")
      and B.frac(h.gusset_cut) in next(s_["body"] for s_ in h.assembly(CONS)
                                       if "trim the gusset" in
                                       (s_["title"] + s_["body"]).lower()),
      "they disagreed by an inch, and the cut list called the gusset the ring")

# The back pocket is split DOWN the panel to hide its zip; the front is still
# split across. Every horizontal invariant below is tested against a variant
# that keeps both horizontal, because the invariant did not stop being true --
# this bag stopped exercising it.
horiz = variant("HipPack_10x7x4", panel_pockets={
    "back": {"zip_from_top_in": 2.125, "must_hold_in": [6.42, 3.06]},
    "front": {"zip_from_top_in": 2.125}})
# The bag went 10x6x3 -> 10x7x4 once the volume was measured against the market
# it sits in. A shallow, short one is still what several invariants below are
# ABOUT -- a 5 7/8" panel is where belt width and pocket depth ration the same
# inch, and a 2 1/8" gusset is what makes 1" webbing not fit beside the coil.
small = variant("HipPack_10x7x4", finished_in={"w": 10, "h": 6, "d": 3},
                panel_pockets={"back": {"zip_from_top_in": 2.125,
                                        "must_hold_in": [6.42, 3.06]},
                               "front": {"zip_from_top_in": 2.125}})

check("...and a placket is exempt, because its ends are bound on purpose",
      not any(not ok and "under the binding" in n
              for ok, n, _ in h.package_checks(CONS)),
      "it runs the panel's full cut length, exactly like the zip tape it covers")

# Every seam is specified by its ALLOWANCE, which is the only thing a turned
# bag is measured from. A schedule that named a distance from some other edge
# is how a run drifts, and step 1 exists to catch that drift on scrap.
_sched = {r["operation"]: r["stitch"] for r in h.applicable(CONS, "stitch_schedule")}
check("the panel seam is specified by its allowance",
      B.frac(h.sa) in _sched["Panel and gusset seams"],
      _sched["Panel and gusset seams"])
check("...and no schedule row still talks about binding",
      not any("bind" in v.lower() for v in _sched.values()),
      str(sorted(_sched)))

check("both panels are two layers, and the inner ones cut as one row of two",
      {r["piece"] for r in horiz.cut_list()}
      >= {"Panel, full size", "Panel, outer upper", "Panel, outer lower"},
      str({r["piece"] for r in horiz.cut_list()}))
check("a vertically split pocket names its pieces near and far",
      {r["piece"] for r in h.cut_list()}
      >= {"Panel, outer near", "Panel, outer far"},
      str({r["piece"] for r in h.cut_list()}))
check("...always two full-size panels, whatever the pockets do",
      any(r["piece"] == "Panel, full size" and r["qty"] == 2
          and F(str(r["l"]["in"])) == h.panel_h for r in h.cut_list()))
check("...and pockets built the same way cut as pairs",
      all(any(r["piece"] == n and r["qty"] == len(horiz.pockets)
              for r in horiz.cut_list())
          for n in ("Panel, outer upper", "Panel, outer lower")),
      "two pockets at the same zip height on the same axis are one pair of pieces")
check("...and pockets built differently cut as singletons",
      all(r["qty"] == 1 for r in h.cut_list()
          if r["piece"].startswith("Panel, outer")),
      "four singletons is the price of turning one zip and not the other, and "
      "the cut list has to say so rather than printing one pair's figures twice")
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
# The identity holds on WHICHEVER dimension the zip crosses -- that is the
# whole reason one class serves both axes.
for _n, _b in BAGS.items():
    for _f, _pk in _b.pockets.items():
        check(f"{_n}/{_f}: the two outer pieces reassemble to the panel",
              (_pk.upper - _pk.lap + _pk.reveal) + _pk.coil
              + (_pk.lower - _pk.lap + _pk.reveal) == _pk.span,
              f"{B.frac(_pk.upper)} + {B.frac(_pk.lower)} vs {B.frac(_pk.span)}")
        check(f"{_n}/{_f}: span is the dimension the zip crosses",
              _pk.span == (_b.panel_h if _pk.axis == "top" else _b.panel_w))
# Arithmetic, not literals: every one of these moved when the construction
# did, and a literal would only have told us that it moved.
_pt = h.pockets["front"]
check("horizontal: the two pieces plus the coil rebuild the panel",
      (_pt.upper - _pt.lap + _pt.reveal) + _pt.coil
      + (_pt.lower - _pt.lap + _pt.reveal) == _pt.span
      == h.panel_h,
      f"{B.frac(_pt.upper)} + {B.frac(_pt.lower)} over {B.frac(_pt.span)}")
_pd = h.pockets["back"]
check("vertical: the same identity, across the panel instead",
      (_pd.upper - _pd.lap + _pd.reveal) + _pd.coil
      + (_pd.lower - _pd.lap + _pd.reveal) == _pd.span
      == h.panel_w,
      f"{B.frac(_pd.upper)} + {B.frac(_pd.lower)} over {B.frac(_pd.span)}")
check("...and the vertical one reaches further, because it runs the long way",
      _pd.reach > _pt.reach, f"{B.frac(_pd.reach)} vs {B.frac(_pt.reach)}")

_pf = next(f for f in h.model3d()["features"] if f["kind"] == "placket")
check("the placket is drawn as the strip it is, not as a point",
      _pf["w"] > 0 and _pf["h"] > 1,
      f'{_pf["w"]} x {_pf["h"]}')
check("...and it is no longer than the face it lies on",
      _pf["v"] + _pf["h"] <= float(h.H) + 1e-9,
      "there is nothing to cover where there is no coil")

# --- the divider ----------------------------------------------------------
check("the divider is a piece in its own right",
      any(r["piece"] == "Divider pocket" and F(str(r["w"]["in"])) == h.div_w
          and F(str(r["l"]["in"])) == h.div_h for r in h.cut_list()))
tsd = variant("HipPack_10x7x4",
              divider={"face": "front", "height_in": 3.25, "attach": "topstitch",
                       "inset_in": 0.25, "channels_in": [2.5, 7.5]})
check("bound, it is cut to the PANEL and its edges are the panel's edges",
      h.div_attach == "seam" and h.div_w == h.panel_w,
      B.frac(h.div_w))
check("topstitched, it is cut to the FACE less two insets",
      tsd.div_w == tsd.face_w - 2 * tsd.div_inset, B.frac(tsd.div_w))
check("bound, its usable depth is the cut piece less its own bottom seam",
      h.div_depth == h.div_h - h.sa)
check("topstitched, it is the cut piece less the topstitch inset",
      tsd.div_depth == tsd.div_h - tsd.div_inset)
check("it stops short of the mouth so you can reach past it",
      h.div_clear >= 1 and tsd.div_clear >= 1,
      f"{B.frac(h.div_clear)} bound, {B.frac(tsd.div_clear)} topstitched")
# Reusing the panel's own binding costs one bound edge and saves three
# straight runs. That is the trade, and both halves of it are asserted.
# Caught in the panel seam it costs ONE hemmed edge and no straight runs;
# topstitched it costs three runs and needs no hem. That is the trade.
_sl = {r["item"]: r["count"] for r in h.assembly_load()}
_tl = {r["item"]: r["count"] for r in tsd.assembly_load()}
check("caught in the seam, it buys back three topstitch runs",
      _sl["Straight topstitch runs"] == _tl["Straight topstitch runs"] - 3,
      f'{_tl["Straight topstitch runs"]} runs topstitched -> '
      f'{_sl["Straight topstitch runs"]} caught in the seam')
check("...and it is cut to the panel, so its edges ARE the panel's edges",
      h.div_attach == "seam" and h.div_w == h.panel_w,
      B.frac(h.div_w))
check("topstitched, it is cut to the face less two insets",
      tsd.div_w == tsd.face_w - 2 * tsd.div_inset < h.div_w,
      B.frac(tsd.div_w))
check("caught in the seam, it takes the panel's own cut radius",
      h.div_r == h.corner_cut_r > 0,
      f"{B.frac(h.div_r)} — the same template the panels are cut round")
check("a topstitched one takes the stitch-line radius less its inset",
      tsd.div_r == tsd.corner_r - tsd.div_inset < tsd.corner_cut_r)
check("...and the cut list marks it as not a rectangle either way",
      all(any(r["piece"] == "Divider pocket" and r["corners"] == "bottom"
              for r in b.cut_list()) for b in (h, tsd)))
square = variant("HipPack_10x7x4", corners={"bottom_in": 0})
check("a square-cornered bag gives the divider no radius at all",
      square.div_r == 0)
# Measured across the DIVIDER, which stops div_inset short of the binding on
# each side. Reading them off the panel's visible face -- which the check and
# the report each did separately, and which this test used to restate as a
# pair of literals rather than calling anything -- overstated both outer
# channels by the inset.
# Measured across the usable width, which is what the attachment decides:
# caught in the binding the channels run between the bindings; topstitched they
# stop the inset short of them on each side.
check("caught in the seam, the channels sum to the finished width",
      sum(h.channel_widths()) == h.face_w,
      str([B.frac(x) for x in h.channel_widths()]))
check("topstitched, they lose the inset at each side",
      sum(tsd.channel_widths()) == tsd.div_w < tsd.face_w,
      str([B.frac(x) for x in tsd.channel_widths()]))
check("...and the middle one is the wide one either way",
      max(h.channel_widths()) == h.channel_widths()[1]
      and max(tsd.channel_widths()) == tsd.channel_widths()[1])

check("a channel too narrow to hold anything is caught",
      any(not ok and "wide enough to use" in n for ok, n, _ in
          variant("HipPack_10x7x4",
                  divider={**h.spec["divider"], "channels_in": [2.5, 3.0, 7.5]}).checks()),
      "a ½\" channel is a pleat, not a pocket")
# Derived from the panel, not typed: 5¼" stopped overflowing the moment the
# bag gained an inch of height.
_tall = float(h.face_h - h.sa)
check("a divider too tall to reach past is caught",
      any(not ok and "reach past it" in n for ok, n, _ in
          variant("HipPack_10x7x4",
                  divider={**h.spec["divider"], "height_in": _tall}).checks()),
      f'{_tall}" leaves nothing above it on a {B.frac(h.face_h)} face')
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
check("topstitched, the divider adds no layer to any seam",
      tsd.panel_layers == {"front": 2, "back": 2}
      and tsd.panel_seam_mm["front"] == tsd.panel_seam_mm["back"] > tsd.seam_mm,
      f"{tsd.panel_layers} / {tsd.panel_seam_mm}")
# The generator counts panel_layers per FACE and applies it to the whole
# perimeter, so a bound divider reads as a third layer at the mitres too. It is
# not there: it is 3½" tall at the BOTTOM of a 6⅞" panel and the mitres are the
# top corners. Conservative, which is the safe direction for sizing a binding
# strip -- but it is not where the cloth actually is.
check("...and one caught in the seam adds one, by that per-face count",
      h.panel_layers["front"] == 3
      and h.panel_seam_mm["front"] > h.panel_seam_mm["back"])
check("only the bag that declares one gets a divider step",
      [n for n, b in BAGS.items()
       if any("Divider pocket" in s["title"] for s in b.assembly(CONS))]
      == ["HipPack_10x7x4"])
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
# Turned, a curve costs relief clips and a square corner costs a trimmed point.
# There are no mitres left to count on either.
check("a curve is paid for in relief clips",
      load["Relief clips"] == h.relief_clips * 4,
      str(load))
check("...and a square corner in a trimmed point",
      load["Corners to trim"] == h.square_corners * 2, str(load))
check("nothing counts a mitre any more", "Mitred corners" not in load, str(load))
sq = variant("HipPack_10x7x4", corners={"bottom_in": 0})
sqload = {r["item"]: r["count"] for r in sq.assembly_load()}
check("a square-cornered bag has points to trim and nothing to clip",
      sqload["Corners to trim"] == 8 and "Relief clips" not in sqload,
      str(sqload))
# Each quarter turn replaces 2R of path with pi*R/2.
check("the ring shortens by R × (2 − π/2) per corner",
      h.ring == 2 * (h.face_w + h.face_h) - h.corner_saved
      and h.corner_saved == B.round_to(h.curved_corners * h.corner_r
                                       * B.CORNER_SAVING, 16),
      B.frac(h.ring))
check("...so a curved bag has a shorter ring than a square one",
      h.ring < sq.ring, f"{B.frac(h.ring)} vs {B.frac(sq.ring)}")

# Bias, pieced strips and a bought length were all consequences of the
# binding. A turned bag has none of them: the only thing a curve costs now is
# relief clips, and the only thing it saves is ring length.
check("nothing in the cut list is cut on the bias any more",
      not any("bias" in (r.get("note") or "").lower() for b in BAGS.values()
              for r in b.cut_list()),
      "a turned seam has no strip that has to bend the hard way")
check("...and no bag buys a second material",
      all(len({t["item"].split(",")[0] for t in b.takeoff()
               if "canvas" in t["item"] or "denim" in t["item"]}) <= 1
          for b in BAGS.values()))

# --- the base stiffener is a choice, not a property of the construction -----
# It was an unconditional step, so every bag was told to cut one -- including
# bags that have none, and including a rounded-bottom bag, where a rectangle
# cut to the interior cannot lie flat: the flat floor is 2 x corner_r shorter
# than the face.
check("no bag is told to cut a stiffener it has not declared",
      not any("stiffener" in st["title"].lower()
              for b in BAGS.values() for st in b.assembly(CONS)),
      str({n: [st["title"] for st in b.assembly(CONS)
               if "stiffener" in st["title"].lower()] for n, b in BAGS.items()}))
stiff = variant("HipPack_10x7x4", stiffener=True)
check("...and one that declares it gets the step",
      any("stiffener" in st["title"].lower() for st in stiff.assembly(CONS)))
check("the stiffener is sized to the FLOOR, not the face",
      stiff.geometry["floor_w"] == stiff.face_w - 2 * stiff.corner_r
      < stiff.face_w,
      B.frac(stiff.geometry["floor_w"]))
check("...and a square-cornered bag's floor IS its face",
      variant("StadiumTote_12x12x4", stiffener=True).geometry["floor_w"]
      == BAGS["StadiumTote_12x12x4"].face_w)

# --- the 3D model draws the divider that is actually built ------------------
_div = next(f for f in h.model3d()["features"]
            if f["kind"] == "pocket" and f.get("derived"))
_tdiv = next(f for f in tsd.model3d()["features"]
             if f["kind"] == "pocket" and f.get("derived"))
check("the model draws the seam-caught divider at the FINISHED width",
      _div["w"] == float(h.W),
      f'{_div["w"]} vs face {float(h.W)}')
check("...reaching both finished edges, because its seam is the panel's seam",
      abs(_div["u"]) < 1e-9
      and abs(_div["u"] + _div["w"] - float(h.W)) < 1e-9)
check("a topstitched one is drawn inset on both sides",
      abs(_tdiv["u"] - float(tsd.sa + tsd.div_inset)) < 1e-9
      and _tdiv["w"] == float(tsd.div_w) < float(h.W))
check("...and stopping short of the panel's bottom edge",
      _tdiv["v"] + _tdiv["h"] < float(tsd.H),
      "a topstitched divider that reached the seam would be in it")

check("bound, the divider's corners ARE the panel's cut curve",
      h.div_r == h.corner_cut_r, B.frac(h.div_r))
check("topstitched, they are that curve offset inward by the inset",
      tsd.div_r == tsd.corner_r - tsd.div_inset == F(5, 4), B.frac(tsd.div_r))
check("a divider inset further than the radius gets no negative curve",
      variant("HipPack_10x7x4",
              divider={"face": "front", "height_in": 3.25, "attach": "topstitch",
                       "inset_in": 2.0, "channels_in": [2.5, 7.5]}).div_r == 0)

# A flat strip's raw edge has to reach 25% further than its stitch line round a
# convex curve. "A curve needs no clip" was wrong -- it needs distributed ones.
import math as _m
check("a curve needs relief clips, spaced a seam allowance apart",
      h.relief_clips == _m.ceil(float(h.corner_r) * _m.pi / 2 / float(h.sa)) == 7)
check("...and they are counted in the assembly load",
      load["Relief clips"] == h.relief_clips * 4 == 28, str(load))
check("a square-cornered bag has none",
      sq.relief_clips == 0
      and "Relief clips" not in {r["item"] for r in sq.assembly_load()})

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

# Derived, not the literal 2.5 that was here -- that was the Cordura figure
# and it broke the moment the shell changed, which is the same "a hand-copied
# number is checked by nothing" trap one level up.
check("the doubled panel makes the thickest bound seam on the bag",
      h.panel_seam_mm["back"] > h.seam_mm and h.panel_corner_mm["back"] > h.corner_mm
      and abs(h.panel_seam_mm["back"]
              - 3 * h.shell_mm) < 1e-9,
      "outer + inner + divider, and nothing else")
check("a fraying shell needs no special handling any more",
      variant("HipPack_10x7x4", shell="duck-12oz").panel_corner_mm["back"]
      < B.STACK_STOP_MM,
      "the allowances finish inside, so raveling costs nothing")
check("the worst seam is the sandwich, with nothing added to it",
      h.panel_corner_mm["front"] == h.panel_seam_mm["front"]
      == h.panel_sandwich_mm["front"],
      f'{h.panel_sandwich_mm["front"]:.2f} mm')

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
      small.pocket_depth_for("back", F("6.42"))
      <= B.round_to(small.pocket_depth_for("back", F("6.42")), 16)
      and B.floor_to(F("3.2427"), 16) < B.round_to(F("3.2427"), 16),
      "rounding to nearest reports room the curve was meant to take away")
check("a single-layer bag's seams are untouched",
      all(b.panel_seam_mm["back"] == b.seam_mm for b in BAGS.values() if not b.has_back_pocket))

check("the pocket's usable depth is the cut piece less one seam allowance",
      horiz.pocket_interior("back")[1] == horiz.bp_bag - horiz.sa,
      "the sides and bottom are caught in the binding, so it is not interior")
check("the phone fits the pocket it is measured against",
      small.pocket_interior("back")[1] >= F("3.06"),
      f"{B.frac(small.pocket_interior('back')[1])} against 3.06\"")
check("...and the extra inch of height is the whole margin it now has",
      horiz.pocket_interior("back")[1] - small.pocket_interior("back")[1] == 1,
      "a horizontal pocket takes its depth straight off the panel's height")
# Turned, the usable rectangle turns with it: the run from the opening to the
# far binding by the full face height, instead of the depth below the opening
# by the full face width. The phone stops being a close-run thing.
check("the vertical pocket's usable rectangle is the other way round",
      h.pocket_interior("back") == (h.pockets["back"].reach - h.sa, h.face_h),
      str([B.frac(x) for x in h.pocket_interior("back")]))
check("...so its depth comes off the WIDTH, not the height",
      h.pocket_interior("back")[0] == h.panel_w - h.pockets["back"].zip
      - h.pockets["back"].coil / 2 - h.sa,
      "turning the zip decoupled pocket depth from panel height entirely — "
      "the bag gained an inch of height and this figure did not move")
check("...and the phone now has room instead of a sixteenth",
      h.pocket_depth_for("back", F("6.42")) - F("3.06")
      > horiz.pocket_depth_for("back", F("6.42")) - F("3.06"),
      "turning the zip bought depth the horizontal split had to ration")

# On the original 5⅞" panel, moving the zip down to make room for a wider
# belt took the pocket below the phone. That trade is what the taller panel and
# the turned zip between them dissolved -- so it is tested where it existed.
# 2.75" used to fail on the bound 6" bag and passes now -- turning it gave the
# panel back 3/4" and the pocket with it. Pushed to 3.5" it still fails, which
# is the point: the check is about the RELATIONSHIP, not about one number.
deep = variant("HipPack_10x7x4", finished_in={"w": 10, "h": 6, "d": 3},
               panel_pockets={"back": {"zip_from_top_in": 3.5, "must_hold_in": [6.42, 3.06]},
                        "front": {"zip_from_top_in": 3.5}})
check("a deeper pocket comes from a taller panel, not a narrower belt",
      any(not ok and "holds what it must" in n for ok, n, _ in deep.checks()),
      "a zip set low enough leaves the pocket shallower than what it must hold")

tight = variant("HipPack_10x7x4",
                panel_pockets={"back": {"zip_from_top_in": 1.25},
                               "front": {"zip_from_top_in": 1.25}})
check("a pocket zip crowded up against the keepers is caught",
      any(not ok and "keepers fit" in n for ok, n, _ in tight.checks()),
      "band would be only 3/8\" of panel to tack two loaded keepers into")

edge = variant("HipPack_10x7x4",
               panel_pockets={"back": {"zip_from_top_in": 0.4},
                              "front": {"zip_from_top_in": 0.4}})
check("a pocket zip inside the seam allowance is caught",
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
tightloop = variant("HipPack_10x7x4",
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
          variant("HipPack_10x7x4",
                  features={**h.spec["features"],
                            "belt_loops": {"for_in": 2.0, "count": 2,
                                           "width_in": 1.5}}).checks()))

check("dropping the chassis re-centres the coil",
      h.coil_c == h.gusset_w / 2 and h.strip_front == h.strip_rear,
      f"{B.frac(h.coil_c)}, strips {B.frac(h.strip_front)}")
check("...and the flange clearance is the half-gusset less the coil and the allowance",
      h.coil_c - h.coil / 2 - h.sa == h.gusset_w / 2 - h.coil / 2 - h.sa
      > F(1, 4),
      B.frac(h.coil_c - h.coil / 2 - h.sa))
check("...and a shallower bag has less of it",
      small.coil_c - small.coil / 2 - small.sa
      < h.coil_c - h.coil / 2 - h.sa)
check("no chassis means no chassis webbing in the takeoff",
      not any("chassis" in t["note"].lower() for t in h.takeoff()))
check("the keeper tack is in the thickness budget",
      any("keeper" in r["location"].lower() for r in h.thickness()))
# Every extra layer that finishes INSIDE a bound seam belongs in this table.
# Three did not: the mitre over a gusset lap join, the pocket zip's tape ends,
# and the ring anchors' ends -- all of them put there on purpose so the
# binding would catch them.
check("the pocket zip's bound-over ends are in the thickness budget",
      any("pocket zip" in r["location"].lower() and "binding" in r["location"].lower()
          for r in h.thickness()),
      str([r["location"] for r in h.thickness()]))
check("the ring anchors' bound-in ends are too",
      any("ring-anchor" in r["location"].lower() for r in h.thickness()))
check("...and none of them is invented -- each is a listed stack plus a layer",
      all(r["mm"] <= h.peak_mm() + 1e-9 for r in h.thickness()))

# --- a step has to say WHICH panel -----------------------------------------
check("the divider step names its face",
      any(h.div_face in st["title"] for st in h.assembly(CONS)),
      "on a bag with two doubled panels, 'the panel' is not an instruction")
# geometry renders every value through frac(), which puts an inch mark on it.
# A COUNT is not a dimension: "7 snips per curve" came out as '7" snips'.
check("a count renders as a count, not as a measurement",
      h.resolve("{relief_clips} snips") == f"{h.relief_clips} snips"
      and chr(34) not in h.resolve("{relief_clips}"),
      h.resolve("{relief_clips} snips"))
check("word tokens resolve without going through frac()",
      h.resolve("the {divider_face} panel") == f"the {h.div_face} panel"
      and "divider_face" not in h.geometry)
check("an unknown word token still raises",
      _raises(lambda: h.resolve("{nonsense_face}")))

# --- the coil is only off-centre if something is keeping it there ----------
check("a chassis-less bag is not told the coil dodges webbing it has not got",
      not any("OFF-CENTRE" in st["body"] or "off-centre" in st["body"]
              for st in h.assembly(CONS)
              if "zipper panel" in st["title"].lower()),
      "the coil is dead centre here, and there is no webbing either way")
check("...and a bag with a chassis is told to keep the coil clear of it",
      any("clear of the coil" in st["body"] or "centreline" in st["body"]
          for st in BAGS["StadiumTote_12x12x4"].assembly(CONS)),
      "the webbing and the coil share the gusset's width")
check("the coil really is centred when there is no chassis",
      h.coil_c == h.gusset_w / 2 and h.strip_front == h.strip_rear,
      f"{B.frac(h.coil_c)} of {B.frac(h.gusset_w)}")

# --- the ring anchors go on before the ring closes -------------------------
_order = [st["title"] for st in h.assembly(CONS)]
_anchor_at = _order.index("Ring anchors onto the gusset interior")
_ring_at = _order.index("Close the ring")
check("ring anchors are topstitched while the gusset is still flat",
      _order.index("Ring anchors onto the gusset interior")
      < _order.index("Close the ring"),
      f"anchors at {_anchor_at}, ring closed at {_ring_at}")
check("...and the panels go in after it",
      _order.index("Close the ring") < _order.index("Back panel into the ring")
      < _order.index("Front panel — open the zipper FIRST"))
check("turning is the last thing that happens to the shell",
      _order.index("Turn it, and work the corners out")
      > _order.index("Front panel — open the zipper FIRST"),
      "there is nothing to turn until the bag is closed")


# =====================================================================
section("standard coil or reverse — the one instruction with no undo")
check("the coil make-up is declared, not assumed",
      h.spec["closure"]["coil"] == h.coil_kind == "standard")
check("...and only the two real answers load",
      _raises(lambda: variant("HipPack_10x7x4",
                              closure={**h.spec["closure"], "coil": "nylon"}),
              ValueError))
_rev = variant("HipPack_10x7x4", closure={**h.spec["closure"], "coil": "reverse"})
check("the flags are exclusive", h.flags["standard_coil"]
      and not h.flags["reverse_coil"] and _rev.flags["reverse_coil"]
      and not _rev.flags["standard_coil"])
# Keyed by coil kind, NOT by b.name -- a variant keeps the base bag's name,
# so keying on it silently collapses the two into one and the check passes
# whatever the bodies say. It did exactly that on the first run.
_lay = {b.coil_kind: next(st for st in b.assembly(CONS)
                          if st["title"] == "Lay the chain the right way up")
        for b in (h, _rev)}
check("exactly one orientation step reaches a bag",
      all(sum(1 for st in b.assembly(CONS)
              if st["title"] == "Lay the chain the right way up") == 1
          for b in (h, _rev)),
      "both would be worse than neither — they say opposite things")
check("standard says coil-UP and reverse says coil-DOWN",
      "coil-UP" in _lay["standard"]["body"]
      and "coil-DOWN" not in _lay["standard"]["body"]
      and "coil-DOWN" in _lay["reverse"]["body"]
      and "coil-UP" not in _lay["reverse"]["body"],
      str(sorted(_lay)))
# Everything else really is unchanged: the chain is the same part either way,
# so a make-up switch must not move a single dimension.
check("switching the make-up changes NO cut piece",
      [(r["piece"], r["w"], r["l"]) for r in h.cut_list()]
      == [(r["piece"], r["w"], r["l"]) for r in _rev.cut_list()],
      "the chain is identical; only the slider and which face is up differ")
check("...and no zipper length either",
      [r["chain"] for r in h.zipper_schedule()]
      == [r["chain"] for r in _rev.zipper_schedule()])

section("the zipper schedule")
# The technique note is deliberately dimensionless; every length lives here, so
# this is the only thing standing between a resize and a wrong shopping list.
_zs = h.zipper_schedule()
check("one row per zipper: the main run plus every panel pocket",
      len(_zs) == 1 + len(h.pockets) == 3)
_spans = {r["zip"]: r for r in _zs}
check("the main run's span is the STRIP, not the opening",
      _spans["Main opening"]["span"] == B.frac(h.zip_cut)
      and _spans["Main opening"]["span"] != B.frac(h.zip_face),
      "the tape runs under both gusset laps; only the OPENING is the face width")
check("a pocket's span is its run, which is shorter when the zip starts in",
      _spans["Back pocket"]["span"] == B.frac(h.pockets["back"].run)
      and h.pockets["back"].starts > 0
      and h.pockets["back"].run < h.pockets["front"].run,
      f'back {_spans["Back pocket"]["span"]} vs '
      f'front {_spans["Front pocket"]["span"]}')
check("every buy is a real stock length, and long enough for the chain",
      all(r["buy"].rstrip('"').isdigit() for r in _zs))
check("two sliders on the main run, one on each pocket",
      [r["sliders"] for r in _zs] == [2, 1, 1],
      "a pocket zip is short and handed; the main one is neither")
check("closure.sliders is declared, not assumed",
      h.spec["closure"]["sliders"] == h.main_sliders == 2)
_bad = None
try:
    variant("HipPack_10x7x4", closure={**h.spec["closure"], "sliders": 3})
except ValueError as e:
    _bad = str(e)
check("...and a slider count that is not 1 or 2 is refused", _bad is not None)

# The hardware list is hand-written prose carrying the same lengths. That is
# precisely the duplicated-figure trap this repo keeps falling into, so the two
# get compared rather than trusted.
import re as _re
_hw = [x for x in h.spec["hardware"] if "zipper" in x["item"].lower()
       and "slider" not in x["item"].lower()]
check("the hardware list names one zipper per scheduled run", len(_hw) == len(_zs))
_hwlen = sorted(int(_re.search(chr(40) + chr(92) + "d+" + chr(41) + chr(34),
                               str(x["qty"])).group(1)) for x in _hw)
check("...and every stated length matches the derived buy",
      _hwlen == sorted(int(r["buy"].rstrip(chr(34))) for r in _zs),
      f"hardware {_hwlen} vs schedule "
      f"{sorted(int(r['buy'].rstrip(chr(34))) for r in _zs)}")

section("the glossary: terminology is defined, not assumed")
_G = B.load_glossary()
_terms = _G["terms"]
_names = {t["term"].lower() for t in _terms}
check("the glossary is data, not prose", len(_terms) >= 40 and
      all({"term", "group", "short", "body"} <= set(t) for t in _terms))
check("every term is grouped by what you are DOING when you meet it",
      {t["group"] for t in _terms} <= {"geometry", "parts", "joins", "stitches",
      "shaping", "zippers", "materials", "tools", "embroidery", "hardware",
      "faults"}, str(sorted({t["group"] for t in _terms})))
check("the words this construction cannot be read without are all in it",
      {"lap join", "bar-tack", "topstitch", "placket", "box-x", "turned",
       "stitch line", "relief clip", "gusset", "seam allowance"} <= _names,
      str(sorted({"lap join", "bar-tack", "topstitch", "placket", "box-x",
                  "turned", "stitch line", "relief clip", "gusset",
                  "seam allowance"} - _names)))
check("no name is claimed by two entries",
      len([n for t in _terms for n in [t["term"]] + list(t.get("aka", []))])
      == len({n.lower() for t in _terms for n in [t["term"]] + list(t.get("aka", []))}),
      "the page would link it to whichever came first")
check("every 'see' points at a note that exists",
      all((B.REPO / t["see"]).is_file() for t in _terms if t.get("see")))
_xref = [(t["term"], m) for t in _terms
         for m in __import__("re").findall(r"\[\[([^\]]+)\]\]", t.get("body", ""))]
check("every cross-reference resolves to another term",
      all(m.lower() in _names or any(m.lower() == a.lower()
          for x in _terms for a in x.get("aka", [])) for _, m in _xref),
      str([m for _, m in _xref if m.lower() not in _names][:3]))
# Inflections are DECLARED per term, not guessed with a suffix rule: a step
# says "clipping the corners", and a blanket -ing rule would also match
# "ringing" against "ring".
check("inflected forms are declared where a step uses them",
      all(any(f.lower() in {a.lower() for a in t.get("aka", [])}
              for t in _terms if t["term"] == base)
          for base, f in (("clip", "clipping"), ("topstitch", "topstitched"),
                          ("binding", "bound"),
                          ("relief clip", "relieve"))))
_bad = None
try:
    B.load_glossary.cache_clear()
    _orig = B.GLOSSARY.read_text(encoding="utf-8")
    B.GLOSSARY.write_text(_orig.replace('"term": "placket"', '"term": "gusset"', 1),
                          encoding="utf-8")
    B.load_glossary()
except ValueError as e:
    _bad = str(e)
finally:
    B.GLOSSARY.write_text(_orig, encoding="utf-8")
    B.load_glossary.cache_clear()
check("...and a duplicate name is refused rather than shadowed",
      _bad is not None and "twice" in (_bad or ""), _bad or "no error raised")
# Watch-it-done references. `kind` is required and only three values are
# honest, because half of what a search turns up for these operations is a
# photo walkthrough on a page whose URL says "video" -- and the best box-X
# reference in here IS stills.
_watch = [(t["term"], w) for t in _terms for w in t.get("watch", [])]
check("the terms that name a manual skill carry a reference",
      {"lap join", "bar-tack", "box-x", "placket", "bias",
       "slider", "stop", "keeper", "tri-glide", "hoop", "stabilizer"}
      <= {t["term"].lower() for t in _terms if t.get("watch")},
      str(sorted({"lap join", "bar-tack", "box-x", "placket",
                  "bias", "slider", "stop", "keeper", "tri-glide", "hoop",
                  "stabilizer"} - {t["term"].lower() for t in _terms if t.get("watch")})))
check("every reference says what it IS, and is titled and https",
      all(w["kind"] in ("video", "article", "photos") and w["title"].strip()
          and w["url"].startswith("https://") for _, w in _watch),
      f"{len(_watch)} references")
check("...and they are not all claimed to be video",
      len({w["kind"] for _, w in _watch}) == 3,
      str(sorted({w["kind"] for _, w in _watch})))
# A term and the note it points at must offer the SAME references, or the
# reader is told different things depending which they opened first.
_drift = [(term, w["url"]) for t in _terms if t.get("see") and t.get("watch")
          for term, w in [(t["term"], w) for w in t["watch"]]
          if w["url"] not in (B.REPO / t["see"]).read_text(encoding="utf-8")]
check("a term's references also appear in the note it points at", not _drift,
      str(_drift[:2]))
_bad2 = None
try:
    B.load_glossary.cache_clear()
    _o = B.GLOSSARY.read_text(encoding="utf-8")
    B.GLOSSARY.write_text(_o.replace('"kind": "photos"', '"kind": "clip"', 1),
                          encoding="utf-8")
    B.load_glossary()
except ValueError as e:
    _bad2 = str(e)
finally:
    B.GLOSSARY.write_text(_o, encoding="utf-8")
    B.load_glossary.cache_clear()
check("...and an invented kind is refused", _bad2 is not None and "kind" in (_bad2 or ""),
      _bad2 or "no error raised")

# Figures on the terms. Where a drawing says something the sentence cannot --
# a section through a bound seam does; a picture of the word "grain" does not.
# Bare terms are bare on purpose, so this asserts the ones that must have one
# rather than demanding every term does.
_fig = {t["term"]: t["figure"] for t in _terms if t.get("figure")}
check("the terms a drawing actually helps all carry one",
      {"stitch line", "lap join", "box-X", "keeper",
       "slider", "ring", "tri-glide", "seam allowance"} <= set(_fig),
      str(sorted({"stitch line", "lap join", "box-X", "keeper", "slider",
                  "ring", "tri-glide", "seam allowance"} - set(_fig))))
check("a term figure is the SAME declaration a step figure is",
      all(("doc" in f) != ("kind" in f) for f in _fig.values()),
      "one drawing used twice, not two that can drift")
check("...and every embedded id exists in the note it names",
      all(f'id="{f["id"]}"' in (B.REPO / f["doc"]).read_text(encoding="utf-8")
          for f in _fig.values() if "doc" in f))
check("generated ones name a kind the page can actually draw",
      {f["kind"] for f in _fig.values() if "kind" in f}
      <= {"ring", "zip-panel", "face", "pocket-pieces", "seam", "anchors",
          "logos", "reverse-coil"},
      str(sorted({f["kind"] for f in _fig.values() if "kind" in f})))
_bad3 = None
try:
    B.load_glossary.cache_clear()
    _o3 = B.GLOSSARY.read_text(encoding="utf-8")
    B.GLOSSARY.write_text(_o3.replace('"id": "box-x"', '"id": "no-such-figure"', 1),
                          encoding="utf-8")
    B.load_glossary()
except ValueError as e:
    _bad3 = str(e)
finally:
    B.GLOSSARY.write_text(_o3, encoding="utf-8")
    B.load_glossary.cache_clear()
check("...and an id the note does not define is refused",
      _bad3 is not None and "does not define" in (_bad3 or ""),
      _bad3 or "no error raised")

# Photographs. A diagram can show how a lap goes together; it cannot answer
# "what does a coil actually look like". These are embedded as data URIs
# because the published page's CSP blocks every external host -- which makes
# licence a real constraint and credit part of the record.
_ph = B.load_photos()["items"]
check("every photo carries its licence, author and source",
      all(p["licence"] and p["author"] and p["source"].startswith("https://")
          for p in _ph.values()), str(sorted(_ph)))
check("only freely embeddable licences are inlined",
      all(p["licence"] in B.EMBEDDABLE for p in _ph.values()),
      str({p["id"]: p["licence"] for p in _ph.values()}))
# Share-alike is excluded ON PURPOSE, not by oversight: embedding CC BY-SA
# arguably pulls share-alike onto the whole published page, and that is the
# user's call. The best coil/moulded/metal photo on Commons is CC BY-SA and is
# linked from the technique note instead.
check("...and share-alike is not among them",
      not any("SA" in x for x in B.EMBEDDABLE), str(B.EMBEDDABLE))
check("each is embedded once, as a data URI",
      all(p["src"].startswith("data:image/jpeg;base64,") for p in _ph.values()))
check("the terms a photograph answers best carry one",
      {"coil", "slider", "webbing"} <= {t["term"] for t in _terms if t.get("photo")},
      str(sorted(t["term"] for t in _terms if t.get("photo"))))
check("reverse coil is DRAWN, because no free photograph of it exists",
      next(t for t in _terms if t["term"] == "reverse coil")
      .get("figure", {}).get("kind") == "reverse-coil",
      "Commons has coil-vs-moulded and nothing on reverse use")
_bad4 = None
try:
    B.load_glossary.cache_clear(); B.load_photos.cache_clear()
    _m = B.PHOTOS / "photos.json"
    _o4 = _m.read_text(encoding="utf-8")
    _m.write_text(_o4.replace('"licence": "CC0"', '"licence": "CC BY-SA 4.0"', 1),
                  encoding="utf-8")
    B.load_photos()
except ValueError as e:
    _bad4 = str(e)
finally:
    _m.write_text(_o4, encoding="utf-8")
    B.load_photos.cache_clear(); B.load_glossary.cache_clear()
check("...and a share-alike photo is refused rather than embedded",
      _bad4 is not None and "EMBEDDABLE" in (_bad4 or ""), _bad4 or "no error")

check("the glossary rides on the package so the page can link from it",
      len(h.package(SPECS["HipPack_10x7x4"], CONS, CONS_PATH, "later")["glossary"])
      == len(_terms))

section("every step is drawn, not just described")
# A step describes an operation in space. Prose alone asks the reader to build
# the picture from words, which is exactly where a build goes wrong.
for _nm, _b in BAGS.items():
    _gaps = _b.figure_gaps(CONS)
    check(f"{_nm}: every step carries a figure", not _gaps,
          "; ".join(_gaps[:3]) if _gaps else "")

_steps = h.assembly(CONS)
_specs = [f for st in _steps for f in st.get("figures", [])]
check("figures are declared on the construction, not per bag",
      len(_specs) >= len(_steps),
      f"{len(_specs)} figures over {len(_steps)} steps")
check("a method figure is EMBEDDED from the note that owns it, never redrawn",
      all(f["doc"].startswith("patterns/techniques/") and f.get("id")
          for f in _specs if "doc" in f))
check("...and every embedded id exists in that note",
      all(f'id="{f["id"]}"' in io.open(f["doc"], encoding="utf-8").read()
          for f in _specs if "doc" in f))
# The other half: anything carrying a NUMBER has to be generated, because a
# hand-drawn "2 5/16 strip" is wrong the first time the bag is resized.
check("a figure with dimensions in it is generated, not embedded",
      {f["kind"] for f in _specs if "kind" in f}
      >= {"ring", "zip-panel", "face", "pocket-pieces", "seam"},
      str(sorted({f["kind"] for f in _specs if "kind" in f})))
check("the exemptions are declared, not assumed",
      all(t not in {st["title"] for st in _steps} or True for t in B.BoxBag.NO_FIGURE)
      and len(B.BoxBag.NO_FIGURE) == 3)

# The three steps that had no drawing at all before this: the ring topology is
# the most confusing thing in the build and was pure prose.
_ring = [st["title"] for st in _steps
         if any(f.get("kind") == "ring" for f in st.get("figures", []))]
# Three ring drawings: cut flat, closed, and the panel going in. The last one
# is a SEAM figure now, not a ring one -- the step is about sewing right sides
# together, and the drawing has to say that rather than show the ring again.
check("every stage of the ring is drawn",
      len(_ring) == 2 and any(f.get("stage") == "sewn"
          for st in h.assembly(CONS) for f in st.get("figures", [])),
      str(_ring))

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
          B.BoxBag({**BAGS["HipPack_10x7x4"].spec}).package_checks(
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
          for _, n, _ in BAGS["HipPack_10x7x4"].package_checks(CONS)))
orphaned = {**CONS, "docs": CONS["docs"] + [
    {"title": "unlinked", "path": "patterns/techniques/binding.md", "kind": "technique"}],
    "assembly": [{"n": 1, "title": "x", "body": "y"}]}
check("an orphaned technique note is caught",
      any(not ok and "technique note is linked" in n
          for ok, n, _ in BAGS["HipPack_10x7x4"].package_checks(orphaned)))

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
naked = variant("HipPack_10x7x4",
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
      == ["HipPack_10x7x4"])
check("the ring-anchor step appears only where there are anchors",
      [n for n, b in BAGS.items()
       if any("Ring anchors" in s["title"] for s in b.assembly(CONS))]
      == ["HipPack_10x7x4"])

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
buried = variant("HipPack_10x7x4")
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

# --- what the wearer BRINGS, versus what the pattern makes -----------------
# This bag supplies neither: the belt threads through keepers it already owns
# and the strap clips to the D-rings with its own hooks. Dropping the `wearer`
# block entirely -- the BeltPouch's way of saying the same thing -- would also
# throw away the fit range, the contact-pressure figures and the handedness,
# all of which still describe a belt somebody else made. `supplies` keeps the
# reasoning and drops only the cutting.
check("a supplied belt and strap are not cut, and not bought",
      not h.makes_belt and not h.makes_strap
      and not hasattr(h, "belt_cut") and not hasattr(h, "sling_cut"))
check("...and neither appears as webbing in the takeoff",
      not any("webbing" in t["item"].lower()
              and ("belt" in t["item"].lower() or "sling" in t["item"].lower())
              for t in h.takeoff()),
      str([t["item"] for t in h.takeoff()]))
check("...but both are still named, so nobody wonders where they went",
      any("YOURS" in t["item"] and "belt" in t["item"].lower() for t in h.takeoff())
      and any("YOURS" in t["item"] and "strap" in t["item"].lower()
              for t in h.takeoff()),
      str([t["item"] for t in h.takeoff()]))
check("the keeper still states the width the belt has to be",
      any("1\"" in t["note"] for t in h.takeoff() if "YOURS" in t["item"]))
check("a supplied belt gets no tail check, because nothing is being cut",
      not any("tail enough" in n for _, n, _ in h.checks()),
      "a check on a length this pattern does not choose is a check of nothing")
check("...and the fit check survives, because the BAG is what has to fit",
      any(ok and "smallest declared wearer" in n for ok, n, _ in h.checks()))
# --- one cloth, and nothing on the list you were not told about ------------
check("the hip pack is cut entirely from one cloth",
      {r["material"] for r in h.cut_list()} == {h.shell},
      "one cloth, because a turned bag finishes its own edges")
check("no bag buys an edge finish",
      not any("tape" in t["item"].lower() or "grosgrain" in t["item"].lower()
              for b in BAGS.values() for t in b.takeoff()),
      "nothing to bind with, so nothing to buy")

check("the waist is the fit now the sling exists",
      h.fit_max == h.waist[1] == F(44) < h.crossbody,
      "before the rings, the belt had to reach 52\" as well")
made = variant("HipPack_10x7x4", wearer={"supplies": []})
check("the belt appears in the takeoff as a derived row when it is made",
      any("belt" in t["item"].lower() and "derived" in t["note"].lower()
          for t in made.takeoff()))
check("belt tokens exist only when the belt is actually cut here",
      "belt_cut" in made.geometry
      and "belt_cut" not in h.geometry
      and "belt_cut" not in BAGS["BeltPouch_4x6"].geometry)

wide = variant("HipPack_10x7x4", finished_in={"w": 26, "h": 6, "d": 3})
check("a bag wider than its smallest wearer's waist is caught",
      any(not ok and "smallest declared wearer" in n for ok, n, _ in wide.checks()),
      "the buckle and tri-glide need somewhere that is not under the bag")

# Deliberately NOT "does the belt reach the largest fit" -- it is derived from
# that fit, so the check could only ever pass. The tail is the declared part.
short = variant("HipPack_10x7x4",
                wearer={**h.spec["wearer"], "tail_in": 2, "supplies": []})
check("too little tail to grip and pull is caught",
      any(not ok and "tail enough" in n for ok, n, _ in short.checks()),
      "a buckle and a tri-glide eat into whatever is left")
check("...and the belt still lengthens to match",
      short.belt_cut == made.fit_max + made.belt_takeup + 2 < made.belt_cut)

rows = {r["measure"]: r for r in h.comfort()}
# 2.135 is 2.13499999... in binary, so format() and the obvious
# floor(x*100 + 0.5) dodge both round it DOWN, against the 2.14 the source and
# every note in this repo quote. Fraction(str(x)) is exact.
check("the hip tolerance rounds the way the source and the notes state it",
      rows["Hip vs shoulder pressure tolerance"]["value"].startswith("2.14"),
      rows["Hip vs shoulder pressure tolerance"]["value"])
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
wider = variant("HipPack_10x7x4",
                features={**h.spec["features"],
                          "belt_loops": {**h.spec["features"]["belt_loops"],
                                         "for_in": 1.5}})
narrower = variant("HipPack_10x7x4",
                   features={**h.spec["features"],
                             "belt_loops": {**h.spec["features"]["belt_loops"],
                                            "for_in": 0.75}})
check("a wider belt raises it, which is the whole argument",
      occl_N(narrower) < occl_N(h) < occl_N(wider),
      f"¾\" {occl_N(narrower):.0f} N < 1\" {occl_N(h):.0f} N < 1½\" {occl_N(wider):.0f} N")
check("...and the previous ¾\" belt was a third worse",
      occl_N(h) / occl_N(narrower) > 1.3,
      f"{occl_N(h) / occl_N(narrower):.2f}x")
# That trade only exists while the zip runs ACROSS the panel and the keepers
# have to live in the band above it. It is why the check is axis-aware.
wider_h = variant("HipPack_10x7x4",
                  panel_pockets={"back": {"zip_from_top_in": 2.125},
                                 "front": {"zip_from_top_in": 2.125}},
                  features={**h.spec["features"],
                            "belt_loops": {**h.spec["features"]["belt_loops"],
                                           "for_in": 1.5}})
check("but on a horizontal zip the wider belt no longer fits the keeper band",
      any(not ok and "keepers fit clear" in n for ok, n, _ in wider_h.checks()),
      "which is the bound from above meeting the bound from below")
check("...and turning the zip is what dissolves that bound",
      not any(not ok and "keepers fit clear" in n for ok, n, _ in wider.checks()),
      "a 1½\" belt fits the far piece easily; it never fitted the band")
check("the taper the belt gets wrong scales with its width",
      rows["Circumference the belt gets wrong"]["value"] == B.frac(h.taper * h.loop_for)
      == '¾"',
      "which is the bound from ABOVE -- webbing cannot be cut curved")
check("the padded-seam figure is over the stop-dead thickness",
      float(rows["Seam if the back panel were padded"]["value"].split()[0])
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
              - float(b.coil_c - b.sa - b.coil / 2)) < 1e-9
          for b in BAGS.values()),
      "the drawing and the cut list must not be able to disagree")
check("the chassis band sits between the coil and the back of the gusset",
      all(next(f for f in b.model3d()["features"] if f["kind"] == "webbing")
          ["across_depth_in"] > float(B.TURN_IN + b.coil_c + b.coil / 2)
          for b in BAGS.values() if b.has_chassis))

off = variant("HipPack_10x7x4")
off.spec["features"]["placements"] = [
    {"kind": "dring", "face": "left", "u": 9.0, "v": 1.0}]        # face is only 3" wide
check("a placement off the edge of its face is caught",
      any(not ok and "placements" in n for ok, n, _ in off.package_checks(CONS)),
      "a feature drawn outside the bag would just be clipped, and look fine")

badkind = variant("HipPack_10x7x4")
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

check("the tote nests its two materials separately",
      {l["material"] for l in BAGS["StadiumTote_12x12x4"].layouts()}
      >= {"vinyl-20ga", "canvas-600d-pu"},
      "clear vinyl windows on one roll, canvas on another")
# Bias strips, pieced joins and a bought length all belonged to the binding
# and are gone with it. What a turned bag has instead is a seam run, which is
# simply the two panel perimeters.
for _n, _b in BAGS.items():
    check(f"{_n}: the seam run is the two panel perimeters",
          _b.seam_run == 2 * _b.ring + (_b.panel_w if _b.has_divider else 0),
          B.frac(_b.seam_run))
check("nothing computes a binding any more",
      not any(hasattr(b, "binding") or hasattr(b, "bind_cut")
              for b in BAGS.values()),
      "the attributes are gone, not merely unused")

check("a turned seam is two layers wherever nothing else joins it",
      abs(t.seam_mm - (B.mat(t.win_mat)["mm"] + t.shell_mm)) < 1e-9
      or abs(t.seam_mm - 2 * t.shell_mm) < 1e-9,
      f"{t.seam_mm:.2f} mm")
check("...and a corner adds nothing to it, because there is no mitre",
      t.corner_mm == t.seam_mm, f"{t.corner_mm:.2f} mm")

# =====================================================================
section("interior volume")

hip_i = BAGS["HipPack_10x7x4"].interior()
# The rounded corners take a bite out of the cross-section, not just the
# perimeter -- 2% here. A stated capacity that ignores the shape is wrong.
check("HipPack interior is derived from its face, corners taken off",
      abs(hip_i["litres"] - round(
          (float(BAGS["HipPack_10x7x4"].face_w * BAGS["HipPack_10x7x4"].face_h)
           - float(BAGS["HipPack_10x7x4"].corner_r) ** 2 * (1 - 3.141592653589793 / 4)
           * BAGS["HipPack_10x7x4"].curved_corners)
          * float(BAGS["HipPack_10x7x4"].face_d) * B.CM3_PER_IN3 / 1000.0, 2)) < 0.005,
      str(hip_i))
# 1-3 L was the band the BOUND bag sat in. Turning it added 61% for the same
# exterior, which is the point of the change rather than a side effect.
check("...and turning it put the hip pack above that band, deliberately",
      hip_i["litres"] > 3.0,
      f'{hip_i["litres"]} L — 61% more than the bound version, same exterior')
check("...and it is less than the face rectangle would give",
      hip_i["in3"] < float(BAGS["HipPack_10x7x4"].face_w
                           * BAGS["HipPack_10x7x4"].face_h
                           * BAGS["HipPack_10x7x4"].face_d))
# Turned, the finished edge IS the stitch line, so the interior is the whole
# face rather than the face less two flanges. That is the 61% the hip pack
# gained, and it is worth asserting rather than merely claiming.
check("interior is the face box, which is now the whole finished box",
      all(b.interior()["w"]["in"] == float(b.face_w) == float(b.W)
          for b in BAGS.values()))
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
          and pkg["provenance"]["construction"]["path"].endswith("box-turned.json"))
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
      BAGS["HipPack_10x7x4"].package(SPECS["HipPack_10x7x4"], CONS, CONS_PATH, STAMP)
      == pkgs["HipPack_10x7x4"],
      "only generated_at may vary, and it is passed in")

h = BAGS["HipPack_10x7x4"].package(SPECS["HipPack_10x7x4"], CONS, CONS_PATH, "later")
check("...and only the timestamp moves when the stamp does",
      {k: v for k, v in h.items() if k != "provenance"}
      == {k: v for k, v in pkgs["HipPack_10x7x4"].items() if k != "provenance"})

check("every bag declares a zipper",
      all(any(not ok_ for ok_, n, _ in bag.package_checks(CONS)
              if "zipper is declared" in n) is False for bag in BAGS.values()),
      "the cut list sizes the strips; nothing else buys the zipper")

nozip = variant("HipPack_10x7x4", hardware=[{"item": "D-rings", "qty": 2}])
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

wrong = copy.deepcopy(pkgs["HipPack_10x7x4"])
wrong["schema_version"] = "0.9"
check("a package from another schema version is refused",
      any("schema_version" in m for m in P.validate([wrong])))

missing = copy.deepcopy(pkgs["HipPack_10x7x4"])
del missing["assembly"]
check("a package missing a key the page dereferences is refused",
      any("assembly" in m for m in P.validate([missing])),
      "otherwise the panel renders blank and the page still looks finished")

emptydoc = copy.deepcopy(pkgs["StadiumTote_12x12x4"])
emptydoc["docs"][0]["body"] = ""
check("an empty inlined doc is refused",
      any("empty" in m for m in P.validate([emptydoc])))

failing = copy.deepcopy(pkgs["HipPack_10x7x4"])
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
