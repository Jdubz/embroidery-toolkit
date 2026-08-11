# File Formats

## What the machine reads

`.pes` · `.phc` · `.dst` · `.pen`

Anything else — `.jef`, `.exp`, `.vp3`, `.hus`, `.xxx`, `.art` — must be
converted first. `stitch convert` does this.

| Format | Origin | Colours | Thumbnail on machine | Use it when |
|---|---|---|---|---|
| **`.pes`** | Brother | Yes | Yes | **Default. Always prefer this.** |
| `.phc` | Brother | Yes | Yes | What the machine writes when *it* saves to USB |
| `.dst` | Tajima | **No** | **No** — filename only | Only when a design is unavailable as PES |
| `.pen` | Brother | Yes | Yes | Artspira line-art; you won't author these by hand |

The machine also reads `.pmv` / `.pmx` / `.pmu` — those are **sewing stitch
patterns**, not embroidery designs. Different menu, different memory pool.

## Why DST is a downgrade

DST stores stitch coordinates and nothing else. There is no colour information
in the file at all. Load a DST and the machine:

- shows it in the list by **filename only**, with no preview image, and
- applies **its own default colour sequence**, which will not be your sequence.

You can fix the colours on the machine screen before stitching, but you're doing
it blind and re-doing it every time you load the design. Convert to PES once,
store the PES.

## PES versions

A PES file is really two things stacked: a **PES section** (editable objects,
version-specific) wrapping a **PEC block** (raw stitches, colours, thumbnail).
The PEC block is what the machine actually stitches, and it has stayed
compatible across the whole product line. That is why old PES files still work.

Version is identified by the first 8 bytes:

```
#PES0001   v1     ← this repo's default
#PES0020   v2
#PES0030   v3
#PES0040   v4
#PES0050   v5
#PES0055   v5.5
#PES0060   v6
```

**This repo writes v1 by default.** Rationale: v1 is the most conservative
structure that every Brother machine accepts, and none of the higher-version
features (embedded vector objects for re-editing) survive the trip to the
machine anyway. Higher versions produce larger files with no stitching benefit.

Change it in `reference/machine-profile.json` → `pes.recommended_version`, or
per-invocation with `stitch convert --pes-version 6`.

Check what you actually wrote:

```powershell
.\stitch.ps1 info designs\out\frame.pes    # prints the version
```

## Colour is quantised to 64 values

PES stores colours as **indices into Brother's fixed 64-colour PEC palette** —
not as RGB. Whatever hex you author in gets snapped to the nearest palette entry
on write. This is not a bug and you cannot avoid it.

Concretely, from this repo's own example generator:

| Authored | Stored as | ΔE |
|---|---|---|
| `#1F3A93` | `#0B3D91` Ultramarine (21) | 4.7 — imperceptible |
| `#C0392B` | `#D15400` Clay Brown (36) | 24.3 — **visibly wrong** |

So pick from the palette deliberately rather than discovering the substitution
after the fact:

```powershell
.\stitch.ps1 palette --match "#C0392B" -n 5   # what will this become?
.\stitch.ps1 palette                          # list all 64
```

### But colour is a label, not an instruction

Worth being clear, because it changes how much you should care: **the machine
cannot know what thread you loaded.** It stops at each colour change and shows a
name; you load whatever spool you like. The manual's wording gives it away —
"*prepare embroidery thread colors as shown on the screen*" is an instruction to
you, not a machine capability. You can even recolour the on-screen preview at the
machine.

So the stored colour is three things: an on-screen preview, a label telling you
which spool to pick up, and — critically — **the thing that separates layers**.

### Distinctness *is* functional

**PES merges adjacent blocks that share a colour.** Verified:

```
written:   #ed171f, #ed171f, #000000   (2 colour changes)
read back: #ed171f, #000000            (1 colour change)
-> machine stops: 2, not 3
```

