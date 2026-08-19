#!/usr/bin/env python
"""Derive a bound-seam box-bag pattern from declared finished dimensions.

Every bag in `patterns/` with `"construction": "box-bound"` is the same object at
a different size: two flat panels, a gusset ring wrapping their perimeter, a
zipper panel forming one face of that ring, and binding wrapping every raw edge.
Given the finished envelope, every cut size follows.

It exists because the numbers do not survive being computed by hand. Five
revisions of StadiumTote each moved a figure that only re-deriving the geometry
caught -- a gusset ring measured at the raw-edge perimeter instead of the
stitch-line perimeter, a zipper strip whose width changed twice as the binding
came and went, a vinyl requirement that had never actually been nested. A bad
stitch file wastes a rebuild; a bad cut wastes material.

    py tools/bag_pattern.py patterns/specs/HipPack_10x6x3.json
    py tools/bag_pattern.py --all
    py tools/bag_pattern.py --all --check       # exit non-zero on any failure
    py tools/bag_pattern.py --all --package     # write build/patterns/*.json
    py tools/bag_pattern.py <spec> --tokens     # list the tokens steps may use

THE GEOMETRY, once, so nothing below has to restate it:

  A bound seam still needs a seam allowance -- the binding *encases* the raw
  edges of one, it does not replace it. The allowance does not turn inward; both
  pieces' allowances lie together pointing OUTWARD, wrapped in binding, forming
  a flange that projects past the stitch line. So:

      face    = overall - 2 * flange        the visible panel between flanges
      cut     = face + 2 * SA               what you actually cut
      flange  = SA + turn                   turn is the binding's own thickness

  and the consequence that is easiest to get wrong:

      ring    = 2 * (face_w + face_h)       the gusset follows the STITCH-LINE
                                            perimeter, not the raw-edge one

  A ring cut to the raw-edge perimeter is 2 * 4 * SA too long -- 3 inches on a
  12 inch bag -- and that is 3 inches of pucker eased into a seam that cannot
  take it.

THE PACKAGE. `--package` writes `build/patterns/<Name>.json`, the fixed schema
described in `patterns/SCHEMA.md`. It merges three things: this bag's spec, its
construction file (assembly order, stitch schedule, tool list -- shared by every
bag of the same kind), and everything derived here. That is the only artefact
`tools/pattern_player.py` reads.

Assembly steps are parameterised two ways, both deliberately dumb:

  * `{token}` in a step resolves against the flat `geometry` map and is replaced
    with the FRACTION form -- the way a cutting mat is marked. An unrecognised
    token raises. A token that silently survived into a build instruction reads
    as literal text at the machine, and the person cutting has no way to know a
    number went missing. Same rule as `svgpath.parse_path` raising on an
    unknown command.

  * `when` / `unless` name flags from a closed set (`FLAGS`). There is no
    expression language and there should not be one: if a step needs a condition
    the flags cannot express, the flag set is what is missing.
"""

from __future__ import annotations

import argparse
import base64
import functools
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from fractions import Fraction as F
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPECS = REPO / "patterns" / "specs"
CONSTRUCTIONS = REPO / "patterns" / "constructions"
#: The vocabulary the patterns use as if you already knew it. Shared by every
#: bag, so it is hoisted into the library once rather than inlined four times.
GLOSSARY = REPO / "patterns" / "glossary.json"
#: Photographs of the physical parts. Embedded as data URIs because the
#: published page's CSP blocks every external host, which makes licence a real
#: constraint rather than a formality -- see load_photos().
PHOTOS = REPO / "patterns" / "photos"
PACKAGES = REPO / "build" / "patterns"

SCHEMA_VERSION = "1.0"

#: Binding wraps the flange and adds its own thickness to the projection. Small,
#: but it is the difference between a 12" bag measuring 12" and measuring 12 1/8.
TURN_IN = F(1, 16)
#: How much zipper tape shows beside the coil once a strip is folded back off
#: it. Not a style choice: the fold has to clear the coil or the foot rides on
#: it, and a quarter inch is the usual figure.
ZIP_REVEAL_IN = F(1, 4)
#: How far artwork and hardware stay clear of a seam. A placement margin only:
#: nothing structural depends on it, and it exists so a design is not stitched
#: into a seam allowance.
SEAM_MARGIN_IN = F(3, 8)

#: Materials. All four columns matter dimensionally, which is why they are one
#: table rather than several -- add a row rather than guessing.
#:
#: `mm`       sets the sandwich the binding has to wrap, so it sets strip width.
#: `frays`    decides single- or double-fold, which doubles the layers at every
#:            seam. A shell swap that looks like a taste decision moves both.
#: `roll_in`  is what the material comes on, and it is what the nesting layout
#:            has to fit inside.
#: `by_length` means it is bought by the yard as a narrow tape or webbing and is
#:            never nested on a roll.
#: `frays` and `melt_seal` are INDEPENDENT and conflating them has already cost
#: one bag's instructions. Fraying decides whether an edge needs turning under
#: and whether the binding must be double-fold. Melt-sealing decides how the
#: piece is CUT -- hot knife or rotary cutter -- and nothing else. Cordura is
#: both, which is why "Cordura seals, so no edge needs a hem" read as one fact
#: and was written into a step as one fact; a coated cotton canvas does not
#: ravel and cannot be hot-knifed, and the step was wrong for it in both
#: directions at once.
MATERIALS = {
    "cordura-1000d":      {"mm": 0.50, "frays": False, "melt_seal": True,  "roll_in": 60,
                           "needle": "jeans 100/16"},
    "vinyl-20ga":         {"mm": 0.51, "frays": False, "melt_seal": False, "roll_in": 54,
                           "needle": "Microtex 90/14"},
    "nylon-binding-tape": {"mm": 0.50, "frays": False, "melt_seal": True,  "by_length": True},
    "webbing-1in":        {"mm": 1.30, "frays": False, "melt_seal": True,  "by_length": True},
    "denim-10oz":         {"mm": 0.60, "frays": True,  "melt_seal": False, "roll_in": 58,
                           "needle": "jeans 100/16"},
    "denim-12oz":         {"mm": 0.75, "frays": True,  "melt_seal": False, "roll_in": 58,
                           "needle": "jeans 100/16"},
    "duck-12oz":          {"mm": 0.70, "frays": True,  "melt_seal": False, "roll_in": 58,
                           "needle": "jeans 100/16"},
    "waxed-canvas-10oz":  {"mm": 0.85, "frays": True,  "melt_seal": False, "roll_in": 58,
                           "needle": "jeans 100/16"},
    # 600D PU-coated polyester, the "waterproof canvas by the yard" sold for
    # outdoor upholstery. Synthetic and coated, so it neither ravels nor needs
    # a hot knife to be cut cleanly -- but it WILL seal if you have one, and
    # the one raw edge on this family (a topstitched divider's mouth) is the
    # only place that matters. 0.45 mm is nominal for 600D: measure yours,
    # because everything the binding does is sized from it.
    # A 90/14 sharp, NOT the jeans 100/16 the rest of this table wants.
    # 600D is half the yarn of a 1000D and the stacks here top out at 3.6 mm,
    # so a heavier needle buys nothing -- and on a coated cloth it costs
    # something real, because the hole it makes is the hole the waterproofing
    # keeps for good.
    "canvas-600d-pu":     {"mm": 0.45, "frays": False, "melt_seal": True,  "roll_in": 58,
                           "needle": "Microtex 90/14"},
}
DEFAULT_ROLL_IN = 60

MM_PER_IN = 25.4
CM3_PER_IN3 = 16.387064

#: Skin capillary blood occlusion, from the load-carriage literature: above
#: this, contact pressure starts shutting off circulation, and static peak
#: pressure is what predicts discomfort -- it accounts for 85-86% of the
#: variation. Reported, never used as a gate here, because the belt tension a
#: wearer actually applies is not something this repo has measured.
OCCLUSION_KPA = 16.0
#: The hip tolerates far more than the shoulder: p_hip = 2.135 * p_shoulder +
#: 18.75. Worth knowing before padding anything -- a hip pack is on the
#: forgiving half of the body.
HIP_TOLERANCE_RATIO = 2.135
#: Circumference gained per inch of drop from natural waist to hip. A flat
#: strap has the same length top and bottom; the body under it does not, so a
#: belt of height w is wrong by taper * w of circumference and wants to ride.
#: Body-dependent -- override in `wearer.taper_in_per_in`.
DEFAULT_TAPER = F(3, 4)
#: Past this a domestic machine needs hand-wheeling; past ~6 mm it stops.
STACK_WARN_MM = 5.0
STACK_STOP_MM = 6.0
#: Nylon webbing, any width -- thickness does not vary with it.
WEBBING_MM = 1.30
#: One side of a #5 nylon coil zipper's tape.
ZIP_TAPE_MM = 0.60
#: A belt keeper turns under at each end so no raw edge shows, and each end
#: needs a box-X footprint to tack into. Both are properties of the method, not
#: of the bag -- see patterns/techniques/webbing-hardware.md.
KEEPER_FOLD_IN = F(3, 8)
KEEPER_TACK_IN = F(5, 8)
#: A D-ring tab tacked to one layer of shell puts the whole bag into a stitch
#: field. It needs something behind it -- either the chassis, or a strip across
#: the gusset with BOTH ends caught in the panel bindings, which is the same
#: argument the chassis makes over a shorter span.
RING_ANCHOR_W_IN = F(3, 2)
#: A quarter circle of radius R replaces a square corner's 2R of path with
#: pi*R/2 of arc, so each rounded corner takes R * (2 - pi/2) out of the
#: perimeter. Rational to 1/10000 -- every figure downstream is rounded to a
#: sixteenth anyway, and an irrational in a Fraction chain poisons everything.
CORNER_SAVING = F(4292, 10000)
#: Bias strips cost about 30% more material than straight grain and have to be
#: pieced. That is the price of a curve, and binding.md says so plainly.
BIAS_WASTE = F(13, 10)
#: An adjustable strap loses length to two hook folds and the tri-glide. 4" is
#: what the StadiumTote's 56" webbing gives against its 52" maximum.
SLING_TAKEUP_IN = F(4)
#: And a belt loses length the same way, which an earlier version forgot. The
#: sling was derived as crossbody + take-up while the belt was derived as waist
#: + tail and nothing else, so at the largest declared fit the "6 inches of
#: tail" was really about two once the buckle's fixed half was folded and
#: box-X'd and the adjustable end was threaded back through its tri-glide.
#: Override in `wearer.belt_takeup_in`.
BELT_TAKEUP_IN = F(4)

#: The closed set of condition flags a construction step may name.
FLAGS = ("has_chassis", "shell_frays", "double_fold", "has_windows",
         "has_handle", "has_drings", "has_belt_loop", "has_belt_anchor",
         "has_ring_anchor", "has_sling", "has_back_pocket", "has_front_pocket",
         "has_panel_pocket", "has_divider", "has_seamed_divider",
         "has_stiffener", "has_pockets", "shell_melts", "self_bound",
         "has_webbing", "supplies_carry",
         "has_top_zip", "has_side_zip", "has_placket",
         "reverse_coil", "standard_coil")

#: Feature kinds the player's renderer knows how to draw. A kind outside this
#: set is a check failure rather than a silently missing detail.
FEATURE_KINDS = ("zip", "webbing", "dring", "handle", "logo", "rib",
                 "pocket", "patch", "belt-loop", "placket")
FACES = ("front", "back", "left", "right", "top", "bottom")

#: Nominal drawn size of the point-like features, so a placement can still be
#: checked against the face it sits on.
NOMINAL_IN = {"dring": (1.25, 0.60), "patch": (1.00, 1.00)}

TOOL_SCRIPTS = ("tools/bag_pattern.py", "tools/pattern_player.py",
                "tools/pattern_player.html")


#: Halves, quarters and eighths have a single-character glyph and can sit hard
#: against the whole number: 1⅛ reads as one-and-an-eighth and cannot read as
#: anything else. Sixteenths have no glyph, and that is where this bites.
VULGAR = {F(1, 2): "½", F(1, 4): "¼", F(3, 4): "¾",
          F(1, 8): "⅛", F(3, 8): "⅜", F(5, 8): "⅝", F(7, 8): "⅞"}


def frac(x, denom: int = 16) -> str:
    """Render to the nearest 1/denom the way a cutting mat is marked.

    The separator is not cosmetic. Concatenating a whole number onto a textual
    sixteenth produces a DIFFERENT measurement that still looks like a real
    one: 1 and 5/16 came out as `15/16"`, and the BeltPouch's two zipper strips
    were published ⅜" under their true width in every cut list this repo had
    ever generated. Nothing caught it, because the geometry was right the whole
    time -- only the rendering was wrong, so the ring still closed and the
    zipper panel still matched the gusset.

    The lesson generalises past this function. A regression run against a
    known-good FILE validates the geometry and not the presentation, because
    the file was printed by the same code being tested. Assert on Fractions.
    """
    # SNAP to the grid, do not approximate on it. `limit_denominator` returns
    # the best rational with denominator at most `denom`, which for 6.42 is
    # 6 and 5/12 -- a true statement about the number and a mark that does not
    # exist on any ruler. Every figure this pattern derives is dyadic, so this
    # is identity for all of them; it only bites on a measured value handed in
    # from outside, which is exactly where a plausible-looking wrong fraction
    # would do the most damage.
    x = F(round(F(x) * denom), denom)
    whole, rest = int(x), x - int(x)
    if rest == 0:
        return f'{whole}"'
    glyph = VULGAR.get(rest)
    if glyph is None:
        sixteenth = f"{rest.numerator}/{rest.denominator}"
        return f'{whole} {sixteenth}"' if whole else f'{sixteenth}"'
    return f'{whole}{glyph}"' if whole else f'{glyph}"'


def round_to(x, denom: int = 8) -> F:
    """Snap to a mark you can actually find on a ruler."""
    return F(round(F(x) * denom), denom)


def floor_to(x, denom: int = 8) -> F:
    """Round DOWN to a mark you can find on a ruler.

    The mirror of `ceil_to`, and the third of the set. A figure that has to
    REACH round something rounds up; a figure that has to FIT INSIDE something
    rounds down; a figure that is just a measurement rounds to nearest. Getting
    this one wrong reports more room than exists -- the curve-aware pocket depth
    came out at 3.2427" and rounding to nearest handed back 3.25", which is the
    rectangle answer the curve was supposed to correct.
    """
    x = F(x)
    n = x * denom
    return F(int(n) - (1 if n < 0 and n != int(n) else 0), denom)


def ceil_to(x, denom: int = 8) -> F:
    """Round UP to a mark you can find on a ruler.

    For anything that has to reach round something, rounding to nearest is
    wrong half the time and the failure is silent. A binding strip needing
    1.1412" rounds to 1⅛" and is 0.4 mm short of getting back over the sandwich
    -- which nobody discovers until they are halfway round a bag.
    """
    x = F(x)
    n = x * denom
    return F(int(n) + (1 if n != int(n) else 0), denom)


def dim(x) -> dict:
    """A dimension, twice: a float for the renderer, a fraction for the human.

    Nothing downstream does arithmetic on dimensions. If a consumer needs a
    figure in a new form the generator grows a key, which keeps every rounding
    decision in `frac`/`round_to` where a cutting mat is the only authority.
    """
    return {"in": float(x), "text": frac(x)}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def mat(name: str) -> dict:
    return MATERIALS.get(name, {"mm": 0.5, "frays": False, "roll_in": DEFAULT_ROLL_IN})


class TokenError(ValueError):
    """A construction step named a figure the geometry does not have."""


