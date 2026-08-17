# Repository layout

Every file in this repo is in exactly one of four states, and the directory it
sits in declares which:

| State | Where | Rule |
|---|---|---|
| **Inbound** | `art/originals/` | Artwork exactly as received. Never edited, never generated. |
| **Declared** | `designs/specs/` | One JSON per design: its source and settings. The source of truth. |
| **Generated** | `art/prepared/`, `designs/out/`, `designs/previews/`, `build/` | Produced by tooling from the two above. Reproducible. |
| **Disposable** | `work/` | Scratch. Nothing here is ever read by tooling. Gitignored. |

Plus `photos/` for stitch-out photographs — evidence of what happened on the
machine, not artwork and not generated.

> **In the public repository, the asset directories are gitignored** — `art/`,
> `photos/`, `designs/out/`, `designs/previews/`, `designs/library/`, `designs/specs/*.json` and
> `build/`. This repo publishes the toolkit, not a personal design library:
> artwork carries its own rights and stitch files are build artifacts. The
> scheme below still describes them because the tooling expects them; they are
> simply yours locally. A fresh clone reports zero designs from `stitch audit`,
> which is correct rather than broken.

`.\stitch.ps1 audit` enforces this. If a file cannot be placed in one of those
states, it is sprawl and the audit says so.

---

## Why it looks like this

Both halves came out of real damage.

**Sprawl.** Artwork accumulated in a single `images/` tree with no rule about
what belonged there. Originals sat beside generated derivatives; a `lemon-cat`
folder moved under `Finals` partway through a session and silently broke every
path that referred to it; 19 throwaway review renders were filed next to the
source SVGs. With 40 files and no rule, nothing could tell you which still
mattered.

**No provenance.** A `.pes` recorded nothing about where it came from. Which
artwork, at what size, with which settings, built by which version of the tools?
The answer lived in a chat log or in a project note written from memory — and
when a design is rebuilt six times in an afternoon, notes drift from files.
`Scream4.pes` and `Scream6.pes` differed only in a tack style, and the only way
to tell them apart was to hash them.

So: **a design is declared, not remembered.**

---

## `art/originals/` — inbound

Artwork as it arrived. Treat as read-only. If you need it changed, that change
belongs in a spec's `prepare` step so it is reproducible, not made by hand.

A PNG that shipped alongside an SVG as its preview counts as inbound and lives
here too.

## `art/prepared/` — generated derivatives

Output of a spec's `prepare` step: sub-minimum detail dropped, artwork
thickened, colours flattened. **Everything here should be reproducible by
`stitch build`**, and the audit warns about anything that is not — that is how
an orphaned derivative gets noticed instead of accumulating.

## `designs/specs/` — the declarations

One `<Name>.json` per design; the filename must match the `name` field.

```json
{
  "name": "IHeartScreaming_on_white",
  "cloth": "F2F0EB",
  "cloth_note": "off-white cotton",
  "description": "what this design is, and anything a future reader needs",
  "prepare": {
    "tool": "svg_subpath_filter",
    "input": "art/originals/....svg",
    "output": "art/prepared/IHeartScreaming_on_white.svg",
    "args": ["--artwork-mm", "87", "--drop-thin", "EE2028=1.0"],
    "why": "why these arguments, and which are constraints vs choices"
  },
  "build": {
    "tool": "svg_to_pes",
    "input": "art/prepared/IHeartScreaming_on_white.svg",
    "artwork_mm": 87,
    "skip": [],
    "options": {},
    "why": "why this size, and anything deliberately left at its default"
  }
}
```

`prepare` is optional — a design whose artwork already clears the machine
minimums builds straight from its original.

**`cloth` is required**, and it is a design input rather than a note. Every
design here uses bare fabric as a colour, so the same stitch file on different
cloth is a different picture. Two things read it: the preview is rendered
against it, and the fill density is derived from its luminance — dark cloth
takes `design_limits.fill_density_mm_dark`, because the gap between rows is
invisible on cream and a dark dot at every needle penetration on black. Stating
the density separately in `options.Cloth` is only for what a colour cannot imply,
such as `knits`.

**`hoop` is optional and defaults to the included 4×4.** Declare it — `"hoop":
"SA431"` — for anything stitched in a smaller frame, and `validate` checks the
design against that frame's stitchable areas instead of the full field. Like
`cloth`, it is a fact the file cannot carry: a `.pes` records no frame, and
unlike most machines the SE700 does not detect one either. Without the
declaration a design too big for its frame passes every check here and then
drives the presser foot into the frame. See `16-narrow-material.md`.

`build.tool` is one of two:

| | |
|---|---|
| `svg_to_pes` | vector source. Always better when you have one. `artwork_mm` is the width of the **drawing**. |
| `inkstitch_pipeline` | raster source. Needs `options.Layer`, bottom layer first. `artwork_mm` is the width of the **canvas**, not the drawing — the ink has margin around it, so read the stitched size from the manifest. |

