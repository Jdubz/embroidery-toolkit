# Software Landscape

## The short version

**Ink/Stitch + Inkscape** for digitizing, this repo's Python toolkit for
generation and validation, **Design Database Transfer** for wireless. Total
cost: nothing. Add **Embrilliance Essentials** (~$139) if you want a friendly
GUI for editing and merging bought designs.

---

## Free / open source

### Ink/Stitch — <https://inkstitch.org>  ← INSTALLED, and the primary digitizer

An Inkscape extension, and the serious free digitizing option. Cross-platform,
actively developed, [source on GitHub](https://github.com/inkstitch/inkstitch).

**Installed here:** Inkscape 1.4.4 at `C:\Program Files\Inkscape\bin\inkscape.exe`,
Ink/Stitch 3.3.0 at
`%APPDATA%\inkscape\extensions\inkstitch\inkstitch\bin\inkstitch.exe`. It is
driven **headless** by `tools/inkstitch_pipeline.ps1` — no GUI, no manual
Inkscape work. See `11-inkstitch-pipeline.md` for the mechanics and
`12-design-generation-playbook.md` for the procedure.

It replaced this repo's own tracer for new work. On the same artwork it cut
jumps 178 → 27 and hand-snipping 12 min → 2.

- Writes **PES**, DST, EXP, JEF, PEC, VP3, U01, XXX and more
- Real control over stitch density, pull compensation, underlay, and pathing
- Built-in **simulator** — watch the stitch order before committing thread
- Lettering, fills, satin columns, running stitch

Caveats, all of which the pipeline now handles for you: it is a digitizing tool,
not a converter — there is no reliable "PNG in, embroidery out" button. Its PES
output is generic rather than tuned to Brother's quirks: **it writes the hoop
code as 130×180 regardless of design size**, so always finish with
`stitch fix-pes`. And driving it headless has real traps (GUI-subsystem binary,
modal dialogs that block forever, extensions that exit 0 having done nothing) —
`11-inkstitch-pipeline.md` documents them.

**Workflow here:** `tools/inkstitch_pipeline.ps1` end to end, then the gates in
`12-design-generation-playbook.md`. The manual route — design in Inkscape,
assign params, simulate, `File → Save a Copy` → `.pes` — still works if you want
hands-on control.

### pyembroidery — <https://github.com/EmbroidePy/pyembroidery>
The Python library this repo's `tools/` are built on. Reads ~46 formats, writes
~19. Native unit is 1/10 mm. Use it when you want designs *generated* — from
data, parametrically, in bulk — rather than drawn.

```powershell
.venv\Scripts\python.exe tools\examples\generate_monogram_frame.py
```

### Others
- **Wilcom TrueSizer** (free, web + Windows) — solid format converter and viewer.
  Good second opinion when a file looks wrong.
- **Embroidermodder / libembroidery** — format-level tooling; more useful for
  understanding formats than for daily work.
- **Inkscape** — needed for Ink/Stitch regardless; also the right place to build
  the vector sources that live in `designs/source/`.

---

## Commercial

### Brother PE-DESIGN 11
Brother's own package. Deep Brother integration, PhotoStitch, Auto Punch,
Intelligent Color Sort, 1000+ designs, 130 fonts, and wireless transfer to the
SE700 built in.

**Street price is roughly $1,000–$2,000 depending on dealer** — several times
what the machine cost. Justifiable for a business doing volume, hard to justify
alongside a 4×4 hobby machine. Buy it because you want PhotoStitch and dealer
support, not because you think you need it for compatibility. You don't.

### Embrilliance Essentials — ~$139 (bundle ~$199)
The pragmatic middle. Windows **and Mac**. Edit, resize, merge, monogram, add
lettering. Modular: buy StitchArtist separately if you later want to digitize
from scratch. **Embrilliance Express** is a free viewer/basic-edit tier — worth
installing just to preview purchased designs.

Essentials does *not* digitize from images. That's StitchArtist's job.

### Hatch (Wilcom)
Subscription, professional-grade, and considerably more machine than a 4×4 hoop
warrants. Note it if you ever move up to a multi-needle.

---

## Choosing

| You want to… | Use |
|---|---|
| Draw a design from scratch, free | Ink/Stitch + Inkscape |
| Generate designs from code or data | pyembroidery + `tools/` here |
| Resize / merge / letter bought designs | Embrilliance Essentials |
| Just look at a file | Embrilliance Express or Wilcom TrueSizer |
| Convert JEF/EXP/VP3 → PES | `.\stitch.ps1 convert` |
| Turn a photo into embroidery | PE-DESIGN (PhotoStitch) or Embrilliance StitchArtist |
| Push designs over WiFi | Design Database Transfer (free) |

---

## What none of them do

**Auto-digitizing from a raster image is not a solved problem.** Every "JPG to
PES in one click" service — free or paid — produces stitch files that look
plausible on screen and stitch badly: wrong densities, no underlay, thread
breaks, puckering. Vector art digitized deliberately beats auto-traced raster
every time. Budget the learning time or pay a human digitizer for anything that
matters.
