# Design specs

One `<Name>.json` per design, declaring its source artwork and every setting
used to build it. Format and rules: `../../docs/13-repository-layout.md`.

**This directory is empty in the public repository by design.** Specs point at
files under `art/`, which is personal artwork and is not published — so the
`*.json` here are gitignored and yours stay local. `stitch audit` on a fresh
clone reports zero designs, which is correct rather than broken.

To start your own, drop artwork in `art/originals/` and write a spec:

```json
{
  "name": "MyDesign",
  "description": "what it is, and anything a future reader needs",
  "build": {
    "tool": "svg_to_pes",
    "input": "art/originals/my-artwork.svg",
    "artwork_mm": 87,
    "skip": [],
    "options": {},
    "why": "why this size, and anything deliberately left at its default"
  }
}
```

Then:

```powershell
.\stitch.ps1 build MyDesign
.\stitch.ps1 audit
```

For artwork that only ever was pixels, `build.tool` is `inkstitch_pipeline`
instead, and `artwork_mm` sizes the whole canvas rather than the drawing:

```json
  "build": {
    "tool": "inkstitch_pipeline",
    "input": "art/originals/my-artwork.webp",
    "artwork_mm": 75.8,
    "skip": ["FAECCE"],
    "options": { "Mode": "layered", "Layer": ["E6B10C:fill", "25270A:auto"] },
    "why": "which colours are thread, which is background, and why each layer's mode"
  }
```

**Always list the background colour in `skip`.** Every pixel is assigned to the
nearest declared colour, so an undeclared background is handed to the nearest
thread and the entire canvas stitches as a solid block.

Add an optional `prepare` step when the artwork needs deterministic surgery
first — dropping detail below the machine's minimum feature size, thickening
strokes, flattening colours. Record in `why` which numbers are machine
constraints and which are taste; that distinction is what makes a spec safe to
change later.

## `prepare` — surgery on the artwork

`prepare.tool` names a script in `tools/`, which is run as
`<tool>.py <input> <output> <args…>`. Its `output` is what `build.input` should
then point at.

**Prefer `svg_edit` for new work.** It applies atomic operations —
`subtract · drop · recolour · offset · pockets · set-stroke · report`, listed by
`svg_edit.py --list-ops` — so the artwork-specific part lives here in the spec
rather than in a script written for one design. This is the whole of
`LemonCat_solid_on_black`:

```json
  "prepare": {
    "tool": "svg_edit",
    "input": "art/originals/LemonCat_embroidery_solid_yellow.svg",
    "output": "art/prepared/LemonCat_solid_on_black.svg",
    "args": [
      "--artwork-mm", "91",
      "--op", "subtract --colour FFD400 --by 000000",
      "--op", "subtract --colour FFFFFF --by 000000",
      "--op", "subtract --colour FFD400 --by FFFFFF",
      "--op", "drop --colour 000000"
    ],
    "why": "why this sequence, in this order, and what each step is for"
  }
```

Three things to get right:

- **`--artwork-mm` here must match `build.artwork_mm`.** Every millimetre an
  operation takes — a `--band`, a `--lid-above`, an `offset --mm` — is measured
  against it, so a mismatch silently shifts every selector.
- **Order is part of the design, so say so in `why`.** The eye knockout above
  only works because it runs *after* the ink has been cut out of the eyes.
- **Operations that author geometry announce themselves.** `--lid-above` seals an
  open outline with a convex hull, which puts a curve in the file that was never
  in the artwork. The tool prints `AUTHORED, not in the source` and the spec
  should say why it was necessary.

Each run writes `build/ops/<Name>.ops.jsonl` recording what actually executed;
`svg_edit --replay <log>` reproduces it byte-for-byte. The spec is the
declaration, the log is the receipt.

The older single-purpose tools — `svg_recolor`, `svg_knockout`, `svg_dark_invert`,
`svg_subpath_filter`, `svg_offset`, `svg_stroke` — are still there and still
valid. Each is a fixed sequence of the same operations, kept because some carry
extra measurement `svg_edit` does not: `svg_offset --to-min` searches for the
smallest growth clearing a width limit, and `svg_subpath_filter --report`
measures per-subpath width and nesting depth.