Two layers assigned the same palette entry collapse into one. The machine never
stops between them, and they stitch in a single pass with a single thread — the
layering silently breaks.

That is why `stitch trace` forces every layer onto a **distinct** palette entry,
substituting the next-nearest thread when two clusters would collide, and marks
it in the output:

```
4. #66BA49 Leaf Green  ...  dE 20.08  <- palette substitute, keeps layers separate
```

**Practical upshot:** ignore ΔE for stitching purposes — it only affects how
faithful the preview looks. Do *not* hand-edit a design so two layers share a
colour unless you genuinely want them stitched together in one pass. If anything,
pick palette entries that look **clearly different from each other** on the
machine's screen, so you can tell layers apart at a glance.

The full palette with RGB values is in
[`reference/charts/brother-pec-thread-palette.csv`](../reference/charts/brother-pec-thread-palette.csv).
Brother's own thread-code list (61 codes across the 12/22/40-colour spool sets)
is at `reference/charts/Brother-Embroidery-Thread-Color-List-Artspira.pdf`.

Note that the palette *index* and the *spool code* printed on Brother thread are
different numbering systems. The CSV's `pec_index` is what goes in the file.

## PES coordinates must start at (0,0)

The single most confusing failure this repo hit, and worth knowing before you
trust any converter's PES output.

pyembroidery centres a design on the origin — stitches run from `-w/2` to `+w/2`.
Brother's Design Database Transfer reads PEC coordinates as running `0..width`.
The result: the left and top halves are drawn off-canvas and **only the
bottom-right quadrant appears**. The design looks cropped to a corner.

The file is not corrupt. An independent PEC decoder written from the format spec
confirms the block is internally consistent — header dimensions match the stitch
extent exactly, the END marker is present, colour changes are correct. It is a
**convention mismatch**, and the stitches are perfect.

Two tells that identify it quickly:

- **The same design exported as DST looks right.** DST carries no such origin
  convention, so it renders correctly while the PES does not. If DST is fine and
  PES is cropped, this is your bug.
- `stitch validate` reports `pes-origin-centred` and prints the actual start
  coordinate.

This repo writes every PES through a path that translates the design to start at
(0,0). To repair files made elsewhere:

```powershell
.\stitch.ps1 fix-pes designs\out\*.pes
```

## The PES header declares a hoop size — and most tools get it wrong

A PES header carries a hoop code: `0` = 100×100 mm, `1` = 130×180 mm. Design
Database Transfer and other PC software read it to lay out their preview.

**pyembroidery hard-codes it to `1`** regardless of the design or machine. The
symptom is alarming and misleading: a correct 4×4 design opens in Design Database
Transfer sitting small and off to one side of a 130×180 frame, looking like only
a corner of the artwork got digitized.

The stitches are unaffected — the machine works from the PEC block, which is
correct. Only the preview is wrong.

This repo patches the field after every PES write. `validate` flags a mismatch,
and existing files can be repaired in place:

```powershell
.\stitch.ps1 fix-pes designs\out\*.pes
```

Check it directly:

```powershell
.\stitch.ps1 validate designs\out\logo.pes   # warns on pes-hoop-mismatch
```

If a design ever previews cropped or oddly positioned in Brother's software but
`stitch info` reports sane extents, this is the first thing to check.

## Naming files

Brother recommends restricting file and folder names to:

```
A-Z  a-z  0-9  -  _
```

Spaces, accents, emoji, and `#` will variously fail to display, display wrong, or
hide the file. Long names get truncated in the on-screen list, so short and
distinctive beats descriptive: `rose4x4.pes` scans better than
`rose_design_final_v3_FIXED.pes`.

`stitch validate` flags both problems.

## Round-tripping

Converting PES → DST → PES loses all colour information permanently. There is no
recovering it; DST never had it. Keep the PES as the master, and keep the
*vector source* (SVG) as the real master — see `designs/source/`.
