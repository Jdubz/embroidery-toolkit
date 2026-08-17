# Box-bound bags — the parametric family

**Four bags, one construction.** Two flat panels, a gusset ring wrapping their
perimeter, a zipper panel forming one face of that ring, and binding wrapping
every raw edge. Change the finished envelope and every cut size follows.

| Bag | Finished | Carried by |
|---|---|---|
| [`StadiumTote_12x12x4`](StadiumTote_12x12x4.md) | 11⅞ × 4⅛ × 11½ | Crossbody, backpack or hand |
| `SlingPack_13x7x4` | 13 × 4 × 7 | Crossbody sling |
| `HipPack_10x6x3` | 10 × 3 × 6 | Waist belt |
| `BeltPouch_4x6` | 4½ × 2 × 6½ | A belt you already own |

Dimensions are **declared**, in `patterns/specs/<Name>.json`. Cut lists are
**derived**, by `tools/bag_pattern.py`. Nothing below is hand-computed.

```
py tools/bag_pattern.py --all --check
```

---

## Why this is a generator and not four cut lists

Five revisions of the StadiumTote each moved a number that only re-deriving the
geometry caught — a ring measured at the raw-edge perimeter instead of the
stitch-line perimeter, a zipper strip whose width changed twice as the binding
came and went, a vinyl requirement that had never actually been nested. A bad
stitch file costs a rebuild; **a bad cut costs material.**

The generator was validated the way this repo validates every new check: **run it
against a known-good file first.** It reproduces all of StadiumTote's
hand-computed figures exactly — panels 11¾ × 11⅜, ring 43¼, zipper strips 1⅜ and
3⅜, coil at 1", binding strip 1⅛. If it had disagreed, the generator was wrong.

Then it immediately failed two of the three new sizes, which is the point.

## The geometry, once

```
face   = overall − 2 × flange      the visible panel between flanges
cut    = face + 2 × SA             what you actually cut
flange = SA + turn                 SA ⅜", turn 1/16" for the binding itself
ring   = 2 × (face_w + face_h)     the STITCH-LINE perimeter, not the raw one
```

A ring cut to the raw-edge perimeter is 8 × SA too long — **3 inches on a 12-inch
bag**, eased into a seam that cannot take it. That is the mistake this whole file
exists to make impossible.

Full explanation of the bound seam itself: **[`techniques/binding.md`](techniques/binding.md)**.

## Two things the generator caught that I would not have

**The hip pack could not fit 1" webbing beside its zipper.** At 3" of depth the
gusset face is 2⅛", and a 1" chassis loop centred on it leaves the coil only ⅛"
of shell outboard — the slider would rub the binding. Dropped to **¾" webbing**,
which is what small packs use anyway.

**The belt pouch could not fit a chassis at all.** At 2" of depth the coil and the
webbing physically overlap — the check reported a **negative** gap. The fix was
not a fudge but a design distinction worth stating:

> **A chassis is for bags carried by straps.** It exists to take load off the
> shell and put it in a webbing loop round the girth. A belt pouch is carried by
> the belt — the load path is belt → loop → back panel, and never crosses the
> gusset. It needs no chassis, and below about 2½" of depth there is no room for
> one beside the zipper anyway.

Declared as `"chassis": null`. The coil then simply sits centred, and the two
zipper strips come out symmetrical.

## Swapping the shell material

Declare it. `"shell"` and `"binding": {"material": ...}` both feed the geometry —
thickness sets the sandwich the binding wraps, and **whether the material frays
decides single or double fold**, which doubles the layers at every seam.

A shell swap that looks like a taste decision moves both. The StadiumTote went
from Cordura to 12 oz denim and the generator caught it immediately:

| Binding | Layers/seam | Plain seam | Mitred corner |
|---|---|---|---|
| Denim, double fold | 4 | 4.3 mm | **7.3 mm — fails** |
| Nylon tape, single fold | 2 | 2.3 mm | 3.3 mm ✓ |

**The binding does not have to match the shell, and with a fraying shell it must
not.** Known materials are in `MATERIALS` in `tools/bag_pattern.py`; add a row
rather than guessing a thickness.

---

## Sizing guide

| Size | Holds | Notes |
|---|---|---|
| **4½ × 2 × 6½** belt pouch | Large phone, cards, keys | Also the largest non-clear bag most stadium policies allow alongside a clear one — a bonus, not a driver |
| **10 × 3 × 6** hip pack | Phone, wallet, keys, a drink pouch | The standard hip-pack proportion |
| **13 × 4 × 7** sling | Small tablet, packed jacket | Wears across the chest or on the hip |
| **12 × 6 × 12** | — | The ceiling most stadium clear-bag policies set, if that ever matters to you |

**Depth is the constraint that bites first.** Below ~2½" a webbing chassis stops
fitting beside the zipper; below ~1½" the gusset face gets too narrow to bind
cleanly. Width and height scale freely.