class PanelPocket:
    """A zipped pocket built INTO a panel, as a cavity between two layers.

    The panel becomes two: an inner one, full size and bound on all four edges,
    which is the compartment's wall; and an outer one cut in two and lapped onto
    a zipper tape. The pocket is the space between them and the zip is its only
    mouth. Nothing is cut open, no load crosses the zip, and the compartment
    behind stays sealed.

    Identical front and back, which is why the pieces come out in pairs.

    A pocket may be split either way. `zip_from_top_in` runs the zip ACROSS the
    panel and the outer becomes an upper and a lower; `zip_from_side_in` runs it
    DOWN the panel and the outer becomes a near and a far. The arithmetic is the
    same identity in both directions -- (near - lap) + coil + (far - lap) has to
    equal the panel dimension the split crosses -- so one class serves both and
    only the axis changes.

    A vertical split is worth knowing about for two reasons beyond looks. The
    opening stops being a line across the whole panel, which is what makes a
    back pocket obvious. And NEITHER outer piece hangs from the coil when it is
    open: each is still caught in the binding along its own outside edge, where
    a horizontal split leaves the lower piece hanging from the zipper alone.
    """

    #: Where the zip is measured from, per axis, and what the two outer pieces
    #: are called once it is cut.
    AXES = {"top": ("zip_from_top_in", "upper", "lower"),
            "side": ("zip_from_side_in", "near", "far")}

    def __init__(self, face: str, spec: dict, bag: "BoxBag"):
        self.face = face
        if "zip_from_side_in" in spec and "zip_from_top_in" in spec:
            raise ValueError(f"{face} pocket: declare zip_from_top_in OR "
                             "zip_from_side_in, not both -- a panel splits one "
                             "way or the other")
        self.axis = "side" if "zip_from_side_in" in spec else "top"
        key, _, _ = self.AXES[self.axis]
        self.zip = F(str(spec[key]))
        self.coil = F(str(spec.get("coil_in", bag.coil)))
        self.lap = F(str(spec.get("lap_in", bag.lap)))
        self.must_hold = spec.get("must_hold_in")
        #: The panel dimension the split crosses: height for a horizontal zip,
        #: width for a vertical one.
        self.span = bag.panel_h if self.axis == "top" else bag.panel_w
        #: ...and the one it RUNS along, which is the other one.
        self.along = bag.panel_w if self.axis == "top" else bag.panel_h
        #: How far in from the panel's start the zip's first stop sits. The
        #: opening does not have to be the whole seam: above it the two outer
        #: pieces lap onto EACH OTHER instead of onto tape, so the seam is one
        #: continuous line and only the zipper is shorter. Costs nothing, and
        #: it is what lets anything else live at that end of the panel -- the
        #: belt keepers here, which could not be centred while a placket ran
        #: the full height.
        self.starts = F(str(spec.get("zip_starts_in", 0)))
        self.run = self.along - self.starts
        # Same standard install as the zipper panel: sewn face down to the
        # tape and folded back, so the cut piece is what shows, less the tape
        # reveal, plus what the seam eats.
        self.reveal = ZIP_REVEAL_IN
        self.upper = self.zip - self.coil / 2 - self.reveal + self.lap
        self.lower = (self.span - (self.zip + self.coil / 2)
                      - self.reveal + self.lap)
        #: How far the cavity reaches past the opening, and how much panel is
        #: left on the near side once the seam allowance and the lap are gone --
        #: the band anything tacked to the near piece has to live in.
        self.reach = self.span - self.zip - self.coil / 2
        self.band = self.upper - self.lap - bag.sa
        self.above = self.zip - self.coil / 2 - bag.sa
        #: A placket -- the flap that hangs over the coil and hides it. Caught
        #: in the near piece's lap topstitching, so it costs one cut piece and
        #: no new seam. `show_in` is what hangs free past the coil.
        pl = spec.get("placket")
        self.placket = None
        if pl:
            show = F(str((pl if isinstance(pl, dict) else {}).get("show_in", "0.75")))
            # As long as the ZIP, not as long as the panel: there is nothing
            # to cover where there is no coil.
            self.placket = {"show": show, "cut": show + self.lap,
                            "long": self.run}

    #: Two pockets cut as one pair of pieces only if they agree on ALL of this.
    def key(self) -> tuple:
        return (self.axis, self.zip, self.coil, self.lap, self.starts,
                None if not self.placket else self.placket["show"])

    @property
    def pieces(self) -> tuple:
        return self.AXES[self.axis][1], self.AXES[self.axis][2]


