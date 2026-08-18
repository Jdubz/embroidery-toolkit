# StadiumTote 12×12×4 — clear vinyl windows, canvas shell, modular straps

A zip-top tote for venues enforcing an NFL-standard clear bag policy. **Two clear
vinyl panels as windows; the entire gusset ring — sides, bottom and zipper panel
— in 600D PU-coated polyester canvas, bound in its own cloth.** A single unbroken webbing loop runs the bag's whole
circumference **inside** the gusset and carries every load: the six D-rings tack
through to it from outside, so nothing weight-bearing touches the PVC and the
gusset exterior stays clean enough to embroider. Removable straps give crossbody, backpack or hand-carry,
and three internal pockets keep small items off the bottom.

No leather, no serger.

**The shell does not fray, so it binds itself** — which is what keeps this
buildable at two layers a seam instead of four. See *Materials* below before
cutting; the reasoning matters more than the conclusion, because it inverts if
you ever swap the cloth.

Built on a **Singer Heavy Duty 4423** with a walking or Teflon foot.

---

## Geometry — read this before cutting anything

Everything below follows from one convention, and getting it wrong is how this
pattern went wrong once already.

| | |
|---|---|
| **Seam allowance** | **3/8"** — raw edge to the binding's stitch line |
| **Flange** | The SA does not turn inward. Both pieces' allowances lie together pointing **outward**, wrapped in binding, projecting ~7/16" past the stitch line |
| **Face** | The visible panel between flanges = cut size − 2 × SA |
| **Overall** | face + 2 × flange projection ≈ cut size + 1/8" |

**A bound seam still needs a seam allowance.** The binding *encases* the raw edges
of an allowance; it does not replace one. Standard practice for a bound seam is
3/8"–5/8", and anything narrower gives the binding nothing to grip.

Because the allowance becomes an outward flange rather than being turned in, the
**cut size is very nearly the overall finished size** — but the *interior* is a
full ¾" smaller in each direction, and the **gusset ring follows the stitch-line
perimeter, not the raw-edge perimeter.**

### The numbers this produces

| | |
|---|---|
| Panel cut | **11¾" wide × 11⅜" tall** |
| Panel face (between flanges) | 11" × 10⅝" |
| Gusset cut width | **4"** |
| Gusset face (depth) | 3¼" |
| **Ring at the stitch line** | **2 × (11" + 10⅝") = 43¼"** |
| **Overall exterior** | **11⅞" W × 4⅛" D × 11½" H** |

Against the 12 × 6 × 12 limit that leaves ⅛" on width, ½" on height and nearly 2"
on depth. *Panels are 11¾" rather than 12" precisely so the flange fits inside the
limit — cut them at 12" and the bag measures 12⅛" and is over.*

**The panel is no longer square.** The vinyl came 11⅜" across, so that dimension
becomes the panel **height** and the 11¾" width runs along the roll. The bag
loses ⅜" of height and nothing else: width, depth, the whole zipper panel, every
D-ring position and the handle are all unchanged, because none of them keys off
the height. Compliance improves — there is now ½" of margin on height instead of ⅛".

---

## Compliance

This is the standard construction for commercially sold approved totes: clear
panels with a solid fabric bottom and trim. The bottom and sides do **not** have
to be clear.

What actually gets a bag refused, from the published rejection criteria:

- a **large non-transparent logo** obscuring the view of contents
- **tint, holograms, printed patterns or stickers** on the clear areas
- the bag not reading as a clear bag at a glance

**The logo therefore goes on the gusset, not on a panel.** That leaves the front
window at 100% and removes the one rejection cause that names a specific feature.

The mental model: *"a security guard will look into your clear bag and may ask you
to shift items around if the bottom is obstructed."* **They look in from the top.**
An opaque base is irrelevant; the large windows are what matters.

Concert policies at stadiums usually mirror the NFL rule but not always. The
venue's own published policy is the authority — check it before cutting.

---

## Materials — the shell does not fray, and that decides everything

The shell is **600D PU-coated polyester canvas**, the same cloth as every other
bag in this family. It went through two earlier answers and the history is worth
keeping, because each one was rejected for a measurable reason.

**Cordura 1000D** was first: stiff, and unpleasant to embroider.

**12 oz denim** was second, and it is a first-rate embroidery substrate —
stable, hoops flat, no coating to gum a needle. But it **frays**, and this design
leaned on "nothing frays" in more places than was obvious. A fraying binding has
to be **double fold**, its outer edge turned under, which puts four layers at
every seam instead of two:

| Binding | Layers/seam | Plain seam | **Mitred corner** |
|---|---|---|---|
| Denim, bound in itself | 4 | 4.3 mm | **7.3 mm — will not drive** |
| Denim, bound in nylon tape | 2 | 2.3 mm | 3.3 mm ✓ |
| **600D canvas, bound in itself** | **2** | **1.86 mm** | **2.76 mm** ✓ |

