# The Ink/Stitch pipeline

> For the step-by-step procedure and the verification gates, use
> **`12-design-generation-playbook.md`**. This document is the mechanics: how
> the pipeline works, and the traps in driving a GUI application headless.

This repo has two digitizers. This document says which to reach for.

| | `stitch trace` (built in) | Ink/Stitch |
|---|---|---|
| Written by | this repo | a decade-old open-source project |
| Line art | scanline-fills every shape | **centreline + one continuous path** |
| Travel routing | Dijkstra under fill, home-grown | `underpath`, well tested |
| Speed | seconds | seconds for line art, **minutes** for large fills |
| Editable result | no — raster in, PES out | yes — the SVG is the source |

**Default to Ink/Stitch.** Use `stitch trace` when you want a one-shot
conversion with no SVG round-trip, or when Ink/Stitch's fill router is taking
too long on a big solid region.

The rest of the repo's tooling — `validate`, `info`, `render`, `fix-pes`,
`stage`, the machine-profile limits — applies to Ink/Stitch output exactly as
it does to tracer output, and you should still run it.

---

## Why the switch

The direct question that prompted it: *can the needle avoid crossing empty
space?* Every current design, rebuilt:

| design | | stitches | jumps | machine | hand-snipping |
|---|---|---|---|---|---|
| **LemonCat_outline_on_yellow** (outline, yellow cloth) | tracer | 4,504 | 178 | 11 min | 12 min |
| | Ink/Stitch | **1,741** | **27** | **4 min** | **2 min** |
| **LemonCat_solid_on_white** (solid, white cloth) | tracer | 7,906 | 275 | 21 min | 18 min |
| | Ink/Stitch | **6,197** | **31** | **17 min** | **2 min** |
| **scream2** (2 colour, white cloth) | tracer | 12,742 | 400 | 33 min | 27 min |
| | Ink/Stitch | **11,487** | **152** | **30 min** | **10 min** |

The hand-snipping column is the one that was the actual complaint. Nothing in
any of the three peaks at or above 30 penetrations/mm².

**These are the figures as measured when the switch was made, and the Ink/Stitch
column has moved since.** `satin_params.py` did not exist yet, so those builds
carried no satin underlay; adding it more than doubles an outline design's
stitch count. LemonCat_outline_on_yellow builds today at **3,919 stitches,
14 jumps, ~10 min machine, ~1 min snipping** — more stitches than the row below
says, and fewer jumps. The comparison stands as a comparison, because both
columns were measured in the same batch against the same artwork; it is not a
statement about any current file. For that, read `measured` in
`build/manifest.json`, or run `stitch info`. Every absolute figure in the rest
of this section is from the same batch and carries the same caveat.

All three run in `layered` mode with `:auto`. **Pure `redwork` mode was tried
first on LemonCat_outline_on_yellow and was wrong** — see below.

Ink/Stitch's own Fill-to-Stroke dialog states the underlying point plainly:
*"Fill outlines never look nice when embroidered."* Filling a 1 mm-wide outline
produces two-stitch-wide rows and a jump between every one of them. Converting
that outline to its centreline and running a single stitch down it is both the
correct look and two orders of magnitude less travel.

---

## Install locations

| What | Where |
|---|---|
| Inkscape 1.4.4 | `C:\Program Files\Inkscape\bin\inkscape.exe` |
| Ink/Stitch 3.3.0 CLI | `%APPDATA%\inkscape\extensions\inkstitch\inkstitch\bin\inkstitch.exe` |
| Extension `.inx` files | `%APPDATA%\inkscape\extensions\inkstitch\inkstitch\bin\icons\inx\` |

---

## "Line art" is rarely all line

The trap that cost the most here. `LemonCat_outline_transparent.png` looks like
pure line art — one colour, transparent background, no fills anywhere. It is
not. **44% of its ink area is at least 1.5 mm across**: the eyebrows, the
pupils, the nose and the ear interiors are solid black masses drawn in the same
stroke colour as the whiskers.

Run through pure `redwork`, those masses get centrelined. A solid pupil becomes
a small starburst, a solid eyebrow becomes a single line along its length, and
on fabric they read as **missing**. The outline, whiskers, mouth and ear fur all
came out perfectly, which is exactly what makes it easy to miss — 34% of the
artwork's area went unstitched and the render still looked like a cat.

Diagnose it by **overlaying the stitch path on the source mask** and measuring
unstitched area, not by looking at the render:

| LemonCat_outline_on_yellow build | unstitched source area | peak density |
|---|---|---|
| `-Mode redwork` | 243 mm² of 714 (**34%**) | 20/mm² |
| `-Mode layered -Layer '000000:auto'` | 81 mm² of 714 (11%) | 13/mm² |

The residual 11% is the outer half of each ~1 mm stroke, which is what
centrelining is supposed to do. Cost of the fix: 974 → 1,741 stitches and
2 → 4 minutes. Still one thread, still no rethread, and lower peak density.

`vectorize.py` now measures this and warns before converting:

```
WARNING: 44% of the artwork is at least 1.5 mm wide, i.e. solid rather than stroke.
         Redwork will centreline those areas and they will read as missing.
         Use:  -Mode layered -Layer '<hex>:auto'  to fill them and centreline the rest.
