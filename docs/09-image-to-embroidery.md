# Image → Embroidery

Turning a picture into stitches. This is the hardest thing in the repo and the
one where expectations need setting first.

> **Read `12-design-generation-playbook.md` first — that is the procedure to
> follow.** Ink/Stitch is the digitizer for new work; `stitch trace`, which most
> of this document is about, is now the fallback for one-shot conversions and
> for when Ink/Stitch's fill router is too slow. This document remains the
> reference for *why* auto-digitizing behaves as it does, what artwork suits it,
> and what every `trace` setting means — all of which applies to either
> digitizer. The step-by-step and the verification gates live in the playbook.

## The honest version

**Auto-digitizing is not a solved problem.** Every "upload a JPG, get a PES"
service — free or paid — produces files that look plausible on screen and stitch
badly: wrong densities, no underlay, thread breaks, puckering. That is a property
of the problem, not a gap in the tooling.

What *does* work reliably is a narrow band of input: **flat, bold, few-colour
artwork**. Logos. Silhouettes. Line art. Sticker-style illustration. Exactly what
an AI image generator produces when you ask it correctly — which is why the AI
route is genuinely viable where scanning a photograph is not.

`stitch trace` measures this rather than guessing, and tells you before you
thread the machine:

```
colour fit    3.1/255  (good)        <- flat logo, will stitch well
colour fit   17.6/255  (good)        <- line art, fine
colour fit   45.4/255  (POOR)        <- photograph, will look muddy
```

That number is the mean distance between each pixel and the thread colour it got
forced into. Under ~22 is good, over ~40 means embroidery cannot represent the
image and no amount of parameter tuning will fix it.

## Prompting an AI generator for embroidery

I cannot generate images — bring your own from whatever generator you like. The
prompt is what decides whether the result is stitchable, so it matters more than
the tool.

**Ask for:**

```
flat vector illustration, bold simple shapes, 3 flat colours, no gradients,
no shading, thick clean outlines, sticker style, solid white background,
high contrast, minimal detail, centred, square composition
```

**Avoid these words**, all of which produce unstitchable output: *photorealistic,
realistic, detailed, intricate, gradient, soft shadow, ambient occlusion, depth
of field, fur, texture, watercolour, painterly, 3D render*.

**Why it works:** every distinct colour is a thread change you make by hand, and
every gradient becomes visible banding. Flat art has neither.

**Practical asks:**

- **Solid white or single-colour background** — `stitch trace` strips it
  automatically, and does so connectivity-aware, so an enclosed white region
  (the counter of an "O") survives while the surround is removed.
- **Square** for the 4×4 hoop.
- **Three to five colours.** Six means five manual rethreads.
- **No small text.** Below ~6 mm cap height letters turn to mush. Add text later
  with the machine's built-in fonts or Ink/Stitch lettering.

## The embroidery-render trap

**Do not ask an AI generator for "an embroidery patch."** It will paint simulated
satin texture, thread sheen and fabric weave into the pixels. To your eye that
reads as embroidery-ready. To a digitizer it is noise — every fake stitch is a
slightly different shade, so colour clustering fragments and the tracer sees
hundreds of thousands of sub-millimetre regions.

An image that *looks* like embroidery is **harder** to digitize than one that
looks like a sticker. Measured on a real example:

| | AI "embroidery" render | After `stitch flatten` |
|---|---|---|
| Unique colours | 109,080 | **5** |
| Regions < 1 mm² | 308,519 | **34** |
| Typical linework | 0.77 mm ❌ | **1.23 mm ✅** |
| Colour fit | 21.5 | **13.9** |

The flattening pushed the linework across the 1.2 mm safe threshold — the design
went from unstitchable to stitchable without redrawing anything.

```powershell
.\stitch.ps1 flatten .\images\art.png -o .\images\art_flat.png --colors 5
.\stitch.ps1 trace   .\images\art_flat.png -o designs\out\art.pes --colors 4
```

`--colors` on `flatten` **includes the background**, so ask for one more than the
design has. Getting this wrong silently merges small elements — at 4 colours a
red heart on green and black disappeared entirely; at 5 it survived.

