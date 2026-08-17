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
PACKAGES = REPO / "build" / "patterns"

SCHEMA_VERSION = "1.0"

#: Binding wraps the flange and adds its own thickness to the projection. Small,
#: but it is the difference between a 12" bag measuring 12" and measuring 12 1/8.
TURN_IN = F(1, 16)

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
MATERIALS = {
    "cordura-1000d":      {"mm": 0.50, "frays": False, "roll_in": 60},
    "vinyl-20ga":         {"mm": 0.51, "frays": False, "roll_in": 54},
    "nylon-binding-tape": {"mm": 0.50, "frays": False, "by_length": True},
    "webbing-1in":        {"mm": 1.30, "frays": False, "by_length": True},
    "denim-10oz":         {"mm": 0.60, "frays": True,  "roll_in": 58},
    "denim-12oz":         {"mm": 0.75, "frays": True,  "roll_in": 58},
    "duck-12oz":          {"mm": 0.70, "frays": True,  "roll_in": 58},
    "waxed-canvas-10oz":  {"mm": 0.85, "frays": True,  "roll_in": 58},
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

#: The closed set of condition flags a construction step may name.
FLAGS = ("has_chassis", "shell_frays", "double_fold", "has_windows",
         "has_handle", "has_drings", "has_belt_loop", "has_belt_anchor",
         "has_ring_anchor", "has_sling", "has_back_pocket", "has_front_pocket",
         "has_panel_pocket", "has_divider",
         "has_pockets")

#: Feature kinds the player's renderer knows how to draw. A kind outside this
#: set is a check failure rather than a silently missing detail.
FEATURE_KINDS = ("zip", "webbing", "dring", "handle", "logo", "rib",
                 "pocket", "patch", "belt-loop")
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
    """

    def __init__(self, face: str, spec: dict, bag: "BoxBag"):
        self.face = face
        self.zip = F(str(spec["zip_from_top_in"]))
        self.coil = F(str(spec.get("coil_in", bag.coil)))
        self.lap = F(str(spec.get("lap_in", bag.lap)))
        self.must_hold = spec.get("must_hold_in")
        self.upper = self.zip - self.coil / 2 + self.lap
        self.lower = bag.panel_h - (self.zip + self.coil / 2) + self.lap
        #: How far the cavity reaches below the opening, and how much panel is
        #: left above it once the seam allowance and the lap are gone -- the
        #: band anything tacked to the outer upper piece has to live in.
        self.reach = bag.panel_h - self.zip - self.coil / 2
        self.band = self.upper - self.lap - bag.sa
        self.above = self.zip - self.coil / 2 - bag.sa

    def key(self) -> tuple:
        return (self.zip, self.coil, self.lap)


class BoxBag:
    """A bound-seam box bag derived from its finished envelope."""

    def __init__(self, spec: dict):
        self.spec = spec
        self.name = spec["name"]
        f = spec["finished_in"]
        self.W, self.H, self.D = F(str(f["w"])), F(str(f["h"])), F(str(f["d"]))
        self.sa = F(str(spec.get("seam_allowance_in", "0.375")))
        self.show = F(str(spec.get("binding_show_in", "0.5")))
        self.shell = spec.get("shell", "cordura-1000d")
        self.win_mat = spec.get("window_material", "vinyl-20ga")
        b = spec.get("binding", {})
        self.bind_mat = b.get("material", self.shell)
        self.shell_mm, self.shell_frays = mat(self.shell)["mm"], mat(self.shell)["frays"]
        self.bind_mm, self.bind_frays = mat(self.bind_mat)["mm"], mat(self.bind_mat)["frays"]
        # Fraying binding must be folded under on its outer edge: four layers
        # at every seam instead of two, and 3/4" more strip width.
        self.double_fold = self.bind_frays
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
            if div and div.get("face", "front") == f                     and div.get("attach", "binding") == "binding":
                n += 1
            self.panel_layers[f] = n

        self.panel_sandwich_mm = {f: win_mm * n + self.shell_mm
                                  for f, n in self.panel_layers.items()}

        worst = max(self.sandwich_mm, *self.panel_sandwich_mm.values())
        # ceil, not round: a strip that has to reach round a sandwich and back
        # is either long enough or it is not, and rounding to nearest is wrong
        # half the time in the direction that cannot be recovered.
        self.bind_cut = ceil_to(2 * self.show
                                + F(str(round(worst / MM_PER_IN, 4)))
                                + F(1, 16)
                                + (F(3, 4) if self.double_fold else 0), 8)
        # Plain bound seam, and the mitred corner where the binding doubles.
        layers = 4 if self.double_fold else 2
        self.bind_layers = layers
        self.seam_mm = self.sandwich_mm + layers * self.bind_mm
        self.corner_mm = self.seam_mm + layers * self.bind_mm
        self.panel_seam_mm = {f: s + layers * self.bind_mm
                              for f, s in self.panel_sandwich_mm.items()}
        self.panel_corner_mm = {f: v + layers * self.bind_mm
                                for f, v in self.panel_seam_mm.items()}
        z = spec.get("closure", {})
        self.coil = F(str(z.get("coil_in", "0.25")))
        self.lap = F(str(z.get("lap_in", "0.5")))
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

        self.flange = self.sa + TURN_IN

        # Faces: what is visible between flanges.
        self.face_w = self.W - 2 * self.flange
        self.face_h = self.H - 2 * self.flange
        self.face_d = self.D - 2 * self.flange

        # Cuts: face plus the allowance that becomes the flange.
        self.panel_w = self.face_w + 2 * self.sa
        self.panel_h = self.face_h + 2 * self.sa
        self.gusset_w = self.face_d + 2 * self.sa

        # Rounded corners. A gusset following a curve needs NO clip and the
        # binding needs NO mitre -- the two hardest operations on the bag, and
        # a rounded corner deletes both. The gusset itself does not care: a band
        # standing on a curved edge is a developable surface, so a flat strip
        # follows it with no easing at all. The binding does care, and has to be
        # cut on the bias, because it bends the hard way round that edge.
        cs = spec.get("corners", {})
        self.corner_r = F(str(cs.get("bottom_in", 0)))
        self.curved_corners = 2 if self.corner_r > 0 else 0
        self.square_corners = 4 - self.curved_corners
        self.bind_bias = self.curved_corners > 0
        # At the cut edge the same corner is one seam allowance further out.
        self.corner_cut_r = self.corner_r + self.sa if self.corner_r else F(0)
        self.corner_saved = round_to(self.curved_corners * self.corner_r
                                     * CORNER_SAVING, 16)
        # The gusset's allowance has to splay round a convex curve exactly as it
        # does at a square corner -- distributed instead of all at one point.
        # Space the snips a seam allowance apart, the usual rule for relieving
        # a curve, so each opens by a fraction of the shortfall.
        self.relief_clips = (math.ceil(float(self.corner_r) * math.pi / 2
                                       / float(self.sa)) if self.corner_r else 0)
        self.corner_cut_saved = round_to(self.curved_corners * self.corner_cut_r
                                         * CORNER_SAVING, 16)

        # The ring follows the stitch line, not the raw edge.
        self.ring = 2 * (self.face_w + self.face_h) - self.corner_saved
        self.zip_face = self.face_w                    # zipper spans the top
        self.gusset_face = self.ring - self.zip_face
        self.gusset_cut = self.gusset_face + 2 * self.lap
        self.zip_cut = self.zip_face + 2 * self.lap

        # Zipper strips. The coil sits off-centre so the webbing can run the
        # face centreline unbroken; centre it in the space forward of the web.
        # With a chassis the coil is pushed forward so the webbing can hold the
        # face centreline unbroken; without one it simply sits centred.
        self.web_lo = self.gusset_w / 2 - self.web / 2
        self.coil_c = (round_to((self.sa + self.web_lo) / 2, 8) if self.has_chassis
                       else round_to(self.gusset_w / 2, 16))
        self.strip_front = self.coil_c - self.coil / 2 + self.lap
        self.strip_rear = self.gusset_w - (self.coil_c + self.coil / 2) + self.lap

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
            self.div_attach = div.get("attach", "binding")
            self.div_inset = F(str(div.get("inset_in", "0.25")))
            if self.div_attach == "binding":
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
        self.div_r = F(0)
        if div and self.corner_r and self.div_attach == "topstitch"                 and self.div_face in ("front", "back"):
            self.div_r = max(F(0), self.corner_r - self.div_inset)

        # Chassis loop and binding.
        self.loop = self.ring + self.overlap
        self.binding = (2 * (2 * self.panel_w + 2 * self.panel_h)
                        - 2 * self.corner_cut_saved)
        if self.has_divider and self.div_attach == "binding":
            self.binding += self.panel_w          # its own bound top edge
        self.binding_buy = round_to(self.binding * F(6, 5)
                                    * (BIAS_WASTE if self.bind_bias else 1), 4)
        # A square of side S yields about S^2 / w inches of continuous bias, so
        # the side you need is the square root of the strip's own area. Derived
        # here rather than formatted into a takeoff line, so a test can assert
        # on the number instead of parsing it back out of a sentence.
        self.bias_square = (ceil_to(F(str(round((float(self.binding_buy)
                                                 * float(self.bind_cut)) ** 0.5, 4))), 2)
                            if self.bind_bias else F(0))

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
            # A bag with rings gets a dedicated sling for crossbody, so its belt
            # only has to reach a waist. Without rings the belt has to do both,
            # and it is the longer of the two that sizes it.
            self.has_sling = (int(self.feat.get("d_rings", 0)) > 0
                              and self.crossbody is not None)
            self.fit_max = (self.waist[1] if self.has_sling
                            else max([self.waist[1]]
                                     + ([self.crossbody] if self.crossbody else [])))
            self.belt_cut = round_to(self.fit_max + self.belt_tail, 1)
            if self.has_sling:
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
            first = next(iter(self.pockets.values()))
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
            "sa": self.sa, "flange": self.flange, "show": self.show,
            "turn": TURN_IN,
            "face_w": self.face_w, "face_h": self.face_h, "face_d": self.face_d,
            "panel_w": self.panel_w, "panel_h": self.panel_h,
            "gusset_w": self.gusset_w, "gusset_face": self.gusset_face,
            "gusset_cut": self.gusset_cut,
            "gusset_cut_long": self.gusset_cut + 3,
            "ring": self.ring, "zip_face": self.zip_face, "zip_cut": self.zip_cut,
            "coil": self.coil, "lap": self.lap, "coil_c": self.coil_c,
            "strip_front": self.strip_front, "strip_rear": self.strip_rear,
            "bind_cut": self.bind_cut,
            "binding_len": self.binding, "binding_buy": self.binding_buy,
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
            g.update({"belt_cut": self.belt_cut, "waist_min": self.waist[0],
                      "waist_max": self.waist[1], "fit_max": self.fit_max})
            if self.crossbody:
                g["crossbody"] = self.crossbody
            if self.has_sling:
                g["sling_cut"] = self.sling_cut
        if self.flags["has_ring_anchor"]:
            g.update({"ring_anchor_w": RING_ANCHOR_W_IN,
                      "ring_anchor_len": self.gusset_w})
        if self.has_divider:
            g.update({"divider_h": self.div_h, "divider_w": self.div_w,
                      "divider_depth": self.div_depth,
                      "divider_clear": self.div_clear,
                      "divider_inset": self.div_inset})
        if self.corner_r:
            g.update({"corner_r": self.corner_r, "corner_cut_r": self.corner_cut_r})
        if self.has_panel_pocket:
            g.update({"bp_zip": self.bp_zip, "bp_coil": self.bp_coil,
                      "bp_lap": self.bp_lap, "bp_upper": self.bp_upper,
                      "bp_lower": self.bp_lower, "bp_bag": self.bp_bag,
                      "bp_band": self.bp_band})
        return g

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
        g = self.geometry
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
            if key not in g:
                raise TokenError(
                    f"{self.name}: unknown token {{{key}}} -- "
                    f"available: {', '.join(sorted(g))}")
            out.append(frac(g[key]))
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
                   row("Panel, outer upper", n, self.panel_w, self.bp_upper,
                       self.panel_mat,
                       f"laps {frac(self.bp_lap)} onto the pocket zip tape ({faces})"),
                   row("Panel, outer lower", n, self.panel_w, self.bp_lower,
                       self.panel_mat, r=self.corner_cut_r,
                       note=f"laps {frac(self.bp_lap)} onto the pocket zip tape "
                            f"({faces}); it carries the panel's bottom edge")]
        else:
            out = [row("Front and back panel", 2, self.panel_w, self.panel_h,
                       self.panel_mat, r=self.corner_cut_r)]
        out.append(row("Gusset", 1, self.gusset_w, self.gusset_cut + 3, self.shell,
                       f"cut long; trim the ring to {frac(self.gusset_cut)} "
                       "against the back panel before closing it"))
        out.append(row("Zip strip, front", 1, self.strip_front, self.zip_cut,
                       self.shell, f"narrow side; laps {frac(self.lap)} onto the tape"))
        out.append(row("Zip strip, rear", 1, self.strip_rear, self.zip_cut,
                       self.shell, f"wide side; laps {frac(self.lap)} onto the tape"))
        for s in self.binding_strips():
            out.append(row("Binding strip", 1, self.bind_cut, s, self.bind_mat,
                           "single fold" if not self.double_fold
                           else "DOUBLE fold -- outer edge turned under"))
        if self.has_divider:
            n = len(self.div_channels)
            out.append(row("Divider pocket", 1, self.div_w, self.div_h, self.shell,
                           r=self.div_r, note=
                           f"lies flat against the {self.div_face} panel's interior; "
                           + ("sides and bottom caught in that panel's own binding, "
                              "top edge bound and free"
                              if self.div_attach == "binding" else
                              f"topstitched down three sides {frac(self.div_inset)} "
                              "clear of the binding, top edge hot-knifed and free")
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

    def binding_strips(self) -> list[F]:
        """The buy length, split into strips a roll can actually yield."""
        roll = mat(self.bind_mat).get("roll_in", DEFAULT_ROLL_IN)
        if mat(self.bind_mat).get("by_length"):
            return [self.binding_buy]
        n = max(1, math.ceil(float(self.binding_buy) / roll))
        each = F(math.ceil(float(self.binding_buy) / n))
        return [each] * n

    # -- nesting -----------------------------------------------------------
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
            if self.bind_bias and r["piece"] == "Binding strip":
                continue
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
        for lay in self.layouts():
            yd = float(lay["buy"]["in"]) / 36.0
            out.append({"item": f"{lay['material']}, {lay['roll_width_in']:g}\" wide",
                        "qty": f"{lay['buy']['text']} of length",
                        "note": f"{lay['used']['text']} nests the pieces; "
                                f"about {yd:.2f} yd with margin"})
        if mat(self.bind_mat).get("by_length"):
            out.append({"item": f"{self.bind_mat}, {frac(self.bind_cut)} wide",
                        "qty": frac(self.binding_buy),
                        "note": f"{frac(self.binding)} needed; the rest covers "
                                "mitres and joins"})
        elif self.bind_bias:
            # A square of side S yields about S^2 / w inches of continuous bias,
            # so the side you need is the square root of the strip's own area.
            out.append({"item": f"{self.bind_mat}, BIAS binding",
                        "qty": f"a {frac(self.bias_square)} square",
                        "note": f"{frac(self.binding)} needed, {frac(self.binding_buy)} "
                                f"cut ({frac(self.bind_cut)} wide) once bias waste and "
                                "45° piecing are counted. Cut on the diagonal, so it is "
                                "not in the nesting layout — that draws pieces along the "
                                "roll and a bias strip does not run that way"})
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
                        "note": " + ".join(parts) + "  (straps and belt are extra)"})
        if self.loops and self.wearer:
            fit = (f"{frac(self.waist[0])}–{frac(self.waist[1])} waist"
                   + ("" if self.has_sling
                      else f", or {frac(self.crossbody)} crossbody"
                      if self.crossbody else ""))
            out.append({"item": f"{frac(self.loop_for)} nylon webbing, belt",
                        "qty": frac(self.belt_cut),
                        "note": f"{fit}, plus {frac(self.belt_tail)} of tail. "
                                "Derived from the declared fit range, so it moves "
                                "when the bag or the wearer does"})
        if self.wearer and self.has_sling:
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
                         f"panel + gusset + {self.bind_layers} x binding",
                         self.seam_mm))
            rows.append(("Mitred corner", "binding doubles", self.corner_mm))
        for face in ("front", "back"):
            n = self.panel_layers[face]
            if n > 1:
                rows.append((f"Bound seam, {face} panel",
                             f"{n} x panel + gusset + {self.bind_layers} x binding",
                             self.panel_seam_mm[face]))
                rows.append((f"Mitred corner, {face} panel", "binding doubles",
                             self.panel_seam_mm[face]
                             + self.bind_layers * self.bind_mm))
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
        if self.loops:
            rows.append(("Belt keeper box-X",
                         "keeper + panel + anchor" if self.loop_anchor
                         else "keeper + panel",
                         (3 if self.loop_anchor else 2) * self.shell_mm))
        # A tab is two layers of webbing folded through the ring. What is behind
        # it is either the chassis (another webbing) or a Cordura anchor.
        behind = WEBBING_MM if self.has_chassis else self.shell_mm
        tack = 2 * WEBBING_MM + self.shell_mm + behind
        backing = "internal webbing" if self.has_chassis else "anchor strip"
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
        mitres = self.square_corners * perims
        curves = self.curved_corners * perims
        bound = 4 * perims + (1 if self.has_divider and self.div_attach == "binding"
                              else 0)
        rows.append({"item": "Bound edges", "count": bound,
                     "note": f"{perims} panel perimeters"
                             + (" + the divider's top" if bound > 4 * perims else "")})
        rows.append({"item": "Mitred corners", "count": mitres,
                     "note": f"the thickest point on the bag — {self.peak_mm():.1f} mm "
                             "here, every one hand-wheeled"
                             + (f". {curves} more are rounded, and a curve needs "
                                "no mitre at all" if curves else "")})
        if curves:
            rows.append({"item": "Rounded corners", "count": curves,
                         "note": f"radius {frac(self.corner_r)} at the stitch line — "
                                 "no mitre, no clip, and the gusset runs straight "
                                 "through"})
        rows.append({"item": "Binding to sew", "count": frac(self.binding),
                     "note": f"{frac(self.bind_cut)} strip"
                             + (", cut on the BIAS" if self.bind_bias else
                                ", straight grain")
                             + f", {perims} joins to close, and it is the seam "
                               "that shows"})
        rows.append({"item": "Gusset corner clips", "count": mitres,
                     "note": "cut to the stitch line at each SQUARE corner, or the "
                             "gusset cannot turn it"})
        if curves:
            rows.append({"item": "Gusset relief clips", "count": self.relief_clips * curves,
                         "note": f"{self.relief_clips} along each arc. A flat strip's "
                                 "raw edge has to reach 25% further than its own "
                                 "stitch line round a convex curve, and nothing but "
                                 "relief lets it — shallow snips, not a deep clip"})
        nzip = 1 + len(self.pockets)
        rows.append({"item": "Zippers", "count": nzip,
                     "note": f"{2 * nzip} laps at two rows each = {4 * nzip} rows on "
                             f"tape, plus {1 + 2 * len(self.pockets)} new bar-tacked stops"})
        rows.append({"item": "Lap joins", "count": 2,
                     "note": "gusset to zipper panel, both at the top corners"})
        tacks = (self.loop_count if self.loops else 0) \
            + int(self.feat.get("d_rings", 0)) + (2 if self.flags["has_handle"] else 0)
        if self.has_chassis:
            tacks += 2
        rows.append({"item": "Box-X tacks", "count": tacks,
                     "note": "twice round each, hand-wheeled"})
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
        return (self.face_w, pk.reach - self.sa)

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
            "value": f"{HIP_TOLERANCE_RATIO:.2f}×",
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
        pad = max(self.sandwich_mm, *self.panel_sandwich_mm.values())             + self.bind_layers * self.bind_mm + 2 * 6.0
        rows.append({
            "measure": "Bound seam if the back panel were padded",
            "value": f"{pad:.1f} mm",
            "basis": f"6 mm of EVA is the usual back-panel figure. Through this "
                     f"construction's bound seam that is {pad:.1f} mm against a "
                     f"{STACK_STOP_MM:g} mm stop — a pad here has to float clear "
                     "of the binding or not exist"})
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
                      "u": float(self.flange), "v": float(TURN_IN + self.coil_c
                                                          - self.coil / 2),
                      "w": float(self.zip_face), "h": float(self.coil),
                      "label": f"coil, {frac(self.coil_c)} from the cut edge"})
        for face, pk in sorted(self.pockets.items()):
            feats.append({"kind": "zip", "derived": True, "face": face,
                          "u": float(self.flange),
                          "v": float(TURN_IN + pk.zip - pk.coil / 2),
                          "w": float(self.face_w), "h": float(pk.coil),
                          "label": f"{face} pocket, {frac(pk.zip)} from the "
                                   f"panel's cut edge"})
        if self.has_chassis:
            feats.append({"kind": "webbing", "derived": True, "ring": True,
                          "across_depth_in": float(TURN_IN + self.web_lo),
                          "width_in": float(self.web),
                          "overlap_in": float(self.overlap),
                          "label": f"{frac(self.loop)} chassis loop, inside the gusset"})
        if self.has_divider:
            fw, fh = self.face_size(self.div_face)
            feats.append({"kind": "pocket", "derived": True, "face": self.div_face,
                          "u": 0.0, "v": float(fh - TURN_IN - self.div_h),
                          "w": float(fw), "h": float(self.div_h + TURN_IN),
                          "interior": True,
                          "label": f"divider pocket, {frac(self.div_depth)} deep"
                                   + (f", {len(self.div_channels) + 1} channels"
                                      if self.div_channels else "")})
        for ft in self.spec.get("features", {}).get("placements", []):
            feats.append(dict(ft))
        return {
            "faces": {f: {"w": dim(self.face_size(f)[0]),
                          "h": dim(self.face_size(f)[1])} for f in FACES},
            "binding_show": dim(self.show),
            "flange": dim(self.flange),
            "corner_radius": dim(self.corner_cut_r),
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

        ck(self.gusset_face + self.zip_face == self.ring,
           "ring closes",
           f"gusset {frac(self.gusset_face)} + zip {frac(self.zip_face)} = {frac(self.ring)}")

        finished = (self.strip_front - self.lap) + self.coil + (self.strip_rear - self.lap)
        ck(finished == self.gusset_w, "zipper panel width matches the gusset",
           f"{frac(finished)} vs {frac(self.gusset_w)}")

        ck(self.face_d > 0 and self.face_w > 0 and self.face_h > 0,
           "faces are positive",
           f"{frac(self.face_w)} x {frac(self.face_h)} x {frac(self.face_d)}")

        worst_seam = max(self.seam_mm, *self.panel_seam_mm.values())
        worst_corner = worst_seam + self.bind_layers * self.bind_mm
        thick = [f"{f} at {k} layers" for f, k in sorted(self.panel_layers.items())
                 if k > 1]
        where = f" ({', '.join(thick)})" if thick else ""
        ck(worst_seam <= STACK_WARN_MM, "plain bound seam is drivable",
           f"{worst_seam:.1f} mm{where} (warn above {STACK_WARN_MM:g})")
        ck(worst_corner <= STACK_WARN_MM + 1, "mitred corner is drivable",
           f"{worst_corner:.1f} mm{where} -- hand-wheel anything over {STACK_WARN_MM:g}")
        if self.shell_frays:
            ck(True, "shell frays: raw edges need folding",
               "zip laps, rib edges, pocket tops, gusset joins")

        ck(self.coil_c - self.coil / 2 - self.sa >= F(1, 4),
           "coil clears the binding flange",
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
            rebuilt = (pk.upper - pk.lap) + pk.coil + (pk.lower - pk.lap)
            ck(rebuilt == self.panel_h, f"{face} pocket reassembles to the panel",
               f"{frac(rebuilt)} vs {frac(self.panel_h)}")
            near = min(pk.zip, self.panel_h - pk.zip) - pk.coil / 2
            ck(near - self.sa >= F(1, 4), f"{face} pocket coil clears the binding",
               f"{frac(near - self.sa)} of visible shell to the nearest edge")
            ck(pk.reach >= 2, f"{face} pocket is deep enough to hold anything",
               f"{frac(pk.reach)} below the opening")
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
            keys = {f: pk.key() for f, pk in self.pockets.items()}
            same = len(set(keys.values())) == 1
            ck(same, "panel pockets agree",
               "identical outer pieces front and back, so they cut as pairs and "
               "one step states them all" if same else
               "the zip heights differ, so the outer pieces are four singletons "
               "and no single step can describe them: " + str(keys))

        if self.corner_r:
            ok_r = self.corner_r >= self.show
            ck(ok_r, "the corner radius can take a binding",
               f"{frac(self.corner_r)} radius against a {frac(self.show)} show"
               if ok_r else
               f"{frac(self.corner_r)} is tighter than the {frac(self.show)} the "
               "binding shows, so it cannot lie round the curve")
            lim = min(self.face_w, self.face_h) / 2
            ck(self.corner_r <= lim, "the corner radius leaves a straight run",
               f"{frac(self.corner_r)} of a {frac(lim)} maximum — beyond half the "
               "shorter face the curves meet and there is no flat edge left")
            ck(self.bind_bias, "a curved corner is bound on the bias",
               "straight grain has no give, and the binding's outer edge has to "
               f"travel {frac(round_to(self.show * F(31416, 20000), 16))} further "
               "than its stitch line round each quarter turn")

        if self.has_divider:
            # A divider caught in the binding has to be cut round any rounded
            # corner it reaches into; topstitched clear of the seam, it does not.
            if self.div_attach == "binding" and self.corner_r:
                ck(False, "the divider clears the rounded corners",
                   "it is caught in the binding and reaches the bottom corners, so "
                   "its own corners have to be cut to the radius — topstitch it "
                   "clear instead")
            # It has to stop short of the mouth or you cannot get past it to
            # reach the main compartment at all.
            ck(self.div_clear >= 1, "the divider leaves room to reach past it",
               f"{frac(self.div_clear)} of open panel above it")
            ck(self.div_depth >= 2, "the divider pocket is deep enough to hold",
               f"{frac(self.div_depth)} deep")
            face_w = self.face_size(self.div_face)[0]
            edges = ([self.flange] + sorted(self.div_channels)
                     + [face_w - self.flange])
            widths = [b - a for a, b in zip(edges, edges[1:])]
            bad = [frac(w) for w in widths if w < 1]
            ck(not bad, "every divider channel is wide enough to use",
               ", ".join(bad) + " — a channel narrower than 1\" holds nothing"
               if bad else
               f"{len(widths)} channel(s): " + " · ".join(frac(w) for w in widths))
            ck(all(self.flange < c < face_w - self.flange for c in self.div_channels),
               "divider channels sit inside the binding",
               f"{len(self.div_channels)} line(s) on a {frac(face_w)} face")

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
                zip_top = TURN_IN + self.bp_zip - self.bp_coil / 2
                low = [ft for ft in self.spec.get("features", {}).get("placements", [])
                       if ft.get("kind") == "belt-loop" and ft.get("face") == "back"
                       and F(str(ft["v"])) + F(str(ft.get("h", 0))) > zip_top]
                ck(not low, "belt load bypasses the pocket zip",
                   f"{len(low)} keeper(s) reach below the zip at {frac(zip_top)}"
                   if low else
                   f"every keeper sits above the zip line, so the tack goes "
                   f"through to the inner panel and the zip carries nothing")

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
                ck(self.bp_band >= self.loop_for + F(1, 2),
                   "keepers fit clear of the pocket zip",
                   f"{frac(self.bp_band)} of band for a {frac(self.loop_for)} belt "
                   f"(want the belt plus ½\" for the tacks)")

        if self.wearer and self.loops:
            # The belt has to close round the smallest declared wearer with the
            # bag ON it, and the buckle and slider need somewhere to sit that
            # is not underneath the bag.
            spare = self.waist[0] - self.panel_w
            ck(spare >= 4, "the bag fits the smallest declared wearer",
               f"{frac(spare)} of waist left outside the bag at "
               f"{frac(self.waist[0])} (buckle and tri-glide want 4\")")
            # NOT "does the belt reach the largest fit" -- the belt is DERIVED
            # from that fit, so such a check can only ever pass and would be
            # a check of nothing. What is declared, and therefore checkable, is
            # the tail: a side-release buckle and a tri-glide consume length,
            # and what is left has to be enough to grip and pull.
            ck(self.belt_tail >= 4, "the belt has tail enough to adjust",
               f"{frac(self.belt_tail)} beyond a {frac(self.fit_max)} "
               f"{'waist' if self.has_sling or not self.crossbody else 'crossbody'}"
               " — the buckle and tri-glide eat into it")

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
        CAUGHT = {"pocket", "rib", "zip", "webbing"}
        under = []
        for ft in self.model3d()["features"]:
            if ft.get("kind") in CAUGHT or not ft.get("face"):
                continue
            rect = self._placement_rect(ft)
            if rect is None:
                continue
            fw, fh = (float(x) for x in self.face_size(ft["face"]))
            fl = float(self.flange)
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
           f"all clear of the {frac(self.flange)} flange")

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
        a(f"  face (between flanges)  {frac(self.face_w)} x {frac(self.face_h)}"
          f"   depth {frac(self.face_d)}")
        a(f"  seam allowance {frac(self.sa)}   flange {frac(self.flange)}"
          f"   binding shows {frac(self.show)}")
        if self.corner_r:
            a(f"  bottom corners round at {frac(self.corner_r)}"
              f" ({frac(self.corner_cut_r)} at the cut edge)"
              f" — {self.curved_corners * 2} fewer mitres, {self.curved_corners * 2}"
              " fewer clips, bias binding")
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
        a(f"  BINDING ({shell})")
        fold = "DOUBLE fold" if self.double_fold else "single fold"
        layers = 4 if self.double_fold else 2
        a(f"    material           {self.bind_mat}  ({fold}, {layers} layers/seam)")
        extra = " + 3/4 to fold under" if self.double_fold else ""
        worst = max(self.sandwich_mm, *self.panel_sandwich_mm.values())
        a(f"    strip width        {frac(self.bind_cut)}   (2 x show + "
          f"{worst:.2f} mm sandwich + turn{extra})")
        a(f"    length needed      {frac(self.binding)}  -> buy {frac(self.binding_buy)}")
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
                  f" x {frac(RING_ANCHOR_W_IN)}   (across the gusset, ends in the bindings)")
        if self.wearer and self.has_sling:
            a(f"    sling strap        1 @  {frac(self.sling_cut)}"
              f"   ({frac(self.crossbody)} crossbody + hardware take-up)")
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
            a(f"  PANEL POCKETS ({self.panel_mat})   {' and '.join(sorted(self.pockets))}"
              f"   zip {frac(self.bp_zip)} from the cut edge")
            a(f"    panel, full size   2 @  {frac(self.panel_w)} x {frac(self.panel_h)}"
              f"   (the inner layer -- seals the compartment)")
            a(f"    outer, upper       {n} @  {frac(self.panel_w)} x {frac(self.bp_upper)}")
            a(f"    outer, lower       {n} @  {frac(self.panel_w)} x {frac(self.bp_lower)}")
            for f in sorted(self.pockets):
                pw, pd = self.pocket_interior(f)
                a(f"    {f} cavity         {frac(pw)} x {frac(pd)} below the opening")
        if self.has_divider:
            a("")
            a(f"  DIVIDER ({shell})   flat against the {self.div_face} panel's interior")
            a(f"    divider pocket     1 @  {frac(self.div_w)} x {frac(self.div_h)}"
              f"   ({frac(self.div_depth)} deep, {frac(self.div_clear)} clear above)")
            if self.div_channels:
                fw = self.face_size(self.div_face)[0]
                edges = [self.flange] + sorted(self.div_channels) + [fw - self.flange]
                ch = " / ".join(frac(b - a_) for a_, b in zip(edges, edges[1:]))
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
                      "note": ""},
                     {"role": "binding", "material": self.bind_mat,
                      "thickness_mm": self.bind_mm, "frays": self.bind_frays,
                      "note": ("DOUBLE fold -- it frays, so its outer edge turns "
                               "under and every seam carries four layers"
                               if self.double_fold else
                               "single fold -- it does not fray, so the outer "
                               "edge stays raw")}]
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
    if spec.get("construction") != "box-bound":
        raise ValueError(f"{path.name}: construction must be 'box-bound'")
    if spec.get("name") != path.stem:
        raise ValueError(f"{path.name}: name must match the filename")
    return BoxBag(spec)


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
            g = bag.geometry
            print(f"{bag.name}")
            for k in sorted(g):
                print(f"  {{{k}}}".ljust(22) + frac(g[k]))
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
