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

Add an optional `prepare` step when the artwork needs deterministic surgery
first — dropping detail below the machine's minimum feature size, thickening
strokes, flattening colours. Record in `why` which numbers are machine
constraints and which are taste; that distinction is what makes a spec safe to
change later.
