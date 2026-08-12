# Designs

Full rules in `docs/13-repository-layout.md`. The short version:

## `specs/` — the declarations

One `<Name>.json` per design, stating its source artwork and every setting used
to build it. **This is the source of truth.** A `.pes` is a build artifact and a
spec can regenerate it at any time.

```powershell
.\stitch.ps1 build --check      # what would rebuild, and why
.\stitch.ps1 build              # build everything stale
.\stitch.ps1 build LemonCat_outline_on_yellow       # build one
.\stitch.ps1 audit              # layout + provenance check
```

A design rebuilds when its spec changes, an input changes, the output changed on
disk since it was built, or the toolchain changed — the tool scripts are hashed
into every build record, so fixing a bug in `satin_params.py` marks every design
that used it as stale.

Provenance lands in `build/manifest.json`: source and output hashes, the full
toolchain, the resolved settings, and the measured result. "Which version and
settings made this file" is answered by the record, not by memory.

## `out/` — machine-ready

Generated `.pes` files, **one per spec, and nothing else**. This is the Design
Database Transfer staging folder — DDT reads a PC folder directly, so anything
else in here is clutter in the transfer list. Proofs and renders go to `build/`.

Before anything leaves for a USB stick or a transfer:

```powershell
.\stitch.ps1 validate designs\out\*.pes
.\stitch.ps1 stage    designs\out\*.pes
```

## `library/` — third-party designs

Purchased and downloaded designs. **Don't edit these in place** — the original
stays intact for re-download comparison and licence provenance. Keep the
vendor's licence or a note of the terms alongside anything you might sell items
from; most commercial designs are personal-use only.

Validate everything you download; free-design sites are inconsistent about
stated sizes:

```powershell
.\stitch.ps1 validate designs\library\*.pes
```

Library files are deliberately outside the spec system — they have no source and
no build, so `audit` ignores them.

## Naming

Machine-safe characters only — `A-Z a-z 0-9 - _` — and **spell things out**.
The convention here is `<Design>_<variant>_on_<background>`:

```
LemonCat_solid_on_white       LemonCat_outline_on_yellow
LemonCat_solid_on_black       LemonCat_outline_on_black
IHeartScreaming_on_white      IHeartScreaming_on_black
```

The stem says what the design *is* and the suffix says what it is built to sit
on. Both halves earn their place: `LemonCat_solid_on_white` and
`LemonCat_solid_on_black` are the same artwork with the eyes stitched white
rather than left as cloth, and nothing but the suffix distinguishes them.

> **This used to say the opposite** — "keep it short, the on-screen list
> truncates", with `rose4x4` held up as better than a descriptive name, and
> `validate` enforced it at 8 characters. **There is no such limit.** A full-text
> search of all four manuals finds no filename length or truncation rule, and the
> embroidery retrieve screen selects patterns from a *thumbnail grid* — the
> settings screen offers thumbnail size and thumbnail background colour (p.15).
> Filenames only drive selection for `.dst`, which carries no thumbnail. The
> guideline now lives in `machine-profile.json` as `usb.filename_long_chars`,
> set where a descriptive name does not trip it.

The spec filename, the `name` field and the `.pes` all have to agree; `build`
refuses a spec whose name does not match its filename, because a mismatch is how
you end up with two files claiming to be the same design.

**Reusing a name changes what the machine already holds.** A wireless transfer
lands in the volatile pocket and does *not* overwrite a copy saved to machine
memory under the same name. If you rebuild a design with different geometry,
delete the old copy from machine memory first, or you will stitch the old one
without knowing.
