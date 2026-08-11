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

*Correction, kept deliberately — this one cost a session.* LemonY came off the
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
| SVG of **fills only** | `tools/svg_subpath_filter.py --report` |
| Raster | `tools/artwork_prep.py --report` |

`svg_prep` is blind to a fill that is too thin — it only knows declared stroke
widths. The I-heart-Screaming artwork is three fill paths and no strokes at all,
so `svg_prep` reported nothing while 14 subpaths sat at 0.40–0.80 mm.

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
  cheaper (LemonY, via Ink/Stitch: 1,741 stitches, 27 jumps, 4 min).

## Prefer Ink/Stitch over `stitch trace` for new work

Inkscape 1.4.4 + Ink/Stitch 3.3.0 are installed. See
`docs/11-inkstitch-pipeline.md`. On the same LemonCat outline, Ink/Stitch cut
jumps from 178 to 27 and stitches from 4,504 to 1,741 — 12 minutes of hand
snipping down to 2.
`stitch trace` stays for one-shot conversions and as a fallback when
Ink/Stitch's fill router is too slow; everything else in this repo —
`validate`, `info`, `render`, `fix-pes`, `stage` — applies to its output too and
should still be run.

Entry points: `tools/inkstitch_pipeline.ps1 -Mode redwork|layered`, backed by
`tools/vectorize.py` (line art) and `tools/color_separate.py` (flat colour).

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
  correctly locked design. On LemonY, 42 of 57 remaining shorts were locks.

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

`tools/tests/test_toolkit.py` — 55 invariant checks, no framework needed:

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
(`MuffyHat`) merged into a single 65%-coverage colour, so the connectivity-aware
background strip ate the hat and left floating text. Raising `--colors` to 7 did
not separate them, and `--bg-tolerance` down to 4 did not either — once k-means
merges two colours they are literally the same pixel value.

The fix is to **skip flatten and trace the original**: on the unflattened image
the hat measured 91% opaque after stripping versus 24% flattened. Check for this
by running `recolor --list` on the flattened file — if the background colour
holds a suspiciously large share, a design element has been absorbed.

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
