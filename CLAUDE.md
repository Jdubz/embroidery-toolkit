# CLAUDE.md

Guidance for Claude Code working in this repository.

## Making a design? Follow the playbook

`docs/12-design-generation-playbook.md` is the procedure. It exists because the
failures in this repo have all been **invisible in the render and clean in
`validate`** — a design missing every solid element still looked like a cat, and
a design with 18% sub-0.5 mm stitches still passed every check that existed at
the time.

The five gates, all one command each:

| | |
|---|---|
| `stitch validate` | field, container, short stitches, peak density, **satin coverage** |
| `stitch coverage --source <art>` | **artwork that never got stitched** — nothing else can see this |
| density-peak finding | the needle-breaking failure mode |
| `stitch proof` | **photorealistic render by Ink/Stitch, not by us** — the independent check |
| `stitch render` | the real stitches on a chosen fabric colour, never the machine's preview |
| `stitch info` | run time and hand-snipping load |

**If a vector source exists, use `tools/svg_prep.py` — not the raster pipeline.**
Tracing exists to recover geometry from pixels; with an SVG the curves are exact
and stroke widths are declared rather than measured. It also gets things the
raster path cannot: strokes become real satin at their declared width
(`zigzag_stitch`), fill and stroke are split and grouped so a two-colour design
needs one colour change, and `--skip` cuts genuine holes instead of merely
uncovering the fill underneath. Live example: `images/lemon-cat/*.svg`.

For raster input, default to `-Mode layered -Layer '<hex>:auto'`. Bare
`-Mode redwork` is the only option that can silently destroy content, and "it
looks like line art" is not evidence — measure it.

**`stroke_to_satin` emits satin columns with NO underlay.** Verified — the
converted SVG carries `inkstitch:satin_column` and zero underlay attributes. A
satin with nothing beneath it sinks into the weave, the top thread sits low
relative to the bobbin, and bobbin colour shows along the rails. Observed on
fabric. `tools/satin_params.py` adds it back.

**Underlay is banded by column width.** Ink/Stitch's own guidance, adopted here
on that authority rather than on fabric evidence: centre-walk up to 2 mm,
**+ contour 2–3.5 mm**, + zigzag beyond. `satin_params.py` measures each column
from its **own geometry** — the median rail-to-rail distance, via
`embroidery_tools.svgpath`.

It has to measure, because nothing else survives: `stroke_to_satin` discards the
source id, forces `stroke-width:1px`, and does **not** promise one column per
input stroke — on the solid LemonCat it turned 9 strokes into 11 columns. An
earlier version joined columns positionally against the widths `svg_prep` wrote
to `.stroke-widths.txt`; that join broke on exactly that file and every column
fell back to one blanket underlay. The widths file is still written, but now
only as a cross-check that prints the measured/declared ratio.

Two traps in measuring a satin column, both hit:

- **Point count does not tell a rail from a rung.** A rail is frequently a
  single cubic, `M x,y C ...`, so it has two on-curve points and looks exactly
  like a straight two-point crossbar. Discriminate on whether a *curve command*
  contributed — `svgpath.parse_path` records it.
- **Rung length is not the width.** Rungs overshoot so they reliably cross both
  rails; measured on real output they run ~1.2× the true width. Use rail-to-rail
  distance, which has no fudge factor.

`svgpath.py` raises on an unrecognised path command rather than skipping it. That
matters more than it looks: if an unknown letter fails to tokenise, its
coordinates get swallowed as arguments to the previous command and the path
parses "successfully" into the wrong geometry.

**Do not invent the contour inset.** It was hard-coded to 0.2 mm here — half
Ink/Stitch's 0.4 mm default and below its documented 0.4–0.6 mm range. At
0.2 mm the underlay's own penetrations land back on the rail's perforation
line, which is the thing contour underlay exists to get clear of. Removed; the
vendor default applies. Same rule as everywhere else in this pipeline: write a
parameter only when this machine demands something different.

Neither of the two changes above was the cause of any known stitch-out failure.
They are adopted on vendor-guidance grounds — see the correction below before
citing them as fixes for anything.

*Correction, kept deliberately — this one cost a session.* LemonCat_outline_on_yellow came off the
machine with white bobbin thread lying over the entire 2.56 mm satin outline
while its fills, one pass earlier on the same thread and the same bobbin, came
out solid black. **The cause was an improperly threaded bobbin.** Confirmed on
fabric: rethreading it fixed the design outright, no other change.

Two things to take from that, because the reasoning that went wrong is
seductive:

- **A symptom that is selective by stitch type is NOT evidence of a design
  defect.** "Fills clean, satin swamped" was treated here as proof the file was
  implicated, and a rail-perforation theory was built on it. A bobbin bypassing
  its tension spring explains it on its own: the bobbin thread is dragged up
  wherever the cloth grips the knot least, and a satin rail — 2.5 needle holes
  per mm on a single line — grips far worse than a sparse staggered fill in
  intact weave. One fault, two substrates.
- **`docs/07` already had the answer, and it was reached for and then walked
  past.** Its *swamped* row sends straight to incorrect bobbin threading, and
  the manual (p.85) lists "the results do not change even after the thread
  tension is adjusted" as a symptom of precisely that — which the user had
  already reported. **Finish the machine-side triage before measuring the
  file.**

A diagnostic that does hold, and is worth keeping: an earlier pass called this
file "centre-walk only, contour missing". It had both. Underlay offsets from the
column centreline were bimodal — a spike at 0.0 mm *and* one at 1.0–1.25 mm —
and only the median was read. **When underlay looks absent, histogram the
offsets; a median near zero says nothing, because centre-walk sits at zero
whatever else is present.**

The mirror of the rule further down this file: there, a mechanical explanation
was reached for while this repo's own parameters were what had moved. Here the
reverse. **Establish which side actually changed before theorising on either.**

**A validation check that flags the repo's own validated values is itself the
bug.** The first `satin-coverage` check compared satin spacing against a
`thread_width_mm` of 0.4 — the same number `design_limits.fill_density_mm` calls
the correct fill density. It therefore reported Ink/Stitch's default satin as
defective, and worse, it made a marginal 0.41 mm spacing look like the cause of
a failure it did not cause. Two stitch-outs were spent on that wrong diagnosis.
A satin is a fill rotated 90 degrees: judge it against `fill_density_mm` times
`satin_sparse_factor`, never against an independently invented figure. **Before
trusting a new check, run it against a known-good file** — if it fires there,
the check is wrong.

**Use `stroke_to_satin`, not `stroke_method="zigzag_stitch"`.** Ink/Stitch's own
docs: *"It is not recommended to use the zigzag stitch mode to create a satin
border, use Satin Column instead"*, and *"sharper curves and corners will result
in sparse stitching around the outside of the curve."* A design that is mostly
curves — any animal outline — is the worst case for it. Switching to real
two-rail satin columns is what finally put visible thread on the fabric.

*Correction, kept deliberately:* an earlier entry here claimed satin needed
0.25 mm spacing against a 0.4 mm "thread width" and that reusing the fill
spacing caused the failure. **That was wrong.** Ink/Stitch's default satin
spacing is 0.4 mm and covers fine — a satin is a fill rotated 90 degrees. The
real defect was the zigzag *mode*, not the spacing. Two stitch-outs were spent
chasing the wrong number.

Two lessons that do hold. **A render cannot show coverage** — each stitch draws
as a line, so a sparse comb and a solid column look identical; `stitch proof`
showed solid black on a file that stitched almost bare. And **when the user
reports a regression, the controlled variable is what changed in this repo** —
do not reach for a mechanical explanation while your own parameters are the
thing that moved.

**Minimum feature size is the defect that keeps recurring.** A single running
stitch is ~0.4 mm against a 1.2 mm safe minimum, and artwork drawn for screen is
routinely below it — 39% of the LemonCat outline's ink area is under 1.0 mm.
Check against `design_limits.safe_satin_width_mm` *before* digitizing.

Which tool depends on how the artwork is built, and picking wrong reports
nothing rather than reporting a problem:

| Artwork | Tool |
|---|---|
| SVG with **strokes** | `svg_prep` prints the stroke-width range |
| SVG of **fills only** | `tools/svg_offset.py --report` (per colour) or `tools/svg_subpath_filter.py --report` (per subpath) |
| Raster | `tools/artwork_prep.py --report` |

`svg_prep` is blind to a fill that is too thin — it only knows declared stroke
widths. The I-heart-Screaming artwork is three fill paths and no strokes at all,
so `svg_prep` reported nothing while 14 subpaths sat at 0.40–0.80 mm.

**Then there are three ways to fix it, and they are not interchangeable:**