So denim needed a second material bought purely to work around the first one's
fraying. The canvas does not: the coating locks the weave, a cut edge does not
ravel, and the binding comes off the same roll as the shell. **One cloth, one
purchase, and the thinnest seams the bag has ever had.**

`tools/tests/test_patterns.py` keeps the denim case alive on a variant, in both
directions — a fraying shell bound in itself still fails at 7.3 mm, and binding
it in tape still fixes it. The rule did not stop being true; this bag stopped
being denim.

### Not waxed canvas

Waxed canvas was a candidate and it is the wrong one here. **Every needle that
goes through it leaves a permanent mark** — this design already has one material
where every hole is forever, and a second doubles the surface where a mistake
cannot be undone. It also scrapes wax onto the feed dogs and needle, and it is
the *worse* embroidery substrate.

### What the coating changes

| | |
|---|---|
| **No pre-wash.** Polyester does not shrink, and there is nothing to soften. The step is gated on `shell_frays` and this bag no longer gets it | |
| **No folding raw edges under.** Nothing ravels, so the four edges that used to need ¼" pressed under go back to their plain cut sizes — the zip strips are 1⅜/3⅜ again, not 1⅝/3⅝ | |
| **Rotary-cut, and do not iron.** The cloth melt-seals, so a hot knife *works*, but on a coated face it can leave a hard bead — test on a scrap. Heat is what the waterproofing cannot survive, so there is no pressing anywhere in this build | |
| **A smaller needle.** 600D is half the yarn of a 1000D and every hole is permanent in the coating, so the schedule calls a **Microtex 90/14** throughout rather than a jeans 100/16 | |
| **Abrasion drops.** 600D is roughly half a 1000D. The base wear strip is still recommended, and it is canvas now rather than Cordura | |

Full coated-substrate handling — hooping, stabilizer, sealing needle holes — is
in [`docs/05-materials-and-consumables.md`](../docs/05-materials-and-consumables.md).

---

## Cut list — clear vinyl (rotary cutter)

| Piece | Qty | Cut size |
|---|---|---|
| Front panel | 1 | **11¾" wide × 11⅜" tall** |
| Back panel | 1 | **11¾" wide × 11⅜" tall** |
| Back-panel pocket | 1 | **11¾" × 6½"** |
| Small-items pocket | 1 | **3" × 4½"** |

**Needs a piece 11⅜" × 36".** The panels take 23½" of length, the back pocket
another 11¾", and the small pocket nests in the offcut above it.

The back-panel pocket is cut to the **panel's full width**, because its bottom and
both sides are caught in the panel's binding rather than being seamed.

## Cut list — 600D canvas (rotary cutter)

| Piece | Qty | Cut size | Purpose |
|---|---|---|---|
| Gusset | 1 | **4" × 35¼"** — *cut long, trim to 32¼"* | Sides and bottom |
| Zipper strip, front | 1 | **1⅜" × 12"** | Narrow side of the coil |
| Zipper strip, rear | 1 | **3⅜" × 12"** | Wide side |
| Binding strip | 2 | **1⅛" × 55½"** | Same cloth — the shell does not ravel |
| Divider rib | 1 | **1¼" × 11⅜"** | Topstitched both long edges → ¾" finished |
| Discreet pocket panel | 1 | **3½" × 11"** | Edges left raw; nothing ravels |
| Base wear strip *(recommended)* | 1 | **4" × 11¾"** | Exterior of the bottom face |

**The gusset is cut long on purpose.** Its finished length is **32¼"** — two
side faces of 10⅝" and a bottom of 11" — and that is also what you trim it
*to*. It gets **no** lap allowance, because the zipper panel already carries it:
two strips lapped by ½" cover their combined length *less* ½", so adding ½" at
each end of both pieces makes the ring close a full inch over. *(This file said
"plus ½" of lap at each end, so 33¼" in theory" for five revisions, and the
generator did the same arithmetic. The check that was supposed to catch it could
not — see `BoxBound_family.md`.)* In practice the ring's true length depends on
the seam allowance you actually achieve and on how tightly the binding pulls,
which is why good patterns give more than the calculation and let you trim.
**Fit the ring to the back panel and trim before you close it.**

**Zipper panel:** 11" of face plus ½" lap at each end = **12"** long — the only
piece carrying that allowance.

**Ring check:** gusset 32¼" + zipper panel 12" − two ½" laps = **43¼"**. ✓

**The coil is deliberately off-centre**, sitting **1" from the panel's cut edge —
½" of visible canvas outboard of it.** That clears the face's centreline so the
webbing can run straight down it. Each strip laps ½" onto the tape, so
(1⅜ − ½) + ¼ coil + (3⅜ − ½) = **4"**, matching the gusset. ✓ The gap between the
coil and the webbing is ⅜".

That last figure is the *exposed* zip run, and 43¼" is the panel face
perimeter, 2 × (11 + 10⅝). ✓

