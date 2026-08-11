# Repository layout

Every file in this repo is in exactly one of four states, and the directory it
sits in declares which:

| State | Where | Rule |
|---|---|---|
| **Inbound** | `art/originals/` | Artwork exactly as received. Never edited, never generated. |
| **Declared** | `designs/specs/` | One JSON per design: its source and settings. The source of truth. |
| **Generated** | `art/prepared/`, `designs/out/`, `build/` | Produced by tooling from the two above. Reproducible. |
| **Disposable** | `work/` | Scratch. Nothing here is ever read by tooling. Gitignored. |

Plus `photos/` for stitch-out photographs — evidence of what happened on the
machine, not artwork and not generated.

> **In the public repository, the asset directories are gitignored** — `art/`,
> `photos/`, `designs/out/`, `designs/library/`, `designs/specs/*.json` and
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
  "name": "Scream",
  "description": "what this design is, and anything a future reader needs",
  "prepare": {
    "tool": "svg_subpath_filter",
    "input": "art/originals/....svg",
    "output": "art/prepared/Scream.svg",
    "args": ["--artwork-mm", "87", "--drop-thin", "EE2028=1.0"],
    "why": "why these arguments, and which are constraints vs choices"
  },
  "build": {
    "tool": "svg_to_pes",
    "input": "art/prepared/Scream.svg",
    "artwork_mm": 87,
    "skip": [],
    "options": {},
    "why": "why this size, and anything deliberately left at its default"
  }
}
```

`prepare` is optional — a design whose artwork already clears the machine
minimums builds straight from its original.

**Write the `why` fields.** They are the difference between a spec you can
change safely and a spec nobody dares touch. Record which numbers are machine
constraints and which are taste: on `Scream`, `--drop-thin` is a constraint
(veins measured 0.40–0.80 mm against a 1.0 mm minimum) while `--drop-at` is a
look choice (the forehead star measured 3.40 mm and would have stitched fine).

## `designs/out/` — machine-ready

`.pes` only, one per spec, flat. **This is the Design Database Transfer staging
folder** — DDT reads a PC folder directly, which is why nothing else may live
here. Proofs, renders and previews go to `build/`.

## `build/` — everything else generated

`build/manifest.json` is the provenance record. `build/proofs/`,
`build/reviews/` hold generated imagery. Deleting `build/` entirely is safe;
`stitch build` recreates the manifest and the gates recreate the rest.

## `work/` — scratch

Anything you or an agent makes while exploring. No tool reads from it, nothing
depends on it, and it can be emptied at any time.

---

## Commands

```powershell
.\stitch.ps1 build --check      # what would rebuild, and why
.\stitch.ps1 build              # build everything stale
.\stitch.ps1 build Scream       # build one
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