| The thin thing | Fix | Tool |
|---|---|---|
| detail that was never going to survive | delete it | `svg_subpath_filter --drop-thin` |
| the drawing itself | thicken the shape | `svg_offset --to-min` |
| an edge that needs to read harder | outline it in satin | `svg_stroke` |

`svg_offset` is the one that was missing, which is why the answer for both Muffy
designs was "centreline it and accept a running stitch". It offsets with
**Shapely**, the same library Ink/Stitch bundles and uses for its own
`knockdown_fill` offsets, so the geometry matches what the consumer would have
produced. `--to-min 25270A=1.2` searches for the smallest growth that brings all
but `--tolerate` percent of that colour's ink area up to 1.2 mm; `--grow` sets it
by hand. **It is a look change** — 0.6 mm to 1.2 mm is twice the line weight —
so grow the least that clears the limit and then look at the render.

**Growing merges things, and nothing downstream can see it.** Two features
0.8 mm apart become one when each grows 0.4 mm, and a 0.5 mm hole closes.
Neither is visible in a render at design size, and `validate` cannot see either,
because the stitches are perfectly good stitches of the wrong shape. `svg_offset`
counts shells and holes before and after and makes a change an **error**;
`--allow-topology-change` proceeds. Same guard as `raster._clean_mask`, and for
the same reason: a hairline join costs almost no area, so an area test misses it.

**Inkscape cannot do this, and two plausible ways of making it are traps.**
Path > Outset is GUI-only — verified, it is absent from all 1213 entries of
`inkscape --action-list`, which carries only the booleans, `object-stroke-to-path`,
`object-to-path`, `path-simplify` and friends. Of the two headless substitutes:

- the **Offset live path effect** does bake, on load/save, into `d` — but
  running `object-to-path` on it **reverts `d` to `inkscape:original-d` and drops
  the effect**, silently un-thickening the shape. Verified on a 10×2 mm bar.
- **stroke-width + `object-stroke-to-path` + `path-union`** grows by exactly
  half the stroke width and keeps the fill colour, but rewrites the whole style
  block. Usable; not worth a subprocess.

**`svg_stroke` writes a satin keyline, because a stroke *is* the satin.**
`svg_prep` splits each shape into a fill op and a stroke op and hands the stroke
to `stroke_to_satin` at the declared width. Stroking a shape in **its own
colour** costs no stop and no rethread — `svg_prep` groups ops by colour — so it
is the cheap way to firm an edge. A different colour costs a manual rethread.

Two measured facts it reports and you will otherwise get wrong:

- **Inkscape's `--query-width` is the VISUAL bbox**, so adding a stroke widens
  the drawing and `svg_prep` scales everything back down to `--artwork-mm`. A
  1.2 mm stroke on an 87 mm design arrives as **1.18 mm** — under the safe width
  it was set to. `svg_offset` prints the same drift for a grow that reaches the
  bbox.
- **`style` beats a presentation attribute in a renderer and loses in
  `svg_prep.prop`**, which reads the attribute first. A file with both stitches
  one colour and previews another, so `svg_stroke` strips the conflicting
  declaration rather than leaving two sources of truth.

**Both tools refuse a `transform` rather than ignoring it**, and walk
`polygon`/`ellipse`/`rect`/`circle` as well as `path` via
`svgpath.parse_shape`. Reading only `<path>` is the silent-partial-application
version of the vtracer registration bug: LemonCat draws its ear tufts as
`<polygon>` and its pupils as `<ellipse>`, both filled #000000, so a path-only
tool reports that layer smaller than it is and offsets part of it.

*A measurement discrepancy worth knowing about, found while building this.*
`svg_offset` samples **pixel centres** (`shapely.contains_xy`);
`svg_subpath_filter` and `svg_dark_invert` rasterise with
`PIL.ImageDraw.polygon`, whose fill is boundary-inclusive. Measured on bars of
known width at 10, 16, 24, 32 and 40 px/mm, PIL is a flat **+2 px** wider at
every resolution — **+0.2 mm at the 10 px/mm those two use**, against a
1.0–1.2 mm limit. So the width figures quoted throughout this file are that much
generous, and `--drop-thin 1.0` really drops at about 0.8 mm. Not retro-fitted,
because restating every figure belongs in the same change as the fix.

**For "how much of this is too thin", use `measure.frac_below_mm`, not a
percentile of `widths_mm`.** `thickness_map` steps radii by a whole pixel, so
every width it can report is a multiple of 2 px and a threshold can only land on
one of those. `frac_below_mm` erodes at exactly `width/2` px — two distance
transforms instead of a sweep of fifty, and it can resolve a limit that falls
between steps. It cut `svg_offset --to-min` on a real design from 62 s to 29 s.

**Width means local thickness, and it lives in `embroidery_tools.measure`.**
Do not re-derive it; three plausible methods have already failed here, each
caught by a shape whose width was known by construction:

- averaging `2 × distance-transform` over every pixel understates by half;
- an 8-neighbour local-max ridge finds almost no medial axis, because the
  distance transform climbs *along* each branch so every branch pixel loses to
  the one ahead of it. It works by accident on uniform line art, where the
  transform is flat along the stroke. **It reported 0.10 mm for a shape 3.3 mm
  across** and nearly got a stitchable fill deleted as sub-minimum;
- per-direction non-maximum suppression over-fires instead: discretisation lets
  a convex interior pass, and a 4 mm disc came back as 1.6 mm.

What works is granulometry — the diameter of the largest disc that fits inside
the shape through each pixel. Exact on bars, discs and stars alike, and
**area-weighted**, so "39% is under 1 mm" means 39% of the ink. Sampling along a
skeleton weights by axis length instead, which is proportional to area/width and
therefore over-represents the very thin features being counted: the same
LemonCat mask reads 39% by area and 82% along the axis. *An older entry here
quoted that 82% — it was the axis figure, not an area one.*

## What this is

A working repository for a **Brother SE700** embroidery machine: reference
documentation, a Python toolkit for generating and validating designs, and the
design library itself.

**There is no Brother "SE7000".** If the user says SE7000, they mean the SE700.
Don't silently substitute — but don't go looking for a machine that doesn't exist
either.

## Hard constraints — check every design against these

| | |
|---|---|
| Embroidery field | **100 × 100 mm**. Design at ≤96 mm for real clearance. |
| Max stitches | **100,000** per design |
| Formats the machine reads | `.pes` `.phc` `.dst` `.pen` — nothing else |
| Filename charset | `A-Z a-z 0-9 - _` only |
| USB | FAT32, root or top-level `BROTHER` folder |
| Colour | PES quantises to a fixed 64-entry Brother palette |

**Never hard-code these numbers.** They live in
`reference/machine-profile.json` and are read via `embroidery_tools.profile`.
Adding a constant to a script instead of reading the profile is a bug — the
whole point of the profile is that swapping machines is a one-file edit.

## Environment

- Windows. PowerShell is the shell. `python` is **not** on PATH — use the
  launcher `py`, or the repo venv at `.venv\Scripts\python.exe`.
- `.\stitch.ps1 <command>` is the entry point; it bootstraps the venv on first run.
- Dependencies: `tools/requirements.txt` (pyembroidery, Pillow, pypdf).

```powershell
$env:PYTHONPATH = "D:\Development\Embroidery\tools"
.venv\Scripts\python.exe -m embroidery_tools.cli validate designs\out\*.pes
```

## Conventions

- **Millimetres in application code, 1/10 mm at the pyembroidery boundary.**
  Convert with `profile.mm_to_units()` / `profile.units_to_mm()`; don't scatter
  `* 10` through the code.
- **PES v1 is the default output.** Set in the profile. Only deviate deliberately.
- **Validate before writing anything to USB.** `usb.stage()` already refuses
  designs with blocking errors; keep it that way.
- **A design is declared, not remembered — see `docs/13-repository-layout.md`.**
  `designs/specs/<Name>.json` states its source artwork and every setting;
  `stitch build` executes exactly that and records provenance in
  `build/manifest.json`. Never hand-run the pipeline for a design that has a
  spec: edit the spec and rebuild, or the file and its record diverge.
  **Names are spelled out: `<Design>_<variant>_on_<background>`** —
  `LemonCat_solid_on_white`, `IHeartScreaming_on_black`. No abbreviations; a
  one-letter cloth suffix means nothing to the next reader. *An earlier rule
  here demanded short names because "the on-screen list truncates", and
  `validate` enforced 8 characters. **No manual says that.** A full-text search
  of all four finds no filename length rule, and the retrieve screen picks
  patterns from a thumbnail grid — thumbnail size and background are settings
  (p.15). Only `.dst` is shown by name, and nothing here is `.dst`. The
  guideline now lives in `machine-profile.json` as `usb.filename_long_chars`.*
  **Build order is derived from the declarations, not from filenames.** A spec
  whose `prepare.input` is another spec's `prepare.output` builds after it —
  `IHeartScreaming_on_black` reads the SVG the white version prepares, so the
  vein surgery is declared once. That used to rest on alphabetical order by
  luck, and renaming inverted it: `_on_black` sorts *before* `_on_white`, which
  would have digitized the previous run's intermediate rather than failing.
  `stitch audit` fails on anything undeclared. Four states, one directory each:
  `art/originals/` inbound and never edited · `art/prepared/` generated
  derivatives · `designs/out/` **`.pes` only**, because it is the DDT staging
  folder · `build/` everything else generated · `work/` scratch nothing reads.
