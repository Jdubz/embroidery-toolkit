# Box-bound bags — the parametric family

**Four bags, one construction.** Two flat panels, a gusset ring wrapping their
perimeter, a zipper panel forming one face of that ring, and binding wrapping
every raw edge. Change the finished envelope and every cut size follows.

| Bag | Finished | Carried by |
|---|---|---|
| [`StadiumTote_12x12x4`](StadiumTote_12x12x4.md) | 11⅞ × 4⅛ × 11½ | Crossbody, backpack or hand |
| `SlingPack_13x7x4` | 13 × 4 × 7 | Crossbody sling |
| `HipPack_10x7x4` | 10 × 3 × 6 | A waist belt and a shoulder strap you already own |
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
face    = overall − 2 × flange     the STITCH-LINE box — not what you can see
cut     = face + 2 × SA            what you actually cut
flange  = SA + turn                finished edge to the stitch line
ring    = 2 × (face_w + face_h)    the stitch-line perimeter, not the raw one
visible = overall − 2 × show       the cloth between the bindings — size artwork to THIS
```

A ring cut to the raw-edge perimeter is 8 × SA too long — **3 inches on a 12-inch
bag**, eased into a seam that cannot take it. That is the mistake this whole file
exists to make impossible.

**`face` is not the visible cloth, and this file used to say it was.** The
binding shows `show` on each face, and its inner edge therefore lands one `turn`
PAST the stitch line — it has to lap over the stitching, or the single line
holding the seam sits on the binding's own edge. So the cloth you can see is
`overall − 2 × show`, an eighth of an inch smaller each way than `face`. The two
were confused because the defaults make them numerically equal *by accident*:
`flange = SA + turn` equals `show − turn` only while `SA = show − 2 × turn`, which
⅜, ½ and 1/16 happen to satisfy. Change the seam allowance and they separate.

It mattered: the gusset was quoted as showing 2⅛" when it shows 2", and a name
sized to that was 51.6 mm wide on 50.8 mm of cloth. **Size artwork to
`visible_*`, and read `face` only as the stitch line.**

**And sew the binding at SA from the RAW EDGES.** Guiding on the binding's inner
edge at ⅛" — which the stitch schedule said for a long time — puts the needle at
5/16", which is precisely the drift step 1 tells you to measure for.

Full explanation of the bound seam itself: **[`techniques/binding.md`](techniques/binding.md)**.

## Three things the generator caught that I would not have

**The hip pack could not fit 1" webbing beside its zipper.** At 3" of depth the
gusset face is 2⅛", and a 1" chassis loop centred on it leaves the coil only ⅛"
of shell outboard — the slider would rub the binding. It went to ¾" webbing
first, and then the whole chassis came out: the pack is carried by a belt
through keepers, so its load path is belt → keepers → back panel → bound seam
and never touches the gusset. The coil re-centred, both zip strips came out
equal, and the belt's width stopped being a clearance problem and became a
comfort one — which is the only reason it could be argued up to 1" on the
pressure figures. **That bag has no webbing on it at all now**, and the
zipper-panel step is written twice for exactly that reason.

**Both pieces of the ring were being cut long, so it closed an inch over.**
Two strips lapped by L cover their combined length *less* L, so only one of the
pair may carry lap allowance. Both did. The zipper panel keeps it — `zip_face`
is the opening and has to survive being lapped over at each end — and the
gusset is trimmed to the bare ring figure. The check that should have caught
this asserted `gusset_face + zip_face == ring`, which is a restatement of the
line that *defines* `gusset_face`; it could never fail, and it sat there
passing while all four bags cut a ring that would not close. **A check has to
be able to fail.** It now tests what gets cut against what gets lapped away.

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

**Whether a shell ravels is what decides if it can bind itself**, and on a
doubled-panel bag that is the difference between buildable and not. The hip
pack in 600D PU-coated polyester binds in its own cloth at a 3.2 mm mitre; the
same bag in an uncoated 12 oz duck of almost the same thickness is forced to
double-fold and lands at **7.7 mm, past the 6 mm a domestic machine stops at**.
One material, one fabric line, no tape — but only because the coating locks
the weave.

**`frays` and `melt_seal` are separate columns for the same reason.** Fraying
decides whether an edge is turned under and whether the binding doubles.
Melt-sealing decides only how a piece is *cut*. Cordura is both, which is how
"Cordura seals, so no edge of it needs a hem" got written into a construction
step as a single fact — and that step was then wrong in both directions for a
coated cotton, which neither ravels nor melts.

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

A loop in the shell fabric on the back panel, cut **2 × (belt width) + 1½"**, so a 2" belt
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

**The cut lists are not in this file and must not be pasted back into it.** A block of them lived here as a "historical record" and it outlived its usefulness in three separate ways at once: every hip-pack figure in it predated that bag's redesign, every gusset figure predated the lap-allowance fix above, and it printed `PANELS (cordura-1000d)` and `BINDING (cordura-1000d)` in a block that reads exactly like a cut list — so opening it in the player next to a bag now cut entirely from 600D canvas said the material was Cordura. It was a copy nothing checked, which is the thing this file already says causes the one defect this family has shipped. Deleted. Run the generator.

---

*Schema:* [`SCHEMA.md`](SCHEMA.md) ·
*Technique:* [`techniques/binding.md`](techniques/binding.md) ·
*Generator:* `tools/bag_pattern.py` · *Player:* `tools/pattern_player.py` ·
*Specs:* `patterns/specs/` · *Construction:* `patterns/constructions/`