class BoxBag:
    """A bound-seam box bag derived from its finished envelope."""

    def __init__(self, spec: dict):
        self.spec = spec
        self.name = spec["name"]
        f = spec["finished_in"]
        self.W, self.H, self.D = F(str(f["w"])), F(str(f["h"])), F(str(f["d"]))
        self.sa = F(str(spec.get("seam_allowance_in", "0.375")))
        # Turned: no binding, so no strip to size and no second material.
        self.shell = spec.get("shell", "cordura-1000d")
        self.win_mat = spec.get("window_material", "vinyl-20ga")
        self.bind_mat = self.shell     # kept only for the "one cloth" flag
        self.shell_mm, self.shell_frays = mat(self.shell)["mm"], mat(self.shell)["frays"]
        self.bind_mm, self.bind_frays = self.shell_mm, self.shell_frays
        self.shell_melts = bool(mat(self.shell).get("melt_seal"))
        # Fraying binding must be folded under on its outer edge: four layers
        # at every seam instead of two, and 3/4" more strip width.
        self.double_fold = False       # nothing to fold: no binding
        self.windows = bool(spec.get("windows"))
        win_mm = mat(self.win_mat)["mm"] if self.windows else self.shell_mm
        self.sandwich_mm = win_mm + self.shell_mm
        self.panel_mat = self.win_mat if self.windows else self.shell
        # A pocket makes its panel TWO layers, and a divider lying flat against
        # a panel's interior adds a third over the edges it is caught in. Every
        # one of those shows up in that panel's bound seam, so size the binding
        # for the WORST seam on the bag rather than the average one.
        div = spec.get("divider")
        pk = spec.get("panel_pockets", {})
        self.panel_layers = {}
        for f in ("front", "back"):
            n = 1 + (1 if f in pk else 0)
            if div and div.get("face", "front") == f                     and div.get("attach", "seam") == "seam":
                n += 1
            self.panel_layers[f] = n

        self.panel_sandwich_mm = {f: win_mm * n + self.shell_mm
                                  for f, n in self.panel_layers.items()}

        worst = max(self.sandwich_mm, *self.panel_sandwich_mm.values())
        # ceil, not round: a strip that has to reach round a sandwich and back
        # is either long enough or it is not, and rounding to nearest is wrong
        # half the time in the direction that cannot be recovered.
        # A turned seam is the pieces and nothing else -- no binding doubling
        # it, and no mitre doubling it again. That is the single biggest
        # reduction the change buys: the worst seam on the bag was 3.60 mm
        # bound and is 1.80 mm turned.
        self.bind_layers = 0
        self.seam_mm = self.sandwich_mm
        self.corner_mm = self.seam_mm
        self.panel_seam_mm = dict(self.panel_sandwich_mm)
        self.panel_corner_mm = dict(self.panel_sandwich_mm)

        z = spec.get("closure", {})
        self.coil = F(str(z.get("coil_in", "0.25")))
        self.lap = F(str(z.get("lap_in", "0.5")))
        # Two sliders on the main run is the default because it is the choice
        # that cannot be made later: both go on the chain before either end is
        # stopped, and the panel is then built round them. A pocket zip is
        # always one -- it is short, and it has a right way round.
        # Standard or reverse COIL. It changes exactly one instruction -- which
        # face of the chain goes up when you lap onto it -- and that instruction
        # has no undo: get it wrong and the finished bag has its pull on the
        # inside with both laps sewn. So it is declared rather than assumed.
        self.coil_kind = str(z.get("coil", "reverse")).lower()
        if self.coil_kind not in ("standard", "reverse"):
            raise ValueError("closure.coil must be 'standard' or 'reverse'")
        self.main_sliders = int(z.get("sliders", 2))
        if self.main_sliders not in (1, 2):
            raise ValueError("closure.sliders must be 1 or 2")
        # A bag carried by straps needs a webbing loop round its girth to take
        # the load off the shell. A belt pouch is carried by the belt, so it
        # needs none -- and below about 2 1/2" of depth there is no room for one
        # beside the zipper anyway. Declaring "chassis": null says so.
        #
        # Absent means "the usual chassis"; only an explicit null turns it off.
        # Reading absent as off silently re-centred the StadiumTote's coil and
        # moved both its zipper strips -- caught by the regression against its
        # hand-computed figures, which is the only reason that check exists.
        c = spec["chassis"] if "chassis" in spec else {}
        self.has_chassis = c is not None
        c = c or {}
        self.web = F(str(c.get("webbing_in", "1.0")))
        self.overlap = F(str(c.get("overlap_in", "4.0")))
        self.feat = spec.get("features", {})
        self.pieces = spec.get("pieces", [])
        # A loose base stiffener is a CHOICE, not a property of the
        # construction. It was an unconditional step, so every bag was told to
        # cut one -- including bags that have none, and including bags with a
        # rounded bottom, where a rectangle cut to the interior cannot lie flat
        # because the flat floor is 2 x corner_r shorter than the face.
        self.stiffener = bool(spec.get("stiffener"))

        # ---- TURNED construction -------------------------------------
        # Panels and gusset are sewn RIGHT SIDES TOGETHER and the bag is turned
        # through the zip, so the allowances finish INSIDE and the finished edge
        # IS the stitch line. That makes the geometry the ordinary one every bag
        # tutorial uses:  cut = finished + 2 x allowance.
        #
        # (It replaced a bound-flange scheme whose allowances pointed outward
        # and were wrapped in binding. That put a rib round the bag, cost 7/16"
        # per edge of interior, and was reached for on a waterproofing argument
        # this shell does not support -- it is water RESISTANT, not waterproof.
        # Turned is the standard construction for a pack this size and it is
        # what the family uses now.)
        #
        # 3/8" is the usual bag-work allowance and what the sources here quote;
        # it is also small enough to keep bulk down at the curves.
        self.face_w = self.W
        self.face_h = self.H
        self.face_d = self.D

        # Keep embroidery and hardware off the seam. Nothing structural depends
        # on this -- it is a placement margin, not a construction dimension.
        self.visible_w = self.W - 2 * SEAM_MARGIN_IN
        self.visible_h = self.H - 2 * SEAM_MARGIN_IN
        self.visible_d = self.D - 2 * SEAM_MARGIN_IN

        # Cuts: finished plus an allowance on every edge.
        self.panel_w = self.W + 2 * self.sa
        self.panel_h = self.H + 2 * self.sa
        self.gusset_w = self.D + 2 * self.sa

        # Rounded corners help a turned bag rather than a bound one: a curve
        # turns out cleanly where a square corner needs its allowance trimmed
        # across the point to sit flat, and there is no mitre either way now.
        cs = spec.get("corners", {})
        self.corner_r = F(str(cs.get("bottom_in", 0)))
        self.curved_corners = 2 if self.corner_r > 0 else 0
        self.square_corners = 4 - self.curved_corners
        # At the cut edge the same corner is one seam allowance further out.
        self.corner_cut_r = self.corner_r + self.sa if self.corner_r else F(0)
        self.corner_saved = round_to(self.curved_corners * self.corner_r
                                     * CORNER_SAVING, 16)
        # Relief clips let the gusset's allowance splay round a convex curve.
        # Practitioner rule, and the reason the depth is not arbitrary: snip to
        # 1/8" SHORT of the stitch line, spaced about a seam allowance apart.
        self.clip_depth = self.sa - F(1, 8)
        self.relief_clips = (math.ceil(float(self.corner_r) * math.pi / 2
                                       / float(self.sa)) if self.corner_r else 0)
        self.corner_cut_saved = round_to(self.curved_corners * self.corner_cut_r
                                         * CORNER_SAVING, 16)

        # The ring follows the stitch line, not the raw edge.
        self.ring = 2 * (self.W + self.H) - self.corner_saved
        self.zip_face = self.face_w                    # zipper spans the top
        self.gusset_face = self.ring - self.zip_face
        # EXACTLY ONE of the two pieces carries the lap allowance. Two strips
        # lapped by L cover (a + b - L) of path, so if both are cut long the
        # ring comes out 2L over -- an inch here, eased into a bound seam that
        # cannot take it, which is the mistake this whole generator exists to
        # make impossible. The ZIPPER PANEL carries it, because zip_face is the
        # opening and has to survive being lapped over at both ends; the gusset
        # is the piece that gets fitted and trimmed, so it is cut to the figure
        # the ring needs and nothing more.
        # Plain seams at both joins, so BOTH pieces carry their own allowance.
        # Under the old lapped join exactly one of them could, and getting that
        # wrong made the ring an inch long on every bag in the family.
        self.zip_cut = self.zip_face + 2 * self.sa
        self.gusset_cut = self.gusset_face + 2 * self.sa

        # Zipper strips. The coil sits off-centre so the webbing can run the
        # face centreline unbroken; centre it in the space forward of the web.
        # With a chassis the coil is pushed forward so the webbing can hold the
        # face centreline unbroken; without one it simply sits centred.
        self.web_lo = self.gusset_w / 2 - self.web / 2
        self.coil_c = (round_to((self.sa + self.web_lo) / 2, 8) if self.has_chassis
                       else round_to(self.gusset_w / 2, 16))
        # Sewn face down to the tape and folded back, so the cut strip is the
        # cloth that will SHOW, less the tape reveal, plus the allowance the
        # seam eats. `lap` is what the seam consumes.
        self.reveal = ZIP_REVEAL_IN
        self.strip_front = (self.coil_c - self.coil / 2
                            - self.reveal + self.lap)
        self.strip_rear = (self.gusset_w - (self.coil_c + self.coil / 2)
                           - self.reveal + self.lap)

        # A divided slip pocket lying flat against a panel's interior. Its sides
        # and bottom are caught in that panel's own binding -- already
        # structural, already there -- so the only new seam is its own top edge.
        # A pocket's contents sit on its bottom seam, and putting that seam in
        # the middle of a panel makes a loaded stitch line where there was none.
        self.divider = div
        self.has_divider = div is not None
        if div:
            self.div_face = div.get("face", "front")
            self.div_h = F(str(div["height_in"]))
            self.div_channels = [F(str(x)) for x in div.get("channels_in", [])]
            # Caught in the panel's binding, or topstitched clear of it. The
            # second costs three straight runs and saves a bound edge, a layer
            # in the worst seam on the bag, and any argument with a rounded
            # corner it would otherwise have to be cut around.
            self.div_attach = div.get("attach", "seam")
            self.div_inset = F(str(div.get("inset_in", "0.25")))
            if self.div_attach == "seam":
                self.div_w = self.panel_w
                self.div_depth = self.div_h - self.sa
                self.div_clear = self.panel_h - self.div_h - self.sa
            else:
                self.div_w = self.face_w - 2 * self.div_inset
                self.div_depth = self.div_h - self.div_inset
                self.div_clear = self.face_h - self.div_inset - self.div_h
        # Inset a uniform distance from a curved boundary, the divider's own
        # corners are that curve offset inward -- radius R - inset. Cut it
        # square and its bottom corners overhang the panel's curve and end up
        # in the binding, which is the one place a topstitched pocket must not
        # be. Measured on this bag: 0.42" of overhang.
        # Both attachments follow the panel's curve; they just sit at different
        # distances from it. Topstitched, the divider is inset from the stitch
        # line so its radius is the stitch-line radius less the inset. Caught
        # in the binding, its edges ARE the panel's cut edges, so it takes the
        # panel's cut radius exactly and gets cut round the same template.
        #
        # Only the first case was derived. The second left div_r at zero, which
        # would have drawn a rectangle whose corners overhang the curve — and
        # rather than derive it, a check simply refused the configuration.
        self.div_r = F(0)
        if div and self.corner_r and self.div_face in ("front", "back"):
            # Caught in the seam, it is cut to the panel and takes the panel's
            # own cut curve; topstitched clear of it, the curve moves in by the
            # inset.
            self.div_r = (max(F(0), self.corner_r - self.div_inset)
                          if self.div_attach == "topstitch" else self.corner_cut_r)

        # Chassis loop. There is no binding to compute any more: a turned bag
        # finishes its own edges, which is most of why it is the simpler build.
        self.loop = self.ring + self.overlap
        # How much seam there is to sew, which is what a turned bag costs
        # instead. Two panel perimeters, plus the divider's hemmed top.
        self.seam_run = 2 * self.ring
        if self.has_divider:
            self.seam_run += self.panel_w

        # Belt keepers. The keeper wraps the belt and both ends tack to the
        # panel, so its cut length is twice the belt width plus the wrap; its
        # WIDTH is how much of the belt's length it grips and is a choice, not
        # a consequence.
        bl = self.feat.get("belt_loops")
        self.loops = bl
        if bl:
            self.loop_for = F(str(bl["for_in"]))
            self.loop_count = int(bl.get("count", 1))
            self.loop_w = F(str(bl.get("width_in", "2.0")))
            self.loop_len = 2 * self.loop_for + F(3, 2)
            # fold under + box-X footprint, each end, plus the belt and the two
            # thicknesses the strip climbs over it.
            self.keeper_min = (2 * KEEPER_FOLD_IN + 2 * KEEPER_TACK_IN
                               + self.loop_for
                               + round_to(2 * WEBBING_MM / MM_PER_IN, 16))
            # A keeper carrying the whole bag pulls on one layer of shell.
            # An anchor strip whose ends are caught in the panel's own binding
            # spreads that into a seam that was already carrying the bag --
            # the same argument the chassis makes, applied to a panel.
            self.loop_anchor = bool(bl.get("anchor"))

        # Who wears it, and how. The belt used to be a hand-written row in the
        # takeoff that would not move when the bag's size did; declaring the
        # fit range makes it derived like everything else.
        wr = spec.get("wearer")
        self.wearer = wr
        if wr:
            self.waist = [F(str(x)) for x in wr["waist_in"]]
            self.crossbody = F(str(wr["crossbody_in"])) if "crossbody_in" in wr else None
            self.handed = wr.get("handed", "right")
            self.taper = F(str(wr.get("taper_in_per_in", DEFAULT_TAPER)))
            self.belt_tail = F(str(wr.get("tail_in", "6")))
            self.sling_takeup = F(str(wr.get("sling_takeup_in", SLING_TAKEUP_IN)))
            self.belt_takeup = F(str(wr.get("belt_takeup_in", BELT_TAKEUP_IN)))
            # A belt or a strap the wearer already owns is DECLARED, not
            # derived. The BeltPouch says so by having no `wearer` at all,
            # which also throws away the fit range, the contact-pressure
            # figures and the handedness -- all of which still describe a belt
            # somebody else made. Naming what is supplied keeps the reasoning
            # and drops only the cutting.
            self.supplies = set(wr.get("supplies", []))
            self.makes_belt = "belt" not in self.supplies
            self.makes_strap = "strap" not in self.supplies
            # A bag with rings gets a dedicated sling for crossbody, so its belt
            # only has to reach a waist. Without rings the belt has to do both,
            # and it is the longer of the two that sizes it.
            self.has_sling = (int(self.feat.get("d_rings", 0)) > 0
                              and self.crossbody is not None)
            self.fit_max = (self.waist[1] if self.has_sling
                            else max([self.waist[1]]
                                     + ([self.crossbody] if self.crossbody else [])))
            # The buckle's fixed half is folded back and box-X'd, and the
            # adjustable end threads through its tri-glide and back on itself.
            # The sling has always carried that allowance; the belt did not,
            # so its declared tail was most of it eaten before the wearer got
            # any of it.
            if self.makes_belt:
                self.belt_cut = round_to(self.fit_max + self.belt_takeup
                                         + self.belt_tail, 1)
            if self.has_sling and self.makes_strap:
                self.sling_cut = round_to(self.crossbody + self.sling_takeup, 1)

        # Zipped pockets built into panels. Every one is the same object on a
        # different face, which is why the outer pieces come out as pairs and
        # one construction step describes them all.
        self.pockets = {f: PanelPocket(f, s, self) for f, s in sorted(pk.items())}
        self.has_back_pocket = "back" in self.pockets
        self.has_front_pocket = "front" in self.pockets
        self.has_panel_pocket = bool(self.pockets)
        if self.pockets:
            # Every pocket on a bag shares its zip height, coil and lap. That is
            # a deliberate constraint rather than an oversight: it makes the
            # outer pieces identical front and back -- two pairs instead of four
            # singletons -- and it lets one assembly step state the figures for
            # all of them. `panel pockets agree` reports it if they diverge.
            # These aggregates describe ONE pocket and are quoted by the
            # construction as if they described all of them, which is only true
            # while every pocket agrees. `panel pockets agree` is what keeps
            # that honest; when they diverge it reports the cost rather than
            # letting one step state figures for a pocket built the other way.
            self.pockets_agree = len({p.key() for p in self.pockets.values()}) == 1
            first = next(iter(self.pockets.values()))
            self.bp_axis = first.axis
            self.bp_zip, self.bp_coil, self.bp_lap = first.zip, first.coil, first.lap
            self.bp_upper, self.bp_lower = first.upper, first.lower
            self.bp_bag, self.bp_band = first.reach, first.band

    # -- derived facts -----------------------------------------------------
    @property
    def flags(self) -> dict:
        return {
            "has_chassis": self.has_chassis,
            "shell_frays": self.shell_frays,
            "double_fold": self.double_fold,
            "has_windows": self.windows,
            "has_handle": bool(self.feat.get("handle_in")),
            "has_drings": int(self.feat.get("d_rings", 0)) > 0,
            "has_belt_loop": bool(self.loops),
            "has_belt_anchor": bool(self.loops) and self.loop_anchor,
            "has_ring_anchor": bool(self.feat.get("d_ring_anchor")),
            "has_divider": self.has_divider,
            # Caught in the panel's binding, or topstitched clear of it. They
            # are different operations with different figures, and one step
            # cannot describe both -- it used to try, and described only the
            # second while the schema still offered the first.
            "has_seamed_divider": self.has_divider and self.div_attach == "seam",
            "has_stiffener": self.stiffener,
            # How a piece is CUT, and whether the binding is a second material
            # at all. A bag bound in its own shell buys no tape and reaches for
            # no hot knife, and saying otherwise sent a reader shopping for
            # both.
            "shell_melts": self.shell_melts,
            "self_bound": self.bind_mat == self.shell,
            "has_webbing": bool(self.has_chassis
                                or int(self.feat.get("d_rings", 0))
                                or self.feat.get("handle_in")
                                or (self.loops and self.wearer
                                    and getattr(self, "makes_belt", True))),
            # The wearer brings the belt AND the strap, so this bag makes
            # neither. Nothing else in the family declares a wearer, so a
            # `makes_belt` flag would read False on three bags that simply
            # never said -- which is not the same statement at all.
            # A pocket split ACROSS the panel and one split DOWN it are
            # different operations with different pieces and different figures.
            # One step cannot state both, and the aggregate tokens describe
            # whichever pocket sorted first -- so a single step would have
            # quoted the back's numbers at the front.
            "reverse_coil": self.coil_kind == "reverse",
            "standard_coil": self.coil_kind == "standard",
            "has_top_zip": any(p.axis == "top" for p in self.pockets.values()),
            "has_side_zip": any(p.axis == "side" for p in self.pockets.values()),
            "has_placket": any(p.placket for p in self.pockets.values()),
            "supplies_carry": bool(self.wearer) and not self.makes_belt
                              and not (self.has_sling and self.makes_strap),
            "has_sling": bool(self.wearer) and getattr(self, "has_sling", False),
            "has_back_pocket": self.has_back_pocket,
            "has_front_pocket": self.has_front_pocket,
            "has_panel_pocket": self.has_panel_pocket,
            # Declared pocket PIECES. The back pocket is its own flag: it is
            # built out of the panel rather than applied to it, so a step
            # written for an applied pocket does not describe it.
            "has_pockets": any(p.get("kind") == "pocket" for p in self.pieces),
        }

    @property
    def geometry(self) -> dict:
        """Every derived figure, flat, keyed by the name a step may use."""
        g = {
            "w": self.W, "h": self.H, "d": self.D,
            "sa": self.sa, "clip_depth": self.clip_depth,
            "reveal": self.reveal,
            "seam_margin": SEAM_MARGIN_IN,
            "turn": TURN_IN,
            "face_w": self.face_w, "face_h": self.face_h, "face_d": self.face_d,
            "visible_w": self.visible_w, "visible_h": self.visible_h,
            "visible_d": self.visible_d,
            "panel_w": self.panel_w, "panel_h": self.panel_h,
            "gusset_w": self.gusset_w, "gusset_face": self.gusset_face,
            "gusset_cut": self.gusset_cut,
            "gusset_cut_long": self.gusset_cut + 3,
            "ring": self.ring, "zip_face": self.zip_face, "zip_cut": self.zip_cut,
            "coil": self.coil, "lap": self.lap, "coil_c": self.coil_c,
            "strip_front": self.strip_front, "strip_rear": self.strip_rear,
            "seam_run": self.seam_run,
        }
        if self.has_chassis:
            g.update({"web": self.web, "overlap": self.overlap, "loop": self.loop,
                      "web_lo": self.web_lo})
        if self.feat.get("handle_in"):
            g["handle"] = F(str(self.feat["handle_in"]))
        if self.loops:
            g.update({"belt": self.loop_for, "keeper_w": self.loop_w,
                      "keeper_len": self.loop_len})
        if self.wearer:
            g.update({"waist_min": self.waist[0], "waist_max": self.waist[1],
                      "fit_max": self.fit_max})
            if self.makes_belt:
                g.update({"belt_cut": self.belt_cut,
                          "belt_takeup": self.belt_takeup,
                          "belt_tail": self.belt_tail})
            if self.crossbody:
                g["crossbody"] = self.crossbody
            if self.has_sling and self.makes_strap:
                g["sling_cut"] = self.sling_cut
        if self.flags["has_ring_anchor"]:
            g.update({"ring_anchor_w": RING_ANCHOR_W_IN,
                      "ring_anchor_len": self.gusset_w})
        if self.has_divider:
            g.update({"divider_h": self.div_h, "divider_w": self.div_w,
                      "divider_depth": self.div_depth,
                      "divider_clear": self.div_clear,
                      "divider_inset": self.div_inset,
                      # ...and where that inset lands measured from the RAW
                      # edge, which is the edge the person at the mat is
                      # looking at. The two differ by a seam allowance and the
                      # step used to quote the wrong one.
                      "divider_edge": self.sa + self.div_inset})
        if self.corner_r:
            g.update({"corner_r": self.corner_r, "corner_cut_r": self.corner_cut_r})
        if self.stiffener:
            # The flat floor, not the face. A rounded bottom corner takes
            # corner_r off each end of the run the gusset lies flat along.
            g["floor_w"] = self.face_w - 2 * self.corner_r
            g["floor_d"] = self.face_d
        if self.has_panel_pocket:
            # Per-AXIS figures, so a step can name the pocket it describes
            # rather than the one that happened to sort first.
            for ax, (near, far) in (("top", ("upper", "lower")),
                                    ("side", ("near", "far"))):
                ps = [q for q in self.pockets.values() if q.axis == ax]
                if not ps:
                    continue
                q = ps[0]
                g.update({f"{ax}_zip": q.zip, f"{ax}_starts": q.starts,
                          f"{ax}_run": q.run,
                          f"{ax}_{near}": q.upper, f"{ax}_{far}": q.lower,
                          f"{ax}_across": (self.panel_w if ax == "top"
                                           else self.panel_h),
                          f"{ax}_reach": q.reach})
                if q.placket:
                    g.update({f"{ax}_placket": q.placket["cut"],
                              f"{ax}_placket_show": q.placket["show"],
                              f"{ax}_placket_long": q.placket["long"]})
            g.update({"bp_across": (self.panel_w if self.bp_axis == "top"
                                    else self.panel_h),
                      "bp_zip": self.bp_zip, "bp_coil": self.bp_coil,
                      "bp_lap": self.bp_lap, "bp_upper": self.bp_upper,
                      "bp_lower": self.bp_lower, "bp_bag": self.bp_bag,
                      "bp_band": self.bp_band})
        return g

    def channel_widths(self) -> list[F]:
        """The channels the divider's topstitch lines actually make.

        Measured across the DIVIDER. A topstitched divider stops div_inset
        short of the binding on each side, so reading its outer channels off
        the panel's visible face -- which the check and the report each did
        separately -- overstated both of them by the inset.
        """
        if not self.has_divider:
            return []
        face_w = self.face_size(self.div_face)[0]
        edge = self.channel_edge()
        edges = [edge] + sorted(self.div_channels) + [face_w - edge]
        return [b - a for a, b in zip(edges, edges[1:])]

    def channel_edge(self) -> F:
        """How far the outermost channel starts from the face's edge.

        Caught in the panel seam the divider reaches the finished edge, so its
        outer channels run the whole way -- there is no inset to subtract.
        Topstitched, it stops div_inset short on each side.
        """
        return F(0) if self.div_attach == "seam" else self.div_inset

    @property
    def words(self) -> dict:
        """Tokens whose value is a WORD, not a figure.

        Kept out of `geometry` because every value there is a dimension the
        package renders twice -- as a float for the drawing and as a fraction
        for the human -- and a face name is neither. A step that says "the
        panel's interior" on a bag with two doubled panels does not tell the
        person at the machine which panel.
        """
        # A COUNT is a word here too, not a dimension: `geometry` renders every
        # value through frac(), which puts an inch mark on it, and "7 snips" came
        # out as '7"' in the middle of a sentence.
        w = {"needle": mat(self.shell).get("needle", "jeans 100/16"),
             "relief_clips": str(self.relief_clips)}
        if self.has_divider:
            w["divider_face"] = self.div_face
        return w

    def interior(self) -> dict:
        # A rounded corner takes a bite out of the cross-section as well as the
        # perimeter: r^2 - (pi r^2)/4 per corner, which the face rectangle does
        # not know about. 2% here, but a stated capacity that ignores the shape
        # is a stated capacity that is wrong.
        bite = (float(self.corner_r) ** 2 * (1 - math.pi / 4)
                * self.curved_corners) if self.corner_r else 0.0
        vol_in3 = (float(self.face_w * self.face_h) - bite) * float(self.face_d)
        return {"w": dim(self.face_w), "h": dim(self.face_h), "d": dim(self.face_d),
                "in3": round(vol_in3, 2),
                "litres": round(vol_in3 * CM3_PER_IN3 / 1000.0, 2)}

    # -- tokens and conditions --------------------------------------------
    def resolve(self, text: str) -> str:
        """Replace every {token} with its fraction form, or raise."""
        if not text or "{" not in text:
            return text
        g, words = self.geometry, self.words
        out, i = [], 0
        while i < len(text):
            ch = text[i]
            if ch != "{":
                out.append(ch)
                i += 1
                continue
            j = text.find("}", i)
            if j < 0:
                raise TokenError(f"{self.name}: unclosed '{{' in {text!r}")
            key = text[i + 1:j]
            if key in words:
                out.append(words[key])
            elif key in g:
                out.append(frac(g[key]))
            else:
                raise TokenError(
                    f"{self.name}: unknown token {{{key}}} -- "
                    f"available: {', '.join(sorted(list(g) + list(words)))}")
            i = j + 1
        return "".join(out)

    def applies(self, step: dict) -> bool:
        fl = self.flags
        for k in step.get("when", []):
            if k not in FLAGS:
                raise ValueError(f"{self.name}: unknown flag {k!r} in a 'when'")
            if not fl[k]:
                return False
        for k in step.get("unless", []):
            if k not in FLAGS:
                raise ValueError(f"{self.name}: unknown flag {k!r} in an 'unless'")
            if fl[k]:
                return False
        return True

    # -- cut list ----------------------------------------------------------
    def cut_list(self) -> list[dict]:
        def row(piece, qty, w, l, material, note="", r=F(0)):
            # A piece that carries the bag's rounded corners is not a rectangle,
            # and a cut list that draws it as one is a cut list you cut wrong.
            d = {"piece": piece, "qty": qty, "w": dim(w), "l": dim(l),
                 "material": material, "note": note,
                 "corner_r": dim(r), "corners": "bottom" if r else "square"}
            if r:
                d["note"] = (note + "; " if note else "") +                     f"BOTTOM CORNERS ROUND AT {frac(r)} — cut round a template"
            return d

        n = len(self.pockets)
        if n:
            faces = " and ".join(sorted(self.pockets))
            plain = [f for f in ("front", "back") if f not in self.pockets]
            # Always two full-size panels, whatever the pockets do. A pocketed
            # panel spends its on the inner layer and a plain one is just
            # itself, so the PIECE is identical either way -- only its job
            # differs. One cut-list row, cut twice.
            out = [row("Panel, full size", 2, self.panel_w, self.panel_h,
                       self.panel_mat, r=self.corner_cut_r, note=
                       f"the inner layer behind the {faces} pocket"
                       + (f", and the plain {plain[0]} panel" if plain else "")
                       + ". Bound on all four edges: it is the compartment wall, "
                       "what seals each pocket, and what anything tacked to the "
                       "panel lands on"),
                   ]
            # One row per DISTINCT pocket build. Two pockets split the same way
            # at the same height are one pair of pieces; split different ways
            # they are four singletons, and the cut list has to say so.
            seen = {}
            for f, pk in sorted(self.pockets.items()):
                seen.setdefault(pk.key(), []).append(f)
            for key, fs in seen.items():
                pk = self.pockets[fs[0]]
                who = " and ".join(fs)
                near, far = pk.pieces
                across = self.panel_w if pk.axis == "top" else self.panel_h
                # The piece carrying the bag's bottom edge inherits its curve.
                # A horizontal split puts that on the lower piece; a vertical
                # one puts it on BOTH, because both reach the bottom.
                r_near = self.corner_cut_r if pk.axis == "side" else F(0)
                r_far = self.corner_cut_r
                out.append(row(f"Panel, outer {near}", len(fs), across, pk.upper,
                               self.panel_mat, r=r_near,
                               note=f"laps {frac(pk.lap)} onto the pocket zip tape "
                                    f"({who}); zip runs "
                                    + ("ACROSS the panel" if pk.axis == "top"
                                       else "DOWN the panel")))
                out.append(row(f"Panel, outer {far}", len(fs), across, pk.lower,
                               self.panel_mat, r=r_far,
                               note=f"laps {frac(pk.lap)} onto the pocket zip tape "
                                    f"({who}); it carries the panel's bottom edge"))
                if pk.placket:
                    out.append(row("Placket", len(fs), pk.placket["long"],
                                   pk.placket["cut"], self.panel_mat,
                                   f"the flap that hides the {who} pocket zip: "
                                   f"{frac(pk.lap)} caught in the near piece's own "
                                   f"lap topstitching, {frac(pk.placket['show'])} "
                                   "hanging free over the coil. Its free edge is "
                                   "left raw"))
        else:
            out = [row("Front and back panel", 2, self.panel_w, self.panel_h,
                       self.panel_mat, r=self.corner_cut_r)]
        out.append(row("Gusset", 1, self.gusset_w, self.gusset_cut + 3, self.shell,
                       f"cut long; trim the GUSSET to {frac(self.gusset_cut)} "
                       "against the back panel before closing it, so the ring "
                       f"closes at {frac(self.ring)}"))
        out.append(row("Zip strip, front", 1, self.strip_front, self.zip_cut,
                       self.shell, f"narrow side; laps {frac(self.lap)} onto the tape"))
        out.append(row("Zip strip, rear", 1, self.strip_rear, self.zip_cut,
                       self.shell, f"wide side; laps {frac(self.lap)} onto the tape"))
        fold = ("single fold" if not self.double_fold
                else "DOUBLE fold -- outer edge turned under")
        # One row, however many strips -- they are all the same length, and
        # seven identical lines is a cut list nobody reads to the end of.
        if self.has_divider:
            n = len(self.div_channels)
            out.append(row("Divider pocket", 1, self.div_w, self.div_h, self.shell,
                           r=self.div_r, note=
                           f"lies flat against the {self.div_face} panel's interior; "
                           + ("sides and bottom caught in that panel's own binding, "
                              "top edge bound and free"
                              if self.div_attach == "binding" else
                              f"topstitched down three sides {frac(self.div_inset)} "
                              "clear of the binding, top edge free — it is the "
                              "pocket's mouth")
                           + (f"; {n} line(s) of topstitching make "
                              f"{n + 1} channels" if n else "")))
        if self.flags["has_ring_anchor"]:
            out.append(row("D-ring anchor strip", int(self.feat["d_rings"]),
                           self.gusset_w, RING_ANCHOR_W_IN, self.shell,
                           "across the gusset's interior at each ring, both ends "
                           "caught in the panel bindings — the tack goes through "
                           "tab + gusset + anchor"))
        if self.loops:
            out.append(row("Belt keeper", self.loop_count, self.loop_w,
                           self.loop_len, self.shell,
                           f"fits a {frac(self.loop_for)} belt"))
            if self.loop_anchor:
                out.append(row("Belt anchor strip", 1, self.panel_w, self.loop_w,
                               self.shell,
                               "interior of the back panel, behind the keepers; "
                               "both ends caught in the side binding, so the load "
                               "spreads into the seam instead of into a stitch field"))
        for p in self.pieces:
            w, l = (F(str(v)) for v in p["cut_in"])
            out.append(row(p["piece"], int(p.get("qty", 1)), w, l,
                           p.get("material", self.shell), p.get("note", "")))
        return out

    def layouts(self) -> list[dict]:
        """One shelf-nested layout per material that is sold on a roll.

        First-fit decreasing by height, longer edge along the roll width. Good
        enough to answer the only question being asked -- how much do I buy --
        and deterministic, so a test can assert nothing overlaps.
        """
        by_mat: dict[str, list[tuple[str, F, F]]] = {}
        for r in self.cut_list():
            m = r["material"]
            if mat(m).get("by_length"):
                continue
            # Bias strips are cut across the grain at 45 degrees. Laying them
            # in a shelf nest as long rectangles along the roll would be a
            # drawing of something you cannot cut -- they come off a square,
            # and the takeoff prices them that way instead.
            w, l = F(str(r["w"]["in"])), F(str(r["l"]["in"]))
            long_, short = (l, w) if l >= w else (w, l)
            rad = F(str(r.get("corner_r", {}).get("in", 0)))
            for _ in range(r["qty"]):
                by_mat.setdefault(m, []).append((r["piece"], long_, short, rad))

        out = []
        for m in sorted(by_mat):
            roll = F(self.spec.get("layout", {}).get(m)
                     or mat(m).get("roll_in", DEFAULT_ROLL_IN))
            items = sorted(by_mat[m], key=lambda t: (-t[2], -t[1], t[0]))
            placed, y, x, row_h = [], F(0), F(0), F(0)
            for piece, w, h, rad in items:
                if x + w > roll and x > 0:
                    y, x, row_h = y + row_h, F(0), F(0)
                placed.append({"piece": piece, "x": float(x), "y": float(y),
                               "w": float(w), "h": float(h), "r": float(rad)})
                x, row_h = x + w, max(row_h, h)
            used = y + row_h
            out.append({"material": m, "roll_width_in": float(roll),
                        "used": dim(used),
                        "buy": dim(round_to(used * F(6, 5), 2)),
                        "pieces": placed})
        return out

    # -- takeoff, hardware, thickness -------------------------------------
    def takeoff(self) -> list[dict]:
        out = []
        # A bias square is not nested -- it comes off the diagonal and the
        # shelf nest draws pieces along the roll -- but when the binding IS the
        # shell it is still the same cloth off the same cut. Splitting one
        # fabric across two takeoff lines and drawing only one of them is how
        # you under-buy, and it reads as "the binding is not in the cut list".
        extra = F(0)
        for lay in self.layouts():
            buy = F(str(lay["buy"]["in"]))
            note = (f"{lay['used']['text']} nests the pieces; "
                    f"about {float(buy) / 36.0:.2f} yd with margin")
            if extra and lay["material"] == self.shell:
                buy = round_to(buy + extra, 2)
                note = (f"{lay['used']['text']} nests the pieces; "
                        f"about {float(buy) / 36.0:.2f} yd with margin")
            out.append({"item": f"{lay['material']}, {lay['roll_width_in']:g}\" wide",
                        "qty": f"{frac(buy)} of length",
                        "note": note})
        web_total = F(0)
        parts = []
        if self.has_chassis:
            web_total += self.loop
            parts.append(f"chassis {frac(self.loop)}")
        n = int(self.feat.get("d_rings", 0))
        if n:
            web_total += n * 4
            parts.append(f"{n} tabs at 4\"")
        if self.feat.get("handle_in"):
            hl = F(str(self.feat["handle_in"]))
            web_total += hl
            parts.append(f"handle {frac(hl)}")
        if web_total:
            out.append({"item": f"{frac(self.web)} nylon webbing",
                        "qty": frac(web_total),
                        "note": " + ".join(parts)
                                + ("  (the belt and the strap are yours)"
                                   if self.wearer and not self.makes_belt
                                   else "  (straps and belt are extra)")})
        if self.loops and self.wearer and not self.makes_belt:
            out.append({"item": f"{frac(self.loop_for)} belt — YOURS, not made here",
                        "qty": "1",
                        "note": f"the keepers are cut for {frac(self.loop_for)}; "
                                "wider will not thread and narrower rattles. It "
                                f"has to close round a {frac(self.waist[0])}–"
                                f"{frac(self.waist[1])} waist with the bag on it"})
        if self.wearer and self.has_sling and not self.makes_strap:
            out.append({"item": "Shoulder strap — YOURS, not made here",
                        "qty": "1",
                        "note": f"clips to the two D-rings; about "
                                f"{frac(self.crossbody)} for crossbody wear. Bring "
                                "its own snap hooks — the bag supplies the rings "
                                "and nothing else"})
        if self.loops and self.wearer and self.makes_belt:
            fit = (f"{frac(self.waist[0])}–{frac(self.waist[1])} waist"
                   + ("" if self.has_sling
                      else f", or {frac(self.crossbody)} crossbody"
                      if self.crossbody else ""))
            out.append({"item": f"{frac(self.loop_for)} nylon webbing, belt",
                        "qty": frac(self.belt_cut),
                        "note": f"{fit}, plus {frac(self.belt_takeup)} lost to the "
                                f"buckle fold and the tri-glide, plus "
                                f"{frac(self.belt_tail)} of tail. Derived from the "
                                "declared fit range, so it moves when the bag or "
                                "the wearer does"})
        if self.wearer and self.has_sling and self.makes_strap:
            out.append({"item": f"{frac(self.loop_for)} nylon webbing, sling strap",
                        "qty": frac(self.sling_cut),
                        "note": f"{frac(self.crossbody)} crossbody plus "
                                f"{frac(self.sling_takeup)} lost to two hook folds "
                                "and the tri-glide. Clips to the D-rings, so the "
                                "belt and the sling stay rigged at once"})
        for h in self.spec.get("hardware", []):
            out.append({"item": h["item"], "qty": str(h.get("qty", "")),
                        "note": h.get("note", "")})
        return out

    def thickness(self) -> list[dict]:
        """The stack at every seam that has one, from the material table.

        Not copied from any pattern document. An earlier hand-written budget
        quoted 4.4 mm for the D-ring tack -- correct when the gusset was
        Cordura, and 0.25 mm stale the moment the shell became denim.
        """
        rows = [("Gusset-to-zip lap join", "2 x shell", 2 * self.shell_mm),
                ("Zipper topstitch", "shell + zip tape", self.shell_mm + ZIP_TAPE_MM)]
        # The single-panel seam only belongs here if the bag actually has one.
        # Listing a 2.0 mm "plain bound seam" on a bag whose every panel is
        # doubled reports a seam nobody will sew, and it reads as the easy
        # number when the real one is half a millimetre thicker.
        if any(n == 1 for n in self.panel_layers.values()):
            rows.append(("Plain bound seam",
                         "panel + gusset, right sides together",
                         self.seam_mm))
            rows.append(("Mitred corner", "binding doubles", self.corner_mm))
        for face in ("front", "back"):
            n = self.panel_layers[face]
            if n > 1:
                rows.append((f"Bound seam, {face} panel",
                             f"{n} x panel + gusset",
                             self.panel_seam_mm[face]))
                rows.append((f"Mitred corner, {face} panel", "binding doubles",
                             self.panel_seam_mm[face]
                             ))
        # Every square corner at the TOP of a panel is also a gusset lap join --
        # the construction says so outright ("Both joins land at the top
        # corners, which is also where the binding will mitre") -- so the
        # thickest seam on the bag is a mitre with a lapped zip strip in it,
        # and the plain mitre figure is the one nobody actually sews there.
        worst_corner = max([self.corner_mm] + list(self.panel_corner_mm.values()))
        rows.append(("Mitred corner over a gusset lap join",
                     "the mitre + the lapped zipper strip",
                     worst_corner + self.shell_mm))
        if self.has_divider:
            rows.append(("Divider channel topstitch", "divider + panel",
                         2 * self.shell_mm))
        if self.has_chassis:
            rows.append(("Chassis topstitch", "webbing + shell",
                         WEBBING_MM + self.shell_mm))
            rows.append(("Chassis overlap box-X", "2 x webbing + shell",
                         2 * WEBBING_MM + self.shell_mm))
        if self.has_panel_pocket:
            rows.append(("Panel pocket zip topstitch", "panel + zip tape",
                         self.shell_mm + ZIP_TAPE_MM))
            # The pocket zip spans the panel's full CUT width, so both of its
            # tape ends finish inside the side binding. Four places per bag,
            # and none of them were in this table.
            if any(q.placket for q in self.pockets.values()):
                rows.append(("Pocket zip lap, under the placket",
                             "panel + placket + zip tape",
                             2 * self.shell_mm + ZIP_TAPE_MM))
            rows.append(("Side binding over a pocket zip end",
                         "the bound seam + zip tape",
                         max(self.panel_seam_mm.values()) + ZIP_TAPE_MM))
        if self.loops:
            rows.append(("Belt keeper box-X",
                         "keeper + panel + anchor" if self.loop_anchor
                         else "keeper + panel",
                         (3 if self.loop_anchor else 2) * self.shell_mm))
        # A tab is two layers of webbing folded through the ring. What is behind
        # it is either the chassis (another webbing) or a shell-fabric anchor.
        behind = WEBBING_MM if self.has_chassis else self.shell_mm
        tack = 2 * WEBBING_MM + self.shell_mm + behind
        backing = "internal webbing" if self.has_chassis else "anchor strip"
        if self.flags["has_ring_anchor"]:
            # Both ends of every anchor strip finish flush with the panel
            # edges on purpose, so the bindings catch them -- which puts one
            # more layer in the bound seam at 2 places per ring.
            rows.append(("Side binding over a ring-anchor end",
                         "the bound seam + the anchor strip",
                         max(self.panel_seam_mm.values()) + self.shell_mm))
        if self.flags["has_drings"]:
            rows.append(("D-ring tab box-X",
                         f"doubled tab + shell + {backing}", tack))
        if self.flags["has_handle"]:
            rows.append(("Grab handle box-X",
                         f"doubled end + shell + {backing}", tack))
        return [{"location": a, "stack": b, "mm": round(c, 2)} for a, b, c in rows]

    def peak_mm(self) -> float:
        return max(r["mm"] for r in self.thickness())

    # -- assembly load -----------------------------------------------------
    #: Steps that legitimately have no drawing: there is nothing spatial to
    #: show. Declared, so that a step which merely got MISSED is a failure
    #: rather than an assumed exemption.
    NO_FIGURE = {
        "Pre-wash and dry the shell",
        "Finish the inside allowances",

        "Base stiffener, loose",
    }

    def figure_gaps(self, construction: dict) -> list[str]:
        """Steps with no figure and no declared reason to lack one.

        A step describes an operation in space, and prose alone asks the reader
        to build the picture. Every drawing here is either generated from this
        bag's own geometry or embedded from the technique note that owns it --
        never redrawn per bag, because a hand-drawn "2 5/16 strip" is wrong the
        first time the bag is resized and nothing would catch it.
        """
        return [st["title"] for st in self.assembly(construction)
                if not st.get("figures") and st["title"] not in self.NO_FIGURE]

    def assembly_load(self) -> list[dict]:
        """What this bag actually costs to sew, counted rather than felt.

        Ease of assembly was the one design goal with no number behind it, so
        every decision that added a seam got judged on the feature it bought
        and never on the seam. These are the counts that matter, in the order
        they hurt: a mitred corner is the thickest point on the bag and has to
        be hand-wheeled, a binding run is the seam that shows, and a zip lap is
        two rows through tape with a zipper foot.
        """
        rows = []
        perims = 2                                   # front and back panels
        curves = self.curved_corners * perims
        rows.append({"item": "Panel seams", "count": perims,
                     "note": f"{frac(self.ring)} each, right sides together at "
                             f"{frac(self.sa)} — then the bag turns through the zip"})
        if curves:
            rows.append({"item": "Relief clips", "count": self.relief_clips * curves,
                         "note": f"{self.relief_clips} per curve, each cut to "
                                 f"{frac(self.clip_depth)} — an eighth SHORT of the "
                                 "stitch line, or the stitching pulls out"})
        if self.square_corners:
            rows.append({"item": "Corners to trim", "count": self.square_corners * perims,
                         "note": "allowance cut back across the point so it turns out "
                                 "flat instead of bunching"})
        nzip = 1 + len(self.pockets)
        rows.append({"item": "Zippers", "count": nzip,
                     "note": f"{2 * nzip} laps at two rows each = {4 * nzip} rows on "
                             f"tape, plus {1 + 2 * len(self.pockets)} new bar-tacked stops"})
        rows.append({"item": "Lap joins", "count": 2,
                     "note": "gusset to zipper panel, both at the top corners"})
        # A keeper is tacked at BOTH ends -- webbing-hardware.md step 5, and
        # the assembly step says so too. One per keeper undercounted every
        # belted bag in the family.
        tacks = (2 * self.loop_count if self.loops else 0) \
            + int(self.feat.get("d_rings", 0)) + (2 if self.flags["has_handle"] else 0)
        if self.has_chassis:
            tacks += 2
        rows.append({"item": "Box-X tacks", "count": tacks,
                     "note": "twice round each, hand-wheeled"
                             + (f" — {2 * self.loop_count} of them are the "
                                "keepers, both ends of each" if self.loops else "")})
        runs = 0
        if self.has_divider:
            runs += len(self.div_channels) + (3 if self.div_attach == "topstitch" else 0)
        if self.flags["has_ring_anchor"]:
            runs += 2 * int(self.feat["d_rings"])
        if self.flags["has_belt_anchor"]:
            runs += 2
        if self.has_chassis:
            runs += 2
        rows.append({"item": "Straight topstitch runs", "count": runs,
                     "note": "anchors, dividers and channels — the easy seams"})
        return rows

    def zipper_schedule(self) -> list[dict]:
        """Every zipper on this bag, in the order it has to be built.

        The technique note explains how to lap a zipper; it cannot say how long
        THIS one is. Hand-writing that per bag is exactly the stale-figure
        failure the rest of this repo exists to prevent -- the opening is
        derived from the ring, the pocket openings from the panel, and all three
        move whenever the bag is resized.

        Order matters and is not obvious. Sliders go on before either end is
        stopped, and a two-slider run cannot be retro-fitted once the panel is
        built round it.
        """
        rows = []
        # Chain is cut to span + 1": half an inch of tape past each new stop, so
        # the stop has cloth behind it and the cut end can be capped. Buying is
        # a separate question -- chain comes off a roll but a made-up zipper
        # comes in stock lengths, so round UP to one and shorten it.
        STOCK = (6, 8, 9, 10, 12, 14, 16, 18, 20, 22, 24, 30, 36)

        def buy_for(chain: F) -> str:
            for n in STOCK:
                if F(n) >= chain:
                    return f'{n}"'
            return f'{frac(chain)} — longer than stock; buy chain by the yard'

        def row(where, span, sliders, stops, note):
            chain = span + F(1)
            rows.append({"zip": where, "span": frac(span), "chain": frac(chain),
                         "buy": buy_for(chain), "sliders": sliders,
                         "stops": stops, "note": note})

        # The main run. Its opening is the stitch-line width, because the ends
        # are lapped over by the gusset -- not the cut length of the strip.
        row("Main opening", self.zip_cut, self.main_sliders,
            "2 new stops, one at each end of the opening",
            f"the tape runs the full {frac(self.zip_cut)} of the zipper panel so the "
            f"gusset laps over it at both ends, but the OPENING is only "
            f"{frac(self.zip_face)} — the stitch-line width — so the stops go "
            f"{frac(self.lap)} in from each end of the strip. "
            + (f"{self.main_sliders} sliders, noses OUTWARD, and both go on the "
               "chain BEFORE the panel is built round it"
               if self.main_sliders > 1 else "single slider"))

        for face, pk in self.pockets.items():
            across = "ACROSS" if pk.axis == "top" else "DOWN"
            # upper/lower are the two piece widths whichever way the panel
            # splits; only the NAMES change with the axis.
            near, far = frac(pk.upper), frac(pk.lower)
            n1, n2 = pk.pieces
            full = pk.starts in (None, F(0))
            art = "an" if n1[0] in "aeiou" else "a"
            note = (f"runs {across} the panel; the outer splits into {art} {n1} of "
                    f"{near} and a {n2} of {far}, each lapped {frac(pk.lap)} onto "
                    f"the tape. ")
            if full:
                note += ("Both ends finish inside the seam allowance and get bound "
                         "over, so BOTH stops are bar-tacked just inside the stitch "
                         "line and no metal stop may stay there")
            else:
                note += (f"It stops {frac(pk.starts)} short, so the two outer pieces "
                         f"lap onto EACH OTHER above the run: that end's stop is a "
                         f"bar-tack in open panel, the other is bound over")
            if pk.placket:
                note += (f". A {frac(pk.placket['cut'])} placket is caught in the "
                         f"{n1} piece's own lap and hangs {frac(pk.placket['show'])} "
                         "free over the coil")
            row(f"{face.title()} pocket", pk.run, 1,
                "2 new stops, both bar-tacked", note)
        return rows

    # -- comfort -----------------------------------------------------------
    def pocket_interior(self, face: str) -> tuple[F, F] | None:
        """Usable inside of a panel pocket: between the stitch lines.

        NOT the cut piece. The cavity runs to the panel's edge but the outer
        seam allowance is caught in the binding, so it is not interior depth --
        and that 3/8" is the difference between a phone fitting and not.
        """
        pk = self.pockets.get(face)
        if pk is None:
            return None
        # `reach` is always measured along the axis the zip splits, so a
        # vertical zip's usable rectangle is the OTHER way round: the run from
        # the opening to the far binding, by the full face height.
        if pk.axis == "top":
            return (self.face_w, pk.reach - self.sa)
        return (pk.reach - self.sa, self.face_h)

    def pocket_depth_for(self, face: str, width) -> F:
        """How deep a thing of that width can actually sit, given the curve.

        A rounded bottom corner takes the corners off the pocket too, so the
        rectangle the cut list implies is optimistic. Small here -- 0.008" --
        but it scales with the radius and with how wide the item is, and it is
        the difference nobody would think to look for.
        """
        pk = self.pockets.get(face)
        if pk is None:
            return F(0)
        pw, pd = self.pocket_interior(face)
        r = self.corner_r
        if not r:
            return pd
        half = (pw - F(str(width))) / 2
        if half >= r:
            return pd
        inner = float(r) - float(half)
        dy = math.sqrt(max(float(r) ** 2 - inner ** 2, 0.0))
        return min(pd, floor_to(pd - r + F(str(round(dy, 6))), 16))

    def comfort(self) -> list[dict]:
        """Figures from the load-carriage literature, REPORTED not enforced.

        None of these is a gate. The threshold that matters -- 16 kPa, where
        contact pressure starts to occlude capillary blood flow -- depends on
        the belt tension the wearer actually applies, and this repo has not
        measured that on anybody. What CAN be stated without inventing a number
        is the tension at which a belt of this width reaches that threshold,
        which is a property of the belt and the body and nothing else.

        The rule from `docs/16` applies in full: practitioner and literature
        sourced, not yet worn by anyone here.
        """
        rows = []
        vol = self.interior()["litres"]
        rows.append({
            "measure": "Capacity",
            "value": f"{vol} L",
            "basis": "1–3 L across the fourteen hip packs OutdoorGearLab tested; "
                     "the band this size of bag actually lives in"})
        if self.loops and self.wearer:
            w_m = float(self.loop_for) * MM_PER_IN / 1000.0
            # Smallest declared waist is the worst case: pressure goes as 1/R.
            r_m = float(self.waist[0]) * MM_PER_IN / 1000.0 / (2 * math.pi)
            occl = OCCLUSION_KPA * 1000.0 * r_m * w_m
            rows.append({
                "measure": "Belt tension at blood occlusion",
                "value": f"{occl:.0f} N  ({occl / 9.80665:.1f} kgf)",
                "basis": f"16 kPa over a {frac(self.loop_for)} belt on a "
                         f"{frac(self.waist[0])} waist, the smallest declared. "
                         "Pressure goes as 1/width, so this is the number a "
                         "wider belt buys you"})
            taper = self.taper * self.loop_for
            rows.append({
                "measure": "Circumference the belt gets wrong",
                "value": frac(taper),
                "basis": f"the waist is a truncated cone, gaining about "
                         f"{frac(self.taper)} of girth per inch of drop. A flat "
                         "strap is the same length top and bottom, so it is out "
                         "by this much and wants to ride. Cutting a belt curved "
                         "fixes it; webbing cannot be cut curved"})
        rows.append({
            "measure": "Hip vs shoulder pressure tolerance",
            # Half-up on the DECIMAL value. 2.135 is not representable in
            # binary -- it is 2.13499999... -- so both format() and a
            # floor(x*100 + 0.5) dodge round it DOWN to 2.13, against the 2.14
            # the source and every note in this repo quote. Fraction(str(x)) is
            # exact, and this file is already a Fraction file.
            "value": f"{float((F(str(HIP_TOLERANCE_RATIO)) * 100 + F(1, 2)) // 1) / 100:.2f}×",
            "basis": "p_hip = 2.135 × p_shoulder + 18.75 for equal discomfort. "
                     "The hip is the forgiving half of the body, which is why an "
                     "unpadded hip pack is bearable and an unpadded shoulder "
                     "strap is not"})
        if self.pockets and self.wearer:
            side = "left" if self.handed == "right" else "right"
            rows.append({
                "measure": "Pocket sliders park",
                "value": f"at the wearer's {side}",
                "basis": f"a belt bag's zip should open away from the centre of "
                         f"the body toward the dominant hand, so a {self.handed}-"
                         f"handed wearer pulls it {self.handed}ward. Invisible "
                         "until the bag is finished and unfixable after"})
        for face in sorted(self.pockets):
            pw, pd = self.pocket_interior(face)
            rows.append({
                "measure": f"{face.capitalize()} pocket, usable inside",
                "value": f"{frac(pw)} × {frac(pd)}  "
                         f"({float(pw) * MM_PER_IN:.0f} × {float(pd) * MM_PER_IN:.0f} mm)",
                "basis": "between the stitch lines: the sides and bottom are "
                         "caught in the panel's binding, so the seam allowance "
                         "is not usable depth"})
        # Padding, and why there is none. The seam is the reason, and it is
        # arithmetic rather than an opinion.
        pad = max(self.sandwich_mm, *self.panel_sandwich_mm.values())             + 2 * 6.0
        rows.append({
            "measure": "Seam if the back panel were padded",
            "value": f"{pad:.1f} mm",
            "basis": f"6 mm of EVA is the usual back-panel figure. Through this "
                     f"construction's seam that is {pad:.1f} mm against a "
                     f"{STACK_STOP_MM:g} mm stop — a pad here has to float clear "
                     "of the seam or not exist"})
        return rows

    # -- the 3D model ------------------------------------------------------
    def face_size(self, face: str) -> tuple[F, F]:
        """(width, height) of a face in inches, viewed straight on."""
        return {"front": (self.W, self.H), "back": (self.W, self.H),
                "left": (self.D, self.H), "right": (self.D, self.H),
                "top": (self.W, self.D), "bottom": (self.W, self.D)}[face]

    def model3d(self) -> dict:
        feats = []
        # The zipper and the chassis are DERIVED, never declared. Re-declaring
        # them would let the drawing disagree with the cut list, and the whole
        # point of the coil sitting off-centre is a relationship between two
        # numbers this class already holds.
        feats.append({"kind": "zip", "derived": True, "face": "top",
                      "u": 0.0, "v": float(self.coil_c - self.sa
                                             - self.coil / 2),
                      "w": float(self.zip_face), "h": float(self.coil),
                      "label": f"coil, {frac(self.coil_c)} from the cut edge"})
        for face, pk in sorted(self.pockets.items()):
            if pk.axis == "top":
                z = {"u": 0.0,
                     "v": float(pk.zip - self.sa - pk.coil / 2),
                     "w": float(self.face_w), "h": float(pk.coil)}
                where = "down from the top"
            else:
                _fw, _fh = self.face_size(face)
                _v = float(pk.starts - self.sa)
                z = {"u": float(pk.zip - self.sa - pk.coil / 2),
                     "v": _v,
                     "w": float(pk.coil), "h": float(_fh) - _v}
                where = "in from the side"
            feats.append({"kind": "zip", "derived": True, "face": face,
                          **z, "label": f"{face} pocket, {frac(pk.zip)} {where} "
                                        "of the panel's cut edge"})
            if pk.placket:
                # Drawn where it hangs, over the coil, on the far side of it.
                if pk.axis == "top":
                    pf = {"u": 0.0,
                          "v": float(pk.zip - self.sa - pk.coil / 2),
                          "w": float(self.face_w),
                          "h": float(pk.coil + pk.placket["show"])}
                else:
                    _fw, _fh = self.face_size(face)
                    _v = float(pk.starts - self.sa)
                    pf = {"u": float(pk.zip - self.sa - pk.coil / 2),
                          "v": _v,
                          "w": float(pk.coil + pk.placket["show"]),
                          "h": float(_fh) - _v}
                # NOT kind "patch". `patch` is POINT-like -- the player draws
                # it as a fixed 1 x 1 inch square centred on u,v, and
                # NOMINAL_IN measures it the same way -- so a 1 x 5 1/8 inch
                # flap rendered as a small square and looked like nothing at
                # all. A placket has a real extent and needs a kind that keeps
                # it.
                feats.append({"kind": "placket", "derived": True, "face": face,
                              **pf,
                              "label": f"placket — {frac(pk.placket['show'])} of "
                                       "flap hanging free over the coil"})
        if self.has_chassis:
            feats.append({"kind": "webbing", "derived": True, "ring": True,
                          "across_depth_in": float(TURN_IN + self.web_lo),
                          "width_in": float(self.web),
                          "overlap_in": float(self.overlap),
                          "label": f"{frac(self.loop)} chassis loop, inside the gusset"})
        if self.has_divider:
            # Draw the divider that is actually built. Caught in the binding it
            # runs the panel's full cut width and reaches the bottom edge;
            # topstitched it is div_inset clear of the binding on three sides,
            # which is 1 3/8" narrower and 5/8" up from the bottom. The model
            # used to draw the bound version whatever the spec said.
            fw, fh = self.face_size(self.div_face)
            if self.div_attach == "topstitch":
                inset = self.sa + self.div_inset
                du, dw, dh = inset, self.div_w, self.div_h
                dv = fh - inset - self.div_h
            else:
                # Caught in the panel seam, so on the face it shows the
                # FINISHED width -- the allowance is inside.
                du, dw, dh = F(0), fw, self.div_h - self.sa
                dv = fh - dh
            feats.append({"kind": "pocket", "derived": True, "face": self.div_face,
                          "u": float(du), "v": float(dv),
                          "w": float(dw), "h": float(dh),
                          "interior": True,
                          "label": f"divider pocket, {frac(self.div_depth)} deep"
                                   + (f", {len(self.div_channels) + 1} channels"
                                      if self.div_channels else "")})
        for ft in self.spec.get("features", {}).get("placements", []):
            feats.append(dict(ft))
        return {
            "faces": {f: {"w": dim(self.face_size(f)[0]),
                          "h": dim(self.face_size(f)[1])} for f in FACES},
            "seam_allowance": dim(self.sa),
            # The faces here are FINISHED sizes, so the radius the preview has
            # to draw is the finished outline's -- the stitch line's radius one
            # flange further out. corner_cut_r is a cutting figure and belongs
            # in the cut list, which is where it already is.
            "corner_radius": dim(self.corner_r if self.corner_r
                                 else F(0)),
            "features": feats,
        }

    def _placement_rect(self, ft: dict) -> tuple[float, float, float, float] | None:
        """(u, v, w, h) in inches, or None if the feature is not face-bound."""
        k = ft.get("kind")
        if ft.get("ring") or "face" not in ft:
            return None
        if k == "handle":
            u0, u1 = float(ft["from"]), float(ft["to"])
            return (min(u0, u1), 0.0, abs(u1 - u0), 0.0)
        if k in NOMINAL_IN:
            w, h = NOMINAL_IN[k]
            return (float(ft["u"]) - w / 2, float(ft["v"]) - h / 2, w, h)
        if k == "rib":
            return (float(ft["u"]), 0.0, float(ft["w"]), 0.0)
        return (float(ft["u"]), float(ft["v"]),
                float(ft.get("w", 0)), float(ft.get("h", 0)))

    # -- checks ------------------------------------------------------------
    def checks(self) -> list[tuple[bool, str, str]]:
        out = []

        def ck(ok, name, detail):
            out.append((bool(ok), name, detail))

        # NOT "gusset_face + zip_face == ring". gusset_face is DEFINED as
        # ring - zip_face two hundred lines up, so that check could only ever
        # pass -- exactly the worthless-check shape SCHEMA.md warns about, and
        # it sat here while the two pieces were both cut long and the ring came
        # out 2 x lap over. Test what gets CUT, against what gets lapped away.
        # Plain seams now: each of the two joins eats an allowance from
        # BOTH pieces, so four in all.
        closes = self.gusset_cut + self.zip_cut - 4 * self.sa
        ck(closes == self.ring, "the cut pieces close the ring",
           f"gusset {frac(self.gusset_cut)} + zip panel {frac(self.zip_cut)} "
           f"- 2 laps of {frac(self.lap)} = {frac(closes)}"
           + ("" if closes == self.ring
              else f", but the panels need {frac(self.ring)}"))

        # Each strip shows its cut width less the seam, plus the tape
        # reveal beside the coil that the fold does not cover.
        finished = ((self.strip_front - self.lap + self.reveal)
                    + self.coil
                    + (self.strip_rear - self.lap + self.reveal))
        ck(finished == self.gusset_w, "zipper panel width matches the gusset",
           f"{frac(finished)} vs {frac(self.gusset_w)}")

        ck(self.face_d > 0 and self.face_w > 0 and self.face_h > 0,
           "faces are positive",
           f"{frac(self.face_w)} x {frac(self.face_h)} x {frac(self.face_d)}")

        # A turned bag has no binding to check. What it does have is a seam
        # allowance that must survive being clipped: relief cuts stop 1/8"
        # short of the stitch line, so an allowance under 1/4" leaves nothing
        # to clip into and the curve cannot splay.
        ck(self.sa >= F(1, 4), "the seam allowance can take a relief clip",
           f"{frac(self.sa)} allowance, clipped to {frac(self.clip_depth)} — "
           f"a snip that stops 1/8\" short of the stitch line")
        ck(self.visible_w > 0 and self.visible_h > 0,
           "artwork clears the seam",
           f"{frac(self.visible_w)} x {frac(self.visible_h)} inside a "
           f"{frac(SEAM_MARGIN_IN)} margin")

        # A turned seam is only the pieces meeting in it, so the worst point on
        # the bag is wherever the most layers coincide -- no binding doubling
        # it and no mitre doubling it again.
        worst_seam = max(self.panel_seam_mm.values())
        thick = [f"{f} at {k} layers" for f, k in sorted(self.panel_layers.items())
                 if k > 1]
        where = f" ({', '.join(thick)})" if thick else ""
        ck(worst_seam <= STACK_WARN_MM, "the worst seam is drivable",
           f"{worst_seam:.1f} mm{where} (warn above {STACK_WARN_MM:g})")
        if self.shell_frays:
            ck(True, "shell frays: raw edges need folding",
               "zip laps, rib edges, pocket tops, gusset joins")

        ck(self.coil_c - self.coil / 2 - self.sa >= F(1, 4),
           "coil clears the seam",
           f"{frac(self.coil_c - self.coil / 2 - self.sa)} of visible shell outboard")

        if self.has_chassis:
            gap = self.web_lo - (self.coil_c + self.coil / 2)
            ck(gap >= F(1, 8), "coil clears the webbing",
               f"gap {frac(gap)} (want 1/8\" or more)")
            tail = (self.loop - self.gusset_face) / 2
            ov = 2 * tail - self.zip_face
            ck(ov > 0, "chassis overlap lands on the top face", f"{frac(ov)} of overlap")
            ck(self.overlap >= 3 * self.web,
               "overlap is at least 3x the webbing width",
               f"{frac(self.overlap)} vs {frac(3 * self.web)}")

        for face, pk in self.pockets.items():
            # The same reassembly test the gusset's zipper panel gets, and for
            # the same reason: two strips lapped onto a tape either add back up
            # to the piece they replaced or the panel comes out the wrong size.
            rebuilt = ((pk.upper - pk.lap + pk.reveal) + pk.coil
                       + (pk.lower - pk.lap + pk.reveal))
            ck(rebuilt == pk.span, f"{face} pocket reassembles to the panel",
               f"{frac(rebuilt)} vs {frac(pk.span)} "
               + ("(height, zip across)" if pk.axis == "top"
                  else "(width, zip down)"))
            near = min(pk.zip, pk.span - pk.zip) - pk.coil / 2
            ck(near - self.sa >= F(1, 4), f"{face} pocket coil clears the seam",
               f"{frac(near - self.sa)} of visible shell to the nearest edge")
            ck(pk.reach >= 2, f"{face} pocket is deep enough to hold anything",
               f"{frac(pk.reach)} "
               + ("below" if pk.axis == "top" else "beyond") + " the opening")
            ck(self.panel_layers[face] >= 2, f"the {face} pocket is a sealed space",
               f"inner panel {frac(self.panel_w)} × {frac(self.panel_h)}, bound on "
               "all four edges — the zip opens into the cavity, never into the bag")
            if pk.must_hold:
                a, b = sorted(F(str(x)) for x in pk.must_hold)
                pw, _ = self.pocket_interior(face)
                # Curve-aware: the usable depth depends on how wide the item is,
                # because a rounded bottom corner pinches in at the bottom.
                pd = self.pocket_depth_for(face, b)
                fits = (a <= pd and b <= pw) or (b <= pd and a <= pw)
                ck(fits, f"{face} pocket holds what it must",
                   f"{frac(pw)} × {frac(pd)} inside for a {frac(b)} × {frac(a)} "
                   f"item — {frac(pd - a)} of depth to spare" if fits else
                   f"{frac(pw)} × {frac(pd)} inside cannot take {frac(b)} × {frac(a)}")

        if len(self.pockets) > 1:
            # NOT a failure when they differ on purpose. Two pockets built
            # the same way cut as pairs and one step states both; built
            # differently they are four singletons and two steps, which is a
            # real cost and the reason to be told -- but hiding a back zip by
            # turning it while the front stays put is a legitimate reason to
            # pay it. What must never differ silently is the coil or the lap,
            # because those are the zipper you buy.
            axes = {f: pk.axis for f, pk in self.pockets.items()}
            hard = {(pk.coil, pk.lap) for pk in self.pockets.values()}
            ck(len(hard) == 1, "panel pockets share a zipper",
               f"one #{frac(self.bp_coil)} coil and a {frac(self.bp_lap)} lap "
               "throughout, so every pocket takes the same zipper off the same "
               "reel" if len(hard) == 1 else
               "the coil or the lap differs between pockets, so they are not "
               "the same zipper: " + str(hard))
            same = len({pk.key() for pk in self.pockets.values()}) == 1
            ck(True, "panel pockets cut as pairs" if same else
               "panel pockets are built differently, by declaration",
               "identical outer pieces front and back, so they cut as pairs and "
               "one step states them all" if same else
               f"{axes} — four singleton outer pieces instead of two pairs, and "
               "an assembly step each. Declared, not accidental")

        if self.corner_r:
            # A turned corner wants a radius it can actually turn out. Below
            # about a seam allowance the allowance bunches inside the curve and
            # the corner comes out lumpy however carefully it is clipped.
            ok_r = self.corner_r >= self.sa
            ck(ok_r, "the corner radius turns out cleanly",
               f"{frac(self.corner_r)} radius against a {frac(self.sa)} "
               "allowance" + ("" if ok_r else " — the allowance will bunch "
                              "inside the curve"))
            lim = min(self.face_w, self.face_h) / 2
            ck(self.corner_r <= lim, "the corner radius leaves a straight run",
               f"{frac(self.corner_r)} of a {frac(lim)} maximum — beyond half the "
               "shorter face the curves meet and there is no flat edge left")
            # Round a convex curve the gusset's raw edge has to reach further
            # than its own stitch line, and relief clips are what let it. The
            # shortfall is (pi/2) x the seam allowance per quarter turn -- the
            # same at any radius, but a tighter corner asks for it in less room,
            # which is why the clips are spaced about an allowance apart.
            reach = round_to(self.sa * F(31416, 20000), 16)
            arc = round_to(self.corner_r * F(31416, 20000), 16)
            ck(self.relief_clips >= 3, "the curve gets enough relief clips",
               f"{self.relief_clips} clips over {frac(arc)} of arc, each cut to "
               f"{frac(self.clip_depth)} — between them they open the {frac(reach)} "
               "the raw edge is short by")

        if self.has_divider:
            # A divider caught in the panel seam has to be cut round any rounded
            # corner it reaches into; topstitched clear of it, it does not.
            # NOT a refusal. Cutting a piece round the corner template is
            # something this pattern already does four times over, and reusing
            # a seam that is being sewn anyway beats adding three straight runs
            # to avoid it. What has to be true is that the divider's corners
            # MATCH the panel's -- cut it square and it overhangs the curve
            # into the seam, which is the one place it must not be.
            if self.corner_r:
                want = (self.corner_cut_r if self.div_attach == "seam"
                        else max(F(0), self.corner_r - self.div_inset))
                ck(self.div_r == want,
                   "the divider's corners follow the panel's",
                   f"cut it round a {frac(self.div_r)} radius — "
                   + ("its edges are the panel's cut edges, so it is the same "
                      "template the panels use" if self.div_attach == "binding"
                      else f"the stitch line's {frac(self.corner_r)} less the "
                           f"{frac(self.div_inset)} inset"))
            # It has to stop short of the mouth or you cannot get past it to
            # reach the main compartment at all.
            ck(self.div_clear >= 1, "the divider leaves room to reach past it",
               f"{frac(self.div_clear)} of open panel above it")
            ck(self.div_depth >= 2, "the divider pocket is deep enough to hold",
               f"{frac(self.div_depth)} deep")
            face_w = self.face_size(self.div_face)[0]
            edge = self.channel_edge()
            widths = self.channel_widths()
            bad = [frac(w) for w in widths if w < 1]
            ck(not bad, "every divider channel is wide enough to use",
               ", ".join(bad) + " — a channel narrower than 1\" holds nothing"
               if bad else
               f"{len(widths)} channel(s): " + " · ".join(frac(w) for w in widths)
               + f", measured across the {frac(self.div_w)} divider")
            inside = all(edge < c < face_w - edge for c in self.div_channels)
            ck(inside, "divider channels land on the divider",
               f"{len(self.div_channels)} line(s) between {frac(edge)} and "
               f"{frac(face_w - edge)}" if inside else
               "a line outside the divider stitches the panel to nothing")

            # A channel line is topstitched through the panel, so it SHOWS on
            # the outside -- and on this family the outside of a panel is where
            # the embroidery goes. Unless that panel carries a pocket, in which
            # case the divider lies against the INNER layer and the stitching
            # never reaches the outside at all.
            logo = next((f for f in self.spec.get("features", {}).get("placements", [])
                         if f.get("kind") == "logo" and f.get("face") == self.div_face),
                        None)
            if logo and self.div_channels and self.div_face not in self.pockets:
                lo, hi = F(str(logo["u"])), F(str(logo["u"])) + F(str(logo["w"]))
                clash = [frac(c) for c in self.div_channels if lo <= c <= hi]
                ck(not clash, "divider channels clear the embroidery field",
                   ", ".join(clash) + f" crosses the field at {frac(lo)}–{frac(hi)}"
                   if clash else
                   f"nearest line is {frac(min(min(abs(c - lo), abs(c - hi)) for c in self.div_channels))} clear")
            elif self.div_channels:
                ck(True, "divider channels are hidden by the outer layer",
                   f"the {self.div_face} panel carries a pocket, so the channel "
                   "stitching goes through the inner layer only and nothing "
                   "shows outside")

        if self.loops:
            if self.has_back_pocket:
                # Open the pocket zip and the outer layer is two loose pieces.
                # A keeper below the zip line would hang the loaded bag off the
                # lower one, whose only attachment upward IS the zipper. Above
                # it, the tack passes through to the inner panel, which the
                # gusset ring holds on all four edges. This is checkable because
                # the placements are declared: it is where they sit that decides
                # whether the zip is in the load path.
                bp = self.pockets["back"]
                loops = [ft for ft in self.spec.get("features", {}).get("placements", [])
                         if ft.get("kind") == "belt-loop" and ft.get("face") == "back"]
                lo = TURN_IN + bp.zip - bp.coil / 2
                hi = lo + bp.coil
                if bp.axis == "top":
                    # A horizontal zip leaves the LOWER piece hanging from the
                    # coil when it is open, so nothing loaded may tack into it.
                    bad = [ft for ft in loops
                           if F(str(ft["v"])) + F(str(ft.get("h", 0))) > lo]
                    ck(not bad, "belt load bypasses the pocket zip",
                       f"{len(bad)} keeper(s) reach below the zip at {frac(lo)}"
                       if bad else
                       "every keeper sits above the zip line, so the tack goes "
                       "through to the inner panel and the zip carries nothing")
                else:
                    # A vertical zip leaves BOTH pieces caught in the binding
                    # along their own outer edge, so neither hangs from the
                    # coil. What matters instead is that no keeper STRADDLES
                    # the opening -- a tack across it would sew the pocket shut
                    # and put the belt on the zipper at the same time.
                    bad = [ft for ft in loops
                           if F(str(ft["u"])) < hi
                           and F(str(ft["u"])) + F(str(ft.get("w", 0))) > lo]
                    ck(not bad, "belt load bypasses the pocket zip",
                       f"{len(bad)} keeper(s) straddle the zip at "
                       f"{frac(lo)}–{frac(hi)}" if bad else
                       f"the zip runs down the panel at {frac(lo)}–{frac(hi)} and "
                       "every keeper clears it, so no tack crosses the opening — "
                       "and neither outer piece hangs from the coil, because both "
                       "are caught in the binding along their own outer edge")

            ck(self.loop_w >= self.loop_for, "keepers are wide enough for the belt",
               f"{frac(self.loop_w)} keeper on a {frac(self.loop_for)} belt")
            # A keeper is not a flat span. It folds under at each end, carries a
            # box-X footprint at each end, and has to arch over the belt's own
            # thickness twice. `2 x belt + 1 1/2` is a rule of thumb; this is
            # what the rule has to cover, and the difference is trim allowance.
            ck(self.loop_len >= self.keeper_min,
               "keepers are long enough to fold, tack and arch",
               f"{frac(self.loop_len)} cut against {frac(self.keeper_min)} needed "
               f"— {frac(self.loop_len - self.keeper_min)} to trim after fitting "
               "it round the real belt")
            if self.has_back_pocket:
                # The keepers live on the upper back piece, between its seam
                # allowance and its lap onto the pocket zip tape. That band is
                # all the material there is to tack into.
                bp = self.pockets["back"]
                if bp.axis == "top":
                    ck(bp.band >= self.loop_for + F(1, 2),
                       "keepers fit clear of the pocket zip",
                       f"{frac(bp.band)} of band for a {frac(self.loop_for)} belt "
                       f"(want the belt plus ½\" for the tacks)")
                else:
                    # Turning the zip retires the trade this check policed. The
                    # keepers no longer live in a band left over above the zip;
                    # they sit on the far piece, which is the whole panel less
                    # a strip, so belt width and pocket depth stop competing for
                    # the same 5 7/8".
                    ck(bp.reach - self.sa >= self.loop_for + F(1, 2),
                       "keepers fit clear of the pocket zip",
                       f"{frac(bp.reach - self.sa)} of far piece for a "
                       f"{frac(self.loop_for)} belt — a vertical zip takes the "
                       "keepers out of competition with the pocket's depth")

        # A placket is only a flap while nothing holds it down. Anything tacked
        # through the panel where it hangs pins it flat, and then it stops
        # being a cover and starts being a patch sewn over the zip -- the
        # pocket cannot be opened at all. Nothing else could see this: the
        # placket is not a piece anything else measures against, and the
        # keeper's own checks only ask whether it clears the ZIP.
        TACKED = ("belt-loop", "dring", "handle", "logo")
        for face, pk in sorted(self.pockets.items()):
            if not pk.placket:
                continue
            # A RECTANGLE, not a band. The placket only exists where the zip
            # does, so once the zip stops short of one end there is clear panel
            # beyond it -- and a band test would still call that occupied and
            # refuse a keeper that is nowhere near the flap.
            across = TURN_IN + pk.zip - pk.coil / 2
            box = (across, TURN_IN + pk.starts,
                   across + pk.coil + pk.placket["show"], TURN_IN + pk.run)
            if pk.axis == "top":
                box = (box[1], box[0], box[3], box[2])
            clash = []
            for ft in self.spec.get("features", {}).get("placements", []):
                if ft.get("face") != face or ft.get("kind") not in TACKED:
                    continue
                rect = self._placement_rect(ft)
                if rect is None:
                    continue
                u0 = F(str(round(rect[0], 6))); v0 = F(str(round(rect[1], 6)))
                u1 = u0 + F(str(round(rect[2], 6)))
                v1 = v0 + F(str(round(rect[3], 6)))
                if u0 < box[2] and u1 > box[0] and v0 < box[3] and v1 > box[1]:
                    clash.append(f"{ft.get('kind')} at {frac(u0)},{frac(v0)}")
            lo, hi = box[0], box[2]
            ck(not clash, f"nothing is tacked onto the {face} placket",
               f"{frac(lo)}-{frac(hi)} is clear" if not clash else
               ", ".join(clash) + f" lands on the placket, which covers "
               f"{frac(lo)}-{frac(hi)}. A tack there pins the flap flat and the "
               "pocket cannot be opened")

        if self.wearer and self.loops:
            # The belt has to close round the smallest declared wearer with the
            # bag ON it, and the buckle and slider need somewhere to sit that
            # is not underneath the bag.
            spare = self.waist[0] - self.panel_w
            ck(spare >= 4, "the bag fits the smallest declared wearer",
               f"{frac(spare)} of waist left outside the bag at "
               f"{frac(self.waist[0])} — a buckle and its adjuster want 4\" of "
               "that, and none of it can sit under the bag")
            # NOT "does the belt reach the largest fit" -- the belt is DERIVED
            # from that fit, so such a check can only ever pass and would be
            # a check of nothing. What is declared, and therefore checkable, is
            # the tail: a side-release buckle and a tri-glide consume length,
            # and what is left has to be enough to grip and pull.
            if self.makes_belt:
                ck(self.belt_tail >= 4, "the belt has tail enough to adjust",
                   f"{frac(self.belt_tail)} beyond a {frac(self.fit_max)} "
                   f"{'waist' if self.has_sling or not self.crossbody else 'crossbody'}"
                   f", on top of the {frac(self.belt_takeup)} the buckle and "
                   "tri-glide take out of the cut length")

        lim = self.spec.get("fits_within_in")
        if lim:
            ok = (self.W <= F(str(lim["w"])) and self.D <= F(str(lim["d"]))
                  and self.H <= F(str(lim["h"])))
            ck(ok, f"within the declared limit {lim['w']}x{lim['d']}x{lim['h']}",
               f"{frac(self.W)} x {frac(self.D)} x {frac(self.H)}")
        return out

    def package_checks(self, construction: dict | None) -> list[tuple[bool, str, str]]:
        """The checks that only exist once a bag is packaged for the player."""
        out = []

        def ck(ok, name, detail):
            out.append((bool(ok), name, detail))

        peak = self.peak_mm()
        ck(peak <= STACK_STOP_MM, "peak stack is sewable",
           f"{peak:.2f} mm at the worst seam (a domestic machine stops "
           f"near {STACK_STOP_MM:g})")

        if construction is None:
            ck(False, "construction resolves",
               f"no patterns/constructions/{self.spec.get('construction')}.json")
        else:
            bad, rows = [], 0
            for key in ("assembly", "stitch_schedule", "tools", "checklist"):
                for row in construction.get(key, []):
                    if not self.applies(row):
                        continue
                    rows += 1
                    for v in row.values():
                        if not isinstance(v, str):
                            continue
                        try:
                            self.resolve(v)
                        except TokenError as e:
                            bad.append(f"{key} {row.get('n', '')}: {e}")
            ck(not bad, "construction tokens resolve",
               "; ".join(bad) if bad else
               f"{len(self.assembly(construction))} steps and {rows} rows apply, "
               "every token known")

        # A ring tacked to one layer of shell puts the whole bag into a stitch
        # field. The StadiumTote learned this on vinyl and answered it with the
        # chassis; a bag without one needs an anchor behind every ring.
        if self.flags["has_drings"]:
            ck(self.has_chassis or self.flags["has_ring_anchor"],
               "D-ring tabs have something behind them",
               "the chassis" if self.has_chassis else
               f"{self.feat['d_rings']} anchor strip(s), ends in the panel bindings"
               if self.flags["has_ring_anchor"] else
               "NOTHING — a tab box-X'd to one layer of shell will tear out")

        # A tack that lands under the binding sits in the thickest part of the
        # bag. Pieces MEANT to be caught in it are exempt: a full-width pocket
        # bag and a rib both reach the flange on purpose.
        # A placket belongs here for the same reason the zip does: it runs the
        # panel's full CUT length and both its ends are bound over on purpose,
        # exactly like the zipper tape it covers. It is not a tack that has
        # wandered under the binding.
        CAUGHT = {"pocket", "rib", "zip", "webbing", "placket"}
        under = []
        for ft in self.model3d()["features"]:
            if ft.get("kind") in CAUGHT or not ft.get("face"):
                continue
            rect = self._placement_rect(ft)
            if rect is None:
                continue
            fw, fh = (float(x) for x in self.face_size(ft["face"]))
            # `show`, not `flange`. The binding covers the face as far as its
            # own inner edge, which is one `turn` inboard of the stitch line --
            # so a placement judged against the flange passes while sitting up
            # to that much underneath the binding.
            fl = float(self.sa)
            u, v, w, h = rect
            if u < fl - 1e-6 or u + w > fw - fl + 1e-6:
                under.append(f"{ft.get('kind')} on {ft['face']}")
            # A zero height means the placement makes no claim about v -- a
            # handle is two anchors along u and nothing else. Testing the dummy
            # would fail every handle in the family against its own top flange.
            elif h and (v < fl - 1e-6 or v + h > fh - fl + 1e-6):
                under.append(f"{ft.get('kind')} on {ft['face']}")
        ck(not under, "nothing that gets tacked sits under the binding",
           ", ".join(sorted(set(under))) if under else
           f"all clear of the {frac(self.sa)} seam allowance")

        bad = []
        for ft in self.model3d()["features"]:
            k = ft.get("kind")
            if k not in FEATURE_KINDS:
                bad.append(f"unknown kind {k!r}")
                continue
            face = ft.get("face")
            if face and face not in FACES:
                bad.append(f"{k}: unknown face {face!r}")
                continue
            rect = self._placement_rect(ft)
            if rect is None:
                continue
            fw, fh = (float(v) for v in self.face_size(face))
            u, v, w, h = rect
            if u < -1e-6 or v < -1e-6 or u + w > fw + 1e-6 or v + h > fh + 1e-6:
                bad.append(f"{k} on {face} runs to "
                           f"{u + w:.2f} x {v + h:.2f} of {fw:g} x {fh:g}")
        ck(not bad, "3D placements sit on their face",
           "; ".join(bad) if bad else
           f"{len(self.model3d()['features'])} features, all on the bag")

        missing = [d["path"] for d in self.docs_declared()
                   if not (REPO / d["path"]).is_file()]
        ck(not missing, "supporting docs exist",
           ", ".join(missing) if missing else
           f"{len(self.docs_declared())} referenced, all present")

        if construction is not None:
            have = {d["path"] for d in
                    construction.get("docs", []) + self.docs_declared()}
            links = [(s.get("n"), p) for s in construction.get("assembly", [])
                     if self.applies(s) for p in s.get("see", [])]
            dead = [f"step {n} -> {p}" for n, p in links if p not in have]
            # A link the package does not carry renders as nothing at all: the
            # step simply loses its button and reads as if no method existed.
            ck(not dead, "every step link resolves to a doc in the package",
               "; ".join(dead) if dead else
               f"{len(links)} link(s) across {len(have)} doc(s)")

            # And the other direction. A technique note nobody links is a note
            # nobody reads: it sits in the quick-help rail while the step that
            # needs it explains the method badly in eighty words instead.
            all_links = {p for s in construction.get("assembly", [])
                         for p in s.get("see", [])}
            orphan = [d["path"] for d in construction.get("docs", [])
                      if d.get("kind") == "technique" and d["path"] not in all_links]
            ck(not orphan, "every technique note is linked from a step",
               ", ".join(orphan) if orphan else
               f"{len(all_links)} distinct doc(s) reached from the assembly order")

        bad = []
        for lay in self.layouts():
            roll = lay["roll_width_in"]
            ps = lay["pieces"]
            for p in ps:
                if p["x"] + p["w"] > roll + 1e-6:
                    bad.append(f"{p['piece']} exceeds the {roll:g}\" roll")
            for i, a in enumerate(ps):
                for b in ps[i + 1:]:
                    if (a["x"] < b["x"] + b["w"] - 1e-6 and b["x"] < a["x"] + a["w"] - 1e-6
                            and a["y"] < b["y"] + b["h"] - 1e-6
                            and b["y"] < a["y"] + a["h"] - 1e-6):
                        bad.append(f"{a['piece']} overlaps {b['piece']}")
        ck(not bad, "cutting layout nests",
           "; ".join(sorted(set(bad))) if bad else
           " + ".join(f"{l['material']} {l['used']['text']}" for l in self.layouts()))

        # The cut list sizes fabric and webbing and stops there. Two bags here
        # shipped a complete-looking cut list with no zipper in it.
        items = " ".join(h.get("item", "") for h in self.spec.get("hardware", [])).lower()
        ck("zip" in items, "a zipper is declared",
           "hardware[] names one" if "zip" in items else
           "the cut list sizes the two zip strips but nothing buys the zipper")

        return out

    def docs_declared(self) -> list[dict]:
        out = list(self.spec.get("docs", []))
        return out

    def failed(self) -> int:
        return sum(1 for ok, _, _ in self.checks() if not ok)

    # -- assembly ----------------------------------------------------------
    def assembly(self, construction: dict) -> list[dict]:
        out = []
        for step in construction.get("assembly", []):
            if not self.applies(step):
                continue
            out.append({"n": len(out) + 1,
                        "title": self.resolve(step.get("title", "")),
                        "body": self.resolve(step.get("body", "")),
                        "stitch": self.resolve(step.get("stitch", "") or ""),
                        # A figure is DECLARED per step and drawn per bag. Its
                        # caption is resolved like any other prose, so a figure
                        # can name the dimension it is showing without that
                        # number being written down anywhere.
                        "figures": [{k: (self.resolve(v) if isinstance(v, str) else v)
                                     for k, v in f.items()}
                                    for f in step.get("figures", [])
                                    if self.applies(f)],
                        "see": list(step.get("see", []))})
        return out

    def applicable(self, construction: dict, key: str) -> list[dict]:
        """Filter any construction list by its rows' conditions, resolving tokens.

        The stitch schedule, tool list and checklist get the same treatment as
        the assembly order: a bag with no chassis should not be told to box-X
        an overlap it does not have, and a row nobody can act on is a row that
        teaches the reader to skim the whole table.
        """
        out = []
        for row in construction.get(key, []):
            if not self.applies(row):
                continue
            out.append({k: (self.resolve(v) if isinstance(v, str) else v)
                        for k, v in row.items() if k not in ("when", "unless")})
        return out

    # -- report ------------------------------------------------------------
    def report(self) -> str:
        L = []
        a = L.append
        shell = self.spec.get("shell", "cordura-1000d")
        win = self.spec.get("windows", False)
        a(f"{self.name}")
        a("=" * len(self.name))
        a(f"  finished overall   {frac(self.W)} W x {frac(self.D)} D x {frac(self.H)} H")
        a(f"  finished / stitch line  {frac(self.face_w)} x {frac(self.face_h)}"
          f"   depth {frac(self.face_d)}   <- turned, so the finished edge IS the seam")
        a(f"  artwork field       {frac(self.visible_w)} x {frac(self.visible_h)}"
          f"   depth {frac(self.visible_d)}   <- {frac(SEAM_MARGIN_IN)} clear of every seam")
        a(f"  seam allowance {frac(self.sa)}   relief clips cut to {frac(self.clip_depth)}"
          f"   ({self.relief_clips} per curve)")
        if self.corner_r:
            a(f"  bottom corners round at {frac(self.corner_r)}"
              f" ({frac(self.corner_cut_r)} at the cut edge)")
        a("")
        a(f"  PANELS ({self.win_mat if win else shell})")
        if self.pockets:
            a(f"    full size          2 @  {frac(self.panel_w)} wide x {frac(self.panel_h)} tall")
            a(f"    outer layer        cut in two -- see PANEL POCKETS below")
        if self.corner_r:
            curved = sorted({r["piece"] for r in self.cut_list()
                             if r["corners"] != "square"})
            a(f"    NOT rectangles: {', '.join(curved)}")
            a(f"    -- bottom corners round at {frac(self.corner_cut_r)}"
              f" (divider {frac(self.div_r)}); cut round one template so they agree")
        else:
            a(f"    front, back        2 @  {frac(self.panel_w)} wide x {frac(self.panel_h)} tall")
        a("")
        a(f"  GUSSET RING ({shell})   ring at the stitch line = {frac(self.ring)}")
        a(f"    gusset             1 @  {frac(self.gusset_w)} x {frac(self.gusset_cut)}"
          f"   (cut long: {frac(self.gusset_cut + 3)})")
        a(f"    zip strip, front   1 @  {frac(self.strip_front)} x {frac(self.zip_cut)}")
        a(f"    zip strip, rear    1 @  {frac(self.strip_rear)} x {frac(self.zip_cut)}")
        a(f"    coil sits {frac(self.coil_c)} from the panel's cut edge")
        a("")
        a(f"  SEAMS")
        a(f"    allowance          {frac(self.sa)} on every edge, sewn right sides together")
        a(f"    to sew             {frac(self.seam_run)} of panel seam, then turned through the zip")
        worst = max(self.panel_seam_mm.values())
        a(f"    worst stack        {worst:.2f} mm   (no binding, no mitre)")
        a("")
        a("  CARRY")
        if self.has_chassis:
            a(f"    chassis loop       1 @  {frac(self.loop)}   ({frac(self.ring)} ring + {frac(self.overlap)} overlap)")
        else:
            a("    no chassis         carried by the belt, not by straps")
        n = int(self.feat.get("d_rings", 0))
        if n:
            a(f"    D-ring tabs        {n} @  {frac(F(4))}")
            if self.flags["has_ring_anchor"]:
                a(f"    ring anchors ({shell})  {n} @  {frac(self.gusset_w)}"
                  f" x {frac(RING_ANCHOR_W_IN)}   (across the gusset, ends in the seams)")
        if self.wearer and self.has_sling:
            if self.makes_strap:
                a(f"    sling strap        1 @  {frac(self.sling_cut)}"
                  f"   ({frac(self.crossbody)} crossbody + hardware take-up)")
            else:
                a(f"    shoulder strap     YOURS   (clips to the {n} D-rings; "
                  f"about {frac(self.crossbody)} for crossbody)")
        if self.loops and self.wearer and not self.makes_belt:
            a(f"    belt               YOURS   (cut the keepers for "
              f"{frac(self.loop_for)}; it closes round "
              f"{frac(self.waist[0])}–{frac(self.waist[1])})")
        if self.feat.get("handle_in"):
            a(f"    grab handle        1 @  {frac(F(str(self.feat['handle_in'])))}")
        if self.loops:
            a(f"    belt keeper ({shell})  {self.loop_count} @  {frac(self.loop_w)}"
              f" x {frac(self.loop_len)}   (fits a {frac(self.loop_for)} belt)")
            if self.loop_anchor:
                a(f"    anchor strip       1 @  {frac(self.panel_w)}"
                  f" x {frac(self.loop_w)}   (behind the keepers, caught in the binding)")
        if self.pockets:
            n = len(self.pockets)
            a("")
            a(f"  PANEL POCKETS ({self.panel_mat})   "
              f"{' and '.join(sorted(self.pockets))}")
            a(f"    panel, full size   2 @  {frac(self.panel_w)} x {frac(self.panel_h)}"
              f"   (the inner layer -- seals the compartment)")
            # One block per DISTINCT build, not one set of figures for all of
            # them -- two pockets split different ways share nothing but the
            # zipper, and printing the aggregate quietly described one of them
            # with the other's numbers.
            seen = {}
            for f in sorted(self.pockets):
                seen.setdefault(self.pockets[f].key(), []).append(f)
            for fs in seen.values():
                pk = self.pockets[fs[0]]
                near, far = pk.pieces
                across = self.panel_w if pk.axis == "top" else self.panel_h
                a(f"    {' + '.join(fs)}: zip {frac(pk.zip)} "
                  + ("down from the top" if pk.axis == "top" else "in from the side")
                  + " of the cut edge")
                a(f"      outer, {near:<12}{len(fs)} @  {frac(across)} x {frac(pk.upper)}")
                a(f"      outer, {far:<12}{len(fs)} @  {frac(across)} x {frac(pk.lower)}")
                if pk.placket:
                    a(f"      placket      {len(fs)} @  {frac(pk.placket['long'])}"
                      f" x {frac(pk.placket['cut'])}"
                      f"   ({frac(pk.placket['show'])} hangs over the coil)")
            for f in sorted(self.pockets):
                pw, pd = self.pocket_interior(f)
                a(f"    {f} cavity         {frac(pw)} x {frac(pd)} inside")
        if self.has_divider:
            a("")
            a(f"  DIVIDER ({shell})   flat against the {self.div_face} panel's interior")
            a(f"    divider pocket     1 @  {frac(self.div_w)} x {frac(self.div_h)}"
              f"   ({frac(self.div_depth)} deep, {frac(self.div_clear)} clear above)")
            if self.div_channels:
                ch = " / ".join(frac(w) for w in self.channel_widths())
                a(f"    channels           {ch}"
                  f"   (topstitched at {', '.join(frac(c) for c in self.div_channels)})")
        a("")
        a("  ASSEMBLY LOAD")
        for r in self.assembly_load():
            a(f"    {str(r['count']):>8}  {r['item']}")
        a("")
        a("  CHECKS")
        for ok, name, detail in self.checks():
            a(f"    {'ok  ' if ok else 'FAIL'}  {name:<44} {detail}")
        return "\n".join(L)

    # -- the package -------------------------------------------------------
    def package(self, spec_path: Path, construction: dict,
                cons_path: Path, stamp: str) -> dict:
        docs = []
        for d in (construction.get("docs", []) + self.docs_declared()):
            p = REPO / d["path"]
            docs.append({"title": d["title"], "path": d["path"],
                         "kind": d.get("kind", "doc"),
                         "body": p.read_text(encoding="utf-8") if p.is_file() else ""})

        checks = [{"ok": ok, "name": n, "detail": t}
                  for ok, n, t in self.checks() + self.package_checks(construction)]

        materials = [{"role": "shell", "material": self.shell,
                      "thickness_mm": self.shell_mm, "frays": self.shell_frays,
                      "note": "turned construction: every edge finishes inside "
                              "its own seam, so there is no second material and "
                              "no edge finish to buy"}]
        if self.windows:
            materials.append({"role": "window", "material": self.win_mat,
                              "thickness_mm": mat(self.win_mat)["mm"],
                              "frays": False, "note": "rotary-cut only, never hot-knifed"})
        materials.extend(self.spec.get("materials", []))

        return {
            "schema_version": SCHEMA_VERSION,
            "name": self.name,
            "title": self.spec.get("title", self.name),
            "construction": self.spec["construction"],
            "construction_title": construction.get("title", ""),
            "description": self.spec.get("description", ""),
            "summary": construction.get("summary", ""),
            "finished": {"w": dim(self.W), "d": dim(self.D), "h": dim(self.H),
                         "w_mm": round(float(self.W) * MM_PER_IN, 1),
                         "d_mm": round(float(self.D) * MM_PER_IN, 1),
                         "h_mm": round(float(self.H) * MM_PER_IN, 1)},
            "interior": self.interior(),
            "flags": self.flags,
            "geometry": {k: dim(v) for k, v in self.geometry.items()},
            "materials": materials,
            "cut_list": self.cut_list(),
            "layouts": self.layouts(),
            "takeoff": self.takeoff(),
            "hardware": self.spec.get("hardware", []),
            "zipper_schedule": self.zipper_schedule(),
            "glossary": load_glossary()["terms"],
            "photos": load_photos()["items"],
            "assembly": self.assembly(construction),
            "stitch_schedule": self.applicable(construction, "stitch_schedule"),
            "tools": self.applicable(construction, "tools"),
            "checklist": self.applicable(construction, "checklist"),
            "thickness": self.thickness(),
            "peak_mm": round(self.peak_mm(), 2),
            "comfort": self.comfort(),
            "assembly_load": self.assembly_load(),
            "sources": construction.get("sources", []),
            "model3d": self.model3d(),
            "checks": checks,
            "notes": self.spec.get("notes", []),
            "open_questions": self.spec.get("open_questions", []),
            "docs": docs,
            "embroidery": self.spec.get("embroidery",
                                        {"panel": None, "design": None,
                                         "field_mm": [96, 96]}),
            "provenance": {
                "generated_at": stamp,
                "schema_version": SCHEMA_VERSION,
                "spec": {"path": spec_path.relative_to(REPO).as_posix(),
                         "sha256": sha256(spec_path)},
                "construction": {"path": cons_path.relative_to(REPO).as_posix(),
                                 "sha256": sha256(cons_path)},
                "tools": {p: sha256(REPO / p) for p in TOOL_SCRIPTS
                          if (REPO / p).is_file()},
            },
        }