- **Version identity is the hash of the tool scripts, not a commit.** This
  working copy has a `.gitignore` and no repository, so `build.TOOL_SCRIPTS`
  hashes are what tie a `.pes` to the tooling that made it. Fixing a bug in
  `satin_params.py` marks every design that used it stale, automatically. Add a
  script to that list when it can change output.
- **Never round-trip a source file through PowerShell text I/O.** `Get-Content |
  Set-Content -Encoding utf8` reads UTF-8 as ANSI and re-encodes it, turning
  every em-dash into `â€"` across the file. Done to `cli.py` here; recovered
  with `txt.encode('cp1252').decode('utf-8')`, but use the editing tools.
- `designs/out/` is build output
  and is disposable. `designs/library/` is third-party work — don't modify in place.
- New reference facts about the machine go in `docs/` **and**, if they're
  machine limits, in `machine-profile.json`.

## Reference material is local

The official Brother PDFs are in `reference/manuals/`, including a text
extraction of the 104-page Operation Manual. Grep that before searching the web:

```powershell
Select-String -Path reference\manuals\SE700-Operation-Manual-EN.txt -Pattern "bobbin"
```

Key pages: specs p.96 · software update p.97 · error messages p.93 ·
troubleshooting p.89 · fabric/thread/needle table p.27 · **embroidery tension
p.72** · embroidering procedure p.70 · settings screen p.15.

**Every PDF now has a `.txt` beside it** — Operation Manual, Quick Reference,
Design Guide, and the Design Database Transfer manual. Grep all four, not just
the Operation Manual; the Design Guide went unread for a long time and turned
out to hold the most useful calibration data in the repo:

- `SE700-Embroidery-Design-Guide.txt` catalogues all **128 built-in designs**
  with size, colour count and run time. That is the ground truth for what this
  machine is *designed around*, as opposed to what it will merely accept:
  median 3 colours / 7 min / 78.7 mm, and **98% are within 96 mm**. Summarised
  in `machine-profile.json` under `embroidery.builtin_pattern_benchmark` and
  `docs/10`. Use it to sanity-check generated designs.
- Re-extract with pypdf if a manual is replaced.

## Facts that are easy to get wrong

- The **SA434 4"×6.75" hoop attaches but does not enlarge the stitchable field.**
  It's still 100 × 100 mm. Don't suggest it as a way to stitch bigger designs.
- **DST carries no colour data.** Converting PES → DST → PES loses colours
  permanently.
- **Do not oil this machine.** The manual explicitly prohibits it.
- **Scaling a stitch file ≠ resizing a design.** Stitch count is unchanged, so
  density changes inversely. Warn on anything beyond ±10%.
- Wireless is **2.4 GHz only** and cannot do WPA/WPA2 **Enterprise**.
- An oversized design usually produces **no error** — the machine just doesn't
  list it. But this is conditional: the **[Embroidery Frame Identification
  View]** setting, when ON, both filters the list to patterns that fit the
  *selected* frame and raises "Pattern extends to the outside of embroidery
  frame. Select a larger frame." So "it isn't in the list" can mean the design
  is over 100 × 100 mm **or** that the frame filter is on with a small frame
  selected. Check the setting before re-exporting the design.
- **Embroidery speed is fixed at 400 spm and cannot be lowered.** The manual:
  the speed controller "cannot be adjusted while sewing decorative stitches or
  embroidering", and the Embroidery settings screen has no speed option. Never
  offer "slow the machine down" as a remedy — it is standard advice everywhere
  else and impossible here. It also means `runtime_minutes()` is an exact rate,
  not an upper bound.
- **The machine's MAC is not registered to Brother.** Its radio is an OEM module
  (this unit: `44:F7:9F` = Cloud Network Technology / Foxconn). Identify it by
  service fingerprint instead — `Server: debut/1.20` and a TLS cert CN of the
  form `60;3;1;<version>.local`. `stitch discover --deep` does this.
- **There is no programmable network path.** Brother's transfer protocol is
  closed; the machine exposes only 443 and has no web UI (all paths 404). Don't
  propose scripting a wireless push — it isn't possible.
- **Design Database Transfer is the user's preferred transfer method, not USB.**
  DDT reads a PC folder directly, so `designs\out` *is* the staging area and a
  rebuild is picked up on the next transfer. `stitch stage` with no `--to` is
  the pre-flight gate for that route; `--to` still copies to USB.
- **A wireless transfer does NOT overwrite a design already in machine memory.**
  It lands in the volatile *wireless function pocket* (source 3 on the retrieve
  screen) and is deleted at power-off. A copy saved to machine memory on an
  earlier run persists and stays selectable, so picking it silently stitches the
  old geometry. **When a user reports "I regenerated it but the machine did the
  same thing", ask which source they retrieved from before re-examining the
  file.** Confirm the file on disk changed, then confirm which copy ran.

## Auto-digitizing (`stitch trace`, `embroidery_tools/raster.py`)

- Works on **flat, bold, few-colour art only**. Photographs produce muddy
  results — that is inherent, not a tuning problem. Don't promise otherwise.
- The `colour fit` score (mean pixel-to-centroid distance, 0–255) is the honest
  suitability signal: ≤22 good, >40 unusable.
- **One `add_thread` + one contiguous block per colour.** Calling `add_block`
  per path makes every path a colour change and PES hard-fails above 255 of
  them. Break paths with `trim()` + `JUMP`, not new blocks.
- Quantise over **opaque pixels only** — including background pixels lets them
  claim palette slots and silently drop real design colours.
- Fill is sampled along scan lines in the mask's own coordinate space. Do not
  "simplify" this by rotating the raster; that resamples away thin features.

## Design limits specific to THIS machine

Generic digitizing advice assumes a 5×7+ field, 6–15 needles, and 800–1000 spm.
All three are wrong here, so don't repeat it uncritically.

| Feature | Minimum | Safe |
|---|---|---|
| Satin / linework width | 1.0 mm | 1.2 mm |
| Filled shape | 2 mm | 3 mm |
| Text cap height (sans) | 5 mm | 6 mm |
| Colours | — | **3–4** (single needle: each change is a manual rethread) |
| Fill density | 0.4 mm rows | 0.45 on knits |

At the 96 mm working size, **1.2 mm is 1/80th of the design width** — anything
thinner than ~1% of the design will not survive. Commercial "6–8 stitches/mm"
density figures do not apply; err sparse.

At 400 spm, stitch count is wall-clock time. `analyze.runtime_minutes()` reports
it and `validate` warns past 45 minutes. Quote run time whenever discussing a
design's viability — it is usually the deciding factor, not the stitch limit.

## Colour is a label — but distinctness is functional

The machine cannot detect what thread is loaded. It stops at each change and
shows a name; the user loads any spool. So ΔE against the Brother palette is
**preview fidelity only** — never present it as a stitching defect.

What *is* functional: **PES merges adjacent blocks sharing a colour.** Verified —
three layers written as `#ed171f, #ed171f, #000000` read back as two, so the
machine stops twice, not three times, and two layers stitch as one pass.
`raster._quantise` therefore forces distinct palette entries per layer and flags
substitutions. Do not "optimise" that away.

Corollary: layer count, layer *order*, and the segmentation that decides which
pixels join which layer all matter enormously. The specific hue does not.

## Unstitched cloth is a colour — so the fabric is a design input

Every design here uses bare fabric as a colour: that is why `LemonCat_solid_on_white` is named for
white cloth and `LemonCat_outline_on_yellow` for yellow, and why `IHeartScreaming_on_white` has white eyeballs, teeth
and lettering while carrying no white thread. Move the file to black cloth and
that colour changes underneath you. Full procedure in
`docs/14-designing-for-dark-cloth.md`; the decisions that are easy to get wrong:

