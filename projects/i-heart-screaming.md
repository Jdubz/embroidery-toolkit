# I ♥ Screaming — 3 colour, vector source

**Date:** 2026-08-10
**Design:** `designs/out/Scream.pes`  *(one file per design; the numbered
Scream3–6 builds below are history, and only the final one survives on disk)*
**Vector master:** `designs/source/I_Heart_Screaming_prepared.svg`
**Source art:** `images/finals/I_Heart_Screaming_hollow_spit_embroidery_FINAL.svg`

Supersedes `screaming-2color.md`, which was traced from a raster derived from an
AI render. This one starts from clean vector: 3 paths, one per thread colour,
`fill-rule="evenodd"`, `M`/`L`/`Z` only, white as transparent negative space.

## Target

| | |
|---|---|
| Item | white / off-white cloth, patch |
| Design size | 87.4 × 95.8 mm |
| Stitch count | 10,751 (19 jumps) |
| Colours | 3 — green, red, black |
| Run time | ~30 min (27 sewing + 3 rethreading) + ~1 min snipping |

**Sized by height, not width.** The artwork is 1073 × 1179 units, so at the
usual 91 mm width it comes out 100.0 mm tall — exactly the field, with no
clearance. 87 mm wide gives 95.6 mm tall, inside the 96 mm working maximum.

## Setup

| | |
|---|---|
| Hoop | SA432 4×4 |
| Stabilizer | cut-away (see the bobbin note below) |
| Needle | 75/11 |
| Top thread | 40 wt — green, then red, then black |
| Bobbin | **60 wt**, and check it is seated under the tension spring |

Stitch order is green → red → black, light to dark, so black owns every
boundary. All white areas are unstitched: eyeballs, teeth, the "Screaming"
letters and the forehead star are cloth showing through. **This design only
works on light cloth** — on anything dark those areas need a white fill layer
and it becomes a 4-colour job.

## The thin-detail decision

43% of the source ink measures under the 1.2 mm safe minimum. Most is
structural black keyline and stays. The rest was isolated and genuinely
unstitchable:

| Dropped | Measured | Why |
|---|---|---|
| 14 red eye-vein subpaths | 0.40–0.80 mm | Machine constraint — every one under the 1.0 mm minimum. |
| 1 green sliver near the mouth | 0.80 mm | Machine constraint. |
| Green star centre (15.8 mm²) | 3.40 mm | **Look choice, not a constraint** — it stitches fine. Leaves a white star inside the black rim. |

Heart (11.80 mm) and tongue (4.40 mm) are untouched, as is all black.

*(Widths restated after the local-thickness measurement was corrected: adaptive
radius stepping had been quantising anything above ~1.6 mm, reporting the star
as 3.24 mm and the heart as 10.53. The veins were always in the fine band and
are unchanged, so no decision moved — and the built file is byte-identical.)*

Removing the veins is what made the red pass cheap: **973 stitches / 8 jumps →
559 / 2**. Every isolated small fill needs a jump in, a tie-in and a tie-off,
and those scattered sub-millimetre fills are the fragile ones.

Alternatives considered and rejected: thickening every vein to 1.2 mm (tripled
their drawn width and crowded both eyeballs); thinning them by area (the
smallest are 0.0–0.9 mm² specks, so dropping those changed nothing visible);
selecting a spatially even subset (worked, but the two-shape red pass won).

## How it was built

Reproducible from the original art:

```powershell
# 1. Drop the sub-minimum subpaths and empty the star. The two selectors are
#    deliberately separate: --drop-thin is the machine constraint, --drop-at is
#    the look change. Both are colour-scoped — an unscoped width rule would
#    delete the black keyline, which is one long subpath and measures thin
#    everywhere.
.\.venv\Scripts\python.exe tools\svg_subpath_filter.py `
    "images\finals\I_Heart_Screaming_hollow_spit_embroidery_FINAL.svg" `
    "designs\source\I_Heart_Screaming_prepared.svg" --artwork-mm 87 `
    --drop-thin EE2028=1.0 --drop-thin 73B236=1.0 --drop-at 73B236=62.7,19.3

# 2. Vector -> PES. No strokes in this artwork, so everything is auto_fill and
#    no satin columns are produced.
.\tools\svg_to_pes.ps1 -Svg "designs\source\I_Heart_Screaming_prepared.svg" `
    -Out designs\out\Scream.pes -ArtworkMm 87

# 3. Gates.
.\stitch.ps1 validate designs\out\Scream.pes
.\stitch.ps1 coverage designs\out\Scream.pes --source <prepared art as PNG>
.\stitch.ps1 proof    designs\out\Scream.pes
.\stitch.ps1 stage    designs\out\Scream.pes
```