```

**Reserve `-Mode redwork` for artwork that really is all thin strokes.** When in
doubt use `layered` with `:auto` — on genuinely thin art the split simply finds
nothing to fill and the result is identical.

## Line art -> running stitch

```powershell
.\tools\inkstitch_pipeline.ps1 `
    -Image images\LemonCat_outline_transparent.png `
    -Out   designs\out\LemonY_rw.pes `
    -WidthMm 91
```

Stages:

1. **`tools/vectorize.py`** — vtracer, raster to filled SVG shapes, sized in
   real millimetres.
2. **`fill_to_stroke`** — filled linework to centrelines. 10 filled paths came
   back as 191 strokes on the LemonCat.
3. **`redwork`** — those 191 strokes to *one* continuous running-stitch path.
   This is the stage that removes the jumps.
4. **`output --format=pes`**.
5. **`stitch fix-pes`** — see the hoop-code trap below.

## Flat colour -> layered design

```powershell
.\tools\inkstitch_pipeline.ps1 `
    -Image images\LemonCat_solid_yellow.png `
    -Out   designs\out\LemonCat_solid_on_white.pes `
    -Mode  layered -WidthMm 91 `
    -Layer 'FFD600:fill','000000:line' -Skip 'FFFFFF'
```

`-Layer` takes one `RRGGBB:mode` per thread, **bottom layer first** — document
order is stitch order. `-Skip` colours take part in pixel assignment but are
never stitched, so the fabric shows through; that is how the white eyes stay
unstitched on white cloth. Colours in neither list are background.

**Quote the colours.** PowerShell evaluates an unquoted `000000` as the number
`0`. `color_separate.py` rejects malformed hex rather than padding it, because
a wrong guess quietly stitches the wrong colour.

### Choosing `fill` vs `line` per layer

This is the decision that matters, and getting it wrong is expensive. A first
attempt filled *both* layers of the LemonCat:

| layer | cells | p99 | max | cells ≥16/mm² |
|---|---|---|---|---|
| yellow body (genuinely solid) | 2,624 | 5 | **9** | 0 |
| black linework (filled) | 1,062 | 15 | **45** | 10 |

The yellow was flawless. The black was not, and both failure modes came from
the same cause — the black is *linework*, averaging about 0.23 mm wide:

- At 0.4 mm row spacing a 0.23 mm stroke gets zero or one row of fill. The
  whiskers effectively vanished and the ears smeared into the eyebrows.
- Where a dozen such strokes converge — the left ear tip — every travel run in
  the region passes through the same square millimetre. That cell measured
  **52 penetrations/mm²**. See `docs/07-troubleshooting.md`: 30+ means broken
  needles.

So: `fill` only for areas that are genuinely solid; `line` for anything that
reads as a drawn stroke. Line layers go through `fill_to_stroke` → `redwork`
and come out as one continuous running stitch.

`--bleed` (default 0.3 mm) grows each layer under the ones above it so pull
cannot open a seam of bare fabric. Keep it small — colour-boundary stacking was
previously this repo's single biggest source of needle-breaking density peaks.

Layers are merged by `tools/svg_merge.py`, which **refuses** to merge documents
whose viewBox or physical size disagree rather than rescaling them. A layer
1 mm out of register looks like a machine fault, not a tooling bug.

---

## Ink/Stitch as a PES viewer — free, open source, already installed