## What changes with size, and what does not

| Scales | Fixed |
|---|---|
| Panels, gusset, ring, chassis loop, binding length | Seam allowance ⅜" |
| Zipper strip widths | Binding shows ½" each face, strip 1⅛" |
| Number of D-rings | Stitch schedule — see StadiumTote |
| Webbing width | The bound-seam method itself |

The **stitch schedule, lock-off policy, tool list and machine setup** in
[`StadiumTote_12x12x4.md`](StadiumTote_12x12x4.md) apply unchanged to all four.
They are properties of the materials and the machine, not of the size.

## Belt loop — the pouch's one extra piece

A Cordura loop on the back panel, cut **2 × (belt width) + 1½"**, so a 2" belt
takes a 2 × 5½" piece. Fold, and box-X both ends to the back panel **before** it
goes into the gusset ring, so the binding catches nothing but the panel edge.

Size it to the belt you own. A loop cut for a 1½" belt will not go over a 2" one,
and one cut for 2" flaps on a 1½".

---

## The cut lists live in the player now

They used to be pasted into this file, which made them a copy that nothing
checked — and that is exactly how the one defect this family has shipped
survived. `frac()` concatenated a whole number straight onto a textual
sixteenth, so **1 5/16" printed as `15/16"`** and the BeltPouch's two zipper
strips were published ⅜" under their true width in every cut list this repo
had generated.

The geometry was right the whole time. The ring closed, the zipper panel
matched the gusset, every check passed, and a regression run against the block
that used to sit below this line passed too — because that block had been
printed by the same function being tested. **A known-good file validates the
geometry, not the presentation.** `tools/tests/test_patterns.py` asserts on
`Fraction` values now, which is the form that cannot lie.

```powershell
py tools\bag_pattern.py --all                    # read them here
py tools\bag_pattern.py --all --package          # build\patterns\*.json
py tools\pattern_player.py --open                # the player
```

The player carries all four bags, the 3D preview, the cut list, the nesting
layout, the assembly order and the technique notes — see
[`SCHEMA.md`](SCHEMA.md) for how a pattern is declared and what gets derived.

<!-- The block below is kept ONLY as the historical record of what was
     published before the frac() fix. It is not current and must not be
     regenerated into. -->
<details>
<summary>The figures as they were published, before the separator fix</summary>

```
BeltPouch_4x6
=============
  finished overall   4½" W x 2" D x 6½" H
  face (between flanges)  3⅝" x 5⅝"   depth 1⅛"
  seam allowance ⅜"   flange 7/16"   binding shows ½"

  PANELS (cordura-1000d)
    front, back        2 @  4⅜" wide x 6⅜" tall

  GUSSET RING (cordura-1000d)   ring at the stitch line = 18½"
    gusset             1 @  1⅞" x 15⅞"   (cut long: 18⅞")
    zip strip, front   1 @  15/16" x 4⅝"
    zip strip, rear    1 @  15/16" x 4⅝"
    coil sits 15/16" from the panel's cut edge

  BINDING (cordura-1000d)
    material           cordura-1000d  (single fold, 2 layers/seam)
    strip width        1⅛"   (2 x show + 1.00 mm sandwich + turn)
    length needed      43"  -> buy 51½"

  WEBBING
    no chassis         carried by the belt, not by straps
    belt loop (cordura-1000d)  1 @  2" x 5½"   (fits a 2" belt)

  CHECKS
    ok    ring closes                                  gusset 14⅞" + zip 3⅝" = 18½"
    ok    zipper panel width matches the gusset        1⅞" vs 1⅞"
    ok    faces are positive                           3⅝" x 5⅝" x 1⅛"
    ok    plain bound seam is drivable                 2.0 mm (warn above 5)
    ok    mitred corner is drivable                    3.0 mm -- hand-wheel anything over 5
    ok    coil clears the binding flange               7/16" of visible shell outboard

HipPack_10x6x3
==============
  finished overall   10" W x 3" D x 6" H
  face (between flanges)  9⅛" x 5⅛"   depth 2⅛"
  seam allowance ⅜"   flange 7/16"   binding shows ½"

  PANELS (cordura-1000d)
    front, back        2 @  9⅞" wide x 5⅞" tall

  GUSSET RING (cordura-1000d)   ring at the stitch line = 28½"
    gusset             1 @  2⅞" x 20⅜"   (cut long: 23⅜")
    zip strip, front   1 @  1⅛" x 10⅛"
    zip strip, rear    1 @  2½" x 10⅛"
    coil sits ¾" from the panel's cut edge

  BINDING (cordura-1000d)
    material           cordura-1000d  (single fold, 2 layers/seam)
    strip width        1⅛"   (2 x show + 1.00 mm sandwich + turn)
    length needed      63"  -> buy 75½"

  WEBBING
    chassis loop       1 @  31½"   (28½" ring + 3" overlap)
    D-ring tabs        2 @  4"
    grab handle        1 @  8"

  CHECKS
    ok    ring closes                                  gusset 19⅜" + zip 9⅛" = 28½"
    ok    zipper panel width matches the gusset        2⅞" vs 2⅞"
    ok    faces are positive                           9⅛" x 5⅛" x 2⅛"
    ok    plain bound seam is drivable                 2.0 mm (warn above 5)
    ok    mitred corner is drivable                    3.0 mm -- hand-wheel anything over 5
    ok    coil clears the binding flange               ¼" of visible shell outboard
    ok    coil clears the webbing                      gap 3/16" (want 1/8" or more)
    ok    chassis overlap lands on the top face        3" of overlap
    ok    overlap is at least 3x the webbing width     3" vs 2¼"

SlingPack_13x7x4
================
  finished overall   13" W x 4" D x 7" H
  face (between flanges)  12⅛" x 6⅛"   depth 3⅛"
  seam allowance ⅜"   flange 7/16"   binding shows ½"

  PANELS (cordura-1000d)
    front, back        2 @  12⅞" wide x 6⅞" tall

  GUSSET RING (cordura-1000d)   ring at the stitch line = 36½"
    gusset             1 @  3⅞" x 25⅜"   (cut long: 28⅜")
    zip strip, front   1 @  1¼" x 13⅛"
    zip strip, rear    1 @  3⅜" x 13⅛"
    coil sits ⅞" from the panel's cut edge

  BINDING (cordura-1000d)
    material           cordura-1000d  (single fold, 2 layers/seam)
    strip width        1⅛"   (2 x show + 1.00 mm sandwich + turn)
    length needed      79"  -> buy 94¾"

  WEBBING
    chassis loop       1 @  40½"   (36½" ring + 4" overlap)
    D-ring tabs        4 @  4"
    grab handle        1 @  10"

  CHECKS
    ok    ring closes                                  gusset 24⅜" + zip 12⅛" = 36½"
    ok    zipper panel width matches the gusset        3⅞" vs 3⅞"
    ok    faces are positive                           12⅛" x 6⅛" x 3⅛"
    ok    plain bound seam is drivable                 2.0 mm (warn above 5)
    ok    mitred corner is drivable                    3.0 mm -- hand-wheel anything over 5
    ok    coil clears the binding flange               ⅜" of visible shell outboard
    ok    coil clears the webbing                      gap 7/16" (want 1/8" or more)
    ok    chassis overlap lands on the top face        4" of overlap
    ok    overlap is at least 3x the webbing width     4" vs 3"

StadiumTote_12x12x4
===================
  finished overall   11⅞" W x 4⅛" D x 11½" H
  face (between flanges)  11" x 10⅝"   depth 3¼"
  seam allowance ⅜"   flange 7/16"   binding shows ½"

  PANELS (vinyl-20ga)
    front, back        2 @  11¾" wide x 11⅜" tall

  GUSSET RING (denim-12oz)   ring at the stitch line = 43¼"
    gusset             1 @  4" x 33¼"   (cut long: 36¼")
    zip strip, front   1 @  1⅜" x 12"
    zip strip, rear    1 @  3⅜" x 12"
    coil sits 1" from the panel's cut edge

  BINDING (denim-12oz)
    material           nylon-binding-tape  (single fold, 2 layers/seam)
    strip width        1⅛"   (2 x show + 1.26 mm sandwich + turn)
    length needed      92½"  -> buy 111"

  WEBBING
    chassis loop       1 @  47¼"   (43¼" ring + 4" overlap)
    D-ring tabs        6 @  4"
    grab handle        1 @  12"

  CHECKS
    ok    ring closes                                  gusset 32¼" + zip 11" = 43¼"
    ok    zipper panel width matches the gusset        4" vs 4"
    ok    faces are positive                           11" x 10⅝" x 3¼"
    ok    plain bound seam is drivable                 2.3 mm (warn above 5)
    ok    mitred corner is drivable                    3.3 mm -- hand-wheel anything over 5
    ok    shell frays: raw edges need folding          zip laps, rib edges, pocket tops, gusset joins
    ok    coil clears the binding flange               ½" of visible shell outboard
    ok    coil clears the webbing                      gap ⅜" (want 1/8" or more)
    ok    chassis overlap lands on the top face        4" of overlap
    ok    overlap is at least 3x the webbing width     4" vs 3"
    ok    within the declared limit 12x6x12            11⅞" x 4⅛" x 11½"
```

</details>

---

*Schema:* [`SCHEMA.md`](SCHEMA.md) ·
*Technique:* [`techniques/binding.md`](techniques/binding.md) ·
*Generator:* `tools/bag_pattern.py` · *Player:* `tools/pattern_player.py` ·
*Specs:* `patterns/specs/` · *Construction:* `patterns/constructions/`