Run `svg_subpath_filter.py --report` first on any new artwork — it lists every
subpath with area, width and even/odd nesting depth, which is the only way to
see a fill that is too thin. `svg_prep` reports stroke widths and this design
has no strokes at all.

## Gate results

| Gate | Result |
|---|---|
| `validate` | clean — 0% short stitches mid-run, no density or satin findings |
| `coverage` | 100% (1 mm² of 4,364 unstitched) |
| `proof` | white eyeballs, empty star, all keyline legible |
| `info` | 30 min, under the 45 min warning |

Per-colour: green 2,555 st / 2 jumps · red 559 / 2 · black 7,637 / 15.

## Notes carried forward

- **Width measured on a strict local-max ridge is wrong on compact shapes.** It
  reported 0.10 mm for the forehead star, which is 3.3 mm across, because the
  star has five ridge pixels and two are corner artefacts. That nearly got a
  perfectly viable fill deleted as "sub-minimum". **Fixed** — width now lives in
  `embroidery_tools.measure` as local thickness by granulometry, shared by
  `artwork_prep.py` and `svg_subpath_filter.py`, with nine tests covering shapes
  of known width. The figures in the table above are the corrected ones; the
  decisions they support are unchanged, and the prepared SVG is byte-identical
  before and after the fix.
- **Coverage passing 100% does not clear a thin-feature problem.** It only asks
  whether a stitch passes within 0.4 mm. The as-drawn build scored 100% with
  veins that were never going to read.
- `expand_mm: 0.2` adds 0.4 mm to every fill's width, so measured artwork width
  understates what lands on fabric. Worth remembering before condemning
  something as too thin.

## Stitch-out 1 — Scream4, 2026-08-10: needle bent, then broke

Green ran almost to the end, then the needle bent and threw the pattern off
registration. A fresh needle broke almost immediately into red.

**The file was measured afterwards and does not explain it.** Peak density
15/mm² against a cap of 16, only two cells at ≥12, median 2. At the point green
failed: median 3 penetrations/mm², max 8, 8 mm from any design edge, zero
stitches in the top/bottom 3 mm — and green is the first pass, so there was no
other colour's thread in the cloth to punch through. Do not go looking for a
density fault here; there isn't one.

Most likely mechanical. The manual's first cause for a bent needle is fabric
hanging over the table stopping the embroidery unit moving freely, so the frame
strikes the needle. The second break was probably consequential: a bend leaves
the needle plate and hook burred, and the thrown-off pattern leaves a thread
mass to drive into.

Two things the file *does* flag, both worth fixing anyway:

- **Size.** 87.4 × 95.8 mm centred in a 100 × 100 field leaves **2.1 mm top and
  bottom**. Longest edge 95.8 mm against Brother's own 128 built-ins: median
  78.7, p90 95.4. The carriage runs to its limits, which is when any restriction
  bites. The red heart — first element of the red pass — sits in that band.
- **Colour boundaries carry all the density.** 100% of the forty densest cells
  sat on one; median 4/mm² against 1 in single-colour areas. That is `expand_mm`
  growing each colour outward independently so both sides claim the same band.
  It threatens the **black** pass most: 7,637 stitches, stitched last, bordering
  everything.

## Scream5 — reliability build, same size

`designs/out/Scream5.pes`. Size deliberately unchanged, so the 2.1 mm margin
remains; only the density levers moved.

```powershell
.\tools\svg_to_pes.ps1 -Svg "designs\source\I_Heart_Screaming_prepared.svg" `
    -Out designs\out\Scream5.pes -ArtworkMm 87 `
    -Spacing 0.45 -Expand 0.1 -NoFillUnderlay
```

| | Scream4 | Scream5 |
|---|---|---|
| Stitches | 10,751 | **6,955** (−35%) |
| Thread laid | 21,671 mm | **13,329 mm** (−38%) |
| Peak density | 15/mm² | **10/mm²** (−33%) |
| Cells ≥12/mm² | 2 | **0** |
| Boundary cells | 955 | 754 (−21%) |
| Median density on boundaries | 4/mm² | 3/mm² |
| Run time | 30 min | **20 min** |
| Coverage | 100% | 100% |

**The cost is visible in the proof: fills are noticeably more open**, green worst.
Dropping the underlay is most of that — it fills the interstices between rows as
well as supporting them — with 0.45 mm spacing adding to it. Short stitches also
went 0% → 1% (79 mid-run), still under the 2% threshold but a regression.

If that reads too sparse on fabric, the middle setting is `-Expand 0.1
-NoFillUnderlay` at the standard 0.40 mm spacing: keeps most of the density
reduction and most of the coverage.

