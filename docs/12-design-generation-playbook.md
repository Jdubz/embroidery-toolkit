# Design Generation Playbook

The ordered procedure for turning artwork into a PES this machine will actually
stitch. `06-stitch-out-playbook.md` covers what happens at the machine; this
covers everything before it.

**Follow the gates.** Every one of them exists because a design shipped here
without it and failed on fabric. Each is a single command. Skipping them is how
a session regresses — the failures in the table at the bottom were all invisible
in the render, and several validated clean.

---

## Start here: is the artwork vector?

**If you have an SVG, use it.** This is by far the best input and it skips most
of what can go wrong:

```powershell
py tools\svg_prep.py images\lemon-cat\Thing.svg work\ready.svg `
    --artwork-mm 91 --skip 'FFFFFF'
```

Then export and gate as normal. No tracing, no centrelining, no stroke-width
guessing — the curves are exact and the stroke widths are *declared*, so
`svg_prep` can tell you before you stitch whether every line clears the
machine's minimum:

```
  stroke widths on fabric: 1.65 - 2.56 mm (machine minimum 1.2)
```

What it handles that the raster path cannot:

- **Sizes the document so the *artwork* is the width you asked for.** An SVG
  canvas has margin; setting the document to 91 mm gave a 73 mm design. It
  measures the drawing bounds with Inkscape and scales accordingly.
- **Resolves inherited `fill` / `stroke` / `stroke-width`.** These are set once
  on a wrapping `<g>` in most hand-authored SVGs. Reading them off the element
  alone found 2 stroked paths in a drawing of 16.
- **Strokes become real satin.** `stroke_method="zigzag_stitch"` stitches a
  stroke at its own declared width, so a 2 mm line is a 2 mm satin column rather
  than a single 0.4 mm running stitch.
- **Splits each shape into fill and stroke operations and groups them by
  colour.** A shape with a yellow fill and a black outline would otherwise force
  a colour change at every shape; grouped, the whole design is one change.
- **`--skip` cuts real holes.** Skipping a colour is *not* the same as bare
  fabric: on screen a white eye sits on top of the yellow body and hides it, but
  in stitches dropping the white just uncovers the yellow and the eye comes out
  yellow. `svg_prep` merges the skipped outline into the fill beneath it as an
  `evenodd` subpath, so it becomes a genuine hole.

Only fall through to the raster path below when there is no vector source.

### Tailoring the artwork before `svg_prep`

`svg_prep` digitizes what it is given; it does not change the drawing. When the
artwork itself needs work — a feature under the machine's minimum, a colour that
should not be stitched, linework that must become negative space — do that first
with `tools/svg_edit.py`, which applies atomic operations and previews each one:

```powershell
.\.venv\Scripts\python.exe tools\svg_edit.py in.svg work\ready.svg --artwork-mm 91 `
    --preview work\steps `
    --op "report" `
    --op "offset --colour 25270A --mm 0.3" `
    --op "drop --colour 000000"
```

`--list-ops` prints the vocabulary: `subtract · drop · recolour · offset ·
pockets · set-stroke · report`. Start with `report` to see what colours and areas
are actually in the file, which is usually not what the picture suggests.

Two specialised tools measure things the operations do not, and are worth running
before deciding anything:

| Question | Tool |
|---|---|
| Is any feature below the minimum, and by how much? | `svg_offset --report` (per colour) · `svg_subpath_filter --report` (per subpath) |
| What is the smallest growth that clears the limit? | `svg_offset --to-min <hex>=1.2` |

For dark cloth this step is usually the *whole* design — see
`14-designing-for-dark-cloth.md`.

## 0. Raster input — pick the mode

Do **not** classify the artwork by eye. Measure it.

```powershell
.\.venv\Scripts\python.exe tools\vectorize.py <image> $env:TEMP\probe.svg 91
```

That prints a warning if a meaningful share of the ink is solid rather than
stroke. Then:

| Artwork | Mode |
|---|---|
| Genuinely all thin strokes, one colour | `-Mode redwork` |
| One colour, but with solid masses in it | `-Mode layered -Layer '<hex>:auto'` |
| Flat colour, several threads | `-Mode layered -Layer 'A:fill','B:auto',…` |

**When in doubt use `:auto`.** On artwork that really is all thin strokes the
width split finds nothing to fill and the result is identical, so `auto` is
never worse. Bare `redwork` is the only option that can silently destroy
content.

> `LemonCat_outline_transparent.png` looks like pure line art — one colour,
> transparent background, no fills anywhere. **44% of its ink is ≥1.5 mm
> across.** Run through `redwork`, the eyebrows, pupils and nose were
> centrelined into skeletons and 34% of the artwork went unstitched. It still
> rendered as a recognisable cat.

For flat-colour work, get the colours from the artwork rather than guessing:

```powershell
.\stitch.ps1 recolor <image> --list
```

**Quote every hex value.** PowerShell evaluates an unquoted `000000` as the
number `0`.

Layer order is stitch order, bottom first. Light before dark — pull
compensation makes neighbours overlap, and whichever colour goes last owns the
boundary. Dark covers a light edge cleanly; light over dark shows every stray
stitch.

---

## 1. Generate

```powershell
.\tools\inkstitch_pipeline.ps1 -Image images\Thing.png -Out designs\out\Thing.pes `
    -Mode layered -WidthMm 91 -Layer 'FFD600:fill','000000:auto' -Skip 'FFFFFF'
```

