# Embroidering narrow material — straps, webbing, lanyards, ribbon

The problem with a 1-inch strap in a 4×4 hoop is not the design. It is that a
hoop grips fabric by stretching it between two rings, and a 25 mm strap only
touches the ring at two edges. There is nothing to tension against, the material
lifts with the needle — *flagging* — and flagged material produces looping,
skipped stitches and thread breaks no amount of digitizing fixes.

The answer is that **you never hoop the strap.** You hoop something the hoop can
grip, and you attach the strap to that. This machine also has a frame that makes
the whole problem smaller, which is where to start.

`12-design-generation-playbook.md` still applies in full — this covers only what
narrow material changes.

---

## First: use the small frame

The SE700's firmware has explicit support for an optional **embroidery frame
(small)** — the **SA431**, also sold as **EF61**. Its primary embroidering area
is:

> **2 cm × 6 cm (approx. 1 inch (H) × 2-1/2 inches (W))** — Operation Manual
> p.68, and again on the preview key at p.75

That is a **1-inch-tall field**, and it is not a coincidence of geometry. Brother
sizes that frame for collars, cuffs, monograms and exactly this class of narrow
work. Under a 25.4 mm strap, a 20 mm-tall field leaves the frame's own arms
bearing on the strap edges and holding them flat — which is the support the 4×4
cannot give and the reason the strap flags in it.

The machine offers **three** embroidering areas for that frame, and a design need
only fit one:

| | width × height |
|---|---|
| the strap area | **60 × 20 mm** |
| | 50 × 30 mm |
| | 30 × 40 mm |