### When flatten makes things worse

If a **pale design element sits on a pale background**, flatten can merge the two
into one colour — and then the background strip removes both. A white hard-hat on
cream vanished this way, leaving the text floating in mid-air. Raising `--colors`
to 7 did not separate them, and lowering `--bg-tolerance` to 4 did not either:
once k-means has merged two colours they are the same pixel value, and nothing
downstream can tell them apart.

**Trace the original instead.** Unflattened, that hat measured 91% intact after
background stripping; flattened, 24%. Flatten is a rescue for texture-heavy
renders, not a mandatory step.

Diagnose it in one command — if the background colour holds a suspiciously large
share, something got absorbed:

```powershell
.\stitch.ps1 recolor designs\source\art_flat.png --list
```

Prefer *"flat vector sticker illustration"* in the prompt and skip the problem.
`flatten` is the rescue for art you already have.

## Minimum feature sizes at 4×4

The hoop is 100 mm. A design occupying the full field cannot resolve fine detail:

| Feature | Minimum |
|---|---|
| Filled shape | ~2 mm across |
| Line as a fill | ~1.5 mm wide |
| Line thinner than that | use a running stitch, not a fill |
| Text cap height | ~6 mm |
| Gap between shapes | ~1 mm, or they merge |

`--min-region` drops anything smaller (default 4 mm²) and reports the count. If
it drops a lot, the artwork is too detailed for this hoop — simplify it rather
than lowering the threshold.

## The pipeline

```powershell
# 1. Trace. Fits the hoop, strips background, picks real Brother threads.
.\stitch.ps1 trace designs\source\logo.png -o designs\out\logo.pes --colors 4 --preview

# 2. Look at it before committing thread.
start designs\out\logo.preview.svg

# 3. Validate against the machine.
.\stitch.ps1 validate designs\out\logo.pes

# 4. Send it.
.\stitch.ps1 stage designs\out\logo.pes --to E:\
```

`trace` validates automatically and exits non-zero on a blocking problem, so it
chains safely.

### What it does internally

1. **Fit** to the hoop, leaving a 2 mm margin.
2. **Strip background** — uses the alpha channel if present; otherwise samples
   the four corners and floods inward from the border only.
3. **Quantise** by k-means over *opaque pixels only*, then snap each cluster to
   the nearest of Brother's 64 threads.
4. **Clean** each colour mask: close pinholes, despeckle, drop tiny regions.
5. **Underlay** — a sparse fill perpendicular to the top fill. Costs ~25% more
   stitches and is what stops the fill sinking into the fabric.
6. **Fill** — scan lines at 45°, serpentine, walked in the mask's own coordinate
   space so thin features are not resampled away.
7. **Outline** — a running stitch around each region, stitched last so it covers
   the fill's stepped edges.
8. One thread and one contiguous block per colour, so the machine stops exactly
   once per colour change.

## Tuning

| Flag | Default | When to change |
|---|---|---|
| `--colors` | 5 | Fewer = fewer rethreads. Three is often plenty. |
| `--density` | 0.4 mm | 0.5 for less stiffness on knits; 0.3 for solid coverage on dark fabric |
| `--size` | fits hoop | Smaller design in the middle of the field |
| `--angle` | 45° | Rarely — 45° avoids the axis-aligned artefacts 0°/90° produce |
| `--min-region` | 4 mm² | Raise to drop more speckle |
| `--min-stitch` | 0.5 mm | Rarely. Below this the needle re-enters the same hole |
| `--pull-comp` | 0.2 mm | 0.3–0.4 on stretchy knits; 0 if fine detail is thickening |
| `--travel` | 12 mm | 0 to always trim instead of routing around holes |
| `--no-locks` | off | **Leave on.** Off means every run unravels after its trim |
| `--no-underlay` | off | Faster and softer, but coverage suffers |
| `--no-outline` | off | Outlines usually help; drop for a soft-edged look |
| `--keep-background` | off | When the background *is* part of the design |

### The three that matter most, and why