**Which tool depends on how the artwork is built, and two of the three wrong
answers validate clean.** Open the SVG rather than looking at the picture — white
areas that are *paths with a white fill* are overpainted; white areas that are
*subpaths of the ink path* are holes. `svg_subpath_filter --report` prints
nesting depth and settles it.

| Artwork | Dark-cloth job | Tool |
|---|---|---|
| One colour, linework | relabel the thread | `tools/svg_recolor.py` |
| Shapes painted over each other | knock upper out of lower | `tools/svg_knockout.py` |
| Ink layer with holes | recover holes as thread, drop the ink | `tools/svg_dark_invert.py` |
| **Anything else** | **compose it** | **`tools/svg_edit.py --op …`** |

**Prefer `svg_edit` for new work; the three above are fixed sequences of it.**
It applies atomic operations — `subtract · drop · recolour · offset · pockets ·
set-stroke · report` — previewing after each and logging them so `--replay`
reproduces the run byte-for-byte. `--list-ops` prints the vocabulary. A new asset
is a new *sequence in the spec*, not new Python; that is the whole point, after
one tool had to be extended twice in a session because the code that fitted one
asset was wrong for the next. LemonCat_solid_on_black's entire treatment:

```
subtract --colour FFD400 --by 000000    cut the linework out of the body
subtract --colour FFFFFF --by 000000    and out of the eyes
subtract --colour FFD400 --by FFFFFF    knock the eyes out of the body
drop     --colour 000000                let the cloth supply the linework
```

**Ink/Stitch's `collapse_len_mm` default of 3.0 mm sews travel across bare
cloth.** Any hop shorter than it becomes ordinary stitches instead of a jump, so
two shapes a couple of millimetres apart get joined by a sewn line. On
MuffyHat_on_white that put three black threads across the white hat, between
SOUR PUSS letters 1.2 mm apart. It had always done it — at the artwork's
original 0.5 mm letter spacing the travel was too short to see, and **re-spacing
the lettering is what made it visible**. Now set from
`design_limits.max_collapse_mm` (1.0 mm, matching `min_satin_width_mm`: a hop
shorter than the narrowest thread this machine holds cannot be seen).

**This inverts the jumps-are-expensive rule, deliberately.** Elsewhere here,
minimise jumps — extra stitches are unattended machine time while extra jumps
are floats you snip. But a jump float is **cut off** and collapsed travel is
**sewn down and stays**. Across bare cloth in a visible area the jump wins. Cost
across the library: a few more jumps each, 0.3–2.5 min of snipping.

*Splitting the fill into one element per component does NOT fix this,* and it is
the obvious first guess — it was built here and then removed. Measured three ways
on the same design: default 3.0 → 13 jumps / 7,520 stitches / travel visible;
split at 3.0 → 13 jumps / 7,584 / still visible; collapse 1.0 unsplit → 20 jumps
/ 7,044 / **gone**. Ink/Stitch already routes subpaths as separate sections and
collapses afterwards, so splitting only adds a lock and an underlay per letter.
**Verify a fix changes the output before keeping the machinery.**

**NEVER stitch thread the colour of the cloth.** It costs stitches, machine time
and a rethread and shows nothing. The risk is specific to inverted dark-cloth
work: the whole technique is to **drop** the ink layer and let the fabric supply
it, so a layer that failed to drop looks correct in every render and is
invisible only on fabric. `validate` gained a `thread-matches-cloth` **error**,
judged by CIELAB distance against `design_limits.min_thread_cloth_delta_e` (25)
— perceptually, not by equality, because PES quantises every thread to the
64-entry Brother palette on the way out, so a layer authored `#000000` is not
the byte the file carries. It needs the spec's `cloth`; `stitch validate` looks
the spec up by filename so `designs/out/*.pes` is checked with no extra typing.
**This is a guard, not a calibrated limit** — there is no fabric evidence for a
specific figure. The evidence that 25 is safe: the closest legitimate pair in
this library is **70.2** and every other is 78+, so it can only fire on a layer
that genuinely should have been dropped.

**A `gap` channel takes its width off EVERY side, so it deletes narrow
features.** MuffyHat's hat bracket is a 1.25 mm-wide gold shell; a 0.9 mm
channel removes 1.8 mm and erased it, and on fabric the hole it left read as an
**"L" printed on the hat**. `gap` now spares any shell the channel would take
below `min_satin_width_mm`, leaving it whole and touching its neighbour, and
says which ones. Backing the channel off to the widest that shell can afford was
tried and is worse — at 0.42 mm the bracket kept 3.35 mm² of 13.27, a mutilated
shape rather than a deleted one. **A feature too narrow to afford separation
should simply not be separated.**

*And the guard that missed it was counting.* `gap` compared shell counts before
and after; the bracket vanished while another shell split in the same pass, so
the count went 9 → 9 and nothing was reported. **Ask each shell whether IT
survived** — a net count is not a survival check. Same error as guarding
`widen-negative` on shells when the failure was holes merging.

**Not every gap in the artwork is a white AREA — some are keylines, and emitting
them as thread haloes the design.** Illustration for light paper routinely sets
ink into a hairline gap in the colour beneath it so the paper reads as an
outline. `pockets` recovered those as **white thread**, putting a halo around
both Muffy faces' eyes and mouths that ran straight into the yellow. Observed on
fabric, after everything else here was already right. `pockets --min-width`
(default `min_satin_width_mm`) drops a pocket that cannot hold a disc that wide;
erosion is exact, so there is no threshold to tune, and the two populations are
not close — real pockets measured 1.25–5.42 mm across, keylines 0.08 mm.

**The cloth is DECLARED, in `spec.cloth`, and two things derive from it.** The
preview is rendered against it, and the fill density comes from its luminance.
Before that field existed the fabric lived only in the design's *name*, so
nothing could render a design as it would actually look, and `_on_black` plus a
forgotten density is exactly the file that stitched out speckled.
`options.Cloth` still overrides, for what a colour cannot imply (`knits`).

**`stitch build` writes `designs/previews/<Name>.png` on every build**, named to
parallel `designs/out/<Name>.pes`, rendered on that design's own cloth. It is
not a gate anyone has to remember. **Human review is the only check that has
caught the defects that matter here** — the yellow LemonCat eyes, the
solid-block PissMuffy, the white keyline haloes — and every one was clean in
`validate` and unmissable on the right fabric. `audit` flags a missing or stale
preview, and a preview no spec declares. Previews stay out of `designs/out/`
because that is the DDT staging folder and holds `.pes` only.

**Three defects are visible only ON DARK CLOTH, and no check in this repo could
see any of them.** From the `MuffyHat_on_black` stitch-out
(`photos/PXL_20260812_064352867.jpg`): `validate` clean, `coverage` fine, render
and `proof` both convincing. Every gate here asks whether the stitches are
*sound*; none asked whether they were *distinguishable*. Full working in
`docs/14`.

- **The validated fill density is validated on WHITE.** 0.4 mm covers; what it
  does not do is hide the cloth between rows, which is invisible on cream and a
  black dot at every penetration on black. Use `Cloth: dark` in the spec →
  `design_limits.fill_density_mm_dark` (0.33 mm), ~21% more rows. Check
  `density_max_per_mm2` against the 16 cap afterwards; it stayed ≤13 here.
- **Two light colours drawn edge to edge stitch as one mass.** Pull
  compensation grows both independently, so a shared boundary is claimed twice:
  339 mm of MuffyHat's white perimeter sat at *zero* distance from the gold and
  the two overlapped by 136 mm² once expanded. This never bit on light cloth
  because a black keyline separated everything — and **inverting for dark cloth
  is the operation that drops that keyline.** The rule below says dropped ink
  must be subtracted from what lies *under* it; this is its other half. Dropped
  ink that lay *between* two colours must be replaced by a cut:
  `gap --colour F6BE00 --by FFFFFF --mm 0.6`. Take the channel out of the shape
  that can afford it, **not** out of the one stitched first — cutting the white
  hat consumed two shells outright, cutting the gold body cost 262 mm² of 3,455
  and changed no topology. A cut of N shows as N − 2·expand.
- **Knocked-out detail is measured on the wrong side of every limit.**
  `design_limits` sizes thread; a hole is the complement, and it is attacked
  from both rails at once. SOUR PUSS is drawn at a 1.42 mm median gap — clear of
  the 1.2 mm safe width, which is why nothing flagged it — and 0.2 mm of pull
  compensation per side takes it to 1.00 mm and closes 29% of the negative
  outright. Size knockouts against `design_limits.negative_space_mm` (1.8 mm).