All three are in `reference/machine-profile.json` under `hoops`, and `validate`
checks against them — see [Declaring the hoop](#declaring-the-hoop) below.

### Two settings, and the second one is a safety interlock

**The machine does not sense which frame is mounted.** You tell it: *Settings →
Embroidery settings → select the embroidery frame*, then set **[Embroidery Frame
Identification View] to ON**. With that on, patterns too large for the selected
frame are shaded out and unselectable, and choosing one raises *"Pattern extends
to the outside of embroidery frame. Select a larger frame."*

With it **off** and the small frame mounted, nothing stops the carriage driving a
100 mm path. The manual is explicit (p.64):

> "If you use a frame that is too small, the presser foot may strike the frame
> during embroidering and cause injury or may damage your machine."

`07-troubleshooting.md` lists the mirror of this — a valid 90 mm design vanishing
from the list because the small frame is still selected. Same setting, and with
the SA431 the filtering is the feature rather than the trap.

---

## When you don't have the small frame: float it in the 4×4

Floating is the manual's own answer for material that cannot be hooped (p.64):

> "When embroidering small pieces of fabric that cannot be hooped on an
> embroidery frame, use stabilizer material as a base. After lightly ironing the
> fabric to the stabilizer material, hoop it in the embroidery frame. If
> stabilizer material cannot be ironed onto the fabric, attach it with a basting
> stitch."

In practice, for webbing:

1. Hoop **sticky self-adhesive tear-away** stabilizer on its own, paper side up,
   drum-tight. This is the piece the hoop grips.
2. Score the paper inside the hoop and peel it away to expose the adhesive.
3. Lay the strap down onto it, straight. Mark a pencil line on the stabilizer
   first and align to that — a strap set down 2° off is 2° off for its whole
   length, and unlike a design on cloth there is no other edge to judge it by.
4. For a dense design, add a layer of cutaway *underneath* the hooped stabilizer.
5. **Roll and clip the tails.** The manual warns that fabric hanging off the
   table stops the embroidery unit moving freely and distorts the pattern (p.63),
   and a metre of webbing hanging off the front does exactly that.

Synthetic webbing often will not take a fusible. If it also will not hold the
adhesive, fall back to the manual's basting: the SE700 has **no automatic basting
box in embroidery mode**, so baste in sewing mode with stitch 1-07 before
mounting the frame, and pick the basting out afterwards.

For volume, tack several straps to one hooped sheet, spaced a couple of inches
apart, and stitch them as an array. Tearing the stabilizer out afterwards leaves
registered openings the next batch drops straight into.

**An accident of this machine that works in your favour:** the standard advice
for sticky stabilizer is to slow the machine to about 400 spm so needle heat does
not melt adhesive onto the needle. The SE700 is **fixed at 400 spm** and cannot
be raised. You are already at the recommended speed — see
`machine-profile.json → embroidery.speed_is_fixed`.

---

## Materials

| | |
|---|---|
| **Thickness** | **Measure it.** The embroidery limit is **2 mm** — tighter than the 6 mm sewing limit (`embroidery.max_fabric_thickness_mm`, Operation Manual p.64) and it counts the strap *plus* stabilizer. Heavy cotton and some nylon webbing exceeds it, and over-thickness is a needle-breakage failure, not a quality one. |
| **Needle** | **Titanium-coated 75/11 sharp.** A sharp, not a ballpoint — you are piercing a tight woven synthetic, not a knit. Titanium because a dull needle in webbing shreds thread within one design. |
| **Thread** | **Polyester, not rayon.** Straps are abraded and washed; rayon degrades in wear. |
| **Bobbin** | Match the bobbin to the strap where it matters. Webbing's tight weave grips a knot *worse* than open cloth, so it is the substrate most likely to pull bobbin colour to the surface — and per `07-troubleshooting.md`, bobbin colour on the surface is a machine-side fault to triage before touching the file. |
| **Tension** | Expect to loosen the upper tension slightly against woven cloth: you are through much denser material. Procedure at Operation Manual p.72. |

**Embroider the strap flat, before assembling it.** The embroidery unit occupies
the free arm, so a strap already sewn into a loop cannot be mounted at all.

---

## Digitizing for a 1-inch strap

### Size

A 25.4 mm strap, less the conventional **1/8" (3.2 mm) margin per edge**, leaves
about **19 mm of usable height**. The SA431's 20 mm field enforces roughly that
for you, which is the second reason to prefer it — the constraint is built into
the hardware instead of relying on you to remember it.

Lettering wants **12–18 mm cap height** on 3/4"–1" webbing, in **block faces**,
not script. That is far above this repo's 5 mm `min_text_cap_height_mm`, so the
type limits are not what binds here; the strap width is.

### Parameters that change

Three departures from this repo's validated values. **All three are starting
points for a test stitch-out, not settled figures** — nothing in this repository
has been stitched on webbing yet, and everything below comes from practitioner
sources rather than from fabric in this workshop.

- **Drop the underlay.** Webbing is already stable and does not need supporting.
  Under a 19 mm design on a dense weave, underlay is penetrations the material
  has no room for.
- **Cut pull compensation to ~0.1 mm**, against the repo default of 0.2. Pull
  compensation offsets fabric pull-in; webbing barely pulls in. On a design whose
  height is 19 mm the extra 0.2 mm per side is expansion toward an edge you
  cannot afford to reach.
- **Density is genuinely contested.** Reported figures for nylon webbing run
  0.33–0.5 mm row spacing, the dense end argued as compensating for needle
  deflection through the weave and the sparse end as avoiding perforating it. The
  0.4 mm default sits in the middle; `fill_density_mm_dark` (0.33) is already in
  the profile if a test says denser.

### What does not change

`max_collapse_mm` matters more here, not less. A strap design is small elements
surrounded by bare material, which is precisely the case where Ink/Stitch's 3.0 mm
`collapse_len_mm` default sews visible travel between them — see the
MuffyHat_on_white write-up in `CLAUDE.md`. And the 1.2 mm safe feature width is
unchanged: a strap is not a reason to draw finer.

---

## Declaring the hoop

A design for a small frame declares it, the same way it declares its cloth:

```json
{
  "name": "StrapName_on_black",
  "cloth": "1A1A1A",
  "hoop": "SA431",
  "build": { "tool": "svg_to_pes", "input": "art/originals/…", "artwork_mm": 55 }
}
```

`stitch validate` reads it and reports **`hoop-overflow`** as an error, or
**`hoop-tight-margin`** as a warning under 2 mm of clearance. `--hoop SA431`
overrides for a one-off file with no spec.

**It has to be declared, because nothing else knows it.** A `.pes` records no
frame, and the machine does not detect one either. A design built for the SA431's
20 mm field but drawn 40 mm tall clears the 100 × 100 machine field by 60 mm — so
`field-overflow` cannot see it, `coverage` cannot, the render cannot, and `proof`
cannot. It gets listed on the machine and then drives the presser foot into the
frame. Omit the field and the design is only checked against the full field,
which is the correct behaviour for the ten 4×4 designs in this repo but is not a
check of anything for a strap.

The profile distinguishes a hoop's **window** from its **fields**, and it is the
fields that matter: SA434's window is 100 × 170 mm while the machine still only
stitches 100 × 100 through it, so a check reading the window would pass a 150 mm
design that cannot be stitched.

---

## Sources

- SE700 Operation Manual — frame selection and identification view pp. 15, 68;
  the too-small-frame caution and the float-on-stabilizer memo p. 64; fabric
  hanging off the table p. 63; embroidery tension p. 72; small-frame preview
  p. 75. Local copy: `reference/manuals/SE700-Operation-Manual-EN.txt`.
- [Brother SA431 product page](https://www.brother-usa.com/p/hoops-stabilizers/SA431)
  and [SE700 compatibility](https://www.amazon.com/Sew-Tech-Embroidery-Brother-Babylock/dp/B083QM1NHS).
- [Floating explained](https://www.embroidery.com/floating-in-hoop) ·
  [sticky tear-away for unhoopable items](https://allstitch.com/products/stickystitch-self-adhesive-peel-stick-backing-rolls-white).
- [Embroidering nylon collars and webbing](https://www.digitsmith.com/embroidering-nylon-dog-collars-15522)
  — needle, underlay, pull compensation, density, lettering height, flagging.
- [Embroidering lanyards](https://www.digitsmith.com/embroidering-lanyards-8157)
  — the batch-float method.
- [Webbing tension](https://www.t-shirtforums.com/threads/embroidery-problems-on-webbing.35041/).