Sizing: **96 mm is the working maximum** on a 100 mm field. 98% of Brother's own
128 built-in designs stay within 96 mm, so this is their practice, not just
caution.

Fills take minutes, not seconds — `underpath` routing is doing real work. The
pipeline bounds the wait and scrapes any modal dialog rather than hanging
forever.

`-Skip` colours take part in pixel assignment but are never stitched, so the
fabric shows through. That is how white eyes stay unstitched on white cloth.

---

## 2. The gates

Run all five. They take about a minute.

### Gate 1 — does it fit, and is the container right?

```powershell
.\stitch.ps1 validate designs\out\Thing.pes
```

Must be `[OK]` or `[INFO]`. Any `[WARNING]` or `[ERROR]` is a stop.

Covers: field overflow, stitch overflow, PES origin centred instead of at
(0,0), PES section misplaced, hoop code left at 130×180, hand-trimming load,
runtime, **short stitches**, and **peak penetration density**.

The pipeline already runs `fix-pes`; this confirms it took.

### Gate 2 — is any of the artwork missing?

```powershell
.\stitch.ps1 coverage designs\out\Thing.pes --source images\Thing.png `
    --skip FFFFFF --overlay work\overlay.png
```

**This is the gate nothing else can replace.** `validate` reads the PES alone
and cannot know what the design was supposed to be — a design missing its
eyebrows validates perfectly and renders beautifully.

- Under ~5% missing: fine for filled work.
- 12–20%: normal for pure line art (the outer half of every centrelined
  stroke). Suspicious for anything else — open the overlay.
- Over 25%: the command exits non-zero. Solid areas are being centrelined; use
  `:auto`.

Do **not** substitute connected-region counting. When LemonCat_outline_on_yellow lost every solid
mass, all ten source regions still reported ≥44% coverage. The component count
showed nothing while a third of the artwork was gone.

### Gate 3 — will it break needles?

Included in Gate 1 as the `density-peak` finding, but know what it means:

| penetrations/mm² | meaning |
|---|---|
| ~3 | normal fill |
| 8–12 | underlay + fill + outline overlapping; fine |
| 16 | the tracer's travel-routing cap |
| **30+** | the manual's own failure mode; expect broken thread and needles |

Never judge this by eye or by average — **the median sits at 3.0 whether the
design is safe or lethal.** Only the peak and the count of hot cells reveal it.

If it fires, cut passes in this order: outline, then underlay, then lower
`--max-density` or `--travel`. Measured on one design, dropping the outline and
underlay improved *every* axis at once: 18,830 → 12,742 stitches, 568 → 400
jumps, 21 → 19 peak density.

### Gate 3b — is the satin actually covering?

Included in Gate 1 as the `satin-coverage` finding. It exists because **a render
cannot show coverage.** A preview draws each stitch as a line, so a sparse comb
and a solid column look identical, and `stitch proof` showed solid black on a
file that stitched almost bare.

**Satin is judged against the validated fill density, not a separate number.** A
satin is a fill rotated 90 degrees — if 0.4 mm rows cover, 0.4 mm satin covers.
The finding fires only past `fill_density_mm × satin_sparse_factor` (0.6 mm).

> **Retracted, kept on purpose.** This section previously insisted satin needed
> 0.25 mm against a 0.4 mm `thread_width_mm`, and that reusing the fill spacing
> caused a failed stitch-out. That was wrong twice over: Ink/Stitch's default
> satin spacing *is* 0.4 mm and covers fine, and the check as written flagged
> both that default and this repo's own validated density as defects. The actual
> cause was the zigzag *mode*, not the spacing. **Before trusting a new check,
> run it against a known-good file — if it fires there, the check is wrong.**

Two things that do matter for satin, both learned on fabric:

- **Use real satin columns.** `stroke_to_satin`, never
  `stroke_method="zigzag_stitch"` — Ink/Stitch's docs warn against the latter
  for borders, and it stitches sparsely around the outside of curves.
- **Add underlay, banded by column width.** `stroke_to_satin` emits columns
  with none. Without it the satin sinks into the weave and bobbin thread shows
  along the rails. `tools/satin_params.py` adds it after conversion, choosing
  per column the way Ink/Stitch's own guidance does — centre-walk to 2 mm,
  **+ contour 2–3.5 mm**, + zigzag beyond. It reads the widths `svg_prep.py`
  measured, because `stroke_to_satin` throws them away.

  The mechanism: a satin puts every penetration on two lines 0.4 mm apart —
  2.5 needle holes per mm, in a row — so the weave along the rail is perforated
  and the knot has little to grip. Contour underlay anchors the rails;
  centre-walk does nothing there.

  **No stitch-out failure here has been traced to the band.** The one that
  looked like it — LemonCat_outline_on_yellow, bobbin thread over the whole 2.56 mm outline while
  its fills came out black — turned out to be an improperly threaded bobbin,
  and rethreading fixed it with no change to the file. Treat the bands as
  vendor guidance worth following, not as a diagnosis. If a satin comes out
  swamped, `07-troubleshooting.md` first.

The check detects satin geometrically — sustained rail-to-rail reversals across
a column at least `min_satin_width_mm` wide — so an isolated serpentine turn or
a tie-off is not mistaken for it. `scream2`, which contains no satin at all,
correctly reports zero satin pairs.

### Gate 4 — look at the actual stitches

```powershell
.\stitch.ps1 proof   designs\out\Thing.pes                      # independent, photorealistic
.\stitch.ps1 render  designs\out\Thing.pes -o work\r.png --fabric "#F2C50A"
```

**`proof` is the one to trust.** It re-reads the PES with Ink/Stitch's own
importer and renders it with Ink/Stitch's own engine — thread width, texture and
sheen to scale. Nothing in this repo touches it, which is the point: our writer
and our renderer can share a wrong assumption and cheerfully agree with each
other. A defect that survives `proof` is in the file.

That independence is not theoretical. Linework 3× thinner than the documented
minimum passed visual review repeatedly, because the check was drawing thread as
a hairline and so was the thing being checked.

`render` remains useful for judging the design against a specific fabric colour,
and `--show-jumps` for pathing.

**Never diagnose from the machine's LCD preview or `preview.render_png`** —
both draw travel between stitches, so a trim-heavy fill renders as scribble
even when the file is perfect.

### Gate 5 — the run cost

```powershell
.\stitch.ps1 info designs\out\Thing.pes
```

Check the numbers against what this machine is built around, from Brother's own
128 designs: median 3 colours, median 7 minutes, 99% under 45 minutes.

Jump count is **hand labour**, not machine time — this machine does not trim
jumps within a colour, so every one is a float you snip. `info` reports the
snipping load directly.

---

## 3. Stage and transfer

**Design Database Transfer is the preferred route.** DDT reads a PC folder
directly, so `designs\out` is already the staging area — there is no copy step.

```powershell
.\stitch.ps1 stage designs\out\Thing.pes
```

With no `--to` this runs the validation gate and prints the wireless checklist.
DDT itself does **not** check that a design fits the hoop; this is that check.
Then transfer from DDT with `designs\out` selected in its folder pane.

**On the machine, retrieve from the wireless pocket — source 3 — not from
machine memory.** A transfer does not overwrite a design already saved to
memory. If you saved `Thing` on an earlier run, that older copy is still there
and still selectable, and choosing it stitches the old geometry with no
indication anything is wrong. This is the first thing to check when a
regenerated design behaves exactly like the previous revision.

Wirelessly transferred designs are deleted at power-off. Save to machine memory
only if you want to keep one — and delete the previous copy of that name first.

For USB instead:

```powershell
.\stitch.ps1 stage designs\out\Thing.pes --to E:\
```

Either way `stage` refuses designs with blocking errors. Keep it that way.

---

## Regressions this playbook prevents

Every row shipped here at some point. The gate is what now catches it.

| Failure | How it presented | Caught by |
|---|---|---|
| Solid masses centrelined into skeletons | Rendered fine; 34% of artwork unstitched | Gate 2 |
| Whiskers vanished, ears smeared | Fill applied to 0.23 mm linework | Gate 2 + `:auto` |
| Travel routing piled thread to 111/mm² | Broken thread, broken needles | Gate 3 |
| Colour-boundary stacking | 83% of hot cells on one seam | Gate 3 |
| Sub-0.5 mm stitches (11–18% of design) | **White bobbin thread on the surface**; thread sawn through | Gate 1 (`short-stitches`) |
| No tie-in/tie-off | Runs unravel in wear or the wash | `raster._add_locks`; Ink/Stitch does its own |
| PES centred on origin | DDT showed only the bottom-right quadrant | Gate 1 (`pes-origin-centred`) |
| Hoop code left at 130×180 | Preview tiny and off-centre in DDT | Gate 1 (`pes-hoop-mismatch`) |
| vtracer transform dropped | Valid SVG, plausible drawing, wrong place | `color_separate.check_registration` |
| Fill sewn across letter counters | Crisp lettering became a slab | `raster._connector_inside` |
| Design over 100 mm | Simply absent from the machine's list | Gate 1 (`field-overflow`) |

## Current designs, as a reference for what "good" looks like

All three built through this playbook, all `[INFO]` on every gate:

| | size mm | stitches | cols | jumps | short mid-run | peak /mm² | machine | snip |
|---|---|---|---|---|---|---|---|---|
| LemonCat_outline_on_yellow (outline, yellow cloth) | 84.8 × 58.8 | 1,548 | 1 | 26 | 1.2% | 14 | 4 min | 2 min |
| LemonCat_solid_on_white (solid, white cloth) | 85.0 × 59.2 | 5,548 | 2 | 31 | 0.4% | 14 | 15 min | 2 min |
| scream2 (2 colour, white cloth) | 82.2 × 80.6 | 9,863 | 2 | 152 | 1.5% | 18 | 26 min | 10 min |

Coverage against source: LemonCat_solid_on_white 100%, scream2 98%, LemonCat_outline_on_yellow 84% — the last being
line art, where the outer half of every centrelined stroke is legitimately
unstitched.

Note the commands are not bit-reproducible: Ink/Stitch's `redwork` router varies
slightly between runs (974/10 one run, 945/7 the next on identical input). Small
differences in stitch and jump counts are normal and are not evidence that
something changed.

## Things that are not true here

Standard embroidery advice that is wrong on this machine. Do not repeat it.

- **"Slow the machine down."** Impossible. The speed controller is disabled
  while embroidering and there is no embroidery speed setting. 400 spm is fixed.
- **"Use the SA434 hoop for bigger designs."** It attaches but the field is
  still 100 × 100 mm.
- **"6–8 stitches per mm for fills."** A commercial figure. 0.4–0.45 mm row
  spacing here, and err sparse.
- **"Reduce trims to save time."** PEC trim count always equals jump count;
  trims cannot be reduced independently, only by reducing jumps.
- **"Adjust the density on the machine."** The thread density key only affects
  built-in alphabet and frame patterns, never an imported design.
- **"Oil it."** The manual prohibits it.

## When something looks wrong

Diagnose by measurement, in this order — each of these caught a real bug that
the previous one missed:

1. `coverage` against the source — is anything simply absent?
2. 1 mm-cell density histogram — where are the peaks, and are they on colour
   boundaries, region rims, or interiors?
3. Stitch-length distribution — how much is under 0.5 mm, and is it mid-run or
   at run ends (locks are supposed to be short)?
4. `render`, not the machine preview.
5. Count paths **at the source** — underlay / fill / outline. Inferring jump
   origins from totals sent this work down two wrong paths.

None of these can see a shape stitched in the **wrong colour**. `coverage` asks
whether pixels got stitched, not which thread reached them, so a fill sewn over
the shape that was meant to sit on top reports 100% and validates clean. Render
on the fabric colour the piece is actually for — `render --fabric` — and check
the `stitch order` line `svg_prep` prints against the artwork's own painting
order. See `14-designing-for-dark-cloth.md`, where this is the main hazard.