def load(path: Path) -> BoxBag:
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("construction") != "box-turned":
        raise ValueError(f"{path.name}: construction must be 'box-turned'")
    if spec.get("name") != path.stem:
        raise ValueError(f"{path.name}: name must match the filename")
    return BoxBag(spec)


#: Licences that may be EMBEDDED. Share-alike is deliberately absent: putting a
#: CC BY-SA image inside the page arguably pulls share-alike onto the whole
#: published artifact, and that is the user's decision rather than a default to
#: inherit. Such an image gets linked from a technique note instead.
EMBEDDABLE = ("CC0", "Public domain", "CC BY 2.0", "CC BY 3.0", "CC BY 4.0")


@functools.lru_cache(maxsize=1)
def load_photos() -> dict:
    """Photographs, base64'd, with the credit that has to travel with them.

    A diagram can show how a lap is put together; it cannot answer "what does a
    coil actually look like". These do. Credit is part of the record, not a
    footnote -- an image whose licence or source is unknown cannot be published
    and is refused here rather than discovered later.
    """
    man = PHOTOS / "photos.json"
    if not man.is_file():
        return {"items": {}}
    doc = json.loads(man.read_text(encoding="utf-8"))
    out = {}
    for it in doc.get("items", []):
        for k in ("id", "file", "title", "caption", "licence", "source"):
            if not str(it.get(k, "")).strip():
                raise ValueError(f"photos: {it.get('id')!r} has no {k!r}")
        if it["licence"] not in EMBEDDABLE:
            raise ValueError(
                f"photos: {it['id']!r} is {it['licence']!r}, which is not in "
                f"EMBEDDABLE -- link it from a technique note instead of "
                "embedding it")
        f = PHOTOS / it["file"]
        if not f.is_file():
            raise ValueError(f"photos: {it['id']!r} names a missing {it['file']!r}")
        if it["id"] in out:
            raise ValueError(f"photos: {it['id']!r} is defined twice")
        b = f.read_bytes()
        out[it["id"]] = {k: it[k] for k in
                         ("id", "title", "caption", "licence", "source")} | {
            "author": it.get("author", "Unknown"),
            "bytes": len(b),
            "src": "data:image/jpeg;base64," + base64.b64encode(b).decode("ascii")}
    return {"items": out, "policy": doc.get("licence_policy", "")}