**Widening a knockout usually is not available, and the guard must count HOLES,
not shells.** `widen-negative` fails by holes running into each other — a closed
letter counter — which is invisible from the shell side. The first version here
guarded on shells, watched them rise (widening lettering severs the shape it
sits in, which is harmless), and produced a SOUR PUSS with every counter shut:
**less legible than the defect it was fixing.** The render caught it; the guard
did not. It now clamps to the largest opening that keeps every hole distinct and
refuses outright when that buys nothing, which is what both Muffy designs get —
the letters are as narrow as the thread between them, so there is no material to
move.

*A second bug in the same op, caught by a test rather than by fabric.* The
"how much is still too narrow" metric measured the **union** of the holes, so
two holes growing into each other read as one wide hole and the number
**improved** — the metric rewarded exactly the failure the clamp exists to
prevent. Measure each hole separately and area-weight. It hid at design
resolution and only showed on a plate whose two slots sat 0.04 mm apart.

**Measure BOTH sides of a knockout — the thread between the holes is the side
that usually fails.** The obvious read on illegible knocked-out lettering is
that the letters are too thin. On SOUR PUSS that was the *second* problem: the
letter strokes are bare cloth at 1.33–1.42 mm against a 1.8 mm limit, and the
**white thread bridges between the letters are 0.45–0.67 mm against 1.2 mm**. A
0.5 mm sliver of fill does not form, it bleeds into its neighbours, and that is
what the photograph shows. **When both sides are under limit at once there is no
material to move** — which is precisely what `widen-negative` reports — and only
redrawing helps.

**Redrawing is `svg_edit` ops, not a new original.** `space-out`, `scale` and
`move` are declared in the spec, so `art/originals/` is still never edited and
the change rebuilds like anything else. Three things that bite:

- **Order is forced and `scale` enforces it.** Scaling first makes the letters
  collide, and the union that must follow — even-odd XORs an overlap into a
  *hole* rather than merging it — fuses eight letters into one polygon for good.
  Every later op then addresses one blob and silently does nothing: `space-out`
  reported "re-spaced 1 component(s)" and moved nothing. Space first, then scale
  into the room that makes; ask `space-out` for more than the target, because
  scaling closes the gaps again by the growth.
- **The scale ceiling is set by the enclosing shape.** 1.10× leaves the block
  1.02 mm clear of the crown edge, and that margin is *itself* a thread bridge
  under the same 1.2 mm limit. The usable interior is the pocket **less the gold
  ridge arcs crossing it**, far smaller than its bounding box.
- **Growing a block needs `move` too.** `space-out` re-centres each row where it
  was, and this block was never centred on its crown — 11.1 mm clear left
  against 22.1 mm right — so it grew off the near edge while a third of the
  crown stayed empty.

*A row is components that vertically OVERLAP, not ones that are near each
other.* SOUR and PUSS sit 0.4 mm apart, so a nearness tolerance merged all eight
letters into one row and re-spaced them into an interleaved single line.

*And `_shift_to_gap` must bracket by doubling.* A component that has to clear
one already pushed along can travel many times the target gap — the fourth
letter moved 14.5 mm to open a 2.2 mm gap. A bracket sized from the target
capped it and quietly returned 1.79 mm. No error, just the wrong answer.

**`svgdoc.Doc.upm` is frozen at load — do not re-derive it per rescan.** It used
to be recomputed from the current bounds, so a millimetre changed length every
time an op resized the drawing and every later op silently worked in a different
unit. Measured on a test document: `space-out` widened it 17.5 → 22 units, and
the 2.0 mm gaps it had just made read back as 1.59 mm. `drop` shrinks the bbox
and is in nearly every dark-cloth sequence here. `bounds` stays live on purpose —
the extent really does move, and positional selectors are relative to it.

**When widening is refused, drop `--expand` instead.** Pull compensation exists
to stop a hairline of cloth appearing where two colours meet, and after a `gap`
op there is nowhere they meet — all that is left of its effect is the 0.2 mm per
side it takes off every knockout. `"options": {"Cloth": "dark", "Expand": 0.05}`
returns the lettering from 1.00 mm to 1.25 mm, and the share of the negative that closes outright from 29% to 7%. **When both levers are exhausted
the artwork is what is wrong**: at 5 mm cap height that lettering is at
`min_text_cap_height_mm` for *positive* text, and a knockout is harder.

**On dark cloth, ask first whether the design should carry the ink colour at
all.** `LemonCat_solid_on_black` was stitching 1,341 mm² of black thread onto
black cloth. 74% of it lay over the yellow, where black-on-yellow reads fine, but
26% lay on bare cloth doing nothing — the silhouette stroke 50.8% over cloth and
both whiskers 49.7%, so they stitched at half width. Inverting it **cost a colour
rather than adding one**: 3 → 2, and 8,768 stitches → 3,994.

**Dropped ink must be SUBTRACTED from what lies under it.** Muffy's yellow and
black intersect over 0 units², so dropping alone works there; LemonCat is drawn
the normal way round and they overlap by 993 mm², so dropping alone lets the
yellow fill back in and the cat loses its face while `validate` stays clean.

**`fill` and `stroke` have OPPOSITE initial values, and getting that backwards
has caused four separate bugs here.** Absent `fill` means black; absent `stroke`
means `none`. Defaulting a stroke to black gave every unstroked element a phantom
hairline and invented 22 cloth pockets out of nothing. Reading it the other way
in the removal check left emptied elements in the document still painting black.
Check both directions whenever either is touched.

Three more, all found the moment a shared document model made state explicit
between operations — the per-asset tools hid them by parsing once and never
re-reading:

- **`d` is shared by an element's fill and its stroke.** Reshaping the fill drags
  the outline with it: cutting LemonCat's linework out of its body made the
  body's own keyline re-trace every whisker, tripling the black region, so the
  next operation cut 333 mm² out of the eyes instead of 163. Nothing errored.
  `svgdoc` splits the stroke onto a clone at its original path.
- **Stroke resolution must go through ancestors.** LemonCat declares `stroke`
  once on a wrapping `<g>`, so reading the element alone finds none — which
  silently disabled the split above.
- **Selectors must address connected COMPONENTS, not elements.** PissMuffy's 29
  letters, eyes, brows and mouth are one `<path>`, so a centroid band matched the
  middle of the whole design and selected nothing. A partial match now splits the
  element. Same class as the hand-placed circle that silently clipped the `?` out
  of `HOT PISS?` — prefer measured predicates over coordinates, and make a
  positional selector report what it matched.

**Dropping ink shrinks the drawing's bounding box, and `svg_prep` scales what is
left UP to reach `--artwork-mm`.** `LemonCat_solid_on_black` finishes at
91.4 × 58.0 mm against the white version's 91.0 × 59.8. An inverted design is not
dimensionally identical to its light-cloth sibling.

Architecture and the survey of what already exists — Graphite, vpype, Penrose,
build123d, Penpot MCP, and the MoVer result that verification lifts LLM
generation from 58.8% to 93.6% — are in `docs/15-composable-svg-architecture.md`.

**`svg_prep` orders light to dark, and the artwork paints in document order. When
those disagree the lower colour is stitched LAST and covers the upper one.**
`LemonCat_embroidery_solid_yellow.svg` draws a full-silhouette yellow body then
white eyes on top; luminance order stitches white first and the body over it, and
the eyes come out yellow. **`validate` was clean and `coverage` reported 100%** —
the yellow really does cover the artwork, and coverage asks whether pixels got
stitched, not whether they got the right colour. Only `stitch render` on the
target fabric showed it. Read the `stitch order` line `svg_prep` prints: a colour
listed before something that sits under it is the warning sign. `svg_knockout`
makes the upper shape a hole in the lower, which is `--skip`'s geometry without
`--skip`'s dropping.

*A cheap check for this would be wrong.* Comparing document order against stitch
order needs no geometry, but it fires on the **fixed** LemonCat_solid_on_black too — the white is
still later and still lighter, it simply no longer overlaps. Same rule as
everywhere: run a new check against a known-good file first. A real check has to
test whether the lower fill still covers the upper one *after* knockouts, which
means rasterising, which `svg_prep` currently has no machinery for. The honest
generalisation is to teach `coverage` to compare **colour** and not just
presence — it already maps stitches to source pixels, and it would have caught
this directly. Not built.

**On dark cloth the ink layer is usually free.** Bare fabric already is that
colour, so `svg_dark_invert` drops it: outlines, pupils, tooth gaps and mouths
still read as the fabric showing between stitched areas. `IHeartScreaming_on_black` is *cheaper*
than `IHeartScreaming_on_white` — 7,054 stitches against 10,751 — because 2,742 mm² of ink came out
and only 1,630 mm² of white went in. *(All four figures re-verified against the
build of 2026-08-11.)* What does not survive is a solid ink mass
with nothing under it; `--promote-at` rescues one by position, which is how the
"I" of "I ♥ Screaming" was kept.