Ink/Stitch registers **PES as an Inkscape input format** (`inkstitch_input_PES.inx`),
so `File → Open` on a `.pes` reconstructs it as an editable SVG. Once open:

- **Extensions → Ink/Stitch → Visualize and Export → Stitch Plan Preview** —
  simple, needle-points, or **realistic** render modes.
- **… → Simulator** — animates the stitch-out in order, which is the way to see
  pathing and colour sequence.

Both are GUI. The headless equivalent is `stitch proof`, which chains two
Ink/Stitch extensions:

```
input          .pes -> SVG   (Ink/Stitch's own PES reader)
png_realistic  SVG  -> PNG   (thread texture, sheen, true width)
```

```powershell
.\stitch.ps1 proof designs\out\Thing.pes
```

**`png_realistic` shells out to `inkscape.exe` to rasterize.** Ink/Stitch does
not know where Inkscape is installed, so without it on PATH the render dies with
`inkex.command.CommandNotFound: Can not find the command: 'inkscape.exe'`.
`proof.py` locates Inkscape and injects it into the child's PATH.

Why bother when this repo has its own renderer: `proof` is **independent**. It
re-reads the file from disk with a separate implementation. Our writer and our
renderer can share a wrong assumption and agree — that is exactly how linework
3× thinner than the documented minimum passed review repeatedly.

## Traps

These each cost real debugging time. All are load-bearing.

**`inkstitch.exe` is a GUI-subsystem binary.** It writes its result to stdout,
but shell `>` redirection silently produces a **0-byte file** — including the
exact invocation shown in Ink/Stitch's own CLI documentation. Use
`Start-Process -RedirectStandardOutput`. `tools/inkstitch_pipeline.ps1` does.

**Extensions operate on a selection, and headless there isn't one.** The
selection is passed as one `--id=<objectid>` argument per object. With none,
Ink/Stitch prints "Please select one or more strokes" — and **exits 0**. Every
path needs an id before it is handed to an extension; `vectorize.py` and
`color_separate.py` both assign them.

**Ink/Stitch exits 0 on parse failure too.** A malformed SVG produces
"A parsing error occurred..." on stderr, an unchanged document on stdout, and a
success exit code. Both generator scripts re-parse their own output with
ElementTree before returning, so a bad document fails at the source. Do not
build SVG with regex — an earlier `vectorize.py` did, emitted
`<path .../ id="p1"/>`, and cost a full debugging cycle.

**PES export leaves the hoop code at 130 × 180.** Ink/Stitch writes hoop code 1
regardless of design size. The SE700 is a 100 × 100 mm machine. Always finish
with `.\stitch.ps1 fix-pes <file>`, which rewrites the code to 0 and leaves the
geometry untouched.

**Fills are slow.** `underpath` routing on a large region with many holes runs
for minutes, not seconds. This is the router doing real work, not a hang.

**Ink/Stitch restarts its id counter on every invocation.** Two layers that each
went through `redwork` will both contain e.g. `underpath_6139`. Merging them
naively repoints every `url(#…)` reference at whichever copy the renderer sees
first, and the result still renders — so nothing complains. `svg_merge.py`
detects the collision, renames the ids in later documents, rewrites their
references, and asserts uniqueness on the merged result.

**A generated document must declare `inkstitch:min_stitch_len_mm`.** Without it
Ink/Stitch filters nothing, and 11–18% of the stitches in the first designs
built here came out under 0.5 mm — which shows on fabric as white bobbin thread
pulled to the surface. Both generators write it from the machine profile.
**The merged document is the one Ink/Stitch exports from**; settings on the
individual layer files do not carry over.

**`redwork` is not bit-reproducible.** Two runs over identical input gave 974
stitches / 10 jumps and 945 / 7. The variation is small and both results are
good, but do not expect a byte-identical PES from a re-run, and do not treat a
small difference in stitch count as evidence that something changed.

**vtracer stores position in a per-path `transform`, not in `d`.** Copy the `d`
attribute alone and every shape collapses toward the origin. Nothing downstream
objects — the SVG is valid, it renders as a plausible drawing, Ink/Stitch
stitches it, and the PES passes `validate`. The error is invisible until it is
on fabric. `color_separate.check_registration` compares the traced bounding box
against the mask it came from and fails on a gross mismatch. Validity is not
registration; check both.