A raster spec must also list the background colour in `skip`. `color_separate`
assigns every pixel to the nearest declared colour, and treats whatever is in
neither `layer` nor `skip` as background — so an undeclared cream background is
simply assigned to the nearest thread and the whole canvas stitches solid.

**Write the `why` fields.** They are the difference between a spec you can
change safely and a spec nobody dares touch. Record which numbers are machine
constraints and which are taste: on `IHeartScreaming_on_white`, `--drop-thin` is a constraint
(veins measured 0.40–0.80 mm against a 1.0 mm minimum) while `--drop-at` is a
look choice (the forehead star measured 3.40 mm and would have stitched fine).

## `designs/out/` — machine-ready

`.pes` only, one per spec, flat. **This is the Design Database Transfer staging
folder** — DDT reads a PC folder directly, which is why nothing else may live
here. Proofs and ad-hoc renders go to `build/`; the per-design preview goes to
`designs/previews/`, below.

## `designs/previews/` — what each design will look like, on its own cloth

One PNG per spec, named to parallel `designs/out/` exactly:

```
designs/out/MuffyHat_on_black.pes
designs/previews/MuffyHat_on_black.png
```

**Written by `stitch build`, on every build.** Not a gate you have to remember
to run — human review is the only check that has ever caught the defects that
matter here, and every one of them was clean in `validate` and obvious the
moment it was drawn on the right fabric:

- `LemonCat_solid_on_white`'s eyes stitched yellow, because a lighter colour was
  ordered under a darker one that then covered it. `coverage` reported 100%.
- `PissMuffy_on_white` stitched as a solid block, because an undeclared
  background colour fell to its nearest declared neighbour.
- Both Muffy faces came off the machine with **white keyline haloes** around the
  eyes and mouth, where the artwork's hairline paper gaps were recovered as
  thread. Nothing measured it; it is unmissable in a preview.

`stitch audit` treats a missing or stale preview the same way it treats a proof
— a preview older than its `.pes` is a picture of the previous build, which is
worse than no picture. A preview with no spec is flagged too, since a leftover
from a renamed design gets reviewed as if it were current.

The fabric colour comes from the spec's **`cloth`** field, which is also what
selects the fill density — see `12-design-generation-playbook.md`. Before that
field existed the fabric was recorded nowhere but the design's *name*, so
nothing could render a design as it would actually look.

## `build/` — everything else generated

`build/manifest.json` is the provenance record. `build/proofs/`,
`build/reviews/` hold generated imagery. `build/ops/` holds the operation logs
`svg_edit` writes — one `<design>.ops.jsonl` per prepare step, replayable with
`svg_edit --replay`. Deleting `build/` entirely is safe; `stitch build` recreates
the manifest and the gates recreate the rest.

The op logs are **records, not sources**. The spec's `prepare.args` is the
declaration and the log is what actually ran; they agree because the log is
written from the run. Keeping the log out of `art/prepared/` is deliberate —
that directory holds exactly one generated derivative per spec, and `stitch
audit` calls anything else there sprawl.

## `work/` — scratch

Anything you or an agent makes while exploring. No tool reads from it, nothing
depends on it, and it can be emptied at any time.

---

## Commands

```powershell
.\stitch.ps1 build --check      # what would rebuild, and why
.\stitch.ps1 build              # build everything stale
.\stitch.ps1 build IHeartScreaming_on_white       # build one
.\stitch.ps1 build --all        # rebuild regardless
.\stitch.ps1 audit              # layout + provenance check
```

`build` is incremental against recorded fact, not timestamps. A design rebuilds
when its spec changes, an input changes, the output changed on disk since it was
built, or **the toolchain changed** — the SHA-256 of any script that shapes the
output.

`audit` also warns when a proof is missing or older than the design it shows. A
stale proof is worse than none: it is the gate that shows what will actually
land on fabric, and an out-of-date one shows the previous build while looking
current. `build` does not regenerate proofs itself, because rendering is slow
and can fail independently of the build succeeding.

That last one matters here: this working copy has a `.gitignore` but no
repository, so there is no commit to name a version by. Hashing the scripts is
what makes "which version made this file" answerable by comparison rather than
by trust. Fixing a bug in `satin_params.py` marks every design that used it as
stale, automatically.

## What the manifest records

Per design: the spec and its hash, every input and its hash, the output and its
hash and size, the full toolchain (Python, pyembroidery, Ink/Stitch, Inkscape,
and the hash of each participating script), and the measured result — size,
stitch count, colours, jumps, run time, and which `validate` findings fired.

So "which version and settings made this `.pes`" is answered by the file itself,
not by memory.