### Canvas cutting layout

The generator nests it and the player draws it; the figure to buy against is
**11½" of 58"-wide canvas**, which includes the binding. The binding is on the
straight grain here — this bag has square corners, so it needs no bias — and it
is the same cloth as everything else, so it nests with the rest rather than
being bought by the yard as tape.

*Do not hand-copy the nest into this file.* A block of cut lists lived in
`BoxBound_family.md` for exactly that reason and was deleted: it went stale in
three independent ways and still read like a cut list. Run
`py tools/bag_pattern.py --all --package` and read the player.

## Cut list — nylon webbing (hot knife)

| Piece | Qty | Cut size | Purpose |
|---|---|---|---|
| Chassis loop | 1 | **47½"** | The whole circumference — **inside** the gusset |
| D-ring tab | 6 | **4"** | External, one per ring |
| Grab handle | 1 | **12"** | Top of the bag |

**83½" total** in the bag itself; straps are separate.

---

## The chassis: one unbroken loop, hidden inside

A **single 47½" length of webbing runs the entire 43¼" circumference** at the face
centreline, closed by one 4" overlap — and it runs on the **inside** of the
gusset, where nothing on the outside has to work around it.

Each D-ring sits on a **short external tab**, and one box-X goes through
**tab + gusset + internal webbing**. That is how high-end packs anchor straps: a
hidden internal anchor behind the shell, with the bar-tack driven through all
three layers so the load spreads into the anchor rather than into the shell.
No slots to cut, none to reinforce, and the tack itself is the connection.

```
   unrolled gusset ring, 43¼" at the stitch line
   +--------+--------+--------+--------+
   | left   | bottom | right  | zipper |
   | 10⅝"   |  11"   | 10⅝"   |  11"   |
   +--------+--------+--------+--------+
   ===[1]=====[5]====[6]=====[2]===[3]|[4]===   <- webbing, INSIDE
                                   \___ 4" overlap, the only joint

   exterior: six 1" box-X patches at the rings, and nothing else
```

**The zipper being off-centre is what makes this possible.** With the coil on the
centreline the webbing has to jog around it, and that jog is what forced two
pieces and two joints — **placed, as it happened, at the two top corners, which is
exactly where rings 1 and 2 carry the whole bag in crossbody mode.** Offsetting
the coil lets the webbing run dead straight and moves the single remaining joint
to the middle of the top face, which carries almost nothing in crossbody and only
the small differential between rings 3 and 4 in backpack mode.

**Better still, the overlap lands under rings 3 and 4.** It spans 3⅜"–7⅝" along
the 11" top face and the rings sit at 4" and 7", so both backpack anchors are on
**doubled webbing**.

The loop also passes over both of the gusset's lap joins and topstitches through
them, reinforcing seams that previously just met there.

*Honest accounting: at stadium loads neither arrangement was going to fail — a
properly box-X'd webbing lap is close to full webbing strength. The real wins are
one piece instead of two, 12" less webbing, two fewer box-X operations, and no
joint sitting at a load concentration. Ring positions are materially unchanged.*

| Rings | Position | Spacing | Job |
|---|---|---|---|
| **1–2** | 1" below the top corner of each side face | — | **Crossbody / shoulder** |
| **3–4** | Top face, on the overlap | **3" apart**, centred on 11" | **Backpack upper** |
| **5–6** | Bottom face | **9" apart**, centred on 11" — 1" from each end | **Backpack lower** |

**The vinyl is a window. It contains; it never carries.** Every carry load
terminates in the canvas-and-webbing chassis, and the panels' only structural
job is holding contents in, spread along 44" of bound seam rather than
concentrated at a point.