---

## What the CLI can actually reach

Measured on this machine, Inkscape 1.4.4 with Ink/Stitch 3.3.0, by dumping
`inkscape --action-list` (1213 entries) and reading the bundled `.inx` files.
Worth having written down, because the useful half is not the half you would
guess from the menus.

**Inkscape's own geometry, all headless:** `path-union`, `path-difference`,
`path-intersection`, `path-exclusion`, `path-division`, `path-cut`,
`path-flatten`, `path-fracture`, `path-split`, `path-break-apart`,
`path-combine`, `path-simplify`, `object-stroke-to-path`, `object-to-path`,
plus `select-by-id`, `object-set-attribute` and `object-set-property`.

**There is no offset action.** No `path-inset`, `path-outset` or `path-offset`
exists; Path > Outset and Dynamic Offset are GUI-only. Two headless
substitutes, both verified on a 10 x 2 mm bar:

- The **Offset live path effect** bakes into `d` when the document is loaded and
  saved. But `object-to-path` on an LPE path **reverts `d` to
  `inkscape:original-d` and removes the effect** — the opposite of flattening,
  and silent. If you use the LPE, bake by open/save and strip
  `inkscape:path-effect` and `inkscape:original-d` yourself.
- **`stroke-width` = 2 x growth, then
  `object-stroke-to-path;selection-ungroup;path-union`** grows by exactly the
  intended amount and preserves the fill colour. It rewrites the style block
  into Inkscape's verbose form, which is harmless but noisy.

`tools/svg_offset.py` uses neither: it offsets with Shapely in process. Shapely
is what Ink/Stitch itself uses — the library is bundled at
`extensions/inkstitch/inkstitch/bin/shapely` alongside numpy — so the geometry
agrees with the tool that consumes it, and there is no subprocess to hang.

**Ink/Stitch extensions are callable as actions**, `org.inkstitch.<name>`, and
several are worth knowing:

| Action | What it does |
|---|---|
| `knockdown-fill` | offset -50..+50 mm around a selection, round/mitre/bevel, `keep-holes` — a full offset engine, though it emits a knockdown *fill* |
| `outline` | generates an outline around stitch paths (`threshold`, `buffer`, `smoothness`, `inset`) |
| `fill-to-satin`, `fill-to-stroke`, `stroke-to-satin`, `zigzag-line-to-satin` | conversions between element kinds |
| `cleanup` | removes small unstitchable elements |
| `break-apart` | breaks apart and repairs broken fill shapes |
| `troubleshoot` | marks problematic spots in the document |
| `density-map` | a coloured dot at every stitch position |

**Two of them will hang a headless run**, because their `.inx` declares
`implements-custom-gui="true"` and they open a modal dialog: **`apply-palette`**
and **`element-info`**. `apply-palette` is the tempting one — matching document
colours to a palette sounds like the answer to PES's fixed 64-entry Brother
palette — and it is exactly the one that blocks forever at ~0% CPU. Check that
attribute in the `.inx` before scripting any extension; see the trap above about
12 minutes elapsed against 1 second of CPU.

---

## Parameter reference

Parameters live as attributes in the `http://inkstitch.org/namespace`
namespace, so they can be written directly into the SVG — no GUI needed. The
authoritative list of names is in the bundled templates, e.g.
`...\bin\icons\inx\fill_knockdown.svg`.

The ones `color_separate.py` sets:

| Attribute | Value | Why |
|---|---|---|
| `row_spacing_mm` | 0.4 | Matches this repo's validated fill density; Ink/Stitch's 0.25 default is denser than a 40wt thread needs |
| `angle` | 45 | Off-grain, so rows do not line up with the weave |
| `max_stitch_length_mm` | 3.0 | |
| `staggers` | 4 | Breaks up the needle-penetration ridge between rows |
| `expand_mm` | 0.2 | Pull compensation |
| `underpath` | True | **Travel routed under the fill instead of across bare fabric** |
| `underlay_underpath` | True | Same, for the underlay pass |
| `fill_underlay` | True | |
| `fill_underlay_angle` | angle − 90 | Crosses the top pass |
| `fill_underlay_row_spacing_mm` | 2.5 | |
| `fill_underlay_inset_mm` | 0.5 | Keeps underlay from peeking out at the edge |