@functools.lru_cache(maxsize=1)
def load_glossary() -> dict:
    """The shared vocabulary, validated on the way in.

    A glossary is prose, and prose gets skipped -- so this one is DATA. The
    page links the first use of each term in every step to its entry, which is
    the only version of a glossary anybody reads. That only works if the terms
    are well-formed, so a malformed entry is an error here rather than a term
    that silently never links.
    """
    g = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    seen = set()
    for t in g.get("terms", []):
        for k in ("term", "group", "short", "body"):
            if not str(t.get(k, "")).strip():
                raise ValueError(f"glossary: {t.get('term')!r} has no {k!r}")
        for name in [t["term"]] + list(t.get("aka", [])):
            if name.lower() in seen:
                raise ValueError(f"glossary: {name!r} is defined twice -- "
                                 "the page would link it to whichever came first")
            seen.add(name.lower())
        if t.get("see") and not (REPO / t["see"]).is_file():
            raise ValueError(f"glossary: {t['term']!r} points at a missing "
                             f"{t['see']!r}")
        # A reference has to say what it IS. Half of what a search turns up for
        # these operations is a photo walkthrough on a page whose URL says
        # "video", and the best box-X reference here is stills -- so "kind" is
        # required rather than assumed, and only these three are honest.
        for w in t.get("watch", []):
            if w.get("kind") not in ("video", "article", "photos"):
                raise ValueError(f"glossary: {t['term']!r} has a reference of "
                                 f"kind {w.get('kind')!r}")
            if not str(w.get("title", "")).strip():
                raise ValueError(f"glossary: {t['term']!r} has an untitled "
                                 "reference -- a bare URL says nothing")
            if not str(w.get("url", "")).startswith("https://"):
                raise ValueError(f"glossary: {t['term']!r} has a non-https "
                                 f"reference {w.get('url')!r}")
        # A term's figure is the SAME declaration a step's figure is, so the
        # drawing of a mitre is one drawing used twice rather than two that can
        # disagree. Only the embedded form can be checked here -- whether a
        # generated one draws anything is a question for the page, and
        # tools/tests/test_figures.js asks it.
        fg = t.get("figure")
        if fg:
            if ("doc" in fg) == ("kind" in fg):
                raise ValueError(f"glossary: {t['term']!r} figure must name "
                                 "either a doc+id or a kind, not both or neither")
            if "doc" in fg:
                d = REPO / fg["doc"]
                if not d.is_file():
                    raise ValueError(f"glossary: {t['term']!r} figure points at "
                                     f"a missing {fg['doc']!r}")
                if f'id="{fg.get("id")}"' not in d.read_text(encoding="utf-8"):
                    raise ValueError(f"glossary: {t['term']!r} figure wants "
                                     f"{fg.get('id')!r}, which {fg['doc']} "
                                     "does not define")
        # A photo is named by id so the same image is never embedded twice.
        ph = t.get("photo")
        if ph and ph not in load_photos()["items"]:
            raise ValueError(f"glossary: {t['term']!r} wants photo {ph!r}, "
                             "which patterns/photos/photos.json does not define")
        # Where a term names a technique note, its references must also appear
        # in that note's own "Watch it done" table, or the two drift and the
        # reader is told different things depending which they opened.
        if t.get("see") and t.get("watch"):
            doc = (REPO / t["see"]).read_text(encoding="utf-8")
            for w in t["watch"]:
                if w["url"] not in doc:
                    raise ValueError(
                        f"glossary: {t['term']!r} links {w['url']} but "
                        f"{t['see']} does not -- keep the two in step")
    return g