**Which holes to fill has to be measured, not read off the artwork.** Three of
IHeartScreaming_on_white's 27 holes reveal the green head, the red heart and the red tongue rather
than cloth. Filling those stitches white *under* a colour that is then stitched
over it — the manual's "three or more overlapping stitches", which broke two
needles here. `svg_dark_invert` rasterises every other colour and measures each
hole's bare fraction. Its mixed-verdict warning band starts at 10%, not 5%,
because a hole cleanly over another colour still loses ~4% of its pixels to its
own rasterised perimeter, and a warning that fires on every correct design stops
being read.

**Emitting nested even-odd regions: emit only regions with no selected ancestor.**
A selected hole already carries its islands and their sub-holes as alternating
rings, so emitting a descendant again XORs it back out and that area silently
comes out unstitched. Both eye glints in `IHeartScreaming_on_black` are depth-3 subpaths inside
selected holes and hit this exactly. The test for it needs a tight tolerance: at
8 px/mm the bug lands 27 mm² from the right answer, close enough to
discretisation error to slip past.

## Previews: the machine's own is misleading

The machine's LCD preview and pyembroidery's PNG writer both **draw travel
between stitches**. On a trim-heavy fill that renders as scribble even when the
design is perfect. Use `stitch render` — it draws only real stitches on a fabric
background, which is what the finished piece will look like. `--show-jumps`
overlays travel in magenta for judging pathing.

Never diagnose a design from the machine preview or `preview.render_png`.

**PEC trim count always equals jump count.** `pec_encode` ignores TRIM commands
and flags every jump after the first as a trim-jump, so trims cannot be reduced
independently — only by reducing jumps.

## The SE700 does NOT trim jumps within a colour

Verified against the Operation Manual: step (i) of the embroidering procedure is
"**Cut the excess thread jumps within the color.**" A full-text search finds no
"Thread Trimming", "Jump Stitch Trim", or equivalent setting. Auto-cut happens
only at colour changes.

Consequences, and they invert the optimisation target:

- **Every within-colour jump is a float lying across the artwork** until the user
  snips it by hand. A jump is a labour cost, not a machine cost.
- `runtime_minutes()` charges trims **only** if
  `machine.trimming.auto_trims_jumps_within_color` is true. An earlier version
  charged ~1 s per trim unconditionally and reported 57 min for a design whose
  real machine time is 41 — hand labour miscounted as machine time.
- `cleanup_minutes()` reports the snipping time separately.
- **Minimise jump count, not stitch count.** Extra stitches are unattended
  machine time; extra jumps are floats you cut one at a time. `travel_mm`
  defaults to 40 mm on that basis (12 mm -> 968 jumps / 65 min snipping;
  40 mm -> 658 / 44 min, for +6 min machine time).
- `stitch render` shows the piece **after** snipping. Use `--show-jumps` to see
  what comes off the machine.

## Colour boundaries: later colour owns the seam

Dilating each colour independently for pull compensation makes **both** sides of
a shared boundary claim the same band, and each lays underlay + fill + outline
there. Measured: **83% of all over-dense cells — and every one of the eight
worst — sat exactly on a colour boundary.** The colour stitched last drives its
needle into a band already packed with the earlier colour's thread. That is the
manual's "three or more overlapping stitches", and it broke two needles.

`trace` now builds every colour's dilated mask up front, sorts by luminance, and
**subtracts later colours from earlier ones**, so no cell carries two colours'
worth of passes while each still pulls outward into bare fabric.

Diagnose this by classifying hot cells by zone (colour boundary / region rim /
interior), not by looking at a global histogram.

## When reliability beats fidelity

If a design breaks needles or thread, cut passes before cutting anything else.
Measured on the same artwork:

| Configuration | stitches | jumps | peak /mm² |
|---|---|---|---|
| all features on | 18,830 | 568 | 21 |
| no outline | 16,536 | 503 | 20 |
| **no outline + no underlay, cap 8, 0.45 mm** | **12,742** | **400** | **19** |

That last row is better on *every* axis — fewer stitches, fewer jumps (so less
frame snapping), lower density. Underlay and outline are quality features; when
the machine is failing they are the first things to drop.

## Density is a hard constraint, jumps are only tedious

Travel routing avoids a jump by laying thread through ground it has already
stitched. Unchecked, that peaked at **111 needle penetrations/mm^2** on a real
design — the manual's own failure mode ("stitch density that is too fine, or
three or more overlapping stitches") and a reliable way to snap thread.

`_Density` caps what travel may push a cell to (`max_density_per_mm2`, default
16). Two things about it:

- **Charge the grid incrementally**, as each run is built. Charging at the end
  of a pass leaves it empty while the travel decisions are being made, and the
  cap never bites — the first version of this did exactly that and changed peak
  density by zero.
- The trade against jump count is **sharp, not gradual**: off -> 192 jumps /
  111 peak; cap 16 -> 788 jumps / 28 peak. There is no middle ground, because
  the jump savings came from the piling.

Resolve it in density's favour. A file that breaks thread is unusable; one with
more floats just takes longer to trim.

Measure with a 1 mm-cell penetration histogram, not by eye — median stays at
3.0/mm^2 in both cases, so only the p99 and max reveal the problem.

## Optimising run time

Trims dominate on hole-heavy artwork, so jump count is the lever, not stitch
count. Measured on real artwork (67 min baseline):

Measured on one real design, jumps from 2,615 -> 201 (floor ~145):

| Change | Effect |
|---|---|
| **Travel-under-fill** (`_travel_path`, BFS round holes) | the single biggest lever |
| **BFS window sized to the travel budget, not the direct hop** | 627 -> 281 jumps. Sizing it to `direct` put any wide detour outside the search box and reported "no path" for 532 of 1,972 routes. |
| **Region fragmentation** (`_scanline_fragments`) | links scan-line segments that overlap on adjacent rows into fragments each fillable in one pass — the approach the commercial patents describe |
| Raising `travel_mm` 20 -> 60 | 619 -> 198 jumps |
| Fill each connected component separately | ~15% fewer jumps |
| Auto fill angle by **principal axis** | **no gain** — the axis says nothing about where holes are. The patents pick the angle giving **fewest fragments**; `_best_fill_angle` does that, still off by default as it did not beat 45 deg here. |
| Trim threshold (carry short hops) | **no effect on PES** — see above |

Compute the floor before optimising: components + fill fragments + underlay
fragments + outline contours. Each is a run needing one jump to reach it, and
travel routing can only merge runs inside the *same* region.

Budget detours against what a trim costs, not against the direct distance: at
400 spm a trim is ~1 s ≈ 6-7 stitches. `travel_mm` sweeps to an optimum near
12 mm; past that the extra stitches cost more than the trims saved and runtime
turns back up. The detour stitches are invisible — same colour, inside the shape.

Before optimising, **count paths at the source** (underlay / fill / outline).
Inferring jump origins from totals sent this work down two wrong paths.

## Stitch quality invariants — do not regress these

| Invariant | Why |
|---|---|
| **No stitch under `min_stitch_mm` (0.5)** | Two penetrations in nearly the same hole. The upper thread gets no length over which to take up tension, so **bobbin thread is drawn to the surface** and shows as flecks of bobbin colour; the needle also saws the upper thread against its own eye until it snaps. Serpentine fills emit one per row turn; `_filter_short` removes them (measured 3,197 -> 18). |
| **Every run has tie-in and tie-off** | The machine does not add them. Without ties, each of ~1,000 trimmed runs unravels in wear or the wash. `_add_locks`. |
| **No zero-length stitches** | `_add_locks` must not re-emit `path[0]`; `path` already starts there. That duplicate produced one per run. |
| **No run below `min_path_mm`** | A 2-stitch fragment is not worth the trim needed to reach it. |
| `pull_comp_mm` grows each colour ~0.2 mm | Offsets fabric pull-in and makes adjacent colours overlap rather than leaving bare fabric between them. |
| **Layers stitch light -> dark** | Pull compensation makes neighbours overlap, so whichever colour goes last owns the boundary. Dark covers a light edge cleanly; light over dark shows every stray stitch. Cluster index order left this to chance. |
| **Tatami stagger (`stagger_rows`, default 4)** | Rows must not put their needle penetrations in the same columns. Aligned penetrations read as ridges *and* perforate the fabric along a continuous line it can tear on. Measured at 0 deg on a rectangle: unstaggered collapses to 2 phase columns (peak/mean 4.95); staggered spreads over 4. A 45 deg fill scatters phases naturally, so test this at 0/90 deg — it hides at other angles. |
| **`_clean_mask` guards on TOPOLOGY, not area** | Its binary opening strips anything narrower than the structuring element, which shatters line art. Guard by comparing connected-region counts before and after: opening removes blobs (count falls); if the count *rises* it is breaking structures and must be discarded. An area-loss guard misses this entirely — a hairline break costs almost no pixels. Observed on outline art: 2.2% area loss while fragmenting 10 regions into 26. |

