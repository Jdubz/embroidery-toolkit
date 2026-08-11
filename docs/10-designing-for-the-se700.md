# Designing Patterns for the SE700

Most digitizing advice online is written for commercial multi-needle machines
with 5×7 or larger fields. Three SE700 facts invalidate a lot of it.

## What makes this machine different

| | SE700 | Typical advice assumes |
|---|---|---|
| Field | **100 × 100 mm** | 130 × 180 mm or larger |
| Needles | **1** — every colour is a manual rethread | 6–15, automatic |
| Speed | **400 spm** | 800–1000 spm |
| Thread | 40 wt top, 60 wt bobbin, 75/11 needle | same |

**The field is the big one.** Halving linear size quarters the area, so your
detail budget is a quarter of what a 5×7 guide assumes. A feature that reads fine
at 180 mm is a smudge at 96 mm.

**The single needle is the second.** On a 10-needle machine colour count is
nearly free. Here, every colour change stops the machine and you rethread by
hand. Your instinct in the prompt was right — and the practical ceiling is lower
than people expect.

**400 spm makes time real.** A 16,000-stitch design is 40 minutes of stitching
before rethreads. `stitch info` now reports this:

```
run time      ~46 min at 400 spm (incl. 4 rethread(s))
```

`validate` warns past 45 minutes, because long unattended runs on a home machine
are where thread breaks and hoop shift happen.

## The numbers that actually bind

Derived from 40 wt thread through a 75/11 needle in a 96 mm working field:

| Feature | Minimum | Safe |
|---|---|---|
| Satin column / linework width | 1.0 mm | **1.2 mm** |
| Filled shape | 2 mm across | 3 mm |
| Text cap height (sans-serif) | 5 mm | **6 mm** |
| Text cap height (serif/script) | 8 mm | 9 mm |
| Gap between shapes | 1 mm | 1.5 mm |
| Fill density | 0.4 mm rows | 0.45 on knits |
| Colours | — | **3–4** |

At 96 mm wide, **1.2 mm is 1/80th of the design**. That is the whole story: any
line thinner than about 1% of your design width will not survive.

Density note: general guides quote "6–8 stitches per mm" for fills. That is a
commercial figure. On a home machine into T-shirt knit, 0.4–0.45 mm row spacing
is the sane range, and erring sparse beats erring dense — over-dense fills
perforate the fabric and go board-stiff.

## Calibrating against Brother's own designs

The best available evidence for what this machine is *designed* to do is the
128 built-in patterns Brother ships with it. Every one is catalogued in
`reference/manuals/SE700-Embroidery-Design-Guide.pdf` with its size, colour
count and run time. Measured across all 128:

| | min | p25 | median | p75 | p90 | max |
|---|---|---|---|---|---|---|
| Run time (min) | 1 | 4 | **7** | 16 | 23 | **47** |
| Colours | 1 | 2 | **3** | 6 | 12 | 30 |
| Longest edge (mm) | 14.8 | 52.6 | **78.7** | 93.5 | 95.4 | **98.5** |

Three things this settles:

- **The 96 mm working size is right.** 126 of 128 (98%) of Brother's own
  designs have a longest edge of 96 mm or less, despite a 100 mm field. They
  leave themselves clearance too. The largest is 98.5 mm, so 96 is slightly
  conservative rather than arbitrary.
- **3 colours is the norm, not a limitation.** Brother's median is exactly 3
  and 65% use 4 or fewer. The "3–4 colours" guidance above is not a compromise
  forced by the single needle — it is what the machine's own catalogue does.
  (They do ship outliers: 24% use more than 6, and one uses 30. Those are
  possible, just tedious.)
- **The 45-minute runtime warning is well placed.** 99% of Brother's designs
  finish inside 45 minutes and the longest is 47. A design of yours running
  much past that is outside anything Brother ships for this machine.

Use these as sanity checks on a generated design: if it wants 8 colours and
70 minutes at 99 mm, it is not a design this machine is built around, whatever
`validate` says about the hard limits.

## Colour strategy on one needle

| Colours | Rethreads | Verdict |
|---|---|---|
| 2 | 1 | Ideal. Bold and graphic. |
| 3–4 | 2–3 | **The sweet spot.** |
| 5 | 4 | Acceptable for a special piece. |
| 6+ | 5+ | You will resent it by number four. |

`validate` now flags 5+ changes and warns at 7+.

Two tricks that buy colours back:

- **Let the fabric be a colour.** Don't stitch a white background onto white
  fabric — leave it unstitched. Saves a colour *and* thousands of stitches.
- **Appliqué for large areas.** Fabric patch tacked down and edged, instead of a
  solid fill. Massively fewer stitches, softer result. The SE700 has built-in
  appliqué patterns.

## Your four images, measured

I scaled each to the SE700's 96 mm working field and measured feature sizes in
millimetres on fabric.