**`svg_prep` gained `--expand` and `--no-fill-underlay` for this.** Note that
`fill_underlay` is one of the few parameters that must be written to be turned
*off* — Ink/Stitch defaults it to True, so staying silent is not the same as
accepting a safe default.

## Stitch-out 2 — Scream5: thread nest at the red colour change

Green ran clean. The instant red started, the top thread was pulled down under
the plate into a nest, jamming the mechanism and locking the fabric in place.

**Both failures now sit at the same moment: the first stitches after the
green→red rethread.** Green is threaded at idle before the run; red is threaded
mid-job with the hoop loaded. That procedural difference is the only variable
that tracks the failures.

Scream5 is measurably *gentler* at the red start than Scream4 — ties 0.67–0.72 mm
against 0.30 mm, and 2.78 mm of thread in the first five stitches against
1.20 mm — and it still nested. **The design is not the cause.** The two live
candidates are the rethread procedure (presser foot down closes the tension
discs; a short unheld tail gets pulled down by the first loop) and the red spool
itself (cap size, thread catching under the spool).

Density was also reverted after this run: Scream5's open weave was judged worse
looking, and the needle failures turned out not to be density-related anyway.

## Current build — `designs/out/Scream.pes`

Built as Scream6, then renamed when `designs/out` was cut back to one file per
design. Scream4's weave, plus a fixed tack at every run start.

```powershell
.\tools\svg_to_pes.ps1 -Svg "designs\source\I_Heart_Screaming_prepared.svg" `
    -Out designs\out\Scream.pes -ArtworkMm 87
```

### Every parameter, and why

| Parameter | Value | Why |
|---|---|---|
| artwork width | 87 mm | height-capped — 91 mm would be exactly 100.0 mm tall |
| `row_spacing_mm` | 0.40 | profile `fill_density_mm`; validated for 40 wt through a 75/11 |
| `expand_mm` | 0.2 | the three colour paths abut with **zero overlap** in the vector (green∩red 0 px, green∩black 54 px of 88,802), so pull compensation is genuinely load-bearing here |
| `underpath` | True | SE700 does not trim jumps within a colour |
| `fill_underlay` | Ink/Stitch default (on) | restored; it fills the interstices and is most of the tight look |
| `lock_start` / `lock_end` | **`bowtie`** | new — see below |
| `min_stitch_len_mm` | 0.5 | from the profile, on the document |
| stitch order | green → red → black | light to dark; the last colour owns every shared boundary |
| angle, staggers, max stitch length | untouched | no machine-specific reason to override |

### The tack, and a trap

Ink/Stitch's default `lock_start` is `half_stitch` — the tie is **half the first
stitch**, so it inherits whatever the fill happened to begin with. Scream4's red
opened with four 0.30 mm ties: four penetrations in nearly one hole, giving the
take-up almost nothing to pull against at the exact moment a freshly rethreaded
thread is most likely to nest.

**`back_and_forth` was tried first, from the docs, and is not a valid value in
3.3.0.** It was silently ignored and produced a PES byte-identical to the run
without it — caught only by hashing the output. Measured on a test fill:

| style | opening stitches (mm) | min | thread before the fill |
|---|---|---|---|
| `half_stitch` (default) | 0.71 0.78 0.78 0.71 | 0.71 | 2.98 mm |
| `triangle` | 0.76 0.76 0.85 | 0.76 | 2.37 mm |
| `star` | 1.43 1.27 1.26 1.14 0.71 | 0.71 | 5.81 mm |
| **`bowtie`** | 1.08 1.22 1.00 1.00 | **1.00** | 4.30 mm |
| `back_and_forth`, `custom` | — | — | **ignored** |

Verified in Scream6's own stitch data, not assumed:

| colour opens with | Scream4 | Scream6 |
|---|---|---|
| green | 0.76 ×4 | 1.06 1.17 1.03 1.04 |
| **red** | **0.30 ×4** | **0.98 1.14 1.02 1.00** |
| black | 0.76 ×4 | 1.00 1.14 1.02 1.03 |
| thread in red's first 5 stitches | 1.80 mm | **4.75 mm** |
| stitches under 0.5 mm (incl. ties) | 99 | 76 |

Same 10,751 stitches — the tack replaces the old ties rather than adding to them.

Gates: `validate` clean (0% short mid-run), `coverage` 100%, `proof` matches
Scream4's weave, `stage` ready.

## Result

- [ ] Test stitch-out on matching scrap first
- [ ] Bobbin checked: 60 wt, seated under the tension spring, dial at 4
- [ ] **Needle plate and hook checked for burrs after the 2026-08-10 break**
- [ ] **Fabric supported level with the bed, not hanging over the table**
- [ ] Fresh needle, checked straight on a flat surface before fitting

**What worked:**

**What didn't:**

**Change next time:**