**`--min-stitch` (0.5 mm).** Sub-0.5 mm stitches make the needle re-enter almost
the same hole while thread is dragged through the eye without advancing. That
sawing weakens the thread until it snaps on the next long move — a leading cause
of mid-design thread breaks. Serpentine fills generate one at every row turn, so
this filter is not optional: on a real design it removed **3,197 of them (22% of
all stitches), leaving 18**.

**`--no-locks` — do not use it.** Tie-in and tie-off are short there-and-back
stitches that anchor a run so it cannot pull out after the machine trims. **The
machine does not add them; they have to be in the file.** A design with ~1,000
trims and no ties will shed thread in wear and the wash. They cost about 5
stitches per run.

**`--pull-comp` (0.2 mm).** Stitching pulls fabric inward, so a filled shape
finishes narrower than drawn. Growing each colour region compensates, and the
side effect is deliberate — adjacent colours overlap instead of leaving a
hairline of bare fabric between them. It does slightly thicken fine detail, so
drop it to 0 if thin linework is closing up.

### Travel routing

When a fill crosses a hole, the alternative to trimming is to walk **around the
hole inside the shape** and keep stitching. Those detour stitches are invisible —
same colour, inside the shape.

Budget the detour against what a trim costs, not against the direct distance: at
400 spm a trim is ~1 s ≈ 6–7 stitches, so a detour several times the direct hop
still wins. Measured on real artwork:

| `--travel` | Jumps | Run time |
|---|---|---|
| 0 mm | 2,217 | 64 min |
| **12 mm** | **1,020** | **54 min** |
| 30 mm | 731 | 57 min |
| 45 mm | 654 | 60 min |

Past ~12 mm the added stitches cost more than the trims they save and run time
turns back up.

### Tatami stagger

A fill is not just parallel rows — it is *tatami*, a brick pattern. Neighbouring
rows offset their needle penetrations so they never line up in columns. Two
reasons, and the second is the important one:

- Aligned penetrations read as ridges or "valleys" running down the fill.
- More seriously, they **perforate the fabric along a continuous line**, which
  it can then tear along. Staggering scatters the holes like bricks in a wall.

`stagger_rows` (default 4) sets how many rows before the phase repeats. Measured
on a 0° fill over a rectangle: unstaggered collapses to 2 phase columns
(peak/mean 4.95); staggered spreads across 4.

Worth knowing when testing: a **45° fill scatters phases naturally**, because
every row is a different length. The defect only shows at 0° or 90°, or on
regular shapes — which is exactly how it goes unnoticed.

## What the algorithm accounts for

Audit of every constraint from the SE700 manual and from digitizing practice,
against what the tracer actually does.

**From the machine's own manual:**

| Manual says | Handled |
|---|---|
| Max pattern 100 × 100 mm | Fitted to 96 mm; `validate` errors on overflow |
| Max 100,000 stitches | `validate` errors; warns past 80% |
| Reads `.pes` `.phc` `.dst` `.pen` only | `validate` errors on other formats |
| Filenames `A-Z a-z 0-9 - _` | `validate` warns |
| "stitch density that is too fine… may break thread or needle" | `max_density_per_mm2` caps travel |
| "three or more overlapping stitches" | Underlay inset removes a layer at the rim; density cap bounds stacking |
| "If the stitches are bunched together, increase the stitch length" | `min_stitch_mm` drops sub-0.5 mm stitches |
| Fabric under **2 mm** for embroidery | Documented — a material choice, not a file property |
| 60 wt bobbin, 75/11 needle | Documented |

**From digitizing practice:**

| Guidance | Handled |
|---|---|
| Fill density ~0.4 mm rows | `density_mm`, default 0.4 |
| Tatami stagger so penetrations don't align | `stagger_rows`, default 4 |
| Pull compensation 0.15–0.2 mm | `pull_comp_mm`, default 0.2 |
| Underlay perpendicular to top fill | Yes, at `underlay_density_mm` |
| **Underlay inset so the top covers it** | `underlay_inset_mm`, default 0.5 |
| Tie-in / tie-off on every run | `lock_stitches` |
| Minimum stitch 0.3–0.5 mm | `min_stitch_mm`, default 0.5 |
| Max stitch 5–7 mm on wearables | `stitch_len_mm`, default 3.0 |
| Closest-join pathing | Nearest-neighbour over components and fragments |
| Fragment regions so each fills continuously | `_scanline_fragments` |
| Convert jumps to travel run stitches | `_travel_path`, bounded by the density cap |
| Light colours before dark | Layers sorted by luminance |
| Distinct thread per layer | Forced in `_quantise` |