def load_construction(name: str) -> tuple[dict | None, Path]:
    p = CONSTRUCTIONS / f"{name}.json"
    if not p.is_file():
        return None, p
    c = json.loads(p.read_text(encoding="utf-8"))
    if c.get("construction") != name:
        raise ValueError(f"{p.name}: 'construction' must equal the filename stem")
    return c, p


def write_package(bag: BoxBag, spec_path: Path, stamp: str) -> tuple[Path, int]:
    """Write build/patterns/<Name>.json. Returns (path, failed check count)."""
    cons, cons_path = load_construction(bag.spec["construction"])
    if cons is None:
        raise FileNotFoundError(f"no construction file at {cons_path}")
    pkg = bag.package(spec_path, cons, cons_path, stamp)
    PACKAGES.mkdir(parents=True, exist_ok=True)
    out = PACKAGES / f"{bag.name}.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(pkg, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    tmp.replace(out)
    return out, sum(1 for c in pkg["checks"] if not c["ok"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec", nargs="*", type=Path)
    ap.add_argument("--all", action="store_true", help="every spec in patterns/specs/")
    ap.add_argument("--check", action="store_true", help="exit non-zero on any failed check")
    ap.add_argument("--package", action="store_true",
                    help="write build/patterns/<Name>.json for the player")
    ap.add_argument("--tokens", action="store_true",
                    help="list the tokens a construction step may use")
    args = ap.parse_args(argv)

    # The report is full of ⅜ and ⅝. A Windows console defaults to cp1252 and
    # dies on them, which would make this tool unusable in the shell this repo
    # actually runs in.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    paths = sorted(SPECS.glob("*.json")) if args.all else list(args.spec)
    if not paths:
        ap.error("give a spec path or --all")

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    bad = 0
    for i, p in enumerate(paths):
        bag = load(p)
        if args.tokens:
            g, w = bag.geometry, bag.words
            print(f"{bag.name}")
            for k in sorted(g):
                print(f"  {{{k}}}".ljust(22) + frac(g[k]))
            for k in sorted(w):
                print(f"  {{{k}}}".ljust(22) + w[k])
            continue
        if i:
            print()
        print(bag.report())
        bad += bag.failed()
        if args.package:
            out, failed = write_package(bag, p, stamp)
            extra = failed - bag.failed()
            tail = f"   ({extra} more check(s) FAILED)" if extra else ""
            print(f"\n  PACKAGE  {out.relative_to(REPO).as_posix()}{tail}")
            bad += extra

    if bad:
        print(f"\n{bad} check(s) FAILED", file=sys.stderr)
    return 1 if (bad and args.check) else 0


if __name__ == "__main__":
    raise SystemExit(main())