**Backpack straps come off the top-back and bottom-back**, which is the correct
geometry. Anchored to the side gussets they would sit 11" apart at the top —
roughly shoulder width, so they slide straight off. Ergonomic guidance puts useful
top spacing at about **70 mm (2¾")**: wider and they fall off, narrower and they
pinch the neck. The 9" bottom spread gives the outward angle that keeps them
seated. The bag is only 4" deep, so rings on the gusset centreline rather than the
panel face is a 2" difference that changes nothing about how it wears.

Backpack and crossbody use different rings, so **both stay rigged at once**.

---

## Internal pockets

| Pocket | Cut | Where | For |
|---|---|---|---|
| **Back panel, divided** | 11¾" × 6½" vinyl | Back panel interior, full width | Phone, tickets, wallet |
| **Small items, divided** | 3" × 4½" vinyl | Right gusset interior | Chapstick and lighter |
| **Discreet** | 3" × 10" canvas | Left gusset interior | Cash, ID, keys |

*Both gusset pockets are 3" wide, not 3½" — the gusset's face between flanges is
only 3¼".*

### The back-panel pocket has no bottom seam of its own

A pocket's contents sit on its bottom seam. Put that seam in the middle of a vinyl
panel and it is a loaded horizontal stitch line in 0.5 mm PVC — the same
tear-initiation line the chassis exists to eliminate, only longer.

So it has none. **The pocket is cut to full panel width and its bottom and both
sides are caught in the panel's binding**, which is already structural and already
canvas-backed. Contents rest on a seam that was carrying the bag anyway, and the
only new stitching in the vinyl field is the divider.

### The divider reads as structure

A **¾" × 11¾" canvas rib on the *outside* of the back panel**, running its full
height with both ends caught in the binding, topstitched down both long edges.
Those two lines pass through the pocket beneath, so one component makes the
divider, reinforces its stitch line, and looks like a reinforcement strap.

Set it **4½" from one cut edge, not centred.** Off-centre reads as structure and
gives two useful sizes: **3¾"** — a phone — and **6½"** for flat items.

### The discreet pocket

Canvas on canvas, black on black, with nothing that reads as an opening. A
3" × 10" panel on the left gusset interior, top edge free and left raw, sitting
1½" below the zipper-panel join. Topstitch both long edges full height and across
the bottom, then **one horizontal line 5" below the top**. Above that line is the
pocket; below it the panel is sewn flat and dead.

From inside it is a doubled black panel with topstitching round it and one line
across — a reinforced gusset. From outside the side seams sit close to the binding
where they disappear, and the horizontal line reads as a bartack row.

*Contents in a canvas pocket are not visible, unlike everything else in this bag.
The policy already allows a small non-clear bag up to 4.5" × 6.5" carried
alongside, which gets the same privacy with none of the ambiguity — a compartment
built to escape notice can read badly at a gate whatever is in it.*

### Both gusset pockets mount on the canvas gusset, not on the panels

A loaded pocket is a weight-bearing attachment; on a vinyl panel it would be a
stitch line under load in 0.5 mm PVC.

**Clear is not optional for the two vinyl pockets.** The obvious move is a fabric
pocket — every bag pattern has one — and in the main compartment of a clear bag
an opaque pocket is exactly what the policy exists to prevent.

---

## The grab handle

**One fixed handle on the top gusset**, box-X'd through the gusset into the
internal chassis loop: 12" of webbing, anchored **2" and 9" along the 11" top face**, giving a **7" span
and ~3" of hand clearance**.

It lands centred on the bag's depth, so the bag lifts level — the loop runs the
face centreline just inside, and the coil is forward of it, which is exactly the
clearance the off-centre zipper bought. Anchors at 2" and 9" also clear rings 3
and 4 (at 4" and 7") and sit outside the 3⅜–7⅝" overlap.

**Why one and not two.** Most totes carry two handles because they anchor to the
front and back panels — which here are vinyl, and nothing weight-bearing goes on
vinyl. The front strip of the zipper panel is only ½" of visible face, too narrow
to anchor anything, and a handle spanning the coil would block the zipper. A
single top haul handle is what the structure permits, and it is what bags with a
zipper gusset use anyway.

It is webbing, so it lies flat when not in use — including against your back in
backpack mode. If the bag rides heavy, fold a 4" scrap of canvas round the grip
zone or double the webbing there.

*This replaces the clip-on 14" handle that used to be in the strap kit, and frees
two swivel hooks.*

## Strap kit

| Strap | Webbing | Hardware |
|---|---|---|
| Crossbody, adjustable ~30–52" | 56" | 1 tri-glide, 2 swivel hooks |
| Backpack pair, adjustable | 2 × 34" | 2 tri-glides, 4 swivel hooks |

Hooks unclip and move between configurations, so four serve all three if you swap.
Build the crossbody first.

**Make a shoulder pad.** Interface-pressure research is unambiguous that wider
straps are markedly more comfortable — best results at 8 cm — and 1" webbing is
narrow for a single strap carrying the whole bag. A slip-on pad, or a canvas
sleeve over closed-cell foam, costs nothing structurally.

**Webbing to buy:** bag 83½" + crossbody 56" = 139½", so **4 yards** covers the bag
and its primary strap; **6 yards** covers every configuration.

## Materials and hardware

| | |
|---|---|
| Shell | **600D PU-coated polyester canvas.** No pre-wash — it does not shrink. **Not waxed canvas**, and not a fraying cotton unless you also buy tape to bind it in. |
| Binding | **The shell.** It does not ravel, so it binds itself at single fold: 1⅛" strips off the same roll, no second material. |
| Clear vinyl | **20 gauge** (0.020") — holds shape on a 12" panel. 16 ga sews easier and slumps more. 36" × 12". |
| Canvas | **11½" of 58"-wide** covers the shell, the binding and the base strip. Buy ½ yd for margin. |
| Webbing | 1" nylon, 4–6 yd per above. |
| Zipper | **#5 nylon coil, 14"** — longer than the opening so it can be shortened to fit. |
| Hardware | **6 × 1" D-rings** · 3 × 1" tri-glide sliders · 4–6 × 1" swivel snap hooks. |
| Thread | Heavy polyester topstitch / upholstery weight. |
| Base stiffener *(optional)* | HDPE, Coroplast or PETG, **10¾" × 3"**. Sized to the interior, not the exterior. |

---

## Cutting — two tools, and one must never touch the vinyl

| Material | Tool |
|---|---|
| Clear vinyl | **Rotary cutter** and ruler |
| Canvas shell and binding | **Rotary cutter.** It *will* melt-seal, but a hot knife on a coated face can leave a hard bead — test on a scrap, and nothing here needs a sealed edge anyway |
| Webbing | **Hot knife**, or a lighter. Nylon ravels the moment it is cut and this is the one thing that genuinely needs sealing |

> **Never hot-knife PVC.** Heating vinyl releases hydrogen chloride — corrosive
> and genuinely harmful, not merely unpleasant like melting nylon. Vinyl is
> rotary-cut, always.

**Metal** straightedge — a plastic ruler melts. Cut on glass or scrap plywood,
never a self-healing mat. Dial the heat well down: nylon melts around 220 °C and
these tools reach 500 °C. Ventilate. One steady pass; practise on scrap.

**Check the tool's duty cycle.** A 60" binding strip is 30–45 seconds of unbroken
cutting. Non-air-cooled units are rated for ~15-second intervals, and pausing
mid-cut leaves a melted blob and a restart notch on a strip whose whole job is to
be an even 1⅛" wide.

## Needles and stitch length

| Seam | Needle |
|---|---|
| Everything — binding, sling, webbing, gusset | **Microtex 90/14 sharp.** 600D is half the yarn of a 1000D and the worst stack here is 4.35 mm, so a heavier needle buys no penetration and makes a bigger hole — which, in a coating, is permanent |
| Zipper topstitching | Microtex/sharp 90/14 |

**Do not reach for a leather needle** for the vinyl. It is chisel-pointed and cuts
a slit rather than piercing a round hole, and in vinyl that slit becomes a tear
that propagates along the stitch line.

**Stitch length 3.0–3.5 mm.** Short stitches perforate vinyl into a tear-here line
— the opposite of the usual shorten-it-for-strength instinct.

## Thickness budget

600D canvas 0.45 mm · 20 ga vinyl 0.51 mm · 1" nylon webbing 1.3 mm.

**Do not hand-copy this table.** `tools/bag_pattern.py` derives every row from
the material table and `stitch info` prints it; the figures below are here to
argue a point and were re-read from the generator on the canvas build. An
earlier version of this section quoted 4.4 mm for the D-ring tack — correct when
the gusset was Cordura, and 0.25 mm stale the moment the shell changed.

| Location | Stack | Thickness |
|---|---|---|
| Gusset-to-zipper lap join | 2 × canvas | 0.9 mm |
| Zipper topstitch | canvas + tape | 1.05 mm |
| **Plain bound seam** | vinyl + canvas + 2 binding | **1.86 mm** |
| Mitred corner | binding doubles | 2.76 mm |
| **Mitred corner over a gusset lap join** | the mitre + the lapped zip strip | **3.21 mm** |
| Chassis topstitch | webbing + canvas | 1.75 mm |
| Chassis overlap box-X | 2 × webbing + canvas | 3.05 mm |
| **D-ring tab box-X** | doubled tab + canvas + internal webbing | **4.35 mm** |
| Grab handle box-X | doubled end + canvas + internal webbing | 4.35 mm |

**Peak on the bag is 4.35 mm**, at the eight external tacks — six rings and the
two handle ends. Hand-wheel those; everything else drives normally. That is the
price of hiding the webbing: an external tab plus the internal anchor is two more
layers than a ring threaded onto exposed webbing.

Two things the canvas bought: the bound seam went **2.26 → 1.86 mm** and the
mitre **3.26 → 2.76**, because a shell that does not ravel binds itself at two
layers instead of needing four. And the thickest *seam* is no longer the plain
mitre — it is the mitre sitting on a gusset lap join, which all four of them do,
and which nothing in this file used to mention.

*If the machine baulks, make the tabs from doubled **canvas** rather than webbing
— 0.9 mm instead of 2.6 — which brings the tack to 2.65 mm. Webbing is the
stronger choice for rings 1 and 2, which carry the whole bag; canvas is ample for
3–6.*

---

## Stitch schedule

Every seam in this bag is one of three stitches. Nothing here needs a machine
feature the 4423 lacks.

### The three stitches

**Straight topstitch** — the workhorse. Every seam, every binding run, every
webbing edge. **Length 3.0–3.5 mm.** Longer than instinct because short stitches
perforate vinyl into a tear-here line.

**Box-X** — a rectangle of straight stitching with an X corner to corner inside
it, sewn as one continuous path so there is no start/stop inside the box. This is
what anchors every webbing joint. It tests **stronger than a bar-tack**, which
fails at its first bar; the X spreads load into four directions instead of one.
**Length 2.5–3.0 mm** (8–10 stitches per inch) and **go round twice.**

**Bar-tack substitute** — the 4423 has no programmed bar-tack, so use a **dense
zigzag: width ~3 mm, length ~0.4 mm**, worked back and forth 5–6 passes. Only one
job needs it: the new zipper stop.

### Sizing a box-X

Load-critical webbing-to-webbing joints want a pattern **3× the webbing width**.
The chassis overlap is 4¼" on 1" webbing — **4×**, comfortably past it.

The D-ring tabs cannot reach that: a 4" tab is a ½" wrap round the ring plus two
1¾" legs, so the box-X is about **1½" × ¾"**. That is 1.5× width, and it is fine
— a tab carrying a few pounds is not a harness joint. If you want more, lengthen
the tabs; nothing else changes.

### The schedule

| Operation | Stitch | Length | Foot | Needle |
|---|---|---|---|---|
| Chassis webbing to gusset | straight, both long edges | 3.0 | walking | Microtex 90/14 |
| Pockets to gusset | straight | 3.5 | walking / Teflon | Microtex 90/14 |
| Zipper strips to tape | straight, **2 rows** | 3.0 | **zipper** | **Microtex 90/14** |
| New zipper stop | **dense zigzag** ~3 mm wide | **0.4** | zigzag | Microtex 90/14 |
| Gusset lap joins | straight, 2 rows | 3.0 | walking | Microtex 90/14 |
| Chassis overlap | **box-X, twice round** | 2.5–3.0 | walking | Microtex 90/14 |
| D-ring tabs, handle ends | **box-X, twice round** | 2.5–3.0 | walking | Microtex 90/14 |
| Divider rib | straight, both long edges | 3.5 | walking | Microtex 90/14 |
| Binding | straight, **⅜" from the panels' raw edges** | 3.5 | walking | Microtex 90/14 |
| Strap box-X at hardware | **box-X, twice round** | 2.5–3.0 | walking | Microtex 90/14 |

**Raise the upper tension** for the webbing passes; thick webbing pulls the top
thread down and leaves loops underneath at normal tension. Drop it back for
binding and pockets.

### Locking off

| Where | How |
|---|---|
| Canvas, webbing | Backstitch 3–4 stitches. Normal. |
| **Exposed vinyl** | **Never backstitch** — it perforates. Leave 4" tails, pull both to one side, square-knot, trim. |
| Vinyl inside a seam the binding will cover | Backstitch is fine; it will be hidden and the binding carries the edge. |

### Thread

Heavy polyester topstitch, **top and bobbin**, so bound seams look the same from
both faces. Wind the bobbin slowly. If tension misbehaves, drop to a strong
all-purpose polyester in the bobbin and raise the top tension a little — in black
on black nobody will see the difference.

### Tools that make this possible

| | |
|---|---|
| **Walking foot** | Low-shank. Vinyl sticks to a metal foot and stalls while the feed dogs keep pulling. |
| **Teflon / roller foot** | Alternative for the vinyl-only passes. |
| **Zipper foot** | For the two rows onto the zipper tape. Not optional — a standard foot cannot get close enough to the coil. |
| **Double-sided basting tape** | The answer to "you cannot pin vinyl". A vinyl-rated basting tape (Seamstick and similar) holds panels and pockets exactly in place while you sew. |
| **Clips** | Everywhere else. Every pin hole in vinyl is permanent. |
| **Height compensation** | A folded scrap of canvas under the back of the foot to step onto the 4.35 mm tacks level. Without it the foot tips and the first stitches bunch. |
| **Edge guide** | Or a strip of tape on the throat plate at ⅛". Binding looks amateur when the stitch line wanders. |

*Basting tape makes the needle sticky.* Wipe it with alcohol, or push the needle
through a bar of soap before fitting it.

---

## Assembly order

Bound seams cannot be unpicked — the holes stay in the vinyl. This order does all
flat sewing first, so nothing has to be reached into.

**0 — Test first.** On scrap, sew a **bound seam** and measure the allowance you
actually achieve — every dimension keys off 3/8". Then sew a **box-X through the
worst stack**: doubled webbing + canvas + webbing, 4.35 mm. If the machine cannot
drive it, switch the tabs to doubled canvas before you cut anything.

**1 — No pre-wash, and no pressing at any point.** Polyester does not shrink,
so there is nothing to pre-shrink; and the coating is the waterproofing, so heat
is the one thing it cannot survive. If a step below says press, it is a leftover
from the denim build — clip it instead.

**2 — Cut.** Vinyl and canvas with a rotary cutter, webbing with the
hot knife. Clips only, never pins — a pin hole in a coated shell is permanent
and it is a hole in the waterproofing. Cut the gusset **long** and leave it long.
Nothing needs pressing under: the cloth does not ravel, which is why the zip
strips are 1⅜/3⅜ and not the 1⅝/3⅝ the denim build cut.

**3 — Embroider the gusset.** Flat, before anything is assembled. Right side
section — see below.

**4 — Chassis webbing onto the gusset INTERIOR.** Mark the centreline on the
gusset's inside face. Lay the 48" webbing along it so **32¼" sits on the gusset
with 7⅝" of tail free at each end**, and **straight topstitch both long edges of
the 32¼" at 3.0 mm**, raising the upper tension for the webbing. Nothing threads
onto it — the rings live on external tabs.

**5 — Gusset pockets, over the webbing.** On the **right** side section: bind the
small-items pocket's top edge, set it 2" below where the zipper panel will join,
**straight topstitch at 3.5 mm** on the other three edges and add the vertical
divider. Hold it with **basting tape**, not clips — a pocket that shifts a
sixteenth shows. On the **left**: lay
the 3" × 10" canvas panel with its top edge free, 1½" below the join, topstitch
both long edges and the bottom, then one horizontal line 5" below the top edge.
The pockets sit over the webbing and their own stitching helps hold it flat.

**6 — Zipper panel.** Lap the **1⅜"** strip and the **3⅜"** strip ½" onto the
zipper tape and **straight topstitch two rows at 3.0 mm with the zipper foot and a
Microtex 90/14**. The coil ends up **1" from the panel's cut edge**, leaving the
face centreline clear for the webbing. Basting tape holds the lap while you sew.

**7 — Shorten the zipper.** Open it halfway and make a new bottom stop with the
**bar-tack substitute — dense zigzag, ~3 mm wide, 0.4 mm long, 5–6 passes back and
forth across the coil**. Then trim 1" beyond it. A coil zipper cut
without a new stop lets the slider run straight off the end. Cap each cut end with
a scrap of canvas.

**8 — One lap join, then the top run.** Fit the ring to the back panel and **trim
the gusset to length** — target **32¼"**, so the ring closes at **43¼"**. Lap
*one* gusset end onto one end of the
zipper panel by ½" and topstitch. Now lay both webbing tails along the zipper
panel's interior centreline: they **overlap each other by 4¼" at its centre**.
Straight topstitch them down at 3.0 mm, then **box-X both ends of the overlap,
twice round at 2.5–3.0 mm**. The chassis is now one unbroken loop.

**9 — Second lap join.** Close the remaining gusset-to-zipper-panel lap, stitching
through the webbing where it crosses so the join is reinforced. Leaving this join
until last is what keeps every webbing pass flat under the foot.

**10 — Rings and handle, from the outside.** Fold each 4" tab through a D-ring and
box-X it to the **exterior** of the gusset, driving the stitch through
**tab + gusset + internal webbing** — the tack is the connection. Positions:
rings 1 and 2 **1" below the top corner of each side face**; 5 and 6 **9" apart,
centred on the bottom face**; 3 and 4 **3" apart, centred on the top face**, where
they land on the overlap. Then the handle: fold 1" under at each end of the 12"
length and box-X it at **2" and 9" along the top face**. **Box-X each one, twice round at 2.5–3.0 mm**, roughly 1½" × ¾". Hand-wheel all
eight — this is the 4.4 mm stack, and a height-compensation scrap under the back
of the foot stops it tipping. Check the handle arcs clear of the slider before
committing its second tack.

**11 — Build the back panel.** Bind the pocket's top edge, then lay the pocket on
the panel's **interior** with its bottom and side edges flush to the panel edges,
and clip. Lay the canvas rib on the **exterior**, 4½" from one side, running the
full height. **Straight topstitch both long edges of the rib at 3.5 mm** — those two lines go
through rib, panel and pocket at once, and make the divider. Basting tape holds
the pocket flush while you clip the rest.

**12 — Back panel on.** Clip the gusset ring around it, raw edges out, matching the
gusset seams to the top corners. **Clip the gusset's seam allowance at each of the
four corners, cutting only as far as the stitch line**, so it can turn the corner
and lie flat. Sew, then bind the full perimeter with a **single straight line at
3.5 mm, ⅛" in from the binding's inner edge**, mitring each corner. That binding
catches the pocket's bottom and sides and both ends of the rib.

**13 — Front panel. Open the zipper first.** Same again, clipping the corners the
same way. With the zipper closed you will not get the bag open afterwards, and
there is no unpicking this seam.

**14 — Straps.** Webbing through the tri-glides and swivel hooks; box-X each fold.
Make the shoulder pad while you are at it.

**15 — Base stiffener.** Drop it in loose. Not sewn — it should come out.

### Binding

**Full technique: [`techniques/binding.md`](techniques/binding.md).** The width
formula, the one-pass method, mitred corners, closing the loop and the failure
modes live there rather than being repeated in every pattern.

What this bag needs from it:

- **1⅛" strip, single fold** — the canvas does not ravel, so its outer edge stays raw.
- **Straight grain, mitred corners.** No curves in this design, so no bias.
- **Set the underside 1/16" deeper than the top**, then one straight line at
  3.5 mm, ⅛" in from the binding's inner edge, catches both faces.
- **Clip the gusset's seam allowance at all four corners**, only as far as the
  stitch line, before binding.
- **Joins mid-edge, never at a corner**, and clear of where the D-ring tabs land.

## Machine setup — Singer 4423

- **Walking foot, or a Teflon/roller foot.** Clear vinyl sticks to a metal foot
  and stalls while the feed dogs keep pulling.
- **Reduce presser foot pressure.**
- **Do not backstitch on exposed vinyl** — it perforates. Backstitch only inside
  seams the binding will cover; elsewhere leave tails and tie off.
- Stop with the **needle down** at corners.
- Hand-wheel anything over 3 mm.

## The gusset is an embroidery job

The logo lives on the canvas gusset, so it can be **embroidered directly into the
panel** before assembly — no patch, no applied edge, nothing to peel.

**Put it on the RIGHT side section.** The discreet pocket's two side seams run the
full height of the left gusset and show on its exterior; embroidering across them
is awkward and would draw attention to the thing meant to look like plain
reinforcement.

Because the chassis runs **inside**, the gusset exterior is clean canvas apart
from six 1" box-X patches at the rings — and the right side section carries
**exactly one**, an inch below the top corner. That leaves roughly **83 × 254 mm**
of clear field. Design to about **75 × 75 mm** and hoop it in the **SA432 4×4**.

*Embroider before the webbing goes in.* Two layers of canvas plus webbing is
1.8 mm — inside the machine's 2 mm limit, but a lumpy substrate that will not
hoop flat. Black canvas is dark cloth, so
`docs/14-designing-for-dark-cloth.md` applies in full: declare
`"cloth": "1A1A1A"` and take `fill_density_mm_dark`, or it comes off speckled.
Back it with cutaway. A long narrow treatment along the strip instead is what the
**SA431** is for — `docs/16-narrow-material.md`.

## Before cutting — the checklist

- [ ] Venue's own bag policy read, not just the NFL one
- [ ] Hot knife duty cycle suits a 45-second continuous cut
- [ ] **Test bound seam sewn on scrap, and the achieved allowance measured** — every dimension keys off ⅜"
- [ ] Binding is **not** the shell material — nothing that frays
- [ ] Vinyl measured: **11⅜" across and at least 36" long**, and the piece is square
- [ ] A **test bound seam** sewn on scrap, and the achieved seam allowance measured
- [ ] Worst-case stack test-sewn: 3 × webbing at the slider fold
- [ ] Gusset cut long and left long until step 7
- [ ] Gusset ring measures 43¼" before the first panel goes on
- [ ] Gusset embroidered **before** the webbing goes in — it will not hoop flat after
- [ ] Coil sits 1" from the zipper panel's cut edge, clear of the centreline
- [ ] Overlap box-X'd at both ends — the chassis is one unbroken loop
- [ ] New zipper stop bar-tacked before trimming
- [ ] Gusset corners clipped to the stitch line before binding
- [ ] Zipper open before the front panel seam

---

## Revision note

Five revisions of this pattern have each moved a number that only re-deriving the
geometry would have caught:

| Revision | What moved | Why |
|---|---|---|
| Leather → Cordura | zip strip 2" → 1¾" | binding the strip edge changed the lap |
| Cutting layout drawn | vinyl 24 × 40 → 36 × 16 | the pieces were never actually nested |
| Vinyl gusset → Cordura | zip strip 1¾" → 2⅜" | Cordura needs no binding, so the lap changed back |
| Chassis | ring tabs → webbing | "caught in the binding seam" still loaded the vinyl |
| **Seam allowance audit** | **ring 48" → 44", panels 12" → 11¾"** | **a bound seam still needs a seam allowance** |
| Cordura → 12 oz denim | binding → nylon tape | denim frays, and a fraying shell bound in itself is 7.3 mm at the mitre |
| **Denim → 600D canvas** | **binding back to the shell; seam 2.26 → 1.86 mm** | **a coated shell does not ravel, so it binds itself and the tape is not bought at all** |
| **Lap allowance** | **gusset 33¼" → 32¼"** | **both pieces carried it, so the ring closed an inch over — and the check meant to catch that could not fail** |

Two of those would have ruined a bag: a 48" ring onto a 44" perimeter is 4" of
pucker, and the lap double-count is another inch of the same thing on a seam that
cannot be eased.

**The declared form now exists.** `patterns/specs/StadiumTote_12x12x4.json`
carries the object, `patterns/constructions/box-bound.json` the procedure, and
`tools/bag_pattern.py` derives the cut list, takeoff, layout, thickness budget
and 3D preview from them. Everything in this file that states a *figure* is a
copy of something the generator computes, and a copy is checked by nothing —
which is exactly how the denim thickness table survived a material change. Read
the player; treat this file as the reasoning.

Log the build in `projects/` when it happens.