**Known gaps, deliberately:**

- **No satin columns.** Borders and lettering are running-stitch outlines, not
  satin. Satin needs centreline extraction from a filled region — a real
  feature, not a setting. Use Ink/Stitch where edge quality is the point.
- **No edge-run underlay.** Only the perpendicular (tatami) kind. Edge run is
  the recommended underlay for knits.
- **No contour or spiral fill** for organic shapes.
- Minimum feature sizes are **reported, not enforced** — the tracer will happily
  stitch a 0.5 mm line and let `assess` tell you it will not hold.

### What did not help

- **Auto fill angle** along each shape's long axis: slightly *worse*. Dominant
  shapes in flat artwork are hole-riddled blobs, not elongated strokes.
- **Trim thresholds** (carrying short hops instead of trimming): no effect on
  PES at all — `pec_encode` ignores TRIM commands and flags every jump as a
  trim-jump. In PEC, trim count always equals jump count.

**Density is the setting that ruins projects.** Too dense and the fabric
perforates and the design goes board-stiff. If in doubt go sparser — 0.45 to 0.5
on anything stretchy.

## Watch for these in the output

- **`<- poor colour match` (ΔE > 15)** — Brother's palette has no close thread.
  Recolour the source art to something the palette *does* have. Check first with
  `.\stitch.ps1 palette --match "#C0392B"`.
- **`jump-heavy` warning** — lots of disconnected regions means lots of trimming
  by hand. Consolidate shapes in the source image.
- **Dropped regions** — detail too fine for the hoop.
- **Enclosed same-colour areas get stitched.** A white hole inside a ring becomes
  a white fill layer. If you want bare fabric there, make it transparent in the
  source image rather than white.

## Higher quality: Ink/Stitch

`stitch trace` does fills, underlay and outlines. It does **not** do proper satin
columns — the dense, raised, tapered stitching that makes commercial embroidery
look sharp on lettering and borders. For that, use Ink/Stitch.

It also has a documented headless CLI, so it can be scripted:

```
inkstitch --extension=zip --format-pes=True input.svg > output.zip
```

That needs Inkscape plus the Ink/Stitch extension installed (neither is on this
machine yet). The workflow is: vectorise or draw in Inkscape → assign Ink/Stitch
parameters per object → simulate → export PES.

**When to reach for it:** lettering, logos with crisp borders, anything where
edge quality is the point. **When `stitch trace` is enough:** filled shapes,
silhouettes, bold flat art — which is most of what AI generators produce well.

## Vectorising first (optional)

`vtracer` is installed and converts raster to clean SVG colour regions. Useful
when you want to hand-edit shapes in Inkscape before digitizing, or feed
Ink/Stitch clean paths:

```powershell
.venv\Scripts\python.exe -c "import vtracer; vtracer.convert_image_to_svg_py('in.png','out.svg', color_precision=4, filter_speckle=8)"
```

Straight-to-stitches via `trace` skips this. Vectorise when you intend to edit.

## Realistic expectations

| Input | Result |
|---|---|
| Flat AI vector art, 3–4 colours | **Good.** Stitches close to the preview. |
| Logo / silhouette / line art | **Good.** |
| Clip art with thin outlines | **Usable.** Expect some detail loss. |
| Photograph | **Poor.** Muddy. Use PhotoStitch in PE-Design instead. |
| Anything with small text | **Poor.** Use built-in fonts or Ink/Stitch lettering. |

Always stitch a test on the same fabric and stabilizer before committing to a
garment. See the [Stitch-Out Playbook](06-stitch-out-playbook.md).