| | LemonCat | ScreamingCat1 | ScreamingCat2 | IheartScreaming |
|---|---|---|---|---|
| Size at 96 mm | 96 × 77 mm | 96 × 96 | 96 × 96 | 96 × 96 |
| Typical linework | 10.8 mm ✅ | **0.94 mm ❌** | **0.94 mm ❌** | 1.09 mm ⚠️ |
| Thinnest 10% | 0.80 mm ❌ | 0.19 mm ❌ | 0.19 mm ❌ | 0.19 mm ❌ |
| Regions < 1 mm² | 90,380 | 51,966 | 52,326 | 54,834 |
| Colour error @ 3 | 21.4 | 64.9 | 60.0 | 51.5 |
| Colour error @ 5 | 21.2 | 22.8 | 60.0 | 19.5 |
| Stitches / run time | 8,483 / **27 min** | 15,008 / **44 min** | 15,028 / 44 min | 15,982 / **46 min** |

**These are sticker designs, not embroidery designs.** That is not a criticism —
it is the normal gap. Stickers are printed at effectively infinite resolution;
embroidery has a 1.2 mm brush and 4 colours.

### LemonCat — best candidate, do this one first

Colour error is already 21 at **three** colours, because it is genuinely a
three-colour design (yellow, black, cream). The others need five.

I ran it at 3 colours with fine detail dropped: **6,527 stitches, 19 minutes, 2
rethreads** versus 8,483 stitches and 27 minutes at five. It reads well.

Two fixes needed in the source image:

1. **Delete the whiskers or thicken them to ≥1.5 mm.** They measure 0.80 mm and
   came out as broken dashes in the test — exactly as predicted.
2. **Delete the speckle texture on the lemon.** 90,000 sub-1 mm² regions
   contribute nothing but trims.
3. Keep the black keyline, but as a deliberate 1.5 mm outline.

### ScreamingCat1 / ScreamingCat2 / IheartScreaming — need surgery

Typical linework is **0.94–1.09 mm**, at or below the floor, and the thinnest 10%
is 0.19 mm — invisible. They also can't go below 5 colours without colour error
tripling.

The problem is that you are asking the 96 mm field to hold a cat head *and* nine
letters of script *and* eyeball veins *and* water droplets. Pick one:

- **Option A — head only.** Drop "I ♥ Screaming" entirely. The head fills the
  hoop at ~90 mm and linework roughly doubles.
- **Option B — text only.** ~12 mm cap height. Two colours, ~10 minutes.
- **Option C — both, simplified hard.** Remove eye veins, water droplets, fur
  spikes and speckle texture; thicken every outline to 1.5 mm.

Do **not** trace the originals as they are — 0.94 mm linework will not hold.

### Correction: after flattening, the text is fine

The above was measured on the **original** files. Once `stitch flatten` removes
the simulated texture, the text measures well clear of the limits:

| Text feature | Measured | Needed |
|---|---|---|
| White letter bodies | **3.49 mm** | ≥1.2 mm |
| Black keyline | **1.23 mm** | ≥1.2 mm |
| Cap height | **~15 mm** | ≥8 mm (script) |

The text already spans 95.9 mm of the 96 mm field, so a text-only layout would
gain nothing — it is at full size already. **Keep the text.** Dropping it was the
right call for the un-flattened art and the wrong call afterwards.

Flattening is what saved it: the keyline went from 0.77 mm to 1.23 mm, crossing
the threshold, without redrawing anything.

## Rules for generating new patterns

Since these came from an AI generator, fold the constraints into the prompt:

```
flat vector sticker illustration, bold simple shapes, 3 flat colours only,
thick uniform outlines, no gradients, no shading, no texture, no speckles,
no fine linework, no small text, large clear features, solid white background,
centred square composition
```

The additions that matter for this machine specifically: **"no texture, no
speckles, no fine linework"** and **"3 flat colours only"**. The generator will
otherwise add exactly the detail the SE700 cannot render.

Then check before you commit thread:

```powershell
.\stitch.ps1 trace .\images\new.png -o designs\out\new.pes --colors 3 --preview
.\stitch.ps1 info designs\out\new.pes      # run time and rethreads
.\stitch.ps1 validate designs\out\new.pes
```

Read three numbers: **colour fit** (≤22 good), **run time** (under ~35 min), and
**dropped regions** (a big number means too much detail for the hoop).

## Workflow that actually works

1. Generate or pick art.
2. **Simplify it deliberately in an editor** — this is the step people skip, and
   it is the one that decides the result. Delete texture, thicken lines, merge
   colours.
3. Trace at 3–4 colours.
4. Check run time and colour fit.
5. **Test stitch on the same fabric and stabilizer.** Always.
6. Adjust density, re-stitch, then commit to the garment.

Related: [Image → Embroidery](09-image-to-embroidery.md) for the tracer's
mechanics, [Materials](05-materials-and-consumables.md) for stabilizer choice,
[Stitch-Out Playbook](06-stitch-out-playbook.md) for the run itself.