## Line art needs different handling from filled art

Outline-only sources (transparent background, one colour, thin strokes) are a
distinct case and easy to mangle:

- Diagnose by **counting connected regions at each stage**, not by coverage.
  Coverage stayed at 12.2% through a step that shattered the outline.
- Raise `pull_comp_mm` to ~0.4 to thicken strokes; at 0.2 mm/px working
  resolution anything below 0.4 mm rounds to a single pixel of dilation.
- `--no-underlay`: perpendicular underlay under a ~1 mm stroke adds density and
  supports nothing.
- One colour means one stop and no rethread — outline designs are dramatically
  cheaper.

**Do not copy a design's stitch count into this file as a record of what that
design is.** `measured` in `build/manifest.json` records stitches, jumps, run
time and peak density for every build, automatically and always current, and
`stitch info` prints them on demand. The figure that used to sit on the line
above — "1,741 stitches, 27 jumps, 4 min" for LemonCat_outline_on_yellow — had
drifted to 3,919 stitches and 14 jumps once `satin_params.py` started adding
satin underlay, and nothing could have caught it, because a hand-copied number
is checked by nothing. A design is declared, not remembered.

Where a figure is instead **carrying an argument** — the dark-cloth passage
needs "7,054 against 10,751" to make the counterintuitive point that the black
version is the cheaper one — keep it, but date it, and re-measure before citing
it rather than trusting the line.

## Prefer Ink/Stitch over `stitch trace` for new work

Inkscape 1.4.4 + Ink/Stitch 3.3.0 are installed. `docs/11-inkstitch-pipeline.md`
carries the tracer-versus-Ink/Stitch A/B across three designs; Ink/Stitch won on
every column, and hand-snipping — the thing actually being complained about —
was where it won by the most. Read the numbers there rather than from a copy.
`stitch trace` stays for one-shot conversions and as a fallback when
Ink/Stitch's fill router is too slow; everything else in this repo —
`validate`, `info`, `render`, `fix-pes`, `stage` — applies to its output too and
should still be run.

Entry points: `tools/inkstitch_pipeline.ps1 -Mode redwork|layered`, backed by
`tools/vectorize.py` (line art) and `tools/color_separate.py` (flat colour).

### Raster designs are declarable — `build.tool: "inkstitch_pipeline"`

`build.tool` accepts `svg_to_pes` (vector, always better when you have it) or
`inkstitch_pipeline` (raster). `MuffyHat_on_white` and `PissMuffy_on_white` are the raster ones.
Three things about that path:

- **Declare the background colour in `skip`, or the design stitches as a solid
  block.** `color_separate` assigns every pixel to the *nearest declared colour*
  and treats anything in neither `--layer` nor `--skip` as background — but
  "background" is a leftover category, not a detector. Cream is nearer yellow
  than black, so with only yellow and black declared the entire canvas became
  one yellow rectangle with the artwork faintly outlined on top. `--skip`
  colours take part in the assignment and are then never stitched, which is the
  whole mechanism. Caught by `render`; `validate` was clean.
- **`artwork_mm` is the width of the CANVAS, not of the drawing.** The pipeline
  scales the image, and sticker art has margin: 75.8 mm of canvas puts
  `PissMuffy_on_white` at 70.4 × 95.6 mm. Size by measuring the ink bbox and working
  backwards, then read `measured` in the manifest for the truth. This differs
  from `svg_to_pes`, where `artwork_mm` really is the artwork.
- **List options are comma-joined into one argument** (`_options` in `build.py`).
  PowerShell only splits `-Layer A,B` when it parses a command line string, and
  passing the flag twice is a hard error — "parameter specified more than once"
  — not a silent last-one-wins. `inkstitch_pipeline.ps1` splits on commas
  itself, the same way `svg_to_pes.ps1` already did for `-Skip`.

**Measure the linework before choosing `fill` vs `line` vs `auto`.** Both Muffy
designs read as bold line art and are not: the dark layer measures 0.60 mm
(`PissMuffy_on_white`) and 0.96 mm (`MuffyHat_on_white`) median local thickness, **below the
1.0 mm satin minimum**, so `:auto` centrelines 68% and 93% of it respectively.
Filling would lose it and satin cannot hold it; a centreline plus the default
2 bean repeats is the only treatment that puts real thread on a 0.6 mm line.
Use `embroidery_tools.measure.widths_mm` per colour layer — area-weighted, so
the percentage means percentage of the ink.

**Bean-stitched centrelines are the density hot spot on raster work.** Each
repeat re-penetrates the same holes, so peaks land far above the vector designs:
27/mm² on `PissMuffy_on_white` and 24 on `MuffyHat_on_white`, against 16 for the worst vector file
and a 30 danger threshold. Zero cells reached 30 in either, so both shipped —
but classify before reacting. `PissMuffy_on_white`'s hottest cells are inside the
lettering (single colour), `MuffyHat_on_white`'s are 81% on colour boundaries, which are
two different causes and two different fixes.

### "Line art" is rarely all line — default to `:auto`

`LemonCat_outline_transparent.png` looks like pure line art: one colour,
transparent background, no fills. **44% of its ink area is ≥1.5 mm across** —
eyebrows, pupils, nose and ear interiors are solid masses in the same stroke
colour as the whiskers. Pure `redwork` centrelines them, so a solid pupil
becomes a starburst and an eyebrow becomes one line, and **on fabric they read
as missing**. 34% of the artwork went unstitched and the render still looked
like a cat.

Use `-Mode layered -Layer '<hex>:auto'`, which splits by local stroke width:
solid parts filled, thin parts centrelined. On genuinely thin art the split
finds nothing to fill and the result is identical, so it is the safe default.
`vectorize.py` warns when redwork is about to eat solid areas.

**Diagnose dropped elements by overlaying the stitch path on the source mask and
measuring unstitched area** — not by looking at the render, and not by counting
connected components. Every one of the 10 source components had ≥44% coverage
while the solid masses were entirely gone; the component count showed nothing.

### Ink/Stitch is a GUI app wearing a CLI — five ways that bites

1. **`inkstitch.exe` is a GUI-subsystem binary.** Shell `>` redirection yields a
   **0-byte file**, including the exact invocation in Ink/Stitch's own CLI docs.
   Use `Start-Process -RedirectStandardOutput`.
2. **On anything irregular it opens a modal dialog and waits forever** at ~0%
   CPU. `Invoke-InkStitch` bounds the wait, scrapes the dialog text over Win32
   so the cause is visible, and fails. *Diagnostic: 12 minutes elapsed against
   1 second of CPU means blocked, not busy.*
3. **A document with `inkstitch:*` params but no version stamp triggers the
   "Unversioned Ink/Stitch SVG file detected" migration dialog.** Generated SVGs
   must carry `<inkstitch:inkstitch_svg_version>` in `<metadata>` —
   `color_separate.py` writes it. Re-check the number after an upgrade.
4. **Extensions act on a selection, passed as `--id=<id>` per object.** With
   none it prints "Please select one or more strokes" and **exits 0**. Give
   every path an id first.
5. **It exits 0 on parse failure too**, emitting the input unchanged. Both
   generator scripts re-parse their own output with ElementTree before
   returning. Never build SVG with regex — an earlier `vectorize.py` did, emitted
   `<path .../ id="p1"/>`, and cost a full debugging cycle.

### vtracer puts position in a per-path `transform`, not in `d`

Copying only the `d` attribute collapses every shape toward the origin. Nothing
downstream complains: the SVG is valid, it renders as a plausible drawing, and
Ink/Stitch stitches it happily — but the geometry is in the wrong place, and
piled-up shapes make `fill_to_stroke` centreline the overlap as one blob. The
error is invisible until it is on fabric.

`color_separate.check_registration` now compares the traced bounding box
against the mask it came from and fails on a gross mismatch. **When copying
vector output between documents, always check that geometry landed where it
belongs** — validity is not registration, and none of `validate`, `info` or the
PES container check can see this class of bug.

Params are plain `inkstitch:*` attributes in the
`http://inkstitch.org/namespace` namespace, so no GUI is needed to set them.
Authoritative names live in the bundled templates under `...\bin\icons\inx\`.
The one that matters most here is `underpath="True"` — travel routed under the
fill instead of across bare fabric.

### Ink/Stitch output bypasses every invariant `raster.py` enforces

`_filter_short`, `_add_locks` and the rest run inside the tracer. A file that
came from Ink/Stitch never touches them. The first designs built here had
**11-18% of their stitches under 0.5 mm** purely because the exporter was never
told the limit — which showed up on fabric as white bobbin thread pulled to the
surface.

Two fixes, both needed:

- Set `<inkstitch:min_stitch_len_mm>` in the document `<metadata>`.
  `color_separate.py` and `svg_merge.py` write it from the profile. **The
  merged document is the one Ink/Stitch exports from** — settings on individual
  layer files do not carry over.
- `validate` gained a `short-stitches` finding so any file, whatever produced
  it, gets checked. It counts **mid-run** shorts only: tie-in and tie-off are
  deliberately short and must stay short, and counting them flags every
  correctly locked design. On LemonCat_outline_on_yellow, 42 of 57 remaining shorts were locks.

When adding any new generator, ask which of the invariants in the table above it
silently skips.

**Stitch-level limits live in `machine-profile.json` under `design_limits`.**
`prof.min_stitch_mm()` is the accessor; `TraceSettings.min_stitch_mm` defaults
from it. It was previously a literal in `TraceSettings` only, which is why the
new tooling had nothing to read.

**Quote hex colours in PowerShell.** `-Stitch 000000` evaluates to the number
`0`; it must be `-Stitch '000000'`. `color_separate.py` rejects malformed hex
rather than guessing, because a wrong guess quietly stitches the wrong colour.

## Review notes on `raster.py`

Things a reviewer should check, all of which were real defects at some point:

- **Feed all fragments of a component through `_lines_to_paths` in ONE call.**
  Per-fragment calls cannot attempt cross-fragment joins, and fragments of a
  component are connected in the mask, so those gaps are routable.
- **`_travel_path` simplification must take the FARTHEST visible point**
  (backward scan). A forward scan that stops at the first non-visible point
  hugs the pixel path and cost 13% more stitches for no speed gain. The window
  is capped at 128 so cost stays bounded when travel budgets are large.
- **`_travel_path`'s BFS window must be sized to the travel budget**, not the
  direct hop, or wide detours fall outside the search box.
- **Report layer area before pull-compensation dilation**, or every layer reads
  ~15% larger than the artwork.
- Dead code accumulates fast here. `_scanline_runs` and `_principal_angle` both
  outlived their replacements and were only kept alive by a test.

## Tests

`tools/tests/test_toolkit.py` — 253 invariant checks, no framework needed:

```powershell
.venv\Scripts\python.exe tools\tests\test_toolkit.py
```

Run it after touching `raster.py` or `convert.py`. Every check maps to a bug
that shipped here. Add a check whenever you fix a new one.

When changing fill or path code, re-measure the stitch-length histogram and the
lock count. Both regressions above were invisible in the render and only showed
up in the histogram.

## PES origin must start at (0,0), not be centred

**Confirmed against Design Database Transfer, 2026-08-07.** pyembroidery centres
a pattern on the origin, so stitches run `-w/2..+w/2`. DDT reads PEC coordinates
as running `0..width`, so a centred design is drawn with its left and top halves
off-canvas and **only the bottom-right quadrant is visible**. The identical
design shifted to start at (0,0) renders correctly; DST is unaffected, which is
why DST always looked right and PES did not.

Always write PES via `convert.write_pes()`, which copies the pattern, translates
it so `bounds()` starts at (0,0), then writes and finalizes. Never call
`pe.write(..., ".pes")` directly. `validate` flags `pes-origin-centred`;
`stitch fix-pes` repairs existing files.

This was not diagnosable from the file alone — an independent PEC decoder written
from the spec confirmed the block was internally consistent and correct (header
dimensions matched the stitch extent exactly). It is a convention mismatch, not
corruption.

## pyembroidery declares the wrong hoop in PES headers

**pyembroidery hard-codes the PES hoop field to 1 = 130x180 mm**, regardless of
the design or the target machine (`PesWriter.write_pes_header_v1` line ~157,
`write_pes_header_v6` line ~162). Brother's own Design Database Transfer reads
that field to lay out its preview, so a 4x4 design shows up small and off-centre
inside a 130x180 frame and looks cropped to a corner. **The stitches are fine** —
the machine works from the PEC block — but the preview is wrong and alarming.

`convert.patch_pes_hoop()` corrects it after every PES write (offset 14 for
`#PES0001`, offset 12 for `#PES0060`); `validate` flags a mismatch; `stitch
fix-pes` repairs existing files. Never remove the post-write patch — upgrading
pyembroidery will not fix this upstream.

## Fill connectors must stay inside the shape

`raster._lines_to_paths` may only join two scan-line segments with stitches if
the straight connector **stays inside the mask** (`_connector_inside`), or if the
hop is shorter than `bridge_mm` (0.8 mm — invisible, saves a trim). Checking
distance alone is wrong and was a real bug: fills sewed straight across letter
counters, turning crisp lettering into a solid slab. The mask was perfect, so it
was invisible in every diagnostic except the rendered stitches.

Corollary for debugging: **pyembroidery's PNG writer draws jump stitches.** On a
design with thousands of jumps that buries the artwork and makes a correct file
look broken. Render only `STITCH` runs when verifying visually.

Trims are not free: `runtime_minutes()` charges ~1 s each, and on a hole-heavy
fill they can exceed the sewing time (observed: 44 min trimming vs 28 sewing).

## The embroidery-render trap

An AI image that *looks* like embroidery (simulated satin texture, thread sheen)
is **harder** to digitize than flat sticker art — the fake texture fragments
colour clustering. Observed: 109,080 unique colours, 308,519 sub-1 mm² regions,
0.77 mm linework. `stitch flatten` recovers it (5 colours, 34 regions, 1.23 mm).

`flatten --colors` **includes the background** — ask for one more than the design
has, or small elements get merged away silently.

**Flatten can merge a pale design element into a pale background, and then no
downstream setting can recover it.** Observed: a white hard-hat on cream
(`MuffyHat_on_white`) merged into a single 65%-coverage colour, so the connectivity-aware
background strip ate the hat and left floating text. Raising `--colors` to 7 did
not separate them, and `--bg-tolerance` down to 4 did not either — once k-means
merges two colours they are literally the same pixel value.

Check for it by running `recolor --list` on the flattened file — if the
background colour holds a suspiciously large share, a design element has been
absorbed. Reproduced when `MuffyHat_on_white` was finally built: 65.1% at `--colors 5`,
still 63.2% at 7.

Two fixes, and the cheap one is usually right. **Skip flatten and trace the
original** if the element must carry thread — on the unflattened image the hat
measured 91% opaque after stripping versus 24% flattened. But first ask whether
it needs thread at all: **`MuffyHat_on_white` shipped by leaving the hat unstitched**, as
white cloth, which is the same trick `IHeartScreaming_on_white` uses for teeth and `LemonCat_solid_on_white` for
eyes. The hat is drawn completely by its outline and its lettering, cream is
declared as the skip colour, the hat and its grey shading fall to cream as their
nearest declared colour, and the merge that could not be undone stopped
mattering. Coverage reports 96% and the missing 4% is hat shading, by intent.
**A pale element on pale cloth may not be a separation problem at all.**

Never label a colour count from `flatten` as the thread count; subtract the
background.

## When adding tooling

Follow the existing shape: a module in `embroidery_tools/` with a thin
subcommand in `cli.py`. Return non-zero from a command when validation finds a
blocking error — these commands are meant to be usable in a chain.

**Ask what invariants a new generator silently skips.** `raster.py` enforces
minimum stitch length, locks, minimum path length and a density cap *inside the
tracer*. Ink/Stitch output touches none of that code, and 11–18% sub-0.5 mm
stitches shipped as a result. Anything that produces stitches from outside
`raster.py` needs its own equivalent, plus a check in `validate` so the finished
file is verified regardless of origin.

**Prefer a check in `validate` over a paragraph in a doc.** Prose gets skipped;
`validate` runs every time. Peak density spent this whole session as an ad-hoc
scratch script before becoming the `density-peak` finding, and `coverage` was a
throwaway overlay script before becoming a command — both caught real defects
while they were still scripts, and would have been lost otherwise.

**Machine limits go in `machine-profile.json`, never in a literal.**
`min_stitch_mm` and `max_density_per_mm2` lived only as `TraceSettings`
defaults, which is exactly why new tooling had nothing to read and silently
disagreed. Accessors: `prof.min_stitch_mm()`, `prof.design_limit(name)`.
